import pytest

from src.core.omega_worker_opportunity_acquisition import (
    OpportunityAcquisitionEngine,
    OpportunityDecisionError,
)


def base():
    return {
        "opportunity_id": "opp-001",
        "capability_score": 90,
        "commercial_score": 85,
        "strategic_score": 80,
        "effort_score": 30,
        "risk_score": 25,
        "evidence_quality": 90,
    }


def test_target_requires_owner_gate():
    engine = OpportunityAcquisitionEngine()
    decision = engine.decide(engine.assess(base()))

    assert decision.decision == "TARGET"
    assert decision.owner_gate_required is True


def test_low_evidence_waits():
    engine = OpportunityAcquisitionEngine()
    data = base()
    data["evidence_quality"] = 20

    decision = engine.decide(engine.assess(data))

    assert decision.decision == "WAIT"
    assert decision.owner_gate_required is True


def test_high_risk_escalates():
    engine = OpportunityAcquisitionEngine()
    data = base()
    data["risk_score"] = 90

    decision = engine.decide(engine.assess(data))

    assert decision.decision == "ESCALATE"
    assert decision.owner_gate_required is True


def test_low_value_rejects():
    engine = OpportunityAcquisitionEngine()
    data = base()
    data["capability_score"] = 30
    data["commercial_score"] = 30
    data["strategic_score"] = 30

    decision = engine.decide(engine.assess(data))

    assert decision.decision == "REJECT"


def test_invalid_score_fails_closed():
    engine = OpportunityAcquisitionEngine()
    data = base()
    data["risk_score"] = 101

    with pytest.raises(OpportunityDecisionError):
        engine.assess(data)
