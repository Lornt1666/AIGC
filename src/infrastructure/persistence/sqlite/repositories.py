from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from typing import Any, Mapping, Sequence

from src.domain.repositories import StoredRecord

from .connection import SQLiteConnectionFactory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stored(row: sqlite3.Row) -> StoredRecord:
    return StoredRecord(
        record_id=row["record_id"],
        revision=row["revision"],
        payload=json.loads(row["payload_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        revoked_at=row["revoked_at"],
        retention_state=row["retention_state"],
    )


class SQLiteRecordRepository:
    def __init__(self, factory: SQLiteConnectionFactory, collection: str) -> None:
        self.factory = factory
        self.collection = collection

    def get(self, record_id: str) -> StoredRecord | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                "SELECT * FROM records WHERE collection = ? AND record_id = ?",
                (self.collection, record_id),
            ).fetchone()
        return _stored(row) if row else None

    def list(self, *, include_revoked: bool = False) -> Sequence[StoredRecord]:
        sql = "SELECT * FROM records WHERE collection = ?"
        params: tuple[Any, ...] = (self.collection,)
        if not include_revoked:
            sql += " AND revoked_at IS NULL"
        sql += " ORDER BY record_id"
        with self.factory.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return tuple(_stored(row) for row in rows)

    def put(
        self,
        record_id: str,
        payload: Mapping[str, Any],
        *,
        expected_revision: int | None = None,
        idempotency_key: str | None = None,
    ) -> StoredRecord:
        payload_json = _canonical(payload)
        request_digest = sha256(payload_json.encode("utf-8")).hexdigest()
        scope = f"record:{self.collection}:{record_id}"
        with self.factory.transaction() as connection:
            if idempotency_key:
                cached = connection.execute(
                    "SELECT request_digest, response_json FROM idempotency_records WHERE scope = ? AND idempotency_key = ?",
                    (scope, idempotency_key),
                ).fetchone()
                if cached:
                    if cached["request_digest"] != request_digest:
                        raise ValueError("Idempotency key reused with different payload")
                    return StoredRecord(**json.loads(cached["response_json"]))

            existing = connection.execute(
                "SELECT * FROM records WHERE collection = ? AND record_id = ?",
                (self.collection, record_id),
            ).fetchone()
            now = _now()
            if existing:
                if expected_revision is None or existing["revision"] != expected_revision:
                    raise RuntimeError("Optimistic concurrency conflict")
                revision = existing["revision"] + 1
                connection.execute(
                    "UPDATE records SET revision = ?, payload_json = ?, updated_at = ? WHERE collection = ? AND record_id = ? AND revision = ?",
                    (revision, payload_json, now, self.collection, record_id, expected_revision),
                )
                created_at = existing["created_at"]
                revoked_at = existing["revoked_at"]
                retention_state = existing["retention_state"]
            else:
                if expected_revision not in (None, 0):
                    raise RuntimeError("Optimistic concurrency conflict")
                revision = 1
                created_at = now
                revoked_at = None
                retention_state = "ACTIVE"
                connection.execute(
                    "INSERT INTO records(collection, record_id, revision, payload_json, created_at, updated_at, retention_state) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (self.collection, record_id, revision, payload_json, now, now, retention_state),
                )

            result = StoredRecord(record_id, revision, dict(payload), created_at, now, revoked_at, retention_state)
            if idempotency_key:
                connection.execute(
                    "INSERT INTO idempotency_records(scope, idempotency_key, request_digest, response_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (scope, idempotency_key, request_digest, json.dumps(result.__dict__, sort_keys=True), now),
                )
            return result

    def revoke(self, record_id: str, *, expected_revision: int, reason: str) -> StoredRecord:
        with self.factory.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM records WHERE collection = ? AND record_id = ?",
                (self.collection, record_id),
            ).fetchone()
            if not existing or existing["revision"] != expected_revision:
                raise RuntimeError("Optimistic concurrency conflict")
            now = _now()
            revision = expected_revision + 1
            connection.execute(
                "UPDATE records SET revision = ?, revoked_at = ?, revocation_reason = ?, retention_state = 'REVOKED', updated_at = ? WHERE collection = ? AND record_id = ? AND revision = ?",
                (revision, now, reason, now, self.collection, record_id, expected_revision),
            )
            return StoredRecord(
                record_id,
                revision,
                json.loads(existing["payload_json"]),
                existing["created_at"],
                now,
                now,
                "REVOKED",
            )


class SQLiteAuthorizationReceiptRepository:
    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self.factory = factory

    def append(self, receipt_id: str, receipt: Mapping[str, Any], *, exact_revision: str, request_digest: str, idempotency_key: str | None = None) -> StoredRecord:
        payload_json = _canonical(receipt)
        scope = f"authorization-receipt:{receipt_id}"
        with self.factory.transaction() as connection:
            existing = connection.execute("SELECT * FROM authorization_receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
            if existing:
                if existing["request_digest"] != request_digest or existing["receipt_json"] != payload_json:
                    raise ValueError("Authorization receipt is immutable")
                return StoredRecord(receipt_id, 1, json.loads(existing["receipt_json"]), existing["created_at"], existing["created_at"])
            now = _now()
            connection.execute(
                "INSERT INTO authorization_receipts(receipt_id, exact_revision, request_digest, receipt_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (receipt_id, exact_revision, request_digest, payload_json, now),
            )
            result = StoredRecord(receipt_id, 1, dict(receipt), now, now)
            if idempotency_key:
                connection.execute(
                    "INSERT INTO idempotency_records(scope, idempotency_key, request_digest, response_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (scope, idempotency_key, request_digest, json.dumps(result.__dict__, sort_keys=True), now),
                )
            return result

    def get(self, receipt_id: str) -> StoredRecord | None:
        with self.factory.connect() as connection:
            row = connection.execute("SELECT * FROM authorization_receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
        if not row:
            return None
        return StoredRecord(receipt_id, 1, json.loads(row["receipt_json"]), row["created_at"], row["created_at"])


class SQLiteAuditEventRepository:
    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self.factory = factory

    def append(self, event_id: str, event_type: str, payload: Mapping[str, Any], *, exact_revision: str, request_digest: str | None = None, idempotency_key: str | None = None) -> StoredRecord:
        payload_json = _canonical(payload)
        with self.factory.transaction() as connection:
            existing = connection.execute("SELECT * FROM audit_events WHERE event_id = ?", (event_id,)).fetchone()
            if existing:
                if existing["payload_json"] != payload_json:
                    raise ValueError("Audit event is immutable")
                return StoredRecord(event_id, 1, json.loads(existing["payload_json"]), existing["created_at"], existing["created_at"])
            previous = connection.execute("SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1").fetchone()
            previous_hash = previous["event_hash"] if previous else None
            now = _now()
            material = "|".join([event_id, event_type, exact_revision, request_digest or "", previous_hash or "", payload_json, now])
            event_hash = sha256(material.encode("utf-8")).hexdigest()
            connection.execute(
                "INSERT INTO audit_events(event_id, event_type, exact_revision, request_digest, payload_json, previous_event_hash, event_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, event_type, exact_revision, request_digest, payload_json, previous_hash, event_hash, now),
            )
            return StoredRecord(event_id, 1, {**dict(payload), "event_hash": event_hash, "previous_event_hash": previous_hash}, now, now)

    def list(self, *, after_event_id: str | None = None) -> Sequence[StoredRecord]:
        with self.factory.connect() as connection:
            if after_event_id:
                marker = connection.execute("SELECT sequence FROM audit_events WHERE event_id = ?", (after_event_id,)).fetchone()
                if not marker:
                    return ()
                rows = connection.execute("SELECT * FROM audit_events WHERE sequence > ? ORDER BY sequence", (marker["sequence"],)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM audit_events ORDER BY sequence").fetchall()
        return tuple(
            StoredRecord(row["event_id"], 1, {**json.loads(row["payload_json"]), "event_hash": row["event_hash"], "previous_event_hash": row["previous_event_hash"]}, row["created_at"], row["created_at"])
            for row in rows
        )
