"""PostgreSQL-owned task lifecycle and transactional outbox.

This module is persistence infrastructure only. It does not start workers, grant
actuation authority, or claim that the web API is already wired to this path.
Redis remains a delivery mechanism; PostgreSQL owns task status and dispatch intent.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.core.contracts import TaskContract


class TaskLifecycleError(RuntimeError):
    """Base error for durable task lifecycle operations."""


class TaskIdempotencyConflict(TaskLifecycleError):
    """An owner-scoped idempotency key was reused for different content."""


class TaskNotFound(TaskLifecycleError):
    """The task or outbox receipt does not exist in the expected state."""


class TaskStoreUnavailable(TaskLifecycleError):
    """The authoritative PostgreSQL task store could not complete an operation."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _task_public(row: dict[str, Any], *, replayed: bool | None = None) -> dict[str, Any]:
    result = {
        "task_id": str(row["task_id"]),
        "owner_id": str(row["owner_id"]),
        "status": str(row["status"]),
        "attempt": int(row["attempt"]),
        "version": int(row["version"]),
        "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
        "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else row["updated_at"],
        "result": row.get("result_json"),
        "artifact_sha256": row.get("artifact_sha256"),
        "evidence": row.get("evidence_json"),
    }
    if replayed is not None:
        result["replayed"] = replayed
    return result


class PostgresTaskLifecycleStore:
    """Small PostgreSQL repository; migrations are applied by a separate controlled step."""

    def __init__(self, dsn: str, *, sslmode: str = "verify-full", sslrootcert: str | None = None):
        if not isinstance(dsn, str) or not dsn.strip():
            raise TaskStoreUnavailable("Task database configuration is missing")
        options: dict[str, Any] = {"sslmode": sslmode, "row_factory": dict_row}
        if sslrootcert:
            options["sslrootcert"] = sslrootcert
        self._pool = ConnectionPool(
            conninfo=dsn,
            kwargs=options,
            min_size=1,
            max_size=4,
            timeout=5,
            open=True,
        )

    def close(self) -> None:
        self._pool.close()

    def healthcheck(self) -> dict[str, Any]:
        try:
            with self._pool.connection(timeout=5) as conn:
                row = conn.execute(
                    "SELECT to_regclass('public.aigc_tasks') AS tasks, "
                    "to_regclass('public.aigc_task_outbox') AS outbox"
                ).fetchone()
                ready = bool(row and row["tasks"] and row["outbox"])
                return {"ok": ready, "durable": True, "backend": "postgresql"}
        except Exception as exc:
            raise TaskStoreUnavailable("Task store health check failed") from exc

    def submit_task(self, *, owner_id: str, idempotency_key: str, task: TaskContract) -> dict[str, Any]:
        if not owner_id or len(owner_id) > 256:
            raise ValueError("owner_id must contain 1..256 characters")
        if not idempotency_key or len(idempotency_key) < 8 or len(idempotency_key) > 256:
            raise ValueError("idempotency_key must contain 8..256 characters")
        if task.idempotency_key != idempotency_key:
            raise ValueError("TaskContract idempotency key must match the submission key")

        key_hash = _sha256(idempotency_key.encode("utf-8"))
        contract_json = task.model_dump(mode="json")
        contract_text = _json(contract_json)
        request_hash = _sha256(_json({
            "schema_version": task.schema_version,
            "task_type": task.task_type,
            "payload": contract_json["payload"],
            "deadline_at": task.deadline_at.isoformat() if task.deadline_at else None,
            "timeout_seconds": task.timeout_seconds,
            "hop_count": task.hop_count,
            "max_hops": task.max_hops,
        }).encode("utf-8"))
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    prior = conn.execute(
                        """SELECT * FROM aigc_tasks
                           WHERE owner_id=%s AND idempotency_key_sha256=%s
                           FOR UPDATE""",
                        (owner_id, key_hash),
                    ).fetchone()
                    if prior:
                        if prior["request_sha256"] != request_hash:
                            raise TaskIdempotencyConflict("Idempotency key is bound to different task content")
                        return _task_public(prior, replayed=True)

                    task_id = task.task_id
                    row = conn.execute(
                        """INSERT INTO aigc_tasks
                           (task_id, owner_id, idempotency_key_sha256, request_sha256,
                            contract_json, status, attempt, version)
                           VALUES (%s,%s,%s,%s,%s::jsonb,'queued',0,1)
                           RETURNING *""",
                        (task_id, owner_id, key_hash, request_hash, contract_text),
                    ).fetchone()
                    conn.execute(
                        """INSERT INTO aigc_task_outbox (task_id, payload_json, status)
                           VALUES (%s,%s::jsonb,'pending')""",
                        (task_id, contract_text),
                    )
                    return _task_public(row, replayed=False)
        except (TaskIdempotencyConflict, ValueError):
            raise
        except UniqueViolation as exc:
            # A concurrent request may have won the same owner-scoped idempotency key.
            # Re-read after the failed transaction so identical submissions replay safely.
            try:
                with self._pool.connection(timeout=5) as conn:
                    prior = conn.execute(
                        """SELECT * FROM aigc_tasks
                           WHERE owner_id=%s AND idempotency_key_sha256=%s""",
                        (owner_id, key_hash),
                    ).fetchone()
                if prior:
                    if prior["request_sha256"] != request_hash:
                        raise TaskIdempotencyConflict(
                            "Idempotency key is bound to different task content"
                        ) from exc
                    return _task_public(prior, replayed=True)
                raise TaskStoreUnavailable("Task uniqueness conflict could not be reconciled") from exc
            except TaskIdempotencyConflict:
                raise
            except TaskStoreUnavailable:
                raise
            except Exception as read_exc:
                raise TaskStoreUnavailable("Task uniqueness conflict could not be reconciled") from read_exc
        except Exception as exc:
            raise TaskStoreUnavailable("Durable task submission failed") from exc

    def get_task(self, *, owner_id: str, task_id: str) -> dict[str, Any] | None:
        try:
            with self._pool.connection(timeout=5) as conn:
                row = conn.execute(
                    "SELECT * FROM aigc_tasks WHERE owner_id=%s AND task_id=%s",
                    (owner_id, task_id),
                ).fetchone()
                return _task_public(row) if row else None
        except Exception as exc:
            raise TaskStoreUnavailable("Durable task lookup failed") from exc

    def claim_outbox(self, *, dispatcher_id: str, lease_seconds: int = 30) -> dict[str, Any] | None:
        if not dispatcher_id or len(dispatcher_id) > 128:
            raise ValueError("dispatcher_id must contain 1..128 characters")
        lease_seconds = max(5, min(int(lease_seconds), 300))
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    row = conn.execute(
                        """WITH candidate AS (
                             SELECT outbox_id FROM aigc_task_outbox
                             WHERE status='pending'
                                OR (status='publishing' AND lease_until < now())
                             ORDER BY outbox_id
                             FOR UPDATE SKIP LOCKED
                             LIMIT 1
                           )
                           UPDATE aigc_task_outbox AS o
                           SET status='publishing', dispatcher_id=%s,
                               lease_until=now() + (%s * interval '1 second'),
                               attempts=attempts+1, updated_at=now()
                           FROM candidate c
                           WHERE o.outbox_id=c.outbox_id
                           RETURNING o.outbox_id,o.task_id,o.payload_json,o.attempts,o.dispatcher_id,o.lease_until""",
                        (dispatcher_id, lease_seconds),
                    ).fetchone()
                    return row
        except Exception as exc:
            raise TaskStoreUnavailable("Outbox claim failed") from exc

    def mark_dispatched(self, *, outbox_id: int, dispatcher_id: str) -> None:
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    row = conn.execute(
                        """UPDATE aigc_task_outbox
                           SET status='dispatched', dispatcher_id=NULL, lease_until=NULL,
                               updated_at=now(), last_error=NULL
                           WHERE outbox_id=%s AND status='publishing' AND dispatcher_id=%s
                           RETURNING task_id""",
                        (outbox_id, dispatcher_id),
                    ).fetchone()
                    if not row:
                        raise TaskNotFound("Outbox lease is missing, expired, or owned by another dispatcher")
        except TaskNotFound:
            raise
        except Exception as exc:
            raise TaskStoreUnavailable("Outbox dispatch receipt could not be persisted") from exc

    def release_outbox(self, *, outbox_id: int, dispatcher_id: str, error_class: str) -> None:
        """Return a failed publish to pending; persist only a bounded error class, never payloads."""
        safe_error = "".join(ch for ch in error_class if ch.isalnum() or ch in "._-")[:80] or "publish_failed"
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    cursor = conn.execute(
                        """UPDATE aigc_task_outbox
                           SET status='pending', dispatcher_id=NULL, lease_until=NULL,
                               last_error=%s, updated_at=now()
                           WHERE outbox_id=%s AND status='publishing' AND dispatcher_id=%s""",
                        (safe_error, outbox_id, dispatcher_id),
                    )
                    if cursor.rowcount != 1:
                        raise TaskNotFound("Outbox lease is missing or owned by another dispatcher")
        except TaskNotFound:
            raise
        except Exception as exc:
            raise TaskStoreUnavailable("Outbox retry state could not be persisted") from exc

    def mark_running(self, *, owner_id: str, task_id: str) -> dict[str, Any]:
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    row = conn.execute(
                        """UPDATE aigc_tasks
                           SET status='running',attempt=attempt+1,version=version+1,
                               lease_until=now()+interval '45 minutes',updated_at=now()
                           WHERE owner_id=%s AND task_id=%s AND status='queued'
                           RETURNING *""",
                        (owner_id, task_id),
                    ).fetchone()
                    if not row:
                        raise TaskNotFound("Task is missing or cannot transition from its current state")
                    return _task_public(row)
        except TaskNotFound:
            raise
        except Exception as exc:
            raise TaskStoreUnavailable("Task start transition failed") from exc

    def complete_task(
        self, *, owner_id: str, task_id: str, result: dict[str, Any], artifact_bytes: bytes
    ) -> dict[str, Any]:
        if not isinstance(artifact_bytes, bytes):
            raise ValueError("artifact_bytes must be bytes")
        if len(artifact_bytes) > 1_000_000:
            raise ValueError("artifact_bytes exceeds the 1 MB task artifact limit")
        artifact_digest = _sha256(artifact_bytes)
        safe_result = json.loads(_json(result))
        evidence = {
            "task_id": task_id,
            "owner_id": owner_id,
            "artifact_sha256": artifact_digest,
            "artifact_size_bytes": len(artifact_bytes),
            "verified": _sha256(artifact_bytes) == artifact_digest,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    row = conn.execute(
                        """UPDATE aigc_tasks
                           SET status='succeeded',result_json=%s::jsonb,artifact_bytes=%s,
                               artifact_sha256=%s,evidence_json=%s::jsonb,
                               lease_until=NULL,version=version+1,updated_at=now()
                           WHERE owner_id=%s AND task_id=%s AND status='running'
                           RETURNING *""",
                        (_json(safe_result), artifact_bytes, artifact_digest, _json(evidence), owner_id, task_id),
                    ).fetchone()
                    if not row:
                        raise TaskNotFound("Task is missing or cannot transition to succeeded")
                    # Verify persisted bytes before the transaction commits terminal success.
                    persisted_digest = _sha256(bytes(row["artifact_bytes"]))
                    if persisted_digest != row["artifact_sha256"] or persisted_digest != evidence["artifact_sha256"]:
                        raise TaskStoreUnavailable("Persisted artifact digest verification failed")
                    return _task_public(row)
        except TaskNotFound:
            raise
        except TaskStoreUnavailable:
            raise
        except Exception as exc:
            raise TaskStoreUnavailable("Task completion and evidence persistence failed") from exc

    def fail_task(self, *, owner_id: str, task_id: str, failure_class: str) -> dict[str, Any]:
        safe_class = "".join(ch for ch in failure_class if ch.isalnum() or ch in "._-")[:80] or "worker_failed"
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    row = conn.execute(
                        """UPDATE aigc_tasks
                           SET status='failed',failure_class=%s,lease_until=NULL,
                               version=version+1,updated_at=now()
                           WHERE owner_id=%s AND task_id=%s AND status IN ('queued','running')
                           RETURNING *""",
                        (safe_class, owner_id, task_id),
                    ).fetchone()
                    if not row:
                        raise TaskNotFound("Task is missing or cannot transition to failed")
                    return _task_public(row)
        except TaskNotFound:
            raise
        except Exception as exc:
            raise TaskStoreUnavailable("Task failure transition failed") from exc
