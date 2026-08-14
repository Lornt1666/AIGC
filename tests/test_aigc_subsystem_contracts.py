from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.core.nexus.subsystem_contracts import (
    HEXGATE_GATES,
    SubsystemContractError,
    build_local_validation_receipt,
    evaluate_chorus,
    evaluate_correlation_station,
    evaluate_hexgate,
    evaluate_silva,
    evaluate_vanis,
    load_contract_set,
    validate_contract_set,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "aigc_subsystem_contracts.v1.json"
SCHEMA = ROOT / "schemas" / "aigc_subsystem_contracts.schema.json"
RECEIPT = ROOT / "reports" / "artifacts" / "aigc_subsystem_contracts_local_validation.json"
RECEIPT_SCHEMA = ROOT / "schemas" / "aigc_subsystem_validation_receipt.schema.json"


def contract_set() -> dict:
    return load_contract_set(CONFIG, SCHEMA)


def test_contract_set_and_receipt_are_complete_and_zero_egress() -> None:
    receipt = build_local_validation_receipt(contract_set())
    assert receipt["terminal_status"] == "PASS"
    assert set(receipt["subsystem_results"]) == {
        "silva", "hexgate", "vanis", "correlation_station", "chorus"
    }
    assert receipt["provider_calls_performed"] == 0
    assert receipt["authority_granted"] is False
    assert receipt["external_action_performed"] is False
    assert receipt["receipt_id"].startswith("SUBSYS-")
    assert len(receipt["receipt_sha256"]) == 64


def test_committed_receipt_matches_fresh_deterministic_evaluation() -> None:
    committed = json.loads(RECEIPT.read_text(encoding="utf-8"))
    schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(committed)
    assert committed == build_local_validation_receipt(contract_set())


def test_contract_set_cannot_self_authorize() -> None:
    changed = copy.deepcopy(contract_set())
    changed["subsystems"][0]["authority_granted"] = True
    with pytest.raises(SubsystemContractError, match="cannot grant authority"):
        validate_contract_set(changed)


def test_silva_blocks_unverified_required_platform() -> None:
    result = evaluate_silva([{"platform": "ios", "required": True, "status": "UNVERIFIED"}])
    assert result["terminal_status"] == "BLOCKED"
    assert result["failed_required_platforms"] == ["ios"]


def test_hexgate_is_exact_and_deny_by_default() -> None:
    gates = {key: True for key in HEXGATE_GATES}
    gates["authorization"] = False
    result = evaluate_hexgate(gates)
    assert result["terminal_status"] == "BLOCKED_PERMISSION"
    assert result["simulation_admitted"] is False
    with pytest.raises(SubsystemContractError, match="exactly six"):
        evaluate_hexgate({"authorization": True})


def test_vanis_blocks_unlisted_or_over_budget_routes_without_dispatch() -> None:
    result = evaluate_vanis(
        {
            "provider": "unknown",
            "capability": "write",
            "provider_allowlisted": False,
            "capability_allowlisted": False,
            "estimated_cost": 2,
            "budget_ceiling": 1,
        }
    )
    assert result["terminal_status"] == "BLOCKED"
    assert result["blockers"] == [
        "provider_not_allowlisted", "capability_not_allowlisted", "budget_exceeded"
    ]
    assert result["provider_dispatch_performed"] is False


def test_correlation_station_rejects_forward_or_authority_edges() -> None:
    with pytest.raises(SubsystemContractError, match="earlier events"):
        evaluate_correlation_station(
            [{"id": "child", "parent_ids": ["missing"], "authority_granted": False}]
        )
    with pytest.raises(SubsystemContractError, match="cannot grant authority"):
        evaluate_correlation_station(
            [{"id": "evidence", "parent_ids": [], "authority_granted": True}]
        )


def test_chorus_never_infers_consequential_consent() -> None:
    result = evaluate_chorus(
        {"summary": "Deploy the candidate.", "consequential": True, "approval_presented": True}
    )
    assert result["terminal_status"] == "AWAITING_HUMAN_APPROVAL"
    assert result["execution_allowed"] is False
    assert result["consent_inferred"] is False
    assert result["authority_granted"] is False
