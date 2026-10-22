"""Bounded, fail-closed AIGC agent operations planner.

This module is a deterministic reference planner, not a production dispatcher.
It does not invoke tools, authenticate signatures, grant permissions, or change
agent activation state. Production execution remains disabled until trusted
identity/permit verification and isolated adapters are implemented and approved.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_ALLOWED_OPERATIONS = {
    "run_allowlisted_agent",
    "reroute_to_allowlisted_agent",
    "retry_after_side_effect_reconciliation",
    "select_approved_fallback",
    "degrade_to_read_only",
}
_NEVER_OVERRIDE = {
    "override_release_gate",
    "disable_repository_protection",
    "skip_required_ci",
    "self_enable_agent",
    "elevate_authority",
    "manufacture_acceptance",
    "forge_evidence",
    "merge",
    "deploy",
    "authorize_release",
}


def _block(reason: str, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "BLOCK",
        "reason": reason,
        "request_id": request.get("request_id") if isinstance(request, Mapping) else None,
        "execution_mode": "dry_run",
        "side_effects_performed": False,
        "production_authorization": False,
        "merge_authorization": False,
        "release_authorization": False,
    }


def plan_agent_operation(
    registry: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    kill_switch_engaged: bool = False,
    side_effect_reconciled: bool = False,
) -> dict[str, Any]:
    """Return a deterministic dry-run plan or a fail-closed block result."""
    if not isinstance(registry, Mapping) or not isinstance(request, Mapping):
        return _block("registry_and_request_must_be_objects")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        return _block("request_id_required", request)
    if kill_switch_engaged:
        return _block("global_kill_switch_engaged", request)

    mode = request.get("mode", "dry_run")
    if mode != "dry_run":
        return _block("production_execution_not_implemented", request)

    operation = request.get("operation")
    if operation in _NEVER_OVERRIDE:
        return _block("non_overridable_security_or_release_invariant", request)
    if operation not in _ALLOWED_OPERATIONS:
        return _block("operation_not_allowlisted", request)
    if operation == "retry_after_side_effect_reconciliation" and side_effect_reconciled is not True:
        return _block("side_effect_outcome_must_be_reconciled_before_retry", request)

    candidate_sha = request.get("source_commit_sha")
    if not isinstance(candidate_sha, str) or not _SHA.fullmatch(candidate_sha):
        return _block("source_commit_sha_invalid", request)
    policy_version = request.get("policy_version")
    if not isinstance(policy_version, str) or not policy_version.strip():
        return _block("policy_version_required", request)
    task_digest = request.get("task_contract_digest")
    if not isinstance(task_digest, str) or not _DIGEST.fullmatch(task_digest):
        return _block("task_contract_digest_invalid", request)

    agents = registry.get("agents")
    if not isinstance(agents, list):
        return _block("registry_agent_list_missing", request)
    by_id = {a.get("id"): a for a in agents if isinstance(a, Mapping) and isinstance(a.get("id"), str)}
    target = request.get("target_agent_id")
    if target not in by_id:
        return _block("target_agent_not_in_registry", request)
    if by_id[target].get("authority_tier") not in {"R0", "R1"}:
        return _block("target_authority_tier_not_permitted_for_reference_plan", request)

    order: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(agent_id: str) -> None:
        if agent_id not in by_id:
            raise ValueError("dependency_not_in_registry:" + agent_id)
        if agent_id in visiting:
            raise ValueError("dependency_cycle:" + agent_id)
        if agent_id in visited:
            return
        visiting.add(agent_id)
        dependencies = by_id[agent_id].get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ValueError("dependency_list_invalid:" + agent_id)
        for dependency in sorted(dependencies):
            visit(dependency)
        visiting.remove(agent_id)
        visited.add(agent_id)
        order.append(agent_id)

    try:
        visit(target)
    except ValueError as exc:
        return _block(str(exc), request)

    # The planner can prepare a simulation even when agents are disabled, but it
    # must never imply that a disabled agent was actually invoked.
    plan = {
        "request_id": request_id,
        "status": "DRY_RUN_PLAN",
        "operation": operation,
        "target_agent_id": target,
        "source_commit_sha": candidate_sha,
        "policy_version": policy_version,
        "task_contract_digest": task_digest if task_digest.startswith("sha256:") else "sha256:" + task_digest,
        "dependency_order": order,
        "dispatchable_in_production": False,
        "requires_authenticated_target_bound_permit_for_production": True,
        "requires_agent_activation_approval": True,
        "requires_isolated_adapter": True,
        "requires_audit_ledger": True,
        "side_effects_performed": False,
        "production_authorization": False,
        "merge_authorization": False,
        "release_authorization": False,
    }
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    plan["plan_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return plan
