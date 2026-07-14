from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app


CANDIDATE_ID = "cand_identity_bound_001"
QUEST_ID = "quest_identity_bound_001"


def candidate_payload() -> dict[str, object]:
    return {
        "candidate_id": CANDIDATE_ID,
        "source_id": "upwork",
        "source_url": "https://www.upwork.com/jobs/identity-bound-example",
        "title": "Build an identity-bound governed API",
        "description": "Connect PIBC identity evidence to governed Quest acceptance.",
        "proposed_quest_title": "Identity-Bound Governed API",
        "domain": "software_development",
        "required_skills": ["python", "fastapi", "sqlite"],
        "budget_range": None,
        "deadline_days": None,
        "remote_status": "remote",
        "risk_class": "low",
        "rights_status": "manual_operator_entry",
        "ingestion_channel": "manual",
    }


def create_approval_required_quest(client: TestClient) -> dict[str, object]:
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
            "reason": "Approved for local identity-bound integration testing.",
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
            "reason": "Review the bounded internal work commitment.",
        },
    )
    assert approval.status_code == 200, approval.text
    quest = approval.json()["quest"]
    assert quest["revision"] == 2
    assert quest["lifecycle_state"] == "APPROVAL_REQUIRED"
    return quest


def local_preflight(client: TestClient) -> dict[str, object]:
    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/local-identity-preflight",
        json={
            "expected_revision": 2,
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"] == "PERMIT"
    assert body["runtime_authority"] == "LOCAL_SIMULATION"
    assert body["production_identity_authorized"] is False
    assert body["external_action_performed"] is False
    return body


def test_identity_bound_acceptance_completes_existing_quest_gate(
    tmp_path: Path,
) -> None:
    database = tmp_path / "identity-bound.sqlite3"
    client = TestClient(create_app(database))
    create_approval_required_quest(client)
    identity = local_preflight(client)

    accepted = client.post(
        f"/api/v1/quests/{QUEST_ID}/identity-bound-accept-work",
        json={
            "expected_revision": 2,
            "identity_receipt_id": identity["identity_receipt_id"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Proceed with bounded internal work.",
        },
    )

    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["work_accepted"] is True
    assert body["external_contract_accepted"] is False
    assert body["production_identity_authorized"] is False
    assert body["external_action_performed"] is False
    assert body["identity_receipt_id"] == identity["identity_receipt_id"]
    quest = body["quest"]
    assert quest["revision"] == 3
    assert quest["lifecycle_state"] == "WORK_ACCEPTED"
    assert quest["approval_request"]["status"] == "CONSUMED"

    authorization = client.get(
        f"/api/v1/audit/receipts/{body['authorization_receipt_id']}"
    )
    assert authorization.status_code == 200, authorization.text
    receipt = authorization.json()
    assert receipt["result"] == "PERMIT"
    assert (
        f"AIGC-PIBC-RECEIPT:{identity['identity_receipt_id']}"
        in receipt["evidence_ids"]
    )
    assert receipt["state_changed"] is False
    assert receipt["external_action_performed"] is False

    restarted = TestClient(create_app(database))
    recovered = restarted.get(f"/api/v1/quests/{QUEST_ID}")
    assert recovered.status_code == 200
    assert recovered.json()["lifecycle_state"] == "WORK_ACCEPTED"


def test_identity_bound_acceptance_is_idempotent_for_same_command(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "replay.sqlite3"))
    create_approval_required_quest(client)
    identity = local_preflight(client)
    command = {
        "expected_revision": 2,
        "identity_receipt_id": identity["identity_receipt_id"],
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Proceed with bounded internal work.",
    }

    first = client.post(
        f"/api/v1/quests/{QUEST_ID}/identity-bound-accept-work",
        json=command,
    )
    replay = client.post(
        f"/api/v1/quests/{QUEST_ID}/identity-bound-accept-work",
        json=command,
    )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert replay.json()["quest"] == first.json()["quest"]
    assert (
        replay.json()["authorization_receipt_id"]
        == first.json()["authorization_receipt_id"]
    )


def test_missing_or_forged_identity_receipt_fails_closed(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "forged.sqlite3"))
    create_approval_required_quest(client)

    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/identity-bound-accept-work",
        json={
            "expected_revision": 2,
            "identity_receipt_id": "IDR-" + "A" * 24,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "This must fail closed.",
        },
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]["code"]
        == "QUEST_LIFECYCLE_AUTHORIZATION_DENIED"
    )
    current = client.get(f"/api/v1/quests/{QUEST_ID}").json()
    assert current["lifecycle_state"] == "APPROVAL_REQUIRED"


def test_local_preflight_requires_pending_approval_state(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "preflight-state.sqlite3"))
    ingested = client.post(
        "/api/v1/quests/candidates/ingest",
        json=candidate_payload(),
    )
    assert ingested.status_code == 201
    qualified = client.post(
        f"/api/v1/quests/candidates/{CANDIDATE_ID}/qualify",
        json={
            "expected_revision": 1,
            "decision": "QUALIFY",
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )
    assert qualified.status_code == 200
    created = client.post(
        f"/api/v1/quests/candidates/{CANDIDATE_ID}/create-quest",
        json={
            "expected_candidate_revision": 2,
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )
    assert created.status_code == 201

    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/local-identity-preflight",
        json={
            "expected_revision": 1,
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUEST_LIFECYCLE_CONFLICT"


def test_identity_bound_command_rejects_caller_supplied_authority(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "extra-fields.sqlite3"))
    create_approval_required_quest(client)
    identity = local_preflight(client)

    response = client.post(
        f"/api/v1/quests/{QUEST_ID}/identity-bound-accept-work",
        json={
            "expected_revision": 2,
            "identity_receipt_id": identity["identity_receipt_id"],
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Attempted authority injection.",
            "principal_id": "principal-attacker",
            "roles": ["administrator"],
            "assurance": {"ial": "IAL3"},
        },
    )

    assert response.status_code == 422
    current = client.get(f"/api/v1/quests/{QUEST_ID}").json()
    assert current["lifecycle_state"] == "APPROVAL_REQUIRED"
