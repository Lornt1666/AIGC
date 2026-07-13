from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import create_app


def candidate_payload(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "candidate_id": "cand_upwork_react_001",
        "source_id": "upwork",
        "source_url": "https://www.upwork.com/jobs/example",
        "title": "Build a React dashboard with Tailwind",
        "description": "Create a typed dashboard with a responsive Tailwind interface.",
        "proposed_quest_title": "React Dashboard Development",
        "domain": "software_development",
        "required_skills": ["React", "Tailwind", "TypeScript", "react"],
        "budget_range": {"min": 800, "max": 1500, "currency": "USD"},
        "deadline_days": 14,
        "remote_status": "remote",
        "risk_class": "low",
        "rights_status": "public_posting",
        "ingestion_channel": "manual",
    }
    payload.update(overrides)
    return payload


def test_ingest_list_qualify_and_restart(tmp_path) -> None:
    database = tmp_path / "aigc.sqlite"
    client = TestClient(create_app(database))

    created = client.post(
        "/api/v1/quests/candidates/ingest",
        json=candidate_payload(),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["candidate_id"] == "cand_upwork_react_001"
    assert body["source_name"] == "Upwork"
    assert body["required_skills"] == ["react", "tailwind", "typescript"]
    assert body["status"] == "DISCOVERED"
    assert body["revision"] == 1
    assert body["external_action_performed"] is False

    listed = client.get("/api/v1/quests/candidates")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    qualified = client.post(
        "/api/v1/quests/candidates/cand_upwork_react_001/qualify",
        json={
            "expected_revision": 1,
            "decision": "QUALIFY",
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Scope is sufficiently clear for governed quest drafting.",
        },
    )
    assert qualified.status_code == 200, qualified.text
    qualified_body = qualified.json()
    assert qualified_body["status"] == "QUALIFIED"
    assert qualified_body["revision"] == 2
    assert qualified_body["qualification"]["quest_creation_authorized"] is True
    assert qualified_body["qualification"]["quest_created"] is False
    assert qualified_body["external_action_performed"] is False

    restarted = TestClient(create_app(database))
    recovered = restarted.get("/api/v1/quests/candidates?status=QUALIFIED")
    assert recovered.status_code == 200
    assert recovered.json()["count"] == 1
    assert recovered.json()["items"][0]["revision"] == 2


def test_ingest_is_idempotent_for_same_normalized_input(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite"))
    first = client.post("/api/v1/quests/candidates/ingest", json=candidate_payload())
    second = client.post("/api/v1/quests/candidates/ingest", json=candidate_payload())
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["candidate_id"] == first.json()["candidate_id"]
    assert second.json()["revision"] == 1
    assert client.get("/api/v1/quests/candidates").json()["count"] == 1


def test_unknown_source_fails_closed(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite"))
    response = client.post(
        "/api/v1/quests/candidates/ingest",
        json=candidate_payload(source_id="unregistered_work_site"),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "WORK_SOURCE_POLICY_DENIED"


def test_account_sensitive_source_cannot_claim_read_only_adapter(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite"))
    response = client.post(
        "/api/v1/quests/candidates/ingest",
        json=candidate_payload(ingestion_channel="approved_read_only_adapter"),
    )
    assert response.status_code == 403


def test_existing_remoteok_adapter_may_ingest_read_only_candidate(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite"))
    response = client.post(
        "/api/v1/quests/candidates/ingest",
        json=candidate_payload(
            candidate_id="cand_remoteok_python_001",
            source_id="remoteok",
            source_url="https://remoteok.com/remote-jobs/example",
            title="Python automation engineer",
            ingestion_channel="existing_read_only_adapter",
            rights_status="official_api_record",
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()["ingestion_channel"] == "existing_read_only_adapter"
    assert response.json()["external_action_performed"] is False


def test_revision_conflict_fails_closed(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite"))
    client.post("/api/v1/quests/candidates/ingest", json=candidate_payload())
    response = client.post(
        "/api/v1/quests/candidates/cand_upwork_react_001/qualify",
        json={
            "expected_revision": 8,
            "decision": "QUALIFY",
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUEST_CANDIDATE_STATE_CONFLICT"


def test_work_source_catalog_exposes_prior_chat_log_examples(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite"))
    response = client.get("/api/v1/quests/sources")
    assert response.status_code == 200
    body = response.json()
    names = {item["name"] for item in body["items"]}
    assert body["count"] >= 52
    assert {
        "RemoteOK",
        "Upwork",
        "Fiverr",
        "GitHub Issues",
        "HackerOne",
        "CanadaBuys",
        "Kijiji",
        "Greenhouse",
        "Apollo.io",
        "Shopify",
    }.issubset(names)
    assert body["catalog_inclusion_grants_external_action"] is False


def test_unknown_fields_fail_contract_boundary(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite"))
    payload = candidate_payload()
    payload["unexpected"] = True
    response = client.post("/api/v1/quests/candidates/ingest", json=payload)
    assert response.status_code == 422
