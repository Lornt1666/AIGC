from src.core.omega_worker_gladiator_strategy import GladiatorStrategyFactory
from src.core.omega_worker_strategy_coliseum import (
    StrategyColiseumAdapter,
    StrategyColiseumIntegrationError,
    StrategyProposalMetrics,
)


def strategy():
    return GladiatorStrategyFactory().build(
        {
            "strategy_id": "s-001",
            "opportunity_id": "opp-001",
            "gladiator_id": "g-001",
            "objective": "Produce a verified deliverable.",
            "plan": "Research, challenge, produce, verify.",
            "resource_budget": 10,
            "evidence_requirements": ["source evidence"],
            "termination_conditions": ["acceptance verified"],
            "self_challenge_questions": ["What could invalidate this plan?"],
        }
    )


def metrics():
    return StrategyProposalMetrics(
        evidence_quality=90,
        value_score=90,
        risk_score=10,
        cost_score=10,
    )


def test_strategy_flows_into_existing_coliseum_without_owner_bypass():
    result = StrategyColiseumAdapter().run(strategy(), metrics())
    assert result.opportunity_id == "opp-001"
    assert result.winner_gladiator_id == "g-001"
    assert result.selection_status == "AWAITING_OWNER_GATE"
    assert result.owner_gate_required is True


def test_boolean_owner_gate_cannot_claim_verified_approval():
    result = StrategyColiseumAdapter().run(strategy(), metrics(), owner_gate=True)
    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"
    assert result.owner_gate_required is True


def test_unready_strategy_is_blocked_before_coliseum():
    contract = strategy()
    blocked = contract.__class__(**{**contract.__dict__, "termination_conditions": ()})

    try:
        StrategyColiseumAdapter().run(blocked, metrics())
    except StrategyColiseumIntegrationError:
        return
    raise AssertionError("unready strategy must not enter Coliseum")


def test_adapter_does_not_execute():
    adapter = StrategyColiseumAdapter()
    assert not hasattr(adapter, "execute")
