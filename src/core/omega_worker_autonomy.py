from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, FrozenSet

from .omega_worker_execution import ControlledExecutor, ExecutionDenied, ExecutionPermit


class AutonomousExecutionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class AutonomousExecutionPolicy:
    policy_id: str
    allowed_actions: FrozenSet[str]
    max_actions: int
    enabled: bool = True
    emergency_stop: bool = False
    require_verification: bool = True

    def validate(self) -> None:
        if not self.policy_id:
            raise AutonomousExecutionDenied("Autonomous policy requires an identifier.")
        if not self.allowed_actions:
            raise AutonomousExecutionDenied("Autonomous policy must allow at least one action.")
        if self.max_actions <= 0:
            raise AutonomousExecutionDenied("Autonomous action budget must be positive.")


@dataclass(frozen=True)
class AutonomousExecutionResult:
    permit_id: str
    action: str
    executed: bool
    verified: bool
    action_count: int


class AutonomousExecutor:
    """Bounded autonomous execution: explicit permit + allowlist + budget + postcondition verification."""

    def __init__(
        self,
        policy: AutonomousExecutionPolicy,
        controlled_executor: ControlledExecutor | None = None,
    ):
        policy.validate()
        self.policy = policy
        self.executor = controlled_executor or ControlledExecutor()
        self._action_count = 0

    def execute(
        self,
        permit: ExecutionPermit,
        *,
        contract_id: str,
        action: str,
        action_fn: Callable[[], Any],
        verify_fn: Callable[[], bool] | None = None,
    ) -> AutonomousExecutionResult:
        if not self.policy.enabled:
            raise AutonomousExecutionDenied("Autonomous execution is disabled.")
        if self.policy.emergency_stop:
            raise AutonomousExecutionDenied("Autonomous execution emergency stop is active.")
        if action not in self.policy.allowed_actions:
            raise AutonomousExecutionDenied("Action is outside the autonomous policy allowlist.")
        if self._action_count >= self.policy.max_actions:
            raise AutonomousExecutionDenied("Autonomous execution budget exhausted.")
        if self.policy.require_verification and verify_fn is None:
            raise AutonomousExecutionDenied("Autonomous execution requires a postcondition verifier.")

        # The permit remains mandatory. Autonomy removes the per-action owner gate;
        # it does not create credentials, targets, recipients, or permissions.
        result = self.executor.execute(
            permit,
            contract_id=contract_id,
            action=action,
            action_fn=action_fn,
        )
        self._action_count += 1

        verified = True
        if verify_fn is not None:
            verified = bool(verify_fn())

        if self.policy.require_verification and not verified:
            raise AutonomousExecutionDenied("Postcondition verification failed.")

        return AutonomousExecutionResult(
            permit_id=result.permit_id,
            action=result.action,
            executed=result.executed,
            verified=verified,
            action_count=self._action_count,
        )
