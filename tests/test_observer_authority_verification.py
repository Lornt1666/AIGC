from __future__ import annotations

from pathlib import Path

from src.core.contract_validator import validate_artifact
from src.core.observer_authority_verification import (
    ObserverAuthorityVerificationError,
    build_authority_verification,
    load_policy,
    run_observer_authority_verification,
    validate_policy,
)


def make_policy() -> dict:
    return {
        "policy_id": "TEST-OBSERVER-AUTHORITY",
        "mode": "verify_before_observer_access",
        "required_checks": {
            "identity_proof_required": True,
            "organization_or_platform_link_required": True,
            "role_authority_required": True,
            "project_scope_required": True,
            "counterparty_request_link_required": True,
            "operator_approval_required": True,
            "redaction_review_required": True,
            "expiry_required": True,
            "revocation_required": True,
            "audit_receipt_required": True,
        },
        "hard_blocks": [
            "whole_account_access",
            "backend_access",
            "raw_chatlog_access_by_default",
            "unrelated_project_access",
            "silent_sharing",
            "unverified_identity",
            "unverified_role_authority",
            "expired_authority",
            "unrevocable_access",
        ],
    }


def make_observer() -> dict:
    return {
        "name": "Example Employer",
        "organization": "Example Org",
        "email": "employer@example.com",
        "observer_type": "employer_or_client",
    }


def make_authority_basis() -> dict:
    return {
        "identity_verified": True,
        "organization_or_platform_link_verified": True,
        "role_authority_verified": True,
        "counterparty_request_linked": True,
        "documented_basis": "Example platform record.",
        "basis_reference": "REQ-001",
    }


def make_scope() -> dict:
    return {
        "chatlog_artifact_id": "AIGC-CHATLOG-001",
        "project_id": "REQ-001",
        "allowed_sections": ["approved_status", "approved_deliverables"],
        "expires_at": "2099-01-01T00:00:00Z",
        "revocable": True,
        "read_only": True,
        "whole_account_access": False,
        "backend_access": False,
        "raw_chatlog_access": False,
    }


def test_authority_verified_packet_can_reach_operator_review() -> None:
    packet = build_authority_verification(
        make_policy(),
        observer=make_observer(),
        authority_basis=make_authority_basis(),
        scope=make_scope(),
    )

    assert packet["decision"]["state"] == "ready_for_operator_review"
    assert packet["decision"]["proceed_enabled"] is True
    assert packet["scope"]["backend_access"] is False
    assert packet["audit"]["silent_sharing_allowed"] is False
    validate_artifact("observer_authority_verification", packet)


def test_missing_identity_is_insufficient_authority() -> None:
    authority = make_authority_basis()
    authority["identity_verified"] = False
    packet = build_authority_verification(
        make_policy(),
        observer=make_observer(),
        authority_basis=authority,
        scope=make_scope(),
    )

    assert packet["decision"]["state"] == "insufficient_authority"
    assert packet["decision"]["proceed_enabled"] is False


def test_backend_or_whole_account_request_is_blocked() -> None:
    scope = make_scope()
    scope["backend_access"] = True
    packet = build_authority_verification(
        make_policy(),
        observer=make_observer(),
        authority_basis=make_authority_basis(),
        scope=scope,
    )

    assert packet["decision"]["state"] == "blocked_scope_overreach"
    assert packet["decision"]["proceed_enabled"] is False


def test_policy_requires_core_checks() -> None:
    policy = make_policy()
    policy["required_checks"]["role_authority_required"] = False
    try:
        validate_policy(policy)
    except ObserverAuthorityVerificationError as exc:
        assert "role_authority_required" in str(exc)
    else:
        raise AssertionError("Unsafe policy should fail validation")


def test_authority_verification_cli_artifacts(tmp_path: Path) -> None:
    policy_path = tmp_path / "observer_authority_verification.json"
    policy_path.write_text(__import__("json").dumps(make_policy()), encoding="utf-8")

    result = run_observer_authority_verification(tmp_path, policy_path=policy_path)

    assert result["external_invite_sent"] is False
    assert (tmp_path / result["packet_path"]).exists()
    assert (tmp_path / result["report_path"]).exists()
