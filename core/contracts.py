"""Versioned typed contracts for RegenExcalibur AIGC runtime.

Contracts are data-only. Never deserialize untrusted input with pickle or import
agent code as a side effect of registry discovery.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = "1.0.0"
_SHA256 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class TaskStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    UNKNOWN = "UNKNOWN"


class RiskTier(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class EvidenceRef(StrictModel):
    evidence_id: str = Field(min_length=1, max_length=256)
    uri: str = Field(min_length=1, max_length=2048)
    sha256: str
    media_type: str = "application/json"
    source: str = Field(min_length=1, max_length=256)
    observed_at: datetime
    authenticated: bool = False

    @field_validator("sha256")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("sha256 must be a 64-character lowercase hexadecimal digest")
        return value.removeprefix("sha256:")


class TraceContext(StrictModel):
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    trace_flags: int = Field(default=1, ge=0, le=255)


class TaskContract(StrictModel):
    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    task_id: UUID = Field(default_factory=uuid4)
    idempotency_key: str = Field(min_length=16, max_length=256)
    project_id: str = Field(min_length=1, max_length=128)
    objective: str = Field(min_length=1, max_length=20_000)
    scope: list[str] = Field(min_length=1, max_length=100)
    exclusions: list[str] = Field(default_factory=list, max_length=100)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=100)
    dependencies: list[UUID] = Field(default_factory=list, max_length=500)
    risk_tier: RiskTier
    policy_version: str = Field(min_length=1, max_length=128)
    allowed_agent_ids: list[str] = Field(min_length=1, max_length=100)
    allowed_tools: list[str] = Field(default_factory=list, max_length=100)
    permitted_side_effects: list[str] = Field(default_factory=list, max_length=100)
    max_hops: int = Field(default=10, ge=1, le=10)
    max_attempts: int = Field(default=3, ge=1, le=8)
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    budget_microunits: int = Field(default=0, ge=0, le=10**12)
    trace: TraceContext | None = None
    input_refs: list[EvidenceRef] = Field(default_factory=list, max_length=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("idempotency_key")
    @classmethod
    def reject_placeholder_key(cls, value: str) -> str:
        if value.lower() in {"todo", "none", "null", "changeme", "test"}:
            raise ValueError("idempotency key must be unique and non-placeholder")
        return value

    @model_validator(mode="after")
    def dependencies_not_self(self) -> "TaskContract":
        if self.task_id in self.dependencies:
            raise ValueError("task cannot depend on itself")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("duplicate task dependencies")
        if len(set(self.allowed_agent_ids)) != len(self.allowed_agent_ids):
            raise ValueError("duplicate allowed agent IDs")
        return self


class MutationPayload(StrictModel):
    operation: str = Field(min_length=1, max_length=128)
    resource: str = Field(min_length=1, max_length=1024)
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=16, max_length=256)
    precondition_digest: str
    compensation_operation: str | None = Field(default=None, max_length=128)
    compensation_arguments: dict[str, Any] = Field(default_factory=dict)
    irreversible: bool = False
    approval_receipt_ref: str | None = None

    @field_validator("precondition_digest")
    @classmethod
    def valid_precondition_digest(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("precondition_digest must be SHA-256")
        return value.removeprefix("sha256:")

    @model_validator(mode="after")
    def irreversible_requires_approval(self) -> "MutationPayload":
        if self.irreversible and not self.approval_receipt_ref:
            raise ValueError("irreversible mutation requires an external human approval receipt reference")
        if self.compensation_operation == self.operation:
            raise ValueError("compensation operation must be explicitly distinct from forward operation")
        return self


class AgentResult(StrictModel):
    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    task_id: UUID
    agent_id: str
    agent_version: str
    status: TaskStatus
    summary: str = Field(max_length=20_000)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(ge=0, le=1)
    side_effects_performed: bool = False
    audit_event_ids: list[str] = Field(default_factory=list)
    policy_version: str
    started_at: datetime
    completed_at: datetime

    @model_validator(mode="after")
    def chronological(self) -> "AgentResult":
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if self.status in {TaskStatus.BLOCKED, TaskStatus.FAILED, TaskStatus.UNKNOWN} and self.side_effects_performed:
            if not self.audit_event_ids:
                raise ValueError("side effects on non-success results require audit event IDs")
        return self


class ToolPermit(StrictModel):
    permit_id: UUID
    issuer: str
    subject_agent_id: str
    operation: str
    resource: str
    candidate_sha: str
    policy_version: str
    issued_at: datetime
    expires_at: datetime
    idempotency_key: str
    signature_envelope_ref: str
    approval_receipt_ref: str | None = None

    @model_validator(mode="after")
    def valid_scope_and_expiry(self) -> "ToolPermit":
        if self.expires_at <= self.issued_at:
            raise ValueError("permit expiry must follow issue time")
        if self.expires_at - self.issued_at > __import__("datetime").timedelta(minutes=15):
            raise ValueError("permit lifetime exceeds 15-minute maximum")
        if not _SHA256.fullmatch(self.candidate_sha):
            raise ValueError("candidate_sha must be a full SHA-256 digest")
        return self
