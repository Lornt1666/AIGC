from __future__ import annotations

from copy import deepcopy

from scripts.collect_github_actions_preflight import classify_live_snapshot
from src.core.contract_validator import validate_file


def _status(description: str = "All Systems Operational") -> dict:
    return {"status": {"description": description}}


def test_committed_zero_step_diagnosis_matches_contract() -> None:
    result = validate_file(
        "github_actions_zero_step_diagnosis",
        "config/github_actions_zero_step_diagnosis.json",
    )
    assert result.valid is True
    assert result.record_count == 1


def test_shell_only_zero_step_operational_status_is_runner_eligibility_block() -> None:
    result = classify_live_snapshot(
        permissions={"enabled": True, "allowed_actions": "all"},
        selected_actions={"http_status": 409},
        job={"steps": []},
        annotations={"value": []},
        status=_status(),
    )
    assert result["classification"] == (
        "HOSTED_RUNNER_NOT_ALLOCATED_ACCOUNT_OR_REPOSITORY_ELIGIBILITY_BLOCK"
    )
    assert result["confidence"] == "high"
    assert result["step_count"] == 0
    assert result["external_action_performed"] is False


def test_disabled_repository_actions_is_detected_before_other_hypotheses() -> None:
    result = classify_live_snapshot(
        permissions={"enabled": False, "allowed_actions": "all"},
        selected_actions={},
        job={"steps": []},
        annotations={"value": []},
        status=_status(),
    )
    assert result["classification"] == "REPOSITORY_ACTIONS_DISABLED"


def test_billing_annotation_is_high_confidence() -> None:
    result = classify_live_snapshot(
        permissions={"enabled": True, "allowed_actions": "all"},
        selected_actions={},
        job={"steps": []},
        annotations={
            "value": [
                {
                    "title": "Job not started",
                    "message": "Actions usage is blocked by a billing or spending limit.",
                }
            ]
        },
        status=_status(),
    )
    assert result["classification"] == "ACCOUNT_BILLING_OR_USAGE_BLOCK"
    assert result["annotation_text_present"] is True


def test_policy_annotation_is_detected() -> None:
    result = classify_live_snapshot(
        permissions={"enabled": True, "allowed_actions": "selected"},
        selected_actions={"http_status": 200},
        job={"steps": []},
        annotations={
            "value": [
                {
                    "message": "This action is not allowed by repository policy."
                }
            ]
        },
        status=_status(),
    )
    assert result["classification"] == "ACTIONS_POLICY_BLOCK"


def test_nonempty_steps_prove_runner_execution() -> None:
    result = classify_live_snapshot(
        permissions={"enabled": True, "allowed_actions": "all"},
        selected_actions={},
        job={
            "steps": [
                {
                    "name": "Set up job",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        },
        annotations={"value": []},
        status=_status(),
    )
    assert result["classification"] == "WORKFLOW_EXECUTION_REACHED_RUNNER"
    assert result["step_count"] == 1


def test_annotation_classification_does_not_mutate_input() -> None:
    annotations = {"value": [{"message": "payment method required"}]}
    original = deepcopy(annotations)
    classify_live_snapshot(
        permissions={"enabled": True, "allowed_actions": "all"},
        selected_actions={},
        job={"steps": []},
        annotations=annotations,
        status=_status(),
    )
    assert annotations == original
