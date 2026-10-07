from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


class TaskContractError(ValueError):
    pass


@dataclass(frozen=True)
class TaskContract:
    """Single authoritative execution envelope; contains policy, not credentials."""
    contract_id: str
    objective: str
    authorized_scope: str
    resource_budget: int
    permitted_actions: Tuple[str, ...]
    evidence_requirements: Tuple[str, ...]
    postconditions: Tuple[str, ...]
    termination_conditions: Tuple[str, ...]
    retry_max: int
    rollback_enabled: bool
    rollback_compensating_action: str
    escalation_policy: str
    owner: str
    policy_reference: str
    expiration: str

    def __post_init__(self) -> None:
        if not self.contract_id or not self.objective or not self.authorized_scope:
            raise TaskContractError("contract identity, objective, and authorized scope are required.")
        if self.resource_budget <= 0:
            raise TaskContractError("resource_budget must be positive.")
        collections = (
            self.permitted_actions,
            self.evidence_requirements,
            self.postconditions,
            self.termination_conditions,
        )
        if any(not values for values in collections):
            raise TaskContractError("actions, evidence, postconditions, and termination conditions are required.")
        if len(set(self.permitted_actions)) != len(self.permitted_actions):
            raise TaskContractError("permitted_actions must be unique.")
        if self.retry_max < 0:
            raise TaskContractError("retry_max cannot be negative.")
        if self.retry_max > 0 and "idempotent" not in self.authorized_scope.lower():
            raise TaskContractError("retry authorization must explicitly declare idempotency.")
        if self.rollback_enabled and not self.rollback_compensating_action:
            raise TaskContractError("enabled rollback requires a compensating action.")
        if not self.owner or not self.policy_reference or not self.expiration:
            raise TaskContractError("owner, policy_reference, and expiration are required.")

    def allows_action(self, action: str) -> bool:
        return action in self.permitted_actions

    def validate_action(self, action: str) -> None:
        if not self.allows_action(action):
            raise TaskContractError("Action is outside the TaskContract permitted action set.")

    def validate_budget(self, amount: int) -> None:
        if amount < 0 or amount > self.resource_budget:
            raise TaskContractError("Requested resource amount exceeds TaskContract budget.")

    def validate_evidence(self, evidence: str) -> None:
        if not evidence:
            raise TaskContractError("TaskContract requires evidence.")
