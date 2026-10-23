"""Async Saga coordinator for AIGC.

PostgreSQL is the durable source of truth (event log + transactional outbox);
Redis Streams is transport, not the authoritative ledger. Delivery is at-least-once:
consumers must deduplicate by event_id/idempotency_key. No LLM-generated code is
executed here. External side effects are disabled by default and require injected
trusted permit verification plus explicitly registered adapters.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import random
import time
from typing import Any, Awaitable, Callable, Mapping, Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError
from redis.asyncio import Redis
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from core.contracts import TaskContract, TaskStatus


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SagaStep:
    step_id: str
    operation: str
    input_payload: Mapping[str, Any]
    compensation_operation: str | None = None
    compensation_payload: Mapping[str, Any] | None = None
    irreversible: bool = False


@dataclass(frozen=True)
class StepReceipt:
    step_id: str
    status: str
    result: Mapping[str, Any]
    idempotency_key: str
    evidence_digest: str
    started_at_monotonic: float
    elapsed_seconds: float


class ActionAdapter(Protocol):
    async def __call__(self, payload: Mapping[str, Any], *, idempotency_key: str) -> Mapping[str, Any]: ...


PermitVerifier = Callable[[str, Mapping[str, Any], str], Awaitable[bool]]


class OrchestrationError(RuntimeError):
    pass


class SagaCoordinator:
    def __init__(
        self,
        *,
        database_url: str,
        redis_url: str,
        stream_name: str = "aigc:tasks:v1",
        consumer_group: str = "aigc-workers-v1",
        dry_run: bool = True,
        max_hops: int = 10,
        max_concurrency: int = 16,
        operation_timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        base_retry_seconds: float = 0.25,
        max_retry_seconds: float = 5.0,
        pool_min_size: int = 1,
        pool_max_size: int = 10,
        adapters: Mapping[str, ActionAdapter] | None = None,
        permit_verifier: PermitVerifier | None = None,
        redis_client: Redis | None = None,
    ):
        if max_hops < 1 or max_hops > 10:
            raise ValueError("max_hops must be between 1 and 10")
        if max_concurrency < 1 or max_concurrency > 256:
            raise ValueError("max_concurrency must be between 1 and 256")
        if operation_timeout_seconds <= 0 or operation_timeout_seconds > 300:
            raise ValueError("operation_timeout_seconds must be in (0, 300]")
        if max_attempts < 1 or max_attempts > 8:
            raise ValueError("max_attempts must be in [1, 8]")
        if pool_min_size < 1 or pool_max_size < pool_min_size:
            raise ValueError("invalid database pool bounds")
        self.database_url = database_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.dry_run = dry_run
        self.max_hops = max_hops
        self.operation_timeout_seconds = operation_timeout_seconds
        self.max_attempts = max_attempts
        self.base_retry_seconds = base_retry_seconds
        self.max_retry_seconds = max_retry_seconds
        self.adapters = dict(adapters or {})
        self.permit_verifier = permit_verifier
        self.redis: Redis = redis_client or Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5, socket_timeout=10)
        self._owns_redis = redis_client is None
        self.pool = AsyncConnectionPool(conninfo=database_url, min_size=pool_min_size, max_size=pool_max_size,
                                        open=False, kwargs={"row_factory": dict_row})
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def open(self) -> None:
        await self.pool.open(wait=True)
        await self.pool.wait()
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        await self.redis.ping()
        try:
            await self.redis.xgroup_create(self.stream_name, self.consumer_group, id="0-0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        await self._ensure_schema()

    async def close(self) -> None:
        await self.pool.close()
        if self._owns_redis:
            await self.redis.aclose()

    async def _ensure_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS aigc_tasks (
            task_id UUID PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            contract_version TEXT NOT NULL,
            project_id TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            status TEXT NOT NULL,
            hop_count INTEGER NOT NULL DEFAULT 0 CHECK (hop_count BETWEEN 0 AND 10),
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS aigc_events (
            event_id UUID PRIMARY KEY,
            task_id UUID NOT NULL REFERENCES aigc_tasks(task_id),
            sequence BIGINT NOT NULL,
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            payload_sha256 CHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(task_id, sequence)
        );
        CREATE TABLE IF NOT EXISTS aigc_outbox (
            event_id UUID PRIMARY KEY REFERENCES aigc_events(event_id),
            stream_id TEXT,
            published_at TIMESTAMPTZ,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS aigc_consumed_events (
            consumer_name TEXT NOT NULL,
            event_id UUID NOT NULL,
            consumed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY(consumer_name, event_id)
        );
        CREATE TABLE IF NOT EXISTS aigc_saga_steps (
            task_id UUID NOT NULL REFERENCES aigc_tasks(task_id),
            step_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            status TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            receipt JSONB,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY(task_id, step_id),
            UNIQUE(task_id, ordinal)
        );
        CREATE INDEX IF NOT EXISTS aigc_outbox_pending_idx ON aigc_outbox(created_at) WHERE published_at IS NULL;
        CREATE INDEX IF NOT EXISTS aigc_events_task_idx ON aigc_events(task_id, sequence);
        """
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(schema)

    async def submit(self, contract: TaskContract) -> dict[str, Any]:
        """Persist a task and its initial event atomically; duplicate keys are idempotent."""
        payload = contract.model_dump(mode="json")
        event_id = uuid4()
        event = {"event_id": str(event_id), "task_id": str(contract.task_id),
                 "event_type": "TASK_ACCEPTED", "contract": payload, "hop_count": 0}
        event_json = canonical_json(event)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        """INSERT INTO aigc_tasks(task_id,idempotency_key,contract_version,project_id,policy_version,status,hop_count,payload)
                           VALUES(%s,%s,%s,%s,%s,%s,0,%s::jsonb)
                           ON CONFLICT(idempotency_key) DO NOTHING
                           RETURNING task_id""",
                        (str(contract.task_id), contract.idempotency_key, contract.contract_version,
                         contract.project_id, contract.policy_version, TaskStatus.ACCEPTED.value, canonical_json(payload)),
                    )
                    inserted = await cur.fetchone()
                    if not inserted:
                        await cur.execute("SELECT task_id,status FROM aigc_tasks WHERE idempotency_key=%s",
                                          (contract.idempotency_key,))
                        existing = await cur.fetchone()
                        if not existing:
                            raise OrchestrationError("idempotency_conflict_without_existing_task")
                        return {"status": "IDEMPOTENT_REPLAY", "task_id": str(existing["task_id"]),
                                "task_status": existing["status"], "side_effects_performed": False}
                    await cur.execute(
                        "INSERT INTO aigc_events(event_id,task_id,sequence,event_type,payload,payload_sha256) VALUES(%s,%s,1,%s,%s::jsonb,%s)",
                        (str(event_id), str(contract.task_id), "TASK_ACCEPTED", event_json, sha256_text(event_json)),
                    )
                    await cur.execute("INSERT INTO aigc_outbox(event_id) VALUES(%s)", (str(event_id),))
        return {"status": "ACCEPTED", "task_id": str(contract.task_id), "event_id": str(event_id),
                "side_effects_performed": False, "transport": "transactional_outbox"}

    async def publish_outbox(self, *, batch_size: int = 100) -> int:
        """Publish outbox records; duplicate stream entries are safe because event_id is stable."""
        if batch_size < 1 or batch_size > 1000:
            raise ValueError("batch_size must be in [1,1000]")
        published = 0
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        """SELECT o.event_id,e.payload FROM aigc_outbox o
                           JOIN aigc_events e USING(event_id)
                           WHERE o.published_at IS NULL ORDER BY o.created_at
                           FOR UPDATE OF o SKIP LOCKED LIMIT %s""", (batch_size,))
                    rows = await cur.fetchall()
                    for row in rows:
                        event_id = str(row["event_id"])
                        event_payload = row["payload"]
                        if not isinstance(event_payload, str):
                            event_payload = canonical_json(event_payload)
                        stream_id = await self.redis.xadd(self.stream_name, {"event_id": event_id, "payload": event_payload})
                        await cur.execute("UPDATE aigc_outbox SET stream_id=%s,published_at=now(),attempts=attempts+1 WHERE event_id=%s",
                                          (stream_id, event_id))
                        published += 1
        return published

    async def record_event(self, task_id: UUID, event_type: str, payload: Mapping[str, Any]) -> str:
        event_id = uuid4()
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute("SELECT COALESCE(MAX(sequence),0)+1 AS seq FROM aigc_events WHERE task_id=%s FOR UPDATE",
                                      (str(task_id),))
                    row = await cur.fetchone()
                    seq = int(row["seq"])
                    event = {"event_id": str(event_id), "task_id": str(task_id), "sequence": seq,
                             "event_type": event_type, "payload": dict(payload)}
                    encoded = canonical_json(event)
                    await cur.execute(
                        "INSERT INTO aigc_events(event_id,task_id,sequence,event_type,payload,payload_sha256) VALUES(%s,%s,%s,%s,%s::jsonb,%s)",
                        (str(event_id), str(task_id), seq, event_type, encoded, sha256_text(encoded)))
                    await cur.execute("UPDATE aigc_tasks SET updated_at=now() WHERE task_id=%s", (str(task_id),))
        return str(event_id)

    async def consume_once(self, handler: Callable[[Mapping[str, Any]], Awaitable[None]], *, block_ms: int = 1000) -> int:
        """Read one stream batch; duplicate deliveries are handled by DB event dedupe."""
        if block_ms < 1 or block_ms > 30_000:
            raise ValueError("block_ms must be in [1,30000]")
        entries = await self.redis.xreadgroup(self.consumer_group, "aigc-worker-" + str(id(self)),
                                              {self.stream_name: ">"}, count=16, block=block_ms)
        processed = 0
        for _, messages in entries:
            for stream_id, fields in messages:
                try:
                    event_id = UUID(fields["event_id"])
                    event = json.loads(fields["payload"])
                    if event.get("event_id") != str(event_id):
                        raise OrchestrationError("stream_event_id_payload_mismatch")
                    async with self.pool.connection() as conn:
                        async with conn.transaction():
                            async with conn.cursor() as cur:
                                await cur.execute(
                                    "INSERT INTO aigc_consumed_events(consumer_name,event_id) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING event_id",
                                    (self.consumer_group, str(event_id)))
                                claimed = await cur.fetchone()
                                if claimed:
                                    await handler(event)
                    await self.redis.xack(self.stream_name, self.consumer_group, stream_id)
                    processed += 1
                except Exception:
                    # Do not ACK failed events. They remain pending for bounded reclaim
                    # by an operator-controlled recovery worker; never hot-loop poison pills.
                    raise
        return processed

    async def run_saga(self, contract: TaskContract, steps: list[SagaStep], *,
                       dry_run: bool | None = None, permit_ref: str | None = None) -> dict[str, Any]:
        """Run an explicitly registered saga; default dry-run, compensate completed steps in reverse order."""
        dry = self.dry_run if dry_run is None else dry_run
        if len(steps) > self.max_hops or len(steps) > contract.max_hops:
            raise OrchestrationError("saga_hop_limit_exceeded")
        if len({step.step_id for step in steps}) != len(steps):
            raise OrchestrationError("duplicate_saga_step_id")
        if any(not step.step_id or not step.operation for step in steps):
            raise OrchestrationError("saga_step_identity_missing")
        if not dry:
            if self.permit_verifier is None or not permit_ref:
                raise OrchestrationError("authenticated_permit_verifier_and_receipt_required")
            if not await self.permit_verifier(permit_ref, {"task_id": str(contract.task_id),
                    "policy_version": contract.policy_version, "steps": [s.operation for s in steps]}, contract.idempotency_key):
                raise OrchestrationError("permit_verification_denied")
        receipts: list[StepReceipt] = []
        completed: list[SagaStep] = []
        started_all = time.monotonic()
        async with self.semaphore:
            for index, step in enumerate(steps):
                if index >= min(self.max_hops, contract.max_hops):
                    raise OrchestrationError("saga_hop_limit_exceeded")
                if step.operation not in self.adapters:
                    raise OrchestrationError("operation_not_allowlisted:" + step.operation)
                if step.irreversible and (dry or not permit_ref):
                    raise OrchestrationError("irreversible_step_requires_verified_human_approval")
                key = hashlib.sha256(f"{contract.idempotency_key}:{step.step_id}".encode()).hexdigest()
                started = time.monotonic()
                if dry:
                    result = {"mode": "DRY_RUN", "operation": step.operation, "input_digest": sha256_text(canonical_json(dict(step.input_payload))),
                              "side_effects_performed": False}
                    status = "SIMULATED"
                else:
                    result = await self._invoke_with_retry(self.adapters[step.operation], step.input_payload, key,
                                                           timeout=min(self.operation_timeout_seconds, contract.timeout_seconds))
                    status = "SUCCEEDED"
                    completed.append(step)
                receipt_body = {"step_id": step.step_id, "operation": step.operation, "status": status,
                                "result": result, "idempotency_key": key, "task_id": str(contract.task_id)}
                receipts.append(StepReceipt(step.step_id, status, result, key, sha256_text(canonical_json(receipt_body)),
                                            started, time.monotonic() - started))
                await self.record_event(contract.task_id, "SAGA_STEP_" + status,
                    {"step_id": step.step_id, "operation": step.operation, "idempotency_key": key,
                     "result_digest": receipts[-1].evidence_digest, "dry_run": dry})
        return {"task_id": str(contract.task_id), "status": "DRY_RUN_PLAN" if dry else "SUCCEEDED",
                "steps": [r.__dict__ for r in receipts], "elapsed_seconds": time.monotonic() - started_all,
                "side_effects_performed": bool(completed), "compensation": "NOT_REQUIRED",
                "release_authorization": False, "merge_authorization": False}

    async def _invoke_with_retry(self, adapter: ActionAdapter, payload: Mapping[str, Any], key: str,
                                 *, timeout: float) -> Mapping[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                async with asyncio.timeout(timeout):
                    result = await adapter(payload, idempotency_key=key)
                if not isinstance(result, Mapping):
                    raise OrchestrationError("adapter_result_must_be_mapping")
                return dict(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= self.max_attempts:
                    break
                ceiling = min(self.max_retry_seconds, self.base_retry_seconds * (2 ** attempt))
                await asyncio.sleep(random.uniform(0, ceiling))
        raise OrchestrationError("adapter_failed_after_bounded_idempotent_retries:" + type(last_error).__name__) from last_error
