from __future__ import annotations

from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from src.api.app import create_app


def candidate_payload() -> dict:
    return {
        "candidate_id": "cand_upwork_react_quest",
        "source_id": "upwork",
        "source_url": "https://www.upwork.com/jobs/example-quest",
        "title": "Build a React dashboard with Tailwind",
        "description": "Create a typed dashboard with a responsive Tailwind interface.",
        "proposed_quest_title": "React Dashboard Development",
        "domain": "software_development",
        "required_skills": ["react", "tailwind", "typescript"],
        "budget_range": {
            "min": 800,
            "max": 1500,
            "currency": "USD",
        },
        "deadline_days": 14,
        "remote_status": "remote",
        "risk_class": "low",
        "rights_status": "manual_operator_entry",
        "ingestion_channel": "manual",
    }


def qualify(client: TestClient) -> dict:
    ingested = client.post(
        "/api/v1/quests/candidates/ingest",
        json=candidate_payload(),
    )
    assert ingested.status_code == 201, ingested.text
    response = client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/qualify",
        json={
            "expected_revision": 1,
            "decision": "QUALIFY",
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Candidate is suitable for formal Quest proposal creation.",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_request(**overrides: object) -> dict:
    request: dict[str, object] = {
        "expected_candidate_revision": 2,
        "operator_role": "ACCOUNTABLE_OPERATOR",
    }
    request.update(overrides)
    return request


def test_discovered_candidate_cannot_create_quest(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    client.post(
        "/api/v1/quests/candidates/ingest",
        json=candidate_payload(),
    )

    response = client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/create-quest",
        json={
            "expected_candidate_revision": 1,
            "operator_role": "ACCOUNTABLE_OPERATOR",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUEST_CREATION_CONFLICT"


def test_qualified_candidate_creates_proposed_quest_atomically(
    tmp_path: Path,
) -> None:
    database = tmp_path / "aigc.sqlite3"
    client = TestClient(create_app(database))
    qualified = qualify(client)
    assert qualified["revision"] == 2
    assert qualified["qualification"]["quest_created"] is False

    response = client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/create-quest",
        json=create_request(),
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["work_accepted"] is False
    assert body["external_action_performed"] is False
    assert body["quest"]["quest_id"] == "quest_upwork_react_quest"
    assert body["quest"]["lifecycle_state"] == "PROPOSED"
    assert body["quest"]["lifecycle_state"] != "WORK_ACCEPTED"
    assert body["quest"]["owner_role"] == "ACCOUNTABLE_OPERATOR"
    assert body["quest"]["authority_class"] == "ACCOUNTABLE_OPERATOR"
    assert body["quest"]["budget"] == {
        "min": 800,
        "max": 1500,
        "currency": "USD",
    }
    assert body["quest"]["revision"] == 1
    assert body["candidate"]["revision"] == 3
    assert body["candidate"]["qualification"]["quest_created"] is True
    assert body["candidate"]["qualification"]["quest_id"] == body["quest"]["quest_id"]
    assert body["candidate"]["qualification"]["next_step"] == "REQUEST_WORK_ACCEPTANCE"

    with sqlite3.connect(database) as connection:
        event = connection.execute(
            "SELECT payload_json FROM audit_events WHERE event_type = ?",
            ("quest.created_from_candidate",),
        ).fetchone()
    assert event is not None
    assert '"work_accepted":false' in event[0]
    assert '"external_action_performed":false' in event[0]


def test_quest_creation_is_idempotent_across_restart(tmp_path: Path) -> None:
    database = tmp_path / "aigc.sqlite3"
    first_client = TestClient(create_app(database))
    qualify(first_client)
    first = first_client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/create-quest",
        json=create_request(),
    )
    assert first.status_code == 201, first.text

    restarted_client = TestClient(create_app(database))
    replay = restarted_client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/create-quest",
        json=create_request(),
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["quest"] == first.json()["quest"]
    assert replay.json()["candidate"] == first.json()["candidate"]
    assert restarted_client.get("/api/v1/quests").json()["count"] == 1


def test_changed_replay_is_rejected(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    qualify(client)
    first = client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/create-quest",
        json=create_request(),
    )
    assert first.status_code == 201

    changed = client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/create-quest",
        json=create_request(purpose="A materially different Quest purpose."),
    )
    assert changed.status_code == 409
    assert changed.json()["detail"]["code"] == "QUEST_CREATION_CONFLICT"


def test_stale_candidate_revision_is_rejected(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    qualify(client)

    response = client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/create-quest",
        json=create_request(expected_candidate_revision=1),
    )
    assert response.status_code == 409


def test_quest_list_filters_by_canonical_state(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))
    qualify(client)
    client.post(
        "/api/v1/quests/candidates/cand_upwork_react_quest/create-quest",
        json=create_request(),
    )

    proposed = client.get("/api/v1/quests?state=PROPOSED")
    accepted = client.get("/api/v1/quests?state=WORK_ACCEPTED")

    assert proposed.status_code == 200
    assert proposed.json()["count"] == 1
    assert accepted.status_code == 200
    assert accepted.json()["count"] == 0


def test_visible_quest_board_renders_operator_workflow(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "aigc.sqlite3"))

    response = client.get("/quest-board")

    assert response.status_code == 200
    assert "AIGC Quest Board" in response.text
    assert "Qualify candidate" in response.text
    assert "Create proposed Quest" in response.text
    assert "does not apply, bid, message" in response.text
    assert "aria-live=\"polite\"" in response.text
