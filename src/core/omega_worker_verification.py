from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


class VerificationFailure(ValueError):
    pass


@dataclass(frozen=True)
class Postcondition:
    condition_id: str
    contract_id: str
    description: str
    required: bool = True


@dataclass(frozen=True)
class VerificationResult:
    condition_id: str
    contract_id: str
    status: str
    evidence: str


class PostconditionVerifier:
    """Verifies an explicit postcondition; it never infers success from execution alone."""

    def verify(
        self,
        condition: Postcondition,
        *,
        evidence: str,
        check: Callable[[], bool],
    ) -> VerificationResult:
        if not condition.condition_id or not condition.contract_id:
            raise VerificationFailure("Postcondition requires stable identifiers.")
        if not condition.description:
            raise VerificationFailure("Postcondition requires a description.")
        if not evidence:
            raise VerificationFailure("Verification requires evidence.")

        passed = bool(check())
        if not passed:
            return VerificationResult(
                condition_id=condition.condition_id,
                contract_id=condition.contract_id,
                status="FAILED",
                evidence=evidence,
            )

        return VerificationResult(
            condition_id=condition.condition_id,
            contract_id=condition.contract_id,
            status="VERIFIED",
            evidence=evidence,
        )
