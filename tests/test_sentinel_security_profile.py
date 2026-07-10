from __future__ import annotations

import json
from pathlib import Path

from src.core.sentinel_security_profile import SentinelSecurityError, build_sentinel_report, run_sentinel_security_profile


def make_profile() -> dict:
    return {
        "profile_id": "TEST-SENTINEL",
        "mode": "defensive_privacy_preserving_repo_wide_security_profile",
        "research_basis": [{"source": "NIST CSF 2.0", "use": "governance"}],
        "layer_model": [
            {"layer_id": "aegis", "name": "Aegis", "purpose": "outer defense", "controls": ["rate_limit"]},
            {"layer_id": "core", "name": "Core", "purpose": "trusted base", "controls": ["deny_by_default"]},
        ],
        "control_families": [
            {"family": "governance", "controls": ["policy_registry", "CI_required_before_merge"]},
            {"family": "privacy", "controls": ["redacted_exports", "no_backdoor_access"]},
        ],
        "authorized_disclosure_boundary": {
            "mode": "evidence_export_with_due_process_only",
            "no_backdoor": True,
            "operator_review_required": True,
            "jurisdiction_review_required": True,
            "share_minimum_necessary": True,
            "audit_receipt_required": True,
        },
        "blocked_capabilities": [
            "offensive_exploit_generation",
            "malware_or_credential_theft",
            "backdoor_or_unrestricted_government_access",
            "silent_external_sharing",
            "raw_secret_logging",
            "raw_chatlog_share_by_default",
            "agent_self_approval",
        ],
        "repo_assignment": {
            "all_security_sensitive_outputs_require_schema": True,
            "all_external_actions_require_operator_approval": True,
            "all_counterparty_visibility_requires_redaction_review": True,
            "all_future_live_connectors_require_terms_review": True,
            "all_future_secret_access_requires_secret_broker": True,
            "all_prs_require_CI_before_merge": True,
        },
    }


def test_sentinel_report_blocks_backdoors_and_self_approval() -> None:
    report = build_sentinel_report(make_profile())

    assert report["overall_status"] == "defensive_profile_ready_for_operator_review"
    assert report["authorized_disclosure_boundary"]["no_backdoor"] is True
    assert "backdoor_or_unrestricted_government_access" in report["blocked_capabilities"]
    assert "agent_self_approval" in report["blocked_capabilities"]


def test_sentinel_profile_rejects_missing_backdoor_block() -> None:
    profile = make_profile()
    profile["blocked_capabilities"].remove("backdoor_or_unrestricted_government_access")

    try:
        build_sentinel_report(profile)
    except SentinelSecurityError as exc:
        assert "Missing required blocked capabilities" in str(exc)
    else:
        raise AssertionError("Profile missing backdoor block should be rejected.")


def test_sentinel_profile_cli_artifacts(tmp_path: Path) -> None:
    profile_path = tmp_path / "sentinel_security_profile.json"
    profile_path.write_text(json.dumps(make_profile()), encoding="utf-8")

    result = run_sentinel_security_profile(tmp_path, profile_path)

    assert result["external_action_performed"] is False
    assert (tmp_path / result["profile_path"]).exists()
    assert (tmp_path / result["report_path"]).exists()
    assert (tmp_path / result["markdown_path"]).exists()
