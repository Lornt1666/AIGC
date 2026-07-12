from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.core.jobs.state_machine import (
    ACCEPTED,
    CANCELLED,
    DELIVERED,
    PROPOSED,
    READY_FOR_REVIEW,
    RESEARCHING,
    GovernedJobStateMachine,
    JobState,
    JobTransitionError,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "governance" / "schemas" / "jobs" / "job_transition_receipt.schema.json"
SOURCE_REVISION = "cac585217c347e3b66a6e13b89646fb38f672c9b"


def validate(receipt: dict[str, object]) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(receipt)


def approval_for(
    job: JobState,
    *,
    to_state: str,
    approval_class: str,
    approval_id: str,
    source_revision: str = SOURCE_REVISION,
    reason: str | None = None,
) -> dict[str, object]:
    digest = GovernedJobStateMachine.transition_digest(
        job,
        to_state=to_state,
        expected_revision=job.revision,
        source_revision=source_revision,
        reason=reason,
    )
    return {
        "approval_id": approval_id,
        "actor_id": "operator-justice",
        "approval_class": approval_class,
        "authorization_receipt_id": f"authz-{approval_id}",
        "job_id": job.job_id,
        "from_state": job.state,
        "to_state": to_state,
        "expected_revision": job.revision,
        "source_revision": source_revision,
        "transition_digest": digest,
        "status": "ACTIVE",
    }


def test_happy_path_requires_transition_bound_operator_approvals() -> None:
    job = JobState("job-a", PROPOSED, 1)

    job, first = GovernedJobStateMachine.transition(
        job,
        to_state=RESEARCHING,
        expected_revision=1,
        source_revision=SOURCE_REVISION,
    )
    job, second = GovernedJobStateMachine.transition(
        job,
        to_state=READY_FOR_REVIEW,
        expected_revision=2,
        source_revision=SOURCE_REVISION,
    )

    acceptance = approval_for(
        job,
        to_state=ACCEPTED,
        approval_class="JOB_ACCEPTANCE",
        approval_id="approval-a",
    )
    job, third = GovernedJobStateMachine.transition(
        job,
        to_state=ACCEPTED,
        expected_revision=3,
        source_revision=SOURCE_REVISION,
        operator_approval=acceptance,
    )

    delivery = approval_for(
        job,
        to_state=DELIVERED,
        approval_class="JOB_DELIVERY",
        approval_id="approval-b",
    )
    job, fourth = GovernedJobStateMachine.transition(
        job,
        to_state=DELIVERED,
        expected_revision=4,
        source_revision=SOURCE_REVISION,
        operator_approval=delivery,
    )

    assert job.state == DELIVERED
    assert job.revision == 5
    assert first.operator_approval_required is False
    assert second.operator_approval_required is False
    assert third.operator_approval_required is True
    assert fourth.operator_approval_required is True
    assert third.operator_approval == acceptance
    assert fourth.operator_approval == delivery
    for receipt in (first, second, third, fourth):
        assert receipt.external_action_performed is False
        assert receipt.source_revision == SOURCE_REVISION
        validate(receipt.as_dict())


def test_accept_without_operator_approval_fails_closed() -> None:
    job = JobState("job-a", READY_FOR_REVIEW, 7)

    with pytest.raises(JobTransitionError, match="OPERATOR_APPROVAL_REQUIRED"):
        GovernedJobStateMachine.transition(
            job,
            to_state=ACCEPTED,
            expected_revision=7,
            source_revision=SOURCE_REVISION,
        )


def test_stale_revision_and_illegal_transition_are_rejected() -> None:
    job = JobState("job-a", PROPOSED, 2)

    with pytest.raises(JobTransitionError, match="JOB_REVISION_CONFLICT"):
        GovernedJobStateMachine.transition(
            job,
            to_state=RESEARCHING,
            expected_revision=1,
            source_revision=SOURCE_REVISION,
        )

    with pytest.raises(JobTransitionError, match="ILLEGAL_JOB_TRANSITION"):
        GovernedJobStateMachine.transition(
            job,
            to_state=DELIVERED,
            expected_revision=2,
            source_revision=SOURCE_REVISION,
        )


def test_cancellation_requires_reason_and_terminal_state_cannot_transition() -> None:
    job = JobState("job-a", PROPOSED, 1)

    with pytest.raises(JobTransitionError, match="TRANSITION_REASON_REQUIRED"):
        GovernedJobStateMachine.transition(
            job,
            to_state=CANCELLED,
            expected_revision=1,
            source_revision=SOURCE_REVISION,
        )

    cancelled, receipt = GovernedJobStateMachine.transition(
        job,
        to_state=CANCELLED,
        expected_revision=1,
        source_revision=SOURCE_REVISION,
        reason="operator withdrew the local proposal",
    )
    validate(receipt.as_dict())

    with pytest.raises(JobTransitionError, match="JOB_TERMINAL_STATE"):
        GovernedJobStateMachine.transition(
            cancelled,
            to_state=RESEARCHING,
            expected_revision=2,
            source_revision=SOURCE_REVISION,
        )


def test_approval_class_and_transition_digest_must_match_exact_transition() -> None:
    job = JobState("job-a", READY_FOR_REVIEW, 3)
    approval = approval_for(
        job,
        to_state=ACCEPTED,
        approval_class="JOB_DELIVERY",
        approval_id="approval-wrong-class",
    )

    with pytest.raises(JobTransitionError, match="OPERATOR_APPROVAL_CLASS_MISMATCH"):
        GovernedJobStateMachine.transition(
            job,
            to_state=ACCEPTED,
            expected_revision=3,
            source_revision=SOURCE_REVISION,
            operator_approval=approval,
        )

    approval["approval_class"] = "JOB_ACCEPTANCE"
    approval["transition_digest"] = "0" * 64
    with pytest.raises(JobTransitionError, match="OPERATOR_APPROVAL_TRANSITION_DIGEST_MISMATCH"):
        GovernedJobStateMachine.transition(
            job,
            to_state=ACCEPTED,
            expected_revision=3,
            source_revision=SOURCE_REVISION,
            operator_approval=approval,
        )


def test_approval_cannot_be_replayed_across_job_or_source_revision() -> None:
    source_job = JobState("job-a", READY_FOR_REVIEW, 3)
    approval = approval_for(
        source_job,
        to_state=ACCEPTED,
        approval_class="JOB_ACCEPTANCE",
        approval_id="approval-a",
    )

    with pytest.raises(JobTransitionError, match="OPERATOR_APPROVAL_JOB_MISMATCH"):
        GovernedJobStateMachine.transition(
            JobState("job-b", READY_FOR_REVIEW, 3),
            to_state=ACCEPTED,
            expected_revision=3,
            source_revision=SOURCE_REVISION,
            operator_approval=approval,
        )

    with pytest.raises(JobTransitionError, match="OPERATOR_APPROVAL_SOURCE_REVISION_MISMATCH"):
        GovernedJobStateMachine.transition(
            source_job,
            to_state=ACCEPTED,
            expected_revision=3,
            source_revision="deadbee1234567890",
            operator_approval=approval,
        )


def test_gated_approval_requires_authorization_receipt_reference() -> None:
    job = JobState("job-a", READY_FOR_REVIEW, 3)
    approval = approval_for(
        job,
        to_state=ACCEPTED,
        approval_class="JOB_ACCEPTANCE",
        approval_id="approval-a",
    )
    approval["authorization_receipt_id"] = ""

    with pytest.raises(JobTransitionError, match="OPERATOR_APPROVAL_MALFORMED"):
        GovernedJobStateMachine.transition(
            job,
            to_state=ACCEPTED,
            expected_revision=3,
            source_revision=SOURCE_REVISION,
            operator_approval=approval,
        )


def test_source_revision_is_required_and_unexpected_approval_fails_closed() -> None:
    job = JobState("job-a", PROPOSED, 1)

    with pytest.raises(JobTransitionError, match="SOURCE_REVISION_REQUIRED"):
        GovernedJobStateMachine.transition(
            job,
            to_state=RESEARCHING,
            expected_revision=1,
            source_revision="short",
        )

    with pytest.raises(JobTransitionError, match="UNEXPECTED_OPERATOR_APPROVAL"):
        GovernedJobStateMachine.transition(
            job,
            to_state=RESEARCHING,
            expected_revision=1,
            source_revision=SOURCE_REVISION,
            operator_approval={"unexpected": "approval"},
        )
