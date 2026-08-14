from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract


EmploymentActionType = Literal[
    "DISCOVER_JOBS",
    "NORMALIZE_JOB",
    "SCAM_ANALYSIS",
    "ELIGIBILITY_ANALYSIS",
    "FIT_SCORING",
    "EMPLOYER_RESEARCH",
    "TAILOR_RESUME",
    "DRAFT_COVER_LETTER",
    "DRAFT_APPLICATION_ANSWERS",
    "ATS_NAVIGATE",
    "ATS_PREFILL_SAFE_FIELDS",
    "SUBMIT_APPLICATION",
    "SEND_RECRUITER_MESSAGE",
    "ANSWER_CALL",
    "SPEAK_TO_CALLER",
    "NEGOTIATE",
    "INTERVIEW_DIALOGUE",
    "ASK_RECRUITER_QUESTION",
    "DISCLOSE_SENSITIVE_IDENTITY",
]


class EmploymentOpsCapabilityProfile(NexusContract):
    """Desired Employment-OPS capabilities. Truth does not imply transport readiness."""

    profile_id: str = Field(pattern=r"^EOPS-[A-Z0-9_-]{6,64}$")
    hyperalpha_employment_ops: Literal[True] = True
    maximal_safe_autonomy: Literal[True] = True

    autonomous_job_discovery: Literal[True] = True
    autonomous_normalization: Literal[True] = True
    autonomous_scam_analysis: Literal[True] = True
    autonomous_eligibility_analysis: Literal[True] = True
    autonomous_fit_scoring: Literal[True] = True
    autonomous_employer_research: Literal[True] = True

    autonomous_resume_tailoring: Literal[True] = True
    autonomous_cover_letters: Literal[True] = True
    autonomous_application_answer_drafting: Literal[True] = True
    autonomous_ats_navigation: Literal[True] = True
    autonomous_safe_field_prefill: Literal[True] = True

    automatic_call_answering: Literal[True] = True
    automatic_speech_to_caller: Literal[True] = True
    automatic_negotiation: Literal[True] = True
    autonomous_interview_dialogue: Literal[True] = True
    autonomous_recruiter_questioning: Literal[True] = True
    real_time_stt: Literal[True] = True
    real_time_tts: Literal[True] = True

    candidate_truth_binding: Literal["REQUIRED"] = "REQUIRED"
    application_context_binding: Literal["REQUIRED"] = "REQUIRED"
    negotiation_envelope: Literal["REQUIRED"] = "REQUIRED"

    human_live_takeover: Literal["ALWAYS_AVAILABLE"] = "ALWAYS_AVAILABLE"
    emergency_stop: Literal[True] = True

    self_authorization: Literal[False] = False
    model_consensus_as_authority: Literal[False] = False
    memory_as_authority: Literal[False] = False
    evidence_as_authority: Literal[False] = False

    unsupported_candidate_claims: Literal["PROHIBITED"] = "PROHIBITED"
    identity_misrepresentation: Literal["PROHIBITED"] = "PROHIBITED"
    sensitive_identity_disclosure: Literal["PROHIBITED"] = "PROHIBITED"

    indeterminate_auto_retry: Literal[False] = False
    read_only_reconciliation: Literal["REQUIRED"] = "REQUIRED"

    provider_neutrality: Literal[True] = True
    telephony_transport_neutrality: Literal[True] = True
    ats_provider_neutrality: Literal[True] = True
    continuous_calibration: Literal[True] = True
    continuous_evolution: Literal[True] = True
    no_blind_automation: Literal[True] = True
    no_metric_gaming: Literal[True] = True
    no_human_micromanagement: Literal[True] = True


class NegotiationDimension(NexusContract):
    name: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=32)
    minimum: Decimal
    target: Decimal
    stretch: Decimal
    maximum: Decimal
    walk_away: Decimal | None = None
    tradeable: bool = True

    @model_validator(mode="after")
    def ordered_bounds(self) -> "NegotiationDimension":
        if not self.minimum <= self.target <= self.stretch <= self.maximum:
            raise ValueError("negotiation bounds must satisfy minimum <= target <= stretch <= maximum")
        return self


class NegotiationAuthorityEnvelope(NexusContract):
    envelope_id: str = Field(pattern=r"^NEG-[A-Z0-9_-]{6,64}$")
    dimensions: tuple[NegotiationDimension, ...]
    may_accept_binding_offer: Literal[False] = False
    may_sign_contract: Literal[False] = False
    may_disclose_government_id: Literal[False] = False
    may_disclose_banking_information: Literal[False] = False
    may_make_legal_attestation: Literal[False] = False

    @model_validator(mode="after")
    def unique_dimensions(self) -> "NegotiationAuthorityEnvelope":
        names = [item.name.casefold() for item in self.dimensions]
        if len(names) != len(set(names)):
            raise ValueError("negotiation dimension names must be unique")
        return self


class EmploymentOpsReadiness(NexusContract):
    """Empirical activation state kept separate from requested capability flags."""

    capability_profile_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    ats_transport_verified: bool = False
    telephony_transport_verified: bool = False
    stt_verified: bool = False
    tts_verified: bool = False
    consent_and_jurisdiction_policy_verified: bool = False
    emergency_stop_verified: bool = False
    application_submission_canary_verified: bool = False
    autonomous_call_canary_verified: bool = False
    autonomous_negotiation_canary_verified: bool = False
    operationally_active: bool = False

    @model_validator(mode="after")
    def activation_requires_empirical_evidence(self) -> "EmploymentOpsReadiness":
        required = (
            self.ats_transport_verified,
            self.telephony_transport_verified,
            self.stt_verified,
            self.tts_verified,
            self.consent_and_jurisdiction_policy_verified,
            self.emergency_stop_verified,
            self.application_submission_canary_verified,
            self.autonomous_call_canary_verified,
            self.autonomous_negotiation_canary_verified,
        )
        if self.operationally_active and not all(required):
            raise ValueError("operational activation requires all external canary and safety evidence")
        return self
