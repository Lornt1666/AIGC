from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.alpha_plan.models import (
    AlphaLevel,
    AlphaNode,
    AlphaOperationRequest,
    AlphaPlan,
    AlphaPlanRequest,
    AlphaVerification,
    AuthorizationRequirements,
    ErrorHandling,
    EstimatedCost,
    ObservabilityHooks,
    RetryPolicy,
)
from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.autonomy_policy import assess_autonomy
from src.domain.nexus.autonomy import ActionIntent, ConsequenceAssessment


ROOT = Path(__file__).resolve().parents[2]


class AlphaPlanPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    policy_id: str
    deterministic_seed: int = Field(ge=0)
    maximum_operations: int = Field(ge=1, le=128)
    maximum_parameter_bytes: int = Field(ge=1, le=1_000_000)
    maximum_automatic_retries: int = Field(ge=0, le=3)
    stable_meta_config: dict[str, float]
    required_external_bindings: tuple[str, ...]


def load_alpha_plan_policy() -> AlphaPlanPolicy:
    path = ROOT / "config" / "aigc_alpha_plan_policy.v1.json"
    return AlphaPlanPolicy.model_validate_json(path.read_text(encoding="utf-8"))


def _json_projection(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_projection(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_projection(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _default_operations(request: AlphaPlanRequest) -> tuple[AlphaOperationRequest, ...]:
    profiles_path = ROOT / "config" / "aigc_alpha_domain_profiles.v1.json"
    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    profile = profiles["profiles"][request.domain_profile]
    return tuple(
        AlphaOperationRequest.model_validate(
            {
                **item,
                "parameters": {
                    **item.get("parameters", {}),
                    "objective": request.objective,
                    "context_refs": list(request.context_refs),
                },
            }
        )
        for item in profile["operations"]
    )


def _topological_order(
    operations: tuple[AlphaOperationRequest, ...],
) -> tuple[AlphaOperationRequest, ...]:
    by_id = {item.operation_id: item for item in operations}
    for operation in operations:
        missing = sorted(set(operation.depends_on).difference(by_id))
        if missing:
            raise ValueError(
                f"{operation.operation_id} has unknown dependencies: {', '.join(missing)}"
            )
    remaining = set(by_id)
    resolved: set[str] = set()
    ordered: list[AlphaOperationRequest] = []
    while remaining:
        candidates = [
            by_id[operation_id]
            for operation_id in remaining
            if set(by_id[operation_id].depends_on) <= resolved
        ]
        if not candidates:
            raise ValueError("operation dependency graph contains a cycle")
        selected = min(candidates, key=lambda item: (item.priority, item.operation_id))
        ordered.append(selected)
        resolved.add(selected.operation_id)
        remaining.remove(selected.operation_id)
    return tuple(ordered)


def _assessment(operation: AlphaOperationRequest) -> ConsequenceAssessment:
    intent_hash = canonical_sha256(operation)
    return assess_autonomy(
        ActionIntent(
            intent_id="ACT-" + intent_hash[:24].upper(),
            effect_class=operation.effect_class,
            public_read_only=operation.public_read_only,
            internal_sandbox_only=operation.internal_sandbox_only,
            accesses_private_data=operation.accesses_private_data,
            credentials_required=operation.credentials_required,
            persistent_internal_mutation=operation.persistent_internal_mutation,
            external_mutation=operation.external_mutation,
            communication=operation.communication,
            financial_spend_cad=operation.financial_spend_cad,
            authorized_spend_cad=Decimal("0.00"),
            legal_commitment=operation.legal_commitment,
            security_sensitive=operation.security_sensitive,
            production_change=operation.production_change,
            physical_effect=operation.physical_effect,
            destructive=operation.destructive,
            irreversible=operation.irreversible,
            outcome_indeterminate=operation.outcome_indeterminate,
            existing_explicit_authority=False,
            permit_id=None,
        )
    )


def _authorization(
    assessment: ConsequenceAssessment, policy: AlphaPlanPolicy
) -> AuthorizationRequirements:
    if assessment.authority_requirement == "POLICY":
        return AuthorizationRequirements(
            authority_requirement="POLICY",
            consent_required=False,
            one_use_permit_required=False,
        )
    if assessment.authority_requirement == "RECONCILIATION":
        return AuthorizationRequirements(
            authority_requirement="RECONCILIATION",
            consent_required=False,
            one_use_permit_required=False,
            required_bindings=("READ_ONLY_RECONCILIATION_RECEIPT",),
        )
    return AuthorizationRequirements(
        authority_requirement="EXPLICIT",
        consent_required=True,
        one_use_permit_required=True,
        required_bindings=policy.required_external_bindings,
    )


def _retry(assessment: ConsequenceAssessment, policy: AlphaPlanPolicy) -> RetryPolicy:
    if not assessment.automatic_retry_allowed:
        return RetryPolicy(
            strategy="none",
            max_retries=0,
            base_delay_ms=0,
            reconciliation_before_retry=assessment.authority_requirement == "RECONCILIATION",
        )
    return RetryPolicy(
        strategy="exponential",
        max_retries=policy.maximum_automatic_retries,
        base_delay_ms=250,
        reconciliation_before_retry=False,
    )


def _error_handling(operation: AlphaOperationRequest) -> ErrorHandling:
    if operation.outcome_indeterminate:
        return ErrorHandling(on_error="reconcile")
    if operation.effect_class in {"WRITE_REVERSIBLE", "WRITE_COMPENSATABLE"}:
        return ErrorHandling(
            on_error="compensate", compensate_steps=operation.rollback_steps
        )
    return ErrorHandling(
        on_error="abort", compensate_steps=("discard local candidate",)
    )


def _build_atomic_node(
    request: AlphaPlanRequest,
    operation: AlphaOperationRequest,
    assessment: ConsequenceAssessment,
    policy: AlphaPlanPolicy,
    node_by_operation: dict[str, str],
) -> AlphaNode:
    node_seed = {
        "request_id": request.request_id,
        "domain_profile": request.domain_profile,
        "operation": operation.model_dump(mode="json"),
        "assessment": assessment.model_dump(mode="json"),
        "policy_id": policy.policy_id,
    }
    digest = canonical_sha256(node_seed)
    node_id = "ALPHA-NODE-" + digest[:24].upper()
    node_by_operation[operation.operation_id] = node_id
    preconditions = tuple(
        f"node:{node_by_operation[dependency]}:postconditions_satisfied"
        for dependency in operation.depends_on
    ) or ("request_contract_valid",)
    postconditions = tuple(
        f"output:{name}:matches:{expected_type}"
        for name, expected_type in sorted(operation.expected_outputs.items())
    ) or ("operation_terminal_receipt_emitted",)
    blocked = not assessment.execution_may_continue_without_new_authority
    return AlphaNode(
        node_id=node_id,
        name=operation.function_name,
        type="atomic",
        priority=operation.priority,
        preconditions=preconditions,
        postconditions=postconditions,
        params=operation.parameters,
        expected_outputs=operation.expected_outputs,
        idempotency_token=canonical_sha256(
            {"node_seed": node_seed, "purpose": "idempotency"}
        ),
        authorization_requirements=_authorization(assessment, policy),
        retry_policy=_retry(assessment, policy),
        error_handling=_error_handling(operation),
        observability=ObservabilityHooks(
            log_id="ALOG-" + canonical_sha256({"node": node_id, "kind": "log"})[:24].upper(),
            metrics=("attempt_count", "latency_ms", "terminal_status"),
            audit_fields=(
                "request_id",
                "node_id",
                "idempotency_token",
                "effect_class",
                "disposition",
            ),
        ),
        estimated_cost=EstimatedCost(
            time_ms=operation.estimated_time_ms,
            monetary_cad=operation.financial_spend_cad,
        ),
        disposition="BLOCKED_PERMISSION" if blocked else "READY_FOR_EXECUTOR",
    )


def compose_alpha_plan(request: AlphaPlanRequest) -> dict[str, object]:
    """Compose and simulate a deterministic Alpha Plan without executing any node."""

    policy = load_alpha_plan_policy()
    operations = request.operations or _default_operations(request)
    if len(operations) > policy.maximum_operations:
        raise ValueError("operation count exceeds policy maximum")
    parameter_bytes = len(
        json.dumps(
            [item.parameters for item in operations],
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    )
    if parameter_bytes > policy.maximum_parameter_bytes:
        raise ValueError("serialized operation parameters exceed policy maximum")

    ordered = _topological_order(operations)
    assessments = {item.operation_id: _assessment(item) for item in ordered}
    node_by_operation: dict[str, str] = {}
    atomic_nodes = tuple(
        _build_atomic_node(
            request, operation, assessments[operation.operation_id], policy, node_by_operation
        )
        for operation in ordered
    )
    blocked_nodes = [node for node in atomic_nodes if node.disposition == "BLOCKED_PERMISSION"]

    composite_digest = canonical_sha256(
        {
            "request_id": request.request_id,
            "children": [node.node_id for node in atomic_nodes],
            "policy_id": policy.policy_id,
        }
    )
    composite = AlphaNode(
        node_id="ALPHA-NODE-" + composite_digest[:24].upper(),
        name="aigc.alpha_plan.fulfill_request",
        type="composite",
        priority=min(item.priority for item in ordered),
        children=tuple(node.node_id for node in atomic_nodes),
        preconditions=("all_child_preconditions_valid",),
        postconditions=("all_children_terminal", "alpha_plan_receipt_emitted"),
        idempotency_token=canonical_sha256(
            {"composite": composite_digest, "purpose": "idempotency"}
        ),
        authorization_requirements=AuthorizationRequirements(
            authority_requirement="EXPLICIT" if blocked_nodes else "POLICY",
            consent_required=bool(blocked_nodes),
            one_use_permit_required=bool(blocked_nodes),
            required_bindings=(
                policy.required_external_bindings if blocked_nodes else ()
            ),
        ),
        retry_policy=RetryPolicy(
            strategy="none",
            max_retries=0,
            base_delay_ms=0,
            reconciliation_before_retry=False,
        ),
        error_handling=ErrorHandling(
            on_error="abort", compensate_steps=("preserve child receipts",)
        ),
        observability=ObservabilityHooks(
            log_id="ALOG-" + canonical_sha256({"composite": composite_digest})[:24].upper(),
            metrics=("plan_latency_ms", "ready_node_count", "blocked_node_count"),
            audit_fields=("request_id", "plan_id", "terminal_status"),
        ),
        estimated_cost=EstimatedCost(
            time_ms=sum(item.estimated_time_ms for item in ordered),
            monetary_cad=sum(
                (item.financial_spend_cad for item in ordered), Decimal("0.00")
            ),
        ),
        disposition="BLOCKED_PERMISSION" if blocked_nodes else "READY_FOR_EXECUTOR",
    )

    plan_seed = {
        "request": request.model_dump(mode="json"),
        "policy": policy.model_dump(mode="json"),
        "atomic_node_ids": [node.node_id for node in atomic_nodes],
        "composite_node_id": composite.node_id,
    }
    plan_id = "ALPHA-PLAN-" + canonical_sha256(plan_seed)[:24].upper()
    first_blocker = (
        f"{blocked_nodes[0].node_id}:EXPLICIT_AUTHORITY_REQUIRED"
        if blocked_nodes
        else None
    )
    plan_payload = {
        "alpha_plan_version": "aigc.alpha-plan.v1",
        "id": plan_id,
        "request_id": request.request_id,
        "domain_profile": request.domain_profile,
        "priority": min(item.priority for item in ordered),
        "alpha_levels": (
            AlphaLevel(level=0, nodes=atomic_nodes),
            AlphaLevel(level=1, nodes=(composite,)),
        ),
        "deterministic_seed": 42,
        "created_at": request.created_at,
        "human_summary": (
            f"Alpha Plan {plan_id} orders {len(atomic_nodes)} atomic function call(s); "
            + (
                f"{len(blocked_nodes)} consequential call(s) stop at explicit authority."
                if blocked_nodes
                else "all calls are locally plan-ready under the policy path."
            )
        ),
        "execution_sequence": tuple(
            {
                "sequence": index,
                "node_id": node.node_id,
                "function": operation.function_name,
                "parameters": operation.parameters,
                "disposition": node.disposition,
            }
            for index, (operation, node) in enumerate(zip(ordered, atomic_nodes), start=1)
        ),
        "verification": AlphaVerification(
            safety_checks=(
                "closed_request_schema",
                "secret_pattern_rejection",
                "bounded_operation_count",
                "zero_egress_simulation",
            ),
            authorization_checks=(
                "caller_authority_rejected",
                "consequence_classified",
                "one_use_permit_required_for_material_effects",
            ),
            graph_checks=(
                "unique_operation_ids",
                "known_dependencies",
                "acyclic_topology",
                "contiguous_alpha_levels",
            ),
            simulation_result="BLOCKED" if blocked_nodes else "OK",
            first_blocker=first_blocker,
        ),
        "meta_config": {
            "mode": "STABLE_FALLBACK",
            "shadow_suggestion_only": True,
            "policy": policy.stable_meta_config,
        },
        "terminal_status": "BLOCKED" if blocked_nodes else "PASS",
    }
    plan = AlphaPlan(
        **plan_payload,
        receipt_sha256=canonical_sha256(_json_projection(plan_payload)),
    )
    return plan.model_dump(mode="json")
