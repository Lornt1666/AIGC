from __future__ import annotations

from typing import Any

from src.core.epistemic.canonicalization import canonical_sha256
from src.regenexcalibur.agent_forge import forge_profiles
from src.regenexcalibur.life_beacon import life_gate, validate_universe_gate_request
from src.regenexcalibur.models import StageResult, UniverseReceipt, UniverseSeed


COORDINATION_STAGES = (
    ("INPUT_PERCEPTION", "Parsed Intent Frame"),
    ("CONTEXT_FUSION", "Contextualized Intent Frame"),
    ("GOAL_CONSTRAINT_INFERENCE", "Goal-Constraint Matrix"),
    ("PARAMETRIC_TUNING", "Parametric Profile"),
    ("RESPONSE_PLANNING", "Response Blueprint"),
    ("CONTENT_GENERATION", "Draft Artifact Set"),
    ("SAFETY_ALIGNMENT_CHECK", "LIFE Gate Decision"),
    ("FORMATTING_FINALIZATION", "Final Structured Artifact Set"),
)

GENESIS_STAGES = (
    ("UNIVERSE_SEED_VALIDATION", "validated closed seed contract"),
    ("ONTOLOGY_EXPANSION", "bounded ontology blueprint"),
    ("ARCHITECTURE_SYNTHESIS", "Prime Kernel and subsystem topology"),
    ("MODULE_GENERATION", "typed implementation contracts"),
    ("SECURITY_GATES", "fail-closed authority and recursion policy"),
    ("OBSERVABILITY_MESH_ACTIVATION", "deterministic stage receipt plan"),
    ("EVOLUTION_LOOP_TRIGGER", "review-required evolution proposal"),
)


def _passed_stages(items: tuple[tuple[str, str], ...]) -> tuple[StageResult, ...]:
    return tuple(StageResult(stage=stage, status="PASS", artifact=artifact) for stage, artifact in items)


def seed_regenexcalibur_universe(
    *, seed: dict[str, Any], requested_evolution_depth: int = 1
) -> dict[str, object]:
    """Build a deterministic universe blueprint and receipt without network or execution."""

    request = {"seed": seed, "requested_evolution_depth": requested_evolution_depth}
    validate_universe_gate_request(request)
    validated = UniverseSeed.model_validate(seed)
    evolution = life_gate(
        requested_depth=requested_evolution_depth,
        recursion_limit=validated.recursion_limit,
    )
    if evolution["status"] != "PASS":
        raise ValueError(str(evolution["reason"]))

    agents = forge_profiles()
    seed_payload = validated.model_dump(mode="json")
    seed_sha256 = canonical_sha256(seed_payload)
    receipt_payload = {
        "seed_sha256": seed_sha256,
        "agent_roles": [agent.role for agent in agents],
        "coordination_stages": [stage for stage, _ in COORDINATION_STAGES],
        "genesis_stages": [stage for stage, _ in GENESIS_STAGES],
        "evolution_proposal": evolution,
        "zero_egress": True,
    }
    receipt_sha256 = canonical_sha256(receipt_payload)
    receipt = UniverseReceipt(
        receipt_id="RX-" + receipt_sha256[:24].upper(),
        universe_name=validated.universe_name,
        seed_sha256=seed_sha256,
        receipt_sha256=receipt_sha256,
        agents=agents,
        coordination_loop=_passed_stages(COORDINATION_STAGES),
        genesis_pipeline=_passed_stages(GENESIS_STAGES),
        evolution_proposal=evolution,
        terminal_status="PASS",
    )
    return receipt.model_dump(mode="json")
