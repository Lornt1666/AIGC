from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import threading
import uuid
from typing import Any

from psycopg.conninfo import make_conninfo
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ACTIVE = {"queued", "running", "unknown"}
_TERMINAL = {"completed", "failed", "timed_out", "unknown", "stopped"}


class CommandCenterStoreError(RuntimeError):
    """Base error for command-center state operations."""


class CommandCenterStoreUnavailable(CommandCenterStoreError):
    """Durable state is missing or unavailable."""


class IdempotencyConflict(CommandCenterStoreError):
    """An idempotency key was reused for a different request."""


class RunAlreadyActive(CommandCenterStoreError):
    """A run is active or has an unreconciled outcome."""


class EmergencyStopActive(CommandCenterStoreError):
    """The durable emergency stop blocks a run transition."""


class RunNotFound(CommandCenterStoreError):
    """A run is missing or its state transition is invalid."""


class ReviewAlreadyDecided(CommandCenterStoreError):
    """A review already has a claimed or completed decision."""


class ReviewOutcomeUnknown(CommandCenterStoreError):
    """A prior decision may have executed; manual reconciliation is required."""


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _check_digest(value: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError("request_digest must be a lowercase SHA-256 digest")


def _public_run(value: dict[str, Any]) -> dict[str, Any]:
    created, updated = value.get("created_at"), value.get("updated_at")
    return {
        "run_id": str(value["run_id"]),
        "status": str(value["status"]),
        "steps": deepcopy(value.get("steps") or []),
        "current": str(value.get("current_step", value.get("current", "")) or ""),
        "complete": bool(value.get("complete")),
        "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
        "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else updated,
        "version": int(value.get("version", 1)),
        "stop_epoch": int(value.get("stop_epoch", 0)),
    }


class MemoryCommandCenterStore:
    """Development/test-only store; health reports durable=false."""

    durable = False

    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {}
        self.run_keys: dict[tuple[str, str], str] = {}
        self.reviews: dict[str, dict[str, Any]] = {}
        self.review_keys: dict[tuple[str, str], str] = {}
        self.stop_active = False
        self.stop_epoch = 0
        self.stop_reason = ""
        self.stop_actor_id = None
        self.control_events: list[dict[str, Any]] = []
        self.reconciliations: list[dict[str, Any]] = []
        self.lock = threading.RLock()

    def healthcheck(self) -> dict[str, Any]:
        return {"ok": True, "durable": False, "backend": "memory"}

    def create_run(self, *, run_id: str, actor_id: str, idempotency_key: str, request_digest: str):
        _check_digest(request_digest)
        key_hash = _hash(idempotency_key)
        with self.lock:
            prior_id = self.run_keys.get((actor_id, key_hash))
            if prior_id:
                prior = self.runs[prior_id]
                if prior["request_digest"] != request_digest:
                    raise IdempotencyConflict("Idempotency key is bound to another request")
                return {**_public_run(prior), "replayed": True}, False
            if self.stop_active:
                raise EmergencyStopActive(f"Emergency stop is active at epoch {self.stop_epoch}")
            if any(item["status"] in _ACTIVE for item in self.runs.values()):
                raise RunAlreadyActive("A run is active or requires reconciliation")
            now = datetime.now(timezone.utc).isoformat()
            value = {
                "run_id": run_id, "actor_id": actor_id, "key_hash": key_hash,
                "request_digest": request_digest, "status": "queued", "steps": [],
                "current": "", "complete": False, "created_at": now,
                "updated_at": now, "version": 1, "stop_epoch": self.stop_epoch,
            }
            self.runs[run_id] = value
            self.run_keys[(actor_id, key_hash)] = run_id
            return {**_public_run(value), "replayed": False}, True

    def get_run(self, run_id: str):
        with self.lock:
            value = self.runs.get(run_id)
            return _public_run(value) if value else None

    def _require_run(self, run_id: str, states: set[str]):
        value = self.runs.get(run_id)
        if not value or value["status"] not in states:
            raise RunNotFound("Run is missing or its state transition is invalid")
        return value

    def mark_running(self, run_id: str):
        with self.lock:
            value = self._require_run(run_id, {"queued"})
            if self.stop_active or value["stop_epoch"] != self.stop_epoch:
                raise EmergencyStopActive(f"Emergency stop blocks run at epoch {self.stop_epoch}")
            value["status"] = "running"
            value["updated_at"] = datetime.now(timezone.utc).isoformat()
            value["version"] += 1

    def set_current(self, run_id: str, current: str):
        with self.lock:
            value = self._require_run(run_id, {"running"})
            if self.stop_active or value["stop_epoch"] != self.stop_epoch:
                raise EmergencyStopActive(f"Emergency stop blocks run at epoch {self.stop_epoch}")
            value["current"] = current
            value["updated_at"] = datetime.now(timezone.utc).isoformat()
            value["version"] += 1

    def append_step(self, run_id: str, step: dict[str, Any]):
        with self.lock:
            value = self._require_run(run_id, {"running"})
            value["steps"].append(deepcopy(step))
            value["updated_at"] = datetime.now(timezone.utc).isoformat()
            value["version"] += 1

    def finish_run(self, run_id: str, *, status: str):
        if status not in _TERMINAL:
            raise ValueError("invalid terminal run status")
        with self.lock:
            value = self._require_run(run_id, {"queued", "running"})
            if status == "completed" and (self.stop_active or value["stop_epoch"] != self.stop_epoch):
                raise EmergencyStopActive(f"Emergency stop blocks run completion at epoch {self.stop_epoch}")
            value.update(status=status, complete=True, current="")
            value["updated_at"] = datetime.now(timezone.utc).isoformat()
            value["version"] += 1

    def reconcile_unknown_run(self, *, run_id: str, actor_id: str, expected_version: int, confirmation_phrase: str):
        expected = f"RECONCILE AIGC RUN {run_id} AS FAILED VERSION {expected_version}"
        if confirmation_phrase != expected:
            raise ValueError("exact reconciliation phrase does not match")
        with self.lock:
            value = self._require_run(run_id, {"unknown"})
            if value["version"] != expected_version:
                raise RunNotFound("Run version changed; reload the run before reconciling")
            value.update(status="failed", complete=True, current="")
            value["updated_at"] = datetime.now(timezone.utc).isoformat()
            value["version"] += 1
            self.reconciliations.append({"run_id":run_id,"expected_version":expected_version,
                "actor_id":actor_id,"confirmation_phrase_sha256":_hash(confirmation_phrase),
                "disposition":"failed"})

    def get_emergency_state(self):
        with self.lock:
            return {"active": self.stop_active, "stop_epoch": self.stop_epoch,
                    "reason": self.stop_reason, "actor_id": self.stop_actor_id}

    def activate_emergency_stop(self, *, actor_id: str, reason: str):
        reason = reason.strip()
        if len(reason) < 10 or len(reason) > 2000:
            raise ValueError("reason must contain 10..2000 characters")
        with self.lock:
            if not self.stop_active:
                self.stop_epoch += 1
                self.stop_active = True
                self.stop_reason = reason.strip()
                self.stop_actor_id = actor_id
                self.control_events.append({"event_type":"activated","actor_id":actor_id,
                    "stop_epoch":self.stop_epoch,"reason_sha256":_hash(self.stop_reason)})
            return self.get_emergency_state()

    def clear_emergency_stop(self, *, actor_id: str, reason: str,
                             expected_epoch: int, exact_phrase: str):
        expected = f"CLEAR AIGC EMERGENCY STOP EPOCH {expected_epoch}"
        reason = reason.strip()
        if len(reason) < 10 or len(reason) > 2000:
            raise ValueError("reason must contain 10..2000 characters")
        if exact_phrase != expected:
            raise ValueError("exact_phrase does not match the emergency-stop epoch")
        with self.lock:
            if not self.stop_active:
                if expected_epoch == self.stop_epoch:
                    return self.get_emergency_state()
                raise RunNotFound("Emergency-stop epoch changed")
            if expected_epoch != self.stop_epoch:
                raise RunNotFound("Emergency-stop epoch changed")
            self.stop_active = False
            self.stop_reason = reason.strip()
            self.stop_actor_id = actor_id
            self.control_events.append({"event_type":"cleared","actor_id":actor_id,
                "stop_epoch":self.stop_epoch,"reason_sha256":_hash(self.stop_reason)})
            return self.get_emergency_state()

    def recover_stale_runs(self) -> int:
        return 0

    def claim_review(self, *, action_id: str, decision_type: str, actor_id: str,
                     idempotency_key: str, request_digest: str):
        if decision_type not in {"accept", "deny", "revise"}:
            raise ValueError("invalid review decision type")
        _check_digest(request_digest)
        key_hash = _hash(idempotency_key)
        with self.lock:
            prior = self.reviews.get(action_id)
            if prior:
                if (prior["actor_id"] == actor_id and prior["key_hash"] == key_hash
                    and prior["request_digest"] == request_digest and prior["state"] == "completed"):
                    return {**deepcopy(prior), "replayed": True}
                if prior["state"] in {"claimed", "unknown"}:
                    raise ReviewOutcomeUnknown("A prior decision may have executed; reconcile before retrying")
                raise ReviewAlreadyDecided("A decision is already recorded for this action")
            if (actor_id, key_hash) in self.review_keys:
                raise IdempotencyConflict("Idempotency key is already bound to another review")
            value = {"action_id": action_id, "actor_id": actor_id, "key_hash": key_hash,
                     "request_digest": request_digest, "decision_type": decision_type,
                     "state": "claimed", "result": None, "replayed": False}
            self.reviews[action_id] = value
            self.review_keys[(actor_id, key_hash)] = action_id
            return deepcopy(value)

    def complete_review(self, *, action_id: str, result: dict[str, Any]):
        with self.lock:
            value = self.reviews.get(action_id)
            if not value or value["state"] != "claimed":
                raise ReviewOutcomeUnknown("Review claim is missing or no longer pending")
            value.update(state="completed", result=deepcopy(result))

    def mark_review_unknown(self, *, action_id: str):
        with self.lock:
            value = self.reviews.get(action_id)
            if value and value["state"] == "claimed":
                value["state"] = "unknown"

    def get_review_decision(self, action_id: str):
        with self.lock:
            value = self.reviews.get(action_id)
            if not value:
                return None
            return {"action_id": action_id, "decision_type": value["decision_type"],
                    "state": value["state"], "result": deepcopy(value["result"])}


class PostgresCommandCenterStore:
    """Shared PostgreSQL store. Migrations are applied by a separate controlled step."""

    durable = True

    def __init__(self, dsn: str, *, sslmode: str = "verify-full") -> None:
        if not isinstance(dsn, str) or not dsn.strip():
            raise CommandCenterStoreUnavailable("Command-center database configuration is missing")
        self._pool = None
        try:
            self._pool = ConnectionPool(
                conninfo=make_conninfo(dsn, sslmode=sslmode),
                min_size=1, max_size=5, timeout=5,
                kwargs={"connect_timeout": 5, "application_name": "aigc-command-center", "row_factory": dict_row},
                open=False, name="aigc-command-center",
            )
            self._pool.open(wait=True)
            if not self.healthcheck()["ok"]:
                raise CommandCenterStoreUnavailable("Command-center database schema is not ready")
            self.recover_stale_runs()
        except CommandCenterStoreError:
            if self._pool:
                self._pool.close()
            raise
        except Exception as exc:
            if self._pool:
                self._pool.close()
            raise CommandCenterStoreUnavailable("Command-center database could not be opened safely") from exc

    def close(self):
        self._pool.close()

    def healthcheck(self):
        try:
            with self._pool.connection(timeout=5) as conn:
                row = conn.execute(
                    "SELECT to_regclass('public.command_center_runs') AS runs, "
                    "to_regclass('public.command_center_review_decisions') AS reviews, "
                    "to_regclass('public.command_center_control_state') AS controls, "
                    "to_regclass('public.command_center_control_events') AS control_events, "
                    "to_regclass('public.command_center_run_reconciliations') AS reconciliations"
                ).fetchone()
                ready = bool(row and all(row[name] for name in ("runs","reviews","controls","control_events","reconciliations")))
                return {"ok": ready, "durable": True, "backend": "postgresql"}
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Command-center database health check failed") from exc

    def get_emergency_state(self):
        try:
            with self._pool.connection(timeout=5) as conn:
                row = conn.execute(
                    "SELECT emergency_stop_active,stop_epoch,reason,actor_id,updated_at "
                    "FROM command_center_control_state WHERE singleton_id=1"
                ).fetchone()
                if not row:
                    raise CommandCenterStoreUnavailable("Emergency-stop state is missing")
                updated = row["updated_at"]
                return {"active": bool(row["emergency_stop_active"]), "stop_epoch": int(row["stop_epoch"]),
                        "reason": row["reason"], "actor_id": row["actor_id"],
                        "updated_at": updated.isoformat() if updated else None}
        except CommandCenterStoreError:
            raise
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Emergency-stop state could not be read") from exc

    def activate_emergency_stop(self, *, actor_id: str, reason: str):
        reason = reason.strip()
        if len(reason) < 10 or len(reason) > 2000:
            raise ValueError("reason must contain 10..2000 characters")
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    row = conn.execute(
                        "SELECT emergency_stop_active,stop_epoch,reason,actor_id,updated_at "
                        "FROM command_center_control_state WHERE singleton_id=1 FOR UPDATE"
                    ).fetchone()
                    if not row:
                        raise CommandCenterStoreUnavailable("Emergency-stop state is missing")
                    if row["emergency_stop_active"]:
                        return {"active": True, "stop_epoch": int(row["stop_epoch"]),
                                "reason": row["reason"], "actor_id": row["actor_id"]}
                    epoch = int(row["stop_epoch"]) + 1
                    updated = conn.execute(
                        """UPDATE command_center_control_state SET emergency_stop_active=TRUE,
                           stop_epoch=%s,reason=%s,actor_id=%s,updated_at=now()
                           WHERE singleton_id=1 RETURNING updated_at""",
                        (epoch, reason, actor_id),
                    ).fetchone()
                    conn.execute(
                        """INSERT INTO command_center_control_events
                           (event_id,event_type,actor_id,stop_epoch,reason_sha256,event_json)
                           VALUES (%s,'activated',%s,%s,%s,%s::jsonb)""",
                        (str(uuid.uuid4()), actor_id, epoch, _hash(reason),
                         json.dumps({"active":True,"stop_epoch":epoch,"reason_sha256":_hash(reason)},sort_keys=True)),
                    )
                    return {"active": True, "stop_epoch": epoch, "reason": reason,
                            "actor_id": actor_id, "updated_at": updated["updated_at"].isoformat()}
        except CommandCenterStoreError:
            raise
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Emergency stop could not be committed") from exc

    def clear_emergency_stop(self, *, actor_id: str, reason: str, expected_epoch: int, exact_phrase: str):
        expected = f"CLEAR AIGC EMERGENCY STOP EPOCH {expected_epoch}"
        if exact_phrase != expected:
            raise ValueError("exact_phrase does not match the emergency-stop epoch")
        reason = reason.strip()
        if len(reason) < 10 or len(reason) > 2000:
            raise ValueError("reason must contain 10..2000 characters")
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    row = conn.execute(
                        "SELECT emergency_stop_active,stop_epoch,reason,actor_id,updated_at "
                        "FROM command_center_control_state WHERE singleton_id=1 FOR UPDATE"
                    ).fetchone()
                    if not row or int(row["stop_epoch"]) != expected_epoch:
                        raise RunNotFound("Emergency-stop epoch changed; refresh before clearing")
                    if not row["emergency_stop_active"]:
                        return {"active": False, "stop_epoch": expected_epoch,
                                "reason": row["reason"], "actor_id": row["actor_id"]}
                    updated = conn.execute(
                        """UPDATE command_center_control_state SET emergency_stop_active=FALSE,
                           reason=%s,actor_id=%s,updated_at=now()
                           WHERE singleton_id=1 RETURNING updated_at""",
                        (reason, actor_id),
                    ).fetchone()
                    conn.execute(
                        """INSERT INTO command_center_control_events
                           (event_id,event_type,actor_id,stop_epoch,reason_sha256,event_json)
                           VALUES (%s,'cleared',%s,%s,%s,%s::jsonb)""",
                        (str(uuid.uuid4()), actor_id, expected_epoch, _hash(reason),
                         json.dumps({"active":False,"stop_epoch":expected_epoch,"reason_sha256":_hash(reason)},sort_keys=True)),
                    )
                    return {"active": False, "stop_epoch": expected_epoch, "reason": reason,
                            "actor_id": actor_id, "updated_at": updated["updated_at"].isoformat()}
        except (RunNotFound, ValueError):
            raise
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Emergency stop could not be cleared") from exc

    def recover_stale_runs(self):
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    cursor = conn.execute(
                        """UPDATE command_center_runs SET status='unknown', complete=TRUE,
                           current_step='', lease_until=NULL, updated_at=now(), version=version+1
                           WHERE status IN ('queued','running') AND lease_until < now()"""
                    )
                    return cursor.rowcount
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Stale runs could not be reconciled") from exc

    def create_run(self, *, run_id: str, actor_id: str, idempotency_key: str, request_digest: str):
        _check_digest(request_digest)
        key_hash = _hash(idempotency_key)
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    control = conn.execute(
                        "SELECT emergency_stop_active,stop_epoch FROM command_center_control_state WHERE singleton_id=1 FOR SHARE"
                    ).fetchone()
                    if not control:
                        raise CommandCenterStoreUnavailable("Durable emergency-stop state is missing")
                    if control["emergency_stop_active"]:
                        raise EmergencyStopActive(f"Emergency stop is active at epoch {control['stop_epoch']}")
                    row = conn.execute(
                        """INSERT INTO command_center_runs
                           (run_id,actor_id,idempotency_key_sha256,request_sha256,status,lease_until,stop_epoch)
                           VALUES (%s,%s,%s,%s,'queued',now()+interval '45 minutes',%s)
                           ON CONFLICT (actor_id,idempotency_key_sha256) DO NOTHING
                           RETURNING run_id,status,steps,current_step,complete,created_at,updated_at,version,stop_epoch""",
                        (run_id, actor_id, key_hash, request_digest, control["stop_epoch"]),
                    ).fetchone()
                    if row:
                        return {**_pg_run(row), "replayed": False}, True
                    prior = conn.execute(
                        """SELECT run_id,status,steps,current_step,complete,created_at,updated_at,version,request_sha256,stop_epoch
                           FROM command_center_runs WHERE actor_id=%s AND idempotency_key_sha256=%s""",
                        (actor_id, key_hash),
                    ).fetchone()
                    if not prior:
                        raise CommandCenterStoreUnavailable("Idempotent run receipt could not be read")
                    if prior["request_sha256"] != request_digest:
                        raise IdempotencyConflict("Idempotency key is bound to another request")
                    return {**_pg_run(prior), "replayed": True}, False
        except (IdempotencyConflict, RunAlreadyActive, EmergencyStopActive, CommandCenterStoreUnavailable):
            raise
        except UniqueViolation as exc:
            if getattr(getattr(exc, "diag", None), "constraint_name", "") == "command_center_one_active_run":
                raise RunAlreadyActive("A run is active or requires reconciliation") from exc
            raise IdempotencyConflict("Idempotency constraint rejected this run") from exc
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Durable run creation failed") from exc

    def get_run(self, run_id: str):
        try:
            with self._pool.connection(timeout=5) as conn:
                row = conn.execute(
                    """SELECT run_id,status,steps,current_step,complete,created_at,updated_at,version,stop_epoch
                       FROM command_center_runs WHERE run_id=%s""", (run_id,)
                ).fetchone()
                return _pg_run(row) if row else None
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Durable run status could not be read") from exc

    def reconcile_unknown_run(self, *, run_id: str, actor_id: str, expected_version: int, confirmation_phrase: str):
        expected = f"RECONCILE AIGC RUN {run_id} AS FAILED VERSION {expected_version}"
        if confirmation_phrase != expected:
            raise ValueError("exact reconciliation phrase does not match")
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    cursor = conn.execute(
                        """UPDATE command_center_runs SET status='failed',complete=TRUE,current_step='',
                           lease_until=NULL,updated_at=now(),version=version+1
                           WHERE run_id=%s AND status='unknown' AND version=%s""",
                        (run_id, expected_version),
                    )
                    if cursor.rowcount != 1:
                        raise RunNotFound("Run version changed; reload before reconciling")
                    conn.execute(
                        """INSERT INTO command_center_run_reconciliations
                           (reconciliation_id,run_id,expected_version,actor_id,confirmation_phrase_sha256,disposition)
                           VALUES (%s,%s,%s,%s,%s,'failed')""",
                        (str(uuid.uuid4()), run_id, expected_version, actor_id, _hash(confirmation_phrase)),
                    )
        except RunNotFound:
            raise
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Run reconciliation audit could not be committed") from exc

    def _update_run(self, sql: str, params: tuple[Any, ...], *, check_stop: bool = False):
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    if check_stop:
                        control = conn.execute(
                            "SELECT emergency_stop_active,stop_epoch FROM command_center_control_state WHERE singleton_id=1 FOR SHARE"
                        ).fetchone()
                        run_id = params[-1]
                        run = conn.execute(
                            "SELECT stop_epoch FROM command_center_runs WHERE run_id=%s AND status IN ('queued','running') FOR UPDATE",
                            (run_id,),
                        ).fetchone()
                        if not run:
                            raise RunNotFound("Run is missing or its state transition is invalid")
                        if not control or control["emergency_stop_active"] or int(run["stop_epoch"]) != int(control["stop_epoch"]):
                            raise EmergencyStopActive("Emergency stop is active or the run was authorized against an old stop epoch")
                    cursor = conn.execute(sql, params)
                    if cursor.rowcount != 1:
                        raise RunNotFound("Run is missing or its state transition is invalid")
        except (RunNotFound, EmergencyStopActive):
            raise
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Durable run transition failed") from exc

    def mark_running(self, run_id: str):
        self._update_run(
            """UPDATE command_center_runs SET status='running',lease_until=now()+interval '45 minutes',
               updated_at=now(),version=version+1 WHERE run_id=%s AND status='queued'""", (run_id,), check_stop=True
        )

    def set_current(self, run_id: str, current: str):
        self._update_run(
            """UPDATE command_center_runs SET current_step=%s,lease_until=now()+interval '45 minutes',
               updated_at=now(),version=version+1 WHERE run_id=%s AND status='running'""", (current, run_id), check_stop=True
        )

    def append_step(self, run_id: str, step: dict[str, Any]):
        self._update_run(
            """UPDATE command_center_runs SET steps=steps || %s::jsonb,
               lease_until=now()+interval '45 minutes',updated_at=now(),version=version+1
               WHERE run_id=%s AND status='running'""", (json.dumps(step, sort_keys=True), run_id)
        )

    def finish_run(self, run_id: str, *, status: str):
        if status not in _TERMINAL:
            raise ValueError("invalid terminal run status")
        self._update_run(
            """UPDATE command_center_runs SET status=%s,complete=TRUE,current_step='',
               lease_until=NULL,updated_at=now(),version=version+1
               WHERE run_id=%s AND status IN ('queued','running')""", (status, run_id),
            check_stop=(status == "completed")
        )

    def claim_review(self, *, action_id: str, decision_type: str, actor_id: str,
                     idempotency_key: str, request_digest: str):
        if decision_type not in {"accept", "deny", "revise"}:
            raise ValueError("invalid review decision type")
        _check_digest(request_digest)
        key_hash = _hash(idempotency_key)
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    row = conn.execute(
                        """INSERT INTO command_center_review_decisions
                           (action_id,actor_id,idempotency_key_sha256,request_sha256,decision_type,state)
                           VALUES (%s,%s,%s,%s,%s,'claimed')
                           ON CONFLICT (action_id) DO NOTHING
                           RETURNING action_id,actor_id,idempotency_key_sha256,request_sha256,
                                     decision_type,state,result_json""",
                        (action_id, actor_id, key_hash, request_digest, decision_type),
                    ).fetchone()
                    if row:
                        return _pg_review(row, replayed=False)
                    prior = conn.execute(
                        """SELECT action_id,actor_id,idempotency_key_sha256,request_sha256,
                                  decision_type,state,result_json
                           FROM command_center_review_decisions WHERE action_id=%s""",
                        (action_id,),
                    ).fetchone()
                    if not prior:
                        raise CommandCenterStoreUnavailable("Review decision receipt could not be read")
                    if (prior["actor_id"] == actor_id and prior["idempotency_key_sha256"] == key_hash
                        and prior["request_sha256"] == request_digest and prior["state"] == "completed"):
                        return _pg_review(prior, replayed=True)
                    if prior["state"] in {"claimed", "unknown"}:
                        raise ReviewOutcomeUnknown("A prior decision may have executed; reconcile before retrying")
                    raise ReviewAlreadyDecided("A decision is already recorded for this action")
        except (ReviewAlreadyDecided, ReviewOutcomeUnknown, IdempotencyConflict, CommandCenterStoreUnavailable):
            raise
        except UniqueViolation as exc:
            raise IdempotencyConflict("Idempotency key is already bound to another review") from exc
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Review decision could not be claimed") from exc

    def complete_review(self, *, action_id: str, result: dict[str, Any]):
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    cursor = conn.execute(
                        """UPDATE command_center_review_decisions
                           SET state='completed',result_json=%s::jsonb,updated_at=now()
                           WHERE action_id=%s AND state='claimed'""",
                        (json.dumps(result, sort_keys=True), action_id),
                    )
                    if cursor.rowcount != 1:
                        raise ReviewOutcomeUnknown("Review claim is missing or no longer pending")
        except ReviewOutcomeUnknown:
            raise
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Review decision receipt could not be committed") from exc

    def mark_review_unknown(self, *, action_id: str):
        try:
            with self._pool.connection(timeout=5) as conn:
                with conn.transaction():
                    conn.execute(
                        """UPDATE command_center_review_decisions SET state='unknown',updated_at=now()
                           WHERE action_id=%s AND state='claimed'""", (action_id,)
                    )
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Unknown review outcome could not be recorded") from exc

    def get_review_decision(self, action_id: str):
        try:
            with self._pool.connection(timeout=5) as conn:
                row = conn.execute(
                    """SELECT action_id,decision_type,state,result_json
                       FROM command_center_review_decisions WHERE action_id=%s""", (action_id,)
                ).fetchone()
                return ({"action_id": row["action_id"], "decision_type": row["decision_type"],
                         "state": row["state"], "result": row["result_json"]} if row else None)
        except Exception as exc:
            raise CommandCenterStoreUnavailable("Review decision state could not be read") from exc


def _pg_run(row: dict[str, Any]) -> dict[str, Any]:
    return _public_run(row)


def _pg_review(row: dict[str, Any], *, replayed: bool) -> dict[str, Any]:
    return {
        "action_id": row["action_id"], "actor_id": row["actor_id"],
        "idempotency_key_sha256": row["idempotency_key_sha256"],
        "request_sha256": row["request_sha256"], "decision_type": row["decision_type"],
        "state": row["state"], "result": row.get("result_json"), "replayed": replayed,
    }


def command_center_store_from_env():
    env = os.environ.get("AIGC_ENV", os.environ.get("ENVIRONMENT", "development")).strip().lower()
    dsn = os.environ.get("AIGC_COMMAND_CENTER_DATABASE_URL", "").strip()
    if env in {"production", "prod"} and not dsn:
        raise CommandCenterStoreUnavailable(
            "AIGC_COMMAND_CENTER_DATABASE_URL is required in production; process-local state is disabled"
        )
    if dsn:
        return PostgresCommandCenterStore(
            dsn, sslmode=os.environ.get("AIGC_COMMAND_CENTER_DB_SSLMODE", "verify-full").strip()
        )
    return MemoryCommandCenterStore()
