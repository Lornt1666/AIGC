from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import threading
from typing import Any, Callable, Literal, Protocol
import uuid

from .runtime_limits import (
    RuntimeLimits,
    validate_idempotency_key,
    validate_principal_id,
    validate_sha256,
)


RunState = Literal[
    "reserved",
    "executing",
    "completed",
    "failed",
    "stopped",
    "evidence_missing",
]
FailureState = Literal["failed", "stopped", "evidence_missing"]


class RuntimeControlError(RuntimeError):
    """Base error for fail-closed runtime-control decisions."""


class RuntimeControlUnavailableError(RuntimeControlError):
    """Raised when durable control state cannot be read or committed."""


RuntimeControlUnavailable = RuntimeControlUnavailableError


class EmergencyStopActiveError(RuntimeControlError):
    """Raised when the durable emergency stop blocks a runtime transition."""

    def __init__(self, state: "EmergencyState") -> None:
        super().__init__(
            f"Gemini runtime is stopped at control epoch {state.stop_epoch}"
        )
        self.state = state


EmergencyStopActive = EmergencyStopActiveError


class StopEpochChanged(RuntimeControlError):
    """Raised when a transition was authorized against stale control state."""


class IdempotencyConflictError(RuntimeControlError):
    """Raised when an idempotency key is reused for different normalized input."""


IdempotencyConflict = IdempotencyConflictError


class RunStateError(RuntimeControlError):
    """Raised when a run transition is invalid or references an unknown run."""


class RuntimeQuotaExceededError(RuntimeControlError):
    """Base error for request-rate and token-budget exhaustion."""

    retry_after_seconds: int


class RuntimeLimitExceeded(RuntimeQuotaExceededError):
    """Raised before a provider call when a request-count limit is exhausted."""

    def __init__(
        self,
        *,
        scope: str,
        window_kind: str,
        retry_after_seconds: int,
    ) -> None:
        super().__init__(
            f"{scope} {window_kind} Gemini run limit has been reached"
        )
        self.scope = scope
        self.window_kind = window_kind
        self.retry_after_seconds = max(1, retry_after_seconds)


class TokenBudgetExceeded(RuntimeQuotaExceededError):
    """Raised before a provider call when a token reservation cannot be made."""

    def __init__(
        self,
        *,
        scope: str,
        retry_after_seconds: int,
    ) -> None:
        super().__init__(f"{scope} daily Gemini token reservation is exhausted")
        self.scope = scope
        self.retry_after_seconds = max(1, retry_after_seconds)


@dataclass(frozen=True)
class EmergencyState:
    active: bool
    stop_epoch: int
    reason: str
    actor_principal_id: str | None
    updated_at: datetime


@dataclass(frozen=True)
class RunReservation:
    run_id: str
    principal_id: str
    idempotency_key_sha256: str
    request_sha256: str
    stop_epoch: int
    state: RunState
    reserved_tokens: int
    actual_tokens: int | None
    minute_window_start: datetime
    day_window_start: datetime
    evidence_object_uri: str | None
    evidence_generation: int | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    model: str = ""
    source_revision: str = ""
    execution_event_id: str | None = None
    decision_event_id: str | None = None
    decision_object_uri: str | None = None
    decision_generation: int | None = None
    replayed: bool = False


@dataclass(frozen=True)
class ControlStoreHealth:
    ok: bool
    durable: bool
    backend: str
    emergency_active: bool
    stop_epoch: int


class RuntimeControlStore(Protocol):
    def get_emergency_state(self) -> EmergencyState: ...

    def activate_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
    ) -> EmergencyState: ...

    def clear_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
        expected_epoch: int,
        exact_phrase: str,
    ) -> EmergencyState: ...

    def reserve_run(
        self,
        *,
        run_id: str | None = None,
        principal_id: str,
        idempotency_key: str,
        request_sha256: str,
        model: str = "",
        source_revision: str = "",
        reserved_tokens: int,
        limits: RuntimeLimits,
    ) -> RunReservation: ...

    def get_run(self, run_id: str) -> RunReservation: ...

    def assert_epoch_current(
        self,
        *,
        run_id: str,
        expected_epoch: int,
    ) -> None: ...

    def mark_executing(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
    ) -> RunReservation: ...

    def complete_run(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
        actual_tokens: int | None,
        execution_event_id: str | None = None,
        evidence_object_uri: str | None,
        evidence_generation: int | None,
    ) -> RunReservation: ...

    def complete_decision(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
        decision_event_id: str,
        decision_object_uri: str | None,
        decision_generation: int | None,
    ) -> RunReservation: ...

    def fail_run(
        self,
        *,
        run_id: str,
        state: FailureState,
        reason: str | None = None,
    ) -> RunReservation: ...

    def healthcheck(self) -> ControlStoreHealth: ...


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


def _retry_after(window_kind: str, now: datetime) -> int:
    current = now.astimezone(timezone.utc)
    if window_kind == "minute":
        boundary = _minute_start(current) + timedelta(minutes=1)
    else:
        boundary = _day_start(current) + timedelta(days=1)
    return max(1, int((boundary - current).total_seconds()) + 1)


def _validate_reason(value: str) -> str:
    normalized = value.strip()
    if len(normalized) < 10 or len(normalized) > 2_000:
        raise ValueError("reason must contain 10..2000 non-whitespace characters")
    return normalized


def _validate_run_id(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 100:
        raise ValueError("run_id is invalid")
    return normalized


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_optional_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    normalized = value.strip()
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} cannot exceed {max_length} characters")
    return normalized


def _validate_evidence_receipt(
    *,
    execution_event_id: str | None,
    evidence_object_uri: str | None,
    evidence_generation: int | None,
) -> tuple[str | None, str | None, int | None]:
    event_id = (
        _validate_optional_text(
            execution_event_id,
            field_name="execution_event_id",
            max_length=128,
        )
        if execution_event_id is not None
        else None
    )
    if event_id == "":
        raise ValueError("execution_event_id cannot be empty")
    if evidence_object_uri is None and evidence_generation is None:
        return event_id, None, None
    if evidence_object_uri is None or evidence_generation is None:
        raise ValueError(
            "evidence_object_uri and evidence_generation must be supplied together"
        )
    object_uri = evidence_object_uri.strip()
    if not object_uri.startswith("gs://"):
        raise ValueError("Production evidence_object_uri must be a gs:// URI")
    if evidence_generation <= 0:
        raise ValueError("evidence_generation must be greater than zero")
    return event_id, object_uri, evidence_generation


def _clear_phrase(expected_epoch: int) -> str:
    return f"CLEAR GEMINI STOP EPOCH {expected_epoch}"


def _validate_clear_phrase(value: str, *, expected_epoch: int) -> None:
    if value != _clear_phrase(expected_epoch):
        raise ValueError(
            "exact_phrase must match the emergency-stop epoch confirmation"
        )


class InMemoryRuntimeControlStore:
    """Thread-safe semantic implementation for unit tests only.

    Production must use a durable implementation. The explicit `durable=False`
    health result prevents this store from being represented as production proof.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._clock = clock
        now = self._now()
        self._emergency = EmergencyState(
            active=False,
            stop_epoch=0,
            reason="",
            actor_principal_id=None,
            updated_at=now,
        )
        self._runs: dict[str, RunReservation] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._usage: dict[tuple[str, str, str, datetime], dict[str, int]] = {}
        self._lock = threading.RLock()
        self._available = True

    def set_available_for_test(self, available: bool) -> None:
        with self._lock:
            self._available = available

    def _require_available(self) -> None:
        if not self._available:
            raise RuntimeControlUnavailable(
                "Runtime control state is unavailable; execution is blocked"
            )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise RuntimeControlUnavailable("Runtime-control clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    def get_emergency_state(self) -> EmergencyState:
        with self._lock:
            self._require_available()
            return self._emergency

    def activate_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
    ) -> EmergencyState:
        principal = validate_principal_id(actor_principal_id)
        normalized_reason = _validate_reason(reason)
        with self._lock:
            self._require_available()
            self._emergency = EmergencyState(
                active=True,
                stop_epoch=self._emergency.stop_epoch + 1,
                reason=normalized_reason,
                actor_principal_id=principal,
                updated_at=self._now(),
            )
            return self._emergency

    def clear_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
        expected_epoch: int,
        exact_phrase: str,
    ) -> EmergencyState:
        principal = validate_principal_id(actor_principal_id)
        normalized_reason = _validate_reason(reason)
        _validate_clear_phrase(exact_phrase, expected_epoch=expected_epoch)
        with self._lock:
            self._require_available()
            if not self._emergency.active:
                raise RunStateError("Emergency stop is not active")
            if self._emergency.stop_epoch != expected_epoch:
                raise StopEpochChanged("Emergency-stop clear used a stale control epoch")
            self._emergency = EmergencyState(
                active=False,
                stop_epoch=self._emergency.stop_epoch + 1,
                reason=normalized_reason,
                actor_principal_id=principal,
                updated_at=self._now(),
            )
            return self._emergency

    def reserve_run(
        self,
        *,
        run_id: str | None = None,
        principal_id: str,
        idempotency_key: str,
        request_sha256: str,
        model: str = "",
        source_revision: str = "",
        reserved_tokens: int,
        limits: RuntimeLimits,
    ) -> RunReservation:
        principal = validate_principal_id(principal_id)
        key = validate_idempotency_key(idempotency_key)
        key_hash = _sha256_text(key)
        request_hash = validate_sha256(request_sha256)
        normalized_model = _validate_optional_text(
            model,
            field_name="model",
            max_length=200,
        )
        normalized_revision = _validate_optional_text(
            source_revision,
            field_name="source_revision",
            max_length=128,
        )
        requested_run_id = (
            _validate_run_id(run_id)
            if run_id is not None
            else f"AIGC-GEMINI-RUN-{uuid.uuid4()}"
        )
        limits.validate_reservation(reserved_tokens)

        with self._lock:
            self._require_available()
            if self._emergency.active:
                raise EmergencyStopActive(self._emergency)

            existing_id = self._idempotency.get((principal, key_hash))
            if existing_id is not None:
                existing = self._runs[existing_id]
                if (
                    existing.request_sha256 != request_hash
                    or existing.model != normalized_model
                    or existing.source_revision != normalized_revision
                ):
                    raise IdempotencyConflict(
                        "Idempotency key is already bound to a different "
                        "request, model, or source revision"
                    )
                return replace(existing, replayed=True)

            if requested_run_id in self._runs:
                raise RunStateError("run_id is already reserved")

            now = self._now()
            minute = _minute_start(now)
            day = _day_start(now)
            windows = [
                (
                    "principal",
                    principal,
                    "minute",
                    minute,
                    limits.principal_runs_per_minute,
                    None,
                ),
                (
                    "global",
                    "*",
                    "minute",
                    minute,
                    limits.global_runs_per_minute,
                    None,
                ),
                (
                    "principal",
                    principal,
                    "day",
                    day,
                    limits.principal_runs_per_day,
                    limits.principal_reserved_tokens_per_day,
                ),
                (
                    "global",
                    "*",
                    "day",
                    day,
                    limits.global_runs_per_day,
                    limits.global_reserved_tokens_per_day,
                ),
            ]
            for scope_type, scope_id, kind, start, max_runs, max_tokens in windows:
                usage = self._usage.get(
                    (scope_type, scope_id, kind, start),
                    {"run_count": 0, "reserved_tokens": 0, "actual_tokens": 0},
                )
                if usage["run_count"] + 1 > max_runs:
                    raise RuntimeLimitExceeded(
                        scope=scope_type,
                        window_kind=kind,
                        retry_after_seconds=_retry_after(kind, now),
                    )
                if (
                    max_tokens is not None
                    and usage["reserved_tokens"] + reserved_tokens > max_tokens
                ):
                    raise TokenBudgetExceeded(
                        scope=scope_type,
                        retry_after_seconds=_retry_after("day", now),
                    )

            for scope_type, scope_id, kind, start, _max_runs, _max_tokens in windows:
                usage_key = (scope_type, scope_id, kind, start)
                usage = self._usage.setdefault(
                    usage_key,
                    {"run_count": 0, "reserved_tokens": 0, "actual_tokens": 0},
                )
                usage["run_count"] += 1
                usage["reserved_tokens"] += reserved_tokens

            reservation = RunReservation(
                run_id=requested_run_id,
                principal_id=principal,
                idempotency_key_sha256=key_hash,
                request_sha256=request_hash,
                stop_epoch=self._emergency.stop_epoch,
                state="reserved",
                reserved_tokens=reserved_tokens,
                actual_tokens=None,
                minute_window_start=minute,
                day_window_start=day,
                evidence_object_uri=None,
                evidence_generation=None,
                failure_reason=None,
                created_at=now,
                updated_at=now,
                model=normalized_model,
                source_revision=normalized_revision,
            )
            self._runs[requested_run_id] = reservation
            self._idempotency[(principal, key_hash)] = requested_run_id
            return reservation

    def get_run(self, run_id: str) -> RunReservation:
        normalized = _validate_run_id(run_id)
        with self._lock:
            self._require_available()
            try:
                return self._runs[normalized]
            except KeyError as exc:
                raise RunStateError("Runtime-control run was not found") from exc

    def assert_epoch_current(
        self,
        *,
        run_id: str,
        expected_epoch: int,
    ) -> None:
        with self._lock:
            self._require_available()
            run = self.get_run(run_id)
            if self._emergency.active:
                raise EmergencyStopActive(self._emergency)
            if (
                run.stop_epoch != expected_epoch
                or self._emergency.stop_epoch != expected_epoch
            ):
                raise StopEpochChanged(
                    "Run authorization was captured under a stale stop epoch"
                )

    def mark_executing(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
    ) -> RunReservation:
        with self._lock:
            current = self.get_run(run_id)
            authorized_epoch = (
                current.stop_epoch
                if expected_epoch is None
                else expected_epoch
            )
            self.assert_epoch_current(
                run_id=run_id,
                expected_epoch=authorized_epoch,
            )
            if current.state == "executing":
                return replace(current, replayed=True)
            if current.state != "reserved":
                raise RunStateError(
                    f"Cannot start a run in terminal state {current.state}"
                )
            updated = replace(
                current,
                state="executing",
                updated_at=self._now(),
            )
            self._runs[current.run_id] = updated
            return updated

    def complete_run(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
        actual_tokens: int | None,
        execution_event_id: str | None = None,
        evidence_object_uri: str | None,
        evidence_generation: int | None,
    ) -> RunReservation:
        if actual_tokens is not None and actual_tokens < 0:
            raise ValueError("actual_tokens cannot be negative")
        event_id, object_uri, generation = _validate_evidence_receipt(
            execution_event_id=execution_event_id,
            evidence_object_uri=evidence_object_uri,
            evidence_generation=evidence_generation,
        )
        with self._lock:
            current = self.get_run(run_id)
            authorized_epoch = (
                current.stop_epoch
                if expected_epoch is None
                else expected_epoch
            )
            self.assert_epoch_current(
                run_id=run_id,
                expected_epoch=authorized_epoch,
            )
            if current.state == "completed":
                if (
                    current.actual_tokens != actual_tokens
                    or current.execution_event_id != event_id
                    or current.evidence_object_uri != object_uri
                    or current.evidence_generation != generation
                ):
                    raise RunStateError(
                        "Completed run receipt cannot be replaced"
                    )
                return replace(current, replayed=True)
            if current.state != "executing":
                raise RunStateError(
                    f"Cannot complete a run in state {current.state}"
                )
            # Missing provider usage is conservatively charged as the complete
            # reservation. A lower actual count never refunds the reservation.
            accounted_tokens = max(
                current.reserved_tokens,
                actual_tokens if actual_tokens is not None else 0,
            )
            for scope_type, scope_id in (
                ("principal", current.principal_id),
                ("global", "*"),
            ):
                for kind, start in (
                    ("minute", current.minute_window_start),
                    ("day", current.day_window_start),
                ):
                    self._usage[
                        (scope_type, scope_id, kind, start)
                    ]["actual_tokens"] += accounted_tokens
            updated = replace(
                current,
                state="completed",
                actual_tokens=actual_tokens,
                execution_event_id=event_id,
                evidence_object_uri=object_uri,
                evidence_generation=generation,
                updated_at=self._now(),
            )
            self._runs[current.run_id] = updated
            return updated

    def complete_decision(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
        decision_event_id: str,
        decision_object_uri: str | None,
        decision_generation: int | None,
    ) -> RunReservation:
        event_id, object_uri, generation = _validate_evidence_receipt(
            execution_event_id=decision_event_id,
            evidence_object_uri=decision_object_uri,
            evidence_generation=decision_generation,
        )
        if event_id is None:
            raise ValueError("decision_event_id is required")
        with self._lock:
            current = self.get_run(run_id)
            authorized_epoch = (
                current.stop_epoch
                if expected_epoch is None
                else expected_epoch
            )
            self.assert_epoch_current(
                run_id=run_id,
                expected_epoch=authorized_epoch,
            )
            if current.state != "completed":
                raise RunStateError(
                    "A decision may be recorded only for a completed run"
                )
            if current.decision_event_id is not None:
                if (
                    current.decision_event_id != event_id
                    or current.decision_object_uri != object_uri
                    or current.decision_generation != generation
                ):
                    raise RunStateError(
                        "Decision receipt conflicts with the completed marker"
                    )
                return replace(current, replayed=True)
            updated = replace(
                current,
                decision_event_id=event_id,
                decision_object_uri=object_uri,
                decision_generation=generation,
                updated_at=self._now(),
            )
            self._runs[current.run_id] = updated
            return updated

    def fail_run(
        self,
        *,
        run_id: str,
        state: FailureState,
        reason: str | None = None,
    ) -> RunReservation:
        if state not in {"failed", "stopped", "evidence_missing"}:
            raise ValueError(
                "Failure state must be failed, stopped, or evidence_missing"
            )
        normalized_reason = _validate_reason(
            reason or f"Run entered terminal state {state}."
        )
        with self._lock:
            self._require_available()
            current = self.get_run(run_id)
            if current.state in {"failed", "stopped", "evidence_missing"}:
                if current.state != state:
                    raise RunStateError(
                        f"Run is already terminal in state {current.state}"
                    )
                return replace(current, replayed=True)
            if current.state == "completed":
                raise RunStateError("A completed run cannot be changed to failure")
            updated = replace(
                current,
                state=state,
                failure_reason=normalized_reason,
                updated_at=self._now(),
            )
            self._runs[current.run_id] = updated
            return updated

    def healthcheck(self) -> ControlStoreHealth:
        with self._lock:
            self._require_available()
            return ControlStoreHealth(
                ok=True,
                durable=False,
                backend="memory_test_only",
                emergency_active=self._emergency.active,
                stop_epoch=self._emergency.stop_epoch,
            )


class UnavailableRuntimeControlStore:
    """Explicit fail-closed sentinel used when durable initialization fails."""

    def __init__(self, reason: str = "Durable runtime control is unavailable") -> None:
        self.reason = reason

    def _blocked(self, *_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeControlUnavailable(self.reason)

    get_emergency_state = _blocked
    activate_emergency_stop = _blocked
    clear_emergency_stop = _blocked
    reserve_run = _blocked
    get_run = _blocked
    assert_epoch_current = _blocked
    mark_executing = _blocked
    complete_run = _blocked
    complete_decision = _blocked
    fail_run = _blocked
    healthcheck = _blocked


class PostgresRuntimeControlStore:
    """Durable PostgreSQL implementation for Cloud SQL production use.

    The caller owns the psycopg pool lifecycle. `from_dsn` is provided as the
    narrow construction helper and imports psycopg lazily so offline tests do not
    need production database dependencies.
    """

    def __init__(
        self,
        pool: Any,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._pool = pool
        self._clock = clock

    @classmethod
    def from_dsn(
        cls,
        dsn: str,
        *,
        min_size: int = 0,
        max_size: int = 5,
        timeout: float = 5.0,
    ) -> "PostgresRuntimeControlStore":
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeControlUnavailable(
                "psycopg_pool is required for durable runtime control"
            ) from exc
        pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            open=True,
        )
        return cls(pool)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise RuntimeControlUnavailable("Runtime-control clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _cursor(connection: Any) -> Any:
        try:
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeControlUnavailable(
                "psycopg is required for durable runtime control"
            ) from exc
        return connection.cursor(row_factory=dict_row)

    @staticmethod
    def _row_to_emergency(row: dict[str, Any]) -> EmergencyState:
        return EmergencyState(
            active=bool(row["emergency_active"]),
            stop_epoch=int(row["stop_epoch"]),
            reason=str(row["reason"] or ""),
            actor_principal_id=row["actor_principal_id"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_run(
        row: dict[str, Any],
        *,
        replayed: bool = False,
    ) -> RunReservation:
        return RunReservation(
            run_id=str(row["run_id"]),
            principal_id=str(row["principal_id"]),
            idempotency_key_sha256=str(row["idempotency_key_sha256"]),
            request_sha256=str(row["request_sha256"]),
            stop_epoch=int(row["stop_epoch"]),
            state=str(row["state"]),  # type: ignore[arg-type]
            reserved_tokens=int(row["reserved_tokens"]),
            actual_tokens=(
                int(row["actual_tokens"])
                if row["actual_tokens"] is not None
                else None
            ),
            minute_window_start=row["minute_window_start"],
            day_window_start=row["day_window_start"],
            evidence_object_uri=row["evidence_object_uri"],
            evidence_generation=(
                int(row["evidence_generation"])
                if row["evidence_generation"] is not None
                else None
            ),
            failure_reason=row["failure_reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            model=str(row["model"] or ""),
            source_revision=str(row["source_revision"] or ""),
            execution_event_id=row["execution_event_id"],
            decision_event_id=row["decision_event_id"],
            decision_object_uri=row["decision_object_uri"],
            decision_generation=(
                int(row["decision_generation"])
                if row["decision_generation"] is not None
                else None
            ),
            replayed=replayed,
        )

    def get_emergency_state(self) -> EmergencyState:
        try:
            with self._pool.connection() as connection:
                with self._cursor(connection) as cursor:
                    cursor.execute(
                        """
                        SELECT emergency_active, stop_epoch, reason,
                               actor_principal_id, updated_at
                        FROM gemini_runtime_control
                        WHERE singleton_id = 1
                        """
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise RuntimeControlUnavailable(
                            "Runtime-control singleton row is missing"
                        )
                    return self._row_to_emergency(row)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Runtime-control read failed: {type(exc).__name__}"
            ) from exc

    def activate_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
    ) -> EmergencyState:
        principal = validate_principal_id(actor_principal_id)
        normalized_reason = _validate_reason(reason)
        now = self._now()
        try:
            with self._pool.connection() as connection:
                with connection.transaction():
                    with self._cursor(connection) as cursor:
                        cursor.execute(
                            """
                            UPDATE gemini_runtime_control
                            SET emergency_active = TRUE,
                                stop_epoch = stop_epoch + 1,
                                reason = %s,
                                actor_principal_id = %s,
                                updated_at = %s
                            WHERE singleton_id = 1
                            RETURNING emergency_active, stop_epoch, reason,
                                      actor_principal_id, updated_at
                            """,
                            (normalized_reason, principal, now),
                        )
                        row = cursor.fetchone()
                        if row is None:
                            raise RuntimeControlUnavailable(
                                "Runtime-control singleton row is missing"
                            )
                        return self._row_to_emergency(row)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Emergency-stop write failed: {type(exc).__name__}"
            ) from exc

    def clear_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
        expected_epoch: int,
        exact_phrase: str,
    ) -> EmergencyState:
        principal = validate_principal_id(actor_principal_id)
        normalized_reason = _validate_reason(reason)
        _validate_clear_phrase(exact_phrase, expected_epoch=expected_epoch)
        now = self._now()
        try:
            with self._pool.connection() as connection:
                with connection.transaction():
                    with self._cursor(connection) as cursor:
                        cursor.execute(
                            """
                            UPDATE gemini_runtime_control
                            SET emergency_active = FALSE,
                                stop_epoch = stop_epoch + 1,
                                reason = %s,
                                actor_principal_id = %s,
                                updated_at = %s
                            WHERE singleton_id = 1
                              AND emergency_active = TRUE
                              AND stop_epoch = %s
                            RETURNING emergency_active, stop_epoch, reason,
                                      actor_principal_id, updated_at
                            """,
                            (
                                normalized_reason,
                                principal,
                                now,
                                expected_epoch,
                            ),
                        )
                        row = cursor.fetchone()
                        if row is None:
                            cursor.execute(
                                """
                                SELECT emergency_active, stop_epoch, reason,
                                       actor_principal_id, updated_at
                                FROM gemini_runtime_control
                                WHERE singleton_id = 1
                                """
                            )
                            current = cursor.fetchone()
                            if current is None:
                                raise RuntimeControlUnavailable(
                                    "Runtime-control singleton row is missing"
                                )
                            if not current["emergency_active"]:
                                raise RunStateError("Emergency stop is not active")
                            raise StopEpochChanged(
                                "Emergency-stop clear used a stale control epoch"
                            )
                        return self._row_to_emergency(row)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Emergency-stop clear failed: {type(exc).__name__}"
            ) from exc

    def reserve_run(
        self,
        *,
        run_id: str | None = None,
        principal_id: str,
        idempotency_key: str,
        request_sha256: str,
        model: str = "",
        source_revision: str = "",
        reserved_tokens: int,
        limits: RuntimeLimits,
    ) -> RunReservation:
        principal = validate_principal_id(principal_id)
        key = validate_idempotency_key(idempotency_key)
        key_hash = _sha256_text(key)
        request_hash = validate_sha256(request_sha256)
        normalized_model = _validate_optional_text(
            model,
            field_name="model",
            max_length=200,
        )
        normalized_revision = _validate_optional_text(
            source_revision,
            field_name="source_revision",
            max_length=128,
        )
        requested_run_id = (
            _validate_run_id(run_id)
            if run_id is not None
            else f"AIGC-GEMINI-RUN-{uuid.uuid4()}"
        )
        limits.validate_reservation(reserved_tokens)
        now = self._now()
        minute = _minute_start(now)
        day = _day_start(now)
        advisory_key = f"{principal}\0{key_hash}"
        try:
            with self._pool.connection() as connection:
                with connection.transaction():
                    with self._cursor(connection) as cursor:
                        cursor.execute(
                            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                            (advisory_key,),
                        )
                        cursor.execute(
                            """
                            SELECT emergency_active, stop_epoch, reason,
                                   actor_principal_id, updated_at
                            FROM gemini_runtime_control
                            WHERE singleton_id = 1
                            FOR UPDATE
                            """
                        )
                        control = cursor.fetchone()
                        if control is None:
                            raise RuntimeControlUnavailable(
                                "Runtime-control singleton row is missing"
                            )
                        emergency = self._row_to_emergency(control)
                        if emergency.active:
                            raise EmergencyStopActive(emergency)

                        cursor.execute(
                            """
                            SELECT *
                            FROM gemini_run_reservations
                            WHERE principal_id = %s
                              AND idempotency_key_sha256 = %s
                            """,
                            (principal, key_hash),
                        )
                        existing = cursor.fetchone()
                        if existing is not None:
                            if (
                                existing["request_sha256"] != request_hash
                                or str(existing["model"] or "")
                                != normalized_model
                                or str(existing["source_revision"] or "")
                                != normalized_revision
                            ):
                                raise IdempotencyConflict(
                                    "Idempotency key is already bound to "
                                    "a different request, model, or source "
                                    "revision"
                                )
                            return self._row_to_run(existing, replayed=True)

                        windows = [
                            (
                                "principal",
                                principal,
                                "minute",
                                minute,
                                limits.principal_runs_per_minute,
                                None,
                            ),
                            (
                                "global",
                                "*",
                                "minute",
                                minute,
                                limits.global_runs_per_minute,
                                None,
                            ),
                            (
                                "principal",
                                principal,
                                "day",
                                day,
                                limits.principal_runs_per_day,
                                limits.principal_reserved_tokens_per_day,
                            ),
                            (
                                "global",
                                "*",
                                "day",
                                day,
                                limits.global_runs_per_day,
                                limits.global_reserved_tokens_per_day,
                            ),
                        ]
                        for window in windows:
                            self._reserve_postgres_window(
                                cursor,
                                *window,
                                reserved_tokens=reserved_tokens,
                                now=now,
                            )

                        cursor.execute(
                            """
                            INSERT INTO gemini_run_reservations (
                                run_id, principal_id,
                                idempotency_key_sha256, request_sha256,
                                model, source_revision, stop_epoch, state,
                                reserved_tokens, actual_tokens,
                                minute_window_start, day_window_start,
                                execution_event_id, evidence_object_uri,
                                evidence_generation,
                                failure_reason, created_at, updated_at
                            )
                            VALUES (
                                %s, %s, %s, %s, %s, %s, %s, 'reserved',
                                %s, NULL, %s, %s, NULL, NULL, NULL,
                                NULL, %s, %s
                            )
                            RETURNING *
                            """,
                            (
                                requested_run_id,
                                principal,
                                key_hash,
                                request_hash,
                                normalized_model,
                                normalized_revision,
                                emergency.stop_epoch,
                                reserved_tokens,
                                minute,
                                day,
                                now,
                                now,
                            ),
                        )
                        row = cursor.fetchone()
                        if row is None:
                            raise RuntimeControlUnavailable(
                                "Run reservation did not return a durable row"
                            )
                        return self._row_to_run(row)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Run reservation failed: {type(exc).__name__}"
            ) from exc

    @staticmethod
    def _reserve_postgres_window(
        cursor: Any,
        scope_type: str,
        scope_id: str,
        window_kind: str,
        window_start: datetime,
        max_runs: int,
        max_tokens: int | None,
        *,
        reserved_tokens: int,
        now: datetime,
    ) -> None:
        effective_token_limit = max_tokens if max_tokens is not None else 2**62
        cursor.execute(
            """
            INSERT INTO gemini_usage_windows (
                scope_type, scope_id, window_kind, window_start,
                run_count, reserved_tokens, actual_tokens, updated_at
            )
            VALUES (%s, %s, %s, %s, 1, %s, 0, %s)
            ON CONFLICT (scope_type, scope_id, window_kind, window_start)
            DO UPDATE SET
                run_count = gemini_usage_windows.run_count + 1,
                reserved_tokens = (
                    gemini_usage_windows.reserved_tokens
                    + EXCLUDED.reserved_tokens
                ),
                updated_at = EXCLUDED.updated_at
            WHERE gemini_usage_windows.run_count + 1 <= %s
              AND (
                  gemini_usage_windows.reserved_tokens
                  + EXCLUDED.reserved_tokens
              ) <= %s
            RETURNING run_count, reserved_tokens
            """,
            (
                scope_type,
                scope_id,
                window_kind,
                window_start,
                reserved_tokens,
                now,
                max_runs,
                effective_token_limit,
            ),
        )
        if cursor.fetchone() is not None:
            return
        cursor.execute(
            """
            SELECT run_count, reserved_tokens
            FROM gemini_usage_windows
            WHERE scope_type = %s AND scope_id = %s
              AND window_kind = %s AND window_start = %s
            """,
            (scope_type, scope_id, window_kind, window_start),
        )
        current = cursor.fetchone()
        if current is not None and int(current["run_count"]) + 1 > max_runs:
            raise RuntimeLimitExceeded(
                scope=scope_type,
                window_kind=window_kind,
                retry_after_seconds=_retry_after(window_kind, now),
            )
        raise TokenBudgetExceeded(
            scope=scope_type,
            retry_after_seconds=_retry_after("day", now),
        )

    def get_run(self, run_id: str) -> RunReservation:
        normalized = _validate_run_id(run_id)
        try:
            with self._pool.connection() as connection:
                with self._cursor(connection) as cursor:
                    cursor.execute(
                        "SELECT * FROM gemini_run_reservations WHERE run_id = %s",
                        (normalized,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise RunStateError("Runtime-control run was not found")
                    return self._row_to_run(row)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Runtime-control run read failed: {type(exc).__name__}"
            ) from exc

    def assert_epoch_current(
        self,
        *,
        run_id: str,
        expected_epoch: int,
    ) -> None:
        normalized = _validate_run_id(run_id)
        try:
            with self._pool.connection() as connection:
                with connection.transaction():
                    with self._cursor(connection) as cursor:
                        self._assert_postgres_epoch(
                            cursor,
                            run_id=normalized,
                            expected_epoch=expected_epoch,
                            lock_rows=False,
                        )
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Stop-epoch check failed: {type(exc).__name__}"
            ) from exc

    def _assert_postgres_epoch(
        self,
        cursor: Any,
        *,
        run_id: str,
        expected_epoch: int | None,
        lock_rows: bool,
    ) -> dict[str, Any]:
        lock = " FOR UPDATE" if lock_rows else ""
        cursor.execute(
            """
            SELECT emergency_active, stop_epoch, reason,
                   actor_principal_id, updated_at
            FROM gemini_runtime_control
            WHERE singleton_id = 1
            """
            + lock
        )
        control = cursor.fetchone()
        if control is None:
            raise RuntimeControlUnavailable("Runtime-control singleton row is missing")
        emergency = self._row_to_emergency(control)
        if emergency.active:
            raise EmergencyStopActive(emergency)
        cursor.execute(
            "SELECT * FROM gemini_run_reservations WHERE run_id = %s" + lock,
            (run_id,),
        )
        run = cursor.fetchone()
        if run is None:
            raise RunStateError("Runtime-control run was not found")
        authorized_epoch = (
            int(run["stop_epoch"])
            if expected_epoch is None
            else expected_epoch
        )
        if (
            int(run["stop_epoch"]) != authorized_epoch
            or emergency.stop_epoch != authorized_epoch
        ):
            raise StopEpochChanged(
                "Run authorization was captured under a stale stop epoch"
            )
        return run

    def mark_executing(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
    ) -> RunReservation:
        normalized = _validate_run_id(run_id)
        now = self._now()
        try:
            with self._pool.connection() as connection:
                with connection.transaction():
                    with self._cursor(connection) as cursor:
                        run = self._assert_postgres_epoch(
                            cursor,
                            run_id=normalized,
                            expected_epoch=expected_epoch,
                            lock_rows=True,
                        )
                        if run["state"] == "executing":
                            return self._row_to_run(run, replayed=True)
                        if run["state"] != "reserved":
                            raise RunStateError(
                                f"Cannot start a run in state {run['state']}"
                            )
                        cursor.execute(
                            """
                            UPDATE gemini_run_reservations
                            SET state = 'executing', updated_at = %s
                            WHERE run_id = %s AND state = 'reserved'
                            RETURNING *
                            """,
                            (now, normalized),
                        )
                        updated = cursor.fetchone()
                        if updated is None:
                            raise RunStateError("Run start transition lost its lock")
                        return self._row_to_run(updated)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Run start transition failed: {type(exc).__name__}"
            ) from exc

    def complete_run(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
        actual_tokens: int | None,
        execution_event_id: str | None = None,
        evidence_object_uri: str | None,
        evidence_generation: int | None,
    ) -> RunReservation:
        normalized = _validate_run_id(run_id)
        if actual_tokens is not None and actual_tokens < 0:
            raise ValueError("actual_tokens cannot be negative")
        event_id, object_uri, generation = _validate_evidence_receipt(
            execution_event_id=execution_event_id,
            evidence_object_uri=evidence_object_uri,
            evidence_generation=evidence_generation,
        )
        if event_id is None or object_uri is None or generation is None:
            raise ValueError(
                "Durable completion requires an execution event ID and "
                "a Cloud Storage generation receipt"
            )
        now = self._now()
        try:
            with self._pool.connection() as connection:
                with connection.transaction():
                    with self._cursor(connection) as cursor:
                        run = self._assert_postgres_epoch(
                            cursor,
                            run_id=normalized,
                            expected_epoch=expected_epoch,
                            lock_rows=True,
                        )
                        if run["state"] == "completed":
                            if (
                                (
                                    int(run["actual_tokens"])
                                    if run["actual_tokens"] is not None
                                    else None
                                )
                                != actual_tokens
                                or run["execution_event_id"] != event_id
                                or run["evidence_object_uri"] != object_uri
                                or int(run["evidence_generation"]) != generation
                            ):
                                raise RunStateError(
                                    "Completed run receipt cannot be replaced"
                                )
                            return self._row_to_run(run, replayed=True)
                        if run["state"] != "executing":
                            raise RunStateError(
                                f"Cannot complete a run in state {run['state']}"
                            )
                        accounted_tokens = max(
                            int(run["reserved_tokens"]),
                            actual_tokens if actual_tokens is not None else 0,
                        )
                        for scope_type, scope_id in (
                            ("principal", run["principal_id"]),
                            ("global", "*"),
                        ):
                            for kind, start in (
                                ("minute", run["minute_window_start"]),
                                ("day", run["day_window_start"]),
                            ):
                                cursor.execute(
                                    """
                                    UPDATE gemini_usage_windows
                                    SET actual_tokens = actual_tokens + %s,
                                        updated_at = %s
                                    WHERE scope_type = %s AND scope_id = %s
                                      AND window_kind = %s
                                      AND window_start = %s
                                    """,
                                    (
                                        accounted_tokens,
                                        now,
                                        scope_type,
                                        scope_id,
                                        kind,
                                        start,
                                    ),
                                )
                                if cursor.rowcount != 1:
                                    raise RuntimeControlUnavailable(
                                        "Usage window is missing during completion"
                                    )
                        cursor.execute(
                            """
                            UPDATE gemini_run_reservations
                            SET state = 'completed',
                                actual_tokens = %s,
                                execution_event_id = %s,
                                evidence_object_uri = %s,
                                evidence_generation = %s,
                                updated_at = %s
                            WHERE run_id = %s AND state = 'executing'
                            RETURNING *
                            """,
                            (
                                actual_tokens,
                                event_id,
                                object_uri,
                                generation,
                                now,
                                normalized,
                            ),
                        )
                        updated = cursor.fetchone()
                        if updated is None:
                            raise RunStateError(
                                "Run completion transition lost its lock"
                            )
                        return self._row_to_run(updated)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Run completion failed: {type(exc).__name__}"
            ) from exc

    def complete_decision(
        self,
        *,
        run_id: str,
        expected_epoch: int | None = None,
        decision_event_id: str,
        decision_object_uri: str | None,
        decision_generation: int | None,
    ) -> RunReservation:
        normalized = _validate_run_id(run_id)
        event_id, object_uri, generation = _validate_evidence_receipt(
            execution_event_id=decision_event_id,
            evidence_object_uri=decision_object_uri,
            evidence_generation=decision_generation,
        )
        if event_id is None or object_uri is None or generation is None:
            raise ValueError(
                "Durable decision completion requires an event ID and "
                "a Cloud Storage generation receipt"
            )
        now = self._now()
        try:
            with self._pool.connection() as connection:
                with connection.transaction():
                    with self._cursor(connection) as cursor:
                        run = self._assert_postgres_epoch(
                            cursor,
                            run_id=normalized,
                            expected_epoch=expected_epoch,
                            lock_rows=True,
                        )
                        if run["state"] != "completed":
                            raise RunStateError(
                                "A decision may be recorded only for a "
                                "completed run"
                            )
                        if run["decision_event_id"] is not None:
                            current_generation = (
                                int(run["decision_generation"])
                                if run["decision_generation"] is not None
                                else None
                            )
                            if (
                                run["decision_event_id"] != event_id
                                or run["decision_object_uri"] != object_uri
                                or current_generation != generation
                            ):
                                raise RunStateError(
                                    "Decision receipt conflicts with the "
                                    "completed marker"
                                )
                            return self._row_to_run(run, replayed=True)
                        cursor.execute(
                            """
                            UPDATE gemini_run_reservations
                            SET decision_event_id = %s,
                                decision_object_uri = %s,
                                decision_generation = %s,
                                updated_at = %s
                            WHERE run_id = %s
                              AND state = 'completed'
                              AND decision_event_id IS NULL
                            RETURNING *
                            """,
                            (
                                event_id,
                                object_uri,
                                generation,
                                now,
                                normalized,
                            ),
                        )
                        updated = cursor.fetchone()
                        if updated is None:
                            raise RunStateError(
                                "Decision completion transition lost its lock"
                            )
                        return self._row_to_run(updated)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Decision completion failed: {type(exc).__name__}"
            ) from exc

    def fail_run(
        self,
        *,
        run_id: str,
        state: FailureState,
        reason: str | None = None,
    ) -> RunReservation:
        normalized = _validate_run_id(run_id)
        if state not in {"failed", "stopped", "evidence_missing"}:
            raise ValueError(
                "Failure state must be failed, stopped, or evidence_missing"
            )
        normalized_reason = _validate_reason(
            reason or f"Run entered terminal state {state}."
        )
        now = self._now()
        try:
            with self._pool.connection() as connection:
                with connection.transaction():
                    with self._cursor(connection) as cursor:
                        cursor.execute(
                            """
                            SELECT *
                            FROM gemini_run_reservations
                            WHERE run_id = %s
                            FOR UPDATE
                            """,
                            (normalized,),
                        )
                        current = cursor.fetchone()
                        if current is None:
                            raise RunStateError("Runtime-control run was not found")
                        if current["state"] in {
                            "failed",
                            "stopped",
                            "evidence_missing",
                        }:
                            if current["state"] != state:
                                raise RunStateError(
                                    "Run is already terminal in a different state"
                                )
                            return self._row_to_run(current, replayed=True)
                        if current["state"] == "completed":
                            raise RunStateError(
                                "A completed run cannot be changed to failure"
                            )
                        cursor.execute(
                            """
                            UPDATE gemini_run_reservations
                            SET state = %s, failure_reason = %s, updated_at = %s
                            WHERE run_id = %s
                              AND state IN ('reserved', 'executing')
                            RETURNING *
                            """,
                            (state, normalized_reason, now, normalized),
                        )
                        updated = cursor.fetchone()
                        if updated is None:
                            raise RunStateError(
                                "Run failure transition lost its lock"
                            )
                        return self._row_to_run(updated)
        except RuntimeControlError:
            raise
        except Exception as exc:
            raise RuntimeControlUnavailable(
                f"Run failure transition failed: {type(exc).__name__}"
            ) from exc

    def healthcheck(self) -> ControlStoreHealth:
        state = self.get_emergency_state()
        return ControlStoreHealth(
            ok=True,
            durable=True,
            backend="postgresql",
            emergency_active=state.active,
            stop_epoch=state.stop_epoch,
        )
