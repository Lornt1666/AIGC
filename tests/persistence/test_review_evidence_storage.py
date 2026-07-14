from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from src.domain.review_evidence import (
    ReviewDecision,
    ReviewEvidenceConflict,
    ReviewEvidencePacket,
    ReviewJudgmentReceipt,
)
from src.infrastructure.persistence.sqlite import (
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteReviewEvidenceRepository,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "sqlite"
NOW = datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc)


def prepared(tmp_path: Path) -> SQLiteReviewEvidenceRepository:
    factory = SQLiteConnectionFactory(tmp_path / "review.sqlite3")
    SQLiteMigrator(factory, MIGRATIONS).apply_all()
    return SQLiteReviewEvidenceRepository(factory)


def packet(
    *,
    packet_id: str = "REP-" + "A" * 24,
    request_digest: str = "b" * 64,
) -> ReviewEvidencePacket:
    return ReviewEvidencePacket(
        packet_id=packet_id,
        packet_digest="a" * 64,
        request_digest=request_digest,
        quest_id="quest_review_storage_001",
        quest_revision=3,
        source_state="WORK_ACCEPTED",
        exact_revision="c" * 40,
        principal_id="principal-a",
        tenant_id="tenant-a",
        project_id="project-a",
        identity_receipt_id="IDR-" + "D" * 24,
        work_authorization_receipt_id="AUTHZ-review-storage",
        work_acceptance_request_digest="e" * 64,
        executive_summary="Ready for review.",
        acceptance_criteria=(
            {
                "criterion_index": 0,
                "criterion_text": "Criterion",
                "status": "SATISFIED",
                "evidence_refs": ["artifact_review_storage"],
                "notes": None,
            },
        ),
        artifacts=(
            {
                "artifact_id": "artifact_review_storage",
                "path": "reports/result.json",
                "sha256": "f" * 64,
                "media_type": "application/json",
                "size_bytes": 10,
                "evidence_state": "HASH_VERIFIED",
                "source": "REPOSITORY_ARTIFACT",
                "description": None,
            },
        ),
        test_receipts=(
            {
                "test_id": "test_review_storage",
                "command": "python -m pytest",
                "result": "PASS",
                "exact_revision": "c" * 40,
                "observed_at": NOW.isoformat(),
                "evidence_ref": None,
                "notes": None,
            },
        ),
        source_references=(),
        findings={"security": (), "privacy": (), "policy": ()},
        unresolved_blockers=(),
        rework_recommendations=(),
        readiness={
            "packet_complete": True,
            "criteria_satisfied": True,
            "tests_acceptable": True,
            "no_unresolved_blockers": True,
            "delivery_candidate": True,
            "recommended_decision": "ACCEPTED_FOR_DELIVERY",
        },
        evidence_ids=(
            "AIGC-PIBC-RECEIPT:IDR-" + "D" * 24,
            "AIGC-AUTHORIZATION-RECEIPT:AUTHZ-review-storage",
        ),
        generated_at=NOW,
    )


def judgment() -> ReviewJudgmentReceipt:
    return ReviewJudgmentReceipt(
        judgment_id="RJR-" + "B" * 24,
        packet_id="REP-" + "A" * 24,
        packet_digest="a" * 64,
        quest_id="quest_review_storage_001",
        quest_revision=4,
        exact_revision="c" * 40,
        identity_receipt_id="IDR-" + "D" * 24,
        authorization_receipt_id="AUTHZ-review-judgment",
        authorization_request_digest="b" * 64,
        reviewer_principal_id="principal-a",
        decision=ReviewDecision.ACCEPTED_FOR_DELIVERY,
        reason="Evidence satisfies the acceptance criteria.",
        evidence_ids=(
            "AIGC-REVIEW-PACKET:REP-" + "A" * 24,
            "AIGC-PIBC-RECEIPT:IDR-" + "D" * 24,
            "AIGC-AUTHORIZATION-RECEIPT:AUTHZ-review-judgment",
        ),
        decided_at=NOW,
    )


def test_review_packet_and_judgment_survive_restart(tmp_path: Path) -> None:
    repository = prepared(tmp_path)
    stored_packet = repository.append_packet(packet())
    stored_judgment = repository.append_judgment(judgment())

    restarted = SQLiteReviewEvidenceRepository(
        SQLiteConnectionFactory(repository.factory.database_path)
    )
    assert restarted.get_packet(stored_packet.packet_id) == stored_packet
    assert (
        restarted.get_packet_for_quest_revision(
            stored_packet.quest_id,
            stored_packet.quest_revision,
        )
        == stored_packet
    )
    assert restarted.get_judgment(stored_judgment.judgment_id) == stored_judgment
    assert (
        restarted.get_judgment_for_packet(stored_packet.packet_id)
        == stored_judgment
    )


def test_review_evidence_tables_are_append_only(tmp_path: Path) -> None:
    repository = prepared(tmp_path)
    repository.append_packet(packet())
    repository.append_judgment(judgment())

    with repository.factory.connect() as connection:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                "UPDATE review_evidence_packets SET recommended_decision = 'REWORK_REQUIRED'"
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute("DELETE FROM review_evidence_packets")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                "UPDATE review_judgment_receipts SET decision = 'REWORK_REQUIRED'"
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute("DELETE FROM review_judgment_receipts")


def test_one_quest_revision_cannot_receive_different_packet_content(
    tmp_path: Path,
) -> None:
    repository = prepared(tmp_path)
    repository.append_packet(packet())

    with pytest.raises(ReviewEvidenceConflict, match="different review packet"):
        repository.append_packet(
            packet(
                packet_id="REP-" + "C" * 24,
                request_digest="d" * 64,
            )
        )


def test_one_packet_cannot_receive_two_different_judgments(tmp_path: Path) -> None:
    repository = prepared(tmp_path)
    repository.append_packet(packet())
    repository.append_judgment(judgment())

    changed = ReviewJudgmentReceipt(
        **{
            **judgment().__dict__,
            "judgment_id": "RJR-" + "C" * 24,
            "decision": ReviewDecision.REWORK_REQUIRED,
            "reason": "Rework is required.",
        }
    )
    with pytest.raises(ReviewEvidenceConflict, match="different human judgment"):
        repository.append_judgment(changed)
