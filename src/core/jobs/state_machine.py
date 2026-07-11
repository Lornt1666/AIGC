from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


PROPOSED = "PROPOSED"
RESEARCHING = "RESEARCHING"
READY_FOR_REVIEW = "READY_FOR_REVIEW"
ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
DELIVERED = "DELIVERED"
CANCELLED = "CANCELLED"

TERMINAL_STATES = {REJECTED, DELIVERED, CANCELLED}
OPERATOR_GATED_STATES = {ACCEPTED, DELIVERED}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PROPOSED: {RESEARCHING, CANCELLED},
    RESEARCHING: {READY_FOR_REVIEW, CANCELLED},
    READY_FOR_REVIEW: {ACCEPTED, REJECTED, RESEARCHING, CANCELLED},
    ACCEPTED: {DELIVERED, CANCELLED},
    REJECTED: set(),
    DELIVERED: set(),
    CANCELLED: set(),
}


class JobTransitionError(ValueError):
    """Raised when a governed job transition fails closed."""


@dataclass(frozen=True)
class JobState:
    job_id: str
    state: str
    revision: int


@dataclass(frozen=True)
class JobTransitionReceipt:
    receipt_id: str
    job_id: str
    from_state: str
    to_state: str
    expected_revision: int
    new_revision: int
    operator_approval_required: bool
    operator_approval_present: bool
    reason: str | None = None
    external_action_performed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "job_id": self.job_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "expected_revision": self.expected_revision,
            "new_revision": self.new_revision,
            "operator_approval_required": self.operator_approval_required,
            "operator_approval_present": self.operator_approval_present,
            "reason": self.reason,
            "external_action_performed": self.external_action_performed,
        }


class GovernedJobStateMachine:
    """Pure, fail-closed job lifecycle kernel with explicit operator gates."""

    @staticmethod
    def transition(
        job: JobState,
        *,
        to_state: str,
        expected_revision: int,
        operator_approval_id: str | None = None,
        reason: str | None = None,
    ) -> tuple[JobState, JobTransitionReceipt]:
        if job.state not in ALLOWED_TRANSITIONS:
            raise JobTransitionError(f"Unknown current job state: {job.state}")
        if to_state not in ALLOWED_TRANSITIONS:
            raise JobTransitionError(f"Unknown target job state: {to_state}")
        if job.revision != expected_revision:
            raise JobTransitionError("JOB_REVISION_CONFLICT")
        if job.state in TERMINAL_STATES:
            raise JobTransitionError("JOB_TERMINAL_STATE")
        if to_state not in ALLOWED_TRANSITIONS[job.state]:
            raise JobTransitionError(f"ILLEGAL_JOB_TRANSITION:{job.state}->{to_state}")

        approval_required = to_state in OPERATOR_GATED_STATES
        approval_present = bool(operator_approval_id)
        if approval_required and not approval_present:
            raise JobTransitionError("OPERATOR_APPROVAL_REQUIRED")
        if to_state in {REJECTED, CANCELLED} and not reason:
            raise JobTransitionError("TRANSITION_REASON_REQUIRED")

        new_revision = job.revision + 1
        receipt_material = "|".join(
            [
                job.job_id,
                job.state,
                to_state,
                str(expected_revision),
                str(new_revision),
                operator_approval_id or "",
                reason or "",
            ]
        )
        receipt_id = "JOB-TRANSITION-" + sha256(receipt_material.encode("utf-8")).hexdigest()[:24]
        next_job = JobState(job_id=job.job_id, state=to_state, revision=new_revision)
        receipt = JobTransitionReceipt(
            receipt_id=receipt_id,
            job_id=job.job_id,
            from_state=job.state,
            to_state=to_state,
            expected_revision=expected_revision,
            new_revision=new_revision,
            operator_approval_required=approval_required,
            operator_approval_present=approval_present,
            reason=reason,
        )
        return next_job, receipt
