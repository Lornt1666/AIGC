from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.phase2_radar import FetchResult, OpportunityRecord


def record() -> OpportunityRecord:
    return OpportunityRecord(
        opportunity_id="d" * 24,
        source_platform="We Work Remotely",
        source_type="rss",
        source_url="https://example.com/jobs/scout-api",
        source_attribution_required=True,
        discovered_at="2026-07-13T17:30:00+00:00",
        title="Python OpenAPI automation engineer",
        employer="Example Company",
        remote_status="remote",
        work_type="contract",
        pay_min=1000,
        pay_max=2000,
        pay_currency="USD",
        pay_interval="project",
        description_plain=(
            "Build Python OpenAPI documentation, automated tests, code, "
            "a dashboard, and a repeatable workflow deliverable."
        ),
        platform_policy_status="green",
    )


class FakeConnector:
    def __init__(self, source: dict, run_config: dict) -> None:
        self.source = source
        self.run_config = run_config

    def fetch(self) -> FetchResult:
        item = record()
        return FetchResult(
            source_slug="weworkremotely",
            source_name="We Work Remotely",
            raw_records=[{"id": item.opportunity_id}],
            normalized_records=[item],
        )


class FailingConnector:
    def __init__(self, source: dict, run_config: dict) -> None:
        self.source = source
        self.run_config = run_config

    def fetch(self) -> FetchResult:
        raise URLError("offline test fixture")


def test_discovery_endpoint_persists_candidate_and_reports_read_only_boundary(
    tmp_path: Path,
) -> None:
    application = create_app(database_path=tmp_path / "operator.sqlite3")
    application.state.container.opportunity_scout_service.connector_registry = {
        "wwr_rss": FakeConnector,
    }
    client = TestClient(application)

    response = client.post(
        "/api/v1/opportunities/discover"
        "?limit=2&source_id=weworkremotely"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["new_candidates"] == 1
    assert body["external_reads_performed"] is True
    assert body["external_action_performed"] is False

    candidates = client.get("/api/v1/quests/candidates").json()
    assert candidates["count"] == 1
    assert candidates["items"][0]["source_id"] == "weworkremotely"
    assert candidates["items"][0]["status"] == "DISCOVERED"


def test_discovery_endpoint_fails_closed_for_unconfigured_source(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(database_path=tmp_path / "operator.sqlite3"))

    response = client.post(
        "/api/v1/opportunities/discover?limit=1&source_id=upwork"
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "OPPORTUNITY_SCOUT_POLICY_DENIED"
    assert response.json()["detail"]["external_action_performed"] is False


def test_discovery_endpoint_returns_structured_upstream_failure(
    tmp_path: Path,
) -> None:
    application = create_app(database_path=tmp_path / "operator.sqlite3")
    application.state.container.opportunity_scout_service.connector_registry = {
        "wwr_rss": FailingConnector,
    }
    client = TestClient(application)

    response = client.post(
        "/api/v1/opportunities/discover"
        "?limit=1&source_id=weworkremotely"
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["code"] == "OPPORTUNITY_SOURCES_UNAVAILABLE"
    assert detail["report"]["status"] == "failed"
    assert detail["external_action_performed"] is False


def test_quest_board_exposes_read_only_scout_controls(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "operator.sqlite3"))

    response = client.get("/quest-board")

    assert response.status_code == 200
    assert "Read-only Opportunity Scout" in response.text
    assert "Discover opportunities" in response.text
    assert "/api/v1/opportunities/discover" in response.text
    assert "No arbitrary URL" in response.text
