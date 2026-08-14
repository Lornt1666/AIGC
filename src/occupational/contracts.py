from __future__ import annotations

# Runtime contract module; this comment intentionally records the approved
# exact-head CI verification trigger for the occupational runtime slice.
import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def canonical_sha256(value: BaseModel | dict[str, Any]) -> str:
    payload = value.model_dump(mode="json", exclude_none=False) if isinstance(value, BaseModel) else value
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AuthorityEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    autonomous_actions: tuple[str, ...] = ()
    approval_required_actions: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()


class WorkCommission(BaseModel):
    """One immutable accepted occupational truth revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commission_id: str = Field(min_length=3)
    commission_revision: int = Field(ge=1)
    discipline_id: str = Field(min_length=3)
    target_repository: str | None = None
    target_base_revision: str | None = None
    requested_outcome: str = Field(min_length=1)
    scope: tuple[str, ...] = ()
    explicit_exclusions: tuple[str, ...] = ()
    acceptance_mode: str
    risk_tier: Literal["R0", "R1", "R2", "R3", "R4"]
    authority_envelope: AuthorityEnvelope
    sealed: Literal[True]

    @property
    def digest(self) -> str:
        return canonical_sha256(self)


class NoProgressPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_cycles: int = Field(ge=1, le=50)
    max_identical_failure_retries: int = Field(ge=0, le=10)


class OutcomeContract(BaseModel):
    """Immutable completion truth for a commission revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str = Field(min_length=3)
    contract_revision: int = Field(ge=1)
    required_artifacts: tuple[str, ...]
    hard_gates: tuple[str, ...]
    required_evidence: tuple[str, ...]
    delivery_receipt_required: bool
    independent_verification_required: bool
    no_progress_policy: NoProgressPolicy
    sealed: Literal[True]

    @property
    def digest(self) -> str:
        return canonical_sha256(self)


class OccupationalBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    commission_id: str
    commission_revision: int = Field(ge=1)
    commission_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    outcome_contract_id: str
    outcome_contract_revision: int = Field(ge=1)
    outcome_contract_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    career_mandate_id: str
    career_mandate_version: int = Field(ge=1)
    policy_version: str = Field(min_length=1)

    @classmethod
    def from_contracts(
        cls,
        commission: WorkCommission,
        outcome_contract: OutcomeContract,
        *,
        career_mandate_id: str,
        career_mandate_version: int,
        policy_version: str,
    ) -> "OccupationalBinding":
        return cls(
            commission_id=commission.commission_id,
            commission_revision=commission.commission_revision,
            commission_sha256=commission.digest,
            outcome_contract_id=outcome_contract.contract_id,
            outcome_contract_revision=outcome_contract.contract_revision,
            outcome_contract_sha256=outcome_contract.digest,
            career_mandate_id=career_mandate_id,
            career_mandate_version=career_mandate_version,
            policy_version=policy_version,
        )

    def matches(
        self,
        commission: WorkCommission,
        outcome_contract: OutcomeContract,
        *,
        current_mandate_version: int,
        current_policy_version: str,
    ) -> bool:
        return all(
            (
                self.commission_id == commission.commission_id,
                self.commission_revision == commission.commission_revision,
                self.commission_sha256 == commission.digest,
                self.outcome_contract_id == outcome_contract.contract_id,
                self.outcome_contract_revision == outcome_contract.contract_revision,
                self.outcome_contract_sha256 == outcome_contract.digest,
                self.career_mandate_version == current_mandate_version,
                self.policy_version == current_policy_version,
            )
        )


class WorkAttemptStatus(StrEnum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    DESIGNING_METHOD = "DESIGNING_METHOD"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    DELIVERY_READY = "DELIVERY_READY"
    BLOCKED = "BLOCKED"
    NO_PROGRESS = "NO_PROGRESS"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    STALE_AUTHORIZATION = "STALE_AUTHORIZATION"
    SUPERSEDED = "SUPERSEDED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    ROLLED_BACK = "ROLLED_BACK"
    COMPLETED = "COMPLETED"


TERMINAL_OR_HALTED = {
    WorkAttemptStatus.STALE_AUTHORIZATION,
    WorkAttemptStatus.SUPERSEDED,
    WorkAttemptStatus.CANCELLED,
    WorkAttemptStatus.FAILED,
    WorkAttemptStatus.ROLLED_BACK,
    WorkAttemptStatus.COMPLETED,
}


class WorkAttempt(BaseModel):
    """Mutable execution state; it never owns occupational truth."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    work_attempt_id: str
    occupational_binding: OccupationalBinding
    status: WorkAttemptStatus = WorkAttemptStatus.CREATED
    task_graph_version: int = Field(default=1, ge=1)
    mutable_execution_revision: int = Field(default=0, ge=0)
    method_genome_id: str | None = None
    writer_lineage_id: str | None = None
    verifier_lineage_ids: list[str] = Field(default_factory=list)
    cycle_count: int = Field(default=0, ge=0)
    identical_failure_retries: int = Field(default=0, ge=0)
    last_failure_signature: str | None = None
    stale_reason: str | None = None

    def _bump(self) -> None:
        object.__setattr__(self, "mutable_execution_revision", self.mutable_execution_revision + 1)

    def revalidate(
        self,
        commission: WorkCommission,
        outcome_contract: OutcomeContract,
        *,
        current_mandate_version: int,
        current_policy_version: str,
        superseded: bool = False,
    ) -> bool:
        if superseded:
            self.status = WorkAttemptStatus.SUPERSEDED
            self.stale_reason = "governing occupational revision was superseded"
            self._bump()
            return False
        if not self.occupational_binding.matches(
            commission,
            outcome_contract,
            current_mandate_version=current_mandate_version,
            current_policy_version=current_policy_version,
        ):
            self.status = WorkAttemptStatus.STALE_AUTHORIZATION
            self.stale_reason = "exact occupational binding no longer matches current truth"
            self._bump()
            return False
        return True

    def transition(
        self,
        target: WorkAttemptStatus,
        *,
        commission: WorkCommission,
        outcome_contract: OutcomeContract,
        current_mandate_version: int,
        current_policy_version: str,
        consequential: bool = True,
        superseded: bool = False,
    ) -> None:
        if self.status in TERMINAL_OR_HALTED:
            raise ValueError(f"attempt is halted in {self.status}")
        if consequential and not self.revalidate(
            commission,
            outcome_contract,
            current_mandate_version=current_mandate_version,
            current_policy_version=current_policy_version,
            superseded=superseded,
        ):
            raise ValueError(f"consequential transition denied: {self.status}")
        self.status = target
        self._bump()

    def record_failure(self, signature: str, policy: NoProgressPolicy) -> None:
        normalized = signature.strip()
        if not normalized:
            raise ValueError("failure signature is required")
        self.cycle_count += 1
        if self.last_failure_signature == normalized:
            self.identical_failure_retries += 1
        else:
            self.identical_failure_retries = 0
            self.last_failure_signature = normalized
        if (
            self.cycle_count >= policy.max_cycles
            or self.identical_failure_retries >= policy.max_identical_failure_retries
        ):
            self.status = WorkAttemptStatus.NO_PROGRESS
        self._bump()

    def register_independent_verifier(self, verifier_lineage_id: str) -> None:
        if self.writer_lineage_id and verifier_lineage_id == self.writer_lineage_id:
            raise ValueError("writer lineage cannot be the sole independent verifier")
        if verifier_lineage_id not in self.verifier_lineage_ids:
            self.verifier_lineage_ids.append(verifier_lineage_id)
            self._bump()


class EvidenceReceipt(BaseModel):
    """Immutable proof record. Evidence never grants authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    work_attempt_id: str
    mutable_execution_revision: int = Field(ge=0)
    occupational_binding: OccupationalBinding
    evidence_type: str
    result: Literal["PASS", "FAIL", "BLOCKED", "OBSERVED"]
    verifier_id: str
    verifier_type: Literal["DETERMINISTIC", "INDEPENDENT_AGENT", "HUMAN", "EXTERNAL_SYSTEM"]
    independent: bool
    artifact_sha256: dict[str, str] = Field(default_factory=dict)
    external_state_fresh: bool | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_artifact_digests(self) -> "EvidenceReceipt":
        for digest in self.artifact_sha256.values():
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("artifact digests must be lowercase SHA-256")
        return self

    @classmethod
    def for_attempt(
        cls,
        *,
        receipt_id: str,
        attempt: WorkAttempt,
        evidence_type: str,
        result: Literal["PASS", "FAIL", "BLOCKED", "OBSERVED"],
        verifier_id: str,
        verifier_type: Literal["DETERMINISTIC", "INDEPENDENT_AGENT", "HUMAN", "EXTERNAL_SYSTEM"],
        independent: bool,
        artifact_sha256: dict[str, str] | None = None,
        external_state_fresh: bool | None = None,
    ) -> "EvidenceReceipt":
        if independent and attempt.writer_lineage_id == verifier_id:
            raise ValueError("writer lineage cannot self-assert independent evidence")
        return cls(
            receipt_id=receipt_id,
            work_attempt_id=attempt.work_attempt_id,
            mutable_execution_revision=attempt.mutable_execution_revision,
            occupational_binding=attempt.occupational_binding,
            evidence_type=evidence_type,
            result=result,
            verifier_id=verifier_id,
            verifier_type=verifier_type,
            independent=independent,
            artifact_sha256=artifact_sha256 or {},
            external_state_fresh=external_state_fresh,
        )


class QuestCompatibilityAlias(BaseModel):
    """Compatibility projection only; carries no authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quest_id: str
    commission_id: str
    commission_revision: int = Field(ge=1)
    active_work_attempt_id: str | None = None
    authority_source: Literal["NONE_COMPATIBILITY_ONLY"] = "NONE_COMPATIBILITY_ONLY"
