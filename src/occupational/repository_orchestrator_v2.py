from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from .contracts import EvidenceReceipt, OutcomeContract, WorkAttempt, WorkCommission
from .repository_engineering import MethodGenomeName, RepositoryAtlas, WriteEligibility


class RepositoryEngineeringAuthority(IntEnum):
    RE0 = 0
    RE1 = 1
    RE2 = 2
    RE3 = 3
    RE4 = 4
    RE5 = 5
    RE6 = 6


class ImpactDomain(StrEnum):
    CODE = "CODE"
    TESTS = "TESTS"
    REQUIREMENTS = "REQUIREMENTS"
    ARCHITECTURE = "ARCHITECTURE"
    AUTHORITY = "AUTHORITY"
    SECURITY = "SECURITY"
    DEPLOYMENT = "DEPLOYMENT"
    EVIDENCE = "EVIDENCE"
    ROLLBACK = "ROLLBACK"


class ImpactEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: str
    target: str
    domain: ImpactDomain
    relation: str
    confidence: float = Field(ge=0.0, le=1.0)


class ImpactGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    proposal_id: str
    repository_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    edges: tuple[ImpactEdge, ...]
    unresolved_impacts: tuple[str, ...] = ()

    @property
    def analyzed(self) -> bool:
        return bool(self.edges) and not self.unresolved_impacts


class EvaluatorProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profile_id: str
    method_genome: MethodGenomeName
    required_gates: tuple[str, ...]
    independent_verification_required: bool
    rollback_test_required: bool = False
    mutation_test_required: bool = False
    performance_regression_required: bool = False


EVALUATOR_PROFILES: dict[MethodGenomeName, EvaluatorProfile] = {
    MethodGenomeName.BUG_REPAIR: EvaluatorProfile(
        profile_id="EP_BUG_REPAIR_V1",
        method_genome=MethodGenomeName.BUG_REPAIR,
        required_gates=("compile", "targeted_tests", "regression_test", "affected_suite", "diff_review"),
        independent_verification_required=False,
    ),
    MethodGenomeName.ARCHITECTURE_MIGRATION: EvaluatorProfile(
        profile_id="EP_ARCHITECTURE_MIGRATION_V1",
        method_genome=MethodGenomeName.ARCHITECTURE_MIGRATION,
        required_gates=("repository_atlas", "impact_graph", "adr", "architecture_fitness", "contract_compatibility", "unit_tests", "integration_tests", "property_tests", "security_verification", "dependency_analysis", "migration_rollback", "performance_regression", "exact_diff_review"),
        independent_verification_required=True,
        rollback_test_required=True,
        mutation_test_required=True,
        performance_regression_required=True,
    ),
}


class EngineeringMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    memory_id: str
    category: str
    statement: str
    evidence_receipt_ids: tuple[str, ...]
    source_attempt_ids: tuple[str, ...]
    supersedes_memory_ids: tuple[str, ...] = ()

    @property
    def admissible(self) -> bool:
        return bool(self.evidence_receipt_ids) and bool(self.source_attempt_ids)


class MethodOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    method_genome: MethodGenomeName
    verified_quality: float = Field(ge=0.0)
    cost: float = Field(ge=0.0)
    latency: float = Field(ge=0.0)
    human_attention: float = Field(ge=0.0)
    risk: float = Field(ge=0.0)

    @property
    def efficiency(self) -> float:
        denominator = self.cost + self.latency + self.human_attention + self.risk
        return self.verified_quality / denominator if denominator > 0 else self.verified_quality


class CompletionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    complete: bool
    missing_gates: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    authority_sufficient: bool
    attempt_current: bool


class RepositoryEngineeringOrchestratorV2:
    """Evidence-governed coordinator; never an authority source."""

    @staticmethod
    def effective_authority(*levels: RepositoryEngineeringAuthority) -> RepositoryEngineeringAuthority:
        return min(levels) if levels else RepositoryEngineeringAuthority.RE0

    @staticmethod
    def require_authority(current: RepositoryEngineeringAuthority, required: RepositoryEngineeringAuthority) -> None:
        if current < required:
            raise PermissionError(f"repository action requires {required.name}; effective authority is {current.name}")

    @staticmethod
    def write_eligible(write: WriteEligibility, impact_graph: ImpactGraph) -> bool:
        return write.eligible and impact_graph.analyzed

    @staticmethod
    def evaluator_profile(method: MethodGenomeName) -> EvaluatorProfile:
        return EVALUATOR_PROFILES.get(method, EvaluatorProfile(
            profile_id=f"EP_{method.value}_BASE_V1",
            method_genome=method,
            required_gates=("repository_atlas", "impact_graph", "compile", "tests", "diff_review"),
            independent_verification_required=True,
        ))

    @staticmethod
    def admit_memory(entry: EngineeringMemoryEntry) -> None:
        if not entry.admissible:
            raise ValueError("engineering memory requires evidence and source attempt lineage")

    @staticmethod
    def select_method(outcomes: Iterable[MethodOutcome]) -> MethodOutcome:
        values = tuple(outcomes)
        if not values:
            raise ValueError("at least one method outcome is required")
        return max(values, key=lambda item: item.efficiency)

    @staticmethod
    def completion_decision(
        *, commission: WorkCommission, contract: OutcomeContract, attempt: WorkAttempt,
        atlas: RepositoryAtlas, impact_graph: ImpactGraph, passed_gates: set[str],
        evidence_receipts: Iterable[EvidenceReceipt], authority_sufficient: bool,
        current_mandate_version: int, current_policy_version: str,
    ) -> CompletionDecision:
        attempt_current = attempt.occupational_binding.matches(
            commission, contract,
            current_mandate_version=current_mandate_version,
            current_policy_version=current_policy_version,
        )
        missing_gates = tuple(sorted(set(contract.hard_gates) - passed_gates))
        evidence_types = {r.evidence_type for r in evidence_receipts if r.result == "PASS"}
        missing_evidence = tuple(sorted(set(contract.required_evidence) - evidence_types))
        complete = all((atlas.mapped, impact_graph.analyzed, attempt_current, authority_sufficient, not missing_gates, not missing_evidence))
        return CompletionDecision(
            complete=complete,
            missing_gates=missing_gates,
            missing_evidence=missing_evidence,
            authority_sufficient=authority_sufficient,
            attempt_current=attempt_current,
        )
