from dataclasses import replace

from src.colosseum.compute_exchange import (
    ComputeAdmission,
    ComputeCandidate,
    ComputeRequirement,
    ResourceType,
)
from src.colosseum.domain import ConfidentialityClass


def requirement() -> ComputeRequirement:
    return ComputeRequirement(
        requirement_id="compute-ceiling",
        workload_class="deterministic",
        minimum_quality=0.9,
        minimum_reliability=0.9,
        minimum_availability=0.9,
        minimum_security_level=3,
        minimum_privacy_level=3,
        maximum_latency_ms=1000,
        maximum_cost_cad=1.0,
        confidentiality_class=ConfidentialityClass.CONFIDENTIAL,
        allowed_jurisdictions=("CA-QC",),
        required_capabilities=("deterministic-validation",),
        maximum_compute_seconds=0,
    )


def candidate() -> ComputeCandidate:
    return ComputeCandidate(
        candidate_id="candidate-ceiling",
        provider="local",
        resource_type=ResourceType.DETERMINISTIC_TOOL,
        model_or_runtime="validator",
        region="CA-QC",
        jurisdiction="CA-QC",
        confidentiality_capability=ConfidentialityClass.CONFIDENTIAL,
        security_level=3,
        privacy_level=3,
        encryption="memory-only",
        estimated_cost_cad=0.0,
        estimated_latency_ms=1,
        predicted_quality=1.0,
        predicted_reliability=1.0,
        availability=1.0,
        commercial_use_allowed=True,
        benchmark_evidence_refs=("benchmark://validator",),
        capabilities=("deterministic-validation",),
        admission=ComputeAdmission.ADMISSIBLE,
        estimated_compute_seconds=1,
    )


def test_zero_compute_ceiling_is_not_treated_as_unbounded() -> None:
    assert candidate().satisfies(requirement()) is False
    assert replace(candidate(), estimated_compute_seconds=0).satisfies(
        requirement()
    ) is True
