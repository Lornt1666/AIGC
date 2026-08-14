from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.domain.nexus.contracts import NexusContract

PillarName = Literal["ACADEMIC", "DISCIPLINARY", "OCCUPATIONAL", "NEXT_GEN"]


class KnowledgePillar(NexusContract):
    pillar: PillarName
    findings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()


class OperationalStrategyArtifact(NexusContract):
    strategy_id: str = Field(pattern=r"^STRAT-[A-Z0-9_-]{6,64}$")
    work_order_id: str
    strategic_blueprint: str = Field(min_length=1, max_length=20000)
    operational_matrix: tuple[str, ...] = ()
    synaptic_advantages: tuple[str, ...] = ()
    academic_frontier: KnowledgePillar
    disciplinary_standards: KnowledgePillar
    occupational_praxis: KnowledgePillar
    next_gen_multipliers: KnowledgePillar
    recommended_specialists: tuple[str, ...] = ()
    compliance_constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    external_action_performed: Literal[False] = False
