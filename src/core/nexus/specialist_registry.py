from __future__ import annotations

from dataclasses import dataclass

from src.domain.nexus.contracts import WorkOrder


@dataclass(frozen=True)
class SpecialistDefinition:
    specialist_id: str
    domain: str
    capabilities: tuple[str, ...]
    external_action_allowed: bool = False


SPECIALISTS = (
    SpecialistDefinition("SPC-PYTHON", "software", ("python", "architecture")),
    SpecialistDefinition("SPC-SECURITY", "software", ("security", "threat_model")),
    SpecialistDefinition("SPC-TEST", "software", ("testing", "verification_design")),
    SpecialistDefinition("SPC-CLOUD", "software", ("cloud", "infrastructure")),
    SpecialistDefinition("SPC-UX", "software", ("ux", "dashboard")),
    SpecialistDefinition("SPC-MECHANICAL", "engineering", ("mechanical",)),
    SpecialistDefinition("SPC-ELECTRICAL", "engineering", ("electrical",)),
    SpecialistDefinition("SPC-CONTROLS", "engineering", ("controls",)),
    SpecialistDefinition("SPC-THERMAL", "engineering", ("thermal",)),
    SpecialistDefinition("SPC-MANUFACTURING", "engineering", ("manufacturing",)),
    SpecialistDefinition("SPC-SAFETY", "engineering", ("safety",)),
    SpecialistDefinition("SPC-MARKET", "business", ("market_research",)),
    SpecialistDefinition("SPC-FINANCE", "business", ("finance",)),
    SpecialistDefinition("SPC-COMPLIANCE", "business", ("legal_compliance",)),
    SpecialistDefinition("SPC-PRODUCT", "business", ("product",)),
    SpecialistDefinition("SPC-OPERATIONS", "business", ("operations",)),
)


def select_specialists(work_order: WorkOrder) -> tuple[SpecialistDefinition, ...]:
    tags = {tag.lower() for tag in work_order.domain_tags}
    selected = []
    for specialist in SPECIALISTS:
        if specialist.domain in tags or tags.intersection(specialist.capabilities):
            selected.append(specialist)
    return tuple(selected)
