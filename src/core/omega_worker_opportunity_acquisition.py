from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any


class OpportunityDecisionError(ValueError):
    pass


@dataclass(frozen=True)
class OpportunityAssessment:
    opportunity_id: str
    capability_score: float
    commercial_score: float
    strategic_score: float
    effort_score: float
    risk_score: float
    evidence_quality: float


@dataclass(frozen=True)
class AcquisitionDecision:
    opportunity_id: str
    decision: str
    rationale: tuple[str, ...]
    owner_gate_required: bool


class OpportunityAcquisitionEngine:
    """Deterministically qualifies opportunities without authorizing external action."""

    DECISIONS = {"TARGET", "REJECT", "ESCALATE", "WAIT"}

    def assess(self, opportunity: Mapping[str, Any]) -> OpportunityAssessment:
        required = (
            "opportunity_id",
            "capability_score",
            "commercial_score",
            "strategic_score",
            "effort_score",
            "risk_score",
            "evidence_quality",
        )
        missing = [key for key in required if key not in opportunity]
        if missing:
            raise OpportunityDecisionError(f"Missing assessment fields: {', '.join(missing)}")

        values = {key: float(opportunity[key]) for key in required[1:]}
        if any(value < 0 or value > 100 for value in values.values()):
            raise OpportunityDecisionError("Assessment scores must be between 0 and 100.")

        return OpportunityAssessment(
            opportunity_id=str(opportunity["opportunity_id"]),
            **values,
        )

    def decide(self, assessment: OpportunityAssessment) -> AcquisitionDecision:
        rationale: list[str] = []

        if assessment.evidence_quality < 50:
            rationale.append("Evidence quality is below the qualification threshold.")
            return AcquisitionDecision(
                assessment.opportunity_id, "WAIT", tuple(rationale), True
            )

        if assessment.risk_score >= 80:
            rationale.append("Risk exceeds the autonomous qualification boundary.")
            return AcquisitionDecision(
                assessment.opportunity_id, "ESCALATE", tuple(rationale), True
            )

        value = (
            assessment.capability_score
            + assessment.commercial_score
            + assessment.strategic_score
        ) / 3
        burden = (assessment.effort_score + assessment.risk_score) / 2

        if value >= 70 and burden <= 55:
            rationale.append("Value clears target threshold while effort/risk remains bounded.")
            rationale.append("Owner authorization remains required before external action.")
            return AcquisitionDecision(
                assessment.opportunity_id, "TARGET", tuple(rationale), True
            )

        rationale.append("Opportunity does not currently meet the target qualification threshold.")
        return AcquisitionDecision(
            assessment.opportunity_id, "REJECT", tuple(rationale), False
        )
