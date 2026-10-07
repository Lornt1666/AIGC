from __future__ import annotations

from dataclasses import dataclass

from .omega_worker_coliseum import ColiseumOrchestrator, ColiseumResult
from .omega_worker_elite_orchestrator import GladiatorProposal
from .omega_worker_gladiator_strategy import GladiatorStrategyContract, GladiatorStrategyFactory


class StrategyColiseumIntegrationError(ValueError):
    pass


@dataclass(frozen=True)
class StrategyProposalMetrics:
    evidence_quality: float
    value_score: float
    risk_score: float
    cost_score: float


class StrategyColiseumAdapter:
    """Binds an assessed Strategy Contract to the existing Coliseum proposal boundary.

    Metrics are supplied explicitly; strategy content never invents qualification scores.
    The adapter has no execution capability and never bypasses the owner gate.
    """

    def __init__(
        self,
        strategy_factory: GladiatorStrategyFactory | None = None,
        coliseum: ColiseumOrchestrator | None = None,
    ):
        self.strategy_factory = strategy_factory or GladiatorStrategyFactory()
        self.coliseum = coliseum or ColiseumOrchestrator()

    def run(
        self,
        strategy: GladiatorStrategyContract,
        metrics: StrategyProposalMetrics,
        owner_gate: bool = False,
    ) -> ColiseumResult:
        assessment = self.strategy_factory.assess(strategy)
        if not assessment.ready:
            raise StrategyColiseumIntegrationError(
                f"Strategy is not ready: {', '.join(assessment.blockers)}"
            )

        proposal = GladiatorProposal(
            gladiator_id=strategy.gladiator_id,
            plan=strategy.plan,
            evidence_quality=metrics.evidence_quality,
            value_score=metrics.value_score,
            risk_score=metrics.risk_score,
            cost_score=metrics.cost_score,
        )
        return self.coliseum.run(
            opportunity_id=strategy.opportunity_id,
            proposals=(proposal,),
            owner_gate=owner_gate,
        )
