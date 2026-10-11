from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import canonical_sha256, money


HARD_FLAGS = {
    "EMPLOYER_UNVERIFIED",
    "PLACEMENT_UNVERIFIED",
    "AGREEMENT_UNVERIFIED",
    "SUCCESS_EVENT_UNVERIFIED",
    "COMPENSATION_UNVERIFIED",
    "DUPLICATE_BILLING_EVENT",
    "PAYER_MISMATCH",
    "TAMPERED_EVIDENCE",
}

REVIEW_FLAGS = {
    "COMPENSATION_OUTLIER",
    "SHARED_ATTRIBUTION",
    "RECENT_EMPLOYER_IDENTITY_CHANGE",
    "UNUSUAL_COMPUTE_MARKUP",
    "HIGH_VALUE_INVOICE",
}


@dataclass(frozen=True)
class FraudAssessmentInput:
    employer_verified: bool
    placement_verified: bool
    agreement_verified: bool
    success_event_verified: bool
    compensation_verified: bool
    duplicate_billing_event: bool
    payer_matches_agreement: bool
    evidence_integrity_valid: bool
    attribution_status: str
    eligible_compensation: Decimal
    expected_compensation_min: Decimal | None = None
    expected_compensation_max: Decimal | None = None
    employer_identity_recently_changed: bool = False
    compute_markup_rate: Decimal = Decimal("0")
    invoice_total: Decimal = Decimal("0")
    high_value_threshold: Decimal = Decimal("10000")

    def __post_init__(self) -> None:
        object.__setattr__(self, "eligible_compensation", money(self.eligible_compensation))
        object.__setattr__(self, "invoice_total", money(self.invoice_total))
        object.__setattr__(self, "high_value_threshold", money(self.high_value_threshold))
        if self.expected_compensation_min is not None:
            object.__setattr__(self, "expected_compensation_min", money(self.expected_compensation_min))
        if self.expected_compensation_max is not None:
            object.__setattr__(self, "expected_compensation_max", money(self.expected_compensation_max))
        if self.eligible_compensation < Decimal("0") or self.invoice_total < Decimal("0"):
            raise ValueError("fraud assessment money values cannot be negative")


@dataclass(frozen=True)
class FraudAssessment:
    decision: str
    hard_flags: tuple[str, ...]
    review_flags: tuple[str, ...]
    automatic_billing_allowed: bool
    assessment_hash: str


def assess_billing_fraud(value: FraudAssessmentInput) -> FraudAssessment:
    hard: list[str] = []
    review: list[str] = []

    if not value.employer_verified:
        hard.append("EMPLOYER_UNVERIFIED")
    if not value.placement_verified:
        hard.append("PLACEMENT_UNVERIFIED")
    if not value.agreement_verified:
        hard.append("AGREEMENT_UNVERIFIED")
    if not value.success_event_verified:
        hard.append("SUCCESS_EVENT_UNVERIFIED")
    if not value.compensation_verified:
        hard.append("COMPENSATION_UNVERIFIED")
    if value.duplicate_billing_event:
        hard.append("DUPLICATE_BILLING_EVENT")
    if not value.payer_matches_agreement:
        hard.append("PAYER_MISMATCH")
    if not value.evidence_integrity_valid:
        hard.append("TAMPERED_EVIDENCE")

    if value.attribution_status == "SHARED_ATTRIBUTION":
        review.append("SHARED_ATTRIBUTION")
    elif value.attribution_status != "ATTRIBUTED":
        hard.append("PLACEMENT_UNVERIFIED")

    if value.expected_compensation_min is not None and value.eligible_compensation < value.expected_compensation_min:
        review.append("COMPENSATION_OUTLIER")
    if value.expected_compensation_max is not None and value.eligible_compensation > value.expected_compensation_max:
        review.append("COMPENSATION_OUTLIER")
    if value.employer_identity_recently_changed:
        review.append("RECENT_EMPLOYER_IDENTITY_CHANGE")
    if value.compute_markup_rate > Decimal("0.50"):
        review.append("UNUSUAL_COMPUTE_MARKUP")
    if value.invoice_total >= value.high_value_threshold:
        review.append("HIGH_VALUE_INVOICE")

    hard = sorted(set(hard))
    review = sorted(set(review))
    if hard:
        decision = "REJECT"
        automatic = False
    elif review:
        decision = "REQUIRE_REVIEW"
        automatic = False
    else:
        decision = "PASS"
        automatic = True

    payload = {
        "decision": decision,
        "hard_flags": hard,
        "review_flags": review,
        "automatic_billing_allowed": automatic,
        "eligible_compensation": value.eligible_compensation,
        "invoice_total": value.invoice_total,
        "attribution_status": value.attribution_status,
    }
    return FraudAssessment(
        decision=decision,
        hard_flags=tuple(hard),
        review_flags=tuple(review),
        automatic_billing_allowed=automatic,
        assessment_hash=canonical_sha256(payload),
    )
