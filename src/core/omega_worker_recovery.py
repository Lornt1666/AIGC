from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


class RecoveryDenied(PermissionError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 0
    idempotent: bool = False

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if self.max_retries > 0 and not self.idempotent:
            raise ValueError("Retries require an explicitly idempotent action.")


@dataclass(frozen=True)
class RollbackPolicy:
    enabled: bool = False
    authorized: bool = False
    compensating_action: str = ""

    def __post_init__(self) -> None:
        if self.enabled and not self.authorized:
            raise ValueError("Rollback requires explicit authorization.")
        if self.enabled and not self.compensating_action:
            raise ValueError("Rollback requires a declared compensating action.")


@dataclass(frozen=True)
class RecoveryDecision:
    status: str
    attempts: int
    reason: str
    evidence: str


@dataclass(frozen=True)
class EscalationPackage:
    contract_id: str
    failure_reason: str
    attempted_actions: tuple[str, ...]
    remaining_budget: int
    recommended_disposition: str


class FailureRecoveryEngine:
    """Classifies execution failures and applies only explicitly authorized recovery."""

    def __init__(self, *, max_total_attempts: int = 1, emergency_stop: bool = False) -> None:
        if max_total_attempts <= 0:
            raise ValueError("max_total_attempts must be positive.")
        self.max_total_attempts = max_total_attempts
        self.emergency_stop = emergency_stop

    def recover(
        self,
        *,
        contract_id: str,
        action: str,
        action_fn: Callable[[], Any],
        retry_policy: RetryPolicy,
        rollback_policy: RollbackPolicy,
        verification_check: Callable[[], bool],
        evidence: str,
        remaining_budget: int,
        irreversible: bool = False,
    ) -> RecoveryDecision:
        if not contract_id or not action:
            raise RecoveryDenied("contract_id and action are required.")
        if not evidence:
            raise RecoveryDenied("Failure recovery requires evidence.")
        if remaining_budget < 0:
            raise RecoveryDenied("remaining_budget cannot be negative.")
        if self.emergency_stop:
            return RecoveryDecision("ESCALATED", 0, "EMERGENCY_STOP", evidence)

        attempts = 0
        while attempts < self.max_total_attempts:
            if attempts > 0:
                if irreversible:
                    return RecoveryDecision("ESCALATED", attempts, "IRREVERSIBLE_ACTION_NO_RETRY", evidence)
                if retry_policy.max_retries < attempts:
                    break
                if remaining_budget <= 0:
                    return RecoveryDecision("BLOCKED", attempts, "BUDGET_EXHAUSTED", evidence)
            try:
                action_fn()
                attempts += 1
            except Exception as exc:
                attempts += 1
                if attempts <= retry_policy.max_retries and attempts < self.max_total_attempts:
                    continue
                if rollback_policy.enabled and not irreversible:
                    return RecoveryDecision("ROLLBACK_REQUIRED", attempts, str(exc), evidence)
                return RecoveryDecision("ESCALATED", attempts, str(exc), evidence)

            if verification_check():
                return RecoveryDecision("VERIFIED", attempts, "POSTCONDITION_VERIFIED", evidence)
            if irreversible:
                return RecoveryDecision("ESCALATED", attempts, "VERIFICATION_FAILED_AFTER_IRREVERSIBLE_ACTION", evidence)
            if attempts >= self.max_total_attempts or attempts > retry_policy.max_retries:
                if rollback_policy.enabled:
                    return RecoveryDecision("ROLLBACK_REQUIRED", attempts, "POSTCONDITION_FAILED", evidence)
                return RecoveryDecision("ESCALATED", attempts, "POSTCONDITION_FAILED", evidence)

        return RecoveryDecision("BLOCKED", attempts, "RECOVERY_BUDGET_EXHAUSTED", evidence)

    def build_escalation(
        self,
        *,
        contract_id: str,
        failure_reason: str,
        attempted_actions: tuple[str, ...],
        remaining_budget: int,
        recommended_disposition: str,
    ) -> EscalationPackage:
        if not contract_id or not failure_reason:
            raise RecoveryDenied("Escalation requires contract and failure reason.")
        if remaining_budget < 0:
            raise RecoveryDenied("remaining_budget cannot be negative.")
        return EscalationPackage(
            contract_id=contract_id,
            failure_reason=failure_reason,
            attempted_actions=attempted_actions,
            remaining_budget=remaining_budget,
            recommended_disposition=recommended_disposition,
        )
