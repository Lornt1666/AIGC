from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.contract_validator import validate_artifact
from src.core.phase_registry import build_phase_registry
from src.phase19_subagent_forge import SubAgentForge


def test_phase19_subagent_forge_generates_internal_team_plan(tmp_path: Path) -> None:
    create_phase19_fixture(tmp_path)
    plans = SubAgentForge(tmp_path).run_from_config(tmp_path / "config" / "phase19_subagent_forge.json")
    payload = asdict(plans[0])

    validate_artifact("subagent_team_plan", payload)
    assert len(plans) == 1
    assert payload["status"] == "internal_plan_only"
    assert payload["approval_required_before_external_action"] is True
    assert payload["external_action_performed"] is False
    assert len(payload["team_members"]) == 2
    assert all(member["external_action_allowed"] is False for member in payload["team_members"])
    assert all("send_external_message" in member["forbidden_actions"] for member in payload["team_members"])


def test_phase19_subagent_forge_filters_ineligible_proposals(tmp_path: Path) -> None:
    create_phase19_fixture(tmp_path, readiness_decision="needs_rewrite")
    plans = SubAgentForge(tmp_path).run_from_config(tmp_path / "config" / "phase19_subagent_forge.json")

    assert plans == []


def test_cli_run_phase19_exports_subagent_team_plans(tmp_path: Path) -> None:
    create_phase19_fixture(tmp_path)
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase19",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase19_subagents" / "aigc_phase19_subagent_team_plans.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("subagent_team_plan", payload[0])
    assert payload[0]["external_action_performed"] is False


def test_phase_registry_includes_phase19_subagent_forge() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase19"].schema_name == "subagent_team_plan"
    assert registry["phase19"].external_action_risk == "subagents_cannot_execute_externally"


def create_phase19_fixture(root: Path, readiness_decision: str = "ready_for_phase_5") -> None:
    for path in [
        root / "config",
        root / "data" / "phase3_processed",
        root / "data" / "phase4_proposals",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    assessment = {
        "dossier_id": "phase3_test",
        "opportunity_id": "opp_test",
        "title": "Documentation task",
        "employer": "Example Client",
        "source_platform": "Example",
        "source_url": "https://example.invalid/task",
        "discovered_taxonomy": ["writing_content", "documentation"],
    }
    proposal = {
        "proposal_id": "phase4_test",
        "dossier_id": "phase3_test",
        "opportunity_id": "opp_test",
        "title": "Documentation task",
        "employer": "Example Client",
        "source_platform": "Example",
        "source_url": "https://example.invalid/task",
        "readiness_decision": readiness_decision,
    }
    (root / "data" / "phase3_processed" / "aigc_phase3_assessment_dossiers.json").write_text(
        json.dumps([assessment], indent=2),
        encoding="utf-8",
    )
    (root / "data" / "phase4_proposals" / "aigc_phase4_proposal_packages.json").write_text(
        json.dumps([proposal], indent=2),
        encoding="utf-8",
    )
    (root / "config" / "phase19_subagent_forge.json").write_text(json.dumps({
        "input_files": {
            "assessments": "data/phase3_processed/aigc_phase3_assessment_dossiers.json",
            "proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
        },
        "output_file": "data/phase19_subagents/aigc_phase19_subagent_team_plans.json",
        "report_file": "data/reports/phase19_signature_update.md",
        "audit_log": "data/audit/aigc_phase19_audit.jsonl",
        "eligible_readiness_decisions": ["ready_for_phase_5"],
        "max_team_plans": 5,
        "default_role_templates": [
            {
                "role": "Task Architect",
                "purpose": "Plan the work.",
                "output_artifact": "task_architecture_brief",
                "handoff_target": "Requirement Extractor",
            },
            {
                "role": "Requirement Extractor",
                "purpose": "Extract requirements.",
                "output_artifact": "requirement_matrix",
                "handoff_target": "Phase 20 Fidelity Forge",
            },
        ],
        "allowed_internal_actions": ["read_internal_artifacts", "extract_requirements"],
        "forbidden_team_behaviors": ["send_external_message", "submit_application", "use_credentials"],
        "required_approval_gates": ["phase5_human_approval_gate"],
        "quality_bar": ["requirements_traceable_to_source"],
    }, indent=2), encoding="utf-8")
