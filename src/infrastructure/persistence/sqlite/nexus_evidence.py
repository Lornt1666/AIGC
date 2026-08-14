from __future__ import annotations

import sqlite3
from pathlib import Path

from src.domain.nexus.evidence import EvidenceReference


class SqliteNexusEvidenceRepository:
    """Durable local evidence index. Evidence remains non-authorizing."""

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
                CREATE TABLE IF NOT EXISTS nexus_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def put(self, evidence: EvidenceReference) -> None:
        if evidence.grants_authority is not False:
            raise ValueError("evidence cannot grant authority")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO nexus_evidence(evidence_id, digest, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                    digest=excluded.digest,
                    payload_json=excluded.payload_json
                """,
                (evidence.evidence_id, evidence.digest, evidence.model_dump_json()),
            )

    def get(self, evidence_id: str) -> EvidenceReference | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM nexus_evidence WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        return EvidenceReference.model_validate_json(row["payload_json"]) if row else None

    def list_all(self) -> tuple[EvidenceReference, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM nexus_evidence ORDER BY evidence_id"
            ).fetchall()
        return tuple(EvidenceReference.model_validate_json(row["payload_json"]) for row in rows)
