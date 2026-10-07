from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class EliteOrchestrationError(ValueError):
    pass


@dataclass(frozen=True)
class GladiatorProposal:
    gladiator_id: str
    plan: str
    evidence_quality: float
    value_score: float
    risk_score: float
    cost_score: float


@dataclass(frozen=True)
class EliteJudgement:
    gladiator_id: str
    red_attack: tuple[str, ...]
    blue_controls: tuple[str, ...]
    green_value: tuple[str, ...]
    aer_decision: str
    total_score: float
    owner_gate_required: bool


class EliteOrchestrator:
    """RGB+/AER+ referee layer. It ranks proposals; it never authorizes external action."""

    def judge(self, proposal: GladiatorProposal) -> EliteJudgement:
        scores = (
            proposal.evidence_quality,
            proposal.value_score,
            proposal.risk_score,
            proposal.cost_score,
        )
        if not proposal.gladiator_id or not proposal.plan:
            raise EliteOrchestrationError("Gladiator identity and plan are required.")
        if any(score < 0 or score > 100 for score in scores):
            raise EliteOrchestrationError("Proposal scores must be between 0 and 100.")

        red: list[str] = []
        blue: list[str] = []
        green: list[str] = []

        if proposal.evidence_quality < 60:
            red.append("Evidence quality is below the elite qualification boundary.")
        if proposal.risk_score >= 70:
            red.append("Risk requires heightened review.")
        if proposal.cost_score >= 80:
            red.append("Cost burden is high.")

        if not red:
            blue.append("No critical RGB red flag detected.")
        else:
            blue.append("Owner review and explicit controls are required.")

        if proposal.value_score >= 70:
            green.append("Proposal demonstrates material expected value.")
        else:
            green.append("Expected value is below the preferred elite threshold.")

        aer_decision = "ALLOW_WITH_CONTROLS"
        if proposal.evidence_quality < 40 or proposal.risk_score >= 90:
            aer_decision = "ESCALATE"
        elif proposal.evidence_quality < 60 or proposal.risk_score >= 70:
            aer_decision = "ALLOW_WITH_CONTROLS"

        total = (
            proposal.evidence_quality * 0.30
            + proposal.value_score * 0.35
            + (100 - proposal.risk_score) * 0.20
            + (100 - proposal.cost_score) * 0.15
        )

        return EliteJudgement(
            gladiator_id=proposal.gladiator_id,
            red_attack=tuple(red),
            blue_controls=tuple(blue),
            green_value=tuple(green),
            aer_decision=aer_decision,
            total_score=round(total, 4),
            owner_gate_required=True,
        )

    def rank(self, proposals: Iterable[GladiatorProposal]) -> list[EliteJudgement]:
        judgements = [self.judge(proposal) for proposal in proposals]
        return sorted(
            judgements,
            key=lambda item: (item.aer_decision != "ALLOW_WITH_CONTROLS", -item.total_score),
        )
