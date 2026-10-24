from __future__ import annotations

import hashlib
import os
from pathlib import Path
import uuid

import pytest

from src.core.contracts import TaskContract
from src.core.task_lifecycle_store import (
    PostgresTaskLifecycleStore,
    TaskIdempotencyConflict,
    TaskNotFound,
)


@pytest.fixture
def task_store():
    dsn = os.environ.get("AIGC_COMMAND_CENTER_TEST_DATABASE_URL", "").strip()
    if not dsn:
        pytest.skip("PostgreSQL integration service is not configured")
    import psycopg
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations" / "command_center_postgresql"
        / "0002_governed_task_outbox.sql"
    ).read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(migration, prepare=False)
        conn.execute("DELETE FROM aigc_task_outbox")
        conn.execute("DELETE FROM aigc_tasks")
    store = PostgresTaskLifecycleStore(dsn, sslmode="disable")
    try:
        yield store
    finally:
        store.close()


def make_task(key: str, payload: dict | None = None) -> TaskContract:
    return TaskContract(
        idempotency_key=key,
        task_type="test.echo",
        payload=payload or {"message": "hello"},
    )


def test_submit_task_and_outbox_are_atomic_and_replayable(task_store) -> None:
    key = f"task-key-{uuid.uuid4()}"
    task = make_task(key)
    first = task_store.submit_task(owner_id="owner-1", idempotency_key=key, task=task)
    replay = task_store.submit_task(owner_id="owner-1", idempotency_key=key, task=make_task(key))
    assert first["status"] == "queued"
    assert first["replayed"] is False
    assert replay["replayed"] is True
    assert replay["task_id"] == first["task_id"]
    with pytest.raises(TaskIdempotencyConflict):
        task_store.submit_task(
            owner_id="owner-1", idempotency_key=key,
            task=make_task(key, {"message": "different"}),
        )
    claimed = task_store.claim_outbox(dispatcher_id="dispatcher-test")
    assert claimed is not None and claimed["task_id"] == first["task_id"]
    task_store.mark_dispatched(outbox_id=claimed["outbox_id"], dispatcher_id="dispatcher-test")
    assert task_store.claim_outbox(dispatcher_id="dispatcher-test-2") is None


def test_outbox_lease_can_be_reclaimed_after_dispatcher_crash(task_store) -> None:
    key = f"task-key-{uuid.uuid4()}"
    task = make_task(key)
    record = task_store.submit_task(owner_id="owner-1", idempotency_key=key, task=task)
    claimed = task_store.claim_outbox(dispatcher_id="dispatcher-crashed", lease_seconds=5)
    assert claimed is not None
    import psycopg
    dsn = os.environ["AIGC_COMMAND_CENTER_TEST_DATABASE_URL"]
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "UPDATE aigc_task_outbox SET lease_until=now()-interval '1 second' WHERE outbox_id=%s",
            (claimed["outbox_id"],),
        )
    reclaimed = task_store.claim_outbox(dispatcher_id="dispatcher-restarted")
    assert reclaimed is not None
    assert reclaimed["outbox_id"] == claimed["outbox_id"]
    assert reclaimed["attempts"] == 2


def test_task_terminal_success_requires_running_and_verified_artifact(task_store) -> None:
    key = f"task-key-{uuid.uuid4()}"
    record = task_store.submit_task(owner_id="owner-1", idempotency_key=key, task=make_task(key))
    with pytest.raises(TaskNotFound):
        task_store.complete_task(
            owner_id="owner-1", task_id=record["task_id"],
            result={"ok": True}, artifact_bytes=b"test artifact",
        )
    task_store.mark_running(owner_id="owner-1", task_id=record["task_id"])
    result = task_store.complete_task(
        owner_id="owner-1", task_id=record["task_id"],
        result={"ok": True}, artifact_bytes=b"test artifact",
    )
    assert result["status"] == "succeeded"
    assert result["artifact_sha256"] == hashlib.sha256(b"test artifact").hexdigest()
    assert result["evidence"]["verified"] is True
    assert result["evidence"]["task_id"] == record["task_id"]


def test_task_result_and_artifact_evidence_commit_together(task_store) -> None:
    key = f"task-key-{uuid.uuid4()}"
    record = task_store.submit_task(owner_id="owner-1", idempotency_key=key, task=make_task(key))
    task_store.mark_running(owner_id="owner-1", task_id=record["task_id"])
    completed = task_store.complete_task(
        owner_id="owner-1", task_id=record["task_id"],
        result={"value": 7}, artifact_bytes=b'{"value":7}',
    )
    fetched = task_store.get_task(owner_id="owner-1", task_id=record["task_id"])
    assert fetched is not None and fetched["status"] == "succeeded"
    assert fetched["artifact_sha256"] == completed["artifact_sha256"]
    assert fetched["evidence"]["artifact_sha256"] == completed["artifact_sha256"]
