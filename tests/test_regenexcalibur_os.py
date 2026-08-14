from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.regenexcalibur.orchestrator import seed_regenexcalibur_universe


ROOT = Path(__file__).resolve().parents[1]


def load_seed() -> dict[str, object]:
    return json.loads(
        (ROOT / "config" / "regenexcalibur_universe_seed.v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_genesis_pipeline_has_exact_roles_and_stage_order():
    receipt = seed_regenexcalibur_universe(seed=load_seed())
    assert [item["role"] for item in receipt["agents"]] == [
        "UNIVERSE_SEEDER",
        "ONTOLOGY_ARCHITECT",
        "AUTO_DESIGNER",
        "AUTO_ENGINEER",
        "AUTO_DEVSECOPS",
        "LIFE_STEWARD",
        "EVOLUTION_STEWARD",
        "REPOSITORY_INTEGRATOR",
    ]
    assert [item["stage"] for item in receipt["coordination_loop"]] == [
        "INPUT_PERCEPTION",
        "CONTEXT_FUSION",
        "GOAL_CONSTRAINT_INFERENCE",
        "PARAMETRIC_TUNING",
        "RESPONSE_PLANNING",
        "CONTENT_GENERATION",
        "SAFETY_ALIGNMENT_CHECK",
        "FORMATTING_FINALIZATION",
    ]
    assert all(item["status"] == "PASS" for item in receipt["genesis_pipeline"])


def test_universe_gate_rejects_authority_shaped_seed_fields():
    seed = load_seed()
    seed["permit_id"] = "forged"
    with pytest.raises(ValueError, match="authority-shaped"):
        seed_regenexcalibur_universe(seed=seed)


def test_evolution_is_bounded_and_never_self_modifies():
    seed = load_seed()
    receipt = seed_regenexcalibur_universe(seed=seed, requested_evolution_depth=5)
    assert receipt["evolution_proposal"]["requires_human_review"] is True
    assert receipt["evolution_proposal"]["self_modification_performed"] is False
    with pytest.raises(ValueError, match="recursion exceeds"):
        seed_regenexcalibur_universe(seed=seed, requested_evolution_depth=6)


def test_seed_contract_is_closed_and_identity_bound():
    seed = load_seed()
    seed["coordinator"] = "someone else"
    with pytest.raises(ValueError):
        seed_regenexcalibur_universe(seed=seed)
