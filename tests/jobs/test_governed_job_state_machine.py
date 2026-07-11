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


def validate(receipt: dict[str, object]) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(receipt)


def test_happy_path_requires_operator_acceptance_and_emits_valid_receipts() -> None:
    job = JobState("job-a", PROPOSED, 1)

    job, first = GovernedJobStateMachine.transition(
        job,
        to_state=RESEARCHING,
        expected_revision=1,
    )
    job, second = GovernedJobStateMachine.transition(
        job,
        to_state=READY_FOR_REVIEW,
        expected_revision=2,
    )
    job, third = GovernedJobStateMachine.transition(
        job,
        to_state=ACCEPTED,
        expected_revision=3,
        operator_approval_id="approval-a",
    )
    job, fourth = GovernedJobStateMachine.transition(
        job,
        to_state=DELIVERED,
        expected_revision=4,
        operator_approval_id="approval-b",
    )

    assert job.state == DELIVERED
    assert job.revision == 5
    assert first.operator_approval_required is False
    assert second.operator_approval_required is False
    assert third.operator_approval_required is True
    assert fourth.operator_approval_required is True
    for receipt in (first, second, third, fourth):
        assert receipt.external_action_performed is False
        validate(receipt.as_dict())


def test_accept_without_operator_approval_fails_closed() -> None:
    job = JobState("job-a", READY_FOR_REVIEW, 7)

    with pytest.raises(JobTransitionError, match="OPERATOR_APPROVAL_REQUIRED"):
        GovernedJobStateMachine.transition(
            job,
            to_state=ACCEPTED,
            expected_revision=7,
        )


def test_stale_revision_and_illegal_transition_are_rejected() -> None:
    job = JobState("job-a", PROPOSED, 2)

    with pytest.raises(JobTransitionError, match="JOB_REVISION_CONFLICT"):
        GovernedJobStateMachine.transition(
            job,
            to_state=RESEARCHING,
            expected_revision=1,
        )

    with pytest.raises(JobTransitionError, match="ILLEGAL_JOB_TRANSITION"):
        GovernedJobStateMachine.transition(
            job,
            to_state=DELIVERED,
            expected_revision=2,
            operator_approval_id="approval-a",
        )


def test_cancellation_requires_reason_and_terminal_state_cannot_transition() -> None:
    job = JobState("job-a", PROPOSED, 1)

    with pytest.raises(JobTransitionError, match="TRANSITION_REASON_REQUIRED"):
        GovernedJobStateMachine.transition(
            job,
            to_state=CANCELLED,
            expected_revision=1,
        )

    cancelled, receipt = GovernedJobStateMachine.transition(
        job,
        to_state=CANCELLED,
        expected_revision=1,
        reason="operator withdrew the local proposal",
    )
    validate(receipt.as_dict())

    with pytest.raises(JobTransitionError, match="JOB_TERMINAL_STATE"):
        GovernedJobStateMachine.transition(
            cancelled,
            to_state=RESEARCHING,
            expected_revision=2,
        )
