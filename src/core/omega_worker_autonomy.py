from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from .omega_worker_execution import ControlledExecutor, ExecutionDenied, ExecutionPermit
from .omega_worker_verification import PostconditionVerifier


class AutonomyDenied(PermissionError):
    pass


@dataclass(frozen=True)
class AutonomousExecutionPolicy:
    policy_id: str
    allowed_actions: tuple[str, ...]
    max_actions: int
    enabled: bool = True
    emergency_stop: bool = False
    require_verification: bool = True

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("policy_id is required.")
        if not self.allowed_actions:
            raise ValueError("At least one allowed action is required.")
        if len(set(self.allowed_actions)) != len(self.allowed_actions):
            raise ValueError("allowed_actions must be unique.")
        if self.max_actions <= 0:
            raise ValueError("max_actions must be positive.")


@dataclass(frozen=True)
class AutonomousExecutionResult:
    permit_id: str
    action: str
    executed: bool
    verified: bool
    action_count: int


class BoundedAutonomousExecutor:
    """Removes per-action owner gating only inside an explicit permit/policy envelope."""

    def __init__(
        self,
        policy: AutonomousExecutionPolicy,
        *,
        controlled_executor: ControlledExecutor | None = None,
        verifier: PostconditionVerifier | None = None,
    ) -> None:
        self.policy = policy
        self.controlled_executor = controlled_executor or ControlledExecutor()
        self.verifier = verifier or PostconditionVerifier()
        self._action_count = 0

    def execute(
        self,
        permit: ExecutionPermit,
        *,
        contract_id: str,
        action: str,
        action_fn: Callable[[], Any],
        verification_evidence: str,
    ) -> AutonomousExecutionResult:
        if not self.policy.enabled or self.policy.emergency_stop:
            raise AutonomyDenied("Autonomous execution is disabled or emergency-stopped.")
        if action not in self.policy.allowed_actions:
            raise AutonomyDenied("Action is outside the autonomous policy allowlist.")
        if self._action_count >= self.policy.max_actions:
            raise AutonomyDenied("Autonomous action budget is exhausted.")
        if not self.policy.require_verification:
            raise AutonomyDenied("Autonomous execution requires mandatory verification.")
        if not verification_evidence:
            raise AutonomyDenied("Verification evidence is required before autonomous execution.")

        try:
            result = self.controlled_executor.execute(
                permit,
                contract_id=contract_id,
                action=action,
                action_fn=action_fn,
            )
        except ExecutionDenied:
            raise

        self._action_count += 1
        verified = self.verifier.verify(
            contract_id=contract_id,
            action=action,
            evidence=verification_evidence,
        )
        if not verified:
            raise AutonomyDenied("Postcondition verification failed.")

        return AutonomousExecutionResult(
            permit_id=result.permit_id,
            action=result.action,
            executed=result.executed,
            verified=verified,
            action_count=self._action_count,
        )
