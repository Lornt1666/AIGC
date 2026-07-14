from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]


def validator(name: str) -> Draft202012Validator:
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def valid_packet() -> dict[str, object]:
    return {
        "contract_id": "AIGC-REVIEW-EVIDENCE-PACKET-001",
        "contract_version": "1.0.0",
        "packet_id": "REP-" + "A" * 24,
        "packet_digest": "a" * 64,
        "request_digest": "b" * 64,
        "quest_id": "quest_review_packet_001",
        "quest_revision": 3,
        "source_state": "WORK_ACCEPTED",
        "exact_revision": "c" * 40,
        "principal_id": "principal-a",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "identity_receipt_id": "IDR-" + "D" * 24,
        "work_authorization_receipt_id": "AUTHZ-review-packet",
        "work_acceptance_request_digest": "e" * 64,
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "executive_summary": "The bounded work is ready for accountable review.",
        "acceptance_criteria": [
            {
                "criterion_index": 0,
                "criterion_text": "All required behavior is implemented.",
                "status": "SATISFIED",
                "evidence_refs": ["artifact_review_packet"],
                "notes": None,
            }
        ],
        "artifacts": [
            {
                "artifact_id": "artifact_review_packet",
                "path": "reports/review/result.json",
                "sha256": "f" * 64,
                "media_type": "application/json",
                "size_bytes": 42,
                "evidence_state": "HASH_VERIFIED",
                "source": "REPOSITORY_ARTIFACT",
                "description": "Review result",
            }
        ],
        "test_receipts": [
            {
                "test_id": "test_review_packet",
                "command": "python -m pytest",
                "result": "PASS",
                "exact_revision": "c" * 40,
                "observed_at": "2026-07-14T00:00:00+00:00",
                "evidence_ref": "ci://run/1",
                "notes": None,
            }
        ],
        "source_references": [],
        "findings": {"security": [], "privacy": [], "policy": []},
        "unresolved_blockers": [],
        "rework_recommendations": [],
        "readiness": {
            "packet_complete": True,
            "criteria_satisfied": True,
            "tests_acceptable": True,
            "no_unresolved_blockers": True,
            "delivery_candidate": True,
            "recommended_decision": "ACCEPTED_FOR_DELIVERY",
        },
        "evidence_ids": [
            "AIGC-PIBC-RECEIPT:IDR-" + "D" * 24,
            "AIGC-AUTHORIZATION-RECEIPT:AUTHZ-review-packet",
        ],
        "generated_at": "2026-07-14T00:00:00+00:00",
        "retention_class": "REVIEW_EVIDENCE_365D",
        "advisory_only": True,
        "human_judgment_required": True,
        "state_changed": False,
        "external_action_performed": False,
    }


def valid_judgment() -> dict[str, object]:
    return {
        "contract_id": "AIGC-REVIEW-JUDGMENT-RECEIPT-001",
        "contract_version": "1.0.0",
        "judgment_id": "RJR-" + "A" * 24,
        "packet_id": "REP-" + "A" * 24,
        "packet_digest": "a" * 64,
        "quest_id": "quest_review_packet_001",
        "quest_revision": 4,
        "source_state": "REVIEW_REQUIRED",
        "target_state": "ACCEPTED_FOR_DELIVERY",
        "exact_revision": "c" * 40,
        "identity_receipt_id": "IDR-" + "D" * 24,
        "authorization_receipt_id": "AUTHZ-review-judgment",
        "authorization_request_digest": "b" * 64,
        "reviewer_principal_id": "principal-a",
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "decision": "ACCEPTED_FOR_DELIVERY",
        "reason": "All acceptance evidence is satisfactory.",
        "evidence_ids": [
            "AIGC-REVIEW-PACKET:REP-" + "A" * 24,
            "AIGC-PIBC-RECEIPT:IDR-" + "D" * 24,
            "AIGC-AUTHORIZATION-RECEIPT:AUTHZ-review-judgment",
        ],
        "decided_at": "2026-07-14T00:05:00+00:00",
        "delivery_performed": False,
        "state_changed": True,
        "external_action_performed": False,
    }


def test_review_packet_schema_accepts_complete_advisory_packet() -> None:
    assert not list(
        validator("review_evidence_packet.schema.json").iter_errors(
            valid_packet()
        )
    )


def test_review_packet_schema_rejects_unknown_authority_fields() -> None:
    packet = valid_packet()
    packet["automatic_acceptance"] = True
    assert list(
        validator("review_evidence_packet.schema.json").iter_errors(packet)
    )


def test_review_packet_schema_prohibits_state_change_and_external_action() -> None:
    packet = valid_packet()
    packet["state_changed"] = True
    packet["external_action_performed"] = True
    assert list(
        validator("review_evidence_packet.schema.json").iter_errors(packet)
    )


def test_review_judgment_schema_accepts_delivery_judgment_without_delivery() -> None:
    assert not list(
        validator("review_judgment_receipt.schema.json").iter_errors(
            valid_judgment()
        )
    )


def test_review_judgment_target_must_match_decision() -> None:
    receipt = valid_judgment()
    receipt["target_state"] = "REWORK_REQUIRED"
    assert list(
        validator("review_judgment_receipt.schema.json").iter_errors(receipt)
    )
