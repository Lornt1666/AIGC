from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from automated_canadian_grant_system.core.constitutional_guardrails import (
    financial_findings,
)
from automated_canadian_grant_system.core.models import GrantApplicationRequest


class FinancialAuditor:
    """Creates a local CAD planning table and flags unverified assumptions."""

    def review(self, request: GrantApplicationRequest) -> dict[str, Any]:
        project = request.project
        requested_cents = self._to_cents(project.requested_funding_cad)
        matching_cents = self._to_cents(project.matching_contribution_cad)
        requested_schedule = self._distribute(
            requested_cents,
            project.duration_months,
        )
        matching_schedule = self._distribute(
            matching_cents,
            project.duration_months,
        )
        monthly_budget = [
            {
                "month": index + 1,
                "requested_funding_cad": self._from_cents(requested),
                "matching_contribution_cad": self._from_cents(matching),
                "total_planned_cad": self._from_cents(requested + matching),
            }
            for index, (requested, matching) in enumerate(
                zip(requested_schedule, matching_schedule)
            )
        ]
        ratio = request.grant.eligibility.required_matching_ratio
        minimum_match = (
            self._from_cents(
                self._to_cents(project.requested_funding_cad * ratio)
            )
            if ratio is not None
            else None
        )
        return {
            "currency": "CAD",
            "duration_months": project.duration_months,
            "requested_funding_cad": self._from_cents(requested_cents),
            "matching_contribution_cad": self._from_cents(matching_cents),
            "total_planned_cad": self._from_cents(
                requested_cents + matching_cents
            ),
            "required_matching_ratio": ratio,
            "minimum_matching_contribution_cad": minimum_match,
            "monthly_budget": monthly_budget,
            "findings": financial_findings(request),
            "financial_values_verified": False,
            "external_action_performed": False,
        }

    @staticmethod
    def _to_cents(value: float) -> int:
        amount = Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        return int(amount * 100)

    @staticmethod
    def _from_cents(value: int) -> float:
        return float(Decimal(value) / Decimal(100))

    @staticmethod
    def _distribute(total_cents: int, months: int) -> list[int]:
        quotient, remainder = divmod(total_cents, months)
        return [
            quotient + (1 if index < remainder else 0)
            for index in range(months)
        ]
