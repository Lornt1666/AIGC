from __future__ import annotations

import json
from pathlib import Path

from src.core.communication_observer_access import CommunicationObserverAccessError, build_observer_access_packet, load_policy, run_observer_access_packet


def make_policy() -> dict:
    return {
        "policy_id": "TEST-COMM",
        "operator_contact_email": "JustLornt95@gmail.com",
        "mode": "prepare_invite_and_visibility_scope_only",
        "channels": [],
        "observer_access_defaults": {
            "read_only": True,
            "counterparty_specific": True,
            "project_specific": True,
            "time_limited": True,
            "operator_can_revoke": True,
            "redacted_by_default": True,
            "show_only_selected_artifacts": True,
            "show_progress_status": True,
            "show_deliverables": True,
            "show_acceptance_criteria": True,
            "show_audit_receipts": True,
            "hide_secrets": True,
            "hide_private_repo_internals": True,
            "hide_unrelated_clients": True,
            "hide_operator_private_notes_by_default": True,
        },
        "approval_controls": {
            "external_invite_sent_by_default": False,
            "operator_popup_required": True,
            "proceed_button_required": True,
            "counterparty_request_required": True,
            "visibility_scope_required": True,
            "privacy_review_required": True,
            "redaction_review_required": True,
            "audit_receipt_required": True,
        },
    }


def test_observer_access_packet_is_read_only_and_not_sent() -> None:
    packet = build_observer_access_packet(
        make_policy(),
        {
            "name": "Example Client",
            "organization": "Example Org",
            "email": "client@example.com",
            "platform": "manual",
            "request_summary": "Build a local dashboard.",
        },
        "PROJECT-001",
        [{"item": "status", "description": "Approved status view"}],
    )

    assert packet["operator_contact_email"] == "JustLornt95@gmail.com"
    assert packet["observer_access"]["read_only"] is True
    assert packet["privacy_boundary"]["hide_secrets"] is True
    assert packet["approval_required"] is True
    assert packet["external_invite_sent"] is False


def test_observer_access_requires_counterparty_description() -> None:
    try:
        build_observer_access_packet(make_policy(), {"name": "Client"}, "PROJECT-001", [{"item": "status"}])
    except CommunicationObserverAccessError as exc:
        assert "request_summary" in str(exc)
    else:
        raise AssertionError("Missing counterparty request summary should be rejected.")


def test_observer_access_cli_artifacts_from_example(tmp_path: Path) -> None:
    policy_path = tmp_path / "communication_observer_access.json"
    request_path = tmp_path / "counterparty_request_example.json"
    policy_path.write_text(json.dumps(make_policy()), encoding="utf-8")
    request_path.write_text(json.dumps({
        "request_id": "REQ-001",
        "counterparty": {"name": "Client", "organization": "Org", "email": "client@example.com"},
        "source": {"platform": "manual"},
        "work_description": "Prepare a proposal packet.",
    }), encoding="utf-8")

    result = run_observer_access_packet(tmp_path, policy_path, request_path)

    assert result["external_invite_sent"] is False
    assert (tmp_path / result["packet_path"]).exists()
    assert (tmp_path / result["report_path"]).exists()
