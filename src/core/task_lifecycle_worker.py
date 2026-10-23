"""Harmless governed worker for the first durable task vertical slice.

Only the explicit test.echo handler is registered. Unknown task types fail closed;
this module performs no external actuation or connector calls.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from src.core.contracts import TaskContract
from src.core.task_lifecycle_store import PostgresTaskLifecycleStore


class DurableSyntheticWorker:
    def __init__(self, store: PostgresTaskLifecycleStore):
        self.store = store

    async def handle(self, task: TaskContract) -> dict[str, Any]:
        claim = self.store.claim_task_for_execution(task_id=task.task_id)
        if claim is None:
            # A duplicate Redis delivery must not execute a terminal/already-claimed task.
            return {"ignored_duplicate": True, "task_id": task.task_id}

        owner_id = claim["owner_id"]
        try:
            if task.deadline_at is not None and task.deadline_at <= datetime.now(timezone.utc):
                raise TimeoutError("Task deadline has elapsed")
            if task.task_type != "test.echo":
                raise ValueError("Task type is not registered for synthetic execution")
            message = task.payload.get("message", "")
            if not isinstance(message, str) or len(message) > 10000:
                raise ValueError("test.echo message must be a string of at most 10000 characters")
            result = {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "message": message,
                "synthetic": True,
                "external_actions_performed": False,
            }
            artifact_bytes = json.dumps(
                result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
            if len(artifact_bytes) > 1_000_000:
                raise ValueError("Synthetic artifact exceeds the 1 MB limit")
            completed = self.store.complete_task(
                owner_id=owner_id,
                task_id=task.task_id,
                result=result,
                artifact_bytes=artifact_bytes,
            )
            if completed.get("artifact_sha256") != hashlib.sha256(artifact_bytes).hexdigest():
                raise RuntimeError("Persisted artifact digest does not match the worker output")
            return {"task_id": task.task_id, "status": completed["status"], "artifact_sha256": completed["artifact_sha256"]}
        except asyncio.CancelledError:
            self._record_failure(owner_id, task.task_id, "worker_cancelled")
            raise
        except Exception as exc:
            self._record_failure(owner_id, task.task_id, type(exc).__name__)
            raise

    def _record_failure(self, owner_id: str, task_id: str, failure_class: str) -> None:
        try:
            self.store.fail_task(owner_id=owner_id, task_id=task_id, failure_class=failure_class)
        except Exception:
            # The durable lease remains for the recovery controller; never mask the original failure.
            pass
