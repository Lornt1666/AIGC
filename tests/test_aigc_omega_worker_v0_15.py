import pytest

from src.core.omega_worker_autonomy import (
    AutonomousExecutionPolicy,
    BoundedAutonomousExecutor,
)
from src.core.omega_worker_execution import ExecutionPermit
from src.core.omega_worker_gladiator_strategy import GladiatorStrategyContract
from src.core.omega_worker_strategy_coliseum import StrategyProposalMetrics
from src.core.omega_worker_verification import Postcondition
from src.core.omega_worker_execution_orchestrator import (
    ExecutionOrchestrationDenied,
    GovernedExecutionOrchestrator,
)


def strategy():
    return GladiatorStrategyContract(
        strategy_id="strategy-1",
        opportunity_id="opp-1",
        gladiator_id="g-1",
        objective="deliver a permitted artifact",
        plan="execute the explicitly permitted delivery",
        resource_budget=10,
        evidence_requirements=("delivery evidence",),
        termination_conditions=("verified",),
        self_challenge_questions=("what could invalidate this?",),
    )


def metrics():
    return StrategyProposalMetrics(90, 90, 10, 10)


def permit(contract_id="contract-1"):
    return ExecutionPermit(
        permit_id="permit-1",
        contract_id=contract_id,
        authorized_action="deliver",
        approved_by="owner",
        policy_reference="policy-1",
        active=True,
    )


def executor():
    return BoundedAutonomousExecutor(
        AutonomousExecutionPolicy("policy-1", ("deliver",), 1)
    )


def verification(check=lambda: True):
    return {
        "verification_evidence": "delivery verified",
        "postcondition": Postcondition(
            "condition-1", "contract-1", "delivery is verified"
        ),
        "verification_check": check,
    }


def run(orchestrator, **kwargs):
    return orchestrator.run(
        strategy(),
        metrics(),
        owner_gate=True,
        contract_id="contract-1",
        action="deliver",
        action_fn=lambda: None,
        permit=permit(),
        **kwargs,
    )


def test_boolean_owner_gate_never_executes_even_with_permit_and_executor():
    seen = []
    result = GovernedExecutionOrchestrator(
        autonomous_executor=executor()
    ).run(
        strategy(),
        metrics(),
        owner_gate=True,
        contract_id="contract-1",
        permit=permit(),
        action="deliver",
        action_fn=lambda: seen.append("ran"),
        **verification(),
    )
    assert seen == []
    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"
    assert result.execution_status == "NOT_EXECUTED"
    assert result.execution is None


def test_without_owner_gate_selection_does_not_execute():
    seen = []
    result = GovernedExecutionOrchestrator(
        autonomous_executor=executor()
    ).run(
        strategy(),
        metrics(),
        owner_gate=False,
        contract_id="contract-1",
        permit=permit(),
        action="deliver",
        action_fn=lambda: seen.append("ran"),
        **verification(),
    )
    assert seen == []
    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"
    assert result.execution_status == "NOT_EXECUTED"
    assert result.execution is None


def test_boolean_owner_gate_does_not_reach_permit_check_or_execute():
    seen = []
    result = GovernedExecutionOrchestrator(autonomous_executor=executor()).run(
        strategy(), metrics(), owner_gate=True, contract_id="contract-1",
        permit=None, action="deliver", action_fn=lambda: seen.append("ran"),
        **verification(),
    )
    assert seen == []
    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"
    assert result.execution_status == "NOT_EXECUTED"
    assert result.execution is None


def test_boolean_owner_gate_cannot_bypass_contract_permit_binding():
    seen = []
    result = GovernedExecutionOrchestrator(autonomous_executor=executor()).run(
        strategy(), metrics(), owner_gate=True, contract_id="contract-1",
        permit=permit("wrong-contract"), action="deliver",
        action_fn=lambda: seen.append("ran"), **verification(),
    )
    assert seen == []
    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"
    assert result.execution_status == "NOT_EXECUTED"
    assert result.execution is None


def test_boolean_owner_gate_does_not_execute_even_when_postcondition_would_fail():
    seen = []
    result = GovernedExecutionOrchestrator(autonomous_executor=executor()).run(
        strategy(), metrics(), owner_gate=True, contract_id="contract-1",
        permit=permit(), action="deliver", action_fn=lambda: seen.append("ran"),
        **verification(lambda: False),
    )
    assert seen == []
    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"
    assert result.execution_status == "NOT_EXECUTED"
    assert result.execution is None


def test_boolean_owner_gate_does_not_require_or_grant_executor_authority():
    seen = []
    result = GovernedExecutionOrchestrator().run(
        strategy(), metrics(), owner_gate=True, contract_id="contract-1",
        permit=permit(), action="deliver", action_fn=lambda: seen.append("ran"),
        **verification(),
    )
    assert seen == []
    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"
    assert result.execution_status == "NOT_EXECUTED"
    assert result.execution is None


def test_missing_contract_id_is_denied_before_selection():
    with pytest.raises(ExecutionOrchestrationDenied, match="contract ID"):
        GovernedExecutionOrchestrator(autonomous_executor=executor()).run(
            strategy(),
            metrics(),
            owner_gate=True,
            contract_id="",
            permit=permit(),
            action="deliver",
            action_fn=lambda: None,
            **verification(),
        )
