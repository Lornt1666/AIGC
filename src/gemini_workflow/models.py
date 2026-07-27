from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpportunityIntake(StrictModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=20, max_length=12_000)
    source_url: HttpUrl
    constraints: list[str] = Field(default_factory=list, max_length=20)
    ai_assistance_permitted: bool
    ai_disclosure_required: bool = True

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip()
            if not item:
                continue
            if len(item) > 400:
                raise ValueError("Each constraint must be 400 characters or fewer")
            normalized.append(item)
        return normalized


class RiskItem(StrictModel):
    severity: Literal["low", "medium", "high", "critical"]
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=3, max_length=500)
    mitigation: str = Field(min_length=3, max_length=500)


class EvidenceObservation(StrictModel):
    input_pointer: str = Field(
        pattern=r"^/(title|description|constraints/[0-9]+)$",
        max_length=80,
    )
    observation: str = Field(min_length=3, max_length=500)
    impact: Literal["positive", "neutral", "negative"]


class GeminiAssessment(StrictModel):
    fit_score: int = Field(ge=0, le=100)
    recommendation: Literal["pursue", "clarify", "decline"]
    rationale: list[str] = Field(min_length=2, max_length=6)
    evidence_basis: list[EvidenceObservation] = Field(min_length=1, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    risks: list[RiskItem] = Field(default_factory=list, max_length=12)
    clarifying_questions: list[str] = Field(default_factory=list, max_length=10)
    proposed_scope: list[str] = Field(default_factory=list, max_length=12)
    ai_use_disclosure: str = Field(min_length=10, max_length=800)
    human_review_required: bool = True


class ProviderUsage(StrictModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    candidate_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class GenerationResult(StrictModel):
    provider: str
    transport: str
    model: str
    response_id: str | None = None
    finish_reason: str | None = None
    latency_ms: int = Field(ge=0)
    usage: ProviderUsage
    assessment: GeminiAssessment
    live_model_call: bool


class PolicyEvaluation(StrictModel):
    outcome: Literal["allow_internal_draft", "clarification_required", "blocked"]
    reasons: list[str] = Field(min_length=1)
    high_impact_review_required: bool = True
    external_action_allowed: bool = False


class HumanDecisionRequest(StrictModel):
    decision: Literal["approve", "deny", "revise"]
    reason: str = Field(min_length=10, max_length=2_000)
    revision_instructions: str = Field(default="", max_length=4_000)

    @field_validator("revision_instructions")
    @classmethod
    def strip_revision_instructions(cls, value: str) -> str:
        return value.strip()

    def validate_for_transition(self) -> None:
        if self.decision == "revise" and not self.revision_instructions:
            raise ValueError("revision_instructions is required for a revise decision")


class WorkflowRecord(StrictModel):
    event_id: str
    event_type: Literal["gemini_execution", "human_decision"]
    run_id: str
    correlation_id: str
    created_at: str
    status: str
    payload: dict[str, Any]
    model_api_call_performed: bool = False
    external_business_action_performed: bool = False
    external_action_performed: bool = False
    record_sha256: str
