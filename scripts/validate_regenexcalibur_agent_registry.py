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
    "mandatory_human_gates", "acceptance_policy", "operational_gate_contracts", "final_decision_contract", "handoff_coordination_contract", "research_intelligence_contract", "opportunity_discovery_contract", "release_operations_assurance_contract",
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
    if len(by_id) != 95:
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
    required_gate_agents = {"RX-21", "RX-22", "RX-23", "RX-24", "RX-25", "RX-26", "RX-27", "RX-28"}
    if not required_gate_agents.issubset(by_id):
        raise RegistryError("release_gate_agent_missing")
    if by_id["RX-21"]["authority_tier"] != "R0" or by_id["RX-22"]["authority_tier"] != "R0":
        raise RegistryError("independent_review_gate_must_be_read_only")
    if by_id["RX-24"]["authority_tier"] != "R4" or by_id["RX-25"]["authority_tier"] != "R4":
        raise RegistryError("human_acceptance_and_merge_gates_must_be_human_reserved")
    if by_id["RX-19"]["authority_tier"] != "R4":
        raise RegistryError("canonical_release_authority_must_be_human_reserved")
    if by_id["RX-28"]["authority_tier"] != "R0":
        raise RegistryError("release_block_coordinator_must_be_read_only")
    if by_id["RX-28"]["enabled"] is not False:
        raise RegistryError("release_block_coordinator_must_be_disabled_by_default")
    if "RX-19" not in by_id["RX-28"]["dependencies"]:
        raise RegistryError("release_block_coordinator_must_depend_on_canonical_assurance")
    if "BLOCK" not in by_id["RX-28"]["authority_boundary"]:
        raise RegistryError("release_block_coordinator_must_preserve_block")
    gate_contracts = data["operational_gate_contracts"]
    required_gate_ids = {"reviewer_assignment", "review_findings_and_remediation", "exact_head_ci", "human_acceptance", "protected_merge", "post_merge_trust_and_artifact_verification", "retained_artifact_and_independent_audit"}
    if not isinstance(gate_contracts, list) or {g.get("gate_id") for g in gate_contracts if isinstance(g, dict)} != required_gate_ids:
        raise RegistryError("operational_gate_contracts_missing_or_ambiguous")
    for gate in gate_contracts:
        if not all(gate.get(key) for key in ("agent_id", "required_inputs", "required_outputs", "pass_criteria", "failure_disposition", "invalidated_by", "side_effects")):
            raise RegistryError("operational_gate_contract_incomplete")
        if gate["agent_id"] not in by_id or gate["failure_disposition"] != "BLOCK":
            raise RegistryError("operational_gate_contract_weak_or_unbound")
        if by_id[gate["agent_id"]]["enabled"] is not False:
            raise RegistryError("operational_gate_agent_must_be_disabled")
    handoff = data.get("handoff_coordination_contract")
    if not isinstance(handoff, dict) or handoff.get("contract_version") != "1.0.0":
        raise RegistryError("handoff_coordination_contract_missing_or_unsupported")
    if handoff.get("default_disposition") != "BLOCK" or handoff.get("canonical_release_authority") != "RX-19":
        raise RegistryError("handoff_coordination_contract_must_fail_closed")
    expected_handoff = [
        ("RX-53", "administrator_protection_readback"),
        ("RX-54", "independent_reviewer_assignment"),
        ("RX-55", "finding_remediation_and_retest"),
        ("RX-50", "lineage_and_exact_head_ci"),
        ("RX-56", "authenticated_human_acceptance"),
        ("RX-49", "protected_merge_preconditions"),
        ("RX-51", "post_merge_provenance_and_retention"),
        ("RX-52", "evidence_packet_handoff"),
    ]
    sequence = handoff.get("sequence")
    if not isinstance(sequence, list) or [
        (step.get("agent_id"), step.get("gate")) for step in sequence if isinstance(step, dict)
    ] != expected_handoff or [step.get("sequence") for step in sequence if isinstance(step, dict)] != list(range(1, 9)):
        raise RegistryError("handoff_coordination_sequence_invalid")
    if any(not step.get("requires") or not step.get("pass_rule") for step in sequence):
        raise RegistryError("handoff_coordination_step_incomplete")
    if any(handoff.get(key) is not True for key in (
        "no_agent_self_approval", "no_agent_may_assign_human_identity",
        "no_agent_may_bypass_protection", "no_agent_may_merge_or_authorize_release"
    )):
        raise RegistryError("handoff_coordination_authority_boundary_weak")
    if not handoff.get("invalidation_rules") or any(by_id[agent_id]["enabled"] is not False for agent_id in ("RX-53", "RX-54", "RX-55", "RX-56", "RX-57")):
        raise RegistryError("handoff_coordination_agent_state_invalid")
    research = data.get("research_intelligence_contract")
    if not isinstance(research, dict) or research.get("contract_version") != "1.0.0":
        raise RegistryError("research_intelligence_contract_missing_or_unsupported")
    if research.get("status") != "SPECIFICATION_ONLY" or research.get("default_disposition") != "BLOCK":
        raise RegistryError("research_intelligence_contract_must_fail_closed")
    if any(research.get(key) is not True for key in (
        "no_unsupported_compliance_claims", "no_agent_self_approval", "no_production_side_effects"
    )):
        raise RegistryError("research_intelligence_authority_boundary_weak")
    required_research_rules = {
        "Prefer primary government, standards-body, official project and original research sources; use secondary commentary only for context.",
        "Record source title, publisher, canonical URL, publication/revision date, access date, jurisdiction, source type and exact claim supported.",
        "Separate binding law/regulation, government policy, standards, normative specifications, voluntary guidance, vendor documentation and opinion.",
        "Cross-check consequential claims against independent sources when feasible; record disagreement and missing evidence.",
        "Never claim compliance, security, safety, certification or production readiness from a mapping exercise alone.",
        "Research agents do not execute production changes, approve policy, assign reviewers, accept releases or override RX-19."
    }
    if not required_research_rules.issubset(set(research.get("research_quality_rules", []))):
        raise RegistryError("research_quality_rules_missing")
    if not research.get("evidence_fields") or not research.get("invalidation_rules"):
        raise RegistryError("research_evidence_contract_incomplete")
    for agent_id in ("RX-58", "RX-59", "RX-60", "RX-61", "RX-62", "RX-63", "RX-64", "RX-65", "RX-66", "RX-67", "RX-68"):
        if agent_id not in by_id or by_id[agent_id]["enabled"] is not False or by_id[agent_id]["authority_tier"] != "R0":
            raise RegistryError("research_agent_must_be_read_only_and_disabled")
    opportunity = data.get("opportunity_discovery_contract")
    if not isinstance(opportunity, dict) or opportunity.get("contract_version") != "1.0.0":
        raise RegistryError("opportunity_discovery_contract_missing_or_unsupported")
    if opportunity.get("status") != "SPECIFICATION_ONLY" or opportunity.get("default_disposition") != "BLOCK":
        raise RegistryError("opportunity_discovery_contract_must_fail_closed")
    if opportunity.get("unknown_source_policy") != "DENY_AUTOMATED_ACCESS":
        raise RegistryError("unknown_opportunity_sources_must_be_denied")
    if opportunity.get("application_policy") != "DRAFTS_AND_RECOMMENDATIONS_AUTOMATIC; SUBMISSION_REQUIRES_EXPLICIT_SCOPED_HUMAN_APPROVAL":
        raise RegistryError("application_submission_policy_weak")
    if any(opportunity.get(key) is not True for key in ("no_unapproved_external_actions", "no_fabricated_candidate_claims", "no_prohibited_scraping", "no_automatic_application_submission")):
        raise RegistryError("opportunity_authority_boundary_weak")
    required_opportunity_agents = ("RX-69", "RX-70", "RX-71", "RX-72", "RX-73", "RX-74", "RX-75", "RX-76", "RX-77", "RX-78", "RX-79", "RX-80", "RX-81", "RX-82", "RX-83")
    for agent_id in required_opportunity_agents:
        if agent_id not in by_id or by_id[agent_id]["enabled"] is not False:
            raise RegistryError("opportunity_agent_must_be_disabled")
    if by_id["RX-73"]["authority_tier"] != "R0":
        raise RegistryError("application_approval_gate_must_be_read_only")
    if not opportunity.get("source_policy_ref") or not opportunity.get("human_only_actions") or not opportunity.get("safety_rules"):
        raise RegistryError("opportunity_policy_contract_incomplete")
    final_contract = data["final_decision_contract"]
    if final_contract.get("agent_id") != "RX-28" or final_contract.get("canonical_decision_authority") != "RX-19":
        raise RegistryError("final_decision_authority_mismatch")
    if final_contract.get("failure_disposition") != "BLOCK" or not final_contract.get("required_gate_ids"):
        raise RegistryError("final_decision_contract_must_fail_closed")
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
    lifecycle = data.get("implementation_lifecycle")
    if not isinstance(lifecycle, dict):
        raise RegistryError("implementation_lifecycle_missing")
    expected_statuses = ["SPECIFIED", "IMPLEMENTED", "TESTED", "INDEPENDENTLY_VERIFIED", "PRODUCTION_AUTHORIZED"]
    if lifecycle.get("operational_statuses") != expected_statuses:
        raise RegistryError("implementation_lifecycle_statuses_invalid")
    if lifecycle.get("default_operational_status") != "SPECIFIED" or lifecycle.get("production_authorization_granted") is not False:
        raise RegistryError("implementation_lifecycle_must_default_to_specified_and_unauthorized")
    if lifecycle.get("non_equivalence_rule") is None or lifecycle.get("policy") is None:
        raise RegistryError("implementation_lifecycle_evidence_policy_missing")
    contract_list = data.get("new_agent_contracts")
    expected_new_agents = {"RX-29", "RX-30", "RX-31", "RX-40", "RX-41", "RX-42", "RX-43", "RX-44", "RX-45", "RX-46", "RX-47", "RX-48", "RX-49", "RX-50", "RX-51", "RX-52", "RX-53", "RX-54", "RX-55", "RX-56", "RX-57", "RX-58", "RX-59", "RX-60", "RX-61", "RX-62", "RX-63", "RX-64", "RX-65", "RX-66", "RX-67", "RX-68", "RX-69", "RX-70", "RX-71", "RX-72", "RX-73", "RX-74", "RX-75", "RX-76", "RX-77", "RX-78", "RX-79", "RX-80", "RX-81", "RX-82", "RX-83", "RX-84", "RX-85", "RX-86", "RX-87", "RX-88", "RX-89", "RX-90", "RX-91", "RX-92", "RX-93", "RX-94", "RX-95", "RX-96", "RX-97", "RX-98", "RX-99", "RX-100", "RX-101", "RX-102"}
    if not isinstance(contract_list, list) or {x.get("agent_id") for x in contract_list if isinstance(x, dict)} != expected_new_agents:
        raise RegistryError("new_agent_contracts_missing_or_ambiguous")
    for contract in contract_list:
        if (contract.get("contract_version") != "1.0.0"
            or not contract.get("input_schema_ref")
            or not contract.get("output_schema_ref")
            or not contract.get("tool_allowlist")
            or contract.get("required_evidence_binding") != lifecycle.get("evidence_binding_fields")
            or contract.get("required_test_classes") != lifecycle.get("minimum_test_classes")
            or contract.get("human_approved_activation_required") is not True
            or contract.get("rollback_plan_required") is not True
            or contract.get("self_approval_prohibited") is not True
            or contract.get("production_authorization") is not False
            or contract.get("failure_disposition") != "BLOCK"):
            raise RegistryError("new_agent_contract_incomplete_or_unsafe")
        agent = by_id.get(contract["agent_id"])
        if not agent or agent["enabled"] is not False or agent["implementation_status"] != "SPECIFIED_NOT_PRODUCTION_INTEGRATED":
            raise RegistryError("new_agent_status_overclaims_readiness")
    for agent_id in expected_new_agents:
        agent = by_id[agent_id]
        if agent["authority_tier"] not in {"R0", "R1", "R2"}:
            raise RegistryError("new_agent_authority_tier_too_high")
        if "cannot" not in agent["authority_boundary"].lower() or "self-approve" not in agent["authority_boundary"].lower():
            raise RegistryError("new_agent_authority_boundary_missing")
    ops = data.get("release_operations_assurance_contract")
    if not isinstance(ops, dict) or ops.get("contract_version") != "1.0.0":
        raise RegistryError("release_operations_contract_missing_or_unsupported")
    if ops.get("status") != "SPECIFICATION_ONLY" or ops.get("default_disposition") != "BLOCK" or ops.get("canonical_release_authority") != "RX-19":
        raise RegistryError("release_operations_contract_must_fail_closed")
    expected_ops_agents = {"RX-95", "RX-96", "RX-97", "RX-98", "RX-99", "RX-100", "RX-101", "RX-102"}
    if set(ops.get("agent_ids", [])) != expected_ops_agents:
        raise RegistryError("release_operations_agents_missing_or_ambiguous")
    if any(ops.get(key) is not True for key in ("no_agent_self_approval", "no_agent_may_assign_human_identity", "no_agent_may_manufacture_acceptance", "no_agent_may_bypass_protection", "no_agent_may_merge_or_authorize_release")):
        raise RegistryError("release_operations_authority_boundary_weak")
    if ops.get("production_authorization") is not False or len(ops.get("research_baseline", [])) < 5 or len(ops.get("required_controls", [])) < 8 or len(ops.get("required_evidence_fields", [])) < 15 or len(ops.get("invalidation_rules", [])) < 5:
        raise RegistryError("release_operations_evidence_contract_incomplete")
    for agent_id in expected_ops_agents:
        if agent_id not in by_id or by_id[agent_id]["enabled"] is not False or by_id[agent_id]["authority_tier"] != "R0":
            raise RegistryError("release_operations_agent_must_be_read_only_and_disabled")
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
