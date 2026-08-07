from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.epistemic.models import ArtifactState


class NexusContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True, str_strip_whitespace=True)


EffectClass = Literal[
    "PURE",
    "READ_LOCAL",
    "READ_EXTERNAL",
    "WRITE_REVERSIBLE",
    "WRITE_COMPENSATABLE",
    "WRITE_IRREVERSIBLE",
    "FINANCIAL",
    "COMMUNICATION",
    "DEPLOYMENT",
    "SECURITY_SENSITIVE",
]


class WorkOrder(NexusContract):
    work_order_id: str = Field(pattern=r"^WO-[A-Z0-9_-]{6,64}$")
    objective: str = Field(min_length=1)
    acceptance_criteria: tuple[str, ...] = ()
    domain_tags: tuple[str, ...] = ()
    external_execution_requested: bool = False


class ContextEnvelope(NexusContract):
    context_id: str = Field(pattern=r"^CTX-[A-Z0-9_-]{6,64}$")
    work_order_id: str
    state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    relevant_claim_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    memory_refs: tuple[str, ...] = ()


class ProposedOperation(NexusContract):
    operation_id: str = Field(pattern=r"^OP-[A-Z0-9_-]{6,64}$")
    operation_type: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_effect_class: EffectClass
    depends_on: tuple[str, ...] = ()


class ChangeSet(NexusContract):
    change_set_id: str = Field(pattern=r"^CHG-[A-Z0-9_-]{6,64}$")
    change_type: Literal["candidate", "revision", "reconciliation", "rollback"] = "candidate"
    work_order_id: str
    parent_state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    producer_agent_id: str
    artifact_patch: dict[str, Any] = Field(default_factory=dict)
    operations: tuple[ProposedOperation, ...] = ()
    trigger_receipt_id: str | None = None

    @model_validator(mode="after")
    def reconciliation_requires_receipt(self) -> "ChangeSet":
        if self.change_type in {"reconciliation", "rollback"} and not self.trigger_receipt_id:
            raise ValueError("reconciliation/rollback ChangeSet requires trigger_receipt_id")
        ids = [item.operation_id for item in self.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("ChangeSet contains duplicate operation IDs")
        return self


class GovernanceDecision(NexusContract):
    decision_id: str = Field(pattern=r"^GOV-[A-Z0-9_-]{6,64}$")
    decision: Literal["approved", "denied", "revise", "requires_human_review", "blocked"]
    authority_source: Literal["POLICY", "HUMAN"]
    authority_actor: str
    artifact_state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    change_set_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    verifier_report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    exact_revision: str
    conditions: tuple[str, ...] = ()
    expires_at: datetime | None = None


class ExecutionPermit(NexusContract):
    permit_id: str = Field(pattern=r"^PERMIT-[A-Z0-9_-]{6,64}$")
    governance_decision_id: str
    principal: str
    capability: str
    resource_scope: tuple[str, ...]
    exact_revision: str
    change_set_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime
    maximum_invocations: int = Field(ge=1, le=100)


class NexusToolInvocationRequest(NexusContract):
    request_id: str = Field(pattern=r"^TREQ-[A-Z0-9_-]{6,64}$")
    permit_id: str | None = None
    run_id: str
    agent_id: str
    tool_name: str
    resource_ref: str
    purpose: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    effect_class: EffectClass
    data_classification: Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"] = "INTERNAL"
    egress_allowed: bool = False
    maximum_records: int | None = Field(default=None, ge=1)
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")


OperationStatus = Literal[
    "not_started",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
    "indeterminate",
]


class OperationReceipt(NexusContract):
    operation_id: str
    status: OperationStatus
    resource_ref: str
    before_hash: str | None = None
    after_hash: str | None = None
    failure_class: str | None = None
    retryable: bool | None = None
    evidence_refs: tuple[str, ...] = ()


class ExecutionReceipt(NexusContract):
    receipt_id: str = Field(pattern=r"^EXEC-[A-Z0-9_-]{6,64}$")
    permit_id: str | None = None
    change_set_id: str
    parent_state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    execution_status: Literal[
        "not_started",
        "succeeded",
        "failed",
        "partially_applied",
        "cancelled",
        "timed_out",
        "indeterminate",
    ]
    operations: tuple[OperationReceipt, ...] = ()
    external_action_performed: bool = False
    reconciliation_required: bool = False

    @model_validator(mode="after")
    def enforce_reconciliation_semantics(self) -> "ExecutionReceipt":
        if self.execution_status in {"partially_applied", "indeterminate"} and not self.reconciliation_required:
            raise ValueError("partial/indeterminate execution requires reconciliation")
        if self.execution_status == "not_started" and self.external_action_performed:
            raise ValueError("not_started receipt cannot claim an external action")
        return self


class StateTransition(NexusContract):
    prior_state: ArtifactState
    receipt: ExecutionReceipt
    next_state: ArtifactState
