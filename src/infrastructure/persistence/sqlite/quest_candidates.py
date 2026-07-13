from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from typing import Any, Mapping, Sequence
from uuid import uuid4

from src.domain.quests import (
    QuestCandidateConflict,
    QuestCandidateNotFound,
    QuestCandidateStateError,
)
from src.domain.repositories import StoredRecord

from .connection import SQLiteConnectionFactory


_COLLECTION = "quest_candidates"


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


def _append_audit_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    exact_revision: str,
    request_digest: str,
    payload: Mapping[str, Any],
) -> None:
    event_id = f"qcevt_{uuid4().hex}"
    payload_json = _canonical(payload)
    previous = connection.execute(
        "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
    ).fetchone()
    previous_hash = previous["event_hash"] if previous else None
    created_at = _now()
    material = "|".join(
        [
            event_id,
            event_type,
            exact_revision,
            request_digest,
            previous_hash or "",
            payload_json,
            created_at,
        ]
    )
    event_hash = sha256(material.encode("utf-8")).hexdigest()
    connection.execute(
        """
        INSERT INTO audit_events(
            event_id,
            event_type,
            exact_revision,
            request_digest,
            payload_json,
            previous_event_hash,
            event_hash,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_type,
            exact_revision,
            request_digest,
            payload_json,
            previous_hash,
            event_hash,
            created_at,
        ),
    )


class SQLiteQuestCandidateRepository:
    """Atomic SQLite persistence for candidate state and audit evidence."""

    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self.factory = factory

    def ingest(
        self,
        candidate: Mapping[str, Any],
        *,
        idempotency_key: str,
        exact_revision: str,
    ) -> StoredRecord:
        candidate_id = str(candidate["candidate_id"])
        payload_json = _canonical(candidate)
        request_digest = str(candidate["provenance"]["input_digest"])
        scope = f"quest-candidate-ingest:{candidate_id}"

        with self.factory.transaction() as connection:
            cached = connection.execute(
                """
                SELECT request_digest, response_json
                FROM idempotency_records
                WHERE scope = ? AND idempotency_key = ?
                """,
                (scope, idempotency_key),
            ).fetchone()
            if cached:
                if cached["request_digest"] != request_digest:
                    raise QuestCandidateConflict(
                        "Idempotency key reused with a different candidate payload"
                    )
                return StoredRecord(**json.loads(cached["response_json"]))

            existing = connection.execute(
                """
                SELECT *
                FROM records
                WHERE collection = ? AND record_id = ?
                """,
                (_COLLECTION, candidate_id),
            ).fetchone()
            if existing:
                existing_record = _stored(existing)
                existing_digest = (
                    existing_record.payload.get("provenance", {}).get("input_digest")
                )
                if existing_digest == request_digest:
                    return existing_record
                raise QuestCandidateConflict(
                    f"Candidate {candidate_id} already exists with different provenance"
                )

            created_at = _now()
            connection.execute(
                """
                INSERT INTO records(
                    collection,
                    record_id,
                    revision,
                    payload_json,
                    created_at,
                    updated_at,
                    retention_state
                ) VALUES (?, ?, 1, ?, ?, ?, 'ACTIVE')
                """,
                (_COLLECTION, candidate_id, payload_json, created_at, created_at),
            )
            result = StoredRecord(
                record_id=candidate_id,
                revision=1,
                payload=dict(candidate),
                created_at=created_at,
                updated_at=created_at,
            )
            _append_audit_event(
                connection,
                event_type="quest_candidate.ingested",
                exact_revision=exact_revision,
                request_digest=request_digest,
                payload={
                    "candidate_id": candidate_id,
                    "source_id": candidate["source_id"],
                    "status": candidate["status"],
                    "external_action_performed": False,
                },
            )
            connection.execute(
                """
                INSERT INTO idempotency_records(
                    scope,
                    idempotency_key,
                    request_digest,
                    response_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    scope,
                    idempotency_key,
                    request_digest,
                    json.dumps(asdict(result), sort_keys=True),
                    created_at,
                ),
            )
            return result

    def get(self, candidate_id: str) -> StoredRecord | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM records
                WHERE collection = ? AND record_id = ?
                """,
                (_COLLECTION, candidate_id),
            ).fetchone()
        return _stored(row) if row else None

    def list(self) -> Sequence[StoredRecord]:
        with self.factory.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM records
                WHERE collection = ? AND revoked_at IS NULL
                ORDER BY updated_at DESC, record_id
                """,
                (_COLLECTION,),
            ).fetchall()
        return tuple(_stored(row) for row in rows)

    def qualify(
        self,
        candidate_id: str,
        candidate: Mapping[str, Any],
        *,
        expected_revision: int,
        exact_revision: str,
    ) -> StoredRecord:
        payload_json = _canonical(candidate)
        request_digest = sha256(payload_json.encode("utf-8")).hexdigest()

        with self.factory.transaction() as connection:
            existing = connection.execute(
                """
                SELECT *
                FROM records
                WHERE collection = ? AND record_id = ?
                """,
                (_COLLECTION, candidate_id),
            ).fetchone()
            if not existing:
                raise QuestCandidateNotFound(candidate_id)
            if int(existing["revision"]) != expected_revision:
                raise QuestCandidateConflict(
                    f"Expected revision {expected_revision}, found {existing['revision']}"
                )
            existing_payload = json.loads(existing["payload_json"])
            if existing_payload.get("status") != "DISCOVERED":
                raise QuestCandidateStateError(
                    f"Candidate {candidate_id} cannot qualify from {existing_payload.get('status')}"
                )
            if candidate.get("status") != "QUALIFIED":
                raise QuestCandidateStateError(
                    "Qualification persistence requires QUALIFIED status"
                )

            updated_at = _now()
            next_revision = expected_revision + 1
            cursor = connection.execute(
                """
                UPDATE records
                SET revision = ?, payload_json = ?, updated_at = ?
                WHERE collection = ? AND record_id = ? AND revision = ?
                """,
                (
                    next_revision,
                    payload_json,
                    updated_at,
                    _COLLECTION,
                    candidate_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise QuestCandidateConflict(
                    "Candidate revision changed during qualification"
                )

            result = StoredRecord(
                record_id=candidate_id,
                revision=next_revision,
                payload=dict(candidate),
                created_at=existing["created_at"],
                updated_at=updated_at,
                revoked_at=existing["revoked_at"],
                retention_state=existing["retention_state"],
            )
            _append_audit_event(
                connection,
                event_type="quest_candidate.qualified",
                exact_revision=exact_revision,
                request_digest=request_digest,
                payload={
                    "candidate_id": candidate_id,
                    "previous_status": existing_payload["status"],
                    "resulting_status": candidate["status"],
                    "expected_revision": expected_revision,
                    "resulting_revision": next_revision,
                    "operator_role": candidate["qualification"]["operator_role"],
                    "quest_creation_authorized": True,
                    "quest_created": False,
                    "external_action_performed": False,
                },
            )
            return result
