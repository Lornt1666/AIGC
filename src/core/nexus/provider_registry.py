from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.provider_runtime import (
    ProviderAttemptResult,
    ProviderDescriptor,
    ProviderInvocation,
)


ProviderAdapterFailureStatus = Literal["failed", "timed_out", "indeterminate"]


class ProviderAdapterError(RuntimeError):
    """Normalized adapter failure with explicit attempt/outcome semantics."""

    def __init__(
        self,
        message: str,
        *,
        attempted: bool,
        outcome_known: bool,
        status: ProviderAdapterFailureStatus = "failed",
    ) -> None:
        super().__init__(message)
        if not attempted and not outcome_known:
            raise ValueError("a non-attempted provider operation has a known not-started outcome")
        if status == "indeterminate" and outcome_known:
            raise ValueError("indeterminate adapter failure requires outcome_known=false")
        if not outcome_known and status != "indeterminate":
            raise ValueError("unknown provider outcome must use status=indeterminate")
        self.attempted = attempted
        self.outcome_known = outcome_known
        self.status = status


class ProviderAdapter(Protocol):
    @property
    def provider_id(self) -> str: ...

    def descriptor(self) -> ProviderDescriptor: ...

    def invoke(self, invocation: ProviderInvocation) -> ProviderAttemptResult: ...


class ProviderRegistry:
    """Explicit provider registry; performs no discovery or dynamic imports."""

    def __init__(self, adapters: tuple[ProviderAdapter, ...]) -> None:
        by_id: dict[str, ProviderAdapter] = {}
        for adapter in adapters:
            descriptor = adapter.descriptor()
            if adapter.provider_id != descriptor.provider_id:
                raise ValueError("provider adapter identity does not match descriptor")
            if descriptor.provider_id in by_id:
                raise ValueError(f"duplicate provider registration: {descriptor.provider_id}")
            by_id[descriptor.provider_id] = adapter
        self._adapters = by_id

    def resolve(self, provider_id: str) -> ProviderAdapter:
        try:
            return self._adapters[provider_id]
        except KeyError as exc:
            raise LookupError(f"unknown provider: {provider_id}") from exc

    def descriptor(self, provider_id: str) -> ProviderDescriptor:
        return self.resolve(provider_id).descriptor()

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


@dataclass
class OfflineDeterministicProviderAdapter:
    """Deterministic provider fixture; never performs provider/network/credential work."""

    capability: str = "deterministic.generate"
    model_label: str = "offline-deterministic-provider-not-live"
    invocation_count: int = 0

    @property
    def provider_id(self) -> str:
        return "offline_deterministic"

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id=self.provider_id,
            adapter_version="1.0.0",
            capabilities=(self.capability,),
            effect_class="PURE",
            network_required=False,
            credentials_required=False,
            live_provider=False,
            supported_modalities=("TEXT",),
        )

    def invoke(self, invocation: ProviderInvocation) -> ProviderAttemptResult:
        if invocation.provider_id != self.provider_id:
            raise ProviderAdapterError(
                "offline adapter received mismatched provider_id",
                attempted=False,
                outcome_known=True,
            )
        if invocation.capability != self.capability:
            raise ProviderAdapterError(
                "offline adapter does not support requested capability",
                attempted=False,
                outcome_known=True,
            )
        self.invocation_count += 1
        input_digest = canonical_sha256({"input_payload": invocation.input_payload})
        payload = (
            "OFFLINE DETERMINISTIC PROVIDER RESULT — NOT A LIVE PROVIDER\n"
            f"input_digest={input_digest}\n"
            f"request_digest={invocation.request_digest}\n"
            f"capability={invocation.capability}\n"
            f"model={self.model_label}\n"
            "UNTRUSTED_PROVIDER_INPUT_ECHO:\n"
            f"{invocation.input_payload}"
        )
        response_digest = canonical_sha256({"response_payload": payload})
        return ProviderAttemptResult(
            invocation_id=invocation.invocation_id,
            provider_id=self.provider_id,
            status="succeeded",
            provider_request_id=None,
            model_or_resource=self.model_label,
            latency_ms=0,
            usage_units=invocation.reserved_usage_units,
            input_usage_units=invocation.maximum_input_units,
            output_usage_units=invocation.maximum_output_units,
            cost_cad=Decimal("0.00"),
            finish_status="offline_complete",
            response_digest=response_digest,
            response_payload=payload,
            external_action_performed=False,
            outcome_known=True,
        )
