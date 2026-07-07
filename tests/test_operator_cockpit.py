from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.operator_cockpit import (
    accept_phrase_matches_required,
    build_accept_command,
    build_enterprise_run_commands,
    render_review_markdown,
    summarize_authorization_packet,
)


def make_packet(expires_at: str) -> dict:
    return {
        "authorization_id": "AUTH-1",
        "action_id": "AIGC-ACT-1",
        "proposal_id": "PROPOSAL-1",
        "opportunity_id": "OPPORTUNITY-1",
        "recipient": "Example Recipient",
        "platform": "Example Platform",
        "expires_at": expires_at,
        "proposed_external_action": "Send proposal/message to Example Recipient.",
        "classification": {
            "risk_class": "medium",
            "safety_status": "caution",
        },
        "checks": {
            "ai_disclosure_status": "required",
        },
        "artifact": {
            "artifact_type": "proposal",
            "artifact_hash": "hash-1",
            "artifact_preview": "Visible review text.",
        },
        "approval": {
            "required_phrase": "I accept AIGC-ACT-1.",
            "denial_phrase": "I deny AIGC-ACT-1.",
            "revision_phrase_template": "Revise action AIGC-ACT-1: [revision instructions]",
        },
        "phase6_status": {
            "external_action_performed": False,
        },
        "decision": "pending",
    }


def test_authorization_summary_is_transparent_and_not_external() -> None:
    expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    review = summarize_authorization_packet(make_packet(expires_at))

    assert review.action_id == "AIGC-ACT-1"
    assert review.expired is False
    assert review.external_action_performed is False

    markdown = render_review_markdown(review)
    assert "What Accept Does" in markdown
    assert "What Accept Does Not Do" in markdown
    assert "does not submit" in markdown


def test_authorization_expiry_is_block_visible() -> None:
    expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    review = summarize_authorization_packet(make_packet(expires_at))

    assert review.expired is True


def test_accept_command_uses_exact_phrase_and_root() -> None:
    root = Path("/tmp/aigc")
    expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    review = summarize_authorization_packet(make_packet(expires_at))
    typed_phrase = "I accept AIGC-ACT-1."
    command = build_accept_command(root, review, typed_phrase)

    assert str(root / "src" / "aigc.py") in command
    assert "--root" in command
    assert "approve" in command
    assert "--phrase" in command
    assert "I accept AIGC-ACT-1." in command


def test_accept_command_rejects_mismatched_typed_phrase() -> None:
    root = Path("/tmp/aigc")
    expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    review = summarize_authorization_packet(make_packet(expires_at))

    assert accept_phrase_matches_required(review, "wrong phrase") is False
    try:
        build_accept_command(root, review, "wrong phrase")
    except ValueError as exc:
        assert "Typed acceptance phrase" in str(exc)
    else:
        raise AssertionError("Mismatched typed phrase should not build an approval command.")


def test_enterprise_run_sequence_keeps_validation_and_governance_gates() -> None:
    commands = build_enterprise_run_commands(Path("/tmp/aigc"))
    labels = [command.label for command in commands]

    assert labels[0] == "Runtime preflight"
    assert "Human approval packet generation" in labels
    assert "Compliance and legal review" in labels
    assert "Ascended work-order governor" in labels
    assert labels[-1] == "Contract validation"


def test_launchers_do_not_install_dependencies_by_default() -> None:
    batch = Path("RUN_AIGC_COCKPIT.bat").read_text(encoding="utf-8")
    powershell = Path("scripts/run_operator_cockpit.ps1").read_text(encoding="utf-8")

    assert "AIGC_INSTALL_DEPENDENCIES" in batch
    assert "AIGC_INSTALL_DEPENDENCIES" in powershell
    assert "AIGC_SKIP_DEPENDENCY_INSTALL" not in batch
    assert "AIGC_SKIP_DEPENDENCY_INSTALL" not in powershell


def test_procurement_procedure_is_process_only() -> None:
    procedure = Path("docs/AIGC_PROCUREMENT_PROCEDURE.md").read_text(encoding="utf-8")

    assert "Procedure instantiated" in procedure
    assert "No purchase" in procedure
    assert "AIGC may not spend money" in procedure
    assert "exact procurement approval phrase is typed" in procedure
    assert "Do not execute procurement" in procedure
