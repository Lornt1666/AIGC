from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from src.domain.epistemic.models import ContractModel


ToolScope = Literal["read", "write", "execute", "deploy"]
DecisionStatus = Literal[
    "DENIED",
    "APPROVAL_REQUIRED",
    "POLICY_PERMIT_PENDING_EXECUTION_GATE",
    "DUPLICATE_INTENT",
    "IDEMPOTENCY_CONFLICT",
]
ExecutionStatus = Literal["SUCCEEDED", "FAILED", "NOT_EXECUTED"]


class ToolCapability(ContractModel):
    tool_name: str = Field(min_length=1, max_length=300)
    scopes: tuple[ToolScope, ...]
    side_effecting: bool


class AgentToolPolicy(ContractModel):
    agent_id: str = Field(pattern=r"^AGT-[A-Z][A-Z0-9-]{2,63}$")
    capabilities: tuple[ToolCapability, ...] = ()
    human_approval_scopes: tuple[ToolScope, ...] = ()
    maximum_requests_per_run: int = Field(default=0, ge=0, le=10000)
    maximum_cost_units_per_run: int = Field(default=0, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def unique_capabilities(self) -> "AgentToolPolicy":
        names = [capability.tool_name for capability in self.capabilities]
        if len(names) != len(set(names)):
            raise ValueError("AgentToolPolicy contains duplicate tool capabilities")
        return self


class HumanApprovalReference(ContractModel):
    approval_id: str = Field(min_length=1, max_length=300)
    approver_actor_id: str = Field(min_length=1, max_length=300)
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    exact_revision: str = Field(min_length=7, max_length=64)
    status: Literal["active", "revoked", "expired"]


class ToolInvocationRequest(ContractModel):
    request_id: str = Field(min_length=1, max_length=300)
    run_id: str = Field(min_length=1, max_length=300)
    agent_id: str = Field(pattern=r"^AGT-[A-Z][A-Z0-9-]{2,63}$")
    exact_revision: str = Field(min_length=7, max_length=64)
    tool_name: str = Field(min_length=1, max_length=300)
    scope: ToolScope
    purpose: str = Field(min_length=1, max_length=2000)
    resource_id: str = Field(min_length=1, max_length=2000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    estimated_cost_units: int = Field(default=0, ge=0, le=1_000_000)
    approval_reference: HumanApprovalReference | None = None


class ToolDecisionReceipt(ContractModel):
    contract_version: Literal["1.0.0"] = "1.0.0"
    request_id: str
    run_id: str
    agent_id: str
    tool_name: str
    scope: ToolScope
    exact_revision: str
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    parameters_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: DecisionStatus
    reason_codes: tuple[str, ...] = ()
    external_action_performed: Literal[False] = False
    production_activation_authorized: Literal[False] = False


class ToolExecutionReceipt(ContractModel):
    """Evidence supplied by a future execution adapter; this slice never creates success receipts itself."""

    contract_version: Literal["1.0.0"] = "1.0.0"
    execution_id: str = Field(min_length=1, max_length=300)
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    exact_revision: str = Field(min_length=7, max_length=64)
    status: ExecutionStatus
    output_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    external_action_performed: bool
    state_changed: bool
