from __future__ import annotations

from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from src.api.app import create_app


CANDIDATE_ID = "cand_review_evidence_001"
QUEST_ID = "quest_review_evidence_001"


def candidate_payload() -> dict[str, object]:
    return {
        "candidate_id": CANDIDATE_ID,
        "source_id": "upwork",
        "source_url": "https://www.upwork.com/jobs/review-evidence-example",
        "title": "Build a governed review evidence gate",
        "description": "Generate immutable evidence and require human judgment.",
        "proposed_quest_title": "Review Evidence Gate",
        "domain": "software_development",
        "required_skills": ["python", "fastapi", "sqlite"],
        "budget_range": None,
        "deadline_days": None,
        "remote_status": "remote",
        "risk_class": "low",
        "rights_status": "manual_operator_entry",
        "ingestion_channel": "manual",
    }


def create_work_accepted_quest(client: TestClient) -> dict[str, object]:
    ingested = client.post(
        "/api/v1/quests/candidates/ingest",
        json=candidate_payload(),
    )
    assert ingested.status_code == 201, ingested.text
    qualified = client.post(
        f"/api/v1/quests/candidates/{CANDIDATE_ID}/qualify",
        json={
            "expected_revision": 1,
            "decision": "QUALIFY",
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Suitable for review evidence testing.",
        },
    )
    assert qualified.status_code == 200, qualified.text
    created = client.post(
        f"/api/v1/quests/candidates/{CANDIDATE_ID}/create-quest",
        json={
            "expected_candidate_revision": 2,
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )
    assert created.status_code == 201, created.text
    approval = client.post(
        f"/api/v1/quests/{QUEST_ID}/request-work-approval",
        json={
            "expected_revision": 1,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Authorize bounded internal implementation.",
        },
    )
    assert approval.status_code == 200, approval.text
    identity = client.post(
        f"/api/v1/quests/{QUEST_ID}/local-identity-preflight",
        json={
            "expected_revision": 2,
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )
    assert identity.status_code == 200, identity.text
    accepted = client.post(
        f"/api/v1/quests/{QUEST_ID}/identity-bound-accept-work",
        json={
            "expected_revision": 2,
            "identity_receipt_id": identity.json()["identity_receipt_id"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Proceed with bounded internal implementation.",
        },
    )
    assert accepted.status_code == 200, accepted.text
    quest = accepted.json()["quest"]
    assert quest["revision"] == 3
    assert quest["lifecycle_state"] == "WORK_ACCEPTED"
    return quest


def review_identity(client: TestClient, revision: int) -> dict[str, object]:
    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/local-review-identity-preflight",
        json={
            "expected_revision": revision,
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"] == "PERMIT"
    assert response.json()["runtime_authority"] == "LOCAL_SIMULATION"
    return response.json()


def packet_command(
    identity_receipt_id: str,
    *,
    blockers: list[str] | None = None,
    criterion_status: str = "SATISFIED",
) -> dict[str, object]:
    return {
        "expected_revision": 3,
        "identity_receipt_id": identity_receipt_id,
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "executive_summary": "The bounded implementation is ready for accountable review.",
        "acceptance_criteria": [
            {
                "criterion_index": index,
                "status": criterion_status,
                "evidence_refs": [f"artifact_review_evidence_{index}"],
                "notes": None,
            }
            for index in range(3)
        ],
        "artifacts": [
            {
                "artifact_id": "artifact_review_evidence_0",
                "path": "reports/review-evidence.json",
                "sha256": "a" * 64,
                "media_type": "application/json",
                "size_bytes": 128,
                "evidence_state": "CI_OBSERVED",
                "source": "CI_ARTIFACT",
                "description": "Review evidence manifest.",
            },
            {
                "artifact_id": "artifact_review_evidence_1",
                "path": "reports/test-results.txt",
                "sha256": "b" * 64,
                "media_type": "text/plain",
                "size_bytes": 64,
                "evidence_state": "TESTED",
                "source": "REPOSITORY_ARTIFACT",
                "description": "Test results.",
            },
            {
                "artifact_id": "artifact_review_evidence_2",
                "path": "docs/review-notes.md",
                "sha256": "c" * 64,
                "media_type": "text/markdown",
                "size_bytes": 256,
                "evidence_state": "HASH_VERIFIED",
                "source": "REPOSITORY_ARTIFACT",
                "description": "Review notes.",
            },
        ],
        "test_receipts": [
            {
                "test_id": "test_review_evidence",
                "command": "python -m pytest",
                "result": "PASS",
                "observed_at": "2026-07-14T00:00:00Z",
                "evidence_ref": "ci://review-evidence/run-1",
                "notes": None,
            }
        ],
        "source_references": [
            {
                "source_id": "source_internal_spec",
                "title": "AIGC review evidence specification",
                "reference": "docs/REVIEW_EVIDENCE_PACKET_V1.md",
                "rights_status": "INTERNAL",
            }
        ],
        "security_findings": [],
        "privacy_findings": [],
        "policy_findings": [],
        "unresolved_blockers": blockers or [],
        "rework_recommendations": (
            ["Resolve the documented blocker before delivery acceptance."]
            if blockers
            else []
        ),
    }


def generate_packet(
    client: TestClient,
    identity_receipt_id: str,
    *,
    blockers: list[str] | None = None,
    criterion_status: str = "SATISFIED",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/review-packets",
        json=packet_command(
            identity_receipt_id,
            blockers=blockers,
            criterion_status=criterion_status,
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()["packet"]


def open_review_gate(
    client: TestClient,
    packet: dict[str, object],
    identity_receipt_id: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/review-gate/open",
        json={
            "expected_revision": 3,
            "packet_id": packet["packet_id"],
            "identity_receipt_id": identity_receipt_id,
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_review_packet_to_delivery_judgment_is_fully_evidence_bound(
    tmp_path: Path,
) -> None:
    database = tmp_path / "review-gate.sqlite3"
    client = TestClient(create_app(database))
    create_work_accepted_quest(client)
    packet_identity = review_identity(client, 3)
    packet = generate_packet(
        client,
        str(packet_identity["identity_receipt_id"]),
    )

    assert packet["readiness"]["delivery_candidate"] is True
    assert packet["readiness"]["recommended_decision"] == (
        "ACCEPTED_FOR_DELIVERY"
    )
    assert packet["advisory_only"] is True
    assert packet["state_changed"] is False
    assert packet["external_action_performed"] is False
    unchanged = client.get(f"/api/v1/quests/{QUEST_ID}").json()
    assert unchanged["revision"] == 3
    assert unchanged["lifecycle_state"] == "WORK_ACCEPTED"

    opened = open_review_gate(
        client,
        packet,
        str(packet_identity["identity_receipt_id"]),
    )
    assert opened["quest"]["revision"] == 4
    assert opened["quest"]["lifecycle_state"] == "REVIEW_REQUIRED"
    assert opened["human_judgment_required"] is True

    judgment_identity = review_identity(client, 4)
    judged = client.post(
        f"/api/v1/quests/{QUEST_ID}/review-gate/judge",
        json={
            "expected_revision": 4,
            "packet_id": packet["packet_id"],
            "identity_receipt_id": judgment_identity["identity_receipt_id"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "decision": "ACCEPTED_FOR_DELIVERY",
            "reason": "All criteria and tests are evidenced and no blockers remain.",
        },
    )

    assert judged.status_code == 200, judged.text
    body = judged.json()
    assert body["quest"]["revision"] == 5
    assert body["quest"]["lifecycle_state"] == "ACCEPTED_FOR_DELIVERY"
    assert body["judgment"]["decision"] == "ACCEPTED_FOR_DELIVERY"
    assert body["judgment"]["delivery_performed"] is False
    assert body["judgment"]["external_action_performed"] is False
    assert body["delivery_performed"] is False

    packet_lookup = client.get(
        f"/api/v1/review-packets/{packet['packet_id']}"
    )
    assert packet_lookup.status_code == 200
    assert packet_lookup.json()["judgment"]["judgment_id"] == (
        body["judgment"]["judgment_id"]
    )

    restarted = TestClient(create_app(database))
    recovered = restarted.get(f"/api/v1/quests/{QUEST_ID}")
    assert recovered.status_code == 200
    assert recovered.json()["lifecycle_state"] == "ACCEPTED_FOR_DELIVERY"

    with sqlite3.connect(database) as connection:
        events = {
            row[0]
            for row in connection.execute(
                "SELECT event_type FROM audit_events"
            ).fetchall()
        }
    assert "quest.review_required" in events
    assert "quest.accepted_for_delivery" in events


def test_incomplete_packet_cannot_be_accepted_and_can_require_rework(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "rework.sqlite3"))
    create_work_accepted_quest(client)
    packet_identity = review_identity(client, 3)
    packet = generate_packet(
        client,
        str(packet_identity["identity_receipt_id"]),
        blockers=["Security review remains unresolved."],
        criterion_status="PARTIAL",
    )
    assert packet["readiness"]["delivery_candidate"] is False
    assert packet["readiness"]["recommended_decision"] == "REWORK_REQUIRED"
    open_review_gate(
        client,
        packet,
        str(packet_identity["identity_receipt_id"]),
    )
    judgment_identity = review_identity(client, 4)

    denied = client.post(
        f"/api/v1/quests/{QUEST_ID}/review-gate/judge",
        json={
            "expected_revision": 4,
            "packet_id": packet["packet_id"],
            "identity_receipt_id": judgment_identity["identity_receipt_id"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "decision": "ACCEPTED_FOR_DELIVERY",
            "reason": "Attempted premature acceptance.",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == (
        "REVIEW_GATE_AUTHORIZATION_DENIED"
    )
    assert client.get(f"/api/v1/quests/{QUEST_ID}").json()[
        "lifecycle_state"
    ] == "REVIEW_REQUIRED"

    rework = client.post(
        f"/api/v1/quests/{QUEST_ID}/review-gate/judge",
        json={
            "expected_revision": 4,
            "packet_id": packet["packet_id"],
            "identity_receipt_id": judgment_identity["identity_receipt_id"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "decision": "REWORK_REQUIRED",
            "reason": "Resolve the security finding and resubmit evidence.",
        },
    )
    assert rework.status_code == 200, rework.text
    assert rework.json()["quest"]["lifecycle_state"] == "REWORK_REQUIRED"
    assert rework.json()["judgment"]["decision"] == "REWORK_REQUIRED"


def test_review_commands_reject_caller_supplied_authority(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "injection.sqlite3"))
    create_work_accepted_quest(client)
    identity = review_identity(client, 3)
    command = packet_command(str(identity["identity_receipt_id"]))
    command["principal_id"] = "principal-attacker"
    command["assurance"] = {"ial": "IAL3"}
    command["automatic_acceptance"] = True

    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/review-packets",
        json=command,
    )

    assert response.status_code == 422
    current = client.get(f"/api/v1/quests/{QUEST_ID}").json()
    assert current["lifecycle_state"] == "WORK_ACCEPTED"
