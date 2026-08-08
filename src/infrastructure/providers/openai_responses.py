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

    def _client(self):
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
        client = OpenAI(api_key=api_key)
        api_key = ""
        return client

    @staticmethod
    def _usage(response: Any) -> tuple[int, int, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            raise ProviderAdapterError(
                "OpenAI response omitted usage metadata",
                attempted=True,
                outcome_known=True,
                status="failed",
            )
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total = int(getattr(usage, "total_tokens", 0) or 0)
        if total <= 0:
            total = input_tokens + output_tokens
        if total <= 0:
            raise ProviderAdapterError(
                "OpenAI response usage is not measurable",
                attempted=True,
                outcome_known=True,
                status="failed",
            )
        return input_tokens, output_tokens, total

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
        try:
            client = self._client()
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
                store=False,
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            known = isinstance(status_code, int)
            raise ProviderAdapterError(
                f"OpenAI provider request failed: {type(exc).__name__}",
                attempted=True,
                outcome_known=known,
                status="failed" if known else "indeterminate",
            ) from None
        latency_ms = max(0, int((perf_counter() - started) * 1000))
        text = str(getattr(response, "output_text", "") or "")
        if not text:
            raise ProviderAdapterError(
                "OpenAI response contained no output_text",
                attempted=True,
                outcome_known=True,
                status="failed",
            )
        input_tokens, output_tokens, total = self._usage(response)
        cost = self._pricing.cost_cad(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        response_id = str(getattr(response, "id", "") or "") or None
        status = str(getattr(response, "status", "") or "") or "completed"
        return ProviderAttemptResult(
            invocation_id=invocation.invocation_id,
            provider_id=self.provider_id,
            status="succeeded",
            provider_request_id=response_id,
            model_or_resource=self._model,
            latency_ms=latency_ms,
            usage_units=total,
            cost_cad=cost,
            finish_status=status,
            response_digest=canonical_sha256({"text": text}),
            response_payload=text,
            external_action_performed=True,
            outcome_known=True,
        )
