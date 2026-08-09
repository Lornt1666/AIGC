from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


MATURITY = {
    "MISSING": 0,
    "DESIGNED": 1,
    "IMPLEMENTED": 2,
    "CI_VERIFIED": 3,
    "SANDBOX_VERIFIED": 4,
    "RUNTIME_VERIFIED": 5,
    "NOT_APPLICABLE": 99,
}

# Strict completion is dimension-specific. Pure deterministic controls can be
# fully verified in CI; externally consequential/runtime controls require
# stronger evidence classes.
OPERATIONAL_DIMENSIONS: dict[str, tuple[int, str]] = {
    "schemas_persistence": (8, "RUNTIME_VERIFIED"),
    "compute_metering": (10, "RUNTIME_VERIFIED"),
    "commission_engine": (8, "CI_VERIFIED"),
    "invoice_generation": (8, "CI_VERIFIED"),
    "email_delivery": (6, "RUNTIME_VERIFIED"),
    "payment_provider_adapter": (10, "RUNTIME_VERIFIED"),
    "payment_webhooks_reconciliation": (7, "RUNTIME_VERIFIED"),
    "accounting_ledger": (9, "CI_VERIFIED"),
    "tax_engine_interface": (5, "RUNTIME_VERIFIED"),
    "anti_fraud": (5, "CI_VERIFIED"),
    "idempotency_duplicate_prevention": (5, "RUNTIME_VERIFIED"),
    "refunds_disputes": (4, "SANDBOX_VERIFIED"),
    "observability": (5, "RUNTIME_VERIFIED"),
    "security_secret_handling": (5, "RUNTIME_VERIFIED"),
    "automated_tests": (5, "CI_VERIFIED"),
}

# Partial/weighted maturity is intentionally conservative.
LEVEL_CREDIT = {
    "MISSING": 0.00,
    "DESIGNED": 0.15,
    "IMPLEMENTED": 0.40,
    "CI_VERIFIED": 0.65,
    "SANDBOX_VERIFIED": 0.85,
    "RUNTIME_VERIFIED": 1.00,
    "NOT_APPLICABLE": 1.00,
}


@dataclass(frozen=True)
class OperationalMaturityDimension:
    dimension: str
    weight: int
    required_level: str
    observed_level: str
    evidence_refs: tuple[str, ...]
    blocker: str = ""

    def __post_init__(self) -> None:
        expected = OPERATIONAL_DIMENSIONS.get(self.dimension)
        if expected is None:
            raise ValueError(f"unknown operational dimension: {self.dimension}")
        if expected != (self.weight, self.required_level):
            raise ValueError(f"dimension configuration mismatch: {self.dimension}")
        if self.observed_level not in MATURITY:
            raise ValueError(f"unsupported maturity: {self.observed_level}")
        if self.observed_level not in {"MISSING", "DESIGNED"} and not self.evidence_refs:
            raise ValueError("implemented/verified maturity requires evidence")
        if self.observed_level == "MISSING" and not self.blocker:
            raise ValueError("missing operational dimension requires blocker")

    @property
    def weighted_credit(self) -> float:
        return self.weight * LEVEL_CREDIT[self.observed_level]

    @property
    def strict_complete(self) -> bool:
        if self.observed_level == "NOT_APPLICABLE":
            return True
        return MATURITY[self.observed_level] >= MATURITY[self.required_level]

    @property
    def strict_credit(self) -> int:
        return self.weight if self.strict_complete else 0


@dataclass(frozen=True)
class OperationalMaturityReport:
    dimensions: tuple[OperationalMaturityDimension, ...]
    weighted_score: float
    strict_score: int
    complete: bool
    blockers: tuple[str, ...]


def evaluate_operational_maturity(
    observed: Mapping[str, tuple[str, tuple[str, ...], str]],
) -> OperationalMaturityReport:
    unknown = set(observed) - set(OPERATIONAL_DIMENSIONS)
    if unknown:
        raise ValueError(f"unknown operational dimensions: {sorted(unknown)}")

    dimensions: list[OperationalMaturityDimension] = []
    for name, (weight, required) in OPERATIONAL_DIMENSIONS.items():
        if name in observed:
            level, evidence, blocker = observed[name]
        else:
            level, evidence, blocker = "MISSING", (), "dimension not supplied"
        dimensions.append(
            OperationalMaturityDimension(
                dimension=name,
                weight=weight,
                required_level=required,
                observed_level=level,
                evidence_refs=tuple(evidence),
                blocker=blocker,
            )
        )

    weighted = round(sum(item.weighted_credit for item in dimensions), 2)
    strict = sum(item.strict_credit for item in dimensions)
    blockers = tuple(
        f"{item.dimension}: {item.blocker or f'requires {item.required_level}, has {item.observed_level}'}"
        for item in dimensions
        if not item.strict_complete
    )
    return OperationalMaturityReport(
        dimensions=tuple(dimensions),
        weighted_score=weighted,
        strict_score=strict,
        complete=all(item.strict_complete for item in dimensions),
        blockers=blockers,
    )
