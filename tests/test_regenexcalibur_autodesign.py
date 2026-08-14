from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.autodesign import (
    AutodesignRequest,
    run_autodesign_iteration,
    run_shadow_autodesign_campaign,
)
from src.autodesign.engine import load_chcm_blueprint
from src.autodesign.models import CHCMBlueprint
from src.core.epistemic.canonicalization import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]


def request_payload() -> dict[str, object]:
    return json.loads(
        (ROOT / "config" / "aigc_regenexcalibur_autodesign_request.v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_chcm_blueprint_maps_the_complete_hierarchy_and_real_world_planes():
    blueprint = load_chcm_blueprint()

    assert len(blueprint.hierarchy.pantheon_board) == 4
    assert blueprint.hierarchy.sovereign_orchestrator.corporate_role == "CEO"
    assert {item.domain for item in blueprint.hierarchy.archons} == {
        "ENERGY",
        "ROBOTICS",
        "CLOUD",
        "BIOTECH",
        "MATERIALS",
        "DEFENSE",
        "LOGISTICS",
        "FINANCE",
        "AI_SYSTEMS",
    }
    assert len(blueprint.hierarchy.c_suite) == 12
    assert len(blueprint.agent_clusters) == 11
    assert len(blueprint.runtime_kernel) == 8
    assert {item.mode for item in blueprint.experience_projections} == {
        "CORPORATION",
        "OPERATING_SYSTEM",
        "CINEMATIC_UNIVERSE",
        "RPG_WORLD",
    }
    assert all(item.egress_enabled is False for item in blueprint.connector_fabric)
    assert all(
        item.status == "DESIGN_ONLY_NOT_PROVISIONED"
        for item in blueprint.deployment_blueprint
    )
    deploy = next(
        item for item in blueprint.interface_registry if item.interface_id == "API-DEPLOY"
    )
    assert deploy.status == "BLOCKED_NOT_EXPOSED"


def test_one_autodesign_iteration_is_deterministic_self_referential_and_zero_egress():
    request = AutodesignRequest.model_validate(request_payload())
    first = run_autodesign_iteration(request)
    second = run_autodesign_iteration(request)

    assert first == second
    assert first["terminal_status"] == "PASS"
    assert [item["capability_id"] for item in first["proposals"]] == [
        "CAP-RUNTIME-KPI-EVALUATOR",
        "CAP-PROCUREMENT-SANDBOX-BRIDGE",
        "CAP-DOMAIN-REPOSITORY-ADAPTERS",
    ]
    assert all(item["implementation_applied"] is False for item in first["proposals"])
    assert first["hierarchy_projection"]["archon_domains"] == 9
    assert first["hierarchy_projection"]["experience_projections"] == 4
    assert len(first["universalization_matrix"]) == 9
    assert all(
        item["logical_repository_id"] is not None
        for item in first["universalization_matrix"]
    )
    assert first["coordination_receipt"]["terminal_status"] == "PASS"
    assert first["gap_analysis"]["evidence_binding_status"] == (
        "REFERENCE_BOUND_NOT_INDEPENDENTLY_RESOLVED"
    )
    coordination = first["coordination_receipt"]["multi_agent_coordination"]
    assert "AGT-OMEGA" in {item["agent_id"] for item in coordination["agents"]}
    assert coordination["waves"][-1]["agent_ids"] == ["AGT-OMEGA"]
    assert first["evolution_continuation"]["self_modification_performed"] is False
    assert first["state_transition_applied"] is False
    assert first["provider_calls_performed"] == 0
    assert first["tool_dispatches_performed"] == 0
    assert first["processes_spawned"] == 0
    assert first["memory_writes_performed"] == 0
    assert first["external_actions_performed"] == 0
    assert first["authority_granted"] is False
    receipt_hash = first.pop("receipt_sha256")
    assert receipt_hash == canonical_sha256(first)


def test_shadow_campaign_terminates_at_cloud_authority_instead_of_spinning_forever():
    request = AutodesignRequest.model_validate(request_payload())
    campaign = run_shadow_autodesign_campaign(request)

    assert campaign["terminal_status"] == "BLOCKED"
    assert len(campaign["iteration_receipts"]) == 3
    assert campaign["first_blocker"] == (
        "CAPABILITY_GATE_REQUIRED:CAP-CLOUD-SANDBOX-DEPLOYMENT"
    )
    assert campaign["newly_proposed_capabilities"] == [
        "CAP-CONNECTOR-CERTIFICATION-HARNESS",
        "CAP-DOMAIN-REPOSITORY-ADAPTERS",
        "CAP-PROCUREMENT-SANDBOX-BRIDGE",
        "CAP-RUNTIME-KPI-EVALUATOR",
    ]
    assert campaign["remaining_capabilities"] == [
        "CAP-CLOUD-SANDBOX-DEPLOYMENT",
        "CAP-INDUSTRY-PILOT-EVIDENCE",
        "CAP-PRODUCTION-ACTIVATION",
    ]
    assert campaign["shadow_only"] is True
    assert campaign["self_modification_performed"] is False
    assert campaign["state_transition_applied"] is False
    assert campaign["external_actions_performed"] == 0


def test_execution_request_and_unknown_domains_fail_closed():
    payload = request_payload()
    payload["execution_requested"] = True
    receipt = run_autodesign_iteration(AutodesignRequest.model_validate(payload))
    assert receipt["terminal_status"] == "BLOCKED"
    assert receipt["evolution_continuation"]["first_blocker"] == "ENDPOINT_PLAN_ONLY"
    assert receipt["external_actions_performed"] == 0

    payload = request_payload()
    payload["industry_scope"] = ["UNDECLARED_REALM"]
    with pytest.raises(ValueError, match="unknown industry domains"):
        run_autodesign_iteration(AutodesignRequest.model_validate(payload))


def test_unknown_current_capability_and_policy_overreach_fail_closed():
    payload = request_payload()
    payload["state"]["current_capabilities"].append("CAP-FICTIONAL")
    payload["state"]["capability_evidence"]["CAP-FICTIONAL"] = [
        "artifact://fictional"
    ]
    with pytest.raises(ValueError, match="unknown current capabilities"):
        run_autodesign_iteration(AutodesignRequest.model_validate(payload))

    payload = request_payload()
    payload["state"]["current_capabilities"] = [
        "CAP-DETERMINISTIC-COORDINATION-BRIDGE"
    ]
    payload["state"]["capability_evidence"] = {
        "CAP-DETERMINISTIC-COORDINATION-BRIDGE": ["artifact://bridge"]
    }
    with pytest.raises(ValueError, match="lacks admitted dependencies"):
        run_autodesign_iteration(AutodesignRequest.model_validate(payload))

    payload = request_payload()
    payload["iteration"]["proposal_limit"] = 4
    blueprint_payload = json.loads(
        (ROOT / "config" / "aigc_regenexcalibur_chcm.v1.json").read_text(
            encoding="utf-8"
        )
    )
    blueprint_payload["autodesign_policy"]["maximum_proposals_per_iteration"] = 3
    request = AutodesignRequest.model_validate(payload)
    blueprint = CHCMBlueprint.model_validate(blueprint_payload)
    from src.autodesign.engine import _validate_request_against_blueprint

    with pytest.raises(ValueError, match="proposal_limit exceeds"):
        _validate_request_against_blueprint(request, blueprint)


def test_blueprint_rejects_unknown_edges_cycles_and_claimed_connector_egress():
    source = json.loads(
        (ROOT / "config" / "aigc_regenexcalibur_chcm.v1.json").read_text(
            encoding="utf-8"
        )
    )
    unknown = deepcopy(source)
    unknown["runtime_kernel"][0]["depends_on_node_ids"] = ["KERNEL-NOT-THERE"]
    with pytest.raises(ValidationError, match="unknown dependencies"):
        CHCMBlueprint.model_validate(unknown)

    cycle = deepcopy(source)
    cycle["runtime_kernel"][0]["depends_on_node_ids"] = ["KERNEL-OMEGA"]
    with pytest.raises(ValidationError, match="contains a cycle"):
        CHCMBlueprint.model_validate(cycle)

    egress = deepcopy(source)
    egress["connector_fabric"][0]["egress_enabled"] = True
    with pytest.raises(ValidationError):
        CHCMBlueprint.model_validate(egress)


def test_fully_covered_shadow_state_converges_without_requesting_another_iteration():
    blueprint = load_chcm_blueprint()
    payload = request_payload()
    payload["state"]["current_capabilities"] = [
        item.capability_id for item in blueprint.capability_roadmap
    ]
    payload["state"]["capability_evidence"] = {
        item.capability_id: ["artifact://evidence/" + item.capability_id]
        for item in blueprint.capability_roadmap
    }
    receipt = run_autodesign_iteration(AutodesignRequest.model_validate(payload))

    assert receipt["terminal_status"] == "PASS"
    assert receipt["proposals"] == []
    assert receipt["evolution_continuation"]["next_iteration"] is None
    assert receipt["evolution_continuation"]["convergence_status"] == "CONVERGED"


def test_current_capabilities_require_exact_nonempty_evidence_bindings():
    payload = request_payload()
    payload["state"]["capability_evidence"].pop("CAP-CHCM-TYPED-REGISTRY")
    with pytest.raises(ValidationError, match="must exactly match"):
        AutodesignRequest.model_validate(payload)

    payload = request_payload()
    payload["state"]["capability_evidence"]["CAP-CHCM-TYPED-REGISTRY"] = []
    with pytest.raises(ValidationError, match="cannot be empty"):
        AutodesignRequest.model_validate(payload)
