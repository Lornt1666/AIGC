from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .domain import ConfidentialityClass, _require_nonnegative, _require_text


class ResourceType(str, Enum):
    LOCAL_CPU = "LOCAL_CPU"
    LOCAL_GPU = "LOCAL_GPU"
    APPLE_NEURAL_ENGINE = "APPLE_NEURAL_ENGINE"
    CORE_ML = "CORE_ML"
    METAL = "METAL"
    CLOUD_CPU = "CLOUD_CPU"
    CLOUD_GPU = "CLOUD_GPU"
    SERVERLESS = "SERVERLESS"
    BATCH = "BATCH"
    AI_MODEL = "AI_MODEL"
    THIRD_PARTY_API = "THIRD_PARTY_API"
    DETERMINISTIC_TOOL = "DETERMINISTIC_TOOL"


class ComputeAdmission(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    NOT_ADMISSIBLE = "NOT_ADMISSIBLE"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"


@dataclass(frozen=True)
class ComputeRequirement:
    requirement_id: str
    workload_class: str
    minimum_quality: float
    minimum_reliability: float
    maximum_latency_ms: int
    maximum_cost_cad: float
    confidentiality_class: ConfidentialityClass
    allowed_jurisdictions: tuple[str, ...]
    allowed_providers: tuple[str, ...] = ()
    prohibited_providers: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    license_must_allow_commercial_use: bool = True

    def __post_init__(self) -> None:
        _require_text("requirement_id", self.requirement_id)
        _require_text("workload_class", self.workload_class)
        for name in ("minimum_quality", "minimum_reliability"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        _require_nonnegative("maximum_latency_ms", self.maximum_latency_ms)
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        if not self.allowed_jurisdictions:
            raise ValueError("allowed_jurisdictions must not be empty")
        if set(self.allowed_providers) & set(self.prohibited_providers):
            raise ValueError("provider cannot be both allowed and prohibited")


@dataclass(frozen=True)
class ComputeCandidate:
    candidate_id: str
    provider: str
    resource_type: ResourceType
    model_or_runtime: str
    region: str
    jurisdiction: str
    confidentiality_capability: ConfidentialityClass
    encryption: str
    estimated_cost_cad: float
    estimated_latency_ms: int
    predicted_quality: float
    predicted_reliability: float
    availability: float
    commercial_use_allowed: bool
    benchmark_evidence_refs: tuple[str, ...]
    capabilities: tuple[str, ...]
    admission: ComputeAdmission
    rejection_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("candidate_id", "provider", "model_or_runtime", "region", "jurisdiction", "encryption"):
            _require_text(name, getattr(self, name))
        _require_nonnegative("estimated_cost_cad", self.estimated_cost_cad)
        _require_nonnegative("estimated_latency_ms", self.estimated_latency_ms)
        for name in ("predicted_quality", "predicted_reliability", "availability"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.admission == ComputeAdmission.NOT_ADMISSIBLE and not self.rejection_reasons:
            raise ValueError("NOT_ADMISSIBLE candidate requires rejection reasons")
        if self.admission == ComputeAdmission.ADMISSIBLE and self.rejection_reasons:
            raise ValueError("ADMISSIBLE candidate cannot carry rejection reasons")

    def satisfies(self, requirement: ComputeRequirement) -> bool:
        if self.admission != ComputeAdmission.ADMISSIBLE:
            return False
        if self.jurisdiction not in requirement.allowed_jurisdictions:
            return False
        if requirement.allowed_providers and self.provider not in requirement.allowed_providers:
            return False
        if self.provider in requirement.prohibited_providers:
            return False
        if self.predicted_quality < requirement.minimum_quality:
            return False
        if self.predicted_reliability < requirement.minimum_reliability:
            return False
        if self.estimated_latency_ms > requirement.maximum_latency_ms:
            return False
        if self.estimated_cost_cad > requirement.maximum_cost_cad:
            return False
        if requirement.license_must_allow_commercial_use and not self.commercial_use_allowed:
            return False
        if not set(requirement.required_capabilities).issubset(self.capabilities):
            return False
        return True


@dataclass(frozen=True)
class ExecutionPortfolio:
    portfolio_id: str
    work_order_id: str
    requirement_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    stage_order: tuple[str, ...]
    fallback_candidate_ids: tuple[str, ...]
    employer_policy_id: str
    verification_route_id: str
    predicted_total_cost_cad: float
    admitted: bool

    def __post_init__(self) -> None:
        for name in ("portfolio_id", "work_order_id", "employer_policy_id", "verification_route_id"):
            _require_text(name, getattr(self, name))
        if not self.requirement_ids:
            raise ValueError("portfolio requires compute requirements")
        if not self.candidate_ids:
            raise ValueError("portfolio requires candidates")
        if not self.stage_order:
            raise ValueError("portfolio requires stage order")
        _require_nonnegative("predicted_total_cost_cad", self.predicted_total_cost_cad)


@dataclass(frozen=True)
class PortfolioPrediction:
    prediction_id: str
    portfolio_id: str
    predicted_quality: float
    predicted_acceptance_probability: float
    predicted_completion_probability: float
    predicted_verification_pass_probability: float
    predicted_deadline_confidence: float
    predicted_cost_cad: float
    predicted_latency_ms: int
    predicted_token_usage: int | None
    predicted_cpu_seconds: int | None
    predicted_gpu_seconds: int | None
    assumptions: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text("prediction_id", self.prediction_id)
        _require_text("portfolio_id", self.portfolio_id)
        for name in (
            "predicted_quality", "predicted_acceptance_probability", "predicted_completion_probability",
            "predicted_verification_pass_probability", "predicted_deadline_confidence",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        _require_nonnegative("predicted_cost_cad", self.predicted_cost_cad)
        _require_nonnegative("predicted_latency_ms", self.predicted_latency_ms)
        for name in ("predicted_token_usage", "predicted_cpu_seconds", "predicted_gpu_seconds"):
            value = getattr(self, name)
            if value is not None:
                _require_nonnegative(name, value)


@dataclass(frozen=True)
class ComputePerformanceObservation:
    observation_id: str
    portfolio_id: str
    candidate_id: str
    observed_at: datetime
    actual_cost_cad: float | None
    actual_latency_ms: int | None
    actual_quality: float | None
    actual_token_usage: int | None
    actual_cpu_seconds: int | None
    actual_gpu_seconds: int | None
    verification_passed: bool | None
    jurisdiction_receipt_ref: str | None
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("observation_id", "portfolio_id", "candidate_id"):
            _require_text(name, getattr(self, name))
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        for name in ("actual_cost_cad", "actual_latency_ms", "actual_token_usage", "actual_cpu_seconds", "actual_gpu_seconds"):
            value = getattr(self, name)
            if value is not None:
                _require_nonnegative(name, value)
        if self.actual_quality is not None and not 0 <= self.actual_quality <= 1:
            raise ValueError("actual_quality must be between 0 and 1")
        if any(
            value is not None
            for value in (self.actual_cost_cad, self.actual_latency_ms, self.actual_quality, self.actual_token_usage, self.actual_cpu_seconds, self.actual_gpu_seconds, self.verification_passed)
        ) and not self.evidence_refs:
            raise ValueError("observed measurements require evidence")


@dataclass(frozen=True)
class PortfolioOutcome:
    outcome_id: str
    portfolio_id: str
    delivered: bool
    verification_passed: bool
    employer_accepted: bool | None
    revision_count: int
    actual_total_cost_cad: float | None
    deadline_met: bool | None
    observed_quality: float | None
    security_incident: bool
    privacy_incident: bool
    confidentiality_incident: bool
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text("outcome_id", self.outcome_id)
        _require_text("portfolio_id", self.portfolio_id)
        _require_nonnegative("revision_count", self.revision_count)
        if self.actual_total_cost_cad is not None:
            _require_nonnegative("actual_total_cost_cad", self.actual_total_cost_cad)
        if self.observed_quality is not None and not 0 <= self.observed_quality <= 1:
            raise ValueError("observed_quality must be between 0 and 1")
        if not self.evidence_refs:
            raise ValueError("portfolio outcome requires evidence")
