import pytest

from src.core.omega_worker_autonomy import (
    AutonomousExecutionDenied,
    AutonomousExecutionPolicy,
    AutonomousExecutor,
)
from src.core.omega_worker_execution import ExecutionPermit


def policy(**overrides):
    values = {
        "policy_id": "autonomy-policy-001",
        "allowed_actions": frozenset({"deliver"}),
        "max_actions": 2,
        "enabled": True,
        "emergency_stop": False,
        "require_verification": True,
    }
    values.update(overrides)
    return AutonomousExecutionPolicy(**values)


def permit():
    return ExecutionPermit(
        permit_id="permit-auto-001",
        contract_id="contract-001",
        authorized_action="deliver",
        approved_by="autonomy-policy-001",
        policy_reference="policy-autonomy-v0.14",
        active=True,
    )


def test_autonomous_execution_runs_without_per_action_owner_gate():
    called = []
    verified = []

    result = AutonomousExecutor(policy()).execute(
        permit(),
        contract_id="contract-001",
        action="deliver",
        action_fn=lambda: called.append(True),
        verify_fn=lambda: verified.append(True) or True,
    )

    assert result.executed is True
    assert result.verified is True
    assert called == [True]
    assert verified == [True]


def test_autonomy_requires_allowlist():
    called = []

    with pytest.raises(AutonomousExecutionDenied):
        AutonomousExecutor(policy()).execute(
            permit(),
            contract_id="contract-001",
            action="submit",
            action_fn=lambda: called.append(True),
            verify_fn=lambda: True,
        )

    assert called == []


def test_autonomy_enforces_budget():
    executor = AutonomousExecutor(policy(max_actions=1))
    executor.execute(
        permit(),
        contract_id="contract-001",
        action="deliver",
        action_fn=lambda: None,
        verify_fn=lambda: True,
    )

    with pytest.raises(AutonomousExecutionDenied):
        executor.execute(
            permit(),
            contract_id="contract-001",
            action="deliver",
            action_fn=lambda: None,
            verify_fn=lambda: True,
        )


def test_autonomy_emergency_stop_fails_closed():
    with pytest.raises(AutonomousExecutionDenied):
        AutonomousExecutor(policy(emergency_stop=True)).execute(
            permit(),
            contract_id="contract-001",
            action="deliver",
            action_fn=lambda: pytest.fail("must not execute"),
            verify_fn=lambda: True,
        )


def test_autonomy_requires_verification():
    with pytest.raises(AutonomousExecutionDenied):
        AutonomousExecutor(policy()).execute(
            permit(),
            contract_id="contract-001",
            action="deliver",
            action_fn=lambda: None,
        )


def test_autonomy_can_be_disabled():
    with pytest.raises(AutonomousExecutionDenied):
        AutonomousExecutor(policy(enabled=False)).execute(
            permit(),
            contract_id="contract-001",
            action="deliver",
            action_fn=lambda: pytest.fail("must not execute"),
            verify_fn=lambda: True,
        )
