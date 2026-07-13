from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "schemas" / "quest.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(
    SCHEMA,
    format_checker=FormatChecker(),
)


def example() -> dict:
    return {
        "quest_id": "quest_example_001",
        "source_candidate_id": "cand_example_001",
        "title": "React Dashboard Development",
        "purpose": "Create a typed dashboard for internal operator review.",
        "scope": "Research, plan, and produce the requested work internally.",
        "non_scope": "No application, bid, message, delivery, or external action.",
        "owner_role": "ACCOUNTABLE_OPERATOR",
        "authority_class": "ACCOUNTABLE_OPERATOR",
        "risk_class": "low",
        "lifecycle_state": "PROPOSED",
        "lifecycle_contract_id": "AIGC-JOB-LIFECYCLE-001",
        "lifecycle_contract_version": "1.0.0",
        "acceptance_criteria": [
            "The output addresses the source posting requirements."
        ],
        "budget": {
            "min": 800,
            "max": 1500,
            "currency": "USD",
        },
        "deadline_at": "2026-07-27T16:00:00+00:00",
        "source_snapshot": {
            "source_id": "upwork",
            "source_name": "Upwork",
            "source_url": "https://www.upwork.com/jobs/example",
            "posting_title": "Build a React dashboard",
            "rights_status": "manual_operator_entry",
            "input_digest": "a" * 64,
        },
        "created_from_candidate_revision": 2,
        "created_at": "2026-07-13T17:00:00+00:00",
        "updated_at": "2026-07-13T17:00:00+00:00",
        "external_action_performed": False,
    }


def test_proposed_quest_contract_is_valid() -> None:
    VALIDATOR.validate(example())


def test_generic_accepted_is_not_a_canonical_state() -> None:
    quest = example()
    quest["lifecycle_state"] = "ACCEPTED"
    assert list(VALIDATOR.iter_errors(quest))


def test_external_action_cannot_be_true() -> None:
    quest = example()
    quest["external_action_performed"] = True
    assert list(VALIDATOR.iter_errors(quest))


def test_personal_owner_string_cannot_replace_authority_role() -> None:
    quest = example()
    quest["owner_role"] = "Justice"
    assert list(VALIDATOR.iter_errors(quest))


def test_unknown_fields_are_rejected() -> None:
    quest = deepcopy(example())
    quest["unexpected"] = True
    assert list(VALIDATOR.iter_errors(quest))
