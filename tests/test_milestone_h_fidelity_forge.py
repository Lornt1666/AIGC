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
from src.phase20_fidelity_forge import FidelityForge


def test_phase20_fidelity_forge_generates_internal_review(tmp_path: Path) -> None:
    create_phase20_fixture(tmp_path)
    reviews = FidelityForge(tmp_path).run_from_config(tmp_path / "config" / "phase20_fidelity_forge.json")
    payload = asdict(reviews[0])

    validate_artifact("fidelity_review", payload)
    assert len(reviews) == 1
    assert payload["status"] == "internal_review_only"
    assert payload["fidelity_score"] >= 90
    assert payload["quality_status"] == "high_fidelity_ready_for_approval_review"
    assert payload["approval_required_before_external_action"] is True
    assert payload["external_action_performed"] is False
    assert all(check["status"] == "passed" for check in payload["checks"])


def test_phase20_fidelity_forge_flags_missing_quality_inputs(tmp_path: Path) -> None:
    create_phase20_fixture(tmp_path, include_disclosure=False, include_team=False)
    reviews = FidelityForge(tmp_path).run_from_config(tmp_path / "config" / "phase20_fidelity_forge.json")
    payload = asdict(reviews[0])

    validate_artifact("fidelity_review", payload)
    assert payload["fidelity_score"] < 90
    assert "failed_ai_disclosure_preserved" in payload["risk_flags"]
    assert "failed_subagent_team_present" in payload["risk_flags"]
    assert payload["revision_recommendations"]
    assert payload["external_action_performed"] is False


def test_cli_run_phase20_exports_fidelity_reviews(tmp_path: Path) -> None:
    create_phase20_fixture(tmp_path)
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase20",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase20_fidelity" / "aigc_phase20_fidelity_reviews.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("fidelity_review", payload[0])
    assert payload[0]["external_action_performed"] is False


def test_phase_registry_includes_phase20_fidelity_forge() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase20"].schema_name == "fidelity_review"
    assert registry["phase20"].external_action_risk == "none_internal_quality_review_only"


def create_phase20_fixture(
    root: Path,
    include_disclosure: bool = True,
    include_team: bool = True,
) -> None:
    for path in [
        root / "config",
        root / "data" / "phase3_processed",
        root / "data" / "phase4_proposals",
        root / "data" / "phase16_compliance",
        root / "data" / "phase19_subagents",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    disclosure = {
        "required": True,
        "recommended": True,
        "draft_language": "I use a structured AI-assisted workflow with final human review.",
    }
    proposal = {
        "proposal_id": "phase4_test",
        "dossier_id": "phase3_test",
        "opportunity_id": "opp_test",
        "title": "Documentation task",
        "employer": "Example Client",
        "source_platform": "Example",
        "source_url": "https://example.invalid/task",
        "status": "internal_draft_only",
        "readiness_decision": "ready_for_phase_5",
        "employer_facing_message": (
            "Hello Example Client,\n"
            "I can help prepare the requested documentation with clear scope, review notes, "
            "and acceptance criteria. The draft will stay traceable to the source request, flag unknowns, "
            "and preserve all approval boundaries. I use a structured AI-assisted workflow with final human review."
        ),
        "scope_of_work": ["Prepare internal documentation draft.", "Review against request."],
        "deliverables": [
            {
                "name": "Documentation Draft",
                "description": "A scoped internal draft.",
                "acceptance_criteria": ["Clear", "Traceable"],
                "format": "Markdown",
            }
        ],
        "clarifying_questions": ["What final format do you prefer?"],
        "forbidden_actions": ["send_external_message", "submit_application", "use_credentials"],
        "approval_required_before": ["phase5_human_approval_gate"],
        "audit_summary": "Internal audit summary for the proposal package.",
    }
    if include_disclosure:
        proposal["ai_use_disclosure"] = disclosure
    assessment = {
        "dossier_id": "phase3_test",
        "opportunity_id": "opp_test",
        "title": "Documentation task",
        "employer": "Example Client",
        "source_platform": "Example",
        "source_url": "https://example.invalid/task",
    }
    compliance = {
        "review_id": "AIGC-COMP-TEST",
        "created_at": "2026-07-02T00:00:00+00:00",
        "opportunity_id": "opp_test",
        "proposal_id": "phase4_test",
        "status": "cleared_internal",
        "compliance_status": "green",
        "risk_flags": [],
        "required_actions": [],
        "external_action_performed": False,
    }
    team = {
        "team_id": "AIGC-TEAM-TEST",
        "created_at": "2026-07-02T00:00:00+00:00",
        "phase": "phase19_subagent_generation_forge",
        "status": "internal_plan_only",
        "opportunity_id": "opp_test",
        "proposal_id": "phase4_test",
        "title": "Documentation task",
        "employer": "Example Client",
        "team_members": [
            {"role": f"Role {index}", "external_action_allowed": False}
            for index in range(1, 6)
        ],
        "approval_required_before_external_action": True,
        "external_action_performed": False,
    }
    (root / "data" / "phase3_processed" / "aigc_phase3_assessment_dossiers.json").write_text(
        json.dumps([assessment], indent=2),
        encoding="utf-8",
    )
    (root / "data" / "phase4_proposals" / "aigc_phase4_proposal_packages.json").write_text(
        json.dumps([proposal], indent=2),
        encoding="utf-8",
    )
    (root / "data" / "phase16_compliance" / "aigc_phase16_compliance_reviews.json").write_text(
        json.dumps([compliance], indent=2),
        encoding="utf-8",
    )
    (root / "data" / "phase19_subagents" / "aigc_phase19_subagent_team_plans.json").write_text(
        json.dumps([team] if include_team else [], indent=2),
        encoding="utf-8",
    )
    (root / "config" / "phase20_fidelity_forge.json").write_text(json.dumps({
        "input_files": {
            "assessments": "data/phase3_processed/aigc_phase3_assessment_dossiers.json",
            "proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
            "subagent_team_plans": "data/phase19_subagents/aigc_phase19_subagent_team_plans.json",
            "compliance_reviews": "data/phase16_compliance/aigc_phase16_compliance_reviews.json",
        },
        "output_file": "data/phase20_fidelity/aigc_phase20_fidelity_reviews.json",
        "report_file": "data/reports/phase20_signature_update.md",
        "audit_log": "data/audit/aigc_phase20_audit.jsonl",
        "eligible_readiness_decisions": ["ready_for_phase_5"],
        "max_reviews": 5,
        "expected_min_subagents": 5,
        "thresholds": {
            "high_fidelity": 90,
            "ready_with_minor_review": 80,
            "revision_recommended": 65,
        },
    }, indent=2), encoding="utf-8")
