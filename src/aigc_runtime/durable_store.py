"""SQLite-backed prototype store for transactional permit use and audit events.

Use a managed PostgreSQL service for multi-instance production deployments. This
implementation is for local integration tests and single-host prototypes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
import threading
from typing import Any, Mapping

from .governed_runtime import GovernanceError, canonical_json, sha256_digest


class SQLiteGovernanceStore:
    def __init__(self, path: str):
        if not path:
            raise GovernanceError("sqlite_path_required")
        self.path = path
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=10000")
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS audit_events (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          event_id TEXT NOT NULL UNIQUE,
          event_type TEXT NOT NULL,
          at TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS permit_usage (
          permit_id TEXT PRIMARY KEY,
          fingerprint TEXT NOT NULL,
          uses INTEGER NOT NULL CHECK (uses >= 0),
          max_uses INTEGER NOT NULL CHECK (max_uses >= 1)
        );
        CREATE TABLE IF NOT EXISTS invocations (
          idempotency_key TEXT PRIMARY KEY,
          request_digest TEXT NOT NULL,
          status TEXT NOT NULL,
          result_json TEXT,
          updated_at TEXT NOT NULL
        );
        """)

    def append(self, event_type: str, payload: Mapping[str, Any], at: str) -> str:
        body = {"event_type": event_type, "at": at, "payload": dict(payload)}
        event_id = sha256_digest(body)
        with self._lock, self._db:
            row = self._db.execute("SELECT event_id FROM audit_events WHERE event_id=?", (event_id,)).fetchone()
            if row:
                return event_id
            self._db.execute(
                "INSERT INTO audit_events(event_id,event_type,at,payload_json) VALUES(?,?,?,?)",
                (event_id, event_type, at, canonical_json(dict(payload))),
            )
        return event_id

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            rows = self._db.execute("SELECT sequence,event_id,event_type,at,payload_json FROM audit_events ORDER BY sequence").fetchall()
        return tuple({"sequence": r["sequence"], "event_id": r["event_id"], "event_type": r["event_type"],
                      "at": r["at"], "payload": json.loads(r["payload_json"])} for r in rows)

    def consume_permit(self, permit_id: str, fingerprint: str, max_uses: int) -> None:
        with self._lock, self._db:
            row = self._db.execute("SELECT fingerprint,uses,max_uses FROM permit_usage WHERE permit_id=?", (permit_id,)).fetchone()
            if row is None:
                if max_uses < 1:
                    raise GovernanceError("permit_max_uses_invalid")
                self._db.execute("INSERT INTO permit_usage VALUES(?,?,?,?)", (permit_id, fingerprint, 1, max_uses))
                return
            if row["fingerprint"] != fingerprint or row["max_uses"] != max_uses:
                raise GovernanceError("permit_id_reused_with_different_contents")
            if row["uses"] >= row["max_uses"]:
                raise GovernanceError("permit_use_limit_exceeded")
            self._db.execute("UPDATE permit_usage SET uses=uses+1 WHERE permit_id=?", (permit_id,))

    def begin_invocation(self, idempotency_key: str, request_digest: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._lock, self._db:
            row = self._db.execute("SELECT * FROM invocations WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if row:
                if row["request_digest"] != request_digest:
                    raise GovernanceError("idempotency_key_reused_with_different_request")
                return {"created": False, "status": row["status"],
                        "result": json.loads(row["result_json"]) if row["result_json"] else None}
            self._db.execute("INSERT INTO invocations VALUES(?,?,?,?,?)",
                             (idempotency_key, request_digest, "RUNNING", None, now))
            return {"created": True, "status": "RUNNING", "result": None}

    def finish_invocation(self, idempotency_key: str, status: str, result: Any) -> None:
        if status not in {"SUCCEEDED", "FAILED", "UNKNOWN"}:
            raise GovernanceError("invocation_status_invalid")
        try:
            result_json = canonical_json(result)
        except (TypeError, ValueError) as exc:
            raise GovernanceError("invocation_result_not_json_serializable") from exc
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._lock, self._db:
            cursor = self._db.execute(
                "UPDATE invocations SET status=?,result_json=?,updated_at=? WHERE idempotency_key=? AND status='RUNNING'",
                (status, result_json, now, idempotency_key),
            )
            if cursor.rowcount != 1:
                raise GovernanceError("invocation_not_running_or_already_finalized")

    def close(self) -> None:
        with self._lock:
            self._db.close()
