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
        "approval_request": None,
        "work_acceptance": None,
        "terminal_decision": None,
        "created_at": "2026-07-13T17:00:00+00:00",
        "updated_at": "2026-07-13T17:00:00+00:00",
        "external_action_performed": False,
    }


def approval_request() -> dict:
    return {
        "approval_request_id": "approval_example_001",
        "requested_at": "2026-07-13T17:05:00+00:00",
        "requested_by_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Review the bounded internal work commitment.",
        "source_state": "PROPOSED",
        "target_state": "WORK_ACCEPTED",
        "quest_revision": 2,
        "exact_revision": "b" * 40,
        "revision_binding_mode": "exact_source_revision",
        "transition_digest": "c" * 64,
        "request_digest": "d" * 64,
        "required_authorization": {
            "resource_id": "quest_example_001",
            "action": "accept_work",
            "scopes": ["quest:work_accept"],
            "purpose": "work_acceptance",
            "evidence_ids": [
                "AIGC-APPROVAL-REQUEST:approval_example_001",
                f"AIGC-TRANSITION-DIGEST:{'c' * 64}",
            ],
        },
        "status": "PENDING",
        "external_action_performed": False,
    }


def work_acceptance() -> dict:
    return {
        "decision": "WORK_ACCEPTED",
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Proceed with bounded internal work.",
        "accepted_at": "2026-07-13T17:10:00+00:00",
        "approval_request_id": "approval_example_001",
        "transition_digest": "c" * 64,
        "request_digest": "e" * 64,
        "authorization_receipt_id": "AUTHZ-REQ-WORK-ACCEPT:example",
        "authorization_decision_id": "AUTHZ-REQ-WORK-ACCEPT",
        "authorization_request_digest": "f" * 64,
        "authorization_exact_revision": "b" * 40,
        "principal_id": "principal-a",
        "source_state": "APPROVAL_REQUIRED",
        "target_state": "WORK_ACCEPTED",
        "external_action_performed": False,
    }


def test_proposed_quest_contract_is_valid() -> None:
    VALIDATOR.validate(example())


def test_approval_required_quest_contract_is_valid() -> None:
    quest = example()
    quest["lifecycle_state"] = "APPROVAL_REQUIRED"
    quest["approval_request"] = approval_request()
    VALIDATOR.validate(quest)


def test_work_accepted_quest_requires_consumed_receipt_bound_evidence() -> None:
    quest = example()
    quest["lifecycle_state"] = "WORK_ACCEPTED"
    quest["approval_request"] = approval_request()
    quest["approval_request"]["status"] = "CONSUMED"
    quest["work_acceptance"] = work_acceptance()
    VALIDATOR.validate(quest)

    missing_receipt = deepcopy(quest)
    missing_receipt["work_acceptance"].pop("authorization_receipt_id")
    assert list(VALIDATOR.iter_errors(missing_receipt))


def test_generic_accepted_is_not_a_canonical_state() -> None:
    quest = example()
    quest["lifecycle_state"] = "ACCEPTED"
    assert list(VALIDATOR.iter_errors(quest))


def test_delivery_acceptance_is_distinct_from_work_acceptance() -> None:
    quest = example()
    quest["lifecycle_state"] = "ACCEPTED_FOR_DELIVERY"
    assert list(VALIDATOR.iter_errors(quest)) == []
    assert quest["lifecycle_state"] != "WORK_ACCEPTED"


def test_approval_required_needs_pending_approval_request() -> None:
    quest = example()
    quest["lifecycle_state"] = "APPROVAL_REQUIRED"
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
