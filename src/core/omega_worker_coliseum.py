from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .omega_worker_elite_orchestrator import (
    EliteJudgement,
    EliteOrchestrator,
    GladiatorProposal,
)


class ColiseumError(ValueError):
    pass


@dataclass(frozen=True)
class ColiseumResult:
    opportunity_id: str
    ranked: tuple[EliteJudgement, ...]
    winner_gladiator_id: str | None
    owner_gate_required: bool
    selection_status: str


class ColiseumOrchestrator:
    """Runs a bounded multi-Gladiator contest after RGB+/AER+ review.

    Ranking is advisory. Winning never grants execution authority.
    """

    def __init__(self, referee: EliteOrchestrator | None = None):
        self.referee = referee or EliteOrchestrator()

    def run(
        self,
        opportunity_id: str,
        proposals: Iterable[GladiatorProposal],
        owner_gate: bool = False,
    ) -> ColiseumResult:
        if not opportunity_id:
            raise ColiseumError("opportunity_id is required.")

        proposals = tuple(proposals)
        if not proposals:
            raise ColiseumError("At least one Gladiator proposal is required.")

        ids = [proposal.gladiator_id for proposal in proposals]
        if len(ids) != len(set(ids)):
            raise ColiseumError("Duplicate Gladiator IDs are not permitted.")

        ranked = tuple(self.referee.rank(proposals))
        eligible = tuple(
            judgement
            for judgement in ranked
            if judgement.aer_decision == "ALLOW_WITH_CONTROLS"
        )

        if not eligible:
            return ColiseumResult(
                opportunity_id=opportunity_id,
                ranked=ranked,
                winner_gladiator_id=None,
                owner_gate_required=True,
                selection_status="NO_ELIGIBLE_WINNER",
            )

        winner = eligible[0]
        if not owner_gate:
            return ColiseumResult(
                opportunity_id=opportunity_id,
                ranked=ranked,
                winner_gladiator_id=winner.gladiator_id,
                owner_gate_required=True,
                selection_status="AWAITING_OWNER_GATE",
            )

        return ColiseumResult(
            opportunity_id=opportunity_id,
            ranked=ranked,
            winner_gladiator_id=winner.gladiator_id,
            owner_gate_required=True,
            selection_status="OWNER_ACCEPTED_SELECTION",
        )
