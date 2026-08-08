from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path

import psycopg
import pytest

from src.core.nexus.provider_registry import OfflineDeterministicProviderAdapter, ProviderRegistry
from src.core.nexus.provider_runtime import (
    EmergencyStopActive,
    IdempotencyConflict,
    NexusProviderRuntime,
    bind_provider_request_digest,
)
from src.domain.nexus.provider_runtime import ProviderInvocation, ProviderRuntimeLimits
from src.infrastructure.runtime.postgres_control_store import PostgresRuntimeControlStore


NOW = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
DSN = os.environ.get("NEXUS_TEST_POSTGRES_DSN", "")


@pytest.fixture(scope="module")
def dsn():
    if not DSN:
        pytest.skip("NEXUS_TEST_POSTGRES_DSN is not configured")
    migration = Path("migrations/003_nexus_provider_runtime_controls.sql").read_text(encoding="utf-8")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS nexus_runtime_permit_usage")
        conn.execute("DROP TABLE IF EXISTS nexus_runtime_usage")
        conn.execute("DROP TABLE IF EXISTS nexus_runtime_invocation")
        conn.execute("DROP TABLE IF EXISTS nexus_runtime_control")
        conn.execute(migration)
    return DSN


def limits():
    return ProviderRuntimeLimits(
        principal_invocations_per_minute=3,
        principal_invocations_per_day=10,
        global_invocations_per_minute=6,
        global_invocations_per_day=20,
        principal_reserved_usage_per_day=1000,
        global_reserved_usage_per_day=2000,
        maximum_usage_per_invocation=100,
        maximum_cost_cad_per_invocation=Decimal("0.00"),
    )


def invocation(*, key="1", input_payload="alpha"):
    value = ProviderInvocation(
        invocation_id=f"PINV-PG-{key}000001",
        request_id=f"TREQ-PG-{key}000001",
        change_set_id=f"CHG-PG-{key}000001",
        parent_state_hash="a" * 64,
        principal="principal:postgres-runtime-test",
        provider_id="offline_deterministic",
        capability="deterministic.generate",
        model_or_resource="offline-deterministic-provider-not-live",
        exact_revision="b" * 40,
        request_digest="0" * 64,
        idempotency_key=(key * 64)[:64],
        reserved_usage_units=10,
        maximum_cost_cad=Decimal("0.00"),
        resource_ref="provider://offline/test",
        purpose="postgres runtime control integration test",
        requested_effect_class="PURE",
        input_payload=input_payload,
    )
    return bind_provider_request_digest(value)


def test_postgres_store_is_durable_and_replays_terminal_result_across_instances(dsn):
    adapter = OfflineDeterministicProviderAdapter()
    first_store = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    first_runtime = NexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=first_store,
        limits=limits(),
    )
    value = invocation(key="1")
    first = first_runtime.execute(value, authoritative_now=NOW)
    assert first.attempt.status == "succeeded"
    assert adapter.invocation_count == 1
    assert first_store.healthcheck().durable is True
    assert first_store.healthcheck().backend == "postgresql"

    second_store = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    second_runtime = NexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=second_store,
        limits=limits(),
    )
    replay = second_runtime.execute(value, authoritative_now=NOW)
    assert replay.replayed is True
    assert replay.receipt.receipt_id == first.receipt.receipt_id
    assert adapter.invocation_count == 1
    stored = second_store.get_execution_result(value.invocation_id)
    assert stored is not None
    assert stored.receipt.receipt_id == first.receipt.receipt_id


def test_postgres_idempotency_conflict_is_atomic(dsn):
    store = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    original = invocation(key="2", input_payload="alpha")
    changed = original.model_copy(update={"request_digest": "f" * 64})
    store.reserve_invocation(
        invocation=original,
        limits=limits(),
        permit_maximum_invocations=None,
    )
    with pytest.raises(IdempotencyConflict):
        store.reserve_invocation(
            invocation=changed,
            limits=limits(),
            permit_maximum_invocations=None,
        )


def test_postgres_emergency_stop_epoch_blocks_and_recovers(dsn):
    store = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    state = store.activate_emergency_stop(
        actor_principal_id="principal:operator",
        reason="integration test activates durable emergency stop",
    )
    assert state.active is True
    value = invocation(key="3")
    with pytest.raises(EmergencyStopActive):
        store.reserve_invocation(
            invocation=value,
            limits=limits(),
            permit_maximum_invocations=None,
        )
    cleared = store.clear_emergency_stop(
        actor_principal_id="principal:operator",
        reason="integration test clears durable emergency stop",
        expected_epoch=state.stop_epoch,
    )
    assert cleared.active is False
    assert cleared.stop_epoch == state.stop_epoch + 1
    reservation = store.reserve_invocation(
        invocation=value,
        limits=limits(),
        permit_maximum_invocations=None,
    )
    assert reservation.stop_epoch == cleared.stop_epoch


def test_postgres_permit_invocation_ceiling_is_durable(dsn):
    store = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    first = invocation(key="4")
    first = first.model_copy(update={"permit_id": "PERMIT-PG-TEST01"})
    store.reserve_invocation(
        invocation=first,
        limits=limits(),
        permit_maximum_invocations=1,
    )
    second = invocation(key="5").model_copy(update={"permit_id": "PERMIT-PG-TEST01"})
    from src.core.nexus.provider_runtime import RuntimeLimitExceeded
    with pytest.raises(RuntimeLimitExceeded):
        store.reserve_invocation(
            invocation=second,
            limits=limits(),
            permit_maximum_invocations=1,
        )
