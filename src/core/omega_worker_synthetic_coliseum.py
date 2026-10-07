from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from .omega_worker_evidence_ledger import EvidenceLedger
from .omega_worker_recovery import FailureRecoveryEngine, RetryPolicy, RollbackPolicy
from .omega_worker_task_contract import TaskContract, TaskContractError


@dataclass(frozen=True)
class SyntheticScenario:
    scenario_id: str
    contract: TaskContract
    action: str
    metrics: Any
    owner_gate: bool
    permit: Any
    postcondition: Any
    action_fn: Callable[[], Any]
    verification_check: Callable[[], bool]
    evidence: str
    remaining_budget: int
    retry_policy: RetryPolicy
    rollback_policy: RollbackPolicy
    irreversible: bool = False


@dataclass(frozen=True)
class SyntheticRunResult:
    scenario_id: str
    status: str
    selection_status: str
    execution_status: str
    recovery_status: str
    ledger_valid: bool
    external_side_effects: bool


class SyntheticColiseum:
    """Deterministic integration harness. It never performs external I/O."""

    def __init__(self, *, ledger: EvidenceLedger | None = None) -> None:
        self.ledger = ledger or EvidenceLedger()
        self.recovery = FailureRecoveryEngine(max_total_attempts=3)

    def run(self, scenario: SyntheticScenario) -> SyntheticRunResult:
        if not scenario.contract.allows_action(scenario.action):
            raise TaskContractError("Synthetic action is outside TaskContract scope.")

        action_calls = {"count": 0}

        def wrapped_action() -> Any:
            action_calls["count"] += 1
            return scenario.action_fn()

        self.ledger.append(
            f"{scenario.scenario_id}:START",
            {"contract_id": scenario.contract.contract_id, "action": scenario.action},
        )

        if not scenario.owner_gate:
            self.ledger.append(
                f"{scenario.scenario_id}:OWNER_GATE",
                {"status": "BLOCKED"},
            )
            return SyntheticRunResult(
                scenario.scenario_id, "BLOCKED", "AWAITING_OWNER_GATE",
                "NOT_EXECUTED", "NOT_STARTED", self.ledger.verify(), False,
            )

        try:
            result = self.recovery.recover(
                contract_id=scenario.contract.contract_id,
                action=scenario.action,
                action_fn=wrapped_action,
                retry_policy=scenario.retry_policy,
                rollback_policy=scenario.rollback_policy,
                verification_check=scenario.verification_check,
                evidence=scenario.evidence,
                remaining_budget=scenario.remaining_budget,
                irreversible=scenario.irreversible,
            )
        except Exception as exc:
            self.ledger.append(
                f"{scenario.scenario_id}:ERROR",
                {"error": type(exc).__name__, "message": str(exc)},
            )
            raise

        self.ledger.append(
            f"{scenario.scenario_id}:RESULT",
            {"status": result.status, "attempts": result.attempts, "reason": result.reason},
        )
        return SyntheticRunResult(
            scenario.scenario_id,
            result.status,
            "OWNER_ACCEPTED_SELECTION",
            "VERIFIED" if result.status == "VERIFIED" else "FAILED",
            result.status,
            self.ledger.verify(),
            False,
        )
