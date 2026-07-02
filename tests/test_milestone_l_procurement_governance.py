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
from src.phase24_procurement_governance import TruthFirstProcurementGovernance


def test_phase24_procurement_flags_expired_generated_packets(tmp_path: Path) -> None:
    create_phase24_fixture(tmp_path, expires_at="2026-01-01T00:00:00+00:00")
    records = TruthFirstProcurementGovernance(tmp_path).run_from_config(
        tmp_path / "config" / "phase24_procurement_governance.json"
    )
    payload = asdict(records[0])

    validate_artifact("procurement_record", payload)
    assert payload["source_truth_status"] == "real_read_only_source_snapshot_present"
    assert payload["procurement_classification"] == "real_source_with_expired_generated_action_candidate"
    assert payload["procurement_decision"] == "archive_or_regenerate_before_action"
    assert payload["current_action_state"]["expired"] is True
    assert payload["truth_controls"]["stale_generated_artifacts_active"] is True
    assert payload["truth_controls"]["requires_regeneration_before_approval"] is True
    assert any("Archive expired Phase 5" in action for action in payload["recommended_cleanup_actions"])
    assert any(item["truth_role"] == "source_evidence" for item in payload["artifact_chain"])
    assert any(item["truth_role"] == "generated_internal_derivative" for item in payload["artifact_chain"])
    assert payload["deletion_performed"] is False
    assert payload["external_action_performed"] is False


def test_phase24_procurement_handles_active_pending_packet(tmp_path: Path) -> None:
    create_phase24_fixture(tmp_path, expires_at="2099-01-01T00:00:00+00:00")
    records = TruthFirstProcurementGovernance(tmp_path).run_from_config(
        tmp_path / "config" / "phase24_procurement_governance.json"
    )
    payload = asdict(records[0])

    validate_artifact("procurement_record", payload)
    assert payload["procurement_classification"] == "real_source_with_pending_generated_action_candidate"
    assert payload["procurement_decision"] == "operator_review_required_before_action"
    assert payload["current_action_state"]["expired"] is False
    assert payload["truth_controls"]["stale_generated_artifacts_active"] is False
    assert payload["deletion_performed"] is False
    assert payload["external_action_performed"] is False


def test_cli_run_phase24_exports_procurement_records(tmp_path: Path) -> None:
    create_phase24_fixture(tmp_path, expires_at="2026-01-01T00:00:00+00:00")
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase24",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase24_procurement" / "aigc_phase24_procurement_records.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("procurement_record", payload[0])
    assert payload[0]["procurement_decision"] == "archive_or_regenerate_before_action"
    assert payload[0]["deletion_performed"] is False


def test_phase_registry_includes_phase24_procurement_governance() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase24"].schema_name == "procurement_record"
    assert registry["phase24"].external_action_risk == "none_internal_procurement_truth_ledger_only"


def create_phase24_fixture(root: Path, expires_at: str) -> None:
    for path in [
        root / "config",
        root / "data" / "phase2_processed",
        root / "data" / "phase4_proposals",
        root / "data" / "phase5_authorizations",
        root / "data" / "phase22_quality",
        root / "data" / "phase23_work_orders",
    ]:
        path.mkdir(parents=True, exist_ok=True)

    opportunity = {
        "opportunity_id": "opp_proc_test",
        "source_platform": "GitHub",
        "source_type": "api",
        "source_url": "https://example.invalid/issues/1",
        "source_attribution_required": False,
        "discovered_at": "2026-07-02T00:00:00+00:00",
        "title": "Procurement truth test",
        "employer": "Example Maintainer",
        "client": "",
        "location": "",
        "remote_status": "remote",
        "work_type": "open_source",
        "employment_type": "unknown",
        "pay_currency": "",
        "pay_interval": "unknown",
        "deadline": "",
        "posted_at": "2026-07-01T00:00:00+00:00",
        "updated_at": "2026-07-01T00:00:00+00:00",
        "description_plain": "A source opportunity captured through read-only discovery.",
        "description_html": "",
        "requirements": [],
        "responsibilities": [],
        "deliverables": ["Truthful procurement classification."],
        "skills_detected": ["documentation"],
        "tools_detected": ["github"],
        "discipline_taxonomy": ["open_source_contribution"],
        "automation_signals": {
            "api_related": False,
            "documentation_related": True,
            "research_related": False,
            "coding_related": False,
            "data_related": False,
            "writing_related": True,
            "repetitive_workflow": False,
            "clear_deliverable": True,
        },
        "ai_use_signals": {
            "ai_allowed_explicit": False,
            "ai_forbidden_explicit": False,
            "ai_unclear": True,
            "disclosure_needed": True,
        },
        "platform_policy_status": "green",
        "risk_flags": ["unclear_pay"],
        "forbidden_flags": [],
        "approval_required_before": ["submit_proposal"],
        "radar_score": 80,
        "radar_decision": "queue_for_phase_3",
        "audit_notes": "Fixture source snapshot.",
    }
    proposal = {
        "proposal_id": "proposal_proc_test",
        "package_id": "proposal_proc_test",
        "opportunity_id": "opp_proc_test",
        "created_at": "2026-07-02T00:10:00+00:00",
        "operator": "Justice Gray Maciocha",
        "status": "internal_draft_only",
        "title": "Procurement truth test",
        "employer": "Example Maintainer",
        "source_platform": "GitHub",
        "source_url": "https://example.invalid/issues/1",
        "employer_facing_message": "Internal draft only.",
        "readiness_decision": "ready_for_phase_5",
        "audit_summary": {"external_action_performed": False},
        "external_action_classification": {
            "classification": "internal_draft_only",
            "external_actions_allowed": False,
            "requires_explicit_justice_approval_before_send": True,
            "send_ready": False,
        },
    }
    authorization = {
        "authorization_id": "auth_proc_test",
        "action_id": "AIGC-ACT-PROC-TEST",
        "proposal_id": "proposal_proc_test",
        "opportunity_id": "opp_proc_test",
        "operator": "Justice Gray Maciocha",
        "created_at": "2026-07-02T00:20:00+00:00",
        "expires_at": expires_at,
        "proposed_external_action": "Send proposal/message to Example Maintainer.",
        "recipient": "Example Maintainer",
        "platform": "GitHub",
        "source_url": "https://example.invalid/issues/1",
        "artifact": {
            "artifact_type": "proposal",
            "artifact_summary": "Internal fixture proposal.",
            "artifact_hash": "abc123",
            "artifact_preview": "Internal draft only.",
        },
        "classification": {
            "action_class": "approval_required",
            "risk_class": "medium",
            "safety_status": "caution",
        },
        "approval": {
            "required": True,
            "required_phrase": "I, Justice Gray Maciocha, accept action AIGC-ACT-PROC-TEST.",
            "denial_phrase": "I, Justice Gray Maciocha, deny action AIGC-ACT-PROC-TEST.",
            "received_phrase": "",
            "approved": False,
            "denied": False,
            "revision_required": False,
            "approved_at": "",
            "decision_notes": "",
        },
        "phase6_status": {
            "authorized_for_phase6": False,
            "external_action_performed": False,
        },
        "decision": "pending",
    }
    quality_record = {
        "record_id": "AIGC-QK-PROC",
        "proposal_id": "proposal_proc_test",
        "opportunity_id": "opp_proc_test",
        "status": "internal_quality_state_recorded",
        "external_action_performed": False,
    }
    work_order_record = {
        "record_id": "AIGC-WOG-PROC",
        "proposal_id": "proposal_proc_test",
        "opportunity_id": "opp_proc_test",
        "status": "internal_work_order_governance_recorded",
        "external_action_performed": False,
    }

    write_json(root / "data" / "phase2_processed" / "aigc_phase2_opportunity_queue.json", [opportunity])
    write_json(root / "data" / "phase4_proposals" / "aigc_phase4_proposal_packages.json", [proposal])
    write_json(root / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json", [authorization])
    write_json(root / "data" / "phase22_quality" / "aigc_phase22_quality_kernel_records.json", [quality_record])
    write_json(root / "data" / "phase23_work_orders" / "aigc_phase23_work_order_governance_records.json", [work_order_record])
    write_json(
        root / "config" / "phase24_procurement_governance.json",
        {
            "input_files": {
                "opportunities": "data/phase2_processed/aigc_phase2_opportunity_queue.json",
                "proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
                "authorizations": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
                "quality_kernel_records": "data/phase22_quality/aigc_phase22_quality_kernel_records.json",
                "work_order_governance_records": "data/phase23_work_orders/aigc_phase23_work_order_governance_records.json",
            },
            "output_file": "data/phase24_procurement/aigc_phase24_procurement_records.json",
            "report_file": "data/reports/phase24_signature_update.md",
            "audit_log": "data/audit/aigc_phase24_audit.jsonl",
            "max_records": 5,
            "blocked_actions": [
                "delete_artifacts_without_operator_command",
                "contact_external_party",
                "submit_application",
                "submit_proposal",
                "submit_deliverable",
                "approve_external_action",
                "use_credentials",
                "bypass_phase5_approval",
            ],
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
