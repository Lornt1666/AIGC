from __future__ import annotations

from copy import deepcopy

import pytest

from src.core.canonical_deployment_sequence import (
    CanonicalSequenceError,
    build_sequence_receipt,
    load_sequence,
    validate_sequence,
)


def test_canonical_sequence_validates_and_points_to_ci_recovery() -> None:
    sequence = load_sequence()

    assert sequence["contract_id"] == (
        "AIGC-CANONICAL-DEPLOYMENT-AUTONOMY-SEQUENCE-001"
    )
    assert sequence["next_admissible_action"]["stage_id"] == (
        "S1_HOSTED_CI_RECOVERY"
    )
    assert sequence["current_truth"]["external_action_performed"] is False


def test_canary_a_precedes_canary_b() -> None:
    sequence = load_sequence()
    orders = {
        stage["stage_id"]: stage["order"]
        for stage in sequence["critical_path"]
    }

    assert orders[sequence["canaries"]["canary_a"]["stage_id"]] < orders[
        sequence["canaries"]["canary_b"]["stage_id"]
    ]


def test_receipt_is_deterministic_and_fail_closed() -> None:
    sequence = load_sequence()

    first = build_sequence_receipt(sequence)
    second = build_sequence_receipt(sequence)

    assert first == second
    assert first["current_stage_id"] == "S1_HOSTED_CI_RECOVERY"
    assert first["automatic_merge_allowed"] is False
    assert first["automatic_external_commitment_allowed"] is False
    assert first["external_action_performed"] is False


def test_rejects_canary_b_before_canary_a() -> None:
    sequence = deepcopy(load_sequence())
    by_id = {
        stage["stage_id"]: stage
        for stage in sequence["critical_path"]
    }
    by_id["S6_CANARY_A_PLATFORM_PROOF"]["order"] = 8
    by_id["S8_CANARY_B_EMPLOYER_DUTY_AUTONOMY"]["order"] = 6

    with pytest.raises(CanonicalSequenceError):
        validate_sequence(sequence)


def test_rejects_forward_dependency() -> None:
    sequence = deepcopy(load_sequence())
    by_id = {
        stage["stage_id"]: stage
        for stage in sequence["critical_path"]
    }
    by_id["S2_PR123_MAINLINE_ADMISSION"]["depends_on"] = [
        "S4_CLOUD_RUN_STAGING_RUNTIME"
    ]

    with pytest.raises(CanonicalSequenceError, match="must appear earlier"):
        validate_sequence(sequence)


def test_rejects_automatic_external_commitment() -> None:
    sequence = deepcopy(load_sequence())
    sequence["authority"]["automatic_external_commitment_allowed"] = True

    with pytest.raises(CanonicalSequenceError, match="must remain false"):
        validate_sequence(sequence)


def test_rejects_unreviewed_automatic_authority_not_on_allowlist() -> None:
    sequence = deepcopy(load_sequence())
    sequence["authority"]["matrix"].append(
        {
            "action": "send_employer_communication",
            "automatic": True,
            "separate_approval_required": False,
        }
    )

    with pytest.raises(CanonicalSequenceError, match="not allowlisted"):
        validate_sequence(sequence)


def test_rejects_next_action_that_skips_first_blocked_stage() -> None:
    sequence = deepcopy(load_sequence())
    sequence["next_admissible_action"]["stage_id"] = (
        "S4_CLOUD_RUN_STAGING_RUNTIME"
    )

    with pytest.raises(CanonicalSequenceError, match="first incomplete stage"):
        validate_sequence(sequence)
