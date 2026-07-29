from __future__ import annotations

from src.core.canonical_deployment_sequence import load_sequence
from src.core.current_repository_truth_procurement import load_procurement


def test_truth_procurement_remains_bound_to_canonical_contract() -> None:
    sequence = load_sequence()
    procurement = load_procurement()
    assert procurement["canonical_sequence"]["contract_id"] == sequence["contract_id"]
    assert procurement["canonical_sequence"]["path"].endswith(
        "canonical_deployment_and_autonomy_sequence.json"
    )


def test_canonical_stage_order_is_reflected_in_truth_transitions() -> None:
    sequence = load_sequence()
    procurement = load_procurement()
    stage_ids = [
        stage["stage_id"]
        for stage in sorted(sequence["critical_path"], key=lambda item: item["order"])
    ]
    truth_ids = [
        item["truth_id"]
        for item in sorted(procurement["transition_targets"], key=lambda item: item["order"])
    ]
    assert stage_ids == [
        "S1_HOSTED_CI_RECOVERY",
        "S2_PR123_MAINLINE_ADMISSION",
        "S3_STAGING_AUTHORIZATION_RECONSTRUCTION",
        "S4_CLOUD_RUN_STAGING_RUNTIME",
        "S5_ISOLATED_STAGING_ACTIVATION",
        "S6_CANARY_A_PLATFORM_PROOF",
        "S7_PR122_RECONSTRUCTION",
        "S8_CANARY_B_EMPLOYER_DUTY_AUTONOMY",
        "S9_READ_ONLY_CONNECTOR_CANARY",
    ]
    assert truth_ids.index("T1_HOSTED_VALIDATION_SUCCESSFUL") < truth_ids.index(
        "T3_PR_123_ADMITTED"
    )
    assert truth_ids.index("T5_PR_121_RECONSTRUCTED_AND_ADMITTED") < truth_ids.index(
        "T6_CLOUD_RUN_RUNTIME_IMPLEMENTED"
    )
    assert truth_ids.index("T8_CANARY_A_PASSED") < truth_ids.index(
        "T10_CANARY_B_PASSED"
    )
    assert truth_ids[-1] == "T11_READ_ONLY_CONNECTOR_PROVEN"


def test_authority_rules_are_consistent_across_ledgers() -> None:
    sequence = load_sequence()
    procurement = load_procurement()
    authority = sequence["authority"]
    invariant_ids = {
        item["truth_id"] for item in procurement["safety_invariants"]
    }
    assert authority["automatic_merge_allowed"] is False
    assert authority["self_approval_allowed"] is False
    assert authority["automatic_external_commitment_allowed"] is False
    assert authority["external_action_performed"] is False
    assert "I2_SELF_APPROVAL_ALLOWED" in invariant_ids
    assert "I3_AUTOMATIC_MERGE_ALLOWED" in invariant_ids
    assert "I4_AUTOMATIC_EXTERNAL_COMMITMENT_ALLOWED" in invariant_ids
    assert "I7_COORDINATION_PR_EXTERNAL_ACTION_PERFORMED" in invariant_ids


def test_canary_b_remains_downstream_of_platform_proof() -> None:
    sequence = load_sequence()
    procurement = load_procurement()
    stages = {stage["stage_id"]: stage for stage in sequence["critical_path"]}
    transitions = {
        item["truth_id"]: item for item in procurement["transition_targets"]
    }
    assert stages["S8_CANARY_B_EMPLOYER_DUTY_AUTONOMY"]["depends_on"] == [
        "S7_PR122_RECONSTRUCTION"
    ]
    assert transitions["T10_CANARY_B_PASSED"]["dependencies"] == [
        "T9_PR_122_RECONSTRUCTED_WITH_ISSUE_128"
    ]
    assert transitions["T9_PR_122_RECONSTRUCTED_WITH_ISSUE_128"]["dependencies"] == [
        "T8_CANARY_A_PASSED"
    ]
