from __future__ import annotations

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.specialist_registry import select_specialists
from src.domain.epistemic.models import ArtifactState, Entity, Relation
from src.domain.nexus.contracts import WorkOrder
from src.domain.nexus.odse import KnowledgePillar, OperationalStrategyArtifact


def select_synapsis_weights(work_order: WorkOrder) -> dict[str, float]:
    """Return a deterministic qualitative weighting profile from WorkOrder tags.

    These weights route attention only; they are not represented as calibrated empirical scores.
    """
    tags = {tag.lower() for tag in work_order.domain_tags}
    if tags.intersection({"safety", "engineering", "compliance", "medical"}):
        return {"academic": 0.30, "disciplinary": 0.35, "occupational": 0.25, "next_gen": 0.10}
    if tags.intersection({"research", "science", "experimental"}):
        return {"academic": 0.40, "disciplinary": 0.20, "occupational": 0.15, "next_gen": 0.25}
    if tags.intersection({"ux", "product", "operations", "business"}):
        return {"academic": 0.15, "disciplinary": 0.20, "occupational": 0.40, "next_gen": 0.25}
    return {"academic": 0.25, "disciplinary": 0.25, "occupational": 0.30, "next_gen": 0.20}


def synthesize_strategy(
    *,
    work_order: WorkOrder,
    academic: KnowledgePillar,
    disciplinary: KnowledgePillar,
    occupational: KnowledgePillar,
    next_gen: KnowledgePillar,
) -> OperationalStrategyArtifact:
    expected = {
        "ACADEMIC": academic,
        "DISCIPLINARY": disciplinary,
        "OCCUPATIONAL": occupational,
        "NEXT_GEN": next_gen,
    }
    for name, pillar in expected.items():
        if pillar.pillar != name:
            raise ValueError(f"ODSE pillar mismatch: expected {name}, observed {pillar.pillar}")

    specialists = tuple(item.specialist_id for item in select_specialists(work_order))
    evidence_refs = tuple(sorted({ref for pillar in expected.values() for ref in pillar.evidence_refs}))
    assumptions = tuple(item for pillar in expected.values() for item in pillar.assumptions)
    uncertainties = tuple(item for pillar in expected.values() for item in pillar.unresolved_questions)
    weights = select_synapsis_weights(work_order)

    blueprint = (
        f"Execute WorkOrder {work_order.work_order_id} by integrating academic evidence, "
        "disciplinary constraints, occupational feasibility, and defensible next-generation multipliers."
    )
    matrix = (
        "Establish evidence-backed problem definition and acceptance criteria.",
        "Apply applicable standards and compliance constraints before optimization.",
        "Translate theory into practitioner-feasible implementation steps.",
        "Evaluate next-generation multipliers only where evidence and maturity justify adoption.",
        "Verify the synthesized artifact before governance promotion.",
    )
    advantages = (
        "Cross-domain assumptions remain explicit instead of being silently blended.",
        "Operational feasibility is evaluated alongside theoretical correctness.",
        "Emerging technology is treated as a bounded multiplier rather than an automatic solution.",
        "Attention weights are WorkOrder-conditioned: " + ", ".join(f"{key}={value:.2f}" for key, value in weights.items()),
    )
    payload = {
        "work_order_id": work_order.work_order_id,
        "blueprint": blueprint,
        "matrix": matrix,
        "advantages": advantages,
        "pillars": {name: pillar.model_dump(mode="json") for name, pillar in expected.items()},
        "specialists": specialists,
    }
    strategy_id = "STRAT-" + canonical_sha256(payload)[:24].upper()

    return OperationalStrategyArtifact(
        strategy_id=strategy_id,
        work_order_id=work_order.work_order_id,
        strategic_blueprint=blueprint,
        operational_matrix=matrix,
        synaptic_advantages=advantages,
        academic_frontier=academic,
        disciplinary_standards=disciplinary,
        occupational_praxis=occupational,
        next_gen_multipliers=next_gen,
        recommended_specialists=specialists,
        assumptions=assumptions,
        uncertainties=uncertainties,
        evidence_refs=evidence_refs,
    )


def strategy_to_artifact_state(
    strategy: OperationalStrategyArtifact,
    *,
    revision: int,
    parent_state_hash: str | None = None,
) -> ArtifactState:
    """Project an ODSE strategy into the frozen ArtifactState graph without extending its schema."""
    root_id = "ENT-" + canonical_sha256({"strategy_id": strategy.strategy_id})[:16].upper()
    root = Entity(
        id=root_id,
        name="ODSE Operational Strategy",
        description=strategy.strategic_blueprint,
        entity_type="artifact",
    )
    entities = [root]
    relations = []
    for pillar in (
        strategy.academic_frontier,
        strategy.disciplinary_standards,
        strategy.occupational_praxis,
        strategy.next_gen_multipliers,
    ):
        entity_id = "ENT-" + canonical_sha256(
            {"strategy_id": strategy.strategy_id, "pillar": pillar.pillar}
        )[:16].upper()
        description = "\n".join(pillar.findings) or f"{pillar.pillar} pillar contains no findings yet."
        entities.append(
            Entity(
                id=entity_id,
                name=f"ODSE {pillar.pillar}",
                description=description[:4000],
                entity_type="domain_concept",
            )
        )
        relations.append(
            Relation(
                id="REL-" + canonical_sha256({"root": root_id, "pillar": entity_id})[:16].upper(),
                source_id=root_id,
                target_id=entity_id,
                relation_type="synthesizes",
                description="Operational strategy integrates this ODSE knowledge pillar.",
                evidence_refs=pillar.evidence_refs,
            )
        )

    return ArtifactState(
        stage="odse_strategy",
        revision=revision,
        entities=tuple(entities),
        relations=tuple(relations),
        parent_state_hash=parent_state_hash,
    )
