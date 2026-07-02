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
from src.phase15_finance_contracts_ledger import FinanceContractsLedger
from src.phase16_compliance_review import ComplianceReviewEngine
from src.phase17_incident_response import Phase17IncidentResponse


def test_phase15_finance_ledger_generates_internal_records(tmp_path: Path) -> None:
    create_milestone_d_fixture(tmp_path)
    records = FinanceContractsLedger(tmp_path).run_from_config(tmp_path / "config" / "phase15_finance_contracts_ledger.json")

    assert len(records) == 1
    record = asdict(records[0])
    validate_artifact("finance_ledger_record", record)
    assert record["status"] == "internal_estimate_only"
    assert record["proposed_amount"] == 1000.0
    assert record["contract_status"] == "not_started"
    assert record["external_action_performed"] is False


def test_phase16_compliance_review_flags_regulated_and_ai_disclosure(tmp_path: Path) -> None:
    create_milestone_d_fixture(tmp_path, regulated=True, missing_disclosure=True)
    records = ComplianceReviewEngine(tmp_path).run_from_config(tmp_path / "config" / "phase16_compliance_review.json")

    assert len(records) == 1
    review = asdict(records[0])
    validate_artifact("compliance_review", review)
    assert review["compliance_status"] == "orange"
    assert "finance" in review["regulated_domain_flags"]
    assert "add_or_confirm_ai_use_disclosure" in review["required_actions"]
    assert review["external_action_performed"] is False


def test_phase17_incident_response_creates_internal_report(tmp_path: Path) -> None:
    create_phase17_config(tmp_path)
    payload = Phase17IncidentResponse(tmp_path).run_from_config(
        config_path=tmp_path / "config" / "phase17_incident_response.json",
        incident_type="prompt_injection",
        severity="medium",
        summary="Unit-test incident.",
        evidence={"source": "unit_test"},
    )
    log_path = tmp_path / "data" / "phase17_incidents" / "incident_reports.jsonl"
    incident = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])

    validate_artifact("incident_report", incident)
    assert payload["incident_count"] == 1
    assert payload["open_incidents"] == 1
    assert payload["external_action_performed"] is False
    assert incident["external_action_performed"] is False


def test_cli_create_incident_writes_internal_report(tmp_path: Path) -> None:
    create_phase17_config(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "create-incident",
            "--incident-type",
            "approval_bypass_attempt",
            "--severity",
            "high",
            "--summary",
            "Unit-test approval bypass incident.",
            "--evidence-json",
            "{\"source\":\"unit_test\"}",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["incident_count"] >= 1
    assert payload["external_action_performed"] is False


def test_phase_registry_includes_milestone_d_phases() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase15"].schema_name == "finance_ledger_record"
    assert registry["phase16"].schema_name == "compliance_review"
    assert registry["phase17"].schema_name == "incident_report"


def create_milestone_d_fixture(
    root: Path,
    regulated: bool = False,
    missing_disclosure: bool = False,
) -> None:
    for path in [
        root / "config",
        root / "data" / "phase2_processed",
        root / "data" / "phase4_proposals",
        root / "data" / "phase5_authorizations",
        root / "data" / "phase6_execution",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    title = "Finance workflow review" if regulated else "Documentation review"
    opportunity = {
        "opportunity_id": "opp_test",
        "source_platform": "Test Platform",
        "source_url": "https://example.invalid/opportunity",
        "title": title,
        "employer": "Example Client",
        "radar_score": 80,
        "radar_decision": "candidate",
        "pay_min": 800,
        "pay_max": 1200,
        "pay_currency": "USD",
        "pay_interval": "project",
        "risk_flags": ["unclear_pay"] if missing_disclosure else [],
        "description_plain": title,
    }
    proposal = {
        "proposal_id": "phase4_test",
        "opportunity_id": "opp_test",
        "status": "internal_draft_only",
        "title": title,
        "employer": "Example Client",
        "source_platform": "Test Platform",
        "source_url": "https://example.invalid/opportunity",
        "employer_facing_message": "Hello, this is an internal test proposal.",
        "scope_of_work": {
            "summary": "Internal test scope."
        },
        "deliverables": [],
        "ai_use_disclosure": {} if missing_disclosure else {"draft_language": "AI assistance disclosed."},
        "readiness_decision": "ready_for_phase_5",
    }
    (root / "data" / "phase2_processed" / "aigc_phase2_opportunity_queue.json").write_text(json.dumps([opportunity], indent=2), encoding="utf-8")
    (root / "data" / "phase4_proposals" / "aigc_phase4_proposal_packages.json").write_text(json.dumps([proposal], indent=2), encoding="utf-8")
    (root / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json").write_text("[]", encoding="utf-8")
    (root / "data" / "phase6_execution" / "aigc_phase6_execution_receipts.json").write_text("[]", encoding="utf-8")
    (root / "config" / "phase15_finance_contracts_ledger.json").write_text(json.dumps({
        "input_files": {
            "opportunities": "data/phase2_processed/aigc_phase2_opportunity_queue.json",
            "proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
            "authorizations": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
            "executions": "data/phase6_execution/aigc_phase6_execution_receipts.json",
        },
        "output_file": "data/phase15_finance/aigc_phase15_finance_ledger.json",
        "currency_fallback": "unknown",
    }, indent=2), encoding="utf-8")
    (root / "config" / "phase16_compliance_review.json").write_text(json.dumps({
        "input_files": {
            "opportunities": "data/phase2_processed/aigc_phase2_opportunity_queue.json",
            "proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
            "authorizations": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
        },
        "output_file": "data/phase16_compliance/aigc_phase16_compliance_reviews.json",
        "regulated_terms": ["finance", "medical", "legal"],
    }, indent=2), encoding="utf-8")


def create_phase17_config(root: Path) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "phase17_incident_response.json").write_text(json.dumps({
        "incident_log": "data/phase17_incidents/incident_reports.jsonl",
        "summary_file": "data/phase17_incidents/incident_response_summary.json",
        "report_file": "reports/phase17_incident_response_report.md",
        "required_controls": ["emergency_stop", "postmortem"],
    }, indent=2), encoding="utf-8")
