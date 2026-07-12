from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.core.jobs.lifecycle_contract import (
    JobLifecycleContractError,
    analyze_compatibility_map,
    analyze_lifecycle_contract,
    build_reconciliation_report,
    require_structurally_valid,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "governance" / "jobs" / "canonical_job_lifecycle_v1.json"
MAP_PATH = ROOT / "governance" / "jobs" / "job_state_compatibility_map_v1.json"
CONTRACT_SCHEMA_PATH = (
    ROOT / "governance" / "schemas" / "jobs" / "job_lifecycle_contract.schema.json"
)
MAP_SCHEMA_PATH = (
    ROOT / "governance" / "schemas" / "jobs" / "job_state_compatibility_map.schema.json"
)
SOURCE_REVISION = "293de53489fe7212fad272c01c698c0ffe2da610"


def load(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def validate(schema_path: Path, payload: dict[str, object]) -> None:
    schema = load(schema_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_canonical_contract_and_compatibility_map_validate() -> None:
    contract = load(CONTRACT_PATH)
    compatibility_map = load(MAP_PATH)

    validate(CONTRACT_SCHEMA_PATH, contract)
    validate(MAP_SCHEMA_PATH, compatibility_map)
    require_structurally_valid(contract, compatibility_map)


def test_contract_disambiguates_work_acceptance_from_delivery_acceptance() -> None:
    contract = load(CONTRACT_PATH)
    states = {str(item["state_id"]) for item in contract["states"]}  # type: ignore[index]

    assert "ACCEPTED" not in states
    assert "WORK_ACCEPTED" in states
    assert "ACCEPTED_FOR_DELIVERY" in states

    transitions = {
        str(item["transition_id"]): item for item in contract["transitions"]  # type: ignore[index]
    }
    assert transitions["ACCEPT_WORK_COMMITMENT"]["to_state"] == "WORK_ACCEPTED"
    assert transitions["ACCEPT_FOR_DELIVERY"]["to_state"] == "ACCEPTED_FOR_DELIVERY"
    assert transitions["ACCEPT_WORK_COMMITMENT"]["authority_class"] == "OPERATOR_JOB_ACCEPTANCE"
    assert transitions["ACCEPT_FOR_DELIVERY"]["authority_class"] == "OPERATOR_WORK_REVIEW"


def test_delivery_is_recorded_only_with_separate_execution_receipt() -> None:
    contract = load(CONTRACT_PATH)
    delivery = next(
        item
        for item in contract["transitions"]  # type: ignore[index]
        if item["to_state"] == "DELIVERED"
    )

    assert delivery["action_effect"] == "INTERNAL_STATE_CHANGE"
    assert delivery["external_action_boundary"] == "SEPARATE_CONNECTOR_RECEIPT_REQUIRED"
    assert "DELIVERY_EXECUTION_RECEIPT" in delivery["evidence_required"]
    assert contract["external_action_performed"] is False


def test_reconciliation_report_blocks_runtime_integration_until_operator_resolution() -> None:
    contract = load(CONTRACT_PATH)
    compatibility_map = load(MAP_PATH)

    report = build_reconciliation_report(
        contract,
        compatibility_map,
        source_revision=SOURCE_REVISION,
    )

    assert report["structural_findings"] == []
    assert report["compatibility_findings"] == []
    assert report["blocking_conflict_count"] == 1
    assert report["ready_for_runtime_integration"] is False
    assert report["operator_review_required"] is True
    assert report["external_action_performed"] is False


def test_pr64_states_are_all_explicitly_mapped() -> None:
    compatibility_map = load(MAP_PATH)
    source = next(
        item
        for item in compatibility_map["source_contracts"]  # type: ignore[index]
        if item["source_contract_id"] == "PR64-GOVERNED-JOB-STATE-MACHINE"
    )
    mapped = {str(item["source_state"]) for item in source["mappings"]}

    assert mapped == {
        "PROPOSED",
        "RESEARCHING",
        "READY_FOR_REVIEW",
        "ACCEPTED",
        "REJECTED",
        "DELIVERED",
        "CANCELLED",
    }


def test_generic_accepted_state_is_rejected_as_ambiguous() -> None:
    contract = load(CONTRACT_PATH)
    mutated = deepcopy(contract)
    mutated["states"].append(  # type: ignore[index]
        {
            "state_id": "ACCEPTED",
            "label": "Accepted",
            "meaning": "Ambiguous acceptance.",
            "lifecycle_scope": "EXECUTION",
            "initial": False,
            "terminal": False,
        }
    )

    assert "AMBIGUOUS_GENERIC_ACCEPTED_STATE" in analyze_lifecycle_contract(mutated)


def test_duplicate_state_and_terminal_outbound_transition_fail_closed() -> None:
    contract = load(CONTRACT_PATH)
    mutated = deepcopy(contract)
    mutated["states"].append(deepcopy(mutated["states"][0]))  # type: ignore[index]
    mutated["transitions"].append(  # type: ignore[index]
        {
            "transition_id": "REOPEN_CLOSED",
            "from_state": "CLOSED",
            "to_state": "RESEARCHING",
            "authority_class": "POLICY_AUTHORIZATION",
            "action_effect": "INTERNAL_STATE_CHANGE",
            "evidence_required": [],
            "reason_required": True,
            "rollback_class": "STATE_REVERSION",
            "external_action_boundary": "NONE",
        }
    )

    findings = analyze_lifecycle_contract(mutated)
    assert "DUPLICATE_STATE:DISCOVERED" in findings
    assert "TERMINAL_STATE_HAS_OUTBOUND:CLOSED" in findings

    with pytest.raises(JobLifecycleContractError):
        require_structurally_valid(mutated, load(MAP_PATH))


def test_unknown_compatibility_target_fails_closed() -> None:
    contract = load(CONTRACT_PATH)
    compatibility_map = load(MAP_PATH)
    mutated = deepcopy(compatibility_map)
    mutated["source_contracts"][0]["mappings"][0]["target_state"] = "NOT_A_STATE"  # type: ignore[index]

    findings = analyze_compatibility_map(contract, mutated)
    assert any(item.startswith("UNKNOWN_TARGET_STATE:") for item in findings)


def test_source_revision_is_required_for_reconciliation_receipt() -> None:
    with pytest.raises(JobLifecycleContractError, match="SOURCE_REVISION_REQUIRED"):
        build_reconciliation_report(load(CONTRACT_PATH), load(MAP_PATH), source_revision="short")
