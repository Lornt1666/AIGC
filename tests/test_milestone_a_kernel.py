from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.contract_validator import ContractValidationError, validate_artifact, validate_file
from src.core.state_store import AIGCStateStore


REQUIRED_SCHEMAS = [
    "domain_record",
    "opportunity_record",
    "assessment_dossier",
    "proposal_package",
    "authorization_packet",
    "execution_receipt",
    "employer_audit_packet",
    "outcome_record",
    "evolution_patch",
    "secret_manifest",
    "runtime_event",
    "customer_satisfaction_record",
    "finance_ledger_record",
    "incident_report",
    "compliance_review",
    "connector_record",
    "productization_release_record",
    "subagent_team_plan",
    "fidelity_review",
]


def test_required_schema_files_exist() -> None:
    for schema_name in REQUIRED_SCHEMAS:
        assert (PROJECT_ROOT / "schemas" / f"{schema_name}.schema.json").exists()


def test_contract_validator_accepts_valid_sample() -> None:
    payload = {
        "event_id": "evt_1",
        "created_at": "2026-07-02T00:00:00+00:00",
        "event_type": "test",
        "phase": "phase14_runtime_engine",
        "status": "completed",
    }
    assert validate_artifact("runtime_event", payload) == payload


def test_contract_validator_rejects_invalid_sample() -> None:
    with pytest.raises(ContractValidationError):
        validate_artifact("runtime_event", {"event_id": "evt_1"})


def test_state_db_initializes(tmp_path: Path) -> None:
    store = AIGCStateStore(tmp_path / "aigc_state.sqlite")
    event = store.insert_event(
        event_type="test_event",
        phase="phase14_runtime_engine",
        status="completed",
        summary="State store test event.",
    )
    summary = store.get_status_summary()
    assert event.event_id.startswith("AIGC-EVENT-")
    assert summary["runtime_events"] == 1
    assert "finance_ledger" in summary["artifact_counts"]
    assert "compliance_reviews" in summary["artifact_counts"]
    assert "connectors" in summary["artifact_counts"]
    assert "productization_releases" in summary["artifact_counts"]
    assert "subagent_team_plans" in summary["artifact_counts"]
    assert "fidelity_reviews" in summary["artifact_counts"]
    assert "customer_satisfaction" in summary["artifact_counts"]


def test_cli_status_works(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "src/aigc.py", "--state-db", str(tmp_path / "state.sqlite"), "status"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert "artifact_counts" in payload
    assert payload["emergency_stop"] is False


def test_emergency_stop_works(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    subprocess.run(
        [sys.executable, "src/aigc.py", "--state-db", str(db_path), "emergency-stop"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    result = subprocess.run(
        [sys.executable, "src/aigc.py", "--state-db", str(db_path), "status"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["emergency_stop"] is True


def test_secret_manifest_validates_without_secret_values() -> None:
    manifest_path = PROJECT_ROOT / "config" / "secret_manifest.json"
    validate_file("secret_manifest", manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["rules"]["store_raw_secret_values_in_repo"] is False
    assert payload["rules"]["log_secret_values"] is False
    assert payload["rules"]["print_secret_values"] is False
    for record in payload["secrets"].values():
        assert record.get("log_value") is False
        assert record.get("store_raw_value_on_external_drive") is False


def test_result_envelope_event_bus_and_run_context(tmp_path: Path) -> None:
    from src.core.event_bus import EventBus
    from src.core.result_envelope import ok
    from src.core.run_context import RunContext

    store = AIGCStateStore(tmp_path / "state.sqlite")
    context = RunContext.create(PROJECT_ROOT, "internal_test", tmp_path / "state.sqlite")
    result = ok("phase14_runtime_engine", "Envelope test.", {"run_id": context.run_id})
    event = EventBus(store).publish_result("result_envelope_test", result)
    summary = store.get_status_summary()
    assert context.external_actions_allowed is False
    assert result.external_action_performed is False
    assert event.event_id.startswith("AIGC-EVENT-")
    assert summary["runtime_events"] == 1


def test_cli_approve_updates_temp_authorization_only(tmp_path: Path) -> None:
    action_id = "AIGC-ACT-TEST-0001"
    phrase = f"I, Justice Gray Maciocha, accept action {action_id}."
    packet_path = tmp_path / "authorizations.json"
    packet_path.write_text(json.dumps([
        {
            "authorization_id": "AIGC-AUTH-TEST",
            "action_id": action_id,
            "proposal_id": "phase4_test",
            "opportunity_id": "opp_test",
            "operator": "Justice Gray Maciocha",
            "proposed_external_action": "Internal test approval only.",
            "recipient": "Test Recipient",
            "platform": "Test Platform",
            "artifact": {
                "artifact_type": "proposal",
                "artifact_hash": "abc123"
            },
            "classification": {
                "action_class": "approval_required",
                "risk_class": "low",
                "safety_status": "cleared"
            },
            "approval": {
                "required": True,
                "required_phrase": phrase,
                "denial_phrase": f"I, Justice Gray Maciocha, deny action {action_id}.",
                "received_phrase": "",
                "approved": False,
                "denied": False,
                "revision_required": False,
                "approved_at": "",
                "decision_notes": ""
            },
            "phase6_status": {
                "authorized_for_phase6": False,
                "external_action_performed": False
            },
            "decision": "pending"
        }
    ], indent=2), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "approve",
            "--action-id",
            action_id,
            "--phrase",
            phrase,
            "--authorizations-path",
            str(packet_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output = json.loads(result.stdout)
    packets = json.loads(packet_path.read_text(encoding="utf-8"))
    assert output["decision"] == "approved_for_phase_6"
    assert output["external_action_performed"] is False
    assert packets[0]["decision"] == "approved_for_phase_6"
    assert packets[0]["phase6_status"]["authorized_for_phase6"] is True
    assert packets[0]["phase6_status"]["external_action_performed"] is False


def test_enhanced_secret_scanner_detects_runtime_secret_like_text() -> None:
    from src.security.redaction_scanner import RedactionScanner

    token = "s" + "k-" + ("a" * 24)
    findings = RedactionScanner().scan_text(f"api_key = '{token}'", path="<test>")
    assert findings
    assert findings[0].line_number == 1


def test_approval_token_store_hashes_raw_token(tmp_path: Path) -> None:
    from src.security.approval_tokens import ApprovalTokenStore

    store_path = tmp_path / "approval_tokens.jsonl"
    store = ApprovalTokenStore(store_path)
    issued = store.issue_token(
        scope="secret:OPENAI_API_KEY",
        phase="phase4_proposal_drafting",
        reason="unit test",
        ttl_minutes=5,
    )
    raw_text = store_path.read_text(encoding="utf-8")
    assert issued.token not in raw_text
    validated = store.validate_token(
        issued.token,
        required_scope="secret:OPENAI_API_KEY",
        phase="phase4_proposal_drafting",
    )
    assert validated.used_at


def test_incident_report_validates(tmp_path: Path) -> None:
    from dataclasses import asdict

    from src.incidents.incident_response import IncidentResponseLedger

    ledger = IncidentResponseLedger(tmp_path / "incidents.jsonl")
    report = ledger.create_report(
        incident_type="secret_leak_suspicion",
        severity="high",
        summary="Unit-test incident report.",
        evidence={"source": "unit_test"},
    )
    validate_artifact("incident_report", asdict(report))
    assert report.external_action_performed is False
    assert report.containment_steps
