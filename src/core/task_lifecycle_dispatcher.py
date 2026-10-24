"""Transactional outbox dispatcher for PostgreSQL -> Redis Streams.

Delivery is at-least-once. The durable task row remains authoritative; the Redis
stream and idempotency reservation are transport/deduplication aids only.
"""
from __future__ import annotations

from typing import Any

from src.core.contracts import TaskContract
from src.core.task_lifecycle_store import PostgresTaskLifecycleStore


class OutboxDispatcher:
    def __init__(self, store: PostgresTaskLifecycleStore, coordinator: Any, *, dispatcher_id: str):
        if not dispatcher_id or len(dispatcher_id) > 128:
            raise ValueError("dispatcher_id must contain 1..128 characters")
        self.store = store
        self.coordinator = coordinator
        self.dispatcher_id = dispatcher_id

    async def dispatch_once(self) -> bool:
        receipt = self.store.claim_outbox(dispatcher_id=self.dispatcher_id)
        if receipt is None:
            return False
        outbox_id = int(receipt["outbox_id"])
        try:
            raw_contract = receipt["payload_json"]
            task = TaskContract.model_validate(raw_contract)
            queued = await self.coordinator.enqueue_with_receipt(task)
            if queued.task_id != task.task_id:
                raise RuntimeError("Redis idempotency receipt returned a different task identity")
            # A crash before this acknowledgement causes a safe replay on the next lease.
            self.store.mark_dispatched(outbox_id=outbox_id, dispatcher_id=self.dispatcher_id)
            return True
        except Exception as exc:
            try:
                self.store.release_outbox(
                    outbox_id=outbox_id,
                    dispatcher_id=self.dispatcher_id,
                    error_class=type(exc).__name__,
                )
            except Exception:
                # Leave the lease to expire; another dispatcher can reclaim it.
                pass
            raise
