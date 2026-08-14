from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.autodesign.models import (
    AutodesignCampaignReceipt,
    AutodesignReceipt,
    AutodesignRequest,
    CHCMBlueprint,
    CapabilityRoadmapItem,
)
from src.coordination import CoordinationEngineeringRequest, engineer_coordination_plan
from src.core.epistemic.canonicalization import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT_PATH = ROOT / "config" / "aigc_regenexcalibur_chcm.v1.json"
SCHEMA_VERSION = "aigc.regenexcalibur-autodesign-receipt.v1"
ENDPOINT = "POST /v1/autodesign/iterate"


def load_chcm_blueprint(path: Path = BLUEPRINT_PATH) -> CHCMBlueprint:
    return CHCMBlueprint.model_validate_json(path.read_text(encoding="utf-8"))


def _proposal_disposition(capability: CapabilityRoadmapItem) -> str:
    if capability.effect_class in {"PURE", "READ_LOCAL"}:
        return "PROPOSED_FOR_REVIEW"
    if capability.effect_class == "READ_EXTERNAL":
        return "BLOCKED_EXTERNAL_EVIDENCE"
    return "BLOCKED_PERMISSION"


def _compile_coordination_request(
    request: AutodesignRequest,
    blueprint: CHCMBlueprint,
    blueprint_sha256: str,
) -> CoordinationEngineeringRequest:
    functions = tuple(
        {
            "tool_id": item.tool_id,
            "function_name": item.function_name,
            "purpose": item.purpose,
            "parameters": {
                "autodesign_request_id": request.request_id,
                "target_component": request.target_component,
            },
            "expected_outputs": item.expected_outputs,
            "effect_class": item.effect_class,
            "maximum_calls_per_iteration": 1,
            "estimated_time_ms": 25,
        }
        for item in blueprint.function_catalog
    )
    cluster_to_agent = {
        item.cluster_id: item.agent_id for item in blueprint.agent_clusters
    }
    agents = tuple(
        {
            "agent_id": item.agent_id,
            "role": item.role,
            "mandate": item.mandate,
            "capabilities": item.capabilities,
            "assigned_tool_ids": item.assigned_tool_ids,
            "depends_on_agent_ids": tuple(
                cluster_to_agent[cluster_id]
                for cluster_id in item.depends_on_cluster_ids
            ),
            "output_contract": item.output_contract,
            "verification_function": item.verification_function,
        }
        for item in blueprint.agent_clusters
    )
    input_digest = canonical_sha256(request.model_dump(mode="json"))
    return CoordinationEngineeringRequest.model_validate(
        {
            "request_id": "COORD-REQ-" + input_digest[:24].upper(),
            "objective": request.objective,
            "state": {
                "state_id": "COORD-STATE-" + input_digest[:24].upper(),
                "revision": request.state.revision,
                "artifact_refs": request.state.artifact_refs,
                "values": {
                    "autodesign_state_id": request.state.state_id,
                    "blueprint_sha256": blueprint_sha256,
                    "current_capabilities": request.state.current_capabilities,
                    "capability_evidence": request.state.capability_evidence,
                    "industry_scope": request.industry_scope,
                },
            },
            "iteration": {
                "current_iteration": request.iteration.current_iteration,
                "maximum_iterations": request.iteration.maximum_iterations,
                "minimum_progress_delta": blueprint.autodesign_policy.minimum_progress_delta,
                "no_progress_limit": blueprint.autodesign_policy.no_progress_limit,
            },
            "tools": functions,
            "agents": agents,
            "coordination": {
                "strategy": "HIERARCHICAL_DAG",
                "maximum_parallel_agents": blueprint.autodesign_policy.maximum_parallel_agents,
                "fail_fast": True,
                "require_independent_verification": True,
            },
            "acceptance_criteria": (
                "CHCM hierarchy and dependency graphs validate",
                "autodesign proposals are deterministic and bounded",
                "all material effects stop at authority or evidence gates",
                "state transition remains proposed and unapplied",
                "Omega verification emits the first exact blocker",
            ),
            "execution_requested": request.execution_requested,
            "deterministic_seed": 42,
        }
    )


def _validate_request_against_blueprint(
    request: AutodesignRequest, blueprint: CHCMBlueprint
) -> None:
    known_domains = {item.domain for item in blueprint.hierarchy.archons}
    unknown_domains = sorted(set(request.industry_scope).difference(known_domains))
    if unknown_domains:
        raise ValueError("unknown industry domains: " + ", ".join(unknown_domains))
    known_capabilities = {
        item.capability_id for item in blueprint.capability_roadmap
    }
    unknown_capabilities = sorted(
        set(request.state.current_capabilities).difference(known_capabilities)
    )
    if unknown_capabilities:
        raise ValueError(
            "unknown current capabilities: " + ", ".join(unknown_capabilities)
        )
    roadmap = {
        item.capability_id: item for item in blueprint.capability_roadmap
    }
    current = set(request.state.current_capabilities)
    for capability_id in request.state.current_capabilities:
        missing_dependencies = sorted(
            set(roadmap[capability_id].depends_on).difference(current)
        )
        if missing_dependencies:
            raise ValueError(
                f"current capability {capability_id} lacks admitted dependencies: "
                + ", ".join(missing_dependencies)
            )
    if (
        request.iteration.maximum_iterations
        > blueprint.autodesign_policy.maximum_iterations_per_run
    ):
        raise ValueError("iteration request exceeds the CHCM policy ceiling")
    if (
        request.iteration.proposal_limit
        > blueprint.autodesign_policy.maximum_proposals_per_iteration
    ):
        raise ValueError("proposal_limit exceeds the CHCM policy ceiling")


def run_autodesign_iteration(request: AutodesignRequest) -> dict[str, Any]:
    """Design the next bounded RegenExcalibur change set without applying it."""

    blueprint = load_chcm_blueprint()
    _validate_request_against_blueprint(request, blueprint)
    request_payload = request.model_dump(mode="json")
    input_sha256 = canonical_sha256(request_payload)
    blueprint_payload = blueprint.model_dump(mode="json")
    blueprint_sha256 = canonical_sha256(blueprint_payload)
    current = set(request.state.current_capabilities)
    roadmap = {item.capability_id: item for item in blueprint.capability_roadmap}
    missing = set(roadmap).difference(current)
    eligible = [
        item
        for item in blueprint.capability_roadmap
        if item.capability_id in missing and set(item.depends_on) <= current
    ]
    selected = tuple(
        sorted(eligible, key=lambda item: (item.priority, item.capability_id))[
            : request.iteration.proposal_limit
        ]
    )

    proposals: list[dict[str, Any]] = []
    safe_shadow_capabilities: list[str] = []
    blocked_proposals: list[dict[str, Any]] = []
    for capability in selected:
        disposition = _proposal_disposition(capability)
        proposal_seed = {
            "request_id": request.request_id,
            "iteration": request.iteration.current_iteration,
            "capability": capability.model_dump(mode="json"),
            "blueprint_sha256": blueprint_sha256,
        }
        proposal = {
            "proposal_id": "AUTODESIGN-PROP-"
            + canonical_sha256(proposal_seed)[:24].upper(),
            "capability_id": capability.capability_id,
            "name": capability.name,
            "priority": capability.priority,
            "depends_on": list(capability.depends_on),
            "effect_class": capability.effect_class,
            "responsible_cluster_id": capability.responsible_cluster_id,
            "change_targets": list(capability.change_targets),
            "acceptance_criteria": list(capability.acceptance_criteria),
            "disposition": disposition,
            "implementation_applied": False,
            "authority_granted": False,
        }
        proposals.append(proposal)
        if disposition == "PROPOSED_FOR_REVIEW":
            safe_shadow_capabilities.append(capability.capability_id)
        else:
            blocked_proposals.append(proposal)

    coordination_request = _compile_coordination_request(
        request, blueprint, blueprint_sha256
    )
    coordination_receipt = engineer_coordination_plan(coordination_request)
    iteration_exhausted = (
        request.iteration.current_iteration + 1
        >= request.iteration.maximum_iterations
    )
    blockers: list[str] = []
    if request.execution_requested:
        blockers.append("ENDPOINT_PLAN_ONLY")
    if blocked_proposals:
        blockers.append(
            "CAPABILITY_GATE_REQUIRED:" + blocked_proposals[0]["capability_id"]
        )
    if not selected and missing:
        blockers.append("CAPABILITY_DEPENDENCY_GAP")
    if iteration_exhausted and missing:
        blockers.append("ITERATION_BUDGET_EXHAUSTED_AFTER_CURRENT_PASS")
    terminal_status = "BLOCKED" if blockers else "PASS"
    next_iteration = None
    if (
        missing
        and not iteration_exhausted
        and not blocked_proposals
        and selected
    ):
        next_iteration = request.iteration.current_iteration + 1
    shadow_capabilities = tuple(
        sorted(current.union(safe_shadow_capabilities))
    )

    repository_by_domain = {
        "ENERGY": "REPO-ENERGY",
        "ROBOTICS": "REPO-ROBOTICS",
        "CLOUD": "REPO-CLOUD",
        "BIOTECH": "REPO-BIOTECH",
        "MATERIALS": "REPO-MATERIALS",
        "DEFENSE": "REPO-DEFENSIVE-SYSTEMS",
        "LOGISTICS": "REPO-LOGISTICS",
        "FINANCE": "REPO-FINANCE",
        "AI_SYSTEMS": "REPO-AI-SYSTEMS",
    }
    universalization_matrix = tuple(
        {
            "domain": division.domain,
            "archon": division.title,
            "agent_cluster_id": division.agent_cluster_id,
            "logical_repository_id": repository_by_domain.get(division.domain),
            "current_state": "BLUEPRINTED_NOT_DEPLOYED",
            "target_state": "DOMAIN_PILOT_VERIFIED",
            "required_capability": "CAP-DOMAIN-REPOSITORY-ADAPTERS",
            "production_claim": False,
        }
        for division in blueprint.hierarchy.archons
        if division.domain in request.industry_scope
    )

    total_capabilities = len(roadmap)
    receipt_seed: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "endpoint": ENDPOINT,
        "receipt_id": "AUTODESIGN-RCPT-" + input_sha256[:24].upper(),
        "request_id": request.request_id,
        "input_sha256": input_sha256,
        "blueprint_sha256": blueprint_sha256,
        "hierarchy_projection": {
            "blueprint_id": blueprint.blueprint_id,
            "pantheon_roles": len(blueprint.hierarchy.pantheon_board),
            "sovereign_orchestrators": 1,
            "archon_domains": len(blueprint.hierarchy.archons),
            "c_suite_roles": len(blueprint.hierarchy.c_suite),
            "agent_clusters": len(blueprint.agent_clusters),
            "runtime_kernel_nodes": len(blueprint.runtime_kernel),
            "function_catalog_entries": len(blueprint.function_catalog),
            "logical_repositories": len(blueprint.repository_federation),
            "experience_projections": len(blueprint.experience_projections),
            "deployment_components": len(blueprint.deployment_blueprint),
            "connector_designs": len(blueprint.connector_fabric),
            "kpi_definitions": len(blueprint.kpis),
            "procurement_stages": len(blueprint.procurement_pipeline),
        },
        "universalization_matrix": universalization_matrix,
        "gap_analysis": {
            "declared_current_capabilities": sorted(current),
            "capability_evidence": request.state.capability_evidence,
            "evidence_binding_status": "REFERENCE_BOUND_NOT_INDEPENDENTLY_RESOLVED",
            "missing_capabilities": sorted(missing),
            "eligible_capabilities": [item.capability_id for item in selected],
            "declared_coverage_ratio": len(current) / total_capabilities,
            "shadow_coverage_ratio_after_proposals": len(shadow_capabilities)
            / total_capabilities,
            "remaining_after_shadow": sorted(
                set(roadmap).difference(shadow_capabilities)
            ),
        },
        "proposals": tuple(proposals),
        "coordination_receipt": coordination_receipt,
        "evolution_continuation": {
            "infinite_semantics": blueprint.autodesign_policy.infinite_semantics,
            "current_iteration": request.iteration.current_iteration,
            "next_iteration": next_iteration,
            "maximum_iterations": request.iteration.maximum_iterations,
            "resume_token": canonical_sha256(
                {
                    "request_id": request.request_id,
                    "current_iteration": request.iteration.current_iteration,
                    "shadow_capabilities": shadow_capabilities,
                    "blueprint_sha256": blueprint_sha256,
                }
            ),
            "shadow_capabilities": shadow_capabilities,
            "requires_human_review": bool(proposals),
            "convergence_status": (
                "CONVERGED" if not missing else "OPEN_GAPS_REMAIN"
            ),
            "first_blocker": blockers[0] if blockers else None,
            "self_modification_allowed": False,
            "self_modification_performed": False,
            "state_transition_applied": False,
        },
        "terminal_status": terminal_status,
        "production_ready": False,
        "zero_egress": True,
        "self_modification_performed": False,
        "state_transition_applied": False,
        "provider_calls_performed": 0,
        "tool_dispatches_performed": 0,
        "processes_spawned": 0,
        "memory_writes_performed": 0,
        "external_actions_performed": 0,
        "authority_granted": False,
    }
    receipt_seed["receipt_sha256"] = canonical_sha256(receipt_seed)
    return AutodesignReceipt.model_validate(receipt_seed).model_dump(mode="json")


def run_shadow_autodesign_campaign(
    request: AutodesignRequest,
) -> dict[str, Any]:
    """Explore dependent design proposals across bounded shadow iterations only."""

    blueprint = load_chcm_blueprint()
    _validate_request_against_blueprint(request, blueprint)
    initial_payload = request.model_dump(mode="json")
    initial_sha256 = canonical_sha256(initial_payload)
    current_request = request
    shadow_capabilities = set(request.state.current_capabilities)
    iteration_receipts: list[dict[str, Any]] = []
    first_blocker: str | None = None

    while True:
        receipt = run_autodesign_iteration(current_request)
        iteration_receipts.append(receipt)
        safe = {
            item["capability_id"]
            for item in receipt["proposals"]
            if item["disposition"] == "PROPOSED_FOR_REVIEW"
        }
        shadow_capabilities.update(safe)
        first_blocker = receipt["evolution_continuation"]["first_blocker"]
        next_iteration = receipt["evolution_continuation"]["next_iteration"]
        if first_blocker or next_iteration is None or not safe:
            break
        next_seed = canonical_sha256(
            {
                "initial_request_sha256": initial_sha256,
                "next_iteration": next_iteration,
                "shadow_capabilities": sorted(shadow_capabilities),
            }
        )
        current_request = current_request.model_copy(
            update={
                "request_id": "AUTODESIGN-REQ-SHADOW_"
                + next_seed[:24].upper(),
                "state": current_request.state.model_copy(
                    update={
                        "revision": current_request.state.revision + 1,
                        "current_capabilities": tuple(sorted(shadow_capabilities)),
                        "capability_evidence": {
                            **current_request.state.capability_evidence,
                            **{
                                capability_id: (
                                    "shadow://autodesign/proposal/"
                                    + capability_id,
                                )
                                for capability_id in safe
                            },
                        },
                    }
                ),
                "iteration": current_request.iteration.model_copy(
                    update={"current_iteration": next_iteration}
                ),
            }
        )

    all_capabilities = {
        item.capability_id for item in blueprint.capability_roadmap
    }
    remaining = tuple(sorted(all_capabilities.difference(shadow_capabilities)))
    terminal_status = "PASS" if not remaining else "BLOCKED"
    campaign_seed: dict[str, Any] = {
        "schema_version": "aigc.regenexcalibur-autodesign-shadow-campaign.v1",
        "campaign_id": "AUTODESIGN-CAMPAIGN-" + initial_sha256[:24].upper(),
        "initial_request_sha256": initial_sha256,
        "iteration_receipts": tuple(iteration_receipts),
        "initial_capabilities": request.state.current_capabilities,
        "shadow_capabilities": tuple(sorted(shadow_capabilities)),
        "newly_proposed_capabilities": tuple(
            sorted(shadow_capabilities.difference(request.state.current_capabilities))
        ),
        "remaining_capabilities": remaining,
        "first_blocker": first_blocker,
        "terminal_status": terminal_status,
        "production_ready": False,
        "zero_egress": True,
        "shadow_only": True,
        "self_modification_performed": False,
        "state_transition_applied": False,
        "provider_calls_performed": 0,
        "tool_dispatches_performed": 0,
        "processes_spawned": 0,
        "memory_writes_performed": 0,
        "external_actions_performed": 0,
        "authority_granted": False,
    }
    campaign_seed["receipt_sha256"] = canonical_sha256(campaign_seed)
    return AutodesignCampaignReceipt.model_validate(campaign_seed).model_dump(
        mode="json"
    )
