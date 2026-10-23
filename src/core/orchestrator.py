"""Redis Streams coordinator with bounded execution and best-effort Saga compensation.

Delivery semantics are at-least-once, not exactly-once. Handlers must be idempotent.
Redis pending entries require an operational reclaim policy; this module exposes a
reclaim method rather than pretending consumer crashes cannot happen.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Sequence

from src.core.contracts import (
    EventKind,
    OrchestrationEvent,
    SagaStepContract,
    TaskContract,
    TaskStatus,
)

TaskHandler = Callable[[TaskContract], Awaitable[dict[str, Any]]]
SagaCallable = Callable[[], Awaitable[Any]]


class OrchestrationError(RuntimeError):
    pass


class HopLimitExceeded(OrchestrationError):
    pass


class SagaExecutionError(OrchestrationError):
    def __init__(self, message: str, *, compensation_errors: Sequence[str] = ()):
        super().__init__(message)
        self.compensation_errors = tuple(compensation_errors)


@dataclass(frozen=True)
class SagaAction:
    contract: SagaStepContract
    execute: SagaCallable
    compensate: SagaCallable


@dataclass(frozen=True)
class SagaResult:
    status: str
    completed_steps: tuple[str, ...]
    compensation_errors: tuple[str, ...] = ()


class RedisStreamsCoordinator:
    """Small coordination adapter; pass an async redis.Redis client explicitly."""

    def __init__(
        self,
        redis_client: Any,
        *,
        stream: str = "aigc:tasks:v1",
        consumer_group: str = "aigc-workers-v1",
        dead_letter_stream: str = "aigc:tasks:dead-letter:v1",
        result_stream: str = "aigc:task-results:v1",
        max_hops: int = 10,
        max_timeout_seconds: float = 30.0,
    ) -> None:
        if not 1 <= max_hops <= 10:
            raise ValueError("max_hops must be between 1 and 10")
        if not 0 < max_timeout_seconds <= 30:
            raise ValueError("max_timeout_seconds must be in (0, 30]")
        self.redis = redis_client
        self.stream = stream
        self.consumer_group = consumer_group
        self.dead_letter_stream = dead_letter_stream
        self.result_stream = result_stream
        self.max_hops = max_hops
        self.max_timeout_seconds = max_timeout_seconds

    async def ensure_group(self) -> None:
        from redis.exceptions import ResponseError

        try:
            await self.redis.xgroup_create(
                name=self.stream, groupname=self.consumer_group, id="0", mkstream=True
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, task: TaskContract) -> bool:
        """Atomically reserve an idempotency key and append a task to the stream."""
        if task.hop_count >= min(task.max_hops, self.max_hops):
            raise HopLimitExceeded("Task is at its hop limit and cannot be enqueued again.")
        payload = task.model_dump_json()
        idempotency_key = f"aigc:idem:task:{task.idempotency_key}"
        script = """
        if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[3]) then
          redis.call('XADD', KEYS[2], '*', 'task_json', ARGV[2], 'task_id', ARGV[1])
          return 1
        end
        return 0
        """
        accepted = await self.redis.eval(
            script, 2, idempotency_key, self.stream, task.task_id, payload, 604800
        )
        return bool(accepted)

    async def consume_once(
        self,
        *,
        consumer_name: str,
        handler: TaskHandler,
        block_ms: int = 1000,
    ) -> bool:
        """Process one new message. Returns False when no message was available."""
        await self.ensure_group()
        batches = await self.redis.xreadgroup(
            groupname=self.consumer_group,
            consumername=consumer_name,
            streams={self.stream: ">"},
            count=1,
            block=max(1, min(block_ms, 5000)),
        )
        if not batches:
            return False

        for _stream_name, entries in batches:
            for message_id, fields in entries:
                await self._process_message(message_id, fields, handler)
                return True
        return False

    async def reclaim_pending(
        self,
        *,
        consumer_name: str,
        min_idle_ms: int = 60_000,
        start_id: str = "0-0",
        count: int = 10,
    ) -> tuple[str, ...]:
        """Claim abandoned pending messages; caller should process claimed IDs explicitly.

        This method intentionally does not auto-ack or discard claimed entries.
        """
        result = await self.redis.xautoclaim(
            name=self.stream,
            groupname=self.consumer_group,
            consumername=consumer_name,
            min_idle_time=max(1000, min_idle_ms),
            start_id=start_id,
            count=max(1, min(count, 100)),
        )
        claimed = result[1] if len(result) > 1 else []
        return tuple(str(message_id) for message_id, _fields in claimed)

    async def _process_message(
        self, message_id: Any, fields: dict[Any, Any], handler: TaskHandler
    ) -> None:
        raw = fields.get("task_json") or fields.get(b"task_json")
        try:
            if raw is None:
                raise ValueError("Message has no task_json field.")
            task = TaskContract.model_validate_json(raw)
            if task.hop_count >= min(task.max_hops, self.max_hops):
                raise HopLimitExceeded("Task exceeded the configured hop limit.")
            timeout = min(task.timeout_seconds, self.max_timeout_seconds)
            result = await asyncio.wait_for(handler(task), timeout=timeout)
            event = OrchestrationEvent(
                event_kind=EventKind.TASK_SUCCEEDED,
                task_id=task.task_id,
                idempotency_key=task.idempotency_key,
                hop_count=task.hop_count,
                data={"status": TaskStatus.SUCCEEDED.value, "result": result},
                telemetry=task.telemetry,
            )
            await self.redis.xadd(
                self.result_stream,
                {"event_json": event.model_dump_json(), "task_id": task.task_id},
            )
            await self.redis.xack(self.stream, self.consumer_group, message_id)
        except Exception as exc:
            await self._dead_letter(message_id, fields, exc)

    async def _dead_letter(self, message_id: Any, fields: dict[Any, Any], exc: Exception) -> None:
        raw = fields.get("task_json") or fields.get(b"task_json") or ""
        dead_letter = {
            "source_message_id": str(message_id),
            "reason": f"{type(exc).__name__}: {str(exc)[:1000]}",
            "task_json": raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw),
        }
        await self.redis.xadd(self.dead_letter_stream, dead_letter)
        await self.redis.xack(self.stream, self.consumer_group, message_id)

    @staticmethod
    async def run_saga(actions: Sequence[SagaAction]) -> SagaResult:
        """Execute steps in order and compensate completed steps in reverse on failure.

        Compensation is best-effort and bounded. Durable crash recovery must be
        supplied by a persistent Saga ledger; this in-process method is not one.
        """
        completed: list[SagaAction] = []
        try:
            for action in actions:
                timeout = min(action.contract.timeout_seconds, 30.0)
                await asyncio.wait_for(action.execute(), timeout=timeout)
                completed.append(action)
            return SagaResult("succeeded", tuple(a.contract.step_id for a in completed))
        except Exception as exc:
            compensation_errors: list[str] = []
            for action in reversed(completed):
                try:
                    await asyncio.wait_for(action.compensate(), timeout=min(action.contract.timeout_seconds, 30.0))
                except Exception as compensation_exc:
                    compensation_errors.append(
                        f"{action.contract.step_id}: {type(compensation_exc).__name__}: {str(compensation_exc)[:500]}"
                    )
            raise SagaExecutionError(
                f"Saga failed after {len(completed)} completed step(s): {type(exc).__name__}: {str(exc)[:500]}",
                compensation_errors=compensation_errors,
            ) from exc
