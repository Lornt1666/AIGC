from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

import psycopg
from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.core.nexus.provider_runtime import (
    EmergencyStopActive,
    IdempotencyConflict,
    ProviderRuntimeError,
    RuntimeControlHealth,
    RuntimeControlUnavailable,
    RuntimeLimitExceeded,
    StaleControlEpoch,
    UsageBudgetExceeded,
)
from src.domain.nexus.provider_runtime import (
    InvocationReservation,
    ProviderInvocation,
    ProviderRuntimeExecution,
    ProviderRuntimeLimits,
    RuntimeEmergencyState,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _minute_start(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)


def _day_start(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


class PostgresRuntimeControlStore:
    """Transactional PostgreSQL implementation of Nexus RuntimeControlStore.

    All consequential state transitions use database transactions and row locks. The
    singleton emergency-stop epoch, idempotency claims, rate/usage reservations, permit
    invocation counters, invocation state, and terminal execution result are durable.
    """

    def __init__(
        self,
        dsn: str,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not dsn.strip():
            raise ValueError("Postgres runtime-control DSN is required")
        self._dsn = dsn
        self._clock = clock

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeControlUnavailable("runtime-control clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    def _connect(self):
        return psycopg.connect(self._dsn, row_factory=dict_row)

    @staticmethod
    def _reservation(row: dict, *, replayed: bool = False) -> InvocationReservation:
        return InvocationReservation(
            invocation_id=row["invocation_id"],
            principal=row["principal"],
            provider_id=row["provider_id"],
            capability=row["capability"],
            permit_id=row["permit_id"],
            idempotency_key=row["idempotency_key"],
            request_digest=row["request_digest"],
            exact_revision=row["exact_revision"],
            stop_epoch=int(row["stop_epoch"]),
            state=row["state"],
            reserved_usage_units=int(row["reserved_usage_units"]),
            actual_usage_units=(
                int(row["actual_usage_units"])
                if row["actual_usage_units"] is not None
                else None
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            failure_reason=row["failure_reason"],
            replayed=replayed,
        )

    @staticmethod
    def _emergency(row: dict) -> RuntimeEmergencyState:
        return RuntimeEmergencyState(
            active=bool(row["emergency_active"]),
            stop_epoch=int(row["stop_epoch"]),
            reason=row["reason"],
            actor_principal_id=row["actor_principal_id"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _fetch_emergency(cur, *, for_update: bool = False) -> dict:
        suffix = " FOR UPDATE" if for_update else ""
        cur.execute(
            "SELECT emergency_active, stop_epoch, reason, actor_principal_id, updated_at "
            f"FROM nexus_runtime_control WHERE singleton = TRUE{suffix}"
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeControlUnavailable("nexus_runtime_control singleton is missing")
        return row

    def get_emergency_state(self) -> RuntimeEmergencyState:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                return self._emergency(self._fetch_emergency(cur))
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres runtime control is unavailable: {type(exc).__name__}"
            ) from None

    def activate_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
    ) -> RuntimeEmergencyState:
        normalized = reason.strip()
        if not actor_principal_id.strip() or not normalized:
            raise ValueError("emergency-stop actor and reason are required")
        now = self._now()
        try:
            with self._connect() as conn, conn.cursor() as cur:
                row = self._fetch_emergency(cur, for_update=True)
                epoch = int(row["stop_epoch"]) + 1
                cur.execute(
                    "UPDATE nexus_runtime_control SET emergency_active=TRUE, stop_epoch=%s, "
                    "reason=%s, actor_principal_id=%s, updated_at=%s WHERE singleton=TRUE",
                    (epoch, normalized[:2000], actor_principal_id[:200], now),
                )
                return RuntimeEmergencyState(
                    active=True,
                    stop_epoch=epoch,
                    reason=normalized[:2000],
                    actor_principal_id=actor_principal_id[:200],
                    updated_at=now,
                )
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres emergency-stop update failed: {type(exc).__name__}"
            ) from None

    def clear_emergency_stop(
        self,
        *,
        actor_principal_id: str,
        reason: str,
        expected_epoch: int,
    ) -> RuntimeEmergencyState:
        normalized = reason.strip()
        if not actor_principal_id.strip() or not normalized:
            raise ValueError("emergency-stop clear actor and reason are required")
        now = self._now()
        try:
            with self._connect() as conn, conn.cursor() as cur:
                row = self._fetch_emergency(cur, for_update=True)
                if not row["emergency_active"]:
                    raise ProviderRuntimeError("emergency stop is not active")
                if int(row["stop_epoch"]) != expected_epoch:
                    raise StaleControlEpoch("emergency-stop clear used stale epoch")
                epoch = expected_epoch + 1
                cur.execute(
                    "UPDATE nexus_runtime_control SET emergency_active=FALSE, stop_epoch=%s, "
                    "reason=%s, actor_principal_id=%s, updated_at=%s WHERE singleton=TRUE",
                    (epoch, normalized[:2000], actor_principal_id[:200], now),
                )
                return RuntimeEmergencyState(
                    active=False,
                    stop_epoch=epoch,
                    reason=normalized[:2000],
                    actor_principal_id=actor_principal_id[:200],
                    updated_at=now,
                )
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres emergency-stop clear failed: {type(exc).__name__}"
            ) from None

    def reserve_invocation(
        self,
        *,
        invocation: ProviderInvocation,
        limits: ProviderRuntimeLimits,
        permit_maximum_invocations: int | None,
    ) -> InvocationReservation:
        limits.validate_invocation(invocation)
        now = self._now()
        minute = _minute_start(now)
        day = _day_start(now)
        try:
            with self._connect() as conn, conn.cursor() as cur:
                emergency = self._fetch_emergency(cur, for_update=True)
                if emergency["emergency_active"]:
                    raise EmergencyStopActive(
                        f"provider runtime is stopped at epoch {emergency['stop_epoch']}"
                    )
                cur.execute(
                    "SELECT * FROM nexus_runtime_invocation "
                    "WHERE principal=%s AND idempotency_key=%s FOR UPDATE",
                    (invocation.principal, invocation.idempotency_key),
                )
                existing = cur.fetchone()
                if existing is not None:
                    if existing["request_digest"] != invocation.request_digest:
                        raise IdempotencyConflict(
                            "idempotency key is already bound to a different request digest"
                        )
                    return self._reservation(existing, replayed=True)
                cur.execute(
                    "SELECT 1 FROM nexus_runtime_invocation WHERE invocation_id=%s FOR UPDATE",
                    (invocation.invocation_id,),
                )
                if cur.fetchone() is not None:
                    raise IdempotencyConflict("invocation_id is already reserved")

                if invocation.permit_id is not None and permit_maximum_invocations is not None:
                    cur.execute(
                        "INSERT INTO nexus_runtime_permit_usage(permit_id, invocation_count, updated_at) "
                        "VALUES (%s, 0, %s) ON CONFLICT (permit_id) DO NOTHING",
                        (invocation.permit_id, now),
                    )
                    cur.execute(
                        "SELECT invocation_count FROM nexus_runtime_permit_usage "
                        "WHERE permit_id=%s FOR UPDATE",
                        (invocation.permit_id,),
                    )
                    permit_row = cur.fetchone()
                    if permit_row is None:
                        raise RuntimeControlUnavailable("permit usage row disappeared")
                    if int(permit_row["invocation_count"]) >= permit_maximum_invocations:
                        raise RuntimeLimitExceeded("ExecutionPermit maximum_invocations exhausted")

                windows = (
                    ("principal", invocation.principal, "minute", minute, limits.principal_invocations_per_minute, None),
                    ("global", "*", "minute", minute, limits.global_invocations_per_minute, None),
                    ("principal", invocation.principal, "day", day, limits.principal_invocations_per_day, limits.principal_reserved_usage_per_day),
                    ("global", "*", "day", day, limits.global_invocations_per_day, limits.global_reserved_usage_per_day),
                )
                locked: list[tuple] = []
                for scope_type, scope_id, kind, start, run_limit, usage_limit in windows:
                    cur.execute(
                        "INSERT INTO nexus_runtime_usage(scope_type, scope_id, window_kind, window_start) "
                        "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (scope_type, scope_id, kind, start),
                    )
                    cur.execute(
                        "SELECT run_count, reserved_usage_units FROM nexus_runtime_usage "
                        "WHERE scope_type=%s AND scope_id=%s AND window_kind=%s AND window_start=%s FOR UPDATE",
                        (scope_type, scope_id, kind, start),
                    )
                    usage = cur.fetchone()
                    if usage is None:
                        raise RuntimeControlUnavailable("runtime usage row disappeared")
                    if int(usage["run_count"]) + 1 > run_limit:
                        raise RuntimeLimitExceeded(f"{scope_type} {kind} invocation limit exceeded")
                    if usage_limit is not None and int(usage["reserved_usage_units"]) + invocation.reserved_usage_units > usage_limit:
                        raise UsageBudgetExceeded(f"{scope_type} daily reserved usage exceeded")
                    locked.append((scope_type, scope_id, kind, start))

                for scope_type, scope_id, kind, start in locked:
                    cur.execute(
                        "UPDATE nexus_runtime_usage SET run_count=run_count+1, "
                        "reserved_usage_units=reserved_usage_units+%s "
                        "WHERE scope_type=%s AND scope_id=%s AND window_kind=%s AND window_start=%s",
                        (invocation.reserved_usage_units, scope_type, scope_id, kind, start),
                    )
                cur.execute(
                    "INSERT INTO nexus_runtime_invocation(" 
                    "invocation_id, principal, provider_id, capability, permit_id, idempotency_key, "
                    "request_digest, exact_revision, stop_epoch, state, reserved_usage_units, "
                    "actual_usage_units, created_at, updated_at, failure_reason, result_json) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'reserved',%s,NULL,%s,%s,NULL,NULL)",
                    (
                        invocation.invocation_id,
                        invocation.principal,
                        invocation.provider_id,
                        invocation.capability,
                        invocation.permit_id,
                        invocation.idempotency_key,
                        invocation.request_digest,
                        invocation.exact_revision,
                        int(emergency["stop_epoch"]),
                        invocation.reserved_usage_units,
                        now,
                        now,
                    ),
                )
                if invocation.permit_id is not None and permit_maximum_invocations is not None:
                    cur.execute(
                        "UPDATE nexus_runtime_permit_usage SET invocation_count=invocation_count+1, updated_at=%s "
                        "WHERE permit_id=%s",
                        (now, invocation.permit_id),
                    )
                cur.execute(
                    "SELECT * FROM nexus_runtime_invocation WHERE invocation_id=%s",
                    (invocation.invocation_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeControlUnavailable("reserved invocation row disappeared")
                return self._reservation(row)
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres invocation reservation failed: {type(exc).__name__}"
            ) from None

    def get_invocation(self, invocation_id: str) -> InvocationReservation:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT * FROM nexus_runtime_invocation WHERE invocation_id=%s", (invocation_id,))
                row = cur.fetchone()
                if row is None:
                    raise ProviderRuntimeError("runtime invocation reservation not found")
                return self._reservation(row)
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres invocation lookup failed: {type(exc).__name__}"
            ) from None

    def get_execution_result(self, invocation_id: str) -> ProviderRuntimeExecution | None:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT result_json FROM nexus_runtime_invocation WHERE invocation_id=%s",
                    (invocation_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ProviderRuntimeError("runtime invocation reservation not found")
                payload = row["result_json"]
                return ProviderRuntimeExecution.model_validate(payload) if payload is not None else None
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres result lookup failed: {type(exc).__name__}"
            ) from None

    def assert_epoch_current(self, *, invocation_id: str, expected_epoch: int) -> None:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                emergency = self._fetch_emergency(cur)
                cur.execute(
                    "SELECT stop_epoch FROM nexus_runtime_invocation WHERE invocation_id=%s",
                    (invocation_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ProviderRuntimeError("runtime invocation reservation not found")
                if emergency["emergency_active"]:
                    raise EmergencyStopActive(
                        f"provider runtime is stopped at epoch {emergency['stop_epoch']}"
                    )
                if int(row["stop_epoch"]) != expected_epoch or int(emergency["stop_epoch"]) != expected_epoch:
                    raise StaleControlEpoch("provider invocation was reserved under a stale control epoch")
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres epoch assertion failed: {type(exc).__name__}"
            ) from None

    def mark_executing(self, *, invocation_id: str, expected_epoch: int) -> InvocationReservation:
        now = self._now()
        try:
            with self._connect() as conn, conn.cursor() as cur:
                emergency = self._fetch_emergency(cur, for_update=True)
                cur.execute(
                    "SELECT * FROM nexus_runtime_invocation WHERE invocation_id=%s FOR UPDATE",
                    (invocation_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ProviderRuntimeError("runtime invocation reservation not found")
                if emergency["emergency_active"]:
                    raise EmergencyStopActive(
                        f"provider runtime is stopped at epoch {emergency['stop_epoch']}"
                    )
                if int(row["stop_epoch"]) != expected_epoch or int(emergency["stop_epoch"]) != expected_epoch:
                    raise StaleControlEpoch("provider invocation was reserved under a stale control epoch")
                if row["state"] == "executing":
                    return self._reservation(row, replayed=True)
                if row["state"] != "reserved":
                    raise ProviderRuntimeError(f"cannot execute invocation in state {row['state']}")
                cur.execute(
                    "UPDATE nexus_runtime_invocation SET state='executing', updated_at=%s WHERE invocation_id=%s",
                    (now, invocation_id),
                )
                row["state"] = "executing"
                row["updated_at"] = now
                return self._reservation(row)
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres mark-executing failed: {type(exc).__name__}"
            ) from None

    def complete_invocation(
        self,
        *,
        invocation_id: str,
        expected_epoch: int,
        result: ProviderRuntimeExecution,
    ) -> InvocationReservation:
        now = self._now()
        try:
            with self._connect() as conn, conn.cursor() as cur:
                emergency = self._fetch_emergency(cur, for_update=True)
                cur.execute(
                    "SELECT * FROM nexus_runtime_invocation WHERE invocation_id=%s FOR UPDATE",
                    (invocation_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ProviderRuntimeError("runtime invocation reservation not found")
                if emergency["emergency_active"]:
                    raise EmergencyStopActive(
                        f"provider runtime is stopped at epoch {emergency['stop_epoch']}"
                    )
                if int(row["stop_epoch"]) != expected_epoch or int(emergency["stop_epoch"]) != expected_epoch:
                    raise StaleControlEpoch("provider invocation was reserved under a stale control epoch")
                if row["state"] != "executing":
                    raise ProviderRuntimeError(f"cannot complete invocation in state {row['state']}")
                attempt = result.attempt
                state = {
                    "succeeded": "completed",
                    "failed": "failed",
                    "timed_out": "timed_out",
                    "indeterminate": "indeterminate",
                    "not_started": "failed",
                }[attempt.status]
                actual = max(
                    int(row["reserved_usage_units"]),
                    int(attempt.usage_units or 0),
                )
                failure = None if attempt.status == "succeeded" else attempt.finish_status
                cur.execute(
                    "UPDATE nexus_runtime_invocation SET state=%s, actual_usage_units=%s, updated_at=%s, "
                    "failure_reason=%s, result_json=%s WHERE invocation_id=%s",
                    (
                        state,
                        actual,
                        now,
                        failure,
                        Jsonb(result.model_dump(mode="json")),
                        invocation_id,
                    ),
                )
                created = row["created_at"].astimezone(timezone.utc)
                for scope_type, scope_id, kind, start in (
                    ("principal", row["principal"], "minute", _minute_start(created)),
                    ("global", "*", "minute", _minute_start(created)),
                    ("principal", row["principal"], "day", _day_start(created)),
                    ("global", "*", "day", _day_start(created)),
                ):
                    cur.execute(
                        "UPDATE nexus_runtime_usage SET actual_usage_units=actual_usage_units+%s "
                        "WHERE scope_type=%s AND scope_id=%s AND window_kind=%s AND window_start=%s",
                        (actual, scope_type, scope_id, kind, start),
                    )
                row["state"] = state
                row["actual_usage_units"] = actual
                row["updated_at"] = now
                row["failure_reason"] = failure
                return self._reservation(row)
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres completion failed: {type(exc).__name__}"
            ) from None

    def fail_invocation(self, *, invocation_id: str, reason: str) -> InvocationReservation:
        now = self._now()
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM nexus_runtime_invocation WHERE invocation_id=%s FOR UPDATE",
                    (invocation_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ProviderRuntimeError("runtime invocation reservation not found")
                if row["state"] not in {"reserved", "executing"}:
                    return self._reservation(row)
                cur.execute(
                    "UPDATE nexus_runtime_invocation SET state='failed', failure_reason=%s, updated_at=%s "
                    "WHERE invocation_id=%s",
                    (reason[:2000], now, invocation_id),
                )
                row["state"] = "failed"
                row["failure_reason"] = reason[:2000]
                row["updated_at"] = now
                return self._reservation(row)
        except PsycopgError as exc:
            raise RuntimeControlUnavailable(
                f"Postgres fail-invocation failed: {type(exc).__name__}"
            ) from None

    def healthcheck(self) -> RuntimeControlHealth:
        try:
            state = self.get_emergency_state()
            return RuntimeControlHealth(
                ok=True,
                durable=True,
                backend="postgresql",
                emergency_active=state.active,
                stop_epoch=state.stop_epoch,
            )
        except RuntimeControlUnavailable:
            raise
