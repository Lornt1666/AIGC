from __future__ import annotations

from typing import Any

from src.alpha_plan.models import AlphaOperationRequest, AlphaPlanRequest
from src.alpha_plan.orchestrator import compose_alpha_plan
from src.coordination.models import (
    AgentFunctionSpec,
    CoordinationEngineeringRequest,
    CoordinationEngineeringReceipt,
    ToolFunctionSpec,
)
from src.core.epistemic.canonicalization import canonical_sha256


SCHEMA_VERSION = "aigc.coordination-engineering-receipt.v1"
ENDPOINT = "POST /v1/coordination/engineer"


def _operation_id(kind: str, identifier: str) -> str:
    digest = canonical_sha256({"kind": kind, "identifier": identifier})[:16].upper()
    return f"ALPHA-OP-{kind}_{digest}"


def _agent_waves(
    agents: tuple[AgentFunctionSpec, ...], maximum_parallel_agents: int
) -> tuple[tuple[str, ...], ...]:
    by_id = {item.agent_id: item for item in agents}
    remaining = set(by_id)
    resolved: set[str] = set()
    waves: list[tuple[str, ...]] = []
    while remaining:
        ready = tuple(
            sorted(
                agent_id
                for agent_id in remaining
                if set(by_id[agent_id].depends_on_agent_ids) <= resolved
            )
        )
        if not ready:  # defensive: the request contract already rejects cycles
            raise ValueError("agent dependency graph contains a cycle")
        waves.extend(
            ready[index : index + maximum_parallel_agents]
            for index in range(0, len(ready), maximum_parallel_agents)
        )
        resolved.update(ready)
        remaining.difference_update(ready)
    return tuple(waves)


def _tool_disposition(tool: ToolFunctionSpec) -> str:
    if tool.outcome_indeterminate:
        return "RECONCILIATION_REQUIRED"
    if (
        tool.credentials_required
        or tool.data_classification in {"CONFIDENTIAL", "RESTRICTED"}
        or tool.legal_commitment
        or tool.physical_effect
        or tool.destructive
        or tool.irreversible
    ):
        return "BLOCKED_PERMISSION"
    if tool.effect_class in {"PURE", "READ_LOCAL"}:
        return "SIMULATION_READY"
    if tool.effect_class == "READ_EXTERNAL":
        return (
            "SIMULATION_READY"
            if tool.data_classification == "PUBLIC" and not tool.credentials_required
            else "BLOCKED_PERMISSION"
        )
    if tool.effect_class == "WRITE_REVERSIBLE" and tool.internal_sandbox_only:
        return "SIMULATION_READY"
    return "BLOCKED_PERMISSION"


def _build_operations(
    request: CoordinationEngineeringRequest,
    state_sha256: str,
) -> tuple[AlphaOperationRequest, ...]:
    state_operation_id = _operation_id("STATE", request.state.state_id)
    operations: list[AlphaOperationRequest] = [
        AlphaOperationRequest(
            operation_id=state_operation_id,
            function_name="coordination.state.validate",
            parameters={
                "state_id": request.state.state_id,
                "revision": request.state.revision,
                "state_sha256": state_sha256,
                "parent_state_sha256": request.state.parent_state_sha256,
                "artifact_refs": list(request.state.artifact_refs),
            },
            expected_outputs={"state_validation": "object", "state_sha256": "sha256"},
            priority=10,
            effect_class="PURE",
            estimated_time_ms=5,
        )
    ]

    tool_operation_ids: dict[str, str] = {}
    for index, tool in enumerate(sorted(request.tools, key=lambda item: item.tool_id), start=1):
        operation_id = _operation_id("TOOL", tool.tool_id)
        tool_operation_ids[tool.tool_id] = operation_id
        operations.append(
            AlphaOperationRequest(
                operation_id=operation_id,
                function_name=tool.function_name,
                parameters={
                    **tool.parameters,
                    "coordination_request_id": request.request_id,
                    "tool_id": tool.tool_id,
                    "purpose": tool.purpose,
                    "maximum_calls_per_iteration": tool.maximum_calls_per_iteration,
                },
                expected_outputs=tool.expected_outputs,
                depends_on=(state_operation_id,),
                priority=20 + index,
                effect_class=tool.effect_class,
                target_ref=tool.target_ref,
                public_read_only=(
                    tool.effect_class == "READ_EXTERNAL"
                    and tool.data_classification == "PUBLIC"
                    and not tool.credentials_required
                ),
                internal_sandbox_only=tool.internal_sandbox_only,
                accesses_private_data=tool.data_classification in {"CONFIDENTIAL", "RESTRICTED"},
                credentials_required=tool.credentials_required,
                persistent_internal_mutation=(
                    tool.effect_class in {"WRITE_REVERSIBLE", "WRITE_COMPENSATABLE"}
                    and not tool.internal_sandbox_only
                ),
                external_mutation=(
                    tool.effect_class
                    in {"WRITE_REVERSIBLE", "WRITE_COMPENSATABLE", "WRITE_IRREVERSIBLE"}
                    and not tool.internal_sandbox_only
                ),
                communication=tool.effect_class == "COMMUNICATION",
                financial_spend_cad=tool.estimated_cost_cad,
                legal_commitment=tool.legal_commitment,
                security_sensitive=tool.effect_class == "SECURITY_SENSITIVE",
                production_change=tool.effect_class == "DEPLOYMENT",
                physical_effect=tool.physical_effect,
                destructive=tool.destructive,
                irreversible=tool.irreversible or tool.effect_class == "WRITE_IRREVERSIBLE",
                outcome_indeterminate=tool.outcome_indeterminate,
                rollback_steps=tool.rollback_steps,
                estimated_time_ms=tool.estimated_time_ms,
            )
        )

    agent_operation_ids = {
        agent.agent_id: _operation_id("AGENT", agent.agent_id) for agent in request.agents
    }
    for index, agent in enumerate(sorted(request.agents, key=lambda item: item.agent_id), start=1):
        dependencies = [state_operation_id]
        dependencies.extend(tool_operation_ids[item] for item in agent.assigned_tool_ids)
        dependencies.extend(agent_operation_ids[item] for item in agent.depends_on_agent_ids)
        operations.append(
            AlphaOperationRequest(
                operation_id=agent_operation_ids[agent.agent_id],
                function_name="coordination.agent.coordinate",
                parameters={
                    "agent_id": agent.agent_id,
                    "role": agent.role,
                    "mandate": agent.mandate,
                    "capabilities": list(agent.capabilities),
                    "assigned_tool_ids": list(agent.assigned_tool_ids),
                    "output_contract": agent.output_contract,
                    "verification_function": agent.verification_function,
                },
                expected_outputs={
                    "candidate_output": agent.output_contract,
                    "verification_receipt": "object",
                },
                depends_on=tuple(dict.fromkeys(dependencies)),
                priority=100 + index,
                effect_class="PURE",
                estimated_time_ms=10,
            )
        )

    iteration_operation_id = _operation_id("ITERATE", request.request_id)
    operations.append(
        AlphaOperationRequest(
            operation_id=iteration_operation_id,
            function_name="coordination.iteration.evaluate",
            parameters={
                "current_iteration": request.iteration.current_iteration,
                "maximum_iterations": request.iteration.maximum_iterations,
                "minimum_progress_delta": request.iteration.minimum_progress_delta,
                "no_progress_limit": request.iteration.no_progress_limit,
                "acceptance_criteria": list(request.acceptance_criteria),
                "stop_conditions": list(request.iteration.stop_conditions),
            },
            expected_outputs={"iteration_decision": "object", "progress_receipt": "object"},
            depends_on=tuple(agent_operation_ids.values()),
            priority=900,
            effect_class="PURE",
            estimated_time_ms=5,
        )
    )
    operations.append(
        AlphaOperationRequest(
            operation_id=_operation_id("RECEIPT", request.request_id),
            function_name="coordination.receipt.emit",
            parameters={
                "request_id": request.request_id,
                "state_sha256": state_sha256,
                "schema_version": SCHEMA_VERSION,
            },
            expected_outputs={"coordination_receipt": SCHEMA_VERSION},
            depends_on=(iteration_operation_id,),
            priority=950,
            effect_class="PURE",
            estimated_time_ms=5,
        )
    )
    return tuple(operations)


def engineer_coordination_plan(
    request: CoordinationEngineeringRequest,
) -> dict[str, Any]:
    """Engineer a deterministic coordination graph; never dispatch tools or persist state."""

    request_payload = request.model_dump(mode="json")
    input_sha256 = canonical_sha256(request_payload)
    state_payload = request.state.model_dump(mode="json")
    state_sha256 = canonical_sha256(state_payload)
    waves = _agent_waves(request.agents, request.coordination.maximum_parallel_agents)
    operations = _build_operations(request, state_sha256)
    alpha_plan = compose_alpha_plan(
        AlphaPlanRequest(
            request_id="ALPHA-REQ-" + input_sha256[:24].upper(),
            objective=request.objective,
            context_refs=tuple(request.state.artifact_refs),
            operations=operations,
            execution_requested=request.execution_requested,
        )
    )

    tool_resolutions = []
    blocked_tools: list[str] = []
    reconciliation_tools: list[str] = []
    total_calls_per_iteration = 0
    for tool in sorted(request.tools, key=lambda item: item.tool_id):
        disposition = _tool_disposition(tool)
        if disposition == "RECONCILIATION_REQUIRED":
            reconciliation_tools.append(tool.tool_id)
        elif disposition != "SIMULATION_READY":
            blocked_tools.append(tool.tool_id)
        total_calls_per_iteration += tool.maximum_calls_per_iteration
        tool_resolutions.append(
            {
                "tool_id": tool.tool_id,
                "function_name": tool.function_name,
                "effect_class": tool.effect_class,
                "data_classification": tool.data_classification,
                "maximum_calls_per_iteration": tool.maximum_calls_per_iteration,
                "disposition": disposition,
                "authority_granted": False,
                "dispatch_performed": False,
            }
        )

    agent_by_id = {item.agent_id: item for item in request.agents}
    agent_resolution: dict[str, dict[str, Any]] = {}
    blocked_agents: set[str] = set()
    for wave in waves:
        for agent_id in wave:
            agent = agent_by_id[agent_id]
            blocked_assignments = sorted(
                set(agent.assigned_tool_ids).intersection(
                    [*blocked_tools, *reconciliation_tools]
                )
            )
            blocked_dependencies = sorted(
                set(agent.depends_on_agent_ids).intersection(blocked_agents)
            )
            if blocked_assignments:
                disposition = "BLOCKED_PERMISSION"
            elif blocked_dependencies:
                disposition = "BLOCKED_DEPENDENCY"
            else:
                disposition = "PLAN_READY"
            if disposition != "PLAN_READY":
                blocked_agents.add(agent_id)
            agent_resolution[agent_id] = {
                "agent_id": agent.agent_id,
                "role": agent.role,
                "assigned_tool_ids": list(agent.assigned_tool_ids),
                "depends_on_agent_ids": list(agent.depends_on_agent_ids),
                "output_contract": agent.output_contract,
                "verification_function": agent.verification_function,
                "blocked_tool_ids": blocked_assignments,
                "blocked_dependency_ids": blocked_dependencies,
                "disposition": disposition,
                "process_spawned": False,
                "provider_call_performed": False,
            }
    agent_plans = [agent_resolution[item] for item in sorted(agent_resolution)]

    iteration_exhausted = request.iteration.current_iteration + 1 >= request.iteration.maximum_iterations
    blockers: list[str] = []
    if reconciliation_tools:
        blockers.append("TOOL_RECONCILIATION_REQUIRED:" + reconciliation_tools[0])
    elif blocked_tools:
        blockers.append("TOOL_AUTHORITY_REQUIRED:" + blocked_tools[0])
    if request.execution_requested:
        blockers.append("ENDPOINT_PLAN_ONLY")
    if iteration_exhausted:
        blockers.append("ITERATION_BUDGET_EXHAUSTED_AFTER_CURRENT_PASS")
    terminal_status = "BLOCKED" if blockers else "PASS"
    next_iteration = None if iteration_exhausted else request.iteration.current_iteration + 1

    candidate_state_seed = {
        "prior_state_sha256": state_sha256,
        "request_id": request.request_id,
        "alpha_plan_receipt_sha256": alpha_plan["receipt_sha256"],
        "proposed_revision": request.state.revision + 1,
    }
    receipt_seed: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "endpoint": ENDPOINT,
        "receipt_id": "COORD-RCPT-" + input_sha256[:24].upper(),
        "request_id": request.request_id,
        "input_sha256": input_sha256,
        "state": {
            "state_id": request.state.state_id,
            "revision": request.state.revision,
            "state_sha256": state_sha256,
            "parent_state_sha256": request.state.parent_state_sha256,
            "artifact_refs": list(request.state.artifact_refs),
            "persistence_performed": False,
        },
        "iteration": {
            "current_iteration": request.iteration.current_iteration,
            "next_iteration": next_iteration,
            "maximum_iterations": request.iteration.maximum_iterations,
            "minimum_progress_delta": request.iteration.minimum_progress_delta,
            "no_progress_limit": request.iteration.no_progress_limit,
            "stop_conditions": list(request.iteration.stop_conditions),
            "maximum_tool_calls_per_iteration": total_calls_per_iteration,
            "maximum_tool_calls_over_plan": total_calls_per_iteration
            * request.iteration.maximum_iterations,
            "decision": "STOP" if blockers else "CONTINUE_TO_SIMULATION",
        },
        "tooling": tool_resolutions,
        "multi_agent_coordination": {
            "strategy": request.coordination.strategy,
            "maximum_parallel_agents": request.coordination.maximum_parallel_agents,
            "fail_fast": request.coordination.fail_fast,
            "require_independent_verification": request.coordination.require_independent_verification,
            "waves": [
                {"wave": index, "agent_ids": list(agent_ids)}
                for index, agent_ids in enumerate(waves)
            ],
            "agents": agent_plans,
        },
        "alpha_plan": alpha_plan,
        "transition_proposal": {
            "status": "PROPOSED_NOT_APPLIED",
            "prior_state_sha256": state_sha256,
            "proposed_revision": request.state.revision + 1,
            "candidate_state_sha256": canonical_sha256(candidate_state_seed),
            "required_admission": [
                "all_acceptance_criteria_verified",
                "all_agent_verification_receipts_valid",
                "no_safety_blocker",
                "confirmed_execution_receipt_if_effects_occur",
            ],
        },
        "verification": {
            "checks": [
                "closed_request_contract",
                "secret_and_authority_material_rejected",
                "unique_tool_and_agent_ids",
                "known_tool_assignments",
                "known_agent_dependencies",
                "acyclic_agent_graph",
                "bounded_iterations",
                "bounded_tool_call_budget",
                "alpha_plan_simulated",
                "zero_egress",
            ],
            "result": "BLOCKED" if blockers else "PASS",
            "first_blocker": blockers[0] if blockers else None,
        },
        "terminal_status": terminal_status,
        "production_ready": False,
        "zero_egress": True,
        "provider_calls_performed": 0,
        "tool_dispatches_performed": 0,
        "processes_spawned": 0,
        "memory_writes_performed": 0,
        "external_actions_performed": 0,
        "authority_granted": False,
    }
    receipt_seed["receipt_sha256"] = canonical_sha256(receipt_seed)
    return CoordinationEngineeringReceipt.model_validate(receipt_seed).model_dump(mode="json")
