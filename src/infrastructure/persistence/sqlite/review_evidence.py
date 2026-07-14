from __future__ import annotations

import json
import sqlite3
from typing import Sequence

from src.domain.review_evidence import (
    ReviewEvidenceConflict,
    ReviewEvidencePacket,
    ReviewEvidenceRepository,
    ReviewJudgmentReceipt,
)

from .connection import SQLiteConnectionFactory


def _canonical(value: dict[str, object]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _packet(row: sqlite3.Row) -> ReviewEvidencePacket:
    return ReviewEvidencePacket.from_dict(json.loads(row["packet_json"]))


def _judgment(row: sqlite3.Row) -> ReviewJudgmentReceipt:
    return ReviewJudgmentReceipt.from_dict(json.loads(row["judgment_json"]))


class SQLiteReviewEvidenceRepository(ReviewEvidenceRepository):
    """Append-only persistence for review packets and human judgments."""

    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self.factory = factory

    def append_packet(
        self,
        packet: ReviewEvidencePacket,
    ) -> ReviewEvidencePacket:
        payload = packet.to_dict()
        payload_json = _canonical(payload)
        with self.factory.transaction() as connection:
            by_id = connection.execute(
                """
                SELECT * FROM review_evidence_packets
                WHERE packet_id = ?
                """,
                (packet.packet_id,),
            ).fetchone()
            if by_id:
                if by_id["packet_json"] != payload_json:
                    raise ReviewEvidenceConflict(
                        "Review packet identity was reused with different content"
                    )
                return _packet(by_id)

            by_revision = connection.execute(
                """
                SELECT * FROM review_evidence_packets
                WHERE quest_id = ? AND quest_revision = ?
                """,
                (packet.quest_id, packet.quest_revision),
            ).fetchone()
            if by_revision:
                existing = _packet(by_revision)
                if existing.request_digest != packet.request_digest:
                    raise ReviewEvidenceConflict(
                        "Quest revision already has a different review packet"
                    )
                return existing

            connection.execute(
                """
                INSERT INTO review_evidence_packets(
                    packet_id,
                    quest_id,
                    quest_revision,
                    exact_revision,
                    packet_digest,
                    request_digest,
                    identity_receipt_id,
                    work_authorization_receipt_id,
                    delivery_candidate,
                    recommended_decision,
                    packet_json,
                    created_at,
                    retention_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    packet.packet_id,
                    packet.quest_id,
                    packet.quest_revision,
                    packet.exact_revision,
                    packet.packet_digest,
                    packet.request_digest,
                    packet.identity_receipt_id,
                    packet.work_authorization_receipt_id,
                    int(bool(packet.readiness["delivery_candidate"])),
                    str(packet.readiness["recommended_decision"]),
                    payload_json,
                    payload["generated_at"],
                    packet.retention_class,
                ),
            )
            return packet

    def get_packet(self, packet_id: str) -> ReviewEvidencePacket | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM review_evidence_packets
                WHERE packet_id = ?
                """,
                (packet_id,),
            ).fetchone()
        return _packet(row) if row else None

    def get_packet_for_quest_revision(
        self,
        quest_id: str,
        quest_revision: int,
    ) -> ReviewEvidencePacket | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM review_evidence_packets
                WHERE quest_id = ? AND quest_revision = ?
                """,
                (quest_id, quest_revision),
            ).fetchone()
        return _packet(row) if row else None

    def list_packets(self, quest_id: str) -> Sequence[ReviewEvidencePacket]:
        with self.factory.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM review_evidence_packets
                WHERE quest_id = ?
                ORDER BY quest_revision ASC, created_at ASC
                """,
                (quest_id,),
            ).fetchall()
        return tuple(_packet(row) for row in rows)

    def append_judgment(
        self,
        receipt: ReviewJudgmentReceipt,
    ) -> ReviewJudgmentReceipt:
        payload = receipt.to_dict()
        payload_json = _canonical(payload)
        with self.factory.transaction() as connection:
            packet_row = connection.execute(
                """
                SELECT * FROM review_evidence_packets
                WHERE packet_id = ?
                """,
                (receipt.packet_id,),
            ).fetchone()
            if packet_row is None:
                raise ReviewEvidenceConflict(
                    "Review judgment requires a persisted evidence packet"
                )
            packet = _packet(packet_row)
            if packet.packet_digest != receipt.packet_digest:
                raise ReviewEvidenceConflict(
                    "Review judgment packet digest does not match persistence"
                )
            if packet.quest_id != receipt.quest_id:
                raise ReviewEvidenceConflict(
                    "Review judgment Quest does not match its packet"
                )

            by_id = connection.execute(
                """
                SELECT * FROM review_judgment_receipts
                WHERE judgment_id = ?
                """,
                (receipt.judgment_id,),
            ).fetchone()
            if by_id:
                if by_id["judgment_json"] != payload_json:
                    raise ReviewEvidenceConflict(
                        "Review judgment identity was reused with different content"
                    )
                return _judgment(by_id)

            by_packet = connection.execute(
                """
                SELECT * FROM review_judgment_receipts
                WHERE packet_id = ?
                """,
                (receipt.packet_id,),
            ).fetchone()
            if by_packet:
                existing = _judgment(by_packet)
                if existing.to_dict() != payload:
                    raise ReviewEvidenceConflict(
                        "Review packet already has a different human judgment"
                    )
                return existing

            connection.execute(
                """
                INSERT INTO review_judgment_receipts(
                    judgment_id,
                    packet_id,
                    quest_id,
                    quest_revision,
                    exact_revision,
                    identity_receipt_id,
                    authorization_receipt_id,
                    decision,
                    judgment_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.judgment_id,
                    receipt.packet_id,
                    receipt.quest_id,
                    receipt.quest_revision,
                    receipt.exact_revision,
                    receipt.identity_receipt_id,
                    receipt.authorization_receipt_id,
                    receipt.decision.value,
                    payload_json,
                    payload["decided_at"],
                ),
            )
            return receipt

    def get_judgment(
        self,
        judgment_id: str,
    ) -> ReviewJudgmentReceipt | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM review_judgment_receipts
                WHERE judgment_id = ?
                """,
                (judgment_id,),
            ).fetchone()
        return _judgment(row) if row else None

    def get_judgment_for_packet(
        self,
        packet_id: str,
    ) -> ReviewJudgmentReceipt | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM review_judgment_receipts
                WHERE packet_id = ?
                """,
                (packet_id,),
            ).fetchone()
        return _judgment(row) if row else None
