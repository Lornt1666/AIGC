from __future__ import annotations

import sqlite3
from pathlib import Path

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.memory import MemoryAdmissionDecision, MemoryCandidate, MemoryRecord


class SqliteNexusMemoryRepository:
    """Durable local Nexus memory adapter. MemoryCandidate cannot be inserted directly."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS nexus_memory_records (
                    memory_id TEXT PRIMARY KEY,
                    canonical_hash TEXT NOT NULL UNIQUE,
                    source_candidate_hash TEXT NOT NULL,
                    admission_decision_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS nexus_memory_admissions (
                    decision_id TEXT PRIMARY KEY,
                    candidate_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def admit(
        self,
        *,
        candidate: MemoryCandidate,
        decision: MemoryAdmissionDecision,
        record: MemoryRecord,
    ) -> None:
        candidate_hash = canonical_sha256(candidate)
        if decision.decision != "ACCEPT":
            raise ValueError("only accepted MemoryAdmissionDecision may create MemoryRecord")
        if decision.candidate_hash != candidate_hash:
            raise ValueError("memory admission decision is not bound to candidate hash")
        if decision.resulting_memory_id != record.memory_id:
            raise ValueError("memory admission result ID does not match MemoryRecord")
        if record.source_candidate_hash != candidate_hash:
            raise ValueError("MemoryRecord is not bound to candidate hash")
        if record.admission_decision_id != decision.decision_id:
            raise ValueError("MemoryRecord is not bound to admission decision")
        expected_record_hash = canonical_sha256(
            record.model_dump(mode="json", exclude={"canonical_hash"})
        )
        if record.canonical_hash != expected_record_hash:
            raise ValueError("MemoryRecord canonical_hash is invalid")

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO nexus_memory_admissions(decision_id, candidate_hash, payload_json) VALUES (?, ?, ?)",
                (decision.decision_id, candidate_hash, decision.model_dump_json()),
            )
            connection.execute(
                """
                INSERT INTO nexus_memory_records(
                    memory_id, canonical_hash, source_candidate_hash, admission_decision_id, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.memory_id,
                    record.canonical_hash,
                    record.source_candidate_hash,
                    record.admission_decision_id,
                    record.model_dump_json(),
                ),
            )

    def get(self, memory_id: str) -> MemoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM nexus_memory_records WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
        return MemoryRecord.model_validate_json(row["payload_json"]) if row else None

    def list_records(self, *, active_only: bool = False) -> tuple[MemoryRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM nexus_memory_records ORDER BY memory_id"
            ).fetchall()
        records = tuple(MemoryRecord.model_validate_json(row["payload_json"]) for row in rows)
        if active_only:
            records = tuple(item for item in records if item.active)
        return records
