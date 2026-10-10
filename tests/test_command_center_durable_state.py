from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import threading
import uuid

import pytest

from src.webapp.command_center_store import (
    IdempotencyConflict,
    MemoryCommandCenterStore,
    PostgresCommandCenterStore,
    ReviewAlreadyDecided,
    ReviewOutcomeUnknown,
    RunAlreadyActive,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_memory_store_is_explicitly_non_durable_and_idempotent() -> None:
    store = MemoryCommandCenterStore()
    first, created = store.create_run(run_id="RUN-1", actor_id="operator",
        idempotency_key="key-0001", request_digest=digest("cycle-v1"))
    replay, created_again = store.create_run(run_id="RUN-2", actor_id="operator",
        idempotency_key="key-0001", request_digest=digest("cycle-v1"))
    assert store.healthcheck() == {"ok": True, "durable": False, "backend": "memory"}
    assert created and not created_again
    assert replay["run_id"] == first["run_id"] and replay["replayed"]
    with pytest.raises(IdempotencyConflict):
        store.create_run(run_id="RUN-3", actor_id="operator",
            idempotency_key="key-0001", request_digest=digest("different"))
    with pytest.raises(RunAlreadyActive):
        store.create_run(run_id="RUN-4", actor_id="operator",
            idempotency_key="key-0002", request_digest=digest("cycle-v1"))


def test_memory_review_unknown_outcome_blocks_retry() -> None:
    store = MemoryCommandCenterStore()
    store.claim_review(action_id="action-1", decision_type="accept", actor_id="operator",
        idempotency_key="decision-0001", request_digest=digest("phrase"))
    store.mark_review_unknown(action_id="action-1")
    with pytest.raises(ReviewOutcomeUnknown):
        store.claim_review(action_id="action-1", decision_type="accept", actor_id="operator",
            idempotency_key="decision-0001", request_digest=digest("phrase"))


@pytest.fixture
def postgres_stores():
    dsn = os.environ.get("AIGC_COMMAND_CENTER_TEST_DATABASE_URL", "").strip()
    if not dsn:
        pytest.skip("PostgreSQL integration service is not configured")
    import psycopg
    migration_dir = Path(__file__).resolve().parents[1] / "migrations" / "command_center_postgresql"
    with psycopg.connect(dsn) as conn:
        for migration_path in sorted(migration_dir.glob("*.sql")):
            conn.execute(migration_path.read_text(encoding="utf-8"), prepare=False)
        conn.execute("UPDATE command_center_control_state SET emergency_stop_active=FALSE, reason='test fixture reset', actor_id=NULL WHERE singleton_id=1")
        conn.execute("DELETE FROM command_center_review_decisions")
        conn.execute("DELETE FROM command_center_runs")
    first = PostgresCommandCenterStore(dsn, sslmode="disable")
    second = PostgresCommandCenterStore(dsn, sslmode="disable")
    try:
        yield first, second, dsn
    finally:
        first.close()
        second.close()


def test_postgres_state_and_evidence_are_shared_across_instances(postgres_stores) -> None:
    first, second, _ = postgres_stores
    run_id = f"RUN-{uuid.uuid4()}"
    first.create_run(run_id=run_id, actor_id="operator", idempotency_key=f"key-{uuid.uuid4()}",
        request_digest=digest("cycle-v1"))
    first.mark_running(run_id)
    first.set_current(run_id, "runtime_preflight")
    first.append_step(run_id, {"name":"runtime_preflight","ok":True,
        "evidence":{"uri":"evidence://run/preflight","sha256":digest("receipt")}})
    observed = second.get_run(run_id)
    assert observed and observed["status"] == "running"
    assert observed["steps"][0]["evidence"]["sha256"] == digest("receipt")
    first.finish_run(run_id, status="completed")
    assert second.get_run(run_id)["status"] == "completed"


def test_postgres_global_admission_and_restart_recovery(postgres_stores) -> None:
    first, second, dsn = postgres_stores
    run_id = f"RUN-{uuid.uuid4()}"
    first.create_run(run_id=run_id, actor_id="operator", idempotency_key=f"key-{uuid.uuid4()}",
        request_digest=digest("cycle-v1"))
    first.mark_running(run_id)
    with pytest.raises(RunAlreadyActive):
        second.create_run(run_id=f"RUN-{uuid.uuid4()}", actor_id="operator",
            idempotency_key=f"key-{uuid.uuid4()}", request_digest=digest("cycle-v1"))
    import psycopg
    with psycopg.connect(dsn) as conn:
        conn.execute("UPDATE command_center_runs SET lease_until=now()-interval '1 minute' WHERE run_id=%s",
            (run_id,))
    restarted = PostgresCommandCenterStore(dsn, sslmode="disable")
    try:
        unknown = restarted.get_run(run_id)
        assert unknown["status"] == "unknown"
        with pytest.raises(RunAlreadyActive):
            restarted.create_run(run_id=f"RUN-{uuid.uuid4()}", actor_id="operator",
                idempotency_key=f"key-{uuid.uuid4()}", request_digest=digest("cycle-v1"))
        phrase = f"RECONCILE AIGC RUN {run_id} AS FAILED VERSION {unknown['version']}"
        restarted.reconcile_unknown_run(run_id=run_id, actor_id="operator",
            expected_version=unknown["version"], confirmation_phrase=phrase)
        assert restarted.get_run(run_id)["status"] == "failed"
        with psycopg.connect(dsn) as conn:
            audit = conn.execute(
                "SELECT actor_id,disposition FROM command_center_run_reconciliations WHERE run_id=%s",
                (run_id,),
            ).fetchone()
        assert audit and audit[0] == "operator" and audit[1] == "failed"
    finally:
        restarted.close()


def test_postgres_review_claim_is_atomic_across_instances(postgres_stores) -> None:
    first, second, _ = postgres_stores
    action_id = f"action-{uuid.uuid4()}"
    barrier = threading.Barrier(2)
    def claim(store, key):
        barrier.wait(timeout=5)
        return store.claim_review(action_id=action_id, decision_type="accept", actor_id="operator",
            idempotency_key=key, request_digest=digest("phrase"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim, first, f"key-{uuid.uuid4()}"),
                   pool.submit(claim, second, f"key-{uuid.uuid4()}")]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=10))
            except (ReviewAlreadyDecided, ReviewOutcomeUnknown):
                outcomes.append("blocked")
    assert sum(isinstance(item, dict) for item in outcomes) == 1
    assert outcomes.count("blocked") == 1


def test_postgres_constraint_failure_rolls_back(postgres_stores) -> None:
    _first, _second, dsn = postgres_stores
    import psycopg
    run_id = f"RUN-{uuid.uuid4()}"
    with psycopg.connect(dsn) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                conn.execute("""INSERT INTO command_center_runs
                    (run_id,actor_id,idempotency_key_sha256,request_sha256,status,complete)
                    VALUES (%s,'operator',%s,%s,'invalid-state',FALSE)""",
                    (run_id, digest(str(uuid.uuid4())), digest("invalid")))
        assert conn.execute("SELECT run_id FROM command_center_runs WHERE run_id=%s",
            (run_id,)).fetchone() is None


def test_memory_unknown_run_requires_exact_versioned_reconciliation() -> None:
    store = MemoryCommandCenterStore()
    run, _ = store.create_run(run_id="RUN-RECONCILE", actor_id="operator",
        idempotency_key="reconcile-key-1", request_digest=digest("cycle-v1"))
    store.mark_running("RUN-RECONCILE")
    store.finish_run("RUN-RECONCILE", status="unknown")
    unknown = store.get_run("RUN-RECONCILE")
    phrase = f"RECONCILE AIGC RUN RUN-RECONCILE AS FAILED VERSION {unknown['version']}"
    with pytest.raises(ValueError):
        store.reconcile_unknown_run(run_id="RUN-RECONCILE", actor_id="operator", expected_version=unknown["version"],
            confirmation_phrase="wrong phrase")
    store.reconcile_unknown_run(run_id="RUN-RECONCILE", actor_id="operator", expected_version=unknown["version"],
        confirmation_phrase=phrase)
    assert store.get_run("RUN-RECONCILE")["status"] == "failed"


def test_production_mode_fails_closed_without_database(monkeypatch) -> None:
    from src.webapp.command_center_store import CommandCenterStoreUnavailable, command_center_store_from_env
    monkeypatch.setenv("AIGC_ENV", "production")
    monkeypatch.delenv("AIGC_COMMAND_CENTER_DATABASE_URL", raising=False)
    with pytest.raises(CommandCenterStoreUnavailable, match="required in production"):
        command_center_store_from_env()


def test_memory_emergency_stop_is_durable_in_store_and_requires_exact_clear_phrase() -> None:
    from src.webapp.command_center_store import EmergencyStopActive
    store = MemoryCommandCenterStore()
    state = store.activate_emergency_stop(actor_id="operator", reason="Operator requested emergency stop")
    assert state["active"] is True
    with pytest.raises(EmergencyStopActive):
        store.create_run(run_id="RUN-BLOCKED", actor_id="operator",
            idempotency_key="blocked-key-1", request_digest=digest("cycle-v1"))
    phrase = f"CLEAR AIGC EMERGENCY STOP EPOCH {state['stop_epoch']}"
    with pytest.raises(ValueError):
        store.clear_emergency_stop(actor_id="operator", reason="Operator reviewed stop",
            expected_epoch=state["stop_epoch"], exact_phrase="wrong")
    cleared = store.clear_emergency_stop(actor_id="operator", reason="Operator reviewed stop",
        expected_epoch=state["stop_epoch"], exact_phrase=phrase)
    assert cleared["active"] is False
    replay = store.clear_emergency_stop(actor_id="operator", reason="Operator reviewed stop",
        expected_epoch=state["stop_epoch"], exact_phrase=phrase)
    assert replay["active"] is False
    assert len(store.control_events) == 2


def test_postgres_emergency_stop_is_shared_and_control_events_are_append_only(postgres_stores) -> None:
    first, second, dsn = postgres_stores
    state = first.activate_emergency_stop(actor_id="operator-1", reason="Operator requested stop")
    assert second.get_emergency_state()["active"] is True
    from src.webapp.command_center_store import EmergencyStopActive
    with pytest.raises(EmergencyStopActive):
        second.create_run(run_id=f"RUN-{uuid.uuid4()}", actor_id="operator-2",
            idempotency_key=f"key-{uuid.uuid4()}", request_digest=digest("cycle-v1"))
    phrase = f"CLEAR AIGC EMERGENCY STOP EPOCH {state['stop_epoch']}"
    cleared = second.clear_emergency_stop(actor_id="operator-2", reason="Operator reviewed stop",
        expected_epoch=state["stop_epoch"], exact_phrase=phrase)
    assert cleared["active"] is False
    import psycopg
    with psycopg.connect(dsn) as conn:
        event_id = conn.execute(
            "SELECT event_id FROM command_center_control_events WHERE stop_epoch=%s ORDER BY created_at DESC LIMIT 1",
            (state["stop_epoch"],),
        ).fetchone()[0]
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute("DELETE FROM command_center_control_events WHERE event_id=%s", (event_id,))
