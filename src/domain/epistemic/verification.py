from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from src.domain.epistemic.models import ContractModel


FindingSeverity = Literal["info", "warning", "error", "critical"]


class UtilityWeights(ContractModel):
    fidelity: float = Field(ge=0.0, le=1.0)
    evidence: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    redundancy: float = Field(ge=0.0, le=1.0)
    unsupported: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def normalized(self) -> "UtilityWeights":
        total = self.fidelity + self.evidence + self.completeness + self.redundancy + self.unsupported
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Verifier utility weights must sum to 1.0; observed {total}")
        return self


class UtilityScore(ContractModel):
    total_score: float = Field(ge=-1.0, le=1.0)
    semantic_fidelity_f: float = Field(ge=0.0, le=1.0)
    evidence_coverage_e: float = Field(ge=0.0, le=1.0)
    structural_completeness_c: float = Field(ge=0.0, le=1.0)
    redundancy_r: float = Field(ge=0.0, le=1.0)
    unsupported_claims_x: float = Field(ge=0.0, le=1.0)


class VerifierFinding(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,100}$")
    severity: FindingSeverity
    message: str = Field(min_length=1, max_length=4000)
    claim_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


class VerifierReport(ContractModel):
    contract_version: Literal["2.0.0"] = "2.0.0"
    verifier_id: Literal["deterministic_epistemic_verifier_v2"] = "deterministic_epistemic_verifier_v2"
    baseline_state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    target_state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_id: str = Field(pattern=r"^VRF-[A-F0-9]{24}$")
    total_claims_audited: int = Field(ge=0)
    unverified_claims: int = Field(ge=0)
    falsified_claims: int = Field(ge=0)
    findings: tuple[VerifierFinding, ...] = ()
    utility_score: UtilityScore
    utility_threshold: float = Field(ge=-1.0, le=1.0)
    hard_failure: bool
    is_passing: bool
    external_action_performed: Literal[False] = False
    output_modified: Literal[False] = False
