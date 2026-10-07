from src.core.omega_worker_elite_orchestrator import (
    EliteOrchestrator,
    GladiatorProposal,
    EliteOrchestrationError,
)


def proposal(**overrides):
    data = {
        "gladiator_id": "g-001",
        "plan": "Produce a verified commercial deliverable.",
        "evidence_quality": 90,
        "value_score": 90,
        "risk_score": 20,
        "cost_score": 20,
    }
    data.update(overrides)
    return GladiatorProposal(**data)


def test_rgb_blue_green_and_aer_are_all_present():
    judgement = EliteOrchestrator().judge(proposal())

    assert judgement.red_attack == ()
    assert judgement.blue_controls
    assert judgement.green_value
    assert judgement.aer_decision == "ALLOW_WITH_CONTROLS"
    assert judgement.owner_gate_required is True


def test_red_risk_escalates_aer():
    judgement = EliteOrchestrator().judge(proposal(risk_score=95))

    assert judgement.red_attack
    assert judgement.aer_decision == "ESCALATE"


def test_low_evidence_is_controlled():
    judgement = EliteOrchestrator().judge(proposal(evidence_quality=50))

    assert judgement.red_attack
    assert judgement.aer_decision == "ALLOW_WITH_CONTROLS"
    assert judgement.owner_gate_required is True


def test_rank_prefers_high_scoring_controlled_proposals():
    engine = EliteOrchestrator()
    ranked = engine.rank([
        proposal(gladiator_id="g-low", value_score=60),
        proposal(gladiator_id="g-high", value_score=95),
    ])

    assert ranked[0].gladiator_id == "g-high"


def test_invalid_score_fails_closed():
    try:
        EliteOrchestrator().judge(proposal(cost_score=101))
    except EliteOrchestrationError:
        return
    raise AssertionError("invalid score must fail closed")
