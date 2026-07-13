from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

import pytest

from src.application import (
    OpportunityScoutApplicationService,
    OpportunityScoutPolicyError,
    OpportunityScoutUnavailable,
    QuestCandidateApplicationService,
)
from src.infrastructure.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteQuestCandidateRepository,
)
from src.phase2_radar import FetchResult, OpportunityRecord


ROOT = Path(__file__).resolve().parents[2]


def strong_record(
    *,
    opportunity_id: str = "a" * 24,
    source_name: str = "We Work Remotely",
    source_type: str = "rss",
    pay_min: float | None = 800,
    pay_max: float | None = 1500,
) -> OpportunityRecord:
    return OpportunityRecord(
        opportunity_id=opportunity_id,
        source_platform=source_name,
        source_type=source_type,
        source_url=f"https://example.com/jobs/{opportunity_id}",
        source_attribution_required=True,
        discovered_at="2026-07-13T17:30:00+00:00",
        title="Python API documentation automation engineer",
        employer="Example Company",
        remote_status="remote",
        work_type="contract",
        pay_min=pay_min,
        pay_max=pay_max,
        pay_currency="USD" if pay_min is not None or pay_max is not None else "",
        pay_interval="project",
        description_plain=(
            "Build Python API documentation, OpenAPI and Swagger assets, "
            "automated tests, a dashboard, a repeatable workflow, and a "
            "clear code and research report deliverable."
        ),
        platform_policy_status="green",
    )


def forbidden_record() -> OpportunityRecord:
    return OpportunityRecord(
        opportunity_id="b" * 24,
        source_platform="We Work Remotely",
        source_type="rss",
        source_url="https://example.com/jobs/forbidden",
        source_attribution_required=True,
        discovered_at="2026-07-13T17:30:00+00:00",
        title="Mass DM captcha bypass automation",
        employer="Unsafe Example",
        remote_status="remote",
        work_type="contract",
        description_plain="Spam users, mass message accounts, and bypass captcha limits.",
        platform_policy_status="green",
    )


class FakeWWRConnector:
    def __init__(self, source: dict, run_config: dict) -> None:
        self.source = source
        self.run_config = run_config

    def fetch(self) -> FetchResult:
        records = [strong_record(), forbidden_record()]
        return FetchResult(
            source_slug="weworkremotely",
            source_name="We Work Remotely",
            raw_records=[{"id": record.opportunity_id} for record in records],
            normalized_records=records,
        )


class FakeNoPayConnector:
    def __init__(self, source: dict, run_config: dict) -> None:
        self.source = source
        self.run_config = run_config

    def fetch(self) -> FetchResult:
        record = strong_record(
            opportunity_id="c" * 24,
            pay_min=None,
            pay_max=None,
        )
        return FetchResult(
            source_slug="weworkremotely",
            source_name="We Work Remotely",
            raw_records=[{"id": record.opportunity_id}],
            normalized_records=[record],
        )


class FailingConnector:
    def __init__(self, source: dict, run_config: dict) -> None:
        self.source = source
        self.run_config = run_config

    def fetch(self) -> FetchResult:
        raise URLError("offline test fixture")


def build_scout(
    tmp_path: Path,
    connector_registry: dict,
) -> tuple[OpportunityScoutApplicationService, SQLiteConnectionFactory]:
    factory = SQLiteConnectionFactory(tmp_path / "operator.sqlite3")
    SQLiteMigrator(factory, ROOT / "migrations" / "sqlite").apply_all()
    candidate_service = QuestCandidateApplicationService(
        SQLiteQuestCandidateRepository(factory),
        catalog_path=ROOT / "config" / "aigc_work_source_gate_catalog.json",
        schema_path=ROOT / "schemas" / "quest_candidate.schema.json",
        exact_revision="TEST-REVISION",
    )
    scout = OpportunityScoutApplicationService(
        candidate_service,
        SQLiteAuditEventRepository(factory),
        source_config_path=ROOT / "config" / "phase2_sources.json",
        exact_revision="TEST-REVISION",
        connector_registry=connector_registry,
    )
    return scout, factory


def test_scout_filters_forbidden_records_and_persists_candidate(tmp_path: Path) -> None:
    scout, factory = build_scout(
        tmp_path,
        {"wwr_rss": FakeWWRConnector},
    )

    report = scout.discover(limit=5, source_ids=["weworkremotely"])

    assert report["status"] == "success"
    assert report["scanned_sources"] == 1
    assert report["records_assessed"] == 2
    assert report["eligible_records"] == 1
    assert report["new_candidates"] == 1
    assert report["existing_candidates"] == 0
    assert report["external_reads_performed"] is True
    assert report["external_action_performed"] is False

    candidate = report["candidates"][0]
    assert candidate["candidate_id"] == f"cand_{'a' * 24}"
    assert candidate["source_id"] == "weworkremotely"
    assert candidate["status"] == "DISCOVERED"
    assert candidate["budget_range"] == {
        "min": 800,
        "max": 1500,
        "currency": "USD",
    }
    assert candidate["deadline_days"] is None
    assert candidate["deadline_at"] is None
    assert candidate["external_action_performed"] is False

    with factory.connect() as connection:
        event_types = {
            row["event_type"]
            for row in connection.execute(
                "SELECT event_type FROM audit_events"
            ).fetchall()
        }
    assert "quest_candidate.ingested" in event_types
    assert "opportunity_scout.completed" in event_types


def test_scout_replay_is_idempotent_across_runs(tmp_path: Path) -> None:
    scout, _ = build_scout(
        tmp_path,
        {"wwr_rss": FakeWWRConnector},
    )

    first = scout.discover(limit=5, source_ids=["weworkremotely"])
    second = scout.discover(limit=5, source_ids=["weworkremotely"])

    assert first["new_candidates"] == 1
    assert second["new_candidates"] == 0
    assert second["existing_candidates"] == 1
    assert second["candidates"][0]["candidate_id"] == first["candidates"][0]["candidate_id"]


def test_scout_does_not_fabricate_budget_or_deadline(tmp_path: Path) -> None:
    scout, _ = build_scout(
        tmp_path,
        {"wwr_rss": FakeNoPayConnector},
    )

    report = scout.discover(limit=1, source_ids=["weworkremotely"])
    candidate = report["candidates"][0]

    assert candidate["budget_range"] is None
    assert candidate["compensation_text"] is None
    assert candidate["deadline_days"] is None
    assert candidate["deadline_at"] is None


def test_scout_rejects_unconfigured_or_credential_sources(tmp_path: Path) -> None:
    scout, _ = build_scout(
        tmp_path,
        {"wwr_rss": FakeWWRConnector},
    )

    with pytest.raises(OpportunityScoutPolicyError):
        scout.discover(limit=1, source_ids=["upwork"])
    with pytest.raises(OpportunityScoutPolicyError):
        scout.discover(limit=1, source_ids=["usajobs"])


def test_scout_returns_evidenced_failure_when_every_source_is_unavailable(
    tmp_path: Path,
) -> None:
    scout, factory = build_scout(
        tmp_path,
        {"wwr_rss": FailingConnector},
    )

    with pytest.raises(OpportunityScoutUnavailable) as caught:
        scout.discover(limit=1, source_ids=["weworkremotely"])

    report = caught.value.report
    assert report["status"] == "failed"
    assert report["scanned_sources"] == 0
    assert report["external_reads_performed"] is False
    assert report["external_action_performed"] is False
    assert report["source_results"][0]["error_type"] == "URLError"

    with factory.connect() as connection:
        row = connection.execute(
            "SELECT event_type FROM audit_events WHERE event_type = 'opportunity_scout.completed'"
        ).fetchone()
    assert row is not None
