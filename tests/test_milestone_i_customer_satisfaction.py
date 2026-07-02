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
from src.phase21_customer_satisfaction_continuum import CustomerSatisfactionContinuum


def test_phase21_customer_satisfaction_generates_internal_chi_record(tmp_path: Path) -> None:
    create_phase21_fixture(tmp_path, compliance_status="green", finance_blockers=[])
    records = CustomerSatisfactionContinuum(tmp_path).run_from_config(
        tmp_path / "config" / "phase21_customer_satisfaction_continuum.json"
    )
    payload = asdict(records[0])

    validate_artifact("customer_satisfaction_record", payload)
    assert len(records) == 1
    assert payload["chi_score"] >= 85
    assert payload["status"] == "strong_customer_fit_ready_for_approval_review"
    assert payload["measurement_stage"] == "pre_external_action"
    assert payload["approval_required_before_external_action"] is True
    assert payload["external_action_performed"] is False


def test_phase21_customer_satisfaction_surfaces_review_risks(tmp_path: Path) -> None:
    create_phase21_fixture(tmp_path, compliance_status="orange", finance_blockers=["pay_or_budget_not_visible"])
    records = CustomerSatisfactionContinuum(tmp_path).run_from_config(
        tmp_path / "config" / "phase21_customer_satisfaction_continuum.json"
    )
    payload = asdict(records[0])

    validate_artifact("customer_satisfaction_record", payload)
    assert "compliance_orange" in payload["risk_flags"]
    assert "pay_or_budget_not_visible" in payload["risk_flags"]
    assert "phase5_approval_pending" in payload["risk_flags"]
    assert payload["improvement_actions"]
    assert payload["external_action_performed"] is False


def test_cli_run_phase21_exports_customer_satisfaction_records(tmp_path: Path) -> None:
    create_phase21_fixture(tmp_path, compliance_status="green", finance_blockers=[])
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase21",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase21_customer_satisfaction" / "aigc_phase21_customer_satisfaction_records.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("customer_satisfaction_record", payload[0])
    assert payload[0]["external_action_performed"] is False


def test_phase_registry_includes_phase21_customer_satisfaction() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase21"].schema_name == "customer_satisfaction_record"
    assert registry["phase21"].external_action_risk == "none_internal_customer_scoring_only"


def create_phase21_fixture(
    root: Path,
    compliance_status: str,
    finance_blockers: list[str],
) -> None:
    for path in [
        root / "config",
        root / "data" / "phase4_proposals",
        root / "data" / "phase5_authorizations",
        root / "data" / "phase15_finance",
        root / "data" / "phase16_compliance",
        root / "data" / "phase20_fidelity",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    proposal = {
        "proposal_id": "phase4_test",
        "opportunity_id": "opp_test",
        "title": "Documentation task",
        "employer": "Example Client",
        "source_platform": "Example",
        "source_url": "https://example.invalid/task",
        "status": "internal_draft_only",
        "employer_facing_message": (
            "Hello Example Client,\n"
            "I can help prepare the requested documentation with clear scope, review notes, "
            "acceptance criteria, and revision support. Before finalizing, I will clarify format, "
            "deadline, and any style requirements so the work stays aligned."
            "\n\nBest regards,\nJustice Gray Maciocha"
        ),
        "technical_message_variant": "Technical review notes and quality plan.",
        "timeline": "One focused internal draft after scope confirmation.",
        "scope_of_work": ["Prepare a draft.", "Review against acceptance criteria."],
        "deliverables": [
            {
                "name": "Documentation Draft",
                "description": "A scoped draft.",
                "acceptance_criteria": ["Clear", "Traceable"],
                "format": "Markdown",
            },
            {
                "name": "Review Notes",
                "description": "Assumptions and unresolved questions.",
                "acceptance_criteria": ["Concise", "Useful"],
                "format": "Markdown",
            },
        ],
        "clarifying_questions": ["What final format do you prefer?"],
        "forbidden_actions": ["send_external_message", "submit_application", "use_credentials"],
        "ai_use_disclosure": {"required": True, "draft_language": "AI-assisted workflow with human review."},
        "quality_assurance_plan": ["Trace requirements.", "Review final draft."],
        "audit_summary": "Internal audit summary.",
    }
    fidelity = {
        "review_id": "AIGC-FID-TEST",
        "opportunity_id": "opp_test",
        "proposal_id": "phase4_test",
        "fidelity_score": 94,
        "quality_status": "high_fidelity_ready_for_approval_review",
        "risk_flags": [],
        "external_action_performed": False,
    }
    finance = {
        "record_id": "AIGC-FIN-TEST",
        "opportunity_id": "opp_test",
        "proposal_id": "phase4_test",
        "status": "internal_estimate_only",
        "payment_status": "not_started",
        "contract_status": "not_started",
        "blockers": finance_blockers,
        "external_action_performed": False,
    }
    compliance = {
        "review_id": "AIGC-COMP-TEST",
        "opportunity_id": "opp_test",
        "proposal_id": "phase4_test",
        "status": "cleared_internal" if compliance_status == "green" else "requires_operator_review",
        "compliance_status": compliance_status,
        "risk_flags": [] if compliance_status == "green" else ["unclear_pay"],
        "required_actions": [],
        "external_action_performed": False,
    }
    authorization = {
        "authorization_id": "AIGC-AUTH-TEST",
        "action_id": "AIGC-ACT-TEST",
        "proposal_id": "phase4_test",
        "opportunity_id": "opp_test",
        "decision": "pending",
        "phase6_status": {"authorized_for_phase6": False, "external_action_performed": False},
    }
    (root / "data" / "phase4_proposals" / "aigc_phase4_proposal_packages.json").write_text(
        json.dumps([proposal], indent=2),
        encoding="utf-8",
    )
    (root / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json").write_text(
        json.dumps([authorization], indent=2),
        encoding="utf-8",
    )
    (root / "data" / "phase15_finance" / "aigc_phase15_finance_ledger.json").write_text(
        json.dumps([finance], indent=2),
        encoding="utf-8",
    )
    (root / "data" / "phase16_compliance" / "aigc_phase16_compliance_reviews.json").write_text(
        json.dumps([compliance], indent=2),
        encoding="utf-8",
    )
    (root / "data" / "phase20_fidelity" / "aigc_phase20_fidelity_reviews.json").write_text(
        json.dumps([fidelity], indent=2),
        encoding="utf-8",
    )
    (root / "config" / "phase21_customer_satisfaction_continuum.json").write_text(json.dumps({
        "input_files": {
            "proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
            "authorizations": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
            "finance_records": "data/phase15_finance/aigc_phase15_finance_ledger.json",
            "compliance_reviews": "data/phase16_compliance/aigc_phase16_compliance_reviews.json",
            "fidelity_reviews": "data/phase20_fidelity/aigc_phase20_fidelity_reviews.json",
        },
        "output_file": "data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json",
        "report_file": "data/reports/phase21_signature_update.md",
        "audit_log": "data/audit/aigc_phase21_audit.jsonl",
        "max_records": 5,
        "measurement_stage": "pre_external_action",
        "thresholds": {
            "strong_customer_fit": 85,
            "good_fit_with_review": 75,
            "revision_recommended": 65,
        },
    }, indent=2), encoding="utf-8")
