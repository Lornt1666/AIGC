from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from src.domain.nexus.contracts import EffectClass, NexusContract
from src.security.redactor import Redactor


CoordinationStrategy = Literal["HIERARCHICAL_DAG", "CAPABILITY_DAG"]
DataClassification = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
StopCondition = Literal[
    "ACCEPTANCE_SATISFIED",
    "SAFETY_BLOCKER",
    "ITERATION_BUDGET_EXHAUSTED",
    "NO_PROGRESS_LIMIT",
]

FORBIDDEN_PARAMETER_KEYS = {
    "api_key",
    "authority_granted",
    "authorization",
    "credential",
    "credential_ref",
    "execution_permit",
    "password",
    "permit",
    "permit_id",
    "private_key",
    "secret",
    "token",
}


def _keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            found.add(str(key).casefold())
            found.update(_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_keys(nested))
    return found


def _reject_secret_material(label: str, value: Any) -> None:
    forbidden = sorted(_keys(value).intersection(FORBIDDEN_PARAMETER_KEYS))
    if forbidden:
        raise ValueError(f"{label} contains forbidden authority or secret keys: {', '.join(forbidden)}")
    serialized = json.dumps(value, sort_keys=True, default=str)
    if Redactor().redact_text(serialized) != serialized:
        raise ValueError(f"{label} contains credential-like material")


class CoordinationStateInput(NexusContract):
    state_id: str = Field(pattern=r"^COORD-STATE-[A-Z0-9_-]{6,64}$")
    revision: int = Field(default=0, ge=0, le=1_000_000)
    parent_state_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    artifact_refs: tuple[str, ...] = Field(default=(), max_length=50)
    values: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_state(self) -> "CoordinationStateInput":
        if len(self.artifact_refs) != len(set(self.artifact_refs)):
            raise ValueError("state artifact_refs must be unique")
        if len(self.values) > 50:
            raise ValueError("state values cannot contain more than 50 keys")
        _reject_secret_material("state values", self.values)
        return self


class IterationPolicy(NexusContract):
    current_iteration: int = Field(default=0, ge=0, le=11)
    maximum_iterations: int = Field(default=4, ge=1, le=12)
    minimum_progress_delta: float = Field(
        default=0.05, ge=0.0, le=1.0, allow_inf_nan=False
    )
    no_progress_limit: int = Field(default=2, ge=1, le=6)
    stop_conditions: tuple[StopCondition, ...] = (
        "ACCEPTANCE_SATISFIED",
        "SAFETY_BLOCKER",
        "ITERATION_BUDGET_EXHAUSTED",
        "NO_PROGRESS_LIMIT",
    )

    @model_validator(mode="after")
    def validate_iteration_bounds(self) -> "IterationPolicy":
        if self.current_iteration >= self.maximum_iterations:
            raise ValueError("current_iteration must be lower than maximum_iterations")
        if self.no_progress_limit > self.maximum_iterations:
            raise ValueError("no_progress_limit cannot exceed maximum_iterations")
        if len(self.stop_conditions) != len(set(self.stop_conditions)):
            raise ValueError("stop_conditions must be unique")
        return self


class ToolFunctionSpec(NexusContract):
    tool_id: str = Field(pattern=r"^TOOL-[A-Z0-9_-]{3,64}$")
    function_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,120}$")
    purpose: str = Field(min_length=3, max_length=1000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: dict[str, str] = Field(default_factory=dict)
    effect_class: EffectClass = "PURE"
    data_classification: DataClassification = "INTERNAL"
    target_ref: str | None = Field(default=None, min_length=1, max_length=500)
    credentials_required: bool = False
    internal_sandbox_only: bool = False
    maximum_calls_per_iteration: int = Field(default=1, ge=1, le=16)
    estimated_time_ms: int = Field(default=0, ge=0, le=3_600_000)
    estimated_cost_cad: Decimal = Field(default=Decimal("0.00"), ge=0, le=10_000_000)
    rollback_steps: tuple[str, ...] = Field(default=(), max_length=16)
    legal_commitment: bool = False
    physical_effect: bool = False
    destructive: bool = False
    irreversible: bool = False
    outcome_indeterminate: bool = False

    @field_validator("rollback_steps")
    @classmethod
    def unique_rollback_steps(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("rollback_steps must be unique")
        return value

    @model_validator(mode="after")
    def validate_tool_boundary(self) -> "ToolFunctionSpec":
        _reject_secret_material("tool parameters", self.parameters)
        if self.effect_class not in {"PURE", "READ_LOCAL"} and self.target_ref is None:
            raise ValueError("external or consequential tool functions require target_ref")
        if self.effect_class in {"WRITE_REVERSIBLE", "WRITE_COMPENSATABLE"} and not self.rollback_steps:
            raise ValueError("reversible or compensatable tools require rollback_steps")
        if self.estimated_cost_cad > 0 and self.effect_class != "FINANCIAL":
            raise ValueError("non-zero estimated_cost_cad requires FINANCIAL effect_class")
        if (self.destructive or self.irreversible) and self.effect_class != "WRITE_IRREVERSIBLE":
            raise ValueError("destructive or irreversible tools require WRITE_IRREVERSIBLE effect_class")
        return self


class AgentFunctionSpec(NexusContract):
    agent_id: str = Field(pattern=r"^AGT-[A-Z][A-Z0-9-]{2,63}$")
    role: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,80}$")
    mandate: str = Field(min_length=8, max_length=1000)
    capabilities: tuple[str, ...] = Field(default=(), max_length=32)
    assigned_tool_ids: tuple[str, ...] = Field(default=(), max_length=12)
    depends_on_agent_ids: tuple[str, ...] = Field(default=(), max_length=12)
    output_contract: str = Field(min_length=3, max_length=500)
    verification_function: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,120}$")

    @model_validator(mode="after")
    def validate_agent_lists(self) -> "AgentFunctionSpec":
        for label, values in (
            ("capabilities", self.capabilities),
            ("assigned_tool_ids", self.assigned_tool_ids),
            ("depends_on_agent_ids", self.depends_on_agent_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        if self.agent_id in self.depends_on_agent_ids:
            raise ValueError("agent cannot depend on itself")
        return self


class MultiAgentPolicy(NexusContract):
    strategy: CoordinationStrategy = "HIERARCHICAL_DAG"
    maximum_parallel_agents: int = Field(default=4, ge=1, le=16)
    fail_fast: bool = True
    require_independent_verification: bool = True


class CoordinationEngineeringRequest(NexusContract):
    request_id: str = Field(pattern=r"^COORD-REQ-[A-Z0-9_-]{6,64}$")
    objective: str = Field(min_length=1, max_length=4000)
    state: CoordinationStateInput
    iteration: IterationPolicy = Field(default_factory=IterationPolicy)
    tools: tuple[ToolFunctionSpec, ...] = Field(default=(), max_length=12)
    agents: tuple[AgentFunctionSpec, ...] = Field(min_length=1, max_length=12)
    coordination: MultiAgentPolicy = Field(default_factory=MultiAgentPolicy)
    acceptance_criteria: tuple[str, ...] = Field(min_length=1, max_length=32)
    execution_requested: bool = False
    deterministic_seed: Literal[42] = 42

    @model_validator(mode="after")
    def validate_graph_and_references(self) -> "CoordinationEngineeringRequest":
        tool_ids = [item.tool_id for item in self.tools]
        agent_ids = [item.agent_id for item in self.agents]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("tool IDs must be unique")
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("agent IDs must be unique")
        if len(self.acceptance_criteria) != len(set(self.acceptance_criteria)):
            raise ValueError("acceptance_criteria must be unique")
        known_tools = set(tool_ids)
        known_agents = set(agent_ids)
        for agent in self.agents:
            missing_tools = sorted(set(agent.assigned_tool_ids).difference(known_tools))
            if missing_tools:
                raise ValueError(f"{agent.agent_id} references unknown tools: {', '.join(missing_tools)}")
            missing_agents = sorted(set(agent.depends_on_agent_ids).difference(known_agents))
            if missing_agents:
                raise ValueError(f"{agent.agent_id} references unknown agents: {', '.join(missing_agents)}")
        remaining = set(agent_ids)
        resolved: set[str] = set()
        by_id = {item.agent_id: item for item in self.agents}
        while remaining:
            ready = sorted(
                agent_id
                for agent_id in remaining
                if set(by_id[agent_id].depends_on_agent_ids) <= resolved
            )
            if not ready:
                raise ValueError("agent dependency graph contains a cycle")
            resolved.update(ready)
            remaining.difference_update(ready)
        total_calls = sum(item.maximum_calls_per_iteration for item in self.tools)
        if total_calls * self.iteration.maximum_iterations > 512:
            raise ValueError("tool call budget exceeds the 512-call planning ceiling")
        request_payload = self.model_dump(mode="json")
        _reject_secret_material("coordination request", request_payload)
        serialized_size = len(
            json.dumps(request_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        if serialized_size > 262_144:
            raise ValueError("coordination request exceeds the 262144-byte contract ceiling")
        return self


class CoordinationEngineeringReceipt(NexusContract):
    schema_version: Literal["aigc.coordination-engineering-receipt.v1"]
    endpoint: Literal["POST /v1/coordination/engineer"]
    receipt_id: str = Field(pattern=r"^COORD-RCPT-[A-F0-9]{24}$")
    request_id: str
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: dict[str, Any]
    iteration: dict[str, Any]
    tooling: tuple[dict[str, Any], ...]
    multi_agent_coordination: dict[str, Any]
    alpha_plan: dict[str, Any]
    transition_proposal: dict[str, Any]
    verification: dict[str, Any]
    terminal_status: Literal["PASS", "BLOCKED"]
    production_ready: Literal[False] = False
    zero_egress: Literal[True] = True
    provider_calls_performed: Literal[0] = 0
    tool_dispatches_performed: Literal[0] = 0
    processes_spawned: Literal[0] = 0
    memory_writes_performed: Literal[0] = 0
    external_actions_performed: Literal[0] = 0
    authority_granted: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
