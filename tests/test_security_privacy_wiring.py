from __future__ import annotations

import json
from pathlib import Path

from src.core.security_privacy_wiring import build_security_privacy_wiring_receipt, run_security_privacy_wiring


def make_policy() -> dict:
    return {
        "policy_id": "TEST-WIRING",
        "mode": "unified_security_privacy_gate",
        "gate_order": [
            "hard_block_precheck",
            "counterparty_request_intake",
            "observer_authority_verification",
            "redaction_privacy_review",
            "sentinel_policy_review",
            "approval_gated_procedure_packet",
            "operator_popup_review",
            "audit_receipt",
        ],
        "external_action_families": ["accept", "message"],
        "observer_action_families": ["observer_access", "invite_observer", "share_chatlog"],
        "sharing_action_families": ["message", "observer_access", "invite_observer", "share_chatlog"],
        "hard_blocks": [
            "raw_secret",
            "raw_chatlog_sharing",
            "whole_account_access",
            "backend_access",
            "self_approval",
            "fabricated_credentials",
            "platform_rule_bypass",
            "unverified_observer_authority",
            "silent_external_sharing",
        ],
        "privacy_scan": {
            "required_for_all_requests": True,
            "explicit_redaction_review_required_for_sharing": True,
            "blocked_secret_markers": ["sk-", "api_key", "password", "client_secret"],
        },
        "sentinel_controls": {
            "deny_by_default": True,
            "operator_popup_required": True,
            "audit_receipt_required": True,
            "external_action_performed_default": False,
            "future_cockpit_tab": "Security & Privacy Gate",
        },
    }


def make_complete_request(action: str = "accept") -> dict:
    return {
        "request_id": "REQ-SEC-WIRE-001",
        "created_at": "2026-07-10T00:00:00+00:00",
        "source": "manual_operator_entry",
        "counterparty": {"name": "Example Client", "platform": "Manual Review", "verified": True},
        "requested_action": action,
        "work_description": {
            "summary": "Client requests a governed local dashboard plan.",
            "success_outcome": "A complete scoped dashboard concept and handoff checklist.",
        },
        "deliverables": [{"deliverable_id": "DEL-001", "title": "Dashboard implementation plan"}],
        "acceptance_criteria": ["Scope is visible.", "No deployment occurs without separate approval."],
        "terms": {
            "compensation": "CAD 250 fixed scope draft",
            "contract_obligations": "operator reviews before accepting",
        },
        "timeline": {"requested_deadline": "2026-07-20T00:00:00+00:00"},
        "constraints": ["no credential use"],
        "attachments": [],
        "communication_history": [],
        "operator_review_required": True,
        "external_action_performed": False,
    }


def test_security_privacy_wiring_blocks_incomplete_counterparty_request() -> None:
    request = make_complete_request()
    request["timeline"]["requested_deadline"] = "not agreed yet"

    receipt = build_security_privacy_wiring_receipt(Path("."), make_policy(), request)

    assert receipt["decision_state"] == "blocked"
    assert "counterparty_request_not_ready" in receipt["blocked_reason"]
    assert "counterparty_request_intake" in receipt["disabled_controls"]
    assert receipt["external_action_performed"] is False


def test_security_privacy_wiring_builds_ready_receipt_for_complete_external_action() -> None:
    receipt = build_security_privacy_wiring_receipt(Path("."), make_policy(), make_complete_request())

    assert receipt["decision_state"] == "ready_for_operator_review_high_risk"
    assert receipt["proceed_enabled"] is True
    assert "counterparty_request_intake" in receipt["enabled_controls"]
    assert "approval_gated_procedure_packet" in receipt["enabled_controls"]
    assert receipt["external_action_performed"] is False


def test_security_privacy_wiring_requires_observer_authority() -> None:
    request = make_complete_request("observer_access")
    request["observer_access_requested"] = True
    request["redaction_review"] = {"status": "passed"}

    receipt = build_security_privacy_wiring_receipt(Path("."), make_policy(), request)

    assert receipt["decision_state"] == "blocked"
    assert receipt["blocked_reason"] == "observer_authority_verification_missing"
    assert "observer_authority_verification" in receipt["disabled_controls"]


def test_security_privacy_wiring_blocks_secret_markers() -> None:
    request = make_complete_request()
    request["notes"] = "accidentally pasted api_key here"

    receipt = build_security_privacy_wiring_receipt(Path("."), make_policy(), request)

    assert receipt["decision_state"] == "blocked"
    assert "redaction_privacy_review_failed" in receipt["blocked_reason"]


def test_security_privacy_wiring_cli_writes_receipt(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    policy_path = tmp_path / "policy.json"
    request_path.write_text(json.dumps(make_complete_request()), encoding="utf-8")
    policy_path.write_text(json.dumps(make_policy()), encoding="utf-8")

    result = run_security_privacy_wiring(Path("."), request_path=request_path, policy_path=policy_path, artifact_root=tmp_path / "artifacts")

    assert result["external_action_performed"] is False
    assert (Path(".") / result["receipt_path"]).exists() or Path(result["receipt_path"]).exists()
    assert result["receipt"]["proceed_enabled"] is True
