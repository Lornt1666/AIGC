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


class GoogleVertexGeminiAdapter:
    """Closed TEXT-only Vertex/Gemini adapter for NexusProviderRuntime.

    Authentication is deliberately delegated to Google ADC / workload identity. This
    class accepts no API-key field and never places credentials in ProviderInvocation.
    """

    provider_id = "google_vertex_gemini"

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

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from google import genai
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
        )

    @staticmethod
    def _usage(response: Any) -> tuple[int, int, int]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            raise ProviderAdapterError(
                "Gemini response omitted usage metadata",
                attempted=True,
                outcome_known=True,
                status="failed",
            )
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        total = int(getattr(usage, "total_token_count", 0) or 0)
        if total <= 0:
            total = input_tokens + output_tokens
        if total <= 0:
            raise ProviderAdapterError(
                "Gemini response usage is not measurable",
                attempted=True,
                outcome_known=True,
                status="failed",
            )
        return input_tokens, output_tokens, total

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
        if not invocation.input_payload:
            raise ProviderAdapterError(
                "Gemini invocation requires non-empty input_payload",
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
                f"Gemini credential/client initialization failed: {type(exc).__name__}",
                attempted=False,
                outcome_known=True,
                status="failed",
            ) from None

        started = perf_counter()
        try:
            try:
                from google.genai import types
                config = types.GenerateContentConfig(temperature=0.0, tools=[])
            except Exception:
                config = None
            response = client.models.generate_content(
                model=self._model,
                contents=invocation.input_payload,
                **({"config": config} if config is not None else {}),
            )
        except Exception as exc:
            code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            known = isinstance(code, int)
            raise ProviderAdapterError(
                f"Gemini provider request failed: {type(exc).__name__}",
                attempted=True,
                outcome_known=known,
                status="failed" if known else "indeterminate",
            ) from None
        latency_ms = max(0, int((perf_counter() - started) * 1000))
        text = str(getattr(response, "text", "") or "")
        if not text:
            raise ProviderAdapterError(
                "Gemini provider returned no text payload",
                attempted=True,
                outcome_known=True,
                status="failed",
            )
        input_tokens, output_tokens, total = self._usage(response)
        cost = self._pricing.cost_cad(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        candidate_status = None
        candidates = getattr(response, "candidates", None) or ()
        if candidates:
            candidate_status = str(getattr(candidates[0], "finish_reason", "") or "") or None
        response_id = str(getattr(response, "response_id", "") or "") or None
        return ProviderAttemptResult(
            invocation_id=invocation.invocation_id,
            provider_id=self.provider_id,
            status="succeeded",
            provider_request_id=response_id,
            model_or_resource=self._model,
            latency_ms=latency_ms,
            usage_units=total,
            cost_cad=cost,
            finish_status=candidate_status or "completed",
            response_digest=canonical_sha256({"text": text}),
            response_payload=text,
            external_action_performed=True,
            outcome_known=True,
        )
