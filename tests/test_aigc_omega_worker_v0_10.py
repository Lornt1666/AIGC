from src.core.omega_worker_gladiator_strategy import (
    GladiatorStrategyError,
    GladiatorStrategyFactory,
)


def data(**overrides):
    value = {
        "strategy_id": "s-001",
        "opportunity_id": "opp-001",
        "gladiator_id": "g-001",
        "objective": "Produce a verified commercial deliverable.",
        "plan": "Research, challenge assumptions, produce, verify.",
        "resource_budget": 10,
        "evidence_requirements": ["source evidence", "deliverable evidence"],
        "termination_conditions": ["acceptance verified", "budget exhausted"],
        "self_challenge_questions": ["What could make this plan wrong?"],
    }
    value.update(overrides)
    return value


def test_strategy_contract_builds_and_assesses_ready():
    factory = GladiatorStrategyFactory()
    contract = factory.build(data())
    assessment = factory.assess(contract)

    assert assessment.ready is True
    assert assessment.challenge_count == 1


def test_missing_evidence_blocks_strategy():
    factory = GladiatorStrategyFactory()
    contract = factory.build(data(evidence_requirements=["proof"]))
    contract = contract.__class__(**{**contract.__dict__, "evidence_requirements": ()})
    assessment = factory.assess(contract)

    assert assessment.ready is False
    assert "Evidence requirements are absent." in assessment.blockers


def test_zero_budget_blocks_execution_planning():
    factory = GladiatorStrategyFactory()
    contract = factory.build(data(resource_budget=0))
    assessment = factory.assess(contract)

    assert assessment.ready is False


def test_invalid_budget_fails_closed():
    try:
        GladiatorStrategyFactory().build(data(resource_budget=-1))
    except GladiatorStrategyError:
        return
    raise AssertionError("negative budget must fail closed")


def test_strategy_does_not_execute():
    factory = GladiatorStrategyFactory()
    contract = factory.build(data())

    assert hasattr(contract, "plan")
    assert not hasattr(factory, "execute")
