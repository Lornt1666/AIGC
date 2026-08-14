from __future__ import annotations

from src.regenexcalibur.models import AgentProfile, AgentRole


_PROFILES: dict[AgentRole, tuple[str, str]] = {
    "UNIVERSE_SEEDER": ("Validate and normalize a supplied universe seed.", "Universe Seed Document"),
    "ONTOLOGY_ARCHITECT": ("Build a bounded conceptual skeleton.", "RegenExcalibur Ontology"),
    "AUTO_DESIGNER": ("Synthesize reviewable architecture proposals.", "OS Architecture Blueprint"),
    "AUTO_ENGINEER": ("Specify typed modules, APIs, and schemas.", "Implementation Contracts"),
    "AUTO_DEVSECOPS": ("Specify test, security, release, and recovery gates.", "DevSecOps Plan"),
    "LIFE_STEWARD": ("Apply human-safety, ecological, factual, and authority constraints.", "LIFE Decision"),
    "EVOLUTION_STEWARD": ("Propose versioned changes within recursion limits.", "Evolution Proposal"),
    "REPOSITORY_INTEGRATOR": ("Map approved artifacts into repository paths.", "Repository Map"),
}


def forge_profiles() -> tuple[AgentProfile, ...]:
    """Return descriptors, not autonomous processes or provider-backed agents."""

    return tuple(
        AgentProfile(role=role, mandate=mandate, output_contract=output)
        for role, (mandate, output) in _PROFILES.items()
    )
