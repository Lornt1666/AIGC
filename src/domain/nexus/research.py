from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from src.domain.nexus.contracts import NexusContract


ResearchStage = Literal[
    "DEFINE",
    "SOURCE",
    "RETRIEVE",
    "SCREEN",
    "EXTRACT",
    "TRIANGULATE",
    "CHALLENGE",
    "SYNTHESIZE",
    "VERIFY",
    "PACKAGE",
]


class ResearchSourceTier(NexusContract):
    rank: int = Field(ge=1, le=20)
    source_class: Literal[
        "PRIMARY_OFFICIAL",
        "PRIMARY_EMPIRICAL",
        "EMPLOYER_INTERNAL",
        "SECONDARY_SYNTHESIS",
        "DISCOVERY_ONLY",
    ]
    minimum: int = Field(ge=0, le=100)
    purpose: str = Field(min_length=1)


class ResearchProviderContract(NexusContract):
    provider: str = Field(min_length=1)
    documentation_url: str = Field(pattern=r"^https://")
    interface: str = Field(min_length=1)
    model_selection: Literal["REVALIDATE_CURRENT_SUPPORTED_MODEL"]
    data_source_requirement: str = Field(min_length=1)
    execution_status: Literal["BLOCKED_EXTERNAL"]


class DeepResearchPolicy(NexusContract):
    policy_id: str = Field(pattern=r"^RESEARCH-POLICY-[A-Z0-9_-]{4,64}$")
    schema_version: Literal["aigc.deep-research-procurement.v1"]
    status: Literal["DRAFT"]
    stages: tuple[ResearchStage, ...]
    source_ladder: tuple[ResearchSourceTier, ...]
    minimum_primary_sources: int = Field(ge=2, le=100)
    minimum_independent_domains: int = Field(ge=2, le=100)
    material_claim_citation_coverage_minimum: float = Field(ge=0, le=1)
    unsupported_material_claims_maximum: int = Field(ge=0)
    unresolved_material_conflicts_maximum: int = Field(ge=0)
    require_disconfirming_search: Literal[True] = True
    require_prompt_injection_screening: Literal[True] = True
    require_source_provenance: Literal[True] = True
    provider_contracts: tuple[ResearchProviderContract, ...]
    provider_dispatch_enabled: Literal[False] = False
    grants_execution_authority: Literal[False] = False
    external_publication_enabled: Literal[False] = False

    @model_validator(mode="after")
    def validate_policy_order(self) -> "DeepResearchPolicy":
        expected = (
            "DEFINE", "SOURCE", "RETRIEVE", "SCREEN", "EXTRACT",
            "TRIANGULATE", "CHALLENGE", "SYNTHESIZE", "VERIFY", "PACKAGE",
        )
        if self.stages != expected:
            raise ValueError("deep research stages must use the canonical order")
        ranks = [item.rank for item in self.source_ladder]
        if ranks != sorted(ranks) or len(ranks) != len(set(ranks)):
            raise ValueError("research source ladder ranks must be unique and ordered")
        return self


class ResearchProcurementRequest(NexusContract):
    request_id: str = Field(pattern=r"^RESEARCH-[A-Z0-9_-]{4,80}$")
    question: str = Field(min_length=20, max_length=4000)
    intended_decision: str = Field(min_length=20, max_length=2000)
    jurisdictions: tuple[str, ...] = ("GLOBAL",)
    maximum_sources: int = Field(default=20, ge=5, le=500)
    maximum_spend_cad: Decimal = Field(default=Decimal("0.00"), ge=0, le=100000)
    execution_authorized: Literal[False] = False
    publication_authorized: Literal[False] = False

    @field_validator("maximum_spend_cad")
    @classmethod
    def require_currency_precision(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("maximum_spend_cad supports at most two decimal places")
        return value

    @model_validator(mode="after")
    def validate_jurisdictions(self) -> "ResearchProcurementRequest":
        if not self.jurisdictions or any(not item.strip() for item in self.jurisdictions):
            raise ValueError("at least one non-empty jurisdiction is required")
        normalized = [item.casefold() for item in self.jurisdictions]
        if len(normalized) != len(set(normalized)):
            raise ValueError("research jurisdictions must be unique")
        return self
