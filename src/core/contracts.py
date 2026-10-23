"""Versioned, fail-closed contracts for the AIGC orchestration kernel.

These models validate message shape; they do not grant authority or prove that a
policy check occurred. External mutation requires a separately verified permit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA_VERSION = "1.0"
MAX_HOPS = 10
MAX_AGENT_TIMEOUT_SECONDS = 30


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EventKind(StrEnum):
    TASK_SUBMITTED = "task.submitted"
    TASK_STARTED = "task.started"
    TASK_SUCCEEDED = "task.succeeded"
    TASK_FAILED = "task.failed"
    TASK_DEAD_LETTERED = "task.dead_lettered"
    SAGA_STARTED = "saga.started"
    SAGA_STEP_SUCCEEDED = "saga.step_succeeded"
    SAGA_COMPENSATION_STARTED = "saga.compensation_started"
    SAGA_COMPENSATED = "saga.compensated"
    SAGA_COMPENSATION_FAILED = "saga.compensation_failed"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    COMPENSATING = "compensating"
    COMPENSATION_FAILED = "compensation_failed"


class TelemetryContext(ContractModel):
    trace_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    trace_flags: str | None = Field(default=None, pattern=r"^[0-9a-f]{2}$")


class TaskContract(ContractModel):
    schema_version: str = SCHEMA_VERSION
    task_id: str = Field(default_factory=lambda: f"AIGC-TASK-{uuid4()}", min_length=8, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=256)
    task_type: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")
    payload: dict[str, Any] = Field(default_factory=dict)
    deadline_at: datetime | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, le=MAX_AGENT_TIMEOUT_SECONDS)
    hop_count: int = Field(default=0, ge=0, le=MAX_HOPS)
    max_hops: int = Field(default=MAX_HOPS, ge=1, le=MAX_HOPS)
    telemetry: TelemetryContext = Field(default_factory=TelemetryContext)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_bounds(self) -> "TaskContract":
        if self.hop_count > self.max_hops:
            raise ValueError("hop_count cannot exceed max_hops")
        if self.deadline_at is not None and self.deadline_at.tzinfo is None:
            raise ValueError("deadline_at must be timezone-aware")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self


class MutationPayload(ContractModel):
    schema_version: str = SCHEMA_VERSION
    mutation_id: str = Field(default_factory=lambda: f"AIGC-MUTATION-{uuid4()}", min_length=8, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=256)
    operation: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")
    resource: str = Field(min_length=1, max_length=512)
    arguments: dict[str, Any] = Field(default_factory=dict)
    external_effect: bool = False
    permit_id: str | None = Field(default=None, max_length=256)
    human_approval_id: str | None = Field(default=None, max_length=256)
    expected_resource_version: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def require_authority_for_external_effect(self) -> "MutationPayload":
        if self.external_effect and (not self.permit_id or not self.human_approval_id):
            raise ValueError(
                "external_effect requires both a verified permit reference and human approval reference"
            )
        return self


class OrchestrationEvent(ContractModel):
    schema_version: str = SCHEMA_VERSION
    event_id: str = Field(default_factory=lambda: f"AIGC-EVENT-{uuid4()}", min_length=8, max_length=128)
    event_kind: EventKind
    task_id: str = Field(min_length=8, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=256)
    hop_count: int = Field(default=0, ge=0, le=MAX_HOPS)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    telemetry: TelemetryContext = Field(default_factory=TelemetryContext)
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_aware_timestamp(self) -> "OrchestrationEvent":
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return self


class SagaStepContract(ContractModel):
    step_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")
    action_name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")
    compensation_name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")
    timeout_seconds: float = Field(default=30.0, gt=0, le=MAX_AGENT_TIMEOUT_SECONDS)
    idempotency_key: str = Field(min_length=8, max_length=256)
