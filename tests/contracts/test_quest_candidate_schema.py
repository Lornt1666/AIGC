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


def assessment() -> dict:
    return {
        "assessment_version": "1.0.0",
        "status": "ASSESSED",
        "basis_digest": "c" * 64,
        "ology": {
            "assessor_id": "AIGC-OLOGY-ASSESSOR-001",
            "assessor_version": "1.0.0",
            "primary_domain": "software_development",
            "discipline_taxonomy": ["api_documentation", "software_coding"],
            "detected_skills": ["python"],
            "detected_tools": ["openapi", "python", "swagger"],
            "required_skills": ["openapi", "python", "swagger"],
            "automation_signals": {
                "api_related": True,
                "coding_related": True,
            },
            "ai_use_signals": {
                "ai_allowed_explicit": False,
                "ai_forbidden_explicit": False,
                "ai_unclear": True,
                "disclosure_needed": True,
            },
        },
        "risk": {
            "assessor_id": "AIGC-RISK-SCOUT-001",
            "assessor_version": "1.0.0",
            "risk_class": "low",
            "radar_score": 88,
            "radar_decision": "queue_for_phase_3",
            "risk_flags": [],
            "forbidden_flags": [],
            "platform_policy_status": "green",
            "operator_review_required": True,
            "qualification_recommended": True,
        },
        "external_action_performed": False,
    }


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
        "assessment": None,
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


def qualified_candidate(*, quest_created: bool) -> dict:
    candidate = example()
    candidate["status"] = "QUALIFIED"
    candidate["qualification"] = {
        "decision": "QUALIFY",
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Suitable for governed Quest proposal creation.",
        "qualified_at": "2026-07-13T16:40:00+00:00",
        "quest_creation_authorized": True,
        "quest_created": quest_created,
        "quest_id": "quest_001example" if quest_created else None,
        "quest_created_at": (
            "2026-07-13T16:45:00+00:00" if quest_created else None
        ),
        "quest_request_digest": "b" * 64 if quest_created else None,
        "next_step": (
            "REQUEST_WORK_ACCEPTANCE"
            if quest_created
            else "CREATE_QUEST_UNDER_CANONICAL_LIFECYCLE"
        ),
    }
    return candidate


def test_discovered_manual_candidate_contract_is_valid() -> None:
    VALIDATOR.validate(example())


def test_assessed_scout_candidate_contract_is_valid() -> None:
    candidate = example()
    candidate["source_id"] = "weworkremotely"
    candidate["source_name"] = "We Work Remotely"
    candidate["ingestion_channel"] = "existing_read_only_adapter"
    candidate["assessment"] = assessment()
    VALIDATOR.validate(candidate)


def test_qualified_candidate_before_conversion_is_valid() -> None:
    VALIDATOR.validate(qualified_candidate(quest_created=False))


def test_converted_candidate_contract_is_valid() -> None:
    VALIDATOR.validate(qualified_candidate(quest_created=True))


def test_assessment_requires_operator_review() -> None:
    candidate = example()
    candidate["assessment"] = assessment()
    candidate["assessment"]["risk"]["operator_review_required"] = False
    assert list(VALIDATOR.iter_errors(candidate))


def test_assessment_cannot_record_external_action() -> None:
    candidate = example()
    candidate["assessment"] = assessment()
    candidate["assessment"]["external_action_performed"] = True
    assert list(VALIDATOR.iter_errors(candidate))


def test_external_action_cannot_be_recorded_as_true() -> None:
    candidate = example()
    candidate["external_action_performed"] = True
    assert list(VALIDATOR.iter_errors(candidate))


def test_qualified_candidate_requires_qualification_record() -> None:
    candidate = example()
    candidate["status"] = "QUALIFIED"
    assert list(VALIDATOR.iter_errors(candidate))


def test_created_candidate_requires_quest_evidence() -> None:
    candidate = qualified_candidate(quest_created=True)
    candidate["qualification"]["quest_id"] = None
    assert list(VALIDATOR.iter_errors(candidate))


def test_unknown_fields_are_rejected() -> None:
    candidate = deepcopy(example())
    candidate["unexpected"] = "not allowed"
    assert list(VALIDATOR.iter_errors(candidate))
