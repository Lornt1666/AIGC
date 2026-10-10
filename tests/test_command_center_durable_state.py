from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import uuid

import pytest

from src.webapp.durable_state import (
    IdempotencyConflictError,
    InMemoryCommandCenterStore,
    PostgresCommandCenterStore,
    ReviewDecisionConflictError,
    RunBusyError,
    StateStoreNotConfiguredError,
    get_command_center_store,
    hash_request,
)


def test_memory_adapter_is_idempotent_and_bounds_active_runs() -> None:
    store = InMemoryCommandCenterStore(max_concurrent_runs=1)
    request_sha = hash_request({"workflow": "test"})
    first = store.create_run(run_id="AIGC-RUN-memory-1", idempotency_key="memory-run-key-0001",
                             request_sha256=request_sha, max_concurrent=1, lease_seconds=60)
    replay = store.create_run(run_id="AIGC-RUN-memory-2", idempotency_key="memory-run-key-0001",
                              request_sha256=request_sha, max_concurrent=1, lease_seconds=60)
    assert first.created and replay.replayed
    assert replay.run["run_id"] == first.run["run_id"]
    with pytest.raises(RunBusyError):
        store.create_run(run_id="AIGC-RUN-memory-3", idempotency_key="memory-run-key-0003",
                         request_sha256=request_sha, max_concurrent=1, lease_seconds=60)
    with pytest.raises(IdempotencyConflictError):
        store.create_run(run_id="AIGC-RUN-memory-4", idempotency_key="memory-run-key-0001",
                         request_sha256=hash_request({"workflow": "different"}),
                         max_concurrent=1, lease_seconds=60)


def _database_stores():
    dsn = os.environ.get("AIGC_TEST_DATABASE_DSN", "").strip()
    if not dsn:
        pytest.skip("AIGC_TEST_DATABASE_DSN is not configured")
    import psycopg
    migration = Path("migrations/003_command_center_state.sql").read_text(encoding="utf-8")
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(migration, prepare=False)
    first, second = PostgresCommandCenterStore(dsn), PostgresCommandCenterStore(dsn)
    with first._transaction() as connection:
        connection.execute("TRUNCATE command_center_review_decisions, command_center_runs")
    return first, second


def test_postgres_run_idempotency_and_restart_recovery() -> None:
    first, second = _database_stores()
    try:
        request_sha = hash_request({"workflow": "restart-test"})
        admission = first.create_run(run_id=f"AIGC-RUN-{uuid.uuid4()}",
                                     idempotency_key="postgres-run-restart-0001",
                                     request_sha256=request_sha, max_concurrent=1, lease_seconds=60)
        replay = second.create_run(run_id=f"AIGC-RUN-{uuid.uuid4()}",
                                   idempotency_key="postgres-run-restart-0001",
                                   request_sha256=request_sha, max_concurrent=1, lease_seconds=60)
        assert replay.replayed and replay.run["run_id"] == admission.run["run_id"]
        first.mark_run_running(admission.run["run_id"], lease_seconds=60)
        with second._transaction() as connection:
            connection.execute(
                "UPDATE command_center_runs SET lease_expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE run_id=%s",
                (admission.run["run_id"],),
            )
        recovered = second.get_run(admission.run["run_id"])
        assert recovered and recovered["status"] == "unknown" and recovered["complete"]
        with pytest.raises(IdempotencyConflictError):
            second.create_run(run_id=f"AIGC-RUN-{uuid.uuid4()}",
                              idempotency_key="postgres-run-restart-0001",
                              request_sha256=hash_request({"workflow": "different"}),
                              max_concurrent=1, lease_seconds=60)
    finally:
        first.close()
        second.close()


def test_postgres_two_instances_allow_only_one_active_run() -> None:
    first, second = _database_stores()
    try:
        def attempt(args):
            store, suffix = args
            try:
                result = store.create_run(run_id=f"AIGC-RUN-{uuid.uuid4()}",
                    idempotency_key=f"postgres-concurrent-run-{suffix:04d}",
                    request_sha256=hash_request({"workflow": "concurrent"}),
                    max_concurrent=1, lease_seconds=60)
                return "created" if result.created else "replayed"
            except RunBusyError:
                return "busy"
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, [(first, 1), (second, 2)]))
        assert results.count("created") == 1
        assert results.count("busy") == 1
    finally:
        first.close()
        second.close()


def test_postgres_review_claim_is_atomic_and_idempotent() -> None:
    first, second = _database_stores()
    try:
        action_id = f"action-{uuid.uuid4()}"
        request_sha = hash_request({"action_id": action_id, "decision": "accept"})
        def attempt(args):
            store, key, token = args
            try:
                result = store.claim_review(action_id=action_id, decision="accept",
                    idempotency_key=key, request_sha256=request_sha, claim_token=token, lease_seconds=60)
                return ("claimed", result, store, key, token)
            except ReviewDecisionConflictError:
                return ("conflict", None, store, key, token)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, [
                (first, "postgres-review-key-0001", "for-tests-claim-token-one"),
                (second, "postgres-review-key-0002", "for-tests-claim-token-two"),
            ]))
        assert sum(row[0] == "claimed" for row in results) == 1
        winner = next(row for row in results if row[0] == "claimed")
        outcome = {"ok": True, "decision_state": "accepted"}
        winner[2].finish_review(action_id=action_id, claim_token=winner[4], state="accepted", outcome=outcome)
        assert second.get_review_replay(action_id=action_id, idempotency_key=winner[3],
                                       request_sha256=request_sha) == outcome
        assert second.claim_review(action_id=action_id, decision="accept", idempotency_key=winner[3],
                                   request_sha256=request_sha, claim_token="for-tests-ignored-replay-token",
                                   lease_seconds=60) == outcome
        with pytest.raises(ReviewDecisionConflictError):
            second.claim_review(action_id=action_id, decision="accept",
                                idempotency_key="postgres-review-key-0003",
                                request_sha256=request_sha, claim_token="for-tests-new-token", lease_seconds=60)
    finally:
        first.close()
        second.close()


def test_production_requires_durable_state_dsn(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_ENV", "production")
    monkeypatch.delenv("AIGC_COMMAND_CENTER_STATE_DSN", raising=False)
    with pytest.raises(StateStoreNotConfiguredError):
        get_command_center_store(max_concurrent_runs=1)


def test_production_rejects_unverified_database_tls(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_ENV", "production")
    monkeypatch.setenv("AIGC_COMMAND_CENTER_STATE_DSN", "postgresql://app:secret@db.example/aigc?sslmode=require")
    with pytest.raises(StateStoreNotConfiguredError, match="sslmode=verify-full"):
        get_command_center_store(max_concurrent_runs=1)
