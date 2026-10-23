"""Run the governed synthetic durable-task worker and outbox dispatcher.

Required environment:
  AIGC_TASK_DATABASE_URL (or AIGC_COMMAND_CENTER_DATABASE_URL)
  AIGC_REDIS_URL

This pilot only registers test.echo; no shell, network, model, or external-action
handlers are available. PostgreSQL remains authoritative for task lifecycle state.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket

from redis.asyncio import Redis

from src.core.orchestrator import RedisStreamsCoordinator
from src.core.task_lifecycle_dispatcher import OutboxDispatcher
from src.core.task_lifecycle_store import PostgresTaskLifecycleStore
from src.core.task_lifecycle_worker import DurableSyntheticWorker

logging.basicConfig(
    level=os.environ.get("AIGC_WORKER_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOG = logging.getLogger("aigc.durable_worker")


async def run() -> None:
    dsn = os.environ.get("AIGC_TASK_DATABASE_URL", os.environ.get("AIGC_COMMAND_CENTER_DATABASE_URL", "")).strip()
    redis_url = os.environ.get("AIGC_REDIS_URL", "").strip()
    if not dsn or not redis_url:
        raise SystemExit("AIGC_TASK_DATABASE_URL and AIGC_REDIS_URL are required")
    sslmode = os.environ.get("AIGC_TASK_DATABASE_SSLMODE", "verify-full").strip()
    sslrootcert = os.environ.get("AIGC_TASK_DATABASE_SSLROOTCERT", "").strip() or None
    consumer_name = os.environ.get("AIGC_WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")[:128]
    store = PostgresTaskLifecycleStore(dsn, sslmode=sslmode, sslrootcert=sslrootcert)
    redis = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5, socket_timeout=10)
    coordinator = RedisStreamsCoordinator(redis)
    dispatcher = OutboxDispatcher(store, coordinator, dispatcher_id=consumer_name)
    worker = DurableSyntheticWorker(store)
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:
            pass

    try:
        await redis.ping()
        store.healthcheck()
        await coordinator.ensure_group()
        LOG.info("worker started; registered task types: test.echo")
        while not stopping.is_set():
            progressed = False
            try:
                if await dispatcher.dispatch_once():
                    progressed = True
            except Exception as exc:
                LOG.warning("outbox dispatch failed (%s)", type(exc).__name__)
            try:
                # Reclaim only messages idle for at least 60 seconds. A PostgreSQL
                # execution lease prevents a live task from being run twice.
                reclaimed = await coordinator.reclaim_pending(
                    consumer_name=consumer_name,
                    handler=worker.handle,
                    min_idle_ms=60_000,
                    count=10,
                )
                progressed = progressed or reclaimed > 0
                consumed = await coordinator.consume_once(
                    consumer_name=consumer_name, handler=worker.handle, block_ms=1000
                )
                progressed = progressed or consumed
            except Exception as exc:
                LOG.warning("stream consumption failed (%s)", type(exc).__name__)
                await asyncio.sleep(1)
            if not progressed:
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
    finally:
        await redis.aclose()
        store.close()
        LOG.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(run())
