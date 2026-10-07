from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Any

from .omega_worker_runtime import OmegaWorkerRuntime, WorkerEvent


class ExecutionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ExecutionPermit:
    permit_id: str
    contract_id: str
    authorized_action: str
    approved_by: str
    policy_reference: str
    active: bool


@dataclass(frozen=True)
class ExecutionResult:
    permit_id: str
    action: str
    executed: bool
    evidence: str


class ControlledExecutor:
    """Executes only an explicitly permitted callable; never infers authorization."""

    def __init__(self, runtime: OmegaWorkerRuntime | None = None):
        self.runtime = runtime or OmegaWorkerRuntime()

    def execute(
        self,
        permit: ExecutionPermit,
        *,
        contract_id: str,
        action: str,
        action_fn: Callable[[], Any],
    ) -> ExecutionResult:
        if not permit.active:
            raise ExecutionDenied("Execution permit is inactive.")
        if permit.contract_id != contract_id:
            raise ExecutionDenied("Execution permit does not match contract.")
        if permit.authorized_action != action:
            raise ExecutionDenied("Requested action is outside the execution permit.")
        if not permit.approved_by or not permit.policy_reference:
            raise ExecutionDenied("Execution permit lacks approval or policy provenance.")

        # The callable is supplied by an already-authorized integration boundary.
        # This layer does not discover credentials, permissions, recipients, or targets.
        action_fn()
        return ExecutionResult(
            permit_id=permit.permit_id,
            action=action,
            executed=True,
            evidence=f"permit:{permit.permit_id};policy:{permit.policy_reference}",
        )
