from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.pipeline_closure import PipelineClosureRunner
from src.core.state_store import AIGCStateStore
from src.phase6_controlled_execution import HashTools


def test_pipeline_closure_creates_internal_receipt_and_audit_packet(tmp_path: Path) -> None:
    create_closure_fixture(tmp_path)
    store = AIGCStateStore(tmp_path / "memory" / "state.sqlite")
    result = PipelineClosureRunner(tmp_path, store).run(execution_mode="dry_run")

    receipts = json.loads((tmp_path / "data" / "phase6_execution" / "aigc_phase6_execution_receipts.json").read_text(encoding="utf-8"))
    packets = json.loads((tmp_path / "data" / "phase7_audit_packets" / "aigc_phase7_employer_audit_packets.json").read_text(encoding="utf-8"))
    summary = store.get_status_summary()

    assert result.status == "phase7_internal_drafts_ready"
    assert result.external_action_performed is False
    assert result.phase6_receipts_created == 1
    assert result.phase7_packets_created == 1
    assert receipts[0]["status"] == "dry_run_complete"
    assert packets[0]["linked_records"]["phase6_execution_id"] == receipts[0]["execution_id"]
    assert summary["runtime_events"] == 1


def test_cli_revise_updates_temp_authorization_only(tmp_path: Path) -> None:
    action_id = "AIGC-ACT-TEST-REV"
    packet_path = tmp_path / "authorizations.json"
    packet_path.write_text(json.dumps([minimal_authorization_packet(action_id)], indent=2), encoding="utf-8")
    phrase = f"Revise action {action_id}: make this shorter before approval"

    result = subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "revise",
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

    assert output["decision"] == "revision_required"
    assert output["external_action_performed"] is False
    assert packets[0]["decision"] == "revision_required"
    assert packets[0]["phase6_status"]["authorized_for_phase6"] is False


def test_cli_approve_rejects_expired_authorization(tmp_path: Path) -> None:
    action_id = "AIGC-ACT-TEST-EXP"
    packet = minimal_authorization_packet(action_id)
    packet["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    packet_path = tmp_path / "authorizations.json"
    packet_path.write_text(json.dumps([packet], indent=2), encoding="utf-8")
    phrase = packet["approval"]["required_phrase"]

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
    )
    packets = json.loads(packet_path.read_text(encoding="utf-8"))

    assert result.returncode == 2
    assert "Authorization expired" in result.stdout
    assert packets[0]["decision"] == "pending"
    assert packets[0]["phase6_status"]["authorized_for_phase6"] is False


def create_closure_fixture(root: Path) -> None:
    for path in [
        root / "config",
        root / "data" / "phase4_proposals",
        root / "data" / "phase5_authorizations",
        root / "data" / "phase6_execution",
        root / "data" / "phase7_audit_packets",
    ]:
        path.mkdir(parents=True, exist_ok=True)

    content = "Hello Example Client,\nThis is an approved internal-only proposal fixture."
    artifact_hash = HashTools.hash_text(content)
    proposal = {
        "proposal_id": "phase4_test",
        "opportunity_id": "opp_test",
        "dossier_id": "phase3_test",
        "title": "Internal Test Task",
        "employer": "Example Client",
        "source_platform": "Manual Test",
        "source_url": "https://example.invalid/test",
        "employer_facing_message": content,
        "scope_of_work": {
            "summary": "Prepare an internal fixture.",
            "included_work": ["Internal test preparation"],
            "excluded_work": ["External submission"],
            "assumptions": ["No external action occurs"],
            "dependencies": ["Approved fixture"],
        },
        "deliverables": [
            {
                "name": "Fixture Deliverable",
                "description": "Internal-only test deliverable.",
                "format": "Markdown",
                "acceptance_criteria": ["Validates closure path"],
            }
        ],
        "ai_use_disclosure": {
            "draft_language": "AI-assisted workflow may be used with human review."
        },
    }
    authorization = minimal_authorization_packet("AIGC-ACT-TEST-CLOSE")
    authorization.update({
        "authorization_id": "AIGC-AUTH-CLOSE",
        "proposal_id": "phase4_test",
        "opportunity_id": "opp_test",
        "recipient": "Example Client",
        "platform": "Manual Test",
        "source_url": "https://example.invalid/test",
        "artifact": {
            "artifact_type": "proposal",
            "artifact_hash": artifact_hash,
            "artifact_preview": content,
        },
        "approval": {
            **authorization["approval"],
            "approved": True,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        },
        "phase6_status": {
            "authorized_for_phase6": True,
            "execution_scope": "Dry-run this approved fixture only.",
            "external_action_performed": False,
        },
        "safety_evidence": {
            name: {
                "status": "passed",
                "evidence_ref": f"test-evidence://phase6/{name}",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewer": "test-fixture-reviewer",
            }
            for name in (
                "platform_policy_checked",
                "ai_disclosure_preserved",
                "privacy_checked",
            )
        },
        "decision": "approved_for_phase_6",
    })

    (root / "data" / "phase4_proposals" / "aigc_phase4_proposal_packages.json").write_text(json.dumps([proposal], indent=2), encoding="utf-8")
    (root / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json").write_text(json.dumps([authorization], indent=2), encoding="utf-8")
    (root / "config" / "phase6_controlled_execution.json").write_text(json.dumps({
        "default_execution_mode": "manual_handoff",
        "live_execution_allowed": False,
        "input_files": {
            "phase4_proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
            "phase5_authorizations": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
        },
        "output_file": "data/phase6_execution/aigc_phase6_execution_receipts.json",
    }, indent=2), encoding="utf-8")
    (root / "config" / "phase7_employer_audit_packet.json").write_text(json.dumps({
        "input_files": {
            "phase4_proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
            "phase5_authorizations": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
            "phase6_receipts": "data/phase6_execution/aigc_phase6_execution_receipts.json",
        },
        "output_file": "data/phase7_audit_packets/aigc_phase7_employer_audit_packets.json",
        "markdown_output_dir": "data/phase7_audit_packets",
    }, indent=2), encoding="utf-8")


def minimal_authorization_packet(action_id: str) -> dict:
    return {
        "authorization_id": "AIGC-AUTH-TEST",
        "action_id": action_id,
        "proposal_id": "phase4_test",
        "opportunity_id": "opp_test",
        "operator": "Justice Gray Maciocha",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "proposed_external_action": "Internal test approval only.",
        "recipient": "Test Recipient",
        "platform": "Test Platform",
        "source_url": "https://example.invalid/test",
        "artifact": {
            "artifact_type": "proposal",
            "artifact_hash": "abc123",
            "artifact_preview": "Internal test artifact.",
        },
        "classification": {
            "action_class": "approval_required",
            "risk_class": "low",
            "safety_status": "cleared",
        },
        "checks": {
            "safety_check_score": 15,
            "coherence_check_score": 10,
            "proposal_readiness_score": 100,
            "ai_disclosure_status": "included",
        },
        "approval": {
            "required": True,
            "required_phrase": f"I, Justice Gray Maciocha, accept action {action_id}.",
            "denial_phrase": f"I, Justice Gray Maciocha, deny action {action_id}.",
            "received_phrase": "",
            "approved": False,
            "denied": False,
            "revision_required": False,
            "approved_at": "",
            "decision_notes": "",
        },
        "phase6_status": {
            "authorized_for_phase6": False,
            "execution_scope": "Internal test only.",
            "external_action_performed": False,
        },
        "decision": "pending",
    }

