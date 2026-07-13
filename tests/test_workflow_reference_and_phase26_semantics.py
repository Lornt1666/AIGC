from __future__ import annotations

from pathlib import Path
import re

import pytest

from src.core.phase_registry import get_phase
from src.phase26_constellation_refactor import build_plan, default_config, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = PROJECT_ROOT / ".github" / "workflows"
TRIGGER_WORKFLOW = WORKFLOW_ROOT / "aigc_constellation_trigger.yml"
CANONICAL_PHASE26_CONFIG = "config/phase26_constellation_refactor.json"
DEFECTIVE_PHASE26_CONFIG = "config/aigc_phase26_constellation_refactor.json"

PYTHON_SCRIPT_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_./-])(src/[A-Za-z0-9_./-]+\.py)(?![A-Za-z0-9_./-])"
)
CONFIG_REFERENCE = re.compile(
    r"--config\s+([A-Za-z0-9_./-]+)"
)


def _workflow_paths() -> list[Path]:
    paths = {
        *WORKFLOW_ROOT.rglob("*.yml"),
        *WORKFLOW_ROOT.rglob("*.yaml"),
    }
    return sorted(path for path in paths if path.is_file())


def _static_local_references(workflow_path: Path) -> list[tuple[str, str]]:
    workflow = workflow_path.read_text(encoding="utf-8")
    references = [
        ("SCRIPT_PATH", value)
        for value in PYTHON_SCRIPT_REFERENCE.findall(workflow)
    ]
    references.extend(
        ("CONFIG_PATH", value)
        for value in CONFIG_REFERENCE.findall(workflow)
    )
    return references


def test_every_static_mandatory_workflow_reference_resolves() -> None:
    workflows = _workflow_paths()
    assert workflows, "repository must contain GitHub Actions workflows"

    observed: list[tuple[Path, str, str]] = []
    missing: list[str] = []
    for workflow_path in workflows:
        for kind, relative_path in _static_local_references(workflow_path):
            observed.append((workflow_path, kind, relative_path))
            resolved = PROJECT_ROOT / relative_path
            if not resolved.is_file():
                missing.append(
                    f"{workflow_path.relative_to(PROJECT_ROOT).as_posix()}: "
                    f"{kind} {relative_path!r} does not resolve to a file"
                )

    assert observed, "workflow scan must observe repository-local executable references"
    assert not missing, "mandatory workflow reference integrity failed:\n" + "\n".join(missing)


def test_phase26_workflow_invocation_matches_canonical_registry() -> None:
    workflow = TRIGGER_WORKFLOW.read_text(encoding="utf-8")
    phase26 = get_phase("phase26", PROJECT_ROOT)
    config_index = phase26.command.index("--config") + 1
    registry_config = Path(phase26.command[config_index]).resolve()
    expected_config = (PROJECT_ROOT / CANONICAL_PHASE26_CONFIG).resolve()

    assert registry_config == expected_config
    assert f"--config {CANONICAL_PHASE26_CONFIG}" in workflow
    assert DEFECTIVE_PHASE26_CONFIG not in workflow


def test_phase26_explicit_missing_config_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Explicit Phase 26 configuration"):
        load_config(tmp_path, "config/missing-phase26.json")

    assert load_config(tmp_path, "") == default_config()


def test_phase25_manifest_drives_governed_phase26_semantics() -> None:
    config = load_config(PROJECT_ROOT, CANONICAL_PHASE26_CONFIG)
    manifest = {
        "generated_at": "2026-07-13T00:00:00Z",
        "status": "completed_proposal_only",
        "files": [
            {
                "path": "docs/operator_guide.md",
                "extension": ".md",
                "constellation_zone": "08_DOCS_OLOGY_LIBRARY",
                "ontology": "operator_documentation",
                "taxonomy": "governed_manual",
                "methodology": "documentation_governance",
                "agent_lane": "audit_archivist",
                "risk_class": "documentation_metadata",
            },
            {
                "path": ".github/workflows/aigc-ci.yml",
                "extension": ".yml",
                "constellation_zone": "01_CLOUD_TRIGGER_INGRESS",
                "ontology": "cloud_automation_control",
                "taxonomy": "workflow_or_repository_automation",
                "methodology": "cloud_trigger_ingress",
                "agent_lane": "cloud_trigger_sentinel",
                "risk_class": "cloud_control_metadata",
            },
        ],
    }

    plan = build_plan(PROJECT_ROOT, config, manifest)
    agent_ids = {
        str(agent["id"])
        for agent in plan["planning_agents"]
        if isinstance(agent, dict)
    }
    proposals = {
        proposal["source_path"]: proposal
        for proposal in plan["proposals"]
    }

    assert agent_ids == {
        "constellation_cartographer",
        "dependency_sentinel",
        "security_governor",
        "audit_archivist",
    }
    assert proposals["docs/operator_guide.md"]["proposed_target_path"] == (
        "constellation/08_docs_ology_library/docs/operator_guide.md"
    )
    workflow_proposal = proposals[".github/workflows/aigc-ci.yml"]
    assert workflow_proposal["proposed_action"] == (
        "retain_in_place_with_constellation_metadata"
    )
    assert workflow_proposal["requires_workflow_review"] is True
    assert workflow_proposal["physical_move_performed"] is False

    doctrine = plan["safety_doctrine"]
    assert doctrine["external_action_allowed"] is False
    assert doctrine["physical_file_moves_allowed"] is False
    assert doctrine["workflow_rewrite_allowed"] is False
    assert doctrine["credential_use_allowed"] is False
    assert doctrine["secret_value_logging_allowed"] is False
    assert doctrine["approval_required_for_future_write_back"] is True

    summary = plan["summary"]
    assert summary["physical_moves_performed"] is False
    assert summary["source_rewrites_performed"] is False
    assert summary["workflow_rewrites_performed"] is False
    assert summary["external_action_performed"] is False
    assert "separate reviewed PR" in plan["promotion_rule"]
