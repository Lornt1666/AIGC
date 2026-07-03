from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "memory" / "aigc_state.sqlite"


ARTIFACT_TABLES = [
    "domains",
    "opportunities",
    "assessments",
    "proposals",
    "authorizations",
    "executions",
    "audit_packets",
    "outcomes",
    "patches",
    "evolution_patches",
    "agent_scores",
    "customer_satisfaction",
    "finance_ledger",
    "compliance_reviews",
    "connectors",
    "productization_releases",
    "subagent_team_plans",
    "fidelity_reviews",
    "quality_kernel_records",
    "work_order_governance_records",
    "procurement_records",
    "intelligence_ingestion_records",
    "capability_procurement_records",
    "stale_artifact_renewal_records",
    "regeneration_candidate_records",
    "secret_access_events",
    "incident_events",
]


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    created_at: str
    event_type: str
    phase: str
    status: str
    summary: str = ""
    data: Dict[str, Any] | None = None
    external_action_performed: bool = False


class AIGCStateStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as conn:
            for table in ARTIFACT_TABLES:
                conn.execute(_artifact_table_sql(table))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    external_action_performed INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_flags (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def insert_event(
        self,
        event_type: str,
        phase: str,
        status: str = "recorded",
        summary: str = "",
        data: Dict[str, Any] | None = None,
        external_action_performed: bool = False,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            event_id=f"AIGC-EVENT-{uuid.uuid4()}",
            created_at=utc_now(),
            event_type=event_type,
            phase=phase,
            status=status,
            summary=summary,
            data=data or {},
            external_action_performed=external_action_performed,
        )
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO runtime_events
                (event_id, created_at, event_type, phase, status, summary, data_json, external_action_performed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.created_at,
                event.event_type,
                event.phase,
                event.status,
                event.summary,
                json.dumps(event.data or {}, ensure_ascii=False, sort_keys=True),
                int(event.external_action_performed),
            ))
            conn.commit()
        return event

    def insert_artifact_record(
        self,
        table: str,
        record_id: str,
        phase: str,
        status: str,
        source_file: str,
        data: Dict[str, Any],
        risk_level: str = "",
        approval_status: str = "",
        audit_event_id: str = "",
    ) -> None:
        if table not in ARTIFACT_TABLES:
            raise ValueError(f"Unknown artifact table: {table}")
        now = utc_now()
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            conn.execute(f"""
                INSERT OR REPLACE INTO {table}
                (id, created_at, updated_at, phase, status, source_file, hash, risk_level,
                 approval_status, audit_event_id, data_json)
                VALUES (?, COALESCE((SELECT created_at FROM {table} WHERE id = ?), ?), ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                record_id,
                now,
                now,
                phase,
                status,
                source_file,
                digest,
                risk_level,
                approval_status,
                audit_event_id,
                payload,
            ))
            conn.commit()

    def set_flag(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO runtime_flags (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, utc_now()))
            conn.commit()

    def get_flag(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM runtime_flags WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def emergency_stop_active(self) -> bool:
        return self.get_flag("emergency_stop", "false") == "true"

    def get_status_summary(self) -> Dict[str, Any]:
        with self._connect() as conn:
            table_counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ARTIFACT_TABLES
            }
            runtime_events = conn.execute("SELECT COUNT(*) FROM runtime_events").fetchone()[0]
            recent_events = conn.execute("""
                SELECT event_id, created_at, event_type, phase, status, summary
                FROM runtime_events
                ORDER BY created_at DESC
                LIMIT 10
            """).fetchall()
        return {
            "db_path": str(self.db_path),
            "emergency_stop": self.emergency_stop_active(),
            "artifact_counts": table_counts,
            "runtime_events": runtime_events,
            "recent_events": [
                {
                    "event_id": row[0],
                    "created_at": row[1],
                    "event_type": row[2],
                    "phase": row[3],
                    "status": row[4],
                    "summary": row[5],
                }
                for row in recent_events
            ],
        }

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def _artifact_table_sql(table: str) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            phase TEXT NOT NULL,
            status TEXT NOT NULL,
            source_file TEXT NOT NULL,
            hash TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            approval_status TEXT NOT NULL,
            audit_event_id TEXT NOT NULL,
            data_json TEXT NOT NULL
        )
    """


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def event_to_dict(event: RuntimeEvent) -> Dict[str, Any]:
    return asdict(event)
