from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BusinessIdentity(StrictModel):
    entity_name: str = Field(min_length=1, max_length=240)
    legal_structure: str = Field(min_length=1, max_length=240)
    headquarters: str = Field(min_length=1, max_length=500)
    operational_region: str = Field(min_length=1, max_length=500)
    founding_year: int = Field(ge=1900, le=2100)
    headcount: int = Field(ge=0, le=1_000_000)
    primary_sector: str = Field(min_length=1, max_length=500)
    technology_readiness_level: str = Field(min_length=1, max_length=500)
    annual_rd_spend_cad: float = Field(ge=0)
    canadian_controlled_private_corporation: bool
    verification_status: Literal["operator_attestation_required"]
    verification_note: str = Field(min_length=1, max_length=2000)
    external_action_performed: Literal[False]


class GrantPortal(StrictModel):
    portal_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    organization: str = Field(min_length=1, max_length=500)
    official_portal_url: str = Field(pattern=r"^https://", max_length=2000)
    connector_status: Literal["not_configured"]
    ingestion_mode: Literal["disabled_pending_phase5_approval"]
    terms_review_status: Literal["not_reviewed"]
    notes: str = Field(min_length=1, max_length=2000)


class GrantPortalCatalog(StrictModel):
    catalog_id: str = Field(min_length=1, max_length=160)
    mode: Literal["local_draft_only"]
    recommended_first_portal_id: str = Field(
        pattern=r"^[a-z][a-z0-9_]{2,79}$"
    )
    recommendation_basis: str = Field(min_length=1, max_length=2000)
    live_ingestion_enabled: Literal[False]
    external_action_performed: Literal[False]
    portals: list[GrantPortal] = Field(min_length=1, max_length=20)


class TruthfulnessPolicy(StrictModel):
    unsupported_financial_claims_blocked: Literal[True]
    operator_attestation_required_for_business_identity: Literal[True]
    program_eligibility_requires_official_guideline_review: Literal[True]
    winning_historical_corpus_requires_rights_review: Literal[True]


class ExternalActionPolicy(StrictModel):
    live_portal_ingestion_enabled: Literal[False]
    credential_use_enabled: Literal[False]
    external_submission_enabled: Literal[False]
    phase5_approval_required: Literal[True]
    operator_exact_payload_review_required: Literal[True]
    manual_handoff_only: Literal[True]


class SecretPolicy(StrictModel):
    raw_secret_storage_forbidden: Literal[True]
    secret_manager_reference_only: Literal[True]


class AuditPolicy(StrictModel):
    append_only_required: Literal[True]
    accepted_history_mutation_forbidden: Literal[True]
    ai_use_disclosure_required_when_applicable: Literal[True]


class ConstitutionalPolicy(StrictModel):
    policy_id: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=40)
    runtime_mode: Literal["local_draft_only"]
    truthfulness: TruthfulnessPolicy
    external_actions: ExternalActionPolicy
    secrets: SecretPolicy
    audit: AuditPolicy
    external_action_performed: Literal[False]


class GrantEligibilityCriteria(StrictModel):
    eligible_regions: list[str] = Field(default_factory=list, max_length=30)
    min_trl: int | None = Field(default=None, ge=1, le=9)
    max_trl: int | None = Field(default=None, ge=1, le=9)
    min_headcount: int | None = Field(default=None, ge=0)
    max_headcount: int | None = Field(default=None, ge=0)
    requires_ccpc: bool | None = None
    minimum_annual_rd_spend_cad: float | None = Field(default=None, ge=0)
    funding_ceiling_cad: float | None = Field(default=None, gt=0)
    required_matching_ratio: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    source_verification_status: Literal["operator_review_required"] = (
        "operator_review_required"
    )


class GrantOpportunity(StrictModel):
    grant_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,80}$")
    portal_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    grant_name: str = Field(min_length=1, max_length=240)
    guideline_url: str = Field(pattern=r"^https://", max_length=2000)
    summary: str = Field(min_length=1, max_length=10_000)
    eligibility: GrantEligibilityCriteria


class ProjectDetails(StrictModel):
    project_title: str = Field(min_length=1, max_length=240)
    project_summary: str = Field(min_length=1, max_length=10_000)
    requested_funding_cad: float = Field(gt=0, le=100_000_000)
    matching_contribution_cad: float = Field(ge=0, le=100_000_000)
    duration_months: int = Field(default=12, ge=1, le=60)
    evidence_references: list[str] = Field(default_factory=list, max_length=50)


class GrantApplicationRequest(StrictModel):
    grant: GrantOpportunity
    project: ProjectDetails
