#!/usr/bin/env python3
"""Validate the governed RegenExcalibur/AIGC agent registry without executing agents."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


REQUIRED_TOP_LEVEL = {
    "schema_version", "project_id", "orchestration_platform", "status",
    "default_disposition", "authority_tiers", "shared_contract", "agents",
    "mandatory_human_gates", "acceptance_policy",
}
REQUIRED_AGENT = {
    "id", "name", "responsibility", "authority_tier", "dependencies",
    "authority_boundary", "enabled", "implementation_status",
}


class RegistryError(ValueError):
    pass


def validate_registry(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not REQUIRED_TOP_LEVEL.issubset(data):
        raise RegistryError("registry_top_level_fields_missing")
    if data["schema_version"] != "regenexcalibur-aigc-agent-registry/1.0":
        raise RegistryError("unsupported_registry_schema")
    if data["project_id"] != "REGENEXCALIBUR" or data["orchestration_platform"] != "AIGC":
        raise RegistryError("project_identity_mismatch")
    if data["default_disposition"] != "BLOCK":
        raise RegistryError("default_disposition_must_block")
    if not isinstance(data["agents"], list) or not data["agents"]:
        raise RegistryError("agent_list_missing")
    ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for agent in data["agents"]:
        if not isinstance(agent, dict) or not REQUIRED_AGENT.issubset(agent):
            raise RegistryError("agent_contract_fields_missing")
        if any(not isinstance(agent[k], str) or not agent[k].strip()
               for k in ("id", "name", "responsibility", "authority_tier", "authority_boundary")):
            raise RegistryError("agent_identity_or_contract_empty")
        if agent["authority_tier"] not in data["authority_tiers"]:
            raise RegistryError("unknown_authority_tier")
        if not isinstance(agent["dependencies"], list) or any(not isinstance(x, str) for x in agent["dependencies"]):
            raise RegistryError("dependencies_malformed")
        if agent["id"] in by_id:
            raise RegistryError("duplicate_agent_id")
        if agent["enabled"] is not False:
            raise RegistryError("new_registry_agents_must_default_disabled")
        if agent["implementation_status"] != "SPECIFIED_NOT_PRODUCTION_INTEGRATED":
            raise RegistryError("implementation_status_overclaims_readiness")
        ids.append(agent["id"])
        by_id[agent["id"]] = agent
    if len(by_id) != 21:
        raise RegistryError("unexpected_agent_count")
    for agent in data["agents"]:
        if agent["id"] in agent["dependencies"]:
            raise RegistryError("self_dependency")
        if any(dep not in by_id for dep in agent["dependencies"]):
            raise RegistryError("unknown_dependency")
    # Verify an acyclic dependency graph with a deterministic Kahn traversal.
    indegree = {agent_id: 0 for agent_id in by_id}
    dependents = {agent_id: [] for agent_id in by_id}
    for agent in data["agents"]:
        for dependency in agent["dependencies"]:
            indegree[agent["id"]] += 1
            dependents[dependency].append(agent["id"])
    ready = sorted(agent_id for agent_id, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        current = ready.pop(0)
        visited += 1
        for child in sorted(dependents[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if visited != len(by_id):
        raise RegistryError("dependency_cycle_detected")
    if sum(1 for a in data["agents"] if a["id"] == "RX-19" and a["name"] == "Canonical AIGC Release Assurance Agent" and a["authority_tier"] == "R4") != 1:
        raise RegistryError("canonical_release_authority_missing_or_ambiguous")
    for agent in data["agents"]:
        if agent["id"] != "RX-19" and "release" in agent["responsibility"].lower() and agent["authority_tier"] == "R4":
            raise RegistryError("multiple_release_authorities")
    policy = data["acceptance_policy"]
    required_true = (
        "independent_review_required", "human_acceptance_required",
        "bind_review_to_exact_artifact_digest", "bind_acceptance_to_exact_artifact_digest",
        "require_live_cryptographic_provenance", "require_independently_administered_audit_retention",
        "no_hash_only_provenance_fallback", "no_agent_self_approval",
    )
    if not isinstance(policy, dict) or any(policy.get(key) is not True for key in required_true):
        raise RegistryError("acceptance_policy_weak_or_incomplete")
    if not data["mandatory_human_gates"]:
        raise RegistryError("mandatory_human_gates_missing")
    return {
        "status": "VALID",
        "agent_count": len(by_id),
        "dependency_graph": "ACYCLIC",
        "all_agents_disabled_by_default": True,
        "default_disposition": "BLOCK",
        "release_authority": "RX-19",
        "production_authorization": "NOT_GRANTED",
    }


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config/regenexcalibur_aigc_agent_registry.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = validate_registry(data)
    except (OSError, json.JSONDecodeError, RegistryError) as exc:
        print("BLOCK: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
