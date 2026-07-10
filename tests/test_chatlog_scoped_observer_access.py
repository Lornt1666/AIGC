from __future__ import annotations

from pathlib import Path

from src.core.chatlog_scoped_observer_access import ChatlogScopedObserverError, build_chatlog_observer_packet, run_chatlog_observer_packet


def make_policy() -> dict:
    return {
        "policy_id": "TEST-CHATLOG",
        "mode": "prepare_specific_chatlog_observer_packet_only",
        "operator_contact_email": "JustLornt95@gmail.com",
        "default_scope_rules": {
            "specific_chatlog_required": True,
            "whole_account_access_allowed": False,
            "whole_conversation_access_allowed_by_default": False,
            "backend_access_allowed": False,
            "raw_chatgpt_link_sharing_allowed_by_default": False,
            "exported_packet_required": True,
            "redaction_required": True,
            "operator_approval_required_before_invite": True,
            "observer_read_only": True,
            "observer_time_limited": True,
            "operator_can_revoke": True,
        },
        "hidden_or_private_content_blocks": ["system_messages", "developer_messages", "secret_values"],
        "required_invite_review_fields": ["observer_identity", "chatlog_artifact_id"],
        "security_posture": {
            "least_privilege": True,
            "deny_by_default": True,
            "share_packet_not_backend": True,
            "hash_exported_packet": True,
            "audit_all_invites": True,
            "watermark_or_identifier_required": True,
            "crawler_indexing_allowed": False,
            "search_engine_discoverability_allowed": False,
        },
    }


def test_chatlog_observer_packet_is_specific_and_not_backend_access() -> None:
    packet = build_chatlog_observer_packet(
        make_policy(),
        chatlog_artifact_id="CHATLOG-001",
        chatlog_title="Scoped work log",
        observer={"name": "Employer", "organization": "Org"},
        allowed_sections=["approved_status", "approved_deliverables"],
        redaction_status="redacted_and_approved",
    )

    assert packet["specific_chatlog_scope"]["whole_account_access"] is False
    assert packet["specific_chatlog_scope"]["backend_access"] is False
    assert packet["specific_chatlog_scope"]["raw_chatgpt_link_shared"] is False
    assert packet["specific_chatlog_scope"]["exported_redacted_packet_only"] is True
    assert packet["visibility_controls"]["proceed_enabled"] is True
    assert packet["sharing_state"]["backend_hardening_claimed"] is False


def test_chatlog_observer_rejects_missing_chatlog_id() -> None:
    try:
        build_chatlog_observer_packet(
            make_policy(),
            chatlog_artifact_id="",
            chatlog_title="Missing",
            observer={"name": "Employer"},
            allowed_sections=["approved_status"],
        )
    except ChatlogScopedObserverError as exc:
        assert "chatlog_artifact_id" in str(exc)
    else:
        raise AssertionError("Missing chatlog_artifact_id must be rejected.")


def test_chatlog_observer_run_writes_packet(tmp_path: Path) -> None:
    policy_path = tmp_path / "chatlog_scoped_observer_access.json"
    policy_path.write_text(__import__("json").dumps(make_policy()), encoding="utf-8")

    result = run_chatlog_observer_packet(tmp_path, policy_path)

    assert result["invite_sent"] is False
    assert result["external_access_enabled"] is False
    assert (tmp_path / result["packet_path"]).exists()
    assert (tmp_path / result["report_path"]).exists()
