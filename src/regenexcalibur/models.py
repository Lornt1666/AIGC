from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract


AgentRole = Literal[
    "UNIVERSE_SEEDER",
    "ONTOLOGY_ARCHITECT",
    "AUTO_DESIGNER",
    "AUTO_ENGINEER",
    "AUTO_DEVSECOPS",
    "LIFE_STEWARD",
    "EVOLUTION_STEWARD",
    "REPOSITORY_INTEGRATOR",
]


class UniverseSeed(NexusContract):
    schema_version: Literal["regenexcalibur.universe-seed.v1"]
    universe_name: Literal["RegenExcalibur OS"]
    seeded_by: Literal["Alpha-Omega-Creatir"]
    coordinator: Literal["Justice Gray Maciocha"]
    watermark: Literal["1JGM"]
    core_intent: str = Field(min_length=20, max_length=2000)
    life_domains: tuple[str, ...] = Field(min_length=1, max_length=32)
    success_criteria: tuple[str, ...] = Field(min_length=1, max_length=32)
    recursion_limit: int = Field(default=5, ge=1, le=12)
    execution_mode: Literal["PLAN_ONLY"] = "PLAN_ONLY"
    grants_external_authority: Literal[False] = False

    @model_validator(mode="after")
    def require_unique_lists(self) -> "UniverseSeed":
        for label, values in (
            ("life_domains", self.life_domains),
            ("success_criteria", self.success_criteria),
        ):
            normalized = [item.strip().casefold() for item in values]
            if any(not item for item in normalized):
                raise ValueError(f"{label} entries must not be blank")
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"{label} entries must be unique")
        return self


class AgentProfile(NexusContract):
    role: AgentRole
    mandate: str = Field(min_length=8, max_length=500)
    output_contract: str = Field(min_length=3, max_length=200)
    effect_ceiling: Literal["LOCAL_DETERMINISTIC_PLAN"] = "LOCAL_DETERMINISTIC_PLAN"
    can_spawn_processes: Literal[False] = False
    can_call_providers: Literal[False] = False
    can_mutate_external_systems: Literal[False] = False


class StageResult(NexusContract):
    stage: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,80}$")
    status: Literal["PASS", "BLOCKED_PERMISSION"]
    artifact: str = Field(min_length=1, max_length=1000)


class UniverseReceipt(NexusContract):
    schema_version: Literal["regenexcalibur.universe-receipt.v1"] = (
        "regenexcalibur.universe-receipt.v1"
    )
    receipt_id: str = Field(pattern=r"^RX-[A-F0-9]{24}$")
    universe_name: str
    seed_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    agents: tuple[AgentProfile, ...]
    coordination_loop: tuple[StageResult, ...]
    genesis_pipeline: tuple[StageResult, ...]
    evolution_proposal: dict[str, object]
    terminal_status: Literal["PASS"]
    zero_egress: Literal[True] = True
    provider_calls_performed: Literal[0] = 0
    external_actions_performed: Literal[0] = 0
    authority_granted: Literal[False] = False
    external_action_performed: Literal[False] = False
