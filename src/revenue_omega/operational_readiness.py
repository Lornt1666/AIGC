from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


OPERATIONAL_READINESS_WEIGHTS: dict[str, int] = {
    "schemas_persistence": 8,
    "compute_metering": 10,
    "commission_engine": 8,
    "invoice_generation": 8,
    "email_delivery": 6,
    "payment_provider_adapter": 10,
    "payment_webhooks_reconciliation": 7,
    "accounting_ledger": 9,
    "tax_engine_interface": 5,
    "anti_fraud": 5,
    "idempotency_duplicate_prevention": 5,
    "refunds_disputes": 4,
    "observability": 5,
    "security_secret_handling": 5,
    "automated_tests": 5,
}

VALID_STATES = {"MISSING", "DESIGNED", "IMPLEMENTED", "VERIFIED", "NOT_APPLICABLE"}
STATE_CREDIT = {
    "MISSING": 0.0,
    "DESIGNED": 0.20,
    "IMPLEMENTED": 0.60,
    "VERIFIED": 1.0,
    "NOT_APPLICABLE": 1.0,
}


@dataclass(frozen=True)
class OperationalReadinessDimension:
    dimension: str
    weight: int
    state: str
    evidence_refs: tuple[str, ...]
    blocker: str = ""

    def __post_init__(self) -> None:
        expected = OPERATIONAL_READINESS_WEIGHTS.get(self.dimension)
        if expected is None:
            raise ValueError(f"unknown operational readiness dimension: {self.dimension}")
        if self.weight != expected:
            raise ValueError(f"weight mismatch for {self.dimension}")
        if self.state not in VALID_STATES:
            raise ValueError(f"unsupported operational readiness state: {self.state}")
        if self.state == "VERIFIED" and not self.evidence_refs:
            raise ValueError("VERIFIED operational readiness requires evidence")
        if self.state == "MISSING" and not self.blocker:
            raise ValueError("MISSING operational readiness requires blocker")

    @property
    def weighted_credit(self) -> float:
        return self.weight * STATE_CREDIT[self.state]

    @property
    def strict_credit(self) -> int:
        return self.weight if self.state in {"VERIFIED", "NOT_APPLICABLE"} else 0


@dataclass(frozen=True)
class OperationalReadinessReport:
    dimensions: tuple[OperationalReadinessDimension, ...]
    weighted_score: float
    strict_score: int
    complete: bool
    missing_dimensions: tuple[str, ...]


def evaluate_operational_readiness(
    states: Mapping[str, tuple[str, tuple[str, ...], str]],
) -> OperationalReadinessReport:
    unknown = set(states) - set(OPERATIONAL_READINESS_WEIGHTS)
    if unknown:
        raise ValueError(f"unknown operational readiness dimensions: {sorted(unknown)}")

    dimensions: list[OperationalReadinessDimension] = []
    for dimension, weight in OPERATIONAL_READINESS_WEIGHTS.items():
        if dimension not in states:
            state, evidence_refs, blocker = "MISSING", (), "dimension not supplied"
        else:
            state, evidence_refs, blocker = states[dimension]
        dimensions.append(
            OperationalReadinessDimension(
                dimension=dimension,
                weight=weight,
                state=state,
                evidence_refs=tuple(evidence_refs),
                blocker=blocker,
            )
        )

    weighted = round(sum(item.weighted_credit for item in dimensions), 2)
    strict = sum(item.strict_credit for item in dimensions)
    missing = tuple(item.dimension for item in dimensions if item.state == "MISSING")
    complete = all(item.state in {"VERIFIED", "NOT_APPLICABLE"} for item in dimensions)
    return OperationalReadinessReport(
        dimensions=tuple(dimensions),
        weighted_score=weighted,
        strict_score=strict,
        complete=complete,
        missing_dimensions=missing,
    )
