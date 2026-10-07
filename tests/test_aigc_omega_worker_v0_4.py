import pytest

from src.core.omega_worker_execution import ControlledExecutor, ExecutionDenied, ExecutionPermit


def permit(action="deliver"):
    return ExecutionPermit(
        permit_id="permit-001",
        contract_id="contract-001",
        authorized_action=action,
        approved_by="owner-review-001",
        policy_reference="policy-001",
        active=True,
    )


def test_controlled_executor_requires_exact_contract_and_action():
    called = []

    ControlledExecutor().execute(
        permit("deliver"),
        contract_id="contract-001",
        action="deliver",
        action_fn=lambda: called.append(True),
    )

    assert called == [True]


def test_executor_rejects_wrong_contract_without_calling_action():
    called = []

    with pytest.raises(ExecutionDenied):
        ControlledExecutor().execute(
            permit("deliver"),
            contract_id="other-contract",
            action="deliver",
            action_fn=lambda: called.append(True),
        )

    assert called == []


def test_executor_rejects_unpermitted_action_without_calling_action():
    called = []

    with pytest.raises(ExecutionDenied):
        ControlledExecutor().execute(
            permit("deliver"),
            contract_id="contract-001",
            action="submit",
            action_fn=lambda: called.append(True),
        )

    assert called == []


def test_executor_rejects_inactive_permit_without_calling_action():
    called = []
    inactive = ExecutionPermit(
        permit_id="permit-002",
        contract_id="contract-001",
        authorized_action="deliver",
        approved_by="owner-review-001",
        policy_reference="policy-001",
        active=False,
    )

    with pytest.raises(ExecutionDenied):
        ControlledExecutor().execute(
            inactive,
            contract_id="contract-001",
            action="deliver",
            action_fn=lambda: called.append(True),
        )

    assert called == []
