from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from src.domain.nexus.contracts import EffectClass, NexusContract
from src.security.redactor import Redactor


NodeType = Literal["atomic", "composite"]
NodeDisposition = Literal["READY_FOR_EXECUTOR", "BLOCKED_PERMISSION"]
SimulationResult = Literal["OK", "BLOCKED"]
TerminalStatus = Literal["PASS", "BLOCKED"]
AlphaDomainProfile = Literal[
    "GENERAL",
    "MULTIMODAL_ECOSYSTEM",
    "PROCUREMENT_ACCELERATION",
]

AUTHORITY_SHAPED_KEYS = {
    "authority_granted",
    "authorized",
    "credential",
    "credential_ref",
    "execution_authorized",
    "existing_explicit_authority",
    "permit",
    "permit_id",
    "secret",
    "token",
}


def _parameter_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).lower())
            keys.update(_parameter_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            keys.update(_parameter_keys(nested))
    return keys


class AlphaOperationRequest(NexusContract):
    """A non-authoritative description of one proposed function call."""

    operation_id: str = Field(pattern=r"^ALPHA-OP-[A-Z0-9_-]{6,64}$")
    function_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,120}$")
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: dict[str, str] = Field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    priority: int = Field(default=100, ge=0, le=1000)
    effect_class: EffectClass = "PURE"
    target_ref: str | None = Field(default=None, min_length=1, max_length=500)
    public_read_only: bool = False
    internal_sandbox_only: bool = False
    accesses_private_data: bool = False
    credentials_required: bool = False
    persistent_internal_mutation: bool = False
    external_mutation: bool = False
    communication: bool = False
    financial_spend_cad: Decimal = Field(default=Decimal("0.00"), ge=0)
    legal_commitment: bool = False
    security_sensitive: bool = False
    production_change: bool = False
    physical_effect: bool = False
    destructive: bool = False
    irreversible: bool = False
    outcome_indeterminate: bool = False
    rollback_steps: tuple[str, ...] = ()
    estimated_time_ms: int = Field(default=0, ge=0, le=86_400_000)

    @field_validator("depends_on", "rollback_steps")
    @classmethod
    def require_unique_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("list values must be unique")
        return value

    @model_validator(mode="after")
    def reject_authority_and_secret_material(self) -> "AlphaOperationRequest":
        if self.operation_id in self.depends_on:
            raise ValueError("operation cannot depend on itself")
        forbidden = sorted(_parameter_keys(self.parameters).intersection(AUTHORITY_SHAPED_KEYS))
        if forbidden:
            raise ValueError(
                "parameters cannot contain authority- or credential-shaped keys: "
                + ", ".join(forbidden)
            )
        serialized = json.dumps(self.parameters, sort_keys=True, default=str)
        if Redactor().redact_text(serialized) != serialized:
            raise ValueError("parameters contain credential-like material")
        if self.effect_class in {
            "READ_EXTERNAL",
            "WRITE_REVERSIBLE",
            "WRITE_COMPENSATABLE",
            "WRITE_IRREVERSIBLE",
            "FINANCIAL",
            "COMMUNICATION",
            "DEPLOYMENT",
            "SECURITY_SENSITIVE",
        } and self.target_ref is None:
            raise ValueError("external or consequential operations require target_ref")
        if self.effect_class in {"WRITE_REVERSIBLE", "WRITE_COMPENSATABLE"} and not self.rollback_steps:
            raise ValueError("reversible or compensatable writes require rollback_steps")
        return self


class AlphaPlanRequest(NexusContract):
    """Closed request for a deterministic Alpha Plan; never an execution permit."""

    request_id: str = Field(pattern=r"^ALPHA-REQ-[A-Z0-9_-]{6,64}$")
    objective: str = Field(min_length=1, max_length=4000)
    domain_profile: AlphaDomainProfile = "GENERAL"
    context_refs: tuple[str, ...] = Field(default=(), max_length=50)
    operations: tuple[AlphaOperationRequest, ...] = Field(default=(), max_length=32)
    execution_requested: bool = False
    deterministic_seed: Literal[42] = 42
    created_at: datetime | None = None

    @model_validator(mode="after")
    def validate_closed_request(self) -> "AlphaPlanRequest":
        operation_ids = [item.operation_id for item in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("operation IDs must be unique")
        if len(self.context_refs) != len(set(self.context_refs)):
            raise ValueError("context_refs must be unique")
        if any(len(item) > 500 for item in self.context_refs):
            raise ValueError("context_refs entries cannot exceed 500 characters")
        if self.created_at is not None and (
            self.created_at.tzinfo is None or self.created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be timezone-aware when supplied")
        return self


class RetryPolicy(NexusContract):
    strategy: Literal["none", "fixed", "exponential"]
    max_retries: int = Field(ge=0, le=3)
    base_delay_ms: int = Field(ge=0, le=60_000)
    reconciliation_before_retry: bool


class ErrorHandling(NexusContract):
    on_error: Literal["abort", "compensate", "reconcile"]
    compensate_steps: tuple[str, ...] = ()
    indeterminate_result_policy: Literal["STOP_AND_RECONCILE"] = "STOP_AND_RECONCILE"


class AuthorizationRequirements(NexusContract):
    authority_requirement: Literal["POLICY", "EXPLICIT", "RECONCILIATION"]
    consent_required: bool
    one_use_permit_required: bool
    required_bindings: tuple[str, ...] = ()
    caller_supplied_authority_accepted: Literal[False] = False
    authority_granted: Literal[False] = False


class ObservabilityHooks(NexusContract):
    log_id: str = Field(pattern=r"^ALOG-[A-F0-9]{24}$")
    metrics: tuple[str, ...]
    audit_fields: tuple[str, ...]


class EstimatedCost(NexusContract):
    time_ms: int = Field(ge=0)
    monetary_cad: Decimal = Field(ge=0)


class AlphaNode(NexusContract):
    node_id: str = Field(pattern=r"^ALPHA-NODE-[A-F0-9]{24}$")
    name: str
    type: NodeType
    priority: int = Field(ge=0, le=1000)
    children: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    params: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: dict[str, str] = Field(default_factory=dict)
    idempotency_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    authorization_requirements: AuthorizationRequirements
    retry_policy: RetryPolicy
    error_handling: ErrorHandling
    observability: ObservabilityHooks
    estimated_cost: EstimatedCost
    disposition: NodeDisposition

    @model_validator(mode="after")
    def enforce_level_semantics(self) -> "AlphaNode":
        if self.type == "atomic" and self.children:
            raise ValueError("atomic nodes cannot have children")
        if self.type == "composite" and not self.children:
            raise ValueError("composite nodes require children")
        return self


class AlphaLevel(NexusContract):
    level: int = Field(ge=0, le=32)
    nodes: tuple[AlphaNode, ...] = Field(min_length=1, max_length=64)


class AlphaVerification(NexusContract):
    safety_checks: tuple[str, ...]
    authorization_checks: tuple[str, ...]
    graph_checks: tuple[str, ...]
    simulation_result: SimulationResult
    first_blocker: str | None = None


class AlphaPlan(NexusContract):
    alpha_plan_version: Literal["aigc.alpha-plan.v1"]
    id: str = Field(pattern=r"^ALPHA-PLAN-[A-F0-9]{24}$")
    request_id: str
    domain_profile: AlphaDomainProfile
    priority: int = Field(ge=0, le=1000)
    alpha_levels: tuple[AlphaLevel, ...] = Field(min_length=2, max_length=33)
    deterministic_seed: Literal[42]
    created_at: datetime | None
    human_summary: str
    execution_sequence: tuple[dict[str, Any], ...]
    verification: AlphaVerification
    meta_config: dict[str, Any]
    terminal_status: TerminalStatus
    zero_egress: Literal[True] = True
    provider_calls_performed: Literal[0] = 0
    memory_writes_performed: Literal[0] = 0
    policy_updates_applied: Literal[0] = 0
    external_actions_performed: Literal[0] = 0
    authority_granted: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_hierarchy(self) -> "AlphaPlan":
        levels = [item.level for item in self.alpha_levels]
        if levels != list(range(len(levels))):
            raise ValueError("alpha levels must be contiguous and start at zero")
        node_ids = [node.node_id for level in self.alpha_levels for node in level.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node IDs must be globally unique")
        known: set[str] = set()
        for level in self.alpha_levels:
            for node in level.nodes:
                if level.level == 0 and node.type != "atomic":
                    raise ValueError("level zero may contain only atomic nodes")
                if level.level > 0 and node.type != "composite":
                    raise ValueError("higher levels may contain only composite nodes")
                if any(child not in known for child in node.children):
                    raise ValueError("composite children must refer to lower-level nodes")
            known.update(node.node_id for node in level.nodes)
        return self
