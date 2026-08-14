from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path

import psycopg
import pytest

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.provider_registry import OfflineDeterministicProviderAdapter, ProviderRegistry
from src.core.nexus.provider_runtime import (
    EmergencyStopActive,
    IdempotencyConflict,
    NexusProviderRuntime,
    bind_provider_request_digest,
)
from src.domain.nexus.autonomy import ConsequenceAssessment
from src.domain.nexus.provider_runtime import (
    ProviderAttemptResult,
    ProviderInvocation,
    ProviderRuntimeAudit,
    ProviderRuntimeExecution,
    ProviderRuntimeLimits,
)
from src.infrastructure.runtime.postgres_control_store import (
    PostgresRuntimeControlStore,
    _sanitize_canary_execution_result,
)


NOW = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
DSN = os.environ.get("NEXUS_TEST_POSTGRES_DSN", "")


def test_persisted_authority_migration_declares_one_use_replay_keys():
    migration = Path("migrations/004_nexus_persisted_authority.sql").read_text(
        encoding="utf-8"
    )
    assert "permit_id TEXT PRIMARY KEY" in migration
    assert "attestation_id TEXT NOT NULL UNIQUE" in migration
    assert "attestation_sha256 TEXT NOT NULL UNIQUE" in migration
    assert "execution_nonce TEXT NOT NULL UNIQUE" in migration
    assert "execution_permit_sha256 TEXT NOT NULL UNIQUE" in migration
    assert "request_digest TEXT NOT NULL UNIQUE" in migration
    assert "execution_name TEXT NOT NULL UNIQUE" in migration


@pytest.fixture(scope="module")
def dsn():
    if not DSN:
        pytest.skip("NEXUS_TEST_POSTGRES_DSN is not configured")
    migrations = [
        Path("migrations/003_nexus_provider_runtime_controls.sql").read_text(encoding="utf-8"),
        Path("migrations/004_nexus_persisted_authority.sql").read_text(encoding="utf-8"),
    ]
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS nexus_canary_authority_claim")
        conn.execute("DROP TABLE IF EXISTS nexus_runtime_permit_usage")
        conn.execute("DROP TABLE IF EXISTS nexus_runtime_usage")
        conn.execute("DROP TABLE IF EXISTS nexus_runtime_invocation")
        conn.execute("DROP TABLE IF EXISTS nexus_runtime_control")
        for migration in migrations:
            conn.execute(migration)
    return DSN


def limits(*, principal_per_minute: int = 3):
    return ProviderRuntimeLimits(
        principal_invocations_per_minute=principal_per_minute,
        principal_invocations_per_day=10,
        global_invocations_per_minute=12,
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
        maximum_input_units=5,
        maximum_output_units=5,
        request_timeout_seconds=30,
        maximum_cost_cad=Decimal("0.00"),
        resource_ref="provider://offline/test",
        purpose="postgres runtime control integration test",
        requested_effect_class="PURE",
        input_payload=input_payload,
    )
    return bind_provider_request_digest(value)


def test_live_canary_result_is_correlated_and_redacted_before_jsonb_persistence():
    value = invocation(key="6", input_payload="synthetic canary").model_copy(
        update={
            "invocation_id": "PINV-CANARY-ABCDEF01",
            "provider_id": "google_vertex_gemini",
            "permit_id": "PERMIT-PG-CANARY01",
            "model_or_resource": "example-model",
            "resource_ref": "provider://google_vertex_gemini/model/example-model",
        }
    )
    value = bind_provider_request_digest(value)
    raw = "raw provider output must never enter JSONB"
    attempt = ProviderAttemptResult(
        invocation_id=value.invocation_id,
        provider_id=value.provider_id,
        status="failed",
        provider_request_id="provider-request-1",
        model_or_resource=value.model_or_resource,
        latency_ms=12,
        usage_units=10,
        input_usage_units=5,
        output_usage_units=5,
        cost_cad=Decimal("0.00"),
        finish_status="credential-like-provider-detail",
        response_digest=canonical_sha256({"text": raw}),
        response_payload=raw,
        external_action_performed=True,
        outcome_known=True,
    )
    receipt = NexusProviderRuntime._receipt(value, attempt)
    result = ProviderRuntimeExecution(
        invocation_id=value.invocation_id,
        consequence_assessment=ConsequenceAssessment(
            assessment_id="AUTO-PG-CANARY01",
            intent_id="ACT-PG-CANARY01",
            consequence_class="EXTERNAL_READ",
            material_consequence=True,
            authority_requirement="EXISTING_EXPLICIT",
            disposition="AUTONOMOUS_WITHIN_EXISTING_AUTHORITY",
            execution_may_continue_without_new_authority=True,
        ),
        attempt=attempt,
        receipt=receipt,
        audit=ProviderRuntimeAudit(
            adapter_invocations=1,
            provider_api_calls_performed=1,
            network_calls_performed=1,
            credentials_used=1,
            external_actions_performed=1,
        ),
    )
    row = {
        "invocation_id": value.invocation_id,
        "provider_id": value.provider_id,
        "permit_id": value.permit_id,
        "request_digest": value.request_digest,
    }
    safe = _sanitize_canary_execution_result(row=row, result=result)
    encoded = safe.model_dump_json()
    assert raw not in encoded
    assert "credential-like-provider-detail" not in encoded
    assert safe.attempt.response_payload is None
    assert safe.attempt.finish_status == "FAILED_PROVIDER_DETAIL_REDACTED"
    assert safe.receipt.operations[0].failure_class == "FAILED_PROVIDER_DETAIL_REDACTED"
    assert safe.receipt.receipt_id != receipt.receipt_id


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
    # This test isolates the permit ceiling from the deliberately shared minute-rate
    # counters exercised above. Production rate limits remain unchanged; only the
    # test-specific limit is widened so the first reservation reaches permit accounting.
    permit_test_limits = limits(principal_per_minute=10)
    first = invocation(key="4")
    first = first.model_copy(update={"permit_id": "PERMIT-PG-TEST01"})
    store.reserve_invocation(
        invocation=first,
        limits=permit_test_limits,
        permit_maximum_invocations=1,
    )
    second = invocation(key="5").model_copy(update={"permit_id": "PERMIT-PG-TEST01"})
    from src.core.nexus.provider_runtime import RuntimeLimitExceeded
    with pytest.raises(RuntimeLimitExceeded):
        store.reserve_invocation(
            invocation=second,
            limits=permit_test_limits,
            permit_maximum_invocations=1,
        )


def test_postgres_canary_authority_claim_is_durable_and_one_use(dsn):
    store = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    values = {
        "permit_id": "PERMIT-PG-CANARY01",
        "attestation_id": "AUTH-PG-CANARY01",
        "attestation_sha256": "1" * 64,
        "execution_nonce": "2" * 64,
        "procurement_sha256": "3" * 64,
        "deployment_sha256": "4" * 64,
        "plan_sha256": "5" * 64,
        "governance_decision_sha256": "6" * 64,
        "execution_permit_sha256": "7" * 64,
        "request_digest": "8" * 64,
        "principal": "operator:postgres-canary",
        "exact_revision": "9" * 40,
        "job_name": "aigc-gemini-pg-canary",
        "execution_name": "aigc-gemini-pg-canary-abc123",
    }
    store.claim_canary_authority(**values)
    from src.core.nexus.provider_runtime import RuntimeLimitExceeded

    with pytest.raises(RuntimeLimitExceeded, match="already consumed"):
        PostgresRuntimeControlStore(dsn, clock=lambda: NOW).claim_canary_authority(
            **values
        )


def _postgres_canary_value(*, key: str) -> ProviderInvocation:
    value = invocation(key=key, input_payload="synthetic reconciliation canary").model_copy(
        update={
            "invocation_id": f"PINV-PG-RECON{key}001",
            "provider_id": "openai_responses",
            "permit_id": f"PERMIT-PG-RECON{key}01",
            "model_or_resource": "gpt-fixture",
            "resource_ref": "provider://openai_responses/model/gpt-fixture",
        }
    )
    return bind_provider_request_digest(value)


def _postgres_canary_result(
    value: ProviderInvocation,
    *,
    status: str = "indeterminate",
) -> ProviderRuntimeExecution:
    attempt = ProviderAttemptResult(
        invocation_id=value.invocation_id,
        provider_id=value.provider_id,
        status=status,
        provider_request_id="provider-request-reconciliation",
        model_or_resource=value.model_or_resource,
        latency_ms=17,
        usage_units=10,
        input_usage_units=5,
        output_usage_units=5,
        cost_cad=Decimal("0.00"),
        finish_status=(
            "PROVIDER_FINALIZATION_FAILED:RuntimeControlUnavailable"
            if status == "indeterminate"
            else "completed"
        ),
        response_digest=canonical_sha256({"text": "redacted provider result"}),
        response_payload=None,
        external_action_performed=True,
        outcome_known=status != "indeterminate",
    )
    return ProviderRuntimeExecution(
        invocation_id=value.invocation_id,
        consequence_assessment=ConsequenceAssessment(
            assessment_id=f"AUTO-PG-RECON{value.invocation_id[-4:]}",
            intent_id=f"ACT-PG-RECON{value.invocation_id[-4:]}",
            consequence_class="EXTERNAL_READ",
            material_consequence=True,
            authority_requirement="EXISTING_EXPLICIT",
            disposition="AUTONOMOUS_WITHIN_EXISTING_AUTHORITY",
            execution_may_continue_without_new_authority=True,
        ),
        attempt=attempt,
        receipt=NexusProviderRuntime._receipt(value, attempt),
        audit=ProviderRuntimeAudit(
            adapter_invocations=1,
            provider_api_calls_performed=1,
            network_calls_performed=1,
            credentials_used=1,
            external_actions_performed=1,
            spend_cad=Decimal("0.00"),
            spend_known=True,
        ),
    )


def test_postgres_reconciliation_result_is_atomic_redacted_and_replayable(dsn):
    store = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    value = _postgres_canary_value(key="7")
    reservation = store.reserve_invocation(
        invocation=value,
        limits=limits(principal_per_minute=10),
        permit_maximum_invocations=1,
    )
    store.mark_executing(
        invocation_id=value.invocation_id,
        expected_epoch=reservation.stop_epoch,
    )
    recorded = store.record_reconciliation_result(
        invocation_id=value.invocation_id,
        result=_postgres_canary_result(value),
    )
    assert recorded.state == "indeterminate"
    assert recorded.actual_usage_units == 10
    second = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    retained = second.get_execution_result(value.invocation_id)
    assert retained is not None
    assert retained.attempt.status == "indeterminate"
    assert retained.attempt.response_payload is None
    assert retained.attempt.usage_units == 10
    replay = second.reserve_invocation(
        invocation=value,
        limits=limits(principal_per_minute=10),
        permit_maximum_invocations=1,
    )
    assert replay.replayed is True
    assert replay.state == "indeterminate"
    with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as conn:
        rows = conn.execute(
            "SELECT actual_usage_units FROM nexus_runtime_usage "
            "WHERE actual_usage_units > 0 AND window_start=%s",
            (NOW.replace(second=0, microsecond=0),),
        ).fetchall()
    assert rows
    assert all(int(row["actual_usage_units"]) >= 10 for row in rows)


def test_postgres_existing_committed_result_wins_without_double_accounting(dsn):
    store = PostgresRuntimeControlStore(dsn, clock=lambda: NOW)
    value = _postgres_canary_value(key="8")
    reservation = store.reserve_invocation(
        invocation=value,
        limits=limits(principal_per_minute=10),
        permit_maximum_invocations=1,
    )
    store.mark_executing(
        invocation_id=value.invocation_id,
        expected_epoch=reservation.stop_epoch,
    )
    succeeded = _postgres_canary_result(value, status="succeeded")
    store.complete_invocation(
        invocation_id=value.invocation_id,
        expected_epoch=reservation.stop_epoch,
        result=succeeded,
    )
    with psycopg.connect(dsn) as conn:
        before = conn.execute(
            "SELECT SUM(actual_usage_units) FROM nexus_runtime_usage"
        ).fetchone()[0]
    observed = store.record_reconciliation_result(
        invocation_id=value.invocation_id,
        result=_postgres_canary_result(value),
    )
    with psycopg.connect(dsn) as conn:
        after = conn.execute(
            "SELECT SUM(actual_usage_units) FROM nexus_runtime_usage"
        ).fetchone()[0]
    assert observed.state == "completed"
    assert before == after
    retained = store.get_execution_result(value.invocation_id)
    assert retained is not None
    assert retained.attempt.status == "succeeded"
