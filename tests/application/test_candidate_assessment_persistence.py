from __future__ import annotations

from pathlib import Path

import pytest

from src.application import (
    OpportunityScoutApplicationService,
    QuestCandidateApplicationService,
)
from src.domain.quests import WorkSourcePolicyError
from src.infrastructure.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteQuestCandidateRepository,
)
from src.phase2_radar import FetchResult, OpportunityRecord


ROOT = Path(__file__).resolve().parents[2]


class AssessmentFixtureConnector:
    def __init__(self, source: dict, run_config: dict) -> None:
        self.source = source
        self.run_config = run_config

    def fetch(self) -> FetchResult:
        record = OpportunityRecord(
            opportunity_id="assessmentpersist000001",
            source_platform="We Work Remotely",
            source_type="rss",
            source_url="https://example.com/jobs/assessmentpersist000001",
            source_attribution_required=True,
            discovered_at="2026-07-13T18:00:00+00:00",
            title="React TypeScript frontend developer",
            employer="Example Company",
            remote_status="remote",
            work_type="contract",
            description_plain=(
                "Build a React TypeScript Tailwind CSS dashboard, an automation "
                "workflow, a repeatable process, and a clear code deliverable."
            ),
            platform_policy_status="green",
        )
        return FetchResult(
            source_slug="weworkremotely",
            source_name="We Work Remotely",
            raw_records=[{"id": record.opportunity_id}],
            normalized_records=[record],
        )


def services(
    tmp_path: Path,
) -> tuple[
    QuestCandidateApplicationService,
    OpportunityScoutApplicationService,
    SQLiteConnectionFactory,
]:
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
        connector_registry={"wwr_rss": AssessmentFixtureConnector},
    )
    return candidate_service, scout, factory


def test_scout_assessment_survives_restart(tmp_path: Path) -> None:
    _, scout, factory = services(tmp_path)

    report = scout.discover(limit=1, source_ids=["weworkremotely"])
    candidate = report["candidates"][0]

    assert candidate["assessment"]["status"] == "ASSESSED"
    assert candidate["assessment"]["ology"]["primary_domain"] == (
        "frontend_development"
    )
    assert candidate["assessment"]["risk"]["operator_review_required"] is True
    assert candidate["assessment"]["external_action_performed"] is False

    restarted_service = QuestCandidateApplicationService(
        SQLiteQuestCandidateRepository(factory),
        catalog_path=ROOT / "config" / "aigc_work_source_gate_catalog.json",
        schema_path=ROOT / "schemas" / "quest_candidate.schema.json",
        exact_revision="TEST-REVISION",
    )
    recovered = restarted_service.get_candidate(candidate["candidate_id"])

    assert recovered is not None
    assert recovered.payload["assessment"] == candidate["assessment"]
    assert recovered.payload["status"] == "DISCOVERED"


def test_manual_candidate_is_persisted_as_unassessed(tmp_path: Path) -> None:
    candidate_service, _, _ = services(tmp_path)

    stored = candidate_service.ingest(
        {
            "candidate_id": "cand_manual_unassessed_001",
            "source_id": "upwork",
            "source_url": "https://www.upwork.com/jobs/manual-example",
            "title": "Manual example",
            "description": "Manually entered opportunity for operator review.",
            "domain": "software_development",
            "required_skills": ["python"],
            "budget_range": None,
            "deadline_days": None,
            "deadline_at": None,
            "risk_class": "unassessed",
            "rights_status": "manual_operator_entry",
            "ingestion_channel": "manual",
        }
    )

    assert stored.payload["assessment"] is None
    assert stored.payload["risk_class"] == "unassessed"


def test_manual_candidate_cannot_inject_trusted_assessment(tmp_path: Path) -> None:
    candidate_service, scout, _ = services(tmp_path)
    trusted = scout.discover(
        limit=1,
        source_ids=["weworkremotely"],
    )["candidates"][0]["assessment"]

    with pytest.raises(WorkSourcePolicyError):
        candidate_service.ingest(
            {
                "candidate_id": "cand_manual_injection_001",
                "source_id": "upwork",
                "source_url": "https://www.upwork.com/jobs/injection-example",
                "title": "Manual assessment injection",
                "description": "Attempt to inject trusted assessor output.",
                "domain": "software_development",
                "required_skills": [],
                "budget_range": None,
                "deadline_days": None,
                "deadline_at": None,
                "risk_class": "low",
                "rights_status": "manual_operator_entry",
                "ingestion_channel": "manual",
                "assessment": trusted,
            }
        )
