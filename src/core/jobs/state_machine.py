from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping


PROPOSED = "PROPOSED"
RESEARCHING = "RESEARCHING"
READY_FOR_REVIEW = "READY_FOR_REVIEW"
ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
DELIVERED = "DELIVERED"
CANCELLED = "CANCELLED"

TERMINAL_STATES = {REJECTED, DELIVERED, CANCELLED}
OPERATOR_GATED_STATES = {ACCEPTED, DELIVERED}
REQUIRED_APPROVAL_CLASS = {
    ACCEPTED: "JOB_ACCEPTANCE",
    DELIVERED: "JOB_DELIVERY",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PROPOSED: {RESEARCHING, CANCELLED},
    RESEARCHING: {READY_FOR_REVIEW, CANCELLED},
    READY_FOR_REVIEW: {ACCEPTED, REJECTED, RESEARCHING, CANCELLED},
    ACCEPTED: {DELIVERED, CANCELLED},
    REJECTED: set(),
    DELIVERED: set(),
    CANCELLED: set(),
}

APPROVAL_FIELDS = {
    "approval_id",
    "actor_id",
    "approval_class",
    "authorization_receipt_id",
    "job_id",
    "from_state",
    "to_state",
    "expected_revision",
    "source_revision",
    "transition_digest",
    "status",
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
    source_revision: str
    transition_digest: str
    operator_approval_required: bool
    operator_approval_present: bool
    operator_approval: dict[str, object] | None
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
            "source_revision": self.source_revision,
            "transition_digest": self.transition_digest,
            "operator_approval_required": self.operator_approval_required,
            "operator_approval_present": self.operator_approval_present,
            "operator_approval": self.operator_approval,
            "reason": self.reason,
            "external_action_performed": self.external_action_performed,
        }


class GovernedJobStateMachine:
    """Pure, fail-closed job lifecycle kernel with transition-bound operator gates."""

    @staticmethod
    def transition_digest(
        job: JobState,
        *,
        to_state: str,
        expected_revision: int,
        source_revision: str,
        reason: str | None = None,
    ) -> str:
        material = {
            "job_id": job.job_id,
            "from_state": job.state,
            "to_state": to_state,
            "expected_revision": expected_revision,
            "source_revision": source_revision,
            "reason": reason,
        }
        canonical = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_operator_approval(
        approval: Mapping[str, Any],
        *,
        job: JobState,
        to_state: str,
        expected_revision: int,
        source_revision: str,
        transition_digest: str,
    ) -> dict[str, object]:
        if set(approval) != APPROVAL_FIELDS:
            raise JobTransitionError("OPERATOR_APPROVAL_MALFORMED")

        normalized = dict(approval)
        for field in ("approval_id", "actor_id", "authorization_receipt_id"):
            if not isinstance(normalized.get(field), str) or not str(normalized[field]).strip():
                raise JobTransitionError("OPERATOR_APPROVAL_MALFORMED")

        required_class = REQUIRED_APPROVAL_CLASS[to_state]
        if normalized.get("approval_class") != required_class:
            raise JobTransitionError("OPERATOR_APPROVAL_CLASS_MISMATCH")
        if str(normalized.get("status", "")).upper() != "ACTIVE":
            raise JobTransitionError("OPERATOR_APPROVAL_INACTIVE")
        if normalized.get("job_id") != job.job_id:
            raise JobTransitionError("OPERATOR_APPROVAL_JOB_MISMATCH")
        if normalized.get("from_state") != job.state or normalized.get("to_state") != to_state:
            raise JobTransitionError("OPERATOR_APPROVAL_STATE_MISMATCH")
        if normalized.get("expected_revision") != expected_revision:
            raise JobTransitionError("OPERATOR_APPROVAL_REVISION_MISMATCH")
        if normalized.get("source_revision") != source_revision:
            raise JobTransitionError("OPERATOR_APPROVAL_SOURCE_REVISION_MISMATCH")
        if normalized.get("transition_digest") != transition_digest:
            raise JobTransitionError("OPERATOR_APPROVAL_TRANSITION_DIGEST_MISMATCH")

        return normalized

    @classmethod
    def transition(
        cls,
        job: JobState,
        *,
        to_state: str,
        expected_revision: int,
        source_revision: str,
        operator_approval: Mapping[str, Any] | None = None,
        reason: str | None = None,
    ) -> tuple[JobState, JobTransitionReceipt]:
        if job.state not in ALLOWED_TRANSITIONS:
            raise JobTransitionError(f"Unknown current job state: {job.state}")
        if to_state not in ALLOWED_TRANSITIONS:
            raise JobTransitionError(f"Unknown target job state: {to_state}")
        if not isinstance(source_revision, str) or len(source_revision.strip()) < 7:
            raise JobTransitionError("SOURCE_REVISION_REQUIRED")
        if job.revision != expected_revision:
            raise JobTransitionError("JOB_REVISION_CONFLICT")
        if job.state in TERMINAL_STATES:
            raise JobTransitionError("JOB_TERMINAL_STATE")
        if to_state not in ALLOWED_TRANSITIONS[job.state]:
            raise JobTransitionError(f"ILLEGAL_JOB_TRANSITION:{job.state}->{to_state}")

        normalized_reason = reason.strip() if isinstance(reason, str) else None
        if to_state in {REJECTED, CANCELLED} and not normalized_reason:
            raise JobTransitionError("TRANSITION_REASON_REQUIRED")

        transition_digest = cls.transition_digest(
            job,
            to_state=to_state,
            expected_revision=expected_revision,
            source_revision=source_revision,
            reason=normalized_reason,
        )
        approval_required = to_state in OPERATOR_GATED_STATES
        normalized_approval: dict[str, object] | None = None
        if approval_required:
            if not isinstance(operator_approval, Mapping):
                raise JobTransitionError("OPERATOR_APPROVAL_REQUIRED")
            normalized_approval = cls._validate_operator_approval(
                operator_approval,
                job=job,
                to_state=to_state,
                expected_revision=expected_revision,
                source_revision=source_revision,
                transition_digest=transition_digest,
            )
        elif operator_approval is not None:
            raise JobTransitionError("UNEXPECTED_OPERATOR_APPROVAL")

        new_revision = job.revision + 1
        receipt_material = "|".join(
            [
                transition_digest,
                str(new_revision),
                str(normalized_approval.get("approval_id", "")) if normalized_approval else "",
                str(normalized_approval.get("actor_id", "")) if normalized_approval else "",
                str(normalized_approval.get("authorization_receipt_id", ""))
                if normalized_approval
                else "",
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
            source_revision=source_revision,
            transition_digest=transition_digest,
            operator_approval_required=approval_required,
            operator_approval_present=normalized_approval is not None,
            operator_approval=normalized_approval,
            reason=normalized_reason,
        )
        return next_job, receipt
