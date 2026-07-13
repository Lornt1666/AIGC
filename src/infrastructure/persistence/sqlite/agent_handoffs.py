from __future__ import annotations

from .connection import SQLiteConnectionFactory
from .repositories import SQLiteRecordRepository


class SQLiteAgentHandoffRepository(SQLiteRecordRepository):
    """SQLite adapter for versioned internal AgentHandoff records."""

    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        super().__init__(factory, "agent_handoffs")


class SQLiteReviewEvidencePacketRepository(SQLiteRecordRepository):
    """SQLite adapter for versioned ReviewEvidencePacket records."""

    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        super().__init__(factory, "review_evidence_packets")
