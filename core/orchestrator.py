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
        if operation_timeout_seconds <= 0 or operation_timeout_seconds > 300:
            raise ValueError("operation_timeout_seconds must be in (0, 300]")
        if max_attempts < 1 or max_attempts > 8:
            raise ValueError("max_attempts must be in [1, 8]")
        if pool_min_size < 1 or pool_max_size < pool_min_size:
            raise ValueError("invalid database pool bounds")
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
                await cur.execute("SELECT to_regclass(%s) AS table_name", ("public.aigc_events",))
                table = await cur.fetchone()
                if not table or not table["table_name"]:
                    raise OrchestrationError("required_runtime_schema_missing")
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

    async def consume_once(self, handler: Callable[[Mapping[str, Any]], Awaitable[None]], *, block_ms: int = 1000) -> int:
        """Process pending retries before new entries; poison messages are dead-lettered at a fixed ceiling."""
        if block_ms < 1 or block_ms > 30_000:
            raise ValueError("block_ms must be in [1,30000]")
        consumer = "aigc-worker-" + str(id(self))
        entries: list[tuple[str, Mapping[str, str]]] = []
        claimed = await self.redis.xautoclaim(self.stream_name, self.consumer_group, consumer,
                                               min_idle_time=self.pending_idle_ms, start_id="0-0", count=16)
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
                hop_count = event.get("hop_count", 0)
                if not isinstance(hop_count, int) or isinstance(hop_count, bool) or hop_count > self.max_hops:
                    raise OrchestrationError("message_hop_limit_exceeded")
                async with self.pool.connection() as conn:
                    async with conn.transaction():
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "INSERT INTO aigc_consumed_events(consumer_name,event_id) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING event_id",
                                (self.consumer_group, str(parsed_id)))
                            claimed_event = await cur.fetchone()
                            if claimed_event:
                                await handler(event)
                await self.redis.xack(self.stream_name, self.consumer_group, stream_id)
                processed += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                pending = await self.redis.xpending_range(self.stream_name, self.consumer_group, min=stream_id, max=stream_id, count=1)
                deliveries = int(pending[0].get("times_delivered", 1)) if pending else 1
                if deliveries >= self.max_deliveries:
                    await self.redis.xadd(self.dead_letter_stream, {
                        "source_stream": self.stream_name, "source_stream_id": stream_id,
                        "event_id": event_id, "payload": fields.get("payload", ""),
                        "failure_type": type(exc).__name__, "delivery_count": str(deliveries),
                        "disposition": "MANUAL_REVIEW_REQUIRED"})
                    await self.redis.xack(self.stream_name, self.consumer_group, stream_id)
                    try:
                        task_id = UUID(json.loads(fields["payload"]).get("task_id"))
                        await self.record_event(task_id, "MESSAGE_DEAD_LETTERED", {
                            "event_id": event_id, "source_stream_id": stream_id,
                            "failure_type": type(exc).__name__, "delivery_count": deliveries,
                            "dead_letter_stream": self.dead_letter_stream})
                    except Exception:
                        # The DLQ record is durable in Redis; an audit-write failure is separately observable.
                        pass
                    processed += 1
                    continue
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
                planned_key = hashlib.sha256(f"{contract.idempotency_key}:{planned.step_id}".encode()).hexdigest()
                claims = {"task_id": str(contract.task_id), "candidate_sha": contract.candidate_sha,
                    "policy_version": contract.policy_version, "operation": planned.operation,
                    "input_digest": sha256_text(canonical_json(dict(planned.input_payload))),
                    "compensation_operation": planned.compensation_operation, "irreversible": planned.irreversible, "approval_receipt_ref": planned.approval_receipt_ref}
                if not await self.permit_verifier(permit_ref, claims, planned_key):
                    raise OrchestrationError("permit_verification_denied:" + planned.step_id)
        receipts: list[StepReceipt] = []
        completed: list[SagaStep] = []
        started_all = time.monotonic()
        async with self.semaphore:
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
                        result = await self._invoke_with_retry(self.adapters[step.operation], step.input_payload, key,
                                                               timeout=min(self.operation_timeout_seconds, contract.timeout_seconds))
                        status = "SUCCEEDED"
                        completed.append(step)
                    except Exception as exc:
                        compensation = await self._compensate(contract, completed, failed_step=step, failed_key=key, permit_ref=permit_ref)
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
        return {"task_id": str(contract.task_id), "status": "DRY_RUN_PLAN" if dry else "SUCCEEDED",
                "steps": [r.__dict__ for r in receipts], "elapsed_seconds": time.monotonic() - started_all,
                "side_effects_performed": bool(completed), "compensation": "NOT_REQUIRED",
                "release_authorization": False, "merge_authorization": False}

    async def _compensate(self, contract: TaskContract, completed: list[SagaStep], *,
                          failed_step: SagaStep, failed_key: str, permit_ref: str | None) -> dict[str, Any]:
        """Reconcile the failed action first; only then attempt reverse-order compensation."""
        if self.outcome_reconciler is None:
            return {"status": "RECONCILIATION_REQUIRED", "steps": [],
                    "reason": "no trusted read-after-write outcome reconciler; compensation was not attempted",
                    "failed_step_id": failed_step.step_id, "release_authorization": False}
        try:
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
            permitted = await self.permit_verifier(permit_ref, {"task_id": str(contract.task_id), "candidate_sha": contract.candidate_sha,
                "operation": operation, "policy_version": contract.policy_version,
                "compensation_for": step.step_id}, key)
            if not permitted:
                results.append({"step_id": step.step_id, "status": "BLOCK", "reason": "compensation_permit_denied"})
                continue
            try:
                result = await self._invoke_with_retry(self.adapters[operation], step.compensation_payload or {},
                    key, timeout=min(self.operation_timeout_seconds, contract.timeout_seconds))
                results.append({"step_id": step.step_id, "status": "COMPENSATION_REQUEST_SUCCEEDED",
                                "result": dict(result)})
            except Exception as exc:
                results.append({"step_id": step.step_id, "status": "MANUAL_RECONCILIATION_REQUIRED",
                                "error_type": type(exc).__name__})
        clean = bool(results) and all(item["status"] == "COMPENSATION_REQUEST_SUCCEEDED" for item in results)
        return {"status": "COMPENSATION_REQUESTS_SUCCEEDED" if clean else "INCOMPLETE",
                "steps": results, "release_authorization": False}
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
