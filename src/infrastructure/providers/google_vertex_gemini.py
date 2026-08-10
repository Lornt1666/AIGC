from __future__ import annotations

from decimal import Decimal
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


THINKING_DISABLED_GEMINI_MODELS = frozenset(
    {"gemini-2.5-flash", "gemini-2.5-flash-lite"}
)


class GoogleVertexGeminiAdapter:
    """Closed TEXT-only Vertex/Gemini adapter for NexusProviderRuntime.

    Authentication is deliberately delegated to Google ADC / workload identity. This
    class accepts no API-key field and never places credentials in ProviderInvocation.
    """

    provider_id = "google_vertex_gemini"
    _INPUT_ACCOUNTING_OVERHEAD_UNITS = 32

    def __init__(
        self,
        *,
        project: str,
        location: str,
        model: str,
        pricing: TokenPricing,
        client_factory: Callable[[], Any] | None = None,
        adapter_version: str = "google-genai-2.6.0",
    ) -> None:
        if not project.strip() or not location.strip() or not model.strip():
            raise ValueError("Google Vertex provider requires project, location, and model")
        self._project = project.strip()
        self._location = location.strip()
        self._model = model.strip()
        self._pricing = pricing
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
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - dependency validation covers this
            raise ProviderAdapterError(
                "google-genai dependency is unavailable",
                attempted=False,
                outcome_known=True,
                status="failed",
            ) from exc
        return genai.Client(
            vertexai=True,
            project=self._project,
            location=self._location,
            http_options=types.HttpOptions(
                api_version="v1",
                timeout=timeout_seconds * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    @staticmethod
    def _usage(response: Any) -> tuple[int, int, int, int, bool]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            raise ProviderAdapterError(
                "Gemini response omitted usage metadata",
                attempted=True,
                outcome_known=False,
                status="indeterminate",
            )
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        candidate_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        thought_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)
        tool_input_tokens = int(
            getattr(usage, "tool_use_prompt_token_count", 0) or 0
        )
        total = int(getattr(usage, "total_token_count", 0) or 0)
        if any(
            value < 0
            for value in (
                prompt_tokens,
                candidate_tokens,
                thought_tokens,
                tool_input_tokens,
                total,
            )
        ):
            raise ProviderAdapterError(
                "Gemini response usage metadata is invalid",
                attempted=True,
                outcome_known=False,
                status="indeterminate",
            )
        input_tokens = prompt_tokens + tool_input_tokens
        output_tokens = candidate_tokens + thought_tokens
        component_total = input_tokens + output_tokens
        if component_total <= 0:
            raise ProviderAdapterError(
                "Gemini response usage is not measurable",
                attempted=True,
                outcome_known=False,
                status="indeterminate",
            )
        return (
            input_tokens,
            output_tokens,
            component_total,
            thought_tokens,
            total == component_total,
        )

    def invoke(self, invocation: ProviderInvocation) -> ProviderAttemptResult:
        if invocation.provider_id != self.provider_id:
            raise ProviderAdapterError(
                "Gemini invocation provider_id mismatch",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        if invocation.capability != "generate.text":
            raise ProviderAdapterError(
                "Gemini adapter supports generate.text only",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        if invocation.model_or_resource != self._model:
            raise ProviderAdapterError(
                "Gemini model is not the configured exact resource",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        if self._model not in THINKING_DISABLED_GEMINI_MODELS:
            raise ProviderAdapterError(
                "Gemini canary model is not in the thinking-disabled allowlist",
                attempted=False,
                outcome_known=True,
                status="failed",
            )
        if not invocation.input_payload:
            raise ProviderAdapterError(
                "Gemini invocation requires non-empty input_payload",
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
                "Gemini input exceeds its pre-authorized input ceiling",
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
                "Gemini worst-case token cost exceeds its pre-authorized cost ceiling",
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
                f"Gemini credential/client initialization failed: {type(exc).__name__}",
                attempted=False,
                outcome_known=True,
                status="failed",
            ) from None

        started = perf_counter()
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=invocation.input_payload,
                config={
                    "temperature": 0.0,
                    "tools": [],
                    "automatic_function_calling": {"disable": True},
                    "max_output_tokens": invocation.maximum_output_units,
                    "thinking_config": {
                        "thinking_budget": 0,
                        "include_thoughts": False,
                    },
                    "http_options": {
                        "timeout": invocation.request_timeout_seconds * 1000,
                        "retry_options": {"attempts": 1},
                    },
                },
            )
        except Exception as exc:
            raise ProviderAdapterError(
                f"Gemini provider request failed: {type(exc).__name__}",
                attempted=True,
                outcome_known=False,
                status="indeterminate",
            ) from None
        latency_ms = max(0, int((perf_counter() - started) * 1000))
        (
            input_tokens,
            output_tokens,
            total,
            thought_tokens,
            usage_consistent,
        ) = self._usage(response)
        cost = self._pricing.cost_cad(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        candidate_status = "UNKNOWN"
        candidates = getattr(response, "candidates", None) or ()
        if candidates:
            raw_finish = getattr(candidates[0], "finish_reason", "")
            candidate_status = str(getattr(raw_finish, "value", raw_finish) or "UNKNOWN")
            candidate_status = candidate_status.rsplit(".", 1)[-1].upper()
        response_id = str(getattr(response, "response_id", "") or "") or None
        observed_model = str(getattr(response, "model_version", "") or "") or self._model
        text = str(getattr(response, "text", "") or "")
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
                finish_status="gemini_usage_total_mismatch",
                response_digest=response_digest,
                response_payload=None,
                external_action_performed=True,
                outcome_known=False,
            )
        if thought_tokens:
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
                finish_status="gemini_unexpected_thinking",
                response_digest=response_digest,
                response_payload=None,
                external_action_performed=True,
                outcome_known=True,
            )
        if candidate_status != "STOP":
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
                finish_status=f"gemini_{candidate_status.lower()}",
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
                finish_status="gemini_stop_empty",
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
            finish_status="STOP",
            response_digest=response_digest,
            response_payload=text,
            external_action_performed=True,
            outcome_known=True,
        )
