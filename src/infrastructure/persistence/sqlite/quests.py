from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from typing import Any, Mapping, Sequence
from uuid import uuid4

from src.domain.quests import (
    QuestConflict,
    QuestCreationResult,
    QuestNotFound,
    QuestStateError,
)
from src.domain.repositories import StoredRecord

from .connection import SQLiteConnectionFactory


_CANDIDATE_COLLECTION = "quest_candidates"
_QUEST_COLLECTION = "quests"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stored(row: sqlite3.Row) -> StoredRecord:
    return StoredRecord(
        record_id=row["record_id"],
        revision=int(row["revision"]),
        payload=json.loads(row["payload_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        revoked_at=row["revoked_at"],
        retention_state=row["retention_state"],
    )


def _restore(value: Mapping[str, Any]) -> QuestCreationResult:
    return QuestCreationResult(
        candidate=StoredRecord(**dict(value["candidate"])),
        quest=StoredRecord(**dict(value["quest"])),
    )


def _append_audit_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    exact_revision: str,
    request_digest: str,
    payload: Mapping[str, Any],
) -> None:
    event_id = f"qevt_{uuid4().hex}"
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


class SQLiteQuestRepository:
    """Atomic persistence for canonical Quests and candidate conversion evidence."""

    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self.factory = factory

    def create_from_candidate(
        self,
        candidate_id: str,
        quest: Mapping[str, Any],
        *,
        expected_candidate_revision: int,
        idempotency_key: str,
        request_digest: str,
        exact_revision: str,
    ) -> QuestCreationResult:
        quest_id = str(quest["quest_id"])
        scope = f"quest-create:{candidate_id}"

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
                    raise QuestConflict(
                        "Quest-creation idempotency key was reused with different input"
                    )
                return _restore(json.loads(cached["response_json"]))

            candidate_row = connection.execute(
                """
                SELECT * FROM records
                WHERE collection = ? AND record_id = ?
                """,
                (_CANDIDATE_COLLECTION, candidate_id),
            ).fetchone()
            if not candidate_row:
                raise QuestNotFound(f"Candidate not found: {candidate_id}")

            candidate = json.loads(candidate_row["payload_json"])
            qualification = dict(candidate.get("qualification") or {})
            if qualification.get("quest_created") is True:
                existing_digest = qualification.get("quest_request_digest")
                existing_quest_id = qualification.get("quest_id")
                if existing_digest != request_digest or existing_quest_id != quest_id:
                    raise QuestConflict(
                        f"Candidate {candidate_id} was already converted using different input"
                    )
                quest_row = connection.execute(
                    """
                    SELECT * FROM records
                    WHERE collection = ? AND record_id = ?
                    """,
                    (_QUEST_COLLECTION, quest_id),
                ).fetchone()
                if not quest_row:
                    raise QuestStateError(
                        "Candidate records a Quest that is missing from persistence"
                    )
                return QuestCreationResult(
                    candidate=_stored(candidate_row),
                    quest=_stored(quest_row),
                )

            if int(candidate_row["revision"]) != expected_candidate_revision:
                raise QuestConflict(
                    f"Expected candidate revision {expected_candidate_revision}, "
                    f"found {candidate_row['revision']}"
                )
            if candidate.get("status") != "QUALIFIED":
                raise QuestStateError(
                    f"Candidate {candidate_id} must be QUALIFIED before Quest creation"
                )
            if qualification.get("quest_creation_authorized") is not True:
                raise QuestStateError(
                    f"Candidate {candidate_id} lacks Quest-creation authorization"
                )
            if quest.get("lifecycle_state") != "PROPOSED":
                raise QuestStateError(
                    "A Quest created from a candidate must begin in PROPOSED"
                )
            if quest.get("external_action_performed") is not False:
                raise QuestStateError(
                    "Quest creation cannot record an external action"
                )

            existing_quest = connection.execute(
                """
                SELECT * FROM records
                WHERE collection = ? AND record_id = ?
                """,
                (_QUEST_COLLECTION, quest_id),
            ).fetchone()
            if existing_quest:
                raise QuestConflict(f"Quest already exists: {quest_id}")

            now = _now()
            quest_payload = dict(quest)
            quest_payload["created_at"] = now
            quest_payload["updated_at"] = now
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
                (_QUEST_COLLECTION, quest_id, _canonical(quest_payload), now, now),
            )
            quest_record = StoredRecord(
                record_id=quest_id,
                revision=1,
                payload=quest_payload,
                created_at=now,
                updated_at=now,
            )

            qualification.update(
                {
                    "quest_created": True,
                    "quest_id": quest_id,
                    "quest_created_at": now,
                    "quest_request_digest": request_digest,
                    "next_step": "REQUEST_WORK_ACCEPTANCE",
                }
            )
            candidate["qualification"] = qualification
            candidate["external_action_performed"] = False
            next_candidate_revision = expected_candidate_revision + 1
            cursor = connection.execute(
                """
                UPDATE records
                SET revision = ?, payload_json = ?, updated_at = ?
                WHERE collection = ? AND record_id = ? AND revision = ?
                """,
                (
                    next_candidate_revision,
                    _canonical(candidate),
                    now,
                    _CANDIDATE_COLLECTION,
                    candidate_id,
                    expected_candidate_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise QuestConflict(
                    "Candidate revision changed during Quest creation"
                )
            candidate_record = StoredRecord(
                record_id=candidate_id,
                revision=next_candidate_revision,
                payload=candidate,
                created_at=candidate_row["created_at"],
                updated_at=now,
                revoked_at=candidate_row["revoked_at"],
                retention_state=candidate_row["retention_state"],
            )

            _append_audit_event(
                connection,
                event_type="quest.created_from_candidate",
                exact_revision=exact_revision,
                request_digest=request_digest,
                payload={
                    "candidate_id": candidate_id,
                    "candidate_previous_revision": expected_candidate_revision,
                    "candidate_resulting_revision": next_candidate_revision,
                    "quest_id": quest_id,
                    "quest_revision": 1,
                    "lifecycle_state": "PROPOSED",
                    "work_accepted": False,
                    "external_action_performed": False,
                },
            )

            result = QuestCreationResult(
                candidate=candidate_record,
                quest=quest_record,
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
                    json.dumps(
                        {
                            "candidate": asdict(candidate_record),
                            "quest": asdict(quest_record),
                        },
                        sort_keys=True,
                    ),
                    now,
                ),
            )
            return result

    def get(self, quest_id: str) -> StoredRecord | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM records
                WHERE collection = ? AND record_id = ?
                """,
                (_QUEST_COLLECTION, quest_id),
            ).fetchone()
        return _stored(row) if row else None

    def list(self) -> Sequence[StoredRecord]:
        with self.factory.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM records
                WHERE collection = ? AND revoked_at IS NULL
                ORDER BY updated_at DESC, record_id
                """,
                (_QUEST_COLLECTION,),
            ).fetchall()
        return tuple(_stored(row) for row in rows)
