from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.provider_registry import ProviderAdapterError
from src.domain.nexus.provider_runtime import (
    ProviderAttemptResult,
    ProviderDescriptor,
    ProviderInvocation,
)
from src.infrastructure.providers.pricing import TokenPricing


class OpenAIResponsesAdapter:
    """Closed TEXT-only OpenAI Responses adapter for NexusProviderRuntime.

    The API key is supplied only through the infrastructure credential callback and is
    never represented in ProviderInvocation, ExecutionPermit, provider output, or audit.
    Responses are created with persistence disabled and without tool definitions.
    """

    provider_id = "openai_responses"
    _INPUT_ACCOUNTING_OVERHEAD_UNITS = 32

    def __init__(
        self,
        *,
        model: str,
        pricing: TokenPricing,
        api_key_supplier: Callable[[], str] | None = None,
        client_factory: Callable[[str], Any] | None = None,
        adapter_version: str = "openai-python-2.38.0",
    ) -> None:
        if not model.strip():
            raise ValueError("OpenAI adapter requires an exact model")
        self._model = model.strip()
        self._pricing = pricing
        self._api_key_supplier = api_key_supplier
        self._client_factory = client_factory
        self._adapter_version = adapter_version

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id=self.provider_id,
            adapter_version=self._adapter_version,
            capabilities=("generate.text",),
            effect_class="READ_EXTERNAL",
            network_required=True,
            credentials_required=True,
            live_provider=True,
            supported_modalities=("TEXT",),
        )

    def _client(self, *, timeout_seconds: int):
        if self._api_key_supplier is None:
            raise ProviderAdapterError(
                "OpenAI credential boundary is unavailable",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        api_key = self._api_key_supplier()
        if not api_key.strip():
            raise ProviderAdapterError(
                "OpenAI project API key is unavailable",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        if self._client_factory is not None:
            client = self._client_factory(api_key)
            api_key = ""
            return client
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency validation covers this
            api_key = ""
            raise ProviderAdapterError(
                "openai dependency is unavailable",
                attempted=False,
                outcome_known=True,
                status="failed",
            ) from exc
        client = OpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=float(timeout_seconds),
        )
        api_key = ""
        return client

    @staticmethod
    def _usage(response: Any) -> tuple[int, int, int, bool]:
        usage = getattr(response, "usage", None)
        if usage is None:
            raise ProviderAdapterError(
                "OpenAI response omitted usage metadata",
                attempted=True,
                outcome_known=False,
                status="indeterminate",
            )
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total = int(getattr(usage, "total_tokens", 0) or 0)
        if input_tokens < 0 or output_tokens < 0 or total < 0:
            raise ProviderAdapterError(
                "OpenAI response usage metadata is invalid",
                attempted=True,
                outcome_known=False,
                status="indeterminate",
            )
        component_total = input_tokens + output_tokens
        if component_total <= 0:
            raise ProviderAdapterError(
                "OpenAI response usage is not measurable",
                attempted=True,
                outcome_known=False,
                status="indeterminate",
            )
        return input_tokens, output_tokens, component_total, total == component_total

    def invoke(self, invocation: ProviderInvocation) -> ProviderAttemptResult:
        if invocation.provider_id != self.provider_id:
            raise ProviderAdapterError(
                "OpenAI invocation provider_id mismatch",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        if invocation.capability != "generate.text":
            raise ProviderAdapterError(
                "OpenAI adapter supports generate.text only",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        if invocation.model_or_resource != self._model:
            raise ProviderAdapterError(
                "OpenAI model is not the configured exact resource",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        if not invocation.input_payload:
            raise ProviderAdapterError(
                "OpenAI invocation requires non-empty input_payload",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        conservative_input_units = (
            len(invocation.input_payload.encode("utf-8"))
            + self._INPUT_ACCOUNTING_OVERHEAD_UNITS
        )
        if conservative_input_units > invocation.maximum_input_units:
            raise ProviderAdapterError(
                "OpenAI input exceeds its pre-authorized input ceiling",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        worst_case_cost = self._pricing.cost_cad(
            input_tokens=invocation.maximum_input_units,
            output_tokens=invocation.maximum_output_units,
        )
        if worst_case_cost > invocation.maximum_cost_cad:
            raise ProviderAdapterError(
                "OpenAI worst-case token cost exceeds its pre-authorized cost ceiling",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        try:
            client = self._client(timeout_seconds=invocation.request_timeout_seconds)
        except ProviderAdapterError:
            raise
        except Exception as exc:
            raise ProviderAdapterError(
                f"OpenAI credential/client initialization failed: {type(exc).__name__}",
                attempted=False,
                outcome_known=True,
                status="failed",
            ) from None

        started = perf_counter()
        try:
            response = client.responses.create(
                model=self._model,
                input=invocation.input_payload,
                max_output_tokens=invocation.maximum_output_units,
                store=False,
                timeout=float(invocation.request_timeout_seconds),
            )
        except Exception as exc:
            raise ProviderAdapterError(
                f"OpenAI provider request failed: {type(exc).__name__}",
                attempted=True,
                outcome_known=False,
                status="indeterminate",
            ) from None
        latency_ms = max(0, int((perf_counter() - started) * 1000))
        input_tokens, output_tokens, total, usage_consistent = self._usage(response)
        cost = self._pricing.cost_cad(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        response_id = str(getattr(response, "id", "") or "") or None
        status = str(getattr(response, "status", "") or "").strip().lower()
        text = str(getattr(response, "output_text", "") or "")
        observed_model = str(getattr(response, "model", "") or "") or self._model
        response_digest = canonical_sha256({"text": text}) if text else None
        if not usage_consistent:
            return ProviderAttemptResult(
                invocation_id=invocation.invocation_id,
                provider_id=self.provider_id,
                status="indeterminate",
                provider_request_id=response_id,
                model_or_resource=observed_model,
                latency_ms=latency_ms,
                usage_units=total,
                input_usage_units=input_tokens,
                output_usage_units=output_tokens,
                cost_cad=cost,
                cost_known=False,
                finish_status="openai_usage_total_mismatch",
                response_digest=response_digest,
                response_payload=None,
                external_action_performed=True,
                outcome_known=False,
            )
        if status != "completed":
            return ProviderAttemptResult(
                invocation_id=invocation.invocation_id,
                provider_id=self.provider_id,
                status="failed",
                provider_request_id=response_id,
                model_or_resource=observed_model,
                latency_ms=latency_ms,
                usage_units=total,
                input_usage_units=input_tokens,
                output_usage_units=output_tokens,
                cost_cad=cost,
                finish_status=f"openai_{status or 'unknown'}",
                response_digest=response_digest,
                response_payload=None,
                external_action_performed=True,
                outcome_known=True,
            )
        if not text:
            return ProviderAttemptResult(
                invocation_id=invocation.invocation_id,
                provider_id=self.provider_id,
                status="failed",
                provider_request_id=response_id,
                model_or_resource=observed_model,
                latency_ms=latency_ms,
                usage_units=total,
                input_usage_units=input_tokens,
                output_usage_units=output_tokens,
                cost_cad=cost,
                finish_status="openai_completed_empty",
                response_digest=None,
                response_payload=None,
                external_action_performed=True,
                outcome_known=True,
            )
        return ProviderAttemptResult(
            invocation_id=invocation.invocation_id,
            provider_id=self.provider_id,
            status="succeeded",
            provider_request_id=response_id,
            model_or_resource=observed_model,
            latency_ms=latency_ms,
            usage_units=total,
            input_usage_units=input_tokens,
            output_usage_units=output_tokens,
            cost_cad=cost,
            finish_status="completed",
            response_digest=response_digest,
            response_payload=text,
            external_action_performed=True,
            outcome_known=True,
        )
