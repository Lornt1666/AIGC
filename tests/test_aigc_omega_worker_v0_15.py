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
        contract_version="AIGC-OMEGA-STRATEGY-0.10",
        strategy_id="strategy-1",
        task_id="task-1",
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
    return StrategyProposalMetrics(
        evidence_quality=90,
        value_score=90,
        risk_score=10,
        cost_score=10,
    )


def permit():
    return ExecutionPermit(
        permit_id="permit-1",
        contract_id="task-1",
        authorized_action="deliver",
        approved_by="owner",
        policy_reference="policy-1",
        active=True,
    )


def executor():
    return BoundedAutonomousExecutor(
        AutonomousExecutionPolicy("policy-1", ("deliver",), 1)
    )


def verification():
    return {
        "verification_evidence": "delivery verified",
        "postcondition": Postcondition(
            "condition-1", "task-1", "delivery is verified"
        ),
        "verification_check": lambda: True,
    }


def test_end_to_end_owner_accepted_selection_executes_and_verifies():
    seen = []
    result = GovernedExecutionOrchestrator(
        autonomous_executor=executor()
    ).run(
        strategy(),
        metrics(),
        owner_gate=True,
        permit=permit(),
        action="deliver",
        action_fn=lambda: seen.append("ran"),
        **verification(),
    )

    assert seen == ["ran"]
    assert result.selection_status == "OWNER_ACCEPTED_SELECTION"
    assert result.execution_status == "VERIFIED"
    assert result.execution is not None
    assert result.execution.verified is True


def test_without_owner_gate_selection_does_not_execute():
    seen = []
    result = GovernedExecutionOrchestrator(
        autonomous_executor=executor()
    ).run(
        strategy(),
        metrics(),
        owner_gate=False,
        permit=permit(),
        action="deliver",
        action_fn=lambda: seen.append("ran"),
        **verification(),
    )

    assert seen == []
    assert result.selection_status == "AWAITING_OWNER_GATE"
    assert result.execution_status == "NOT_EXECUTED"
    assert result.execution is None


def test_owner_accepted_selection_still_requires_permit():
    with pytest.raises(ExecutionOrchestrationDenied, match="execution permit"):
        GovernedExecutionOrchestrator(
            autonomous_executor=executor()
        ).run(
            strategy(),
            metrics(),
            owner_gate=True,
            permit=None,
            action="deliver",
            action_fn=lambda: None,
            **verification(),
        )


def test_contract_binding_is_preserved():
    bad_permit = ExecutionPermit(
        permit_id="permit-1",
        contract_id="wrong-task",
        authorized_action="deliver",
        approved_by="owner",
        policy_reference="policy-1",
        active=True,
    )
    with pytest.raises(ExecutionOrchestrationDenied):
        GovernedExecutionOrchestrator(
            autonomous_executor=executor()
        ).run(
            strategy(),
            metrics(),
            owner_gate=True,
            permit=bad_permit,
            action="deliver",
            action_fn=lambda: None,
            **verification(),
        )


def test_failed_postcondition_blocks_completion():
    seen = []
    with pytest.raises(ExecutionOrchestrationDenied, match="verification"):
        GovernedExecutionOrchestrator(
            autonomous_executor=executor()
        ).run(
            strategy(),
            metrics(),
            owner_gate=True,
            permit=permit(),
            action="deliver",
            action_fn=lambda: seen.append("ran"),
            verification_evidence="delivery checked",
            postcondition=Postcondition(
                "condition-1", "task-1", "delivery is verified"
            ),
            verification_check=lambda: False,
        )
    assert seen == ["ran"]


def test_no_autonomous_executor_means_no_execution_authority():
    with pytest.raises(
        ExecutionOrchestrationDenied, match="autonomous executor"
    ):
        GovernedExecutionOrchestrator().run(
            strategy(),
            metrics(),
            owner_gate=True,
            permit=permit(),
            action="deliver",
            action_fn=lambda: None,
            **verification(),
        )
