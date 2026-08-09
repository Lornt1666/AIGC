from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


COMMERCIAL_READINESS_WEIGHTS: dict[str, int] = {
    "jurisdiction_licensing": 15,
    "employer_agreement": 12,
    "pricing_commission": 10,
    "compute_cost_recovery": 8,
    "tax_accounting": 10,
    "payment_refund": 10,
    "privacy_compensation_data": 8,
    "invoice_email": 7,
    "dispute_guarantee": 7,
    "fraud_duplicate_billing": 5,
    "founder_owner_economics": 4,
    "revenue_reporting_analytics": 4,
}

VALID_STATES = {"MISSING", "DESIGNED", "IMPLEMENTED", "VERIFIED", "NOT_APPLICABLE"}
STATE_CREDIT = {
    "MISSING": 0.0,
    "DESIGNED": 0.25,
    "IMPLEMENTED": 0.60,
    "VERIFIED": 1.0,
    "NOT_APPLICABLE": 1.0,
}


@dataclass(frozen=True)
class ReadinessDimension:
    dimension: str
    weight: int
    state: str
    evidence_refs: tuple[str, ...]
    blocker: str = ""

    def __post_init__(self) -> None:
        if self.dimension not in COMMERCIAL_READINESS_WEIGHTS:
            raise ValueError(f"unknown readiness dimension: {self.dimension}")
        if self.weight != COMMERCIAL_READINESS_WEIGHTS[self.dimension]:
            raise ValueError(f"weight mismatch for {self.dimension}")
        if self.state not in VALID_STATES:
            raise ValueError(f"unsupported readiness state: {self.state}")
        if self.state == "VERIFIED" and not self.evidence_refs:
            raise ValueError("VERIFIED readiness requires evidence")
        if self.state == "MISSING" and not self.blocker:
            raise ValueError("MISSING readiness requires blocker")

    @property
    def weighted_credit(self) -> float:
        return self.weight * STATE_CREDIT[self.state]

    @property
    def strict_credit(self) -> int:
        return self.weight if self.state in {"VERIFIED", "NOT_APPLICABLE"} else 0


@dataclass(frozen=True)
class CommercialReadinessReport:
    dimensions: tuple[ReadinessDimension, ...]
    weighted_score: float
    strict_score: int
    is_complete: bool


def evaluate_commercial_readiness(
    states: Mapping[str, tuple[str, tuple[str, ...], str]],
) -> CommercialReadinessReport:
    unknown = set(states) - set(COMMERCIAL_READINESS_WEIGHTS)
    if unknown:
        raise ValueError(f"unknown readiness dimensions: {sorted(unknown)}")

    dimensions: list[ReadinessDimension] = []
    for dimension, weight in COMMERCIAL_READINESS_WEIGHTS.items():
        if dimension not in states:
            state, evidence_refs, blocker = "MISSING", (), "dimension not supplied"
        else:
            state, evidence_refs, blocker = states[dimension]
        dimensions.append(
            ReadinessDimension(
                dimension=dimension,
                weight=weight,
                state=state,
                evidence_refs=tuple(evidence_refs),
                blocker=blocker,
            )
        )

    weighted = round(sum(item.weighted_credit for item in dimensions), 2)
    strict = sum(item.strict_credit for item in dimensions)
    complete = all(item.state in {"VERIFIED", "NOT_APPLICABLE"} for item in dimensions)
    return CommercialReadinessReport(
        dimensions=tuple(dimensions),
        weighted_score=weighted,
        strict_score=strict,
        is_complete=complete,
    )
