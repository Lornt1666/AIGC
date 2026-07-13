from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "schemas" / "quest_candidate.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def example() -> dict:
    return {
        "candidate_id": "cand_001example",
        "source_id": "upwork",
        "source_url": "https://www.upwork.com/jobs/example",
        "source_name": "Upwork",
        "source_category": "freelance_marketplaces",
        "platform_role": "opportunity_source",
        "title": "Build a React dashboard with Tailwind",
        "description": "Build a governed dashboard.",
        "proposed_quest_title": "React Dashboard Development",
        "domain": "software_development",
        "required_skills": ["react", "tailwind", "typescript"],
        "budget_range": {"min": 800, "max": 1500, "currency": "USD"},
        "compensation_text": None,
        "deadline_days": 14,
        "deadline_at": None,
        "location": None,
        "remote_status": "remote",
        "issuer": None,
        "risk_class": "low",
        "rights_status": "public_posting",
        "ingestion_channel": "manual",
        "source_access_mode": "manual_entry_or_approved_account_connector_only",
        "source_connector_status": "account_sensitive",
        "source_policy_snapshot": {
            "terms_review_target": "official terms",
            "api_or_feed": "official API only if approved",
            "discovery_mode": "manual_only",
            "external_action_mode": "operator authorization required",
        },
        "provenance": {
            "normalized_by": "QuestCandidateApplicationService",
            "catalog_version": "2.0.0",
            "input_digest": "a" * 64,
            "observed_at": "2026-07-13T16:33:00+00:00",
        },
        "ingested_at": "2026-07-13T16:33:00+00:00",
        "status": "DISCOVERED",
        "qualification": None,
        "external_action_performed": False,
    }


def test_discovered_candidate_contract_is_valid() -> None:
    VALIDATOR.validate(example())


def test_external_action_cannot_be_recorded_as_true() -> None:
    candidate = example()
    candidate["external_action_performed"] = True
    errors = list(VALIDATOR.iter_errors(candidate))
    assert errors


def test_qualified_candidate_requires_qualification_record() -> None:
    candidate = example()
    candidate["status"] = "QUALIFIED"
    errors = list(VALIDATOR.iter_errors(candidate))
    assert errors


def test_unknown_fields_are_rejected() -> None:
    candidate = deepcopy(example())
    candidate["unexpected"] = "not allowed"
    errors = list(VALIDATOR.iter_errors(candidate))
    assert errors
