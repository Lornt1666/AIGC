from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from src.core.github_actions_account_remediation import (
    GitHubActionsRemediationError,
    REQUIRED_WORKFLOW_STEPS,
    build_account_remediation_receipt,
    verify_hosted_recovery_observation,
)


HEAD = "a" * 40
MERGE_SHA = "b" * 40
TOOLING = "d" * 40
TOOLING_BRANCH = "agent/github-actions-account-remediation-v1"
NOW = datetime(2026, 7, 16, 2, 0, tzinfo=timezone.utc)
RUN_ID = 987654321


def remediation_receipt() -> dict[str, object]:
    return build_account_remediation_receipt(
        exact_head=HEAD,
        tooling_revision=TOOLING,
        tooling_branch=TOOLING_BRANCH,
        target_is_ancestor_of_tooling_revision=True,
        operator_name="Justice Gray Maciocha",
        observed_banner="GitHub Actions was blocked by the private-repository spending limit.",
        restriction_category="SPENDING_LIMIT",
        remediation_summary="Raised the Actions spending limit and retained the prior controls.",
        billing_ui_evidence_reference="Private GitHub billing screenshot reference GAR-001.",
        remediation_completed_at=NOW - timedelta(minutes=30),
        hosted_rerun_id=RUN_ID,
        created_at=NOW - timedelta(minutes=29),
    )


def pull_request() -> dict[str, object]:
    return {
        "number": 123,
        "state": "open",
        "merge_commit_sha": MERGE_SHA,
        "head": {
            "sha": HEAD,
            "ref": "agent/ci-action-pinning-v2",
        },
    }


def workflow_run() -> dict[str, object]:
    return {
        "id": RUN_ID,
        "name": "AIGC CI",
        "event": "pull_request",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "agent/ci-action-pinning-v2",
        "head_sha": MERGE_SHA,
        "created_at": (NOW - timedelta(minutes=20)).isoformat(),
        "run_started_at": (NOW - timedelta(minutes=20)).isoformat(),
        "updated_at": (NOW - timedelta(minutes=10)).isoformat(),
        "pull_requests": [
            {
                "number": 123,
                "head": {
                    "sha": HEAD,
                    "ref": "agent/ci-action-pinning-v2",
                },
            }
        ],
    }


def workflow_jobs() -> dict[str, object]:
    return {
        "jobs": [
            {
                "id": 1234,
                "name": "validate",
                "status": "completed",
                "conclusion": "success",
                "steps": [
                    {
                        "name": name,
                        "status": "completed",
                        "conclusion": "success",
                    }
                    for name in REQUIRED_WORKFLOW_STEPS
                ],
            }
        ]
    }


def workflow_artifacts() -> dict[str, object]:
    return {
        "artifacts": [
            {
                "id": 1,
                "name": "provider-discovery-simulation-merge-sha",
                "expired": False,
                "workflow_run": {"id": RUN_ID},
            },
            {
                "id": 2,
                "name": "terraform-validation-merge-sha",
                "expired": False,
                "workflow_run": {"id": RUN_ID},
            },
            {
                "id": 3,
                "name": "test-results-merge-sha",
                "expired": False,
                "workflow_run": {"id": RUN_ID},
            },
            {
                "id": 4,
                "name": "production-readiness-merge-sha",
                "expired": False,
                "workflow_run": {"id": RUN_ID},
            },
        ]
    }


def verify(**overrides: object) -> dict[str, object]:
    values = {
        "remediation_receipt": remediation_receipt(),
        "pull_request": pull_request(),
        "workflow_run": workflow_run(),
        "workflow_jobs": workflow_jobs(),
        "workflow_artifacts": workflow_artifacts(),
        "expected_head": HEAD,
        "verification_tooling_revision": TOOLING,
        "verification_tooling_branch": TOOLING_BRANCH,
        "target_is_ancestor_of_verification_tooling_revision": True,
        "evaluated_at": NOW,
    }
    values.update(overrides)
    return verify_hosted_recovery_observation(**values)  # type: ignore[arg-type]


def test_successful_hosted_recovery_is_evidence_only_and_non_authorizing() -> None:
    receipt = verify()

    assert receipt["contract_id"] == "AIGC-GITHUB-ACTIONS-HOSTED-RECOVERY-VERIFICATION-001"
    assert receipt["contract_version"] == "1.1.0"
    assert receipt["receipt_id"].startswith("GHR-")
    assert receipt["workflow_run_id"] == RUN_ID
    assert receipt["workflow_conclusion"] == "success"
    assert receipt["exact_head"] == HEAD
    assert receipt["verification_tooling_revision"] == TOOLING
    assert receipt["verification_tooling_branch"] == TOOLING_BRANCH
    assert receipt["target_is_ancestor_of_verification_tooling_revision"] is True
    assert receipt["current_pr_head_matches_expected"] is True
    assert receipt["run_pr_binding_observed"] is True
    assert receipt["checkout_executed"] is True
    assert receipt["steps_executed"] is True
    assert receipt["provider_discovery_artifact_present"] is True
    assert receipt["terraform_artifact_present"] is True
    assert receipt["test_artifact_present"] is True
    assert receipt["readiness_artifact_present"] is True
    assert receipt["github_api_read_performed"] is True
    assert receipt["github_api_mutation_performed"] is False
    assert receipt["merge_authorized"] is False
    assert receipt["terraform_apply_authorized"] is False
    assert receipt["provider_mutation_authorized"] is False
    assert receipt["external_action_performed"] is False


def test_zero_step_run_fails_closed() -> None:
    jobs = workflow_jobs()
    jobs["jobs"][0]["steps"] = []  # type: ignore[index]

    with pytest.raises(GitHubActionsRemediationError, match="no executed steps"):
        verify(workflow_jobs=jobs)


def test_missing_required_artifact_fails_closed() -> None:
    artifacts = workflow_artifacts()
    artifacts["artifacts"] = [
        item
        for item in artifacts["artifacts"]  # type: ignore[index]
        if not str(item["name"]).startswith("production-readiness-")
    ]

    with pytest.raises(GitHubActionsRemediationError, match="artifacts are missing"):
        verify(workflow_artifacts=artifacts)


def test_run_before_remediation_fails_closed() -> None:
    run = workflow_run()
    run["created_at"] = (NOW - timedelta(hours=2)).isoformat()
    run["run_started_at"] = (NOW - timedelta(hours=2)).isoformat()
    run["updated_at"] = (NOW - timedelta(hours=1, minutes=50)).isoformat()

    with pytest.raises(GitHubActionsRemediationError, match="before the account remediation"):
        verify(workflow_run=run)


def test_failed_required_step_fails_closed() -> None:
    jobs = workflow_jobs()
    steps = jobs["jobs"][0]["steps"]  # type: ignore[index]
    failed = next(item for item in steps if item["name"] == "Run tests")
    failed["conclusion"] = "failure"

    with pytest.raises(GitHubActionsRemediationError, match="did not succeed: Run tests"):
        verify(workflow_jobs=jobs)


def test_current_head_drift_fails_closed() -> None:
    pr = deepcopy(pull_request())
    pr["head"]["sha"] = "c" * 40  # type: ignore[index]

    with pytest.raises(GitHubActionsRemediationError, match="no longer matches"):
        verify(pull_request=pr)


def test_signed_rerun_id_mismatch_fails_closed() -> None:
    run = workflow_run()
    run["id"] = RUN_ID + 1

    with pytest.raises(GitHubActionsRemediationError, match="GAR-signed rerun ID"):
        verify(workflow_run=run)


def test_unproven_verifier_tooling_ancestry_fails_closed() -> None:
    with pytest.raises(GitHubActionsRemediationError, match="must be an ancestor"):
        verify(target_is_ancestor_of_verification_tooling_revision=False)
