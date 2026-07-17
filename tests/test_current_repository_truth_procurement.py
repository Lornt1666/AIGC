from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.core.current_repository_truth_procurement import (
    DEFAULT_CONFIG_PATH,
    NON_BLOCKING_SUPPORT_TARGETS,
    TruthProcurementError,
    build_receipt,
    evaluate_completion_request,
    first_incomplete_transition,
    load_procurement,
    validate_semantics,
)


def _payload() -> dict:
    return load_procurement(DEFAULT_CONFIG_PATH)


def test_current_procurement_contract_and_semantics_pass() -> None:
    payload = _payload()
    assert payload["contract_id"] == "AIGC-CURRENT-REPOSITORY-TRUTH-PROCUREMENT-001"
    assert len(payload["transition_targets"]) == 11
    assert len(payload["safety_invariants"]) == 8


def test_first_incomplete_transition_is_hosted_ci_recovery() -> None:
    transition = first_incomplete_transition(_payload())
    assert transition is not None
    assert transition["truth_id"] == "T1_HOSTED_VALIDATION_SUCCESSFUL"
    assert transition["status"] == "blocked"
    assert transition["external_mutation_required"] is True


def test_receipt_preserves_safety_and_identifies_next_actor() -> None:
    receipt = build_receipt(_payload())
    assert receipt.next_transition_id == "T1_HOSTED_VALIDATION_SUCCESSFUL"
    assert receipt.next_accountable_actor == "GITHUB_ACCOUNT_ADMIN_AND_ACCOUNTABLE_OPERATOR"
    assert receipt.parallel_ready_transition_ids == []
    assert receipt.safety_invariants_preserved is True
    assert receipt.automatic_merge_allowed is False
    assert receipt.automatic_external_commitment_allowed is False
    assert receipt.external_action_performed is False


def test_pr129_coordination_admission_does_not_block_pr121_deployment_path() -> None:
    payload = deepcopy(_payload())
    for item in payload["transition_targets"][:3]:
        item["current_value"] = True
        item["status"] = "completed"
    payload["current_summary"]["completed_transition_count"] = 3
    payload["current_summary"]["next_transition_id"] = (
        "T5_PR_121_RECONSTRUCTED_AND_ADMITTED"
    )

    transition = first_incomplete_transition(payload)
    receipt = build_receipt(payload)

    assert "T4_PR_129_REBOUND_VALIDATED_AND_ADMITTED" in NON_BLOCKING_SUPPORT_TARGETS
    assert transition is not None
    assert transition["truth_id"] == "T5_PR_121_RECONSTRUCTED_AND_ADMITTED"
    assert receipt.parallel_ready_transition_ids == [
        "T4_PR_129_REBOUND_VALIDATED_AND_ADMITTED"
    ]


def test_false_safety_invariants_are_not_treated_as_completion_targets() -> None:
    payload = _payload()
    transition_ids = {item["truth_id"] for item in payload["transition_targets"]}
    invariant_ids = {item["truth_id"] for item in payload["safety_invariants"]}
    assert transition_ids.isdisjoint(invariant_ids)
    assert all(item["current_value"] is False for item in payload["safety_invariants"])
    assert all(item["required_value"] is False for item in payload["safety_invariants"])


def test_completion_request_fails_without_dependencies_evidence_and_attestation() -> None:
    evaluation = evaluate_completion_request(
        _payload(),
        "T3_PR_123_ADMITTED",
        evidence_ids=(),
        operator_attested=False,
    )
    assert evaluation.ready is False
    assert evaluation.missing_dependencies == ["T2_ISSUE_124_RESOLVED"]
    assert evaluation.evidence_count == 0
    assert evaluation.operator_attested is False
    assert evaluation.external_action_performed is False


def test_hosted_ci_completion_request_requires_unique_evidence_slots() -> None:
    payload = _payload()
    target = payload["transition_targets"][0]
    required_count = len(target["required_evidence"])
    evaluation = evaluate_completion_request(
        payload,
        target["truth_id"],
        evidence_ids=["duplicate-evidence"] * required_count,
        operator_attested=True,
    )
    assert evaluation.ready is False
    assert evaluation.evidence_count == 1
    assert evaluation.required_evidence_count == required_count
    assert "Insufficient unique evidence references" in " ".join(evaluation.reasons)


def test_transition_order_must_be_contiguous() -> None:
    payload = deepcopy(_payload())
    payload["transition_targets"][1]["order"] = 9
    with pytest.raises(TruthProcurementError, match="contiguous"):
        validate_semantics(payload)


def test_forward_dependency_is_rejected() -> None:
    payload = deepcopy(_payload())
    payload["transition_targets"][0]["dependencies"] = [
        "T2_ISSUE_124_RESOLVED"
    ]
    with pytest.raises(TruthProcurementError, match="forward or self"):
        validate_semantics(payload)


def test_completed_status_cannot_be_claimed_while_false() -> None:
    payload = deepcopy(_payload())
    payload["transition_targets"][0]["status"] = "completed"
    with pytest.raises(TruthProcurementError, match="current_value=true"):
        validate_semantics(payload)


def test_safety_invariant_cannot_be_flipped_true() -> None:
    payload = deepcopy(_payload())
    payload["safety_invariants"][0]["current_value"] = True
    with pytest.raises(TruthProcurementError, match="must currently remain false"):
        validate_semantics(payload)


def test_summary_must_identify_actual_first_incomplete_transition() -> None:
    payload = deepcopy(_payload())
    payload["current_summary"]["next_transition_id"] = "T6_CLOUD_RUN_RUNTIME_IMPLEMENTED"
    with pytest.raises(TruthProcurementError, match="next transition"):
        validate_semantics(payload)


def test_procurement_artifact_cannot_claim_external_action() -> None:
    payload = deepcopy(_payload())
    payload["current_summary"]["external_action_performed"] = True
    with pytest.raises(TruthProcurementError, match="cannot claim external action"):
        validate_semantics(payload)


def test_default_config_path_is_repository_local() -> None:
    assert isinstance(DEFAULT_CONFIG_PATH, Path)
    assert DEFAULT_CONFIG_PATH.name == "current_repository_truth_procurement.json"
