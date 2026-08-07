from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.autonomy import ConsequenceAssessment
from src.domain.nexus.contracts import EffectClass, ExecutionReceipt, NexusContract


ProviderAttemptStatus = Literal[
    "not_started",
    "succeeded",
    "failed",
    "timed_out",
    "indeterminate",
]

RuntimeReservationState = Literal[
    "reserved",
    "executing",
    "completed",
    "failed",
    "timed_out",
    "indeterminate",
]


class ProviderDescriptor(NexusContract):
    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")
    adapter_version: str = Field(min_length=1, max_length=100)
    capabilities: tuple[str, ...] = ()
    effect_class: EffectClass
    network_required: bool = False
    credentials_required: bool = False
    live_provider: bool = False
    supported_modalities: tuple[str, ...] = ("TEXT",)

    @model_validator(mode="after")
    def validate_descriptor(self) -> "ProviderDescriptor":
        if not self.capabilities:
            raise ValueError("ProviderDescriptor requires at least one capability")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("ProviderDescriptor capabilities must be unique")
        if len(self.supported_modalities) != len(set(self.supported_modalities)):
            raise ValueError("ProviderDescriptor modalities must be unique")
        if self.live_provider and not self.network_required:
            raise ValueError("live_provider requires network_required=true")
        return self


class ProviderInvocation(NexusContract):
    invocation_id: str = Field(pattern=r"^PINV-[A-Z0-9_-]{6,64}$")
    request_id: str = Field(pattern=r"^TREQ-[A-Z0-9_-]{6,64}$")
    change_set_id: str = Field(pattern=r"^CHG-[A-Z0-9_-]{6,64}$")
    parent_state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    principal: str = Field(min_length=1, max_length=200)
    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")
    capability: str = Field(min_length=1, max_length=200)
    model_or_resource: str = Field(min_length=1, max_length=300)
    exact_revision: str = Field(min_length=1, max_length=128)
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    reserved_usage_units: int = Field(ge=1)
    maximum_cost_cad: Decimal = Field(default=Decimal("0.00"), ge=0)
    resource_ref: str = Field(min_length=1, max_length=1000)
    purpose: str = Field(min_length=1, max_length=4000)
    requested_effect_class: EffectClass
    permit_id: str | None = Field(default=None, pattern=r"^PERMIT-[A-Z0-9_-]{6,64}$")


class ProviderAttemptResult(NexusContract):
    invocation_id: str
    provider_id: str
    status: ProviderAttemptStatus
    provider_request_id: str | None = Field(default=None, max_length=300)
    model_or_resource: str
    latency_ms: int = Field(ge=0)
    usage_units: int | None = Field(default=None, ge=0)
    cost_cad: Decimal = Field(default=Decimal("0.00"), ge=0)
    finish_status: str | None = Field(default=None, max_length=300)
    response_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    response_payload: str | None = Field(default=None, max_length=100000)
    external_action_performed: bool | None = False
    outcome_known: bool = True

    @model_validator(mode="after")
    def validate_attempt_truth(self) -> "ProviderAttemptResult":
        if self.status == "indeterminate":
            if self.outcome_known:
                raise ValueError("indeterminate provider attempt must set outcome_known=false")
        elif not self.outcome_known:
            raise ValueError("only indeterminate provider attempts may have unknown outcome")
        if self.status == "not_started" and self.external_action_performed not in {False, None}:
            raise ValueError("not_started provider attempt cannot claim external action")
        if self.response_payload is not None and self.response_digest is None:
            raise ValueError("provider response payload requires response_digest")
        return self


class ProviderRuntimeLimits(NexusContract):
    principal_invocations_per_minute: int = Field(default=3, ge=1)
    principal_invocations_per_day: int = Field(default=50, ge=1)
    global_invocations_per_minute: int = Field(default=6, ge=1)
    global_invocations_per_day: int = Field(default=100, ge=1)
    principal_reserved_usage_per_day: int = Field(default=100000, ge=1)
    global_reserved_usage_per_day: int = Field(default=200000, ge=1)
    maximum_usage_per_invocation: int = Field(default=16384, ge=1)
    maximum_cost_cad_per_invocation: Decimal = Field(default=Decimal("0.00"), ge=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "ProviderRuntimeLimits":
        if self.global_invocations_per_minute < self.principal_invocations_per_minute:
            raise ValueError("global per-minute limit cannot be lower than principal limit")
        if self.global_invocations_per_day < self.principal_invocations_per_day:
            raise ValueError("global daily limit cannot be lower than principal limit")
        if self.global_reserved_usage_per_day < self.principal_reserved_usage_per_day:
            raise ValueError("global usage reservation cannot be lower than principal reservation")
        if self.maximum_usage_per_invocation > self.principal_reserved_usage_per_day:
            raise ValueError("per-invocation usage cannot exceed principal daily reservation")
        return self

    def validate_invocation(self, invocation: ProviderInvocation) -> None:
        if invocation.reserved_usage_units > self.maximum_usage_per_invocation:
            raise ValueError("reserved usage exceeds maximum_usage_per_invocation")
        if invocation.maximum_cost_cad > self.maximum_cost_cad_per_invocation:
            raise ValueError("requested cost exceeds maximum_cost_cad_per_invocation")


class RuntimeEmergencyState(NexusContract):
    active: bool
    stop_epoch: int = Field(ge=0)
    reason: str = Field(default="", max_length=2000)
    actor_principal_id: str | None = Field(default=None, max_length=200)
    updated_at: datetime

    @model_validator(mode="after")
    def validate_time(self) -> "RuntimeEmergencyState":
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("RuntimeEmergencyState.updated_at must be timezone-aware")
        return self


class InvocationReservation(NexusContract):
    invocation_id: str
    principal: str
    provider_id: str
    capability: str
    permit_id: str | None = None
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    exact_revision: str
    stop_epoch: int = Field(ge=0)
    state: RuntimeReservationState
    reserved_usage_units: int = Field(ge=1)
    actual_usage_units: int | None = Field(default=None, ge=0)
    created_at: datetime
    updated_at: datetime
    failure_reason: str | None = Field(default=None, max_length=2000)
    replayed: bool = False

    @model_validator(mode="after")
    def validate_times(self) -> "InvocationReservation":
        for name, value in (("created_at", self.created_at), ("updated_at", self.updated_at)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        return self


class ProviderRuntimeAudit(NexusContract):
    adapter_invocations: int = Field(default=0, ge=0)
    provider_api_calls_performed: int = Field(default=0, ge=0)
    network_calls_performed: int = Field(default=0, ge=0)
    credentials_used: int = Field(default=0, ge=0)
    external_actions_performed: int = Field(default=0, ge=0)
    spend_cad: Decimal = Field(default=Decimal("0.00"), ge=0)


class ProviderRuntimeExecution(NexusContract):
    invocation_id: str
    consequence_assessment: ConsequenceAssessment
    attempt: ProviderAttemptResult
    receipt: ExecutionReceipt
    audit: ProviderRuntimeAudit
    replayed: bool = False
