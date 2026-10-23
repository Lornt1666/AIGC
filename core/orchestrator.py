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
import math
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


def dead_letter_disposition_id(source_stream: str, source_stream_id: str) -> str:
    """Stable key for one source-stream entry; JSON framing avoids delimiter collisions."""
    if not isinstance(source_stream, str) or not source_stream:
        raise ValueError("source_stream must be non-empty text")
    if not isinstance(source_stream_id, str) or not source_stream_id:
        raise ValueError("source_stream_id must be non-empty text")
    return sha256_text(canonical_json([source_stream, source_stream_id]))


def validate_hop_count(value: Any, max_hops: int) -> int:
    """Reject malformed, negative, boolean, and over-limit hop counts."""
    if not isinstance(max_hops, int) or isinstance(max_hops, bool) or not 1 <= max_hops <= 10:
        raise ValueError("max_hops must be an integer in [1, 10]")
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= max_hops:
        raise OrchestrationError("message_hop_limit_exceeded")
    return value


@dataclass(frozen=True)
class SagaStep:
    step_id: str
    operation: str
    input_payload: Mapping[str, Any]
    compensation_operation: str | None = None
    compensation_payload: Mapping[str, Any] | None = None
    irreversible: bool = False
    side_effecting: bool = True
    approval_receipt_ref: str | None = None
    idempotent: bool = False
    compensation_idempotent: bool = False


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
OutcomeReconciler = Callable[[str, Mapping[str, Any], str], Awaitable[str]]


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
        dead_letter_stream: str = "aigc:dead-letter:v1",
        max_deliveries: int = 5,
        pending_idle_ms: int = 30_000,
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
        outcome_reconciler: OutcomeReconciler | None = None,
        redis_client: Redis | None = None,
    ):
        if max_hops < 1 or max_hops > 10:
            raise ValueError("max_hops must be between 1 and 10")
        if max_concurrency < 1 or max_concurrency > 256:
            raise ValueError("max_concurrency must be between 1 and 256")
        if not math.isfinite(operation_timeout_seconds) or operation_timeout_seconds <= 0 or operation_timeout_seconds > 300:
            raise ValueError("operation_timeout_seconds must be finite and in (0, 300]")
        if max_attempts < 1 or max_attempts > 8:
            raise ValueError("max_attempts must be in [1, 8]")
        if not math.isfinite(base_retry_seconds) or not math.isfinite(max_retry_seconds):
            raise ValueError("retry delays must be finite")
        if base_retry_seconds < 0 or max_retry_seconds < base_retry_seconds or max_retry_seconds > 60:
            raise ValueError("retry delays must satisfy 0 <= base <= max <= 60 seconds")
        if pool_min_size < 1 or pool_max_size < pool_min_size or pool_max_size > 256:
            raise ValueError("database pool bounds must satisfy 1 <= min <= max <= 256")
        self.database_url = database_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.dead_letter_stream = dead_letter_stream
        if max_deliveries < 1 or max_deliveries > 20:
            raise ValueError("max_deliveries must be in [1,20]")
        if pending_idle_ms < 1000 or pending_idle_ms > 3_600_000:
            raise ValueError("pending_idle_ms must be in [1000,3600000]")
        self.max_deliveries = max_deliveries
        self.pending_idle_ms = pending_idle_ms
        self._pending_cursor = "0-0"
        self.dry_run = dry_run
        self.max_hops = max_hops
        self.operation_timeout_seconds = operation_timeout_seconds
        self.max_attempts = max_attempts
        self.base_retry_seconds = base_retry_seconds
        self.max_retry_seconds = max_retry_seconds
        self.adapters = dict(adapters or {})
        self.permit_verifier = permit_verifier
        self.outcome_reconciler = outcome_reconciler
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
        """Verify a separately applied migration; the runtime identity has no DDL privilege."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT version FROM aigc_schema_migrations WHERE version = %s", ("001_runtime",))
                migration = await cur.fetchone()
                if not migration:
                    raise OrchestrationError("required_migration_missing:001_runtime")
                await cur.execute("SELECT version FROM aigc_schema_migrations WHERE version = %s", ("002_receipt_claims",))
                receipt_migration = await cur.fetchone()
                if not receipt_migration:
                    raise OrchestrationError("required_migration_missing:002_receipt_claims")
                await cur.execute("SELECT version FROM aigc_schema_migrations WHERE version = %s", ("003_dead_letters",))
                dead_letter_migration = await cur.fetchone()
                if not dead_letter_migration:
                    raise OrchestrationError("required_migration_missing:003_dead_letters")
                await cur.execute("SELECT to_regclass(%s) AS tasks, to_regclass(%s) AS events, to_regclass(%s) AS outbox, to_regclass(%s) AS consumed, to_regclass(%s) AS dead_letters",
                    ("public.aigc_tasks", "public.aigc_events", "public.aigc_outbox", "public.aigc_consumed_events", "public.aigc_dead_letters"))
                tables = await cur.fetchone()
                if not tables or any(not tables[name] for name in ("tasks", "events", "outbox", "consumed", "dead_letters")):
                    raise OrchestrationError("required_runtime_schema_missing_or_incomplete")
                await cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname=%s AND tgrelid=to_regclass(%s) AND NOT tgisinternal) AS present",
                    ("aigc_events_no_update", "public.aigc_events"),
                )
                trigger = await cur.fetchone()
                if not trigger or trigger["present"] is not True:
                    raise OrchestrationError("append_only_event_trigger_missing")
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
                        await cur.execute("SELECT task_id,status,payload FROM aigc_tasks WHERE idempotency_key=%s",
                                          (contract.idempotency_key,))
                        existing = await cur.fetchone()
                        if not existing:
                            raise OrchestrationError("idempotency_conflict_without_existing_task")
                        existing_payload = existing["payload"]
                        if isinstance(existing_payload, str):
                            existing_payload = json.loads(existing_payload)
                        if canonical_json(existing_payload) != canonical_json(payload):
                            raise OrchestrationError("idempotency_key_reused_with_different_payload")
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
                    await cur.execute("SELECT task_id FROM aigc_tasks WHERE task_id=%s FOR UPDATE", (str(task_id),))
                    if not await cur.fetchone():
                        raise OrchestrationError("task_not_found_for_event")
                    await cur.execute("SELECT COALESCE(MAX(sequence),0)+1 AS seq FROM aigc_events WHERE task_id=%s",
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

    async def transition_task(self, task_id: UUID, next_status: TaskStatus, *, reason: str, evidence: Mapping[str, Any] | None = None) -> bool:
        """Apply a validated task state transition and append its event atomically."""
        allowed = {
            TaskStatus.ACCEPTED: {TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.FAILED},
            TaskStatus.READY: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.FAILED},
            TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.PARTIAL, TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.COMPENSATING},
            TaskStatus.COMPENSATING: {TaskStatus.COMPENSATED, TaskStatus.BLOCKED, TaskStatus.FAILED},
        }
        if not isinstance(next_status, TaskStatus) or not isinstance(reason, str) or not reason.strip():
            raise OrchestrationError("task_transition_contract_invalid")
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute("SELECT status FROM aigc_tasks WHERE task_id=%s FOR UPDATE", (str(task_id),))
                    row = await cur.fetchone()
                    if not row:
                        raise OrchestrationError("task_not_found_for_transition")
                    current = TaskStatus(row["status"])
                    if current == next_status:
                        return False
                    if next_status not in allowed.get(current, set()):
                        raise OrchestrationError("task_state_transition_not_allowed:" + current.value + "->" + next_status.value)
                    await cur.execute("SELECT COALESCE(MAX(sequence),0)+1 AS seq FROM aigc_events WHERE task_id=%s", (str(task_id),))
                    sequence = int((await cur.fetchone())["seq"])
                    event_id = uuid4()
                    payload = {"event_id": str(event_id), "task_id": str(task_id), "sequence": sequence,
                               "event_type": "TASK_STATE_TRANSITION", "previous_status": current.value,
                               "next_status": next_status.value, "reason": reason, "evidence": dict(evidence or {})}
                    encoded = canonical_json(payload)
                    await cur.execute("INSERT INTO aigc_events(event_id,task_id,sequence,event_type,payload,payload_sha256) VALUES(%s,%s,%s,%s,%s::jsonb,%s)",
                        (str(event_id), str(task_id), sequence, "TASK_STATE_TRANSITION", encoded, sha256_text(encoded)))
                    await cur.execute("UPDATE aigc_tasks SET status=%s,updated_at=now() WHERE task_id=%s", (next_status.value, str(task_id)))
        return True
    async def consume_once(self, handler: Callable[[Mapping[str, Any], Any], Awaitable[None]], *, block_ms: int = 1000) -> int:
        """Process pending retries before new entries; poison messages are dead-lettered at a fixed ceiling."""
        if block_ms < 1 or block_ms > 30_000:
            raise ValueError("block_ms must be in [1,30000]")
        await self._publish_pending_dead_letters(limit=100)
        consumer = "aigc-worker-" + str(id(self))
        entries: list[tuple[str, Mapping[str, str]]] = []
        claimed = await self.redis.xautoclaim(self.stream_name, self.consumer_group, consumer,
                                               min_idle_time=self.pending_idle_ms, start_id=self._pending_cursor, count=16)
        if claimed:
            # XAUTOCLAIM returns a scan cursor; advancing it prevents repeatedly
            # rescanning only the first page of a large pending-entry list.
            self._pending_cursor = claimed[0] or "0-0"
        if len(claimed) >= 3 and claimed[2]:
            # Redis 7+ removes trimmed/deleted entries from the PEL during XAUTOCLAIM.
            # Preserve the lost-entry IDs in PostgreSQL because their original payload
            # is no longer recoverable from Redis.
            for missing_stream_id in claimed[2]:
                disposition_id = await self._persist_dead_letter(
                    stream_id=str(missing_stream_id), event_id="missing",
                    payload="", failure_type="RedisStreamEntryMissingAfterTrim",
                    delivery_count=0)
                await self._publish_dead_letter(disposition_id)
        if len(claimed) >= 2 and claimed[1]:
            entries.extend((stream_id, fields) for stream_id, fields in claimed[1])
        if not entries:
            new_entries = await self.redis.xreadgroup(self.consumer_group, consumer,
                {self.stream_name: ">"}, count=16, block=block_ms)
            for _, messages in new_entries:
                entries.extend(messages)
        processed = 0
        for stream_id, fields in entries:
            event_id = fields.get("event_id", "missing")
            try:
                event = json.loads(fields["payload"])
                parsed_id = UUID(event_id)
                if not isinstance(event, Mapping) or event.get("event_id") != str(parsed_id):
                    raise OrchestrationError("stream_event_id_payload_mismatch")
                hop_count = validate_hop_count(event.get("hop_count", 0), self.max_hops)
                async with self.pool.connection() as conn:
                    async with conn.transaction():
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "INSERT INTO aigc_consumed_events(consumer_name,event_id) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING event_id",
                                (self.consumer_group, str(parsed_id)))
                            claimed_event = await cur.fetchone()
                            if claimed_event:
                                # Handler must perform only DB-local work using this
                                # transaction; external effects belong in a new outbox.
                                await handler(event, conn)
                await self.redis.xack(self.stream_name, self.consumer_group, stream_id)
                processed += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                pending = await self.redis.xpending_range(self.stream_name, self.consumer_group, min=stream_id, max=stream_id, count=1)
                deliveries = int(pending[0].get("times_delivered", 1)) if pending else 1
                if deliveries >= self.max_deliveries:
                    disposition_id = await self._persist_dead_letter(
                        stream_id=stream_id, event_id=event_id, payload=fields.get("payload", ""),
                        failure_type=type(exc).__name__, delivery_count=deliveries)
                    # The PostgreSQL ledger is canonical. Redis publication is idempotent, and
                    # source acknowledgement occurs only after both durable recording and projection.
                    await self._publish_dead_letter(disposition_id)
                    await self.redis.xack(self.stream_name, self.consumer_group, stream_id)
                    processed += 1
                    continue
                raise
        return processed
    async def _persist_dead_letter(self, *, stream_id: str, event_id: str,
                                   payload: str, failure_type: str,
                                   delivery_count: int) -> str:
        """Persist a stable DLQ disposition before acknowledging its source entry."""
        disposition_id = dead_letter_disposition_id(self.stream_name, stream_id)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        """INSERT INTO aigc_dead_letters
                           (disposition_id, source_stream, source_stream_id, event_id,
                            payload, payload_sha256, failure_type, delivery_count)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (source_stream, source_stream_id) DO NOTHING
                           RETURNING disposition_id""",
                        (disposition_id, self.stream_name, stream_id, event_id,
                         payload, sha256_text(payload), failure_type, delivery_count))
                    inserted = await cur.fetchone()
                    await cur.execute(
                        "SELECT disposition_id FROM aigc_dead_letters WHERE source_stream=%s AND source_stream_id=%s",
                        (self.stream_name, stream_id))
                    row = await cur.fetchone()
                    if not row or row["disposition_id"] != disposition_id:
                        raise OrchestrationError("dead_letter_ledger_conflict")
                    # Add the ordinary event-log record in the same transaction when the
                    # source payload names an existing task. Malformed messages remain in
                    # the dedicated ledger rather than losing their forensic evidence.
                    try:
                        parsed = json.loads(payload)
                        task_id = UUID(parsed.get("task_id"))
                    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
                        task_id = None
                    if inserted and task_id is not None:
                        await cur.execute("SELECT task_id FROM aigc_tasks WHERE task_id=%s FOR UPDATE", (str(task_id),))
                        if await cur.fetchone():
                            await cur.execute("SELECT COALESCE(MAX(sequence),0)+1 AS seq FROM aigc_events WHERE task_id=%s",
                                              (str(task_id),))
                            sequence = int((await cur.fetchone())["seq"])
                            audit_id = uuid4()
                            audit = {"event_id": str(audit_id), "task_id": str(task_id),
                                     "sequence": sequence, "event_type": "MESSAGE_DEAD_LETTERED",
                                     "disposition_id": disposition_id, "source_stream": self.stream_name,
                                     "source_stream_id": stream_id, "failure_type": failure_type,
                                     "delivery_count": delivery_count}
                            encoded = canonical_json(audit)
                            await cur.execute(
                                """INSERT INTO aigc_events(event_id,task_id,sequence,event_type,payload,payload_sha256)
                                   VALUES(%s,%s,%s,%s,%s::jsonb,%s)
                                   ON CONFLICT (task_id,sequence) DO NOTHING""",
                                (str(audit_id), str(task_id), sequence, "MESSAGE_DEAD_LETTERED",
                                 encoded, sha256_text(encoded)))
        return disposition_id

    async def _publish_pending_dead_letters(self, *, limit: int = 100) -> int:
        """Retry ledger rows whose Redis DLQ projection did not receive a receipt."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer in [1,1000]")
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT disposition_id FROM aigc_dead_letters
                       WHERE published_at IS NULL ORDER BY created_at, disposition_id LIMIT %s""",
                    (limit,))
                rows = await cur.fetchall()
        published = 0
        for row in rows:
            await self._publish_dead_letter(row["disposition_id"])
            published += 1
        return published

    async def _publish_dead_letter(self, disposition_id: str) -> None:
        """Project a ledger row to Redis exactly-once per surviving Redis keyspace."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT source_stream,source_stream_id,event_id,payload,payload_sha256,
                              failure_type,delivery_count
                       FROM aigc_dead_letters WHERE disposition_id=%s""", (disposition_id,))
                row = await cur.fetchone()
        if not row:
            raise OrchestrationError("dead_letter_ledger_record_missing")
        # Redis Lua makes the dedupe marker and XADD atomic. PostgreSQL remains the
        # authority if Redis data is restored or lost and the projection must be rebuilt.
        script = """
        local prior = redis.call('GET', KEYS[1])
        if prior then return prior end
        local entry = redis.call('XADD', KEYS[2], '*',
          'disposition_id', ARGV[1], 'source_stream', ARGV[2],
          'source_stream_id', ARGV[3], 'event_id', ARGV[4],
          'payload', ARGV[5], 'payload_sha256', ARGV[6],
          'failure_type', ARGV[7], 'delivery_count', ARGV[8],
          'disposition', 'MANUAL_REVIEW_REQUIRED')
        redis.call('SET', KEYS[1], entry)
        return entry
        """
        redis_key = "aigc:dlq-published:v1:" + sha256_text(canonical_json([self.dead_letter_stream, disposition_id]))
        await self.redis.eval(script, 2, redis_key, self.dead_letter_stream,
            disposition_id, row["source_stream"], row["source_stream_id"],
            row["event_id"] or "", row["payload"], row["payload_sha256"],
            row["failure_type"], str(row["delivery_count"]))
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE aigc_dead_letters SET published_at=COALESCE(published_at,now()) WHERE disposition_id=%s",
                        (disposition_id,))
                    if cur.rowcount != 1:
                        raise OrchestrationError("dead_letter_projection_receipt_missing")

    async def run_saga(self, contract: TaskContract, steps: list[SagaStep], *,
                       dry_run: bool | None = None, permit_ref: str | None = None) -> dict[str, Any]:
        """Run an explicitly registered saga; snapshot inputs before authorization and default to dry-run."""
        dry = self.dry_run if dry_run is None else dry_run
        started_all = time.monotonic()
        deadline = started_all + contract.timeout_seconds
        if len(steps) > self.max_hops or len(steps) > contract.max_hops:
            raise OrchestrationError("saga_hop_limit_exceeded")

        # Frozen dataclasses do not freeze nested Mapping values. Snapshot canonical
        # JSON before the first await so the verified bytes and executed payload match.
        # Bound each payload to prevent unbounded memory use at the authorization boundary.
        def snapshot_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
            if payload is None:
                return None
            if not isinstance(payload, Mapping):
                raise OrchestrationError("saga_payload_must_be_mapping")
            try:
                encoded = canonical_json(dict(payload))
                encoded_bytes = encoded.encode("utf-8")
            except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as exc:
                raise OrchestrationError("saga_payload_not_canonical_json") from exc
            if len(encoded_bytes) > 1_000_000:
                raise OrchestrationError("saga_payload_size_limit_exceeded")
            try:
                snapshot = json.loads(encoded)
            except (json.JSONDecodeError, RecursionError) as exc:
                raise OrchestrationError("saga_payload_snapshot_failed") from exc
            if not isinstance(snapshot, dict):
                raise OrchestrationError("saga_payload_must_be_object")
            return snapshot

        snapshotted_steps: list[SagaStep] = []
        for supplied in steps:
            if not isinstance(supplied, SagaStep):
                raise OrchestrationError("saga_step_type_invalid")
            snapshotted_steps.append(SagaStep(
                step_id=supplied.step_id,
                operation=supplied.operation,
                input_payload=snapshot_payload(supplied.input_payload) or {},
                compensation_operation=supplied.compensation_operation,
                compensation_payload=snapshot_payload(supplied.compensation_payload),
                irreversible=supplied.irreversible,
                side_effecting=supplied.side_effecting,
                approval_receipt_ref=supplied.approval_receipt_ref,
                idempotent=supplied.idempotent,
                compensation_idempotent=supplied.compensation_idempotent,
            ))
        steps = snapshotted_steps
        if len({step.step_id for step in steps}) != len(steps):
            raise OrchestrationError("duplicate_saga_step_id")
        if any(not step.step_id or not step.operation for step in steps):
            raise OrchestrationError("saga_step_identity_missing")
        if not dry:
            if self.permit_verifier is None or not permit_ref:
                raise OrchestrationError("authenticated_permit_verifier_and_receipt_required")
            if not contract.candidate_sha:
                raise OrchestrationError("live_mutation_requires_exact_candidate_sha")
            # Preflight every operation and scope before the first side effect.
            for planned in steps:
                if planned.operation not in self.adapters:
                    raise OrchestrationError("operation_not_allowlisted:" + planned.operation)
                if not planned.idempotent:
                    raise OrchestrationError("live_operation_must_declare_idempotency")
                if planned.irreversible and not planned.approval_receipt_ref:
                    raise OrchestrationError("irreversible_operation_requires_human_approval_receipt")
                if planned.side_effecting and not planned.irreversible:
                    if not planned.compensation_operation or not planned.compensation_idempotent:
                        raise OrchestrationError("reversible_side_effect_requires_idempotent_compensation")
                    if planned.compensation_operation not in self.adapters:
                        raise OrchestrationError("compensation_operation_not_allowlisted")
                planned_key = hashlib.sha256(f"{contract.idempotency_key}:{planned.step_id}".encode()).hexdigest()
                claims = {"task_id": str(contract.task_id), "candidate_sha": contract.candidate_sha,
                    "policy_version": contract.policy_version, "operation": planned.operation,
                    "input_digest": sha256_text(canonical_json(dict(planned.input_payload))),
                    "compensation_operation": planned.compensation_operation, "irreversible": planned.irreversible,
                    "side_effecting": planned.side_effecting, "approval_receipt_ref": planned.approval_receipt_ref}
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OrchestrationError("saga_deadline_exceeded_during_preflight")
                try:
                    async with asyncio.timeout(remaining):
                        permitted = await self.permit_verifier(permit_ref, claims, planned_key)
                except TimeoutError as exc:
                    raise OrchestrationError("saga_deadline_exceeded_during_preflight") from exc
                if not permitted:
                    raise OrchestrationError("permit_verification_denied:" + planned.step_id)
        receipts: list[StepReceipt] = []
        completed: list[SagaStep] = []
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OrchestrationError("saga_deadline_exceeded_before_concurrency_slot")
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=remaining)
        except TimeoutError as exc:
            raise OrchestrationError("saga_deadline_exceeded_waiting_for_concurrency_slot") from exc
        try:
            for index, step in enumerate(steps):
                if index >= min(self.max_hops, contract.max_hops):
                    raise OrchestrationError("saga_hop_limit_exceeded")
                if step.operation not in self.adapters:
                    raise OrchestrationError("operation_not_allowlisted:" + step.operation)
                if step.irreversible and not dry and not step.approval_receipt_ref:
                    raise OrchestrationError("irreversible_step_requires_verified_human_approval")
                if not dry and step.idempotent is not True:
                    raise OrchestrationError("live_operation_must_declare_idempotency")
                key = hashlib.sha256(f"{contract.idempotency_key}:{step.step_id}".encode()).hexdigest()
                started = time.monotonic()
                if dry:
                    result = {"mode": "DRY_RUN", "operation": step.operation, "input_digest": sha256_text(canonical_json(dict(step.input_payload))),
                              "side_effects_performed": False}
                    status = "SIMULATED"
                else:
                    try:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise OrchestrationError("saga_deadline_exceeded")
                        async def verify_permit_at_effect_boundary() -> bool:
                            if self.permit_verifier is None or not permit_ref or not contract.candidate_sha:
                                return False
                            claims = {"task_id": str(contract.task_id), "candidate_sha": contract.candidate_sha,
                                "policy_version": contract.policy_version, "operation": step.operation,
                                "input_digest": sha256_text(canonical_json(dict(step.input_payload))),
                                "compensation_operation": step.compensation_operation, "irreversible": step.irreversible,
                                "side_effecting": step.side_effecting, "approval_receipt_ref": step.approval_receipt_ref}
                            try:
                                permit_remaining = deadline - time.monotonic()
                                if permit_remaining <= 0:
                                    return False
                                async with asyncio.timeout(permit_remaining):
                                    return bool(await self.permit_verifier(permit_ref, claims, key))
                            except asyncio.CancelledError:
                                raise
                            except Exception:
                                return False
                        result = await self._invoke_with_retry(
                            step.operation, self.adapters[step.operation], step.input_payload, key,
                            timeout=min(self.operation_timeout_seconds, remaining),
                            before_attempt=verify_permit_at_effect_boundary if not dry else None)
                        status = "SUCCEEDED"
                        completed.append(step)
                    except Exception as exc:
                        compensation = await self._compensate(contract, completed, failed_step=step, failed_key=key,
                                                              permit_ref=permit_ref, deadline=deadline)
                        await self.record_event(contract.task_id, "SAGA_FAILED", {
                            "failed_step_id": step.step_id, "error_type": type(exc).__name__,
                            "compensation": compensation, "side_effects_may_have_occurred": True})
                        raise OrchestrationError("saga_step_failed; compensation_status:" + compensation["status"]) from exc
                receipt_body = {"step_id": step.step_id, "operation": step.operation, "status": status,
                                "result": result, "idempotency_key": key, "task_id": str(contract.task_id)}
                receipts.append(StepReceipt(step.step_id, status, result, key, sha256_text(canonical_json(receipt_body)),
                                            started, time.monotonic() - started))
                await self.record_event(contract.task_id, "SAGA_STEP_" + status,
                    {"step_id": step.step_id, "operation": step.operation, "idempotency_key": key,
                     "result_digest": receipts[-1].evidence_digest, "dry_run": dry})
        finally:
            self.semaphore.release()
        return {"task_id": str(contract.task_id), "status": "DRY_RUN_PLAN" if dry else "SUCCEEDED",
                "steps": [r.__dict__ for r in receipts], "elapsed_seconds": time.monotonic() - started_all,
                "side_effects_performed": bool(completed), "compensation": "NOT_REQUIRED",
                "release_authorization": False, "merge_authorization": False}

    async def _compensate(self, contract: TaskContract, completed: list[SagaStep], *,
                          failed_step: SagaStep, failed_key: str, permit_ref: str | None,
                          deadline: float) -> dict[str, Any]:
        """Reconcile and compensate only within the original task deadline."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"status": "RECONCILIATION_REQUIRED", "steps": [],
                    "reason": "task_deadline_exceeded_before_outcome_reconciliation",
                    "failed_step_id": failed_step.step_id, "release_authorization": False}
        if self.outcome_reconciler is None:
            return {"status": "RECONCILIATION_REQUIRED", "steps": [],
                    "reason": "no trusted read-after-write outcome reconciler; compensation was not attempted",
                    "failed_step_id": failed_step.step_id, "release_authorization": False}
        try:
            async with asyncio.timeout(remaining):
                outcome = await self.outcome_reconciler(failed_step.operation, failed_step.input_payload, failed_key)
        except Exception as exc:
            return {"status": "RECONCILIATION_REQUIRED", "steps": [],
                    "reason": "outcome_reconciliation_failed:" + type(exc).__name__,
                    "failed_step_id": failed_step.step_id, "release_authorization": False}
        if outcome == "UNKNOWN":
            return {"status": "RECONCILIATION_REQUIRED", "steps": [],
                    "reason": "side_effect_outcome_unknown; fail_stopped_without_compensation",
                    "failed_step_id": failed_step.step_id, "release_authorization": False}
        if outcome == "APPLIED":
            completed = [*completed, failed_step]
        elif outcome != "NOT_APPLIED":
            return {"status": "RECONCILIATION_REQUIRED", "steps": [],
                    "reason": "invalid_reconciliation_result", "release_authorization": False}
        results: list[dict[str, Any]] = []
        for step in reversed(completed):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                results.append({"step_id": step.step_id, "status": "MANUAL_RECONCILIATION_REQUIRED",
                                "reason": "task_deadline_exceeded_before_compensation"})
                break
            operation = step.compensation_operation
            if not operation:
                results.append({"step_id": step.step_id, "status": "MANUAL_RECONCILIATION_REQUIRED",
                                "reason": "compensation_not_defined"})
                continue
            if operation not in self.adapters:
                results.append({"step_id": step.step_id, "status": "BLOCK", "reason": "compensation_not_allowlisted"})
                continue
            if step.compensation_idempotent is not True:
                results.append({"step_id": step.step_id, "status": "BLOCK", "reason": "compensation_idempotency_not_declared"})
                continue
            if not permit_ref or self.permit_verifier is None:
                results.append({"step_id": step.step_id, "status": "BLOCK", "reason": "compensation_permit_missing"})
                continue
            key = hashlib.sha256(f"{contract.idempotency_key}:compensate:{step.step_id}".encode()).hexdigest()
            compensation_payload = step.compensation_payload or {}
            compensation_claims = {
                "task_id": str(contract.task_id),
                "candidate_sha": contract.candidate_sha,
                "operation": operation,
                "policy_version": contract.policy_version,
                "compensation_for": step.step_id,
                "original_operation": step.operation,
                "original_input_digest": sha256_text(canonical_json(dict(step.input_payload))),
                "input_digest": sha256_text(canonical_json(dict(compensation_payload))),
            }
            async def verify_compensation_permit_at_effect_boundary() -> bool:
                try:
                    permit_remaining = deadline - time.monotonic()
                    if permit_remaining <= 0:
                        return False
                    async with asyncio.timeout(permit_remaining):
                        return bool(await self.permit_verifier(permit_ref, compensation_claims, key))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    return False
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    results.append({"step_id": step.step_id, "status": "MANUAL_RECONCILIATION_REQUIRED",
                                    "reason": "task_deadline_exceeded_before_compensation"})
                    break
                result = await self._invoke_with_retry(
                    operation, self.adapters[operation], compensation_payload, key,
                    timeout=min(self.operation_timeout_seconds, remaining),
                    before_attempt=verify_compensation_permit_at_effect_boundary)
                results.append({"step_id": step.step_id, "status": "COMPENSATION_REQUEST_SUCCEEDED",
                                "result": dict(result)})
            except Exception as exc:
                results.append({"step_id": step.step_id, "status": "MANUAL_RECONCILIATION_REQUIRED",
                                "error_type": type(exc).__name__})
        clean = bool(results) and all(item["status"] == "COMPENSATION_REQUEST_SUCCEEDED" for item in results)
        return {"status": "COMPENSATION_REQUESTS_SUCCEEDED" if clean else "INCOMPLETE",
                "steps": results, "release_authorization": False}
    async def _invoke_with_retry(self, operation: str, adapter: ActionAdapter,
                                 payload: Mapping[str, Any], key: str,
                                 *, timeout: float,
                                 before_attempt: Callable[[], Awaitable[bool]] | None = None) -> Mapping[str, Any]:
        """Retry only after a trusted read-after-write reconciler proves no effect occurred.

        A timeout or transport exception is ambiguous: the remote side may have committed
        the operation before the response was lost. Idempotency keys are necessary but are
        not a substitute for reconciling the target system's actual outcome.
        """
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 300:
            raise ValueError("timeout must be finite and in (0,300]")
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OrchestrationError("operation_deadline_exceeded") from last_error
            if before_attempt is not None:
                try:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise OrchestrationError("operation_deadline_exceeded_before_authorization")
                    async with asyncio.timeout(remaining):
                        permitted = await before_attempt()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    raise OrchestrationError("point_of_effect_authorization_check_failed:" + type(exc).__name__) from exc
                if not permitted:
                    raise OrchestrationError("point_of_effect_authorization_denied")
            try:
                async with asyncio.timeout(remaining):
                    result = await adapter(payload, idempotency_key=key)
                if not isinstance(result, Mapping):
                    raise OrchestrationError("adapter_result_must_be_mapping")
                return dict(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # The remote side may have committed before the response timed out.
                    # Stop retrying and explicitly surface the unresolved outcome.
                    raise OrchestrationError(
                        "operation_deadline_exceeded_outcome_unreconciled"
                    ) from exc
                if self.outcome_reconciler is None:
                    raise OrchestrationError(
                        "retry_prohibited_without_trusted_outcome_reconciliation:" + type(exc).__name__
                    ) from exc
                try:
                    async with asyncio.timeout(remaining):
                        outcome = await self.outcome_reconciler(operation, payload, key)
                except asyncio.CancelledError:
                    raise
                except Exception as reconcile_exc:
                    raise OrchestrationError(
                        "retry_prohibited_outcome_reconciliation_failed:" + type(reconcile_exc).__name__
                    ) from reconcile_exc
                if outcome != "NOT_APPLIED":
                    raise OrchestrationError(
                        "retry_prohibited_side_effect_outcome:" + str(outcome)
                    ) from exc
                if attempt + 1 >= self.max_attempts:
                    break
                ceiling = min(self.max_retry_seconds, self.base_retry_seconds * (2 ** attempt))
                delay = random.uniform(0, ceiling)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OrchestrationError("operation_deadline_exceeded") from exc
                await asyncio.sleep(min(delay, remaining))
        raise OrchestrationError(
            "adapter_failed_after_reconciled_not_applied_retries:" + type(last_error).__name__
        ) from last_error
