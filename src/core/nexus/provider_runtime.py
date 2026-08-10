from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import threading
from typing import Callable, Protocol

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.autonomy_policy import assess_autonomy
from src.core.nexus.provider_registry import (
    ProviderAdapterError,
    ProviderRegistry,
)
from src.domain.nexus.autonomy import ActionIntent
from src.domain.nexus.contracts import (
    ExecutionPermit,
    ExecutionReceipt,
    OperationReceipt,
)
from src.domain.nexus.provider_runtime import (
    InvocationReservation,
    ProviderAttemptResult,
    ProviderInvocation,
    ProviderRuntimeAudit,
    ProviderRuntimeExecution,
    ProviderRuntimeLimits,
    RuntimeEmergencyState,
)


class ProviderRuntimeError(RuntimeError):
    pass


class ProviderExecutionBlocked(ProviderRuntimeError):
    pass


class ProviderEffectClassMismatch(ProviderRuntimeError):
    pass


class RuntimeControlUnavailable(ProviderRuntimeError):
    pass


class EmergencyStopActive(ProviderRuntimeError):
    pass


class StaleControlEpoch(ProviderRuntimeError):
    pass


class IdempotencyConflict(ProviderRuntimeError):
    pass


class InvocationAlreadyInProgress(ProviderRuntimeError):
    pass


class RuntimeLimitExceeded(ProviderRuntimeError):
    pass


class UsageBudgetExceeded(ProviderRuntimeError):
    pass


class PermitValidationError(ProviderRuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeControlHealth:
    ok: bool
    durable: bool
    backend: str
    emergency_active: bool
    stop_epoch: int


class RuntimeControlStore(Protocol):
    def get_emergency_state(self) -> RuntimeEmergencyState: ...

    def reserve_invocation(
        self,
        *,
        invocation: ProviderInvocation,
        limits: ProviderRuntimeLimits,
        permit_maximum_invocations: int | None,
    ) -> InvocationReservation: ...

    def get_invocation(self, invocation_id: str) -> InvocationReservation: ...

    def get_execution_result(self, invocation_id: str) -> ProviderRuntimeExecution | None: ...

    def assert_epoch_current(self, *, invocation_id: str, expected_epoch: int) -> None: ...

    def mark_executing(
        self,
        *,
        invocation_id: str,
        expected_epoch: int,
    ) -> InvocationReservation: ...

    def complete_invocation(
        self,
        *,
        invocation_id: str,
        expected_epoch: int,
        result: ProviderRuntimeExecution,
    ) -> InvocationReservation: ...

    def record_reconciliation_result(
        self,
        *,
        invocation_id: str,
        result: ProviderRuntimeExecution,
    ) -> InvocationReservation: ...

    def fail_invocation(
        self,
        *,
        invocation_id: str,
        reason: str,
    ) -> InvocationReservation: ...

    def healthcheck(self) -> RuntimeControlHealth: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _minute_start(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)


def _day_start(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


class InMemoryRuntimeControlStore:
    """Thread-safe semantic control store for tests only; never production proof."""

    def __init__(self, *, clock: Callable[[], datetime] = _utc_now) -> None:
        self._clock = clock
        now = self._now()
        self._emergency = RuntimeEmergencyState(
            active=False,
            stop_epoch=0,
            reason="",
            actor_principal_id=None,
            updated_at=now,
        )
        self._reservations: dict[str, InvocationReservation] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._results: dict[str, ProviderRuntimeExecution] = {}
        self._usage: dict[tuple[str, str, str, datetime], dict[str, int]] = {}
        self._permit_counts: dict[str, int] = {}
        self._lock = threading.RLock()
        self._available = True

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeControlUnavailable("runtime-control clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    def set_available_for_test(self, available: bool) -> None:
        with self._lock:
            self._available = bool(available)

    def _require_available(self) -> None:
        if not self._available:
            raise RuntimeControlUnavailable("runtime control state is unavailable")

    def get_emergency_state(self) -> RuntimeEmergencyState:
        with self._lock:
            self._require_available()
            return self._emergency

    def activate_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
    ) -> RuntimeEmergencyState:
        normalized = reason.strip()
        if not normalized:
            raise ValueError("emergency-stop reason is required")
        with self._lock:
            self._require_available()
            self._emergency = RuntimeEmergencyState(
                active=True,
                stop_epoch=self._emergency.stop_epoch + 1,
                reason=normalized,
                actor_principal_id=actor_principal_id,
                updated_at=self._now(),
            )
            return self._emergency

    def clear_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
        expected_epoch: int,
    ) -> RuntimeEmergencyState:
        normalized = reason.strip()
        if not normalized:
            raise ValueError("emergency-stop clear reason is required")
        with self._lock:
            self._require_available()
            if not self._emergency.active:
                raise ProviderRuntimeError("emergency stop is not active")
            if self._emergency.stop_epoch != expected_epoch:
                raise StaleControlEpoch("emergency-stop clear used stale epoch")
            self._emergency = RuntimeEmergencyState(
                active=False,
                stop_epoch=self._emergency.stop_epoch + 1,
                reason=normalized,
                actor_principal_id=actor_principal_id,
                updated_at=self._now(),
            )
            return self._emergency

    def reserve_invocation(
        self,
        *,
        invocation: ProviderInvocation,
        limits: ProviderRuntimeLimits,
        permit_maximum_invocations: int | None,
    ) -> InvocationReservation:
        limits.validate_invocation(invocation)
        with self._lock:
            self._require_available()
            if self._emergency.active:
                raise EmergencyStopActive(
                    f"provider runtime is stopped at epoch {self._emergency.stop_epoch}"
                )

            idempotency_key = (invocation.principal, invocation.idempotency_key)
            existing_id = self._idempotency.get(idempotency_key)
            if existing_id is not None:
                existing = self._reservations[existing_id]
                if existing.request_digest != invocation.request_digest:
                    raise IdempotencyConflict(
                        "idempotency key is already bound to a different request digest"
                    )
                return existing.model_copy(update={"replayed": True})

            if invocation.invocation_id in self._reservations:
                raise IdempotencyConflict("invocation_id is already reserved")

            if invocation.permit_id is not None and permit_maximum_invocations is not None:
                used = self._permit_counts.get(invocation.permit_id, 0)
                if used >= permit_maximum_invocations:
                    raise RuntimeLimitExceeded("ExecutionPermit maximum_invocations exhausted")

            now = self._now()
            minute = _minute_start(now)
            day = _day_start(now)
            windows = (
                (
                    "principal",
                    invocation.principal,
                    "minute",
                    minute,
                    limits.principal_invocations_per_minute,
                    None,
                ),
                (
                    "global",
                    "*",
                    "minute",
                    minute,
                    limits.global_invocations_per_minute,
                    None,
                ),
                (
                    "principal",
                    invocation.principal,
                    "day",
                    day,
                    limits.principal_invocations_per_day,
                    limits.principal_reserved_usage_per_day,
                ),
                (
                    "global",
                    "*",
                    "day",
                    day,
                    limits.global_invocations_per_day,
                    limits.global_reserved_usage_per_day,
                ),
            )

            for scope_type, scope_id, kind, start, run_limit, usage_limit in windows:
                current = self._usage.get(
                    (scope_type, scope_id, kind, start),
                    {"runs": 0, "reserved_usage": 0},
                )
                if current["runs"] + 1 > run_limit:
                    raise RuntimeLimitExceeded(
                        f"{scope_type} {kind} invocation limit exceeded"
                    )
                if (
                    usage_limit is not None
                    and current["reserved_usage"] + invocation.reserved_usage_units
                    > usage_limit
                ):
                    raise UsageBudgetExceeded(
                        f"{scope_type} daily reserved usage exceeded"
                    )

            for scope_type, scope_id, kind, start, _run_limit, _usage_limit in windows:
                key = (scope_type, scope_id, kind, start)
                current = self._usage.setdefault(
                    key,
                    {"runs": 0, "reserved_usage": 0},
                )
                current["runs"] += 1
                current["reserved_usage"] += invocation.reserved_usage_units

            reservation = InvocationReservation(
                invocation_id=invocation.invocation_id,
                principal=invocation.principal,
                provider_id=invocation.provider_id,
                capability=invocation.capability,
                permit_id=invocation.permit_id,
                idempotency_key=invocation.idempotency_key,
                request_digest=invocation.request_digest,
                exact_revision=invocation.exact_revision,
                stop_epoch=self._emergency.stop_epoch,
                state="reserved",
                reserved_usage_units=invocation.reserved_usage_units,
                actual_usage_units=None,
                created_at=now,
                updated_at=now,
                failure_reason=None,
                replayed=False,
            )
            self._reservations[invocation.invocation_id] = reservation
            self._idempotency[idempotency_key] = invocation.invocation_id
            if invocation.permit_id is not None and permit_maximum_invocations is not None:
                self._permit_counts[invocation.permit_id] = (
                    self._permit_counts.get(invocation.permit_id, 0) + 1
                )
            return reservation

    def get_invocation(self, invocation_id: str) -> InvocationReservation:
        with self._lock:
            self._require_available()
            try:
                return self._reservations[invocation_id]
            except KeyError as exc:
                raise ProviderRuntimeError("runtime invocation reservation not found") from exc

    def get_execution_result(self, invocation_id: str) -> ProviderRuntimeExecution | None:
        with self._lock:
            self._require_available()
            return self._results.get(invocation_id)

    def assert_epoch_current(self, *, invocation_id: str, expected_epoch: int) -> None:
        with self._lock:
            self._require_available()
            reservation = self.get_invocation(invocation_id)
            if self._emergency.active:
                raise EmergencyStopActive(
                    f"provider runtime is stopped at epoch {self._emergency.stop_epoch}"
                )
            if (
                reservation.stop_epoch != expected_epoch
                or self._emergency.stop_epoch != expected_epoch
            ):
                raise StaleControlEpoch(
                    "provider invocation was reserved under a stale control epoch"
                )

    def mark_executing(
        self,
        *,
        invocation_id: str,
        expected_epoch: int,
    ) -> InvocationReservation:
        with self._lock:
            self.assert_epoch_current(
                invocation_id=invocation_id,
                expected_epoch=expected_epoch,
            )
            current = self.get_invocation(invocation_id)
            if current.state == "executing":
                return current.model_copy(update={"replayed": True})
            if current.state != "reserved":
                raise ProviderRuntimeError(
                    f"cannot execute invocation in state {current.state}"
                )
            updated = current.model_copy(
                update={"state": "executing", "updated_at": self._now()}
            )
            self._reservations[invocation_id] = updated
            return updated

    def complete_invocation(
        self,
        *,
        invocation_id: str,
        expected_epoch: int,
        result: ProviderRuntimeExecution,
    ) -> InvocationReservation:
        with self._lock:
            self.assert_epoch_current(
                invocation_id=invocation_id,
                expected_epoch=expected_epoch,
            )
            current = self.get_invocation(invocation_id)
            if current.state not in {"executing"}:
                raise ProviderRuntimeError(
                    f"cannot complete invocation in state {current.state}"
                )
            attempt = result.attempt
            state_map = {
                "succeeded": "completed",
                "failed": "failed",
                "timed_out": "timed_out",
                "indeterminate": "indeterminate",
                "not_started": "failed",
            }
            actual_usage = attempt.usage_units
            updated = current.model_copy(
                update={
                    "state": state_map[attempt.status],
                    "actual_usage_units": actual_usage,
                    "updated_at": self._now(),
                    "failure_reason": (
                        None if attempt.status == "succeeded" else attempt.finish_status
                    ),
                }
            )
            self._reservations[invocation_id] = updated
            self._results[invocation_id] = result
            return updated

    def record_reconciliation_result(
        self,
        *,
        invocation_id: str,
        result: ProviderRuntimeExecution,
    ) -> InvocationReservation:
        """Persist a sanitized terminal result when normal finalization is uncertain."""

        with self._lock:
            self._require_available()
            current = self.get_invocation(invocation_id)
            existing = self._results.get(invocation_id)
            if existing is not None:
                return current
            attempt = result.attempt
            if (
                result.invocation_id != invocation_id
                or attempt.invocation_id != invocation_id
                or attempt.status != "indeterminate"
                or attempt.outcome_known
                or attempt.response_payload is not None
            ):
                raise ProviderRuntimeError(
                    "reconciliation result must be correlated, redacted, and indeterminate"
                )
            if current.state not in {"reserved", "executing", "failed", "indeterminate"}:
                raise ProviderRuntimeError(
                    f"cannot record reconciliation result in state {current.state}"
                )
            updated = current.model_copy(
                update={
                    "state": "indeterminate",
                    "actual_usage_units": attempt.usage_units,
                    "failure_reason": attempt.finish_status,
                    "updated_at": self._now(),
                }
            )
            self._reservations[invocation_id] = updated
            self._results[invocation_id] = result
            return updated

    def fail_invocation(
        self,
        *,
        invocation_id: str,
        reason: str,
    ) -> InvocationReservation:
        with self._lock:
            self._require_available()
            current = self.get_invocation(invocation_id)
            if current.state not in {"reserved", "executing"}:
                return current
            updated = current.model_copy(
                update={
                    "state": "failed",
                    "failure_reason": reason[:2000],
                    "updated_at": self._now(),
                }
            )
            self._reservations[invocation_id] = updated
            return updated

    def healthcheck(self) -> RuntimeControlHealth:
        state = self.get_emergency_state()
        return RuntimeControlHealth(
            ok=True,
            durable=False,
            backend="memory_test_only",
            emergency_active=state.active,
            stop_epoch=state.stop_epoch,
        )


class UnavailableRuntimeControlStore:
    def __init__(self, reason: str = "runtime control store unavailable") -> None:
        self.reason = reason

    def _blocked(self, *_args, **_kwargs):
        raise RuntimeControlUnavailable(self.reason)

    get_emergency_state = _blocked
    reserve_invocation = _blocked
    get_invocation = _blocked
    get_execution_result = _blocked
    assert_epoch_current = _blocked
    mark_executing = _blocked
    complete_invocation = _blocked
    record_reconciliation_result = _blocked
    fail_invocation = _blocked
    healthcheck = _blocked


def provider_request_digest(invocation: ProviderInvocation) -> str:
    """Canonical semantic request digest; authority/idempotency wrappers are excluded."""

    return canonical_sha256(
        invocation.model_dump(
            mode="json",
            exclude={
                "invocation_id",
                "request_digest",
                "idempotency_key",
                "permit_id",
            },
        )
    )


def bind_provider_request_digest(invocation: ProviderInvocation) -> ProviderInvocation:
    return invocation.model_copy(update={"request_digest": provider_request_digest(invocation)})


class NexusProviderRuntime:
    """Provider-neutral execution substrate beneath Nexus governance.

    This runtime performs no credential resolution and introduces no authority
    object. It currently rejects live/network/credential-requiring adapters.
    """

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        control_store: RuntimeControlStore,
        limits: ProviderRuntimeLimits,
    ) -> None:
        self._registry = registry
        self._control_store = control_store
        self._limits = limits

    def execute(
        self,
        invocation: ProviderInvocation,
        *,
        authoritative_now: datetime,
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

        if descriptor.live_provider:
            raise ProviderExecutionBlocked("live providers are disabled in this release gate")
        if descriptor.network_required:
            raise ProviderExecutionBlocked("network-requiring providers are disabled")
        if descriptor.credentials_required:
            raise ProviderExecutionBlocked("credential-requiring providers are disabled")

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
        assessment = assess_autonomy(action_intent)

        if assessment.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY":
            raise ProviderExecutionBlocked("material consequence requires explicit authority")
        if assessment.disposition == "READ_ONLY_RECONCILIATION":
            raise ProviderExecutionBlocked("indeterminate consequence requires reconciliation")
        if (
            assessment.disposition == "AUTONOMOUS_WITHIN_EXISTING_AUTHORITY"
            and permit is None
        ):
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
                if reservation.state not in {"reserved", "executing"}:
                    raise ProviderRuntimeError(
                        "idempotent invocation is terminal without execution evidence; "
                        "manual reconciliation is required"
                    )
                raise InvocationAlreadyInProgress(
                    "idempotent invocation is already reserved or executing"
                )
            return prior.model_copy(update={"replayed": True})

        self._control_store.mark_executing(
            invocation_id=reservation.invocation_id,
            expected_epoch=reservation.stop_epoch,
        )
        attempt = self._invoke_adapter(adapter, invocation)
        try:
            self._validate_attempt(invocation, descriptor.provider_id, attempt)

            receipt = self._receipt(invocation, attempt)
            audit = ProviderRuntimeAudit(
                adapter_invocations=1,
                provider_api_calls_performed=0,
                network_calls_performed=0,
                credentials_used=0,
                external_actions_performed=1 if attempt.external_action_performed else 0,
                spend_cad=attempt.cost_cad,
                spend_known=attempt.cost_known,
            )
            result = ProviderRuntimeExecution(
                invocation_id=invocation.invocation_id,
                consequence_assessment=assessment,
                attempt=attempt,
                receipt=receipt,
                audit=audit,
                replayed=False,
            )
        except Exception as exc:
            self._terminalize_post_attempt_failure(
                invocation=invocation,
                expected_epoch=reservation.stop_epoch,
                assessment=assessment,
                trusted_provider_id=descriptor.provider_id,
                attempt=attempt,
                cause=exc,
                provider_api_calls_performed=0,
                network_calls_performed=0,
                credentials_used=0,
            )
            raise
        try:
            self._control_store.complete_invocation(
                invocation_id=reservation.invocation_id,
                expected_epoch=reservation.stop_epoch,
                result=result,
            )
        except Exception as exc:
            if attempt.status != "not_started":
                self._durably_record_finalization_reconciliation(
                    invocation=invocation,
                    result=result,
                    cause=exc,
                )
            else:
                self._durably_fail_finalization(
                    invocation_id=reservation.invocation_id,
                    cause=exc,
                )
            raise
        return result

    def _validate_permit(
        self,
        invocation: ProviderInvocation,
        permit: ExecutionPermit,
        authoritative_now: datetime,
    ) -> None:
        if invocation.permit_id != permit.permit_id:
            raise PermitValidationError("ExecutionPermit ID does not match invocation")
        permit.verify_temporal_validity(authoritative_now=authoritative_now)
        if permit.principal != invocation.principal:
            raise PermitValidationError("ExecutionPermit principal mismatch")
        if permit.capability != invocation.capability:
            raise PermitValidationError("ExecutionPermit capability mismatch")
        if invocation.resource_ref not in permit.resource_scope:
            raise PermitValidationError("ExecutionPermit resource scope mismatch")
        if permit.exact_revision != invocation.exact_revision:
            raise PermitValidationError("ExecutionPermit exact revision mismatch")
        if permit.request_digest != invocation.request_digest:
            raise PermitValidationError("ExecutionPermit request digest mismatch")

    @staticmethod
    def _action_intent(
        *,
        invocation: ProviderInvocation,
        descriptor_effect_class: str,
        credentials_required: bool,
        permit: ExecutionPermit | None,
    ) -> ActionIntent:
        writes = {
            "WRITE_REVERSIBLE",
            "WRITE_COMPENSATABLE",
            "WRITE_IRREVERSIBLE",
        }
        return ActionIntent(
            intent_id="ACT-" + canonical_sha256(
                {
                    "invocation_id": invocation.invocation_id,
                    "provider_id": invocation.provider_id,
                    "request_digest": invocation.request_digest,
                }
            )[:24].upper(),
            effect_class=descriptor_effect_class,
            public_read_only=False,
            internal_sandbox_only=False,
            accesses_private_data=False,
            credentials_required=credentials_required,
            persistent_internal_mutation=False,
            external_mutation=descriptor_effect_class in writes,
            communication=descriptor_effect_class == "COMMUNICATION",
            financial_spend_cad=invocation.maximum_cost_cad,
            authorized_spend_cad=(
                invocation.maximum_cost_cad if permit is not None else Decimal("0.00")
            ),
            legal_commitment=False,
            security_sensitive=descriptor_effect_class == "SECURITY_SENSITIVE",
            production_change=descriptor_effect_class == "DEPLOYMENT",
            physical_effect=False,
            destructive=descriptor_effect_class == "WRITE_IRREVERSIBLE",
            irreversible=descriptor_effect_class == "WRITE_IRREVERSIBLE",
            outcome_indeterminate=False,
            existing_explicit_authority=permit is not None,
            permit_id=permit.permit_id if permit is not None else None,
        )

    @staticmethod
    def _invoke_adapter(adapter, invocation: ProviderInvocation) -> ProviderAttemptResult:
        try:
            return adapter.invoke(invocation)
        except ProviderAdapterError as exc:
            status = "not_started" if not exc.attempted else exc.status
            return ProviderAttemptResult(
                invocation_id=invocation.invocation_id,
                provider_id=invocation.provider_id,
                status=status,
                provider_request_id=None,
                model_or_resource=invocation.model_or_resource,
                latency_ms=0,
                usage_units=None,
                cost_cad=Decimal("0.00"),
                cost_known=exc.outcome_known,
                finish_status=f"{type(exc).__name__}:{exc}",
                response_digest=None,
                response_payload=None,
                external_action_performed=False if exc.outcome_known else None,
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
                cost_known=False,
                finish_status=f"UNCLASSIFIED_ADAPTER_EXCEPTION:{type(exc).__name__}",
                response_digest=None,
                response_payload=None,
                external_action_performed=None,
                outcome_known=False,
            )

    @staticmethod
    def _validate_attempt(
        invocation: ProviderInvocation,
        trusted_provider_id: str,
        attempt: ProviderAttemptResult,
    ) -> None:
        if attempt.invocation_id != invocation.invocation_id:
            raise ProviderRuntimeError("provider attempt invocation_id mismatch")
        if attempt.provider_id != trusted_provider_id:
            raise ProviderRuntimeError("provider attempt provider_id mismatch")
        if attempt.model_or_resource != invocation.model_or_resource:
            raise ProviderRuntimeError("provider attempt model/resource mismatch")
        if attempt.status == "succeeded" and attempt.usage_units is None:
            raise ProviderRuntimeError("successful provider attempt omitted usage units")
        if (
            attempt.usage_units is not None
            and attempt.usage_units > invocation.reserved_usage_units
        ):
            raise ProviderRuntimeError("provider attempt exceeded reserved usage units")
        if (
            attempt.input_usage_units is not None
            and attempt.input_usage_units > invocation.maximum_input_units
        ):
            raise ProviderRuntimeError("provider attempt exceeded maximum input units")
        if (
            attempt.output_usage_units is not None
            and attempt.output_usage_units > invocation.maximum_output_units
        ):
            raise ProviderRuntimeError("provider attempt exceeded maximum output units")
        if attempt.cost_cad > invocation.maximum_cost_cad:
            raise ProviderRuntimeError("provider attempt exceeded invocation cost ceiling")

    def _terminalize_post_attempt_failure(
        self,
        *,
        invocation: ProviderInvocation,
        expected_epoch: int,
        assessment,
        trusted_provider_id: str,
        attempt: ProviderAttemptResult,
        cause: Exception,
        provider_api_calls_performed: int,
        network_calls_performed: int,
        credentials_used: int,
    ) -> ProviderRuntimeExecution:
        """Persist redacted evidence when a completed adapter boundary fails validation."""

        outcome_indeterminate = attempt.external_action_performed is not False
        safe_attempt = ProviderAttemptResult(
            invocation_id=invocation.invocation_id,
            provider_id=trusted_provider_id,
            status="indeterminate" if outcome_indeterminate else "failed",
            provider_request_id=attempt.provider_request_id,
            model_or_resource=invocation.model_or_resource,
            latency_ms=attempt.latency_ms,
            usage_units=attempt.usage_units,
            input_usage_units=attempt.input_usage_units,
            output_usage_units=attempt.output_usage_units,
            cost_cad=attempt.cost_cad,
            cost_known=attempt.cost_known,
            finish_status=f"POST_PROVIDER_VALIDATION_FAILED:{type(cause).__name__}",
            response_digest=attempt.response_digest,
            response_payload=None,
            external_action_performed=attempt.external_action_performed,
            outcome_known=not outcome_indeterminate,
        )
        result = ProviderRuntimeExecution(
            invocation_id=invocation.invocation_id,
            consequence_assessment=assessment,
            attempt=safe_attempt,
            receipt=self._receipt(invocation, safe_attempt),
            audit=ProviderRuntimeAudit(
                adapter_invocations=1,
                provider_api_calls_performed=provider_api_calls_performed,
                network_calls_performed=network_calls_performed,
                credentials_used=credentials_used,
                external_actions_performed=(
                    1 if safe_attempt.external_action_performed is True else 0
                ),
                spend_cad=safe_attempt.cost_cad,
                spend_known=safe_attempt.cost_known,
            ),
            replayed=False,
        )
        try:
            self._control_store.complete_invocation(
                invocation_id=invocation.invocation_id,
                expected_epoch=expected_epoch,
                result=result,
            )
        except Exception as finalization_exc:
            if safe_attempt.status == "indeterminate":
                self._durably_record_finalization_reconciliation(
                    invocation=invocation,
                    result=result,
                    cause=finalization_exc,
                )
            else:
                self._durably_fail_finalization(
                    invocation_id=invocation.invocation_id,
                    cause=finalization_exc,
                )
        return result

    def _durably_fail_finalization(self, *, invocation_id: str, cause: Exception) -> None:
        """Move a reserved/executing call to a terminal state without persisting secrets.

        Provider output and exception text are intentionally excluded.  A failure to
        record this terminal marker makes the external outcome operationally
        indeterminate and must replace the original exception at the trust boundary.
        """

        reason = f"PROVIDER_FINALIZATION_FAILED:{type(cause).__name__}"
        try:
            self._control_store.fail_invocation(
                invocation_id=invocation_id,
                reason=reason,
            )
        except Exception as control_exc:
            raise RuntimeControlUnavailable(
                "provider outcome requires reconciliation because durable "
                "failure finalization did not complete"
            ) from control_exc

    def _durably_record_finalization_reconciliation(
        self,
        *,
        invocation: ProviderInvocation,
        result: ProviderRuntimeExecution,
        cause: Exception,
    ) -> None:
        """Retain measured, redacted evidence without claiming provider success."""

        safe_attempt = result.attempt.model_copy(
            update={
                "status": "indeterminate",
                "finish_status": f"PROVIDER_FINALIZATION_FAILED:{type(cause).__name__}",
                "response_payload": None,
                "external_action_performed": result.attempt.external_action_performed,
                "outcome_known": False,
            }
        )
        safe_result = result.model_copy(
            update={
                "attempt": safe_attempt,
                "receipt": self._receipt(invocation, safe_attempt),
            }
        )
        try:
            self._control_store.record_reconciliation_result(
                invocation_id=invocation.invocation_id,
                result=safe_result,
            )
        except Exception as control_exc:
            raise RuntimeControlUnavailable(
                "provider outcome requires reconciliation because durable "
                "redacted evidence finalization did not complete"
            ) from control_exc

    @staticmethod
    def _receipt(
        invocation: ProviderInvocation,
        attempt: ProviderAttemptResult,
    ) -> ExecutionReceipt:
        operation = OperationReceipt(
            operation_id=invocation.invocation_id,
            status=attempt.status,
            resource_ref=invocation.resource_ref,
            after_hash=attempt.response_digest if attempt.status == "succeeded" else None,
            failure_class=(
                None if attempt.status == "succeeded" else attempt.finish_status
            ),
            retryable=False if attempt.status == "indeterminate" else None,
            evidence_refs=(),
        )
        receipt_payload = {
            "invocation_id": invocation.invocation_id,
            "request_digest": invocation.request_digest,
            "attempt": attempt.model_dump(mode="json"),
            "change_set_id": invocation.change_set_id,
            "parent_state_hash": invocation.parent_state_hash,
        }
        receipt_id = "EXEC-" + canonical_sha256(receipt_payload)[:24].upper()
        return ExecutionReceipt(
            receipt_id=receipt_id,
            permit_id=invocation.permit_id,
            change_set_id=invocation.change_set_id,
            parent_state_hash=invocation.parent_state_hash,
            execution_status=attempt.status,
            operations=(operation,),
            external_action_performed=bool(attempt.external_action_performed),
            reconciliation_required=attempt.status == "indeterminate",
        )
