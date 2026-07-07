from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from src.core.algorithmic_capabilities import (
    FORBIDDEN_USES,
    assert_algorithmic_manifest_safe,
    build_algorithmic_capability_manifest,
    capabilities_for_role,
)
from src.core.contract_validator import validate_artifact
from src.phase19_subagent_forge import SubAgentForge

from tests.test_milestone_g_subagent_forge import create_phase19_fixture


def test_algorithmic_capability_manifest_is_safe_and_valid() -> None:
    manifest = build_algorithmic_capability_manifest()

    assert validate_artifact("algorithmic_capability_manifest", manifest) == manifest
    assert assert_algorithmic_manifest_safe(manifest) == manifest
    assert manifest["external_action_performed"] is False
    assert manifest["approval_boundary"]["self_approval_allowed"] is False
    assert manifest["capability_count"] == len(manifest["capabilities"])


def test_every_capability_blocks_forbidden_uses_and_external_action() -> None:
    manifest = build_algorithmic_capability_manifest()

    for capability in manifest["capabilities"]:
        assert capability["requires_human_review"] is True
        assert capability["external_action_allowed"] is False
        assert set(FORBIDDEN_USES).issubset(set(capability["forbidden_uses"]))
        assert capability["risk_controls"]
        assert capability["tests_required"]


def test_role_capabilities_are_assigned_without_self_approval() -> None:
    roles = [
        "Opportunity Scout",
        "Job Intake Analyst",
        "Best-Practice Synthesist",
        "Technical Deep-Dive Agent",
        "Learning Measures Agent",
        "Compliance and Ethics Agent",
        "Security Agent",
        "Execution Coordinator",
    ]

    for role in roles:
        capabilities = capabilities_for_role(role, ["documentation", "governed_handoff"])
        assert capabilities
        assert all(item["external_action_allowed"] is False for item in capabilities)
        assert all(item["requires_human_review"] is True for item in capabilities)


def test_phase19_agents_include_algorithmic_capability_metadata(tmp_path: Path) -> None:
    create_phase19_fixture(tmp_path)

    plans = SubAgentForge(tmp_path).run_from_config(tmp_path / "config" / "phase19_subagent_forge.json")
    payload = asdict(plans[0])

    validate_artifact("subagent_team_plan", payload)
    for member in payload["team_members"]:
        assert member["algorithmic_capabilities"]
        assert all(capability["external_action_allowed"] is False for capability in member["algorithmic_capabilities"])
