from __future__ import annotations
import asyncio, os, uuid
import pytest
from redis.asyncio import Redis
from src.core.contracts import TaskContract
from src.core.orchestrator import RedisStreamsCoordinator
from src.core.task_lifecycle_dispatcher import OutboxDispatcher
from src.core.task_lifecycle_store import PostgresTaskLifecycleStore
from src.core.task_lifecycle_worker import DurableSyntheticWorker

@pytest.fixture
def durable_runtime():
    pg_dsn = os.environ.get("AIGC_COMMAND_CENTER_TEST_DATABASE_URL", "").strip()
    redis_url = os.environ.get("AIGC_REDIS_TEST_URL", "").strip()
    if not pg_dsn or not redis_url:
        pytest.skip("Isolated PostgreSQL and Redis services are required")
    import psycopg
    from pathlib import Path
    migration = (Path(__file__).resolve().parents[1] / "migrations" / "command_center_postgresql" / "0002_governed_task_outbox.sql").read_text(encoding="utf-8")
    with psycopg.connect(pg_dsn) as conn:
        conn.execute(migration, prepare=False)
        conn.execute("DELETE FROM aigc_task_outbox")
        conn.execute("DELETE FROM aigc_tasks")
    store = PostgresTaskLifecycleStore(pg_dsn, sslmode="disable")
    redis = Redis.from_url(redis_url, decode_responses=True)
    coordinator = RedisStreamsCoordinator(redis, stream=f"aigc:test:tasks:{uuid.uuid4()}", consumer_group=f"aigc:test:workers:{uuid.uuid4()}", dead_letter_stream=f"aigc:test:dead:{uuid.uuid4()}", result_stream=f"aigc:test:results:{uuid.uuid4()}")
    try:
        yield store, redis, coordinator
    finally:
        asyncio.run(redis.aclose())
        store.close()

def test_postgres_outbox_redis_worker_end_to_end(durable_runtime):
    store, redis, coordinator = durable_runtime
    worker = DurableSyntheticWorker(store)
    key = f"e2e-task-{uuid.uuid4()}"
    task = TaskContract(idempotency_key=key, task_type="test.echo", payload={"message": "hello"})
    submitted = store.submit_task(owner_id="e2e-owner", idempotency_key=key, task=task)
    dispatcher = OutboxDispatcher(store, coordinator, dispatcher_id="e2e-dispatcher")
    async def execute():
        assert await dispatcher.dispatch_once() is True
        assert await dispatcher.dispatch_once() is False
        assert await coordinator.consume_once(consumer_name="e2e-worker", handler=worker.handle, block_ms=1) is True
        # Simulate duplicate delivery after publish but before outbox acknowledgement.
        await redis.xadd(coordinator.stream, {"task_json": task.model_dump_json(), "task_id": task.task_id})
        assert await coordinator.consume_once(consumer_name="e2e-worker", handler=worker.handle, block_ms=1) is True
    asyncio.run(execute())
    persisted = store.get_task(owner_id="e2e-owner", task_id=submitted["task_id"])
    assert persisted is not None and persisted["status"] == "succeeded"
    assert persisted["evidence"]["verified"] is True
    assert persisted["artifact_sha256"] == persisted["evidence"]["artifact_sha256"]

def test_dispatch_failure_releases_outbox_for_retry(durable_runtime):
    store, _redis, _coordinator = durable_runtime
    key = f"e2e-fail-{uuid.uuid4()}"
    task = TaskContract(idempotency_key=key, task_type="test.echo", payload={"message": "retry"})
    store.submit_task(owner_id="e2e-owner", idempotency_key=key, task=task)
    class BrokenCoordinator:
        async def enqueue_with_receipt(self, _task):
            raise ConnectionError("simulated Redis outage")
    dispatcher = OutboxDispatcher(store, BrokenCoordinator(), dispatcher_id="retry-dispatcher")
    with pytest.raises(ConnectionError):
        asyncio.run(dispatcher.dispatch_once())
    claimed = store.claim_outbox(dispatcher_id="retry-dispatcher-2")
    assert claimed is not None and claimed["task_id"] == task.task_id
