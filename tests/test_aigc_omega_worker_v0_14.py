import pytest

from src.core.omega_worker_autonomy import (
    AutonomousExecutionPolicy,
    AutonomyDenied,
    BoundedAutonomousExecutor,
)
from src.core.omega_worker_execution import ExecutionPermit


def permit(action="deliver"):
    return ExecutionPermit(
        permit_id="permit-1",
        contract_id="contract-1",
        authorized_action=action,
        approved_by="owner",
        policy_reference="policy-1",
        active=True,
    )


def test_bounded_autonomy_executes_allowlisted_permitted_action():
    policy = AutonomousExecutionPolicy("policy-1", ("deliver",), 2)
    executor = BoundedAutonomousExecutor(policy)
    seen = []
    result = executor.execute(
        permit(),
        contract_id="contract-1",
        action="deliver",
        action_fn=lambda: seen.append("ran"),
        verification_evidence="verified delivery",
    )
    assert seen == ["ran"]
    assert result.executed is True
    assert result.verified is True
    assert result.action_count == 1


def test_allowlist_is_enforced():
    executor = BoundedAutonomousExecutor(AutonomousExecutionPolicy("p", ("deliver",), 1))
    with pytest.raises(AutonomyDenied):
        executor.execute(
            permit(),
            contract_id="contract-1",
            action="delete",
            action_fn=lambda: None,
            verification_evidence="evidence",
        )


def test_budget_is_enforced():
    executor = BoundedAutonomousExecutor(AutonomousExecutionPolicy("p", ("deliver",), 1))
    executor.execute(permit(), contract_id="contract-1", action="deliver", action_fn=lambda: None, verification_evidence="e")
    with pytest.raises(AutonomyDenied):
        executor.execute(permit("deliver"), contract_id="contract-1", action="deliver", action_fn=lambda: None, verification_evidence="e")


def test_emergency_stop_blocks():
    executor = BoundedAutonomousExecutor(AutonomousExecutionPolicy("p", ("deliver",), 1, emergency_stop=True))
    with pytest.raises(AutonomyDenied):
        executor.execute(permit(), contract_id="contract-1", action="deliver", action_fn=lambda: None, verification_evidence="e")


def test_disabled_policy_blocks():
    executor = BoundedAutonomousExecutor(AutonomousExecutionPolicy("p", ("deliver",), 1, enabled=False))
    with pytest.raises(AutonomyDenied):
        executor.execute(permit(), contract_id="contract-1", action="deliver", action_fn=lambda: None, verification_evidence="e")


def test_permit_is_still_mandatory():
    executor = BoundedAutonomousExecutor(AutonomousExecutionPolicy("p", ("deliver",), 1))
    with pytest.raises(Exception):
        executor.execute(
            ExecutionPermit("permit-1", "other-contract", "deliver", "owner", "policy-1", True),
            contract_id="contract-1",
            action="deliver",
            action_fn=lambda: None,
            verification_evidence="e",
        )
