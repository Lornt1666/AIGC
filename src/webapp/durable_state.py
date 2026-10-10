from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
import re
import threading
import time
from typing import Any, Iterator


class CommandCenterStateStoreError(RuntimeError):
    """Base error for fail-closed command-center state operations."""


class StateStoreNotConfiguredError(CommandCenterStateStoreError):
    """Production persistence is not configured."""


class StateStoreNotReadyError(CommandCenterStateStoreError):
    """Required durable schema is not applied."""


class StateStoreUnavailableError(CommandCenterStateStoreError):
    """Durable state could not be safely read or committed."""


class RunBusyError(CommandCenterStateStoreError):
    """Configured active-run capacity has been reached."""


class RunStateError(CommandCenterStateStoreError):
    """A run transition is invalid."""


class IdempotencyConflictError(CommandCenterStateStoreError):
    """An idempotency key was reused for a different request."""


class ReviewDecisionConflictError(CommandCenterStateStoreError):
    """A review is claimed, already decided, or requires reconciliation."""


@dataclass(frozen=True)
class RunAdmission:
    run: dict[str, Any]
    created: bool
    replayed: bool


_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{16,200}$")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_RUN_STATES = {"queued", "running", "completed", "failed", "timed_out", "unknown"}
_REVIEW_STATES = {"accepted", "denied", "revision_requested", "unknown"}
_ADVISORY_LOCK_ID = 1107400386


def validate_idempotency_key(value: str) -> str:
    key = (value or "").strip()
    if not _KEY_RE.fullmatch(key):
        raise ValueError("Idempotency-Key must be 16-200 safe ASCII characters")
    return key


def hash_idempotency_key(value: str) -> str:
    return hashlib.sha256(validate_idempotency_key(value).encode("utf-8")).hexdigest()


def hash_request(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_run(run: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in run.items() if not key.startswith("_")}


class InMemoryCommandCenterStore:
    """Development/test adapter. It is explicitly not durable."""

    durable = False
    backend = "memory"

    def __init__(self, *, max_concurrent_runs: int = 1) -> None:
        self.max_concurrent_runs = max(1, int(max_concurrent_runs))
        self._lock = threading.RLock()
        self._runs: dict[str, dict[str, Any]] = {}
        self._run_keys: dict[str, tuple[str, str]] = {}
        self._reviews: dict[str, dict[str, Any]] = {}
        self._review_keys: dict[str, str] = {}

    def _recover(self) -> None:
        now = time.time()
        for run in self._runs.values():
            if run["status"] in {"queued", "running"} and run["_lease"] <= now:
                run.update(status="unknown", complete=True, current="", _lease=0, updated_at=_now())
        for review in self._reviews.values():
            if review["state"] == "processing" and review["_lease"] <= now:
                review.update(
                    state="unknown",
                    outcome={"ok": False, "decision_state": "unknown",
                             "detail": "Decision outcome may be unknown; reconcile before retrying."},
                    _lease=0,
                    updated_at=_now(),
                )

    def create_run(self, *, run_id: str, idempotency_key: str, request_sha256: str,
                   max_concurrent: int, lease_seconds: int) -> RunAdmission:
        key_hash = hash_idempotency_key(idempotency_key)
        if not _SHA_RE.fullmatch(request_sha256):
            raise ValueError("request_sha256 must be a lowercase SHA-256 digest")
        with self._lock:
            self._recover()
            prior = self._run_keys.get(key_hash)
            if prior:
                prior_id, prior_hash = prior
                if prior_hash != request_sha256:
                    raise IdempotencyConflictError("Idempotency-Key conflicts with a different run request")
                return RunAdmission(_public_run(deepcopy(self._runs[prior_id])), False, True)
            active = sum(r["status"] in {"queued", "running"} for r in self._runs.values())
            if active >= max(1, int(max_concurrent)):
                raise RunBusyError("A governed run is already active; retry after it finishes")
            now = time.time()
            run = {"run_id": run_id, "status": "queued", "steps": [], "current": "",
                   "complete": False, "created_at": _now(), "updated_at": _now(),
                   "_lease": now + max(5, lease_seconds)}
            self._runs[run_id] = run
            self._run_keys[key_hash] = (run_id, request_sha256)
            return RunAdmission(_public_run(deepcopy(run)), True, False)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._recover()
            run = self._runs.get(run_id)
            return _public_run(deepcopy(run)) if run else None

    def _active(self, run_id: str) -> dict[str, Any]:
        self._recover()
        run = self._runs.get(run_id)
        if not run or run["status"] not in {"queued", "running"}:
            raise RunStateError("Run is unknown, interrupted, or no longer active")
        return run

    def mark_run_running(self, run_id: str, *, lease_seconds: int) -> None:
        with self._lock:
            run = self._active(run_id)
            run.update(status="running", updated_at=_now(), _lease=time.time() + max(5, lease_seconds))

    def set_current_step(self, run_id: str, step: str, *, lease_seconds: int) -> None:
        with self._lock:
            run = self._active(run_id)
            run.update(current=step, updated_at=_now(), _lease=time.time() + max(5, lease_seconds))

    def append_step(self, run_id: str, step: dict[str, Any], *, lease_seconds: int) -> None:
        with self._lock:
            run = self._active(run_id)
            run["steps"].append(deepcopy(step))
            run.update(updated_at=_now(), _lease=time.time() + max(5, lease_seconds))

    def finish_run(self, run_id: str, *, status: str) -> None:
        if status not in _RUN_STATES - {"queued", "running"}:
            raise ValueError("Invalid terminal run state")
        with self._lock:
            run = self._active(run_id)
            run.update(status=status, complete=True, current="", updated_at=_now(), _lease=0)

    def get_review_replay(self, *, action_id: str, idempotency_key: str,
                          request_sha256: str) -> dict[str, Any] | None:
        key_hash = hash_idempotency_key(idempotency_key)
        with self._lock:
            self._recover()
            action = self._review_keys.get(key_hash)
            if action is None:
                return None
            record = self._reviews[action]
            if action != action_id or record["request_sha256"] != request_sha256:
                raise IdempotencyConflictError("Idempotency-Key conflicts with a different review request")
            if record["state"] == "processing":
                raise ReviewDecisionConflictError("Review decision is already processing")
            return deepcopy(record["outcome"])

    def claim_review(self, *, action_id: str, decision: str, idempotency_key: str,
                     request_sha256: str, claim_token: str, lease_seconds: int) -> dict[str, Any] | None:
        key_hash = hash_idempotency_key(idempotency_key)
        if decision not in {"accept", "deny", "revise"} or not _SHA_RE.fullmatch(request_sha256):
            raise ValueError("Invalid review decision or request digest")
        with self._lock:
            self._recover()
            prior_action = self._review_keys.get(key_hash)
            if prior_action is not None:
                prior = self._reviews[prior_action]
                if prior_action != action_id or prior["request_sha256"] != request_sha256:
                    raise IdempotencyConflictError("Idempotency-Key conflicts with a different review request")
                if prior["state"] == "processing":
                    raise ReviewDecisionConflictError("Review decision is already processing")
                return deepcopy(prior["outcome"])
            if action_id in self._reviews:
                raise ReviewDecisionConflictError("Review action was already claimed or decided; reconcile before retrying")
            self._reviews[action_id] = {
                "action_id": action_id, "decision": decision, "state": "processing",
                "request_sha256": request_sha256, "idempotency_key_sha256": key_hash,
                "claim_token_sha256": _sha256(claim_token), "outcome": None,
                "_lease": time.time() + max(5, lease_seconds), "updated_at": _now(),
            }
            self._review_keys[key_hash] = action_id
            return None

    def finish_review(self, *, action_id: str, claim_token: str, state: str,
                      outcome: dict[str, Any]) -> None:
        if state not in _REVIEW_STATES:
            raise ValueError("Invalid review decision state")
        with self._lock:
            self._recover()
            record = self._reviews.get(action_id)
            if (not record or record["state"] != "processing"
                    or record["claim_token_sha256"] != _sha256(claim_token)):
                raise ReviewDecisionConflictError("Review claim was lost or requires reconciliation")
            record.update(state=state, outcome=deepcopy(outcome), _lease=0, updated_at=_now())

    def health(self) -> dict[str, Any]:
        return {"ok": True, "durable": False, "backend": self.backend, "schema_version": None}

    def close(self) -> None:
        return None


class PostgresCommandCenterStore:
    """PostgreSQL-backed shared run admission, restart recovery, and review claims."""

    durable = True
    backend = "postgresql"
    schema_version = 3

    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise StateStoreNotConfiguredError("AIGC_COMMAND_CENTER_STATE_DSN is required")
        try:
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
            from psycopg_pool import ConnectionPool
            self._Jsonb = Jsonb
            self._pool = ConnectionPool(
                conninfo=dsn, min_size=1, max_size=8, timeout=5,
                kwargs={"row_factory": dict_row}, open=True,
            )
        except Exception as exc:
            raise StateStoreUnavailableError("Could not initialize durable command-center storage") from exc

    @contextmanager
    def _transaction(self) -> Iterator[Any]:
        try:
            with self._pool.connection() as conn:
                with conn.transaction():
                    try:
                        row = conn.execute(
                            "SELECT migration_name FROM aigc_schema_migrations WHERE version = %s",
                            (self.schema_version,),
                        ).fetchone()
                    except Exception as exc:
                        raise StateStoreNotReadyError("Command-center migration 003 is not applied") from exc
                    if not row or row["migration_name"] != "003_command_center_state":
                        raise StateStoreNotReadyError("Command-center migration 003 is not applied")
                    yield conn
        except CommandCenterStateStoreError:
            raise
        except Exception as exc:
            raise StateStoreUnavailableError("Durable command-center state is unavailable") from exc

    def _recover_runs(self, conn: Any) -> None:
        conn.execute("""
            UPDATE command_center_runs
               SET status='unknown', complete=TRUE, current_step='',
                   admission_slot=NULL, lease_expires_at=NULL, updated_at=CURRENT_TIMESTAMP
             WHERE status IN ('queued','running') AND lease_expires_at < CURRENT_TIMESTAMP
        """)

    def _recover_reviews(self, conn: Any) -> None:
        conn.execute("""
            UPDATE command_center_review_decisions
               SET state='unknown',
                   outcome=COALESCE(outcome, %s),
                   lease_expires_at=NULL, updated_at=CURRENT_TIMESTAMP
             WHERE state='processing' AND lease_expires_at < CURRENT_TIMESTAMP
        """, (self._Jsonb({"ok": False, "decision_state": "unknown",
                           "detail": "Decision outcome may be unknown; reconcile before retrying."}),))

    @staticmethod
    def _run_dict(row: dict[str, Any]) -> dict[str, Any]:
        return {"run_id": row["run_id"], "status": row["status"], "steps": row["steps"] or [],
                "current": row["current_step"] or "", "complete": bool(row["complete"]),
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def create_run(self, *, run_id: str, idempotency_key: str, request_sha256: str,
                   max_concurrent: int, lease_seconds: int) -> RunAdmission:
        key_hash = hash_idempotency_key(idempotency_key)
        if not _SHA_RE.fullmatch(request_sha256):
            raise ValueError("request_sha256 must be a lowercase SHA-256 digest")
        with self._transaction() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (_ADVISORY_LOCK_ID,))
            self._recover_runs(conn)
            prior = conn.execute(
                "SELECT * FROM command_center_runs WHERE idempotency_key_sha256=%s", (key_hash,)
            ).fetchone()
            if prior:
                if prior["request_sha256"] != request_sha256:
                    raise IdempotencyConflictError("Idempotency-Key conflicts with a different run request")
                return RunAdmission(self._run_dict(prior), False, True)
            capacity = max(1, min(64, int(max_concurrent)))
            active = conn.execute(
                "SELECT count(*) AS count FROM command_center_runs WHERE status IN ('queued','running')"
            ).fetchone()["count"]
            if active >= capacity:
                raise RunBusyError("A governed run is already active; retry after it finishes")
            slot = conn.execute("""
                SELECT candidate.slot FROM generate_series(1, %s) AS candidate(slot)
                 WHERE NOT EXISTS (
                    SELECT 1 FROM command_center_runs r
                     WHERE r.admission_slot=candidate.slot AND r.status IN ('queued','running')
                 )
                 ORDER BY candidate.slot LIMIT 1
            """, (capacity,)).fetchone()
            if not slot:
                raise RunBusyError("A governed run is already active; retry after it finishes")
            row = conn.execute("""
                INSERT INTO command_center_runs
                    (run_id,idempotency_key_sha256,request_sha256,status,steps,current_step,
                     complete,admission_slot,lease_expires_at)
                VALUES (%s,%s,%s,'queued','[]'::jsonb,'',FALSE,%s,
                        CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'))
                RETURNING *
            """, (run_id,key_hash,request_sha256,slot["slot"],max(5,lease_seconds))).fetchone()
            return RunAdmission(self._run_dict(row), True, False)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._transaction() as conn:
            self._recover_runs(conn)
            row = conn.execute("SELECT * FROM command_center_runs WHERE run_id=%s", (run_id,)).fetchone()
            return self._run_dict(row) if row else None

    def mark_run_running(self, run_id: str, *, lease_seconds: int) -> None:
        with self._transaction() as conn:
            row = conn.execute("""
                UPDATE command_center_runs SET status='running',
                    lease_expires_at=CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                    updated_at=CURRENT_TIMESTAMP WHERE run_id=%s AND status='queued' RETURNING run_id
            """, (max(5,lease_seconds),run_id)).fetchone()
            if not row:
                raise RunStateError("Run is unknown, interrupted, or no longer queued")

    def set_current_step(self, run_id: str, step: str, *, lease_seconds: int) -> None:
        with self._transaction() as conn:
            row = conn.execute("""
                UPDATE command_center_runs SET current_step=%s,
                    lease_expires_at=CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                    updated_at=CURRENT_TIMESTAMP WHERE run_id=%s AND status='running' RETURNING run_id
            """, (step,max(5,lease_seconds),run_id)).fetchone()
            if not row:
                raise RunStateError("Run is no longer active; refusing to continue")

    def append_step(self, run_id: str, step: dict[str, Any], *, lease_seconds: int) -> None:
        with self._transaction() as conn:
            row = conn.execute("""
                UPDATE command_center_runs SET steps=steps || %s,
                    lease_expires_at=CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                    updated_at=CURRENT_TIMESTAMP WHERE run_id=%s AND status='running' RETURNING run_id
            """, (self._Jsonb(step),max(5,lease_seconds),run_id)).fetchone()
            if not row:
                raise RunStateError("Run is no longer active; refusing to continue")

    def finish_run(self, run_id: str, *, status: str) -> None:
        if status not in _RUN_STATES - {"queued","running"}:
            raise ValueError("Invalid terminal run state")
        with self._transaction() as conn:
            row = conn.execute("""
                UPDATE command_center_runs SET status=%s, complete=TRUE, current_step='',
                    admission_slot=NULL, lease_expires_at=NULL, updated_at=CURRENT_TIMESTAMP
                 WHERE run_id=%s AND status IN ('queued','running') RETURNING run_id
            """, (status,run_id)).fetchone()
            if not row:
                raise RunStateError("Run is unknown or already terminal")

    def get_review_replay(self, *, action_id: str, idempotency_key: str,
                          request_sha256: str) -> dict[str, Any] | None:
        key_hash = hash_idempotency_key(idempotency_key)
        with self._transaction() as conn:
            self._recover_reviews(conn)
            row = conn.execute(
                "SELECT * FROM command_center_review_decisions WHERE idempotency_key_sha256=%s",
                (key_hash,),
            ).fetchone()
            if not row:
                return None
            if row["action_id"] != action_id or row["request_sha256"] != request_sha256:
                raise IdempotencyConflictError("Idempotency-Key conflicts with a different review request")
            if row["state"] == "processing":
                raise ReviewDecisionConflictError("Review decision is already processing")
            return row["outcome"]

    def claim_review(self, *, action_id: str, decision: str, idempotency_key: str,
                     request_sha256: str, claim_token: str, lease_seconds: int) -> dict[str, Any] | None:
        key_hash = hash_idempotency_key(idempotency_key)
        if decision not in {"accept","deny","revise"} or not _SHA_RE.fullmatch(request_sha256):
            raise ValueError("Invalid review decision or request digest")
        with self._transaction() as conn:
            self._recover_reviews(conn)
            prior = conn.execute(
                "SELECT * FROM command_center_review_decisions WHERE idempotency_key_sha256=%s",
                (key_hash,),
            ).fetchone()
            if prior:
                if prior["action_id"] != action_id or prior["request_sha256"] != request_sha256:
                    raise IdempotencyConflictError("Idempotency-Key conflicts with a different review request")
                if prior["state"] == "processing":
                    raise ReviewDecisionConflictError("Review decision is already processing")
                return prior["outcome"]
            inserted = conn.execute("""
                INSERT INTO command_center_review_decisions
                    (action_id,decision,state,idempotency_key_sha256,request_sha256,
                     claim_token_sha256,lease_expires_at)
                VALUES (%s,%s,'processing',%s,%s,%s,
                        CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'))
                ON CONFLICT DO NOTHING RETURNING action_id
            """, (action_id,decision,key_hash,request_sha256,_sha256(claim_token),max(5,lease_seconds))).fetchone()
            if not inserted:
                raise ReviewDecisionConflictError("Review action was already claimed or decided; reconcile before retrying")
            return None

    def finish_review(self, *, action_id: str, claim_token: str, state: str,
                      outcome: dict[str, Any]) -> None:
        if state not in _REVIEW_STATES:
            raise ValueError("Invalid review decision state")
        with self._transaction() as conn:
            row = conn.execute("""
                UPDATE command_center_review_decisions SET state=%s,outcome=%s,
                    lease_expires_at=NULL,updated_at=CURRENT_TIMESTAMP
                 WHERE action_id=%s AND state='processing' AND claim_token_sha256=%s
                RETURNING action_id
            """, (state,self._Jsonb(outcome),action_id,_sha256(claim_token))).fetchone()
            if not row:
                raise ReviewDecisionConflictError("Review claim was lost or requires reconciliation")

    def health(self) -> dict[str, Any]:
        with self._transaction() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"ok": True, "durable": True, "backend": self.backend, "schema_version": self.schema_version}

    def close(self) -> None:
        self._pool.close()


@lru_cache(maxsize=8)
def _cached_store(environment: str, dsn: str, max_concurrent_runs: int):
    if dsn:
        if environment == "production":
            verified_mode = re.search(r"(?:^|[?&\s])sslmode=verify-full(?:[&\s]|$)", dsn, re.IGNORECASE)
            root_certificate = re.search(r"(?:[?&\s])sslrootcert=[^&\s]+", dsn, re.IGNORECASE)
            if not verified_mode or not root_certificate:
                raise StateStoreNotConfiguredError(
                    "Production DSN must require sslmode=verify-full and an explicit sslrootcert"
                )
        return PostgresCommandCenterStore(dsn)
    if environment == "production":
        raise StateStoreNotConfiguredError("Production requires AIGC_COMMAND_CENTER_STATE_DSN")
    return InMemoryCommandCenterStore(max_concurrent_runs=max_concurrent_runs)


def get_command_center_store(*, max_concurrent_runs: int = 1):
    environment = os.environ.get("AIGC_ENV", "development").strip().lower()
    dsn = os.environ.get("AIGC_COMMAND_CENTER_STATE_DSN", "").strip()
    return _cached_store(environment, dsn, max(1, int(max_concurrent_runs)))
