from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


def _require_text(name: str, value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _require_nonnegative(name: str, value: int | float) -> int | float:
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


class ConfidentialityClass(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class CapabilityVerdict(str, Enum):
    VERIFIED_CAPABLE = "VERIFIED_CAPABLE"
    CAPABLE_WITH_REVIEW = "CAPABLE_WITH_REVIEW"
    CAPABLE_WITH_SPECIALIST = "CAPABLE_WITH_SPECIALIST"
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    LEGALLY_RESTRICTED = "LEGALLY_RESTRICTED"


class DeliverableState(str, Enum):
    GENERATED = "GENERATED"
    VALIDATING = "VALIDATING"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    REQUIRES_REVISION = "REQUIRES_REVISION"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    EMPLOYER_ACCEPTED = "EMPLOYER_ACCEPTED"
    EMPLOYER_REJECTED = "EMPLOYER_REJECTED"


class VerificationStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"
    PASS_WITH_LIMITATION = "PASS_WITH_LIMITATION"
    FAIL = "FAIL"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


@dataclass(frozen=True)
class EmployerVault:
    vault_id: str
    employer_id: str
    confidentiality_class: ConfidentialityClass
    allowed_jurisdictions: tuple[str, ...]
    retention_policy_id: str
    deletion_policy_id: str
    cross_employer_document_access: bool = False
    cross_employer_secret_access: bool = False
    cross_employer_retrieval: bool = False
    cross_employer_prompt_context: bool = False
    cross_employer_training_use: bool = False

    def __post_init__(self) -> None:
        _require_text("vault_id", self.vault_id)
        _require_text("employer_id", self.employer_id)
        _require_text("retention_policy_id", self.retention_policy_id)
        _require_text("deletion_policy_id", self.deletion_policy_id)
        if not self.allowed_jurisdictions:
            raise ValueError("allowed_jurisdictions must not be empty")
        if any(
            (
                self.cross_employer_document_access,
                self.cross_employer_secret_access,
                self.cross_employer_retrieval,
                self.cross_employer_prompt_context,
                self.cross_employer_training_use,
            )
        ):
            raise ValueError("cross-employer access defaults are fail-closed")


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    source_id: str
    employer_id: str
    title: str
    digitally_executable: bool
    physical_presence_required: bool
    legitimacy_status: str
    capability_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("opportunity_id", "source_id", "employer_id", "title", "legitimacy_status"):
            _require_text(name, getattr(self, name))
        if self.physical_presence_required and self.digitally_executable:
            raise ValueError("opportunity cannot be both fully digitally executable and require physical presence")


@dataclass(frozen=True)
class Engagement:
    engagement_id: str
    employer_id: str
    vault_id: str
    statement_of_work_id: str
    acceptance_criteria: tuple[str, ...]
    deadline: datetime
    authorized: bool = False

    def __post_init__(self) -> None:
        for name in ("engagement_id", "employer_id", "vault_id", "statement_of_work_id"):
            _require_text(name, getattr(self, name))
        if not self.acceptance_criteria:
            raise ValueError("engagement requires acceptance criteria")
        if self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware")


@dataclass(frozen=True)
class WorkOrder:
    work_order_id: str
    engagement_id: str
    objective: str
    requirement_ids: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    authorized: bool

    def __post_init__(self) -> None:
        for name in ("work_order_id", "engagement_id", "objective"):
            _require_text(name, getattr(self, name))
        if not self.requirement_ids:
            raise ValueError("work order requires at least one requirement")
        if not self.acceptance_criteria:
            raise ValueError("work order requires acceptance criteria")


@dataclass(frozen=True)
class AgentCell:
    agent_cell_id: str
    role: str
    allowed_tools: tuple[str, ...]
    allowed_data_scopes: tuple[str, ...]
    output_schema_id: str
    maximum_cost_cad: float
    maximum_tokens: int

    def __post_init__(self) -> None:
        for name in ("agent_cell_id", "role", "output_schema_id"):
            _require_text(name, getattr(self, name))
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        _require_nonnegative("maximum_tokens", self.maximum_tokens)


@dataclass(frozen=True)
class Swarm:
    swarm_id: str
    engagement_id: str
    work_order_id: str
    objective: str
    agent_cells: tuple[AgentCell, ...]
    compute_budget_cad: float
    token_budget: int
    confidentiality_class: ConfidentialityClass
    jurisdiction_policy_id: str
    verification_policy_id: str
    emergency_stop_epoch: int

    def __post_init__(self) -> None:
        for name in ("swarm_id", "engagement_id", "work_order_id", "objective", "jurisdiction_policy_id", "verification_policy_id"):
            _require_text(name, getattr(self, name))
        if not self.agent_cells:
            raise ValueError("swarm requires at least one agent cell")
        _require_nonnegative("compute_budget_cad", self.compute_budget_cad)
        _require_nonnegative("token_budget", self.token_budget)
        _require_nonnegative("emergency_stop_epoch", self.emergency_stop_epoch)
        if sum(cell.maximum_cost_cad for cell in self.agent_cells) > self.compute_budget_cad:
            raise ValueError("agent-cell maximum costs exceed swarm compute budget")
        if sum(cell.maximum_tokens for cell in self.agent_cells) > self.token_budget:
            raise ValueError("agent-cell token maxima exceed swarm token budget")


@dataclass(frozen=True)
class Deliverable:
    deliverable_id: str
    work_order_id: str
    artifact_ids: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    state: DeliverableState = DeliverableState.GENERATED

    def __post_init__(self) -> None:
        _require_text("deliverable_id", self.deliverable_id)
        _require_text("work_order_id", self.work_order_id)
        if not self.artifact_ids:
            raise ValueError("deliverable requires at least one artifact")
        if not self.acceptance_criteria:
            raise ValueError("deliverable requires acceptance criteria")


@dataclass(frozen=True)
class Verification:
    verification_id: str
    deliverable_id: str
    verifier_identity: str
    status: VerificationStatus
    checks: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("verification_id", "deliverable_id", "verifier_identity"):
            _require_text(name, getattr(self, name))
        if not self.checks:
            raise ValueError("verification requires checks")
        if self.status in {VerificationStatus.PASS, VerificationStatus.PASS_WITH_LIMITATION} and not self.evidence_refs:
            raise ValueError("successful verification requires evidence")


@dataclass(frozen=True)
class WorkLedgerEntry:
    event_id: str
    work_order_id: str
    actor_id: str
    resource_id: str
    started_at: datetime
    ended_at: datetime
    human_active_seconds: int = 0
    agent_active_seconds: int = 0
    compute_seconds: int = 0
    research_seconds: int = 0
    review_seconds: int = 0
    meeting_seconds: int = 0
    revision_seconds: int = 0
    blocked_seconds: int = 0
    employer_wait_seconds: int = 0
    billability_class: str = "NON_BILLABLE_UNLESS_CONTRACT_AUTHORIZES"
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("event_id", "work_order_id", "actor_id", "resource_id", "billability_class"):
            _require_text(name, getattr(self, name))
        if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
            raise ValueError("ledger timestamps must be timezone-aware")
        if self.ended_at < self.started_at:
            raise ValueError("ended_at cannot precede started_at")
        for name in (
            "human_active_seconds", "agent_active_seconds", "compute_seconds", "research_seconds",
            "review_seconds", "meeting_seconds", "revision_seconds", "blocked_seconds", "employer_wait_seconds",
        ):
            _require_nonnegative(name, getattr(self, name))


@dataclass(frozen=True)
class WorkLedger:
    work_order_id: str
    entries: tuple[WorkLedgerEntry, ...]

    def __post_init__(self) -> None:
        _require_text("work_order_id", self.work_order_id)
        if any(entry.work_order_id != self.work_order_id for entry in self.entries):
            raise ValueError("ledger entry belongs to a different work order")

    @property
    def totals(self) -> dict[str, int]:
        keys = (
            "human_active_seconds", "agent_active_seconds", "compute_seconds", "research_seconds",
            "review_seconds", "meeting_seconds", "revision_seconds", "blocked_seconds", "employer_wait_seconds",
        )
        return {key: sum(getattr(entry, key) for entry in self.entries) for key in keys}


@dataclass(frozen=True)
class CapabilityEvidence:
    capability_evidence_id: str
    discipline: str
    skill: str
    verdict: CapabilityVerdict
    benchmark_ids: tuple[str, ...]
    accepted_deliverable_ids: tuple[str, ...]
    validated_attempts: int
    successful_attempts: int
    human_review_required: bool
    evidence_refs: tuple[str, ...]
    last_verified_at: datetime

    def __post_init__(self) -> None:
        for name in ("capability_evidence_id", "discipline", "skill"):
            _require_text(name, getattr(self, name))
        _require_nonnegative("validated_attempts", self.validated_attempts)
        _require_nonnegative("successful_attempts", self.successful_attempts)
        if self.successful_attempts > self.validated_attempts:
            raise ValueError("successful_attempts cannot exceed validated_attempts")
        if self.last_verified_at.tzinfo is None:
            raise ValueError("last_verified_at must be timezone-aware")
        if self.verdict == CapabilityVerdict.VERIFIED_CAPABLE and not self.evidence_refs:
            raise ValueError("VERIFIED_CAPABLE requires evidence")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
