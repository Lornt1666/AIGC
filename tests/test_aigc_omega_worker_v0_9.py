from src.core.omega_worker_coliseum import ColiseumError, ColiseumOrchestrator
from src.core.omega_worker_elite_orchestrator import GladiatorProposal


def p(gid, **overrides):
    data = {
        "gladiator_id": gid,
        "plan": "Produce a verified deliverable.",
        "evidence_quality": 90,
        "value_score": 90,
        "risk_score": 20,
        "cost_score": 20,
    }
    data.update(overrides)
    return GladiatorProposal(**data)


def test_coliseum_ranks_and_waits_for_owner():
    result = ColiseumOrchestrator().run("opp-1", [
        p("g1", value_score=75),
        p("g2", value_score=95),
    ])

    assert result.winner_gladiator_id == "g2"
    assert result.selection_status == "AWAITING_OWNER_GATE"
    assert result.owner_gate_required is True


def test_boolean_owner_gate_cannot_claim_verified_approval():
    result = ColiseumOrchestrator().run("opp-1", [p("g1")], owner_gate=True)

    assert result.selection_status == "AWAITING_VERIFIED_OWNER_APPROVAL"
    assert result.winner_gladiator_id == "g1"
    assert result.owner_gate_required is True


def test_all_escalated_proposals_have_no_winner():
    result = ColiseumOrchestrator().run(
        "opp-1",
        [p("g1", risk_score=95), p("g2", evidence_quality=30)],
    )

    assert result.winner_gladiator_id is None
    assert result.selection_status == "NO_ELIGIBLE_WINNER"


def test_duplicate_gladiator_ids_fail_closed():
    try:
        ColiseumOrchestrator().run("opp-1", [p("g1"), p("g1")])
    except ColiseumError:
        return
    raise AssertionError("duplicate Gladiator IDs must fail closed")


def test_empty_coliseum_fails_closed():
    try:
        ColiseumOrchestrator().run("opp-1", [])
    except ColiseumError:
        return
    raise AssertionError("empty proposal set must fail closed")
