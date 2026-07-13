from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from src.api.app import create_app


CANDIDATE_ID = "cand_work_acceptance_001"
QUEST_ID = "quest_work_acceptance_001"


def candidate_payload() -> dict:
    return {
        "candidate_id": CANDIDATE_ID,
        "source_id": "upwork",
        "source_url": "https://www.upwork.com/jobs/work-acceptance-example",
        "title": "Build a governed local API",
        "description": "Create a typed local API with tests and documentation.",
        "proposed_quest_title": "Governed Local API",
        "domain": "software_development",
        "required_skills": ["python", "fastapi", "sqlite"],
        "budget_range": None,
        "deadline_days": None,
        "remote_status": "remote",
        "risk_class": "low",
        "rights_status": "manual_operator_entry",
        "ingestion_channel": "manual",
    }


def create_proposed_quest(client: TestClient) -> dict:
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
            "reason": "Suitable for governed internal work review.",
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
    quest = created.json()["quest"]
    assert quest["quest_id"] == QUEST_ID
    assert quest["lifecycle_state"] == "PROPOSED"
    assert quest["approval_request"] is None
    assert quest["work_acceptance"] is None
    return quest


def request_approval(client: TestClient, *, reason: str = "Review work commitment.") -> dict:
    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/request-work-approval",
        json={
            "expected_revision": 1,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": reason,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["quest"]


def authorize_work_acceptance(client: TestClient) -> tuple[dict, dict]:
    prepared = client.get(
        f"/api/v1/quests/{QUEST_ID}/work-acceptance-authorization-bundle"
    )
    assert prepared.status_code == 200, prepared.text
    prepared_body = prepared.json()
    bundle = prepared_body["bundle"]

    request = bundle["request"]
    assert request["resource"]["resource_id"] == QUEST_ID
    assert request["action"] == "accept_work"
    assert request["scopes"] == ["quest:work_accept"]
    assert request["purpose"] == "work_acceptance"
    assert request["assurance"] == {
        "ial": "IAL0",
        "aal": "AAL0",
        "fal": "FAL0",
        "evidence_maturity": "EA0_CLAIMED",
    }
    assert len(request["evidence_ids"]) == 2
    assert prepared_body["external_action_performed"] is False

    authorized = client.post(
        "/api/v1/identity/authorize",
        json=bundle,
    )
    assert authorized.status_code == 200, authorized.text
    authorization = authorized.json()
    assert authorization["result"] == "PERMIT"
    assert authorization["passed"] is True
    assert authorization["receipt"]["state_changed"] is False
    assert authorization["receipt"]["external_action_performed"] is False
    return prepared_body, authorization


def test_work_acceptance_requires_explicit_approval_state(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    create_proposed_quest(client)

    direct = client.post(
        f"/api/v1/quests/{QUEST_ID}/accept-work",
        json={
            "expected_revision": 1,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "authorization_receipt_id": "missing",
            "authorization_request": {},
            "reason": "Attempted direct acceptance.",
        },
    )

    assert direct.status_code == 409
    assert direct.json()["detail"]["code"] == "QUEST_LIFECYCLE_CONFLICT"
    current = client.get(f"/api/v1/quests/{QUEST_ID}").json()
    assert current["lifecycle_state"] == "PROPOSED"


def test_request_work_approval_is_revision_checked_and_idempotent(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    create_proposed_quest(client)

    first = request_approval(client)
    assert first["revision"] == 2
    assert first["lifecycle_state"] == "APPROVAL_REQUIRED"
    assert first["approval_request"]["status"] == "PENDING"
    assert first["approval_request"]["quest_revision"] == 2
    assert first["approval_request"]["target_state"] == "WORK_ACCEPTED"
    assert first["work_acceptance"] is None

    replay = request_approval(client)
    assert replay == first

    changed = client.post(
        f"/api/v1/quests/{QUEST_ID}/request-work-approval",
        json={
            "expected_revision": 1,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Different review basis.",
        },
    )
    assert changed.status_code == 409

    stale = client.post(
        f"/api/v1/quests/{QUEST_ID}/request-work-approval",
        json={
            "expected_revision": 2,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Review work commitment.",
        },
    )
    assert stale.status_code == 409


def test_receipt_bound_work_acceptance_survives_restart(tmp_path: Path) -> None:
    database = tmp_path / "aigc.sqlite3"
    client = TestClient(create_app(database))
    create_proposed_quest(client)
    approval = request_approval(client)
    prepared, authorization = authorize_work_acceptance(client)

    accepted = client.post(
        f"/api/v1/quests/{QUEST_ID}/accept-work",
        json={
            "expected_revision": approval["revision"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "authorization_receipt_id": authorization["receipt_id"],
            "authorization_request": prepared["bundle"]["request"],
            "reason": "Proceed with bounded internal work.",
        },
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    quest = body["quest"]
    assert body["work_accepted"] is True
    assert body["external_contract_accepted"] is False
    assert body["external_action_performed"] is False
    assert quest["revision"] == 3
    assert quest["lifecycle_state"] == "WORK_ACCEPTED"
    assert quest["approval_request"]["status"] == "CONSUMED"
    assert quest["work_acceptance"]["decision"] == "WORK_ACCEPTED"
    assert (
        quest["work_acceptance"]["authorization_receipt_id"]
        == authorization["receipt_id"]
    )
    assert (
        quest["work_acceptance"]["authorization_request_digest"]
        == authorization["receipt"]["request_digest"]
    )
    assert quest["external_action_performed"] is False

    restarted = TestClient(create_app(database))
    recovered = restarted.get(f"/api/v1/quests/{QUEST_ID}")
    assert recovered.status_code == 200
    assert recovered.json()["work_acceptance"] == quest["work_acceptance"]

    replay = restarted.post(
        f"/api/v1/quests/{QUEST_ID}/accept-work",
        json={
            "expected_revision": 2,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "authorization_receipt_id": authorization["receipt_id"],
            "authorization_request": prepared["bundle"]["request"],
            "reason": "Proceed with bounded internal work.",
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["quest"] == quest

    with sqlite3.connect(database) as connection:
        event_types = {
            row[0]
            for row in connection.execute(
                "SELECT event_type FROM audit_events"
            ).fetchall()
        }
    assert "quest.work_approval_requested" in event_types
    assert "quest.work_accepted" in event_types


def test_changed_or_unbound_receipt_is_rejected(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    create_proposed_quest(client)
    approval = request_approval(client)
    prepared, authorization = authorize_work_acceptance(client)

    modified_request = json.loads(json.dumps(prepared["bundle"]["request"]))
    modified_request["resource"]["resource_id"] = "quest_other_target"
    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/accept-work",
        json={
            "expected_revision": approval["revision"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "authorization_receipt_id": authorization["receipt_id"],
            "authorization_request": modified_request,
            "reason": "Should fail closed.",
        },
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]["code"]
        == "QUEST_LIFECYCLE_AUTHORIZATION_DENIED"
    )
    assert client.get(f"/api/v1/quests/{QUEST_ID}").json()[
        "lifecycle_state"
    ] == "APPROVAL_REQUIRED"


def test_quest_board_projection_reports_gate_counts(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    create_proposed_quest(client)

    before = client.get("/api/v1/quest-board")
    assert before.status_code == 200
    assert before.json()["stats"]["proposed_quests"] == 1
    assert before.json()["stats"]["approval_required"] == 0

    request_approval(client)
    after = client.get("/api/v1/quest-board")
    assert after.status_code == 200
    body = after.json()
    assert body["stats"]["proposed_quests"] == 0
    assert body["stats"]["approval_required"] == 1
    assert body["canonical_acceptance_semantics"] == {
        "work_acceptance": "WORK_ACCEPTED",
        "delivery_acceptance": "ACCEPTED_FOR_DELIVERY",
        "generic_accepted_prohibited": True,
    }
    assert body["external_action_performed"] is False


def test_reject_and_cancel_are_separate_reasoned_commands(tmp_path: Path) -> None:
    reject_client = TestClient(create_app(tmp_path / "reject.sqlite3"))
    create_proposed_quest(reject_client)

    missing_reason = reject_client.post(
        f"/api/v1/quests/{QUEST_ID}/reject",
        json={
            "expected_revision": 1,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "",
        },
    )
    assert missing_reason.status_code == 422

    rejected = reject_client.post(
        f"/api/v1/quests/{QUEST_ID}/reject",
        json={
            "expected_revision": 1,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Opportunity is outside the bounded operating scope.",
        },
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["quest"]["lifecycle_state"] == "REJECTED"
    assert rejected.json()["quest"]["terminal_decision"]["decision"] == "REJECTED"

    cancel_client = TestClient(create_app(tmp_path / "cancel.sqlite3"))
    create_proposed_quest(cancel_client)
    approval = request_approval(cancel_client)
    cancelled = cancel_client.post(
        f"/api/v1/quests/{QUEST_ID}/cancel",
        json={
            "expected_revision": approval["revision"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Operator withdrew the internal work proposal.",
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    quest = cancelled.json()["quest"]
    assert quest["lifecycle_state"] == "CANCELLED"
    assert quest["approval_request"]["status"] == "CANCELLED"
    assert quest["terminal_decision"]["decision"] == "CANCELLED"


def test_html_board_exposes_explicit_non_generic_gate_controls(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    response = client.get("/quest-board")
    assert response.status_code == 200
    assert "Request work approval" in response.text
    assert "Authorize and accept work" in response.text
    assert "Reject Quest" in response.text
    assert "Cancel Quest" in response.text
    assert "WORK_ACCEPTED" in response.text
    assert "ACCEPTED_FOR_DELIVERY" in response.text
    assert "external contract" in response.text
    assert "Open Judgment Gate" not in response.text
