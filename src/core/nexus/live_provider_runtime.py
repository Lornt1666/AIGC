from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import FrozenSet

from src.core.nexus.provider_registry import ProviderAdapterError
from src.core.nexus.provider_runtime import (
    InvocationAlreadyInProgress,
    NexusProviderRuntime,
    PermitValidationError,
    ProviderEffectClassMismatch,
    ProviderExecutionBlocked,
    RuntimeControlUnavailable,
    provider_request_digest,
)
from src.domain.nexus.contracts import ExecutionPermit
from src.domain.nexus.provider_runtime import (
    ProviderAttemptResult,
    ProviderRuntimeAudit,
    ProviderRuntimeExecution,
)


@dataclass(frozen=True)
class LiveProviderExecutionPolicy:
    allowed_provider_ids: FrozenSet[str]
    allow_live_providers: bool = False
    allow_network: bool = False
    allow_credentials: bool = False
    require_durable_control_store: bool = True

    def __post_init__(self) -> None:
        if not self.allowed_provider_ids:
            raise ValueError("live provider policy requires an explicit provider allowlist")
        if self.allow_credentials and not self.allow_network:
            raise ValueError("credentialed live providers require network authorization")
        if self.allow_network and not self.allow_live_providers:
            raise ValueError("network authorization requires live provider authorization")


class GovernedLiveNexusProviderRuntime(NexusProviderRuntime):
    """Explicit live-provider evolution of the default fail-closed Nexus runtime.

    The base `NexusProviderRuntime` continues to reject live/network/credentialed
    adapters. This subclass admits them only under an explicit provider policy, an
    actual canonical ExecutionPermit, and (by default) a durable control store.
    """

    def __init__(self, *, execution_policy: LiveProviderExecutionPolicy, **kwargs) -> None:
        super().__init__(**kwargs)
        self._execution_policy = execution_policy

    def execute(
        self,
        invocation,
        *,
        authoritative_now,
        permit: ExecutionPermit | None = None,
    ) -> ProviderRuntimeExecution:
        if authoritative_now.tzinfo is None or authoritative_now.utcoffset() is None:
            raise ValueError("authoritative_now must be timezone-aware")
        expected_digest = provider_request_digest(invocation)
        if invocation.request_digest != expected_digest:
            raise ProviderExecutionBlocked("provider request digest mismatch")

        try:
            adapter = self._registry.resolve(invocation.provider_id)
        except LookupError as exc:
            raise ProviderExecutionBlocked(str(exc)) from exc
        descriptor = adapter.descriptor()
        if adapter.provider_id != descriptor.provider_id:
            raise ProviderExecutionBlocked("provider adapter/descriptor identity mismatch")
        if invocation.capability not in descriptor.capabilities:
            raise ProviderExecutionBlocked("provider capability is not registered")
        if invocation.requested_effect_class != descriptor.effect_class:
            raise ProviderEffectClassMismatch(
                "caller-supplied effect class conflicts with trusted provider descriptor"
            )
        if descriptor.provider_id not in self._execution_policy.allowed_provider_ids:
            raise ProviderExecutionBlocked("provider is not in the live execution allowlist")
        if descriptor.live_provider and not self._execution_policy.allow_live_providers:
            raise ProviderExecutionBlocked("live provider execution is not authorized")
        if descriptor.network_required and not self._execution_policy.allow_network:
            raise ProviderExecutionBlocked("provider network execution is not authorized")
        if descriptor.credentials_required and not self._execution_policy.allow_credentials:
            raise ProviderExecutionBlocked("provider credential use is not authorized")
        if descriptor.live_provider or descriptor.network_required or descriptor.credentials_required:
            if permit is None:
                raise PermitValidationError("live provider execution requires an actual ExecutionPermit")

        health = self._control_store.healthcheck()
        if not health.ok:
            raise RuntimeControlUnavailable("runtime control store health is not OK")
        if self._execution_policy.require_durable_control_store and not health.durable:
            raise RuntimeControlUnavailable("live provider execution requires durable runtime controls")

        self._limits.validate_invocation(invocation)
        if invocation.permit_id is not None and permit is None:
            raise PermitValidationError(
                "permit_id reference is insufficient without the actual ExecutionPermit"
            )
        if permit is not None:
            self._validate_permit(invocation, permit, authoritative_now)

        action_intent = self._action_intent(
            invocation=invocation,
            descriptor_effect_class=descriptor.effect_class,
            credentials_required=descriptor.credentials_required,
            permit=permit,
        )
        from src.core.nexus.autonomy_policy import assess_autonomy
        assessment = assess_autonomy(action_intent)
        if assessment.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY":
            raise ProviderExecutionBlocked("material consequence requires explicit authority")
        if assessment.disposition == "READ_ONLY_RECONCILIATION":
            raise ProviderExecutionBlocked("indeterminate consequence requires reconciliation")
        if assessment.disposition == "AUTONOMOUS_WITHIN_EXISTING_AUTHORITY" and permit is None:
            raise PermitValidationError(
                "material execution requires the actual validated ExecutionPermit"
            )

        permit_maximum = permit.maximum_invocations if permit is not None else None
        reservation = self._control_store.reserve_invocation(
            invocation=invocation,
            limits=self._limits,
            permit_maximum_invocations=permit_maximum,
        )
        if reservation.replayed:
            prior = self._control_store.get_execution_result(reservation.invocation_id)
            if prior is None:
                raise InvocationAlreadyInProgress(
                    "idempotent invocation is already reserved or executing"
                )
            return prior.model_copy(update={"replayed": True})

        self._control_store.mark_executing(
            invocation_id=reservation.invocation_id,
            expected_epoch=reservation.stop_epoch,
        )
        attempt = self._invoke_live_adapter(adapter, invocation)
        self._validate_attempt(invocation, descriptor.provider_id, attempt)
        receipt = self._receipt(invocation, attempt)
        attempted = attempt.status != "not_started"
        external = bool(attempt.external_action_performed)
        audit = ProviderRuntimeAudit(
            adapter_invocations=1,
            provider_api_calls_performed=1 if attempted and descriptor.live_provider else 0,
            network_calls_performed=1 if attempted and descriptor.network_required else 0,
            credentials_used=1 if attempted and descriptor.credentials_required else 0,
            external_actions_performed=1 if external else 0,
            spend_cad=attempt.cost_cad,
        )
        result = ProviderRuntimeExecution(
            invocation_id=invocation.invocation_id,
            consequence_assessment=assessment,
            attempt=attempt,
            receipt=receipt,
            audit=audit,
            replayed=False,
        )
        self._control_store.complete_invocation(
            invocation_id=reservation.invocation_id,
            expected_epoch=reservation.stop_epoch,
            result=result,
        )
        return result

    @staticmethod
    def _invoke_live_adapter(adapter, invocation) -> ProviderAttemptResult:
        try:
            return adapter.invoke(invocation)
        except ProviderAdapterError as exc:
            if not exc.attempted:
                return ProviderAttemptResult(
                    invocation_id=invocation.invocation_id,
                    provider_id=invocation.provider_id,
                    status="not_started",
                    provider_request_id=None,
                    model_or_resource=invocation.model_or_resource,
                    latency_ms=0,
                    usage_units=None,
                    cost_cad=Decimal("0.00"),
                    finish_status=f"{type(exc).__name__}:{exc}",
                    response_digest=None,
                    response_payload=None,
                    external_action_performed=False,
                    outcome_known=True,
                )
            status = exc.status if exc.outcome_known else "indeterminate"
            return ProviderAttemptResult(
                invocation_id=invocation.invocation_id,
                provider_id=invocation.provider_id,
                status=status,
                provider_request_id=None,
                model_or_resource=invocation.model_or_resource,
                latency_ms=0,
                usage_units=None,
                cost_cad=Decimal("0.00"),
                finish_status=f"{type(exc).__name__}:{exc}",
                response_digest=None,
                response_payload=None,
                external_action_performed=True,
                outcome_known=exc.outcome_known,
            )
        except Exception as exc:
            return ProviderAttemptResult(
                invocation_id=invocation.invocation_id,
                provider_id=invocation.provider_id,
                status="indeterminate",
                provider_request_id=None,
                model_or_resource=invocation.model_or_resource,
                latency_ms=0,
                usage_units=None,
                cost_cad=Decimal("0.00"),
                finish_status=f"UNCLASSIFIED_LIVE_ADAPTER_EXCEPTION:{type(exc).__name__}",
                response_digest=None,
                response_payload=None,
                external_action_performed=True,
                outcome_known=False,
            )
