from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app


CANDIDATE_ID = "cand_terminal_replay_001"
QUEST_ID = "quest_terminal_replay_001"


def create_quest(client: TestClient) -> None:
    ingested = client.post(
        "/api/v1/quests/candidates/ingest",
        json={
            "candidate_id": CANDIDATE_ID,
            "source_id": "upwork",
            "source_url": "https://www.upwork.com/jobs/terminal-replay",
            "title": "Terminal replay test",
            "description": "Exercise idempotent terminal lifecycle commands.",
            "domain": "software_development",
            "required_skills": ["python"],
            "budget_range": None,
            "risk_class": "low",
            "rights_status": "manual_operator_entry",
            "ingestion_channel": "manual",
        },
    )
    assert ingested.status_code == 201, ingested.text
    qualified = client.post(
        f"/api/v1/quests/candidates/{CANDIDATE_ID}/qualify",
        json={
            "expected_revision": 1,
            "decision": "QUALIFY",
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": "Create a proposed Quest for terminal replay testing.",
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
    assert created.json()["quest"]["quest_id"] == QUEST_ID


def test_identical_reject_replay_recovers_original_result(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "reject.sqlite3"))
    create_quest(client)
    command = {
        "expected_revision": 1,
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Outside the bounded operating scope.",
    }

    first = client.post(f"/api/v1/quests/{QUEST_ID}/reject", json=command)
    replay = client.post(f"/api/v1/quests/{QUEST_ID}/reject", json=command)

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()

    changed = client.post(
        f"/api/v1/quests/{QUEST_ID}/reject",
        json={**command, "reason": "A materially different rejection basis."},
    )
    assert changed.status_code == 409


def test_identical_cancel_replay_recovers_original_result(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "cancel.sqlite3"))
    create_quest(client)
    command = {
        "expected_revision": 1,
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Operator withdrew the proposed internal work.",
    }

    first = client.post(f"/api/v1/quests/{QUEST_ID}/cancel", json=command)
    replay = client.post(f"/api/v1/quests/{QUEST_ID}/cancel", json=command)

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()

    changed_revision = client.post(
        f"/api/v1/quests/{QUEST_ID}/cancel",
        json={**command, "expected_revision": 2},
    )
    assert changed_revision.status_code == 409
