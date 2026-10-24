from src.core.omega_worker_coliseum import ColiseumOrchestrator
from src.core.omega_worker_elite_orchestrator import GladiatorProposal


def proposal(**overrides):
    data = {
        "gladiator_id": "g-001",
        "plan": "Produce a verified deliverable.",
        "evidence_quality": 90,
        "value_score": 90,
        "risk_score": 20,
        "cost_score": 20,
    }
    data.update(overrides)
    return GladiatorProposal(**data)


def test_boolean_owner_gate_cannot_claim_approval():
    result = ColiseumOrchestrator().run(
        "opp-1",
        [proposal()],
        owner_gate=True,
    )

    assert result.winner_gladiator_id == "g-001"
    assert result.owner_gate_required is True
    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"


def test_missing_owner_gate_stays_awaiting_verified_approval():
    result = ColiseumOrchestrator().run("opp-1", [proposal()])

    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"


def test_escalated_proposal_has_no_eligible_winner():
    result = ColiseumOrchestrator().run(
        "opp-1",
        [proposal(evidence_quality=90, risk_score=95)],
        owner_gate=True,
    )

    assert result.winner_gladiator_id is None
    assert result.selection_status == "NO_ELIGIBLE_WINNER"


def test_duplicate_gladiator_ids_are_rejected():
    try:
        ColiseumOrchestrator().run(
            "opp-1",
            [proposal(), proposal(plan="Alternative plan")],
        )
    except ValueError as exc:
        assert "Duplicate Gladiator IDs" in str(exc)
    else:
        raise AssertionError("duplicate Gladiator IDs must be rejected")
