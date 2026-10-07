import json
from pathlib import Path

from src.core.omega_worker_gladiator_strategy import GladiatorStrategyFactory


SCHEMA = Path("schemas/aigc_omega_worker_v0_1/gladiator_strategy_contract.schema.json")


def valid():
    return {
        "contract_version": "AIGC-OMEGA-GLADIATOR-STRATEGY-0.1",
        "strategy_id": "s-001",
        "task_id": "task-001",
        "opportunity_id": "opp-001",
        "gladiator_id": "g-001",
        "objective": "Produce a verified deliverable.",
        "plan": "Research, challenge, produce, verify.",
        "resource_budget": 10,
        "evidence_requirements": ["source evidence"],
        "termination_conditions": ["acceptance verified"],
        "self_challenge_questions": ["What could invalidate this plan?"],
    }


def test_canonical_schema_exists_and_is_closed():
    schema = json.loads(SCHEMA.read_text())
    assert schema["additionalProperties"] is False
    assert schema["properties"]["contract_version"]["const"] == "AIGC-OMEGA-GLADIATOR-STRATEGY-0.1"
    assert "task_id" in schema["required"]


def test_factory_binds_strategy_to_task_and_opportunity():
    contract = GladiatorStrategyFactory().build(valid())
    assert contract.strategy_id == "s-001"
    assert contract.opportunity_id == "opp-001"


def test_factory_remains_non_executing():
    factory = GladiatorStrategyFactory()
    assert not hasattr(factory, "execute")
