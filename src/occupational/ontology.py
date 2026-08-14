from __future__ import annotations

from datetime import date
from enum import IntEnum, StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompetencyLevel(IntEnum):
    UNKNOWN = 0
    EXPOSED = 1
    LEARNING = 2
    ASSISTED = 3
    DEMONSTRATED = 4
    INDEPENDENT = 5
    VERIFIED = 6
    ADVANCED = 7
    EXPERT = 8
    STALE = 9
    REVALIDATION_REQUIRED = 10


class OccupationalRisk(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"


class CredentialStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ScopeOfPractice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    independently_permitted: tuple[str, ...] = ()
    permitted_with_review: tuple[str, ...] = ()
    credential_restricted: tuple[str, ...] = ()
    prohibited: tuple[str, ...] = ()
    jurisdiction_dependencies: tuple[str, ...] = ()


class StandardOfPractice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    quality_dimensions: tuple[str, ...]
    required_evaluator_profile: str
    minimum_evidence_types: tuple[str, ...] = ()


class CredentialRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    credential_id: str
    holder: str
    issuer: str
    credential_type: str
    jurisdiction: str | None = None
    issued_at: date | None = None
    expires_at: date | None = None
    verification_source: str | None = None
    verification_status: CredentialStatus = CredentialStatus.UNVERIFIED
    scope_granted: tuple[str, ...] = ()


class CompetencyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    competency_id: str
    domain: str
    level: CompetencyLevel
    evidence_receipt_ids: tuple[str, ...] = ()
    evaluator_ids: tuple[str, ...] = ()
    successful_commission_ids: tuple[str, ...] = ()
    failed_commission_ids: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    limitations: tuple[str, ...] = ()
    last_verified: date | None = None
    revalidation_date: date | None = None

    @model_validator(mode="after")
    def verified_levels_require_evidence(self) -> "CompetencyRecord":
        if self.level in {CompetencyLevel.VERIFIED, CompetencyLevel.ADVANCED, CompetencyLevel.EXPERT} and not self.evidence_receipt_ids:
            raise ValueError("verified-or-higher competency requires evidence receipts")
        return self


class ExperienceNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    experience_id: str
    commission_id: str
    discipline_id: str
    specialization_id: str | None = None
    role_ids: tuple[str, ...] = ()
    difficulty: Literal["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
    method_genome_ids: tuple[str, ...] = ()
    artifact_digests: tuple[str, ...] = ()
    outcome: Literal["ACCEPTED", "PARTIAL", "FAILED", "CANCELLED"]
    evaluator_result_ids: tuple[str, ...] = ()
    evidence_receipt_ids: tuple[str, ...] = ()
    human_review_required: bool
    rework_cycles: int = Field(ge=0)

    @model_validator(mode="after")
    def accepted_requires_evidence(self) -> "ExperienceNode":
        if self.outcome == "ACCEPTED" and not self.evidence_receipt_ids:
            raise ValueError("accepted experience must be evidence-backed")
        return self


class DevelopmentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_id: str
    target_competency_id: str
    current_level: CompetencyLevel
    required_level: CompetencyLevel
    gaps: tuple[str, ...]
    development_actions: tuple[str, ...]
    promotion_evidence_requirements: tuple[str, ...]


class InterdisciplinaryPractice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    practice_id: str
    contributing_disciplines: tuple[str, ...] = Field(min_length=2)
    competency_requirements: tuple[str, ...]
    synthesis_method_genomes: tuple[str, ...]
    evaluator_profile: str


class DisciplineProfileV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    discipline_id: str
    profession_id: str
    occupation_id: str
    specializations: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    capabilities: tuple[str, ...]
    skills: tuple[str, ...] = ()
    techniques: tuple[str, ...] = ()
    scope_of_practice: ScopeOfPractice
    standard_of_practice: StandardOfPractice
    occupational_risk_ceiling: OccupationalRisk
    credential_requirements: tuple[str, ...] = ()
    tool_capabilities: tuple[str, ...] = ()
    method_genomes: tuple[str, ...] = ()


class Engagement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    engagement_id: str
    client_id: str
    commission_ids: tuple[str, ...]
    deliverables: tuple[str, ...]
    deadlines: tuple[str, ...] = ()
    compensation_terms: str | None = None
    confidentiality_terms: tuple[str, ...] = ()
    ip_terms: tuple[str, ...] = ()
    communication_rules: tuple[str, ...] = ()
    acceptance_conditions: tuple[str, ...] = ()
    termination_conditions: tuple[str, ...] = ()


class CommissionEconomics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    commission_id: str
    expected_compensation: float = Field(ge=0)
    estimated_execution_cost: float = Field(ge=0)
    model_api_cost: float = Field(ge=0)
    compute_cost: float = Field(ge=0)
    human_review_cost: float = Field(ge=0)
    opportunity_cost: float = Field(ge=0)
    risk_cost: float = Field(ge=0)
    portfolio_value: float = 0
    learning_value: float = 0
    strategic_value: float = 0

    @property
    def expected_utility(self) -> float:
        return (
            self.expected_compensation + self.portfolio_value + self.learning_value + self.strategic_value
            - self.estimated_execution_cost - self.model_api_cost - self.compute_cost
            - self.human_review_cost - self.opportunity_cost - self.risk_cost
        )


class CareerTrajectory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    career_id: str
    objective_ids: tuple[str, ...] = ()
    competency_ids: tuple[str, ...] = ()
    experience_ids: tuple[str, ...] = ()
    credential_ids: tuple[str, ...] = ()
    development_plan_ids: tuple[str, ...] = ()
    portfolio_evidence_ids: tuple[str, ...] = ()
    reputation_evidence_ids: tuple[str, ...] = ()


class OccupationalRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    registry_version: str
    disciplines: tuple[DisciplineProfileV2, ...]
    interdisciplinary_practices: tuple[InterdisciplinaryPractice, ...] = ()

    def discipline(self, discipline_id: str) -> DisciplineProfileV2:
        for discipline in self.disciplines:
            if discipline.discipline_id == discipline_id:
                return discipline
        raise KeyError(discipline_id)


def action_permitted(*, capability_present: bool, competency_sufficient: bool, scope_permits: bool, authority_valid: bool, jurisdiction_valid: bool) -> bool:
    return all((capability_present, competency_sufficient, scope_permits, authority_valid, jurisdiction_valid))
