from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .omega_worker_autonomy import AutonomousExecutionResult, BoundedAutonomousExecutor
from .omega_worker_coliseum import ColiseumResult
from .omega_worker_execution import ExecutionPermit
from .omega_worker_strategy_coliseum import StrategyColiseumAdapter, StrategyProposalMetrics
from .omega_worker_gladiator_strategy import GladiatorStrategyContract
from .omega_worker_verification import Postcondition


class ExecutionOrchestrationDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ExecutionOrchestrationResult:
    opportunity_id: str
    strategy_id: str
    gladiator_id: str
    selection_status: str
    execution_status: str
    execution: AutonomousExecutionResult | None


class GovernedExecutionOrchestrator:
    """Connects strategy selection to bounded execution without adding authority.

    Execution authority is bound to an explicitly supplied contract identifier;
    the orchestrator never infers that identifier from strategy content.
    """

    def __init__(
        self,
        *,
        strategy_coliseum: StrategyColiseumAdapter | None = None,
        autonomous_executor: BoundedAutonomousExecutor | None = None,
    ) -> None:
        self.strategy_coliseum = strategy_coliseum or StrategyColiseumAdapter()
        self.autonomous_executor = autonomous_executor

    def run(
        self,
        strategy: GladiatorStrategyContract,
        metrics: StrategyProposalMetrics,
        *,
        owner_gate: bool,
        contract_id: str,
        permit: ExecutionPermit | None,
        action: str,
        action_fn: Callable[[], Any],
        verification_evidence: str,
        postcondition: Postcondition,
        verification_check: Callable[[], bool],
    ) -> ExecutionOrchestrationResult:
        if not contract_id:
            raise ExecutionOrchestrationDenied(
                "An explicit execution contract ID is required."
            )

        selection: ColiseumResult = self.strategy_coliseum.run(
            strategy,
            metrics,
            owner_gate=owner_gate,
        )

        if selection.selection_status != "OWNER_ACCEPTED_SELECTION":
            return ExecutionOrchestrationResult(
                opportunity_id=strategy.opportunity_id,
                strategy_id=strategy.strategy_id,
                gladiator_id=strategy.gladiator_id,
                selection_status=selection.selection_status,
                execution_status="NOT_EXECUTED",
                execution=None,
            )

        if permit is None:
            raise ExecutionOrchestrationDenied(
                "Owner-accepted selection still requires an execution permit."
            )
        if self.autonomous_executor is None:
            raise ExecutionOrchestrationDenied(
                "A bounded autonomous executor is required for execution."
            )

        try:
            execution = self.autonomous_executor.execute(
                permit,
                contract_id=contract_id,
                action=action,
                action_fn=action_fn,
                verification_evidence=verification_evidence,
                postcondition=postcondition,
                verification_check=verification_check,
            )
        except PermissionError as exc:
            raise ExecutionOrchestrationDenied(str(exc)) from exc

        return ExecutionOrchestrationResult(
            opportunity_id=strategy.opportunity_id,
            strategy_id=strategy.strategy_id,
            gladiator_id=strategy.gladiator_id,
            selection_status=selection.selection_status,
            execution_status="VERIFIED",
            execution=execution,
        )
