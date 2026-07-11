from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "core" / "identity" / "authorization_kernel.py"
SPEC = importlib.util.spec_from_file_location("authorization_kernel", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

IdentityAuthorizationKernel = MODULE.IdentityAuthorizationKernel
NOW = datetime(2026, 7, 11, 18, 0, tzinfo=timezone.utc)


def request() -> dict:
    return {
        "decision_id": "AUTHZ-001",
        "revision": "abcdef123456",
        "actor_reference": {
            "actor_id": "user-1",
            "actor_type": "human",
            "display_name": "Test User",
            "authority_source": "synthetic-test",
            "tenant_id": "tenant-a",
        },
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "revocation_id": "grant-1",
        "session": {
            "session_id": "session-1",
            "expires_at": "2026-07-11T19:00:00Z",
            "revoked": False,
        },
        "action": "read",
        "scopes": ["project:read"],
        "assurance_level": 2,
        "resource": {
            "resource_id": "resource-1",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "sensitivity": "internal",
        },
        "evidence_ids": ["EVID-001"],
    }


def policy() -> dict:
    return {
        "policy_id": "POLICY-001",
        "allowed_actions": ["read"],
        "granted_scopes": ["project:read"],
        "minimum_assurance_level": 2,
        "permitted_sensitivity": ["internal"],
        "revoked_ids": [],
        "human_approval_required": False,
    }


def test_valid_request_permits() -> None:
    result = IdentityAuthorizationKernel().evaluate(request=request(), policy=policy(), now=NOW)
    assert result.passed
    assert result.result == "permit"
    assert result.receipt["payload"]["result"] == "permit"


def test_cross_tenant_request_denies() -> None:
    value = request()
    value["resource"]["tenant_id"] = "tenant-b"
    result = IdentityAuthorizationKernel().evaluate(request=value, policy=policy(), now=NOW)
    assert not result.passed
    assert result.result == "deny"
    assert "TENANT_ISOLATION_VIOLATION" in result.reason_codes


def test_expired_session_denies() -> None:
    value = request()
    value["session"]["expires_at"] = "2026-07-11T17:00:00Z"
    result = IdentityAuthorizationKernel().evaluate(request=value, policy=policy(), now=NOW)
    assert not result.passed
    assert "SESSION_EXPIRED" in result.reason_codes


def test_revoked_authority_denies() -> None:
    value = policy()
    value["revoked_ids"] = ["grant-1"]
    result = IdentityAuthorizationKernel().evaluate(request=request(), policy=value, now=NOW)
    assert not result.passed
    assert "AUTHORITY_REVOKED" in result.reason_codes


def test_missing_required_approval_denies() -> None:
    value = policy()
    value["human_approval_required"] = True
    result = IdentityAuthorizationKernel().evaluate(request=request(), policy=value, now=NOW)
    assert not result.passed
    assert "MISSING_REQUIRED_APPROVAL" in result.reason_codes


def test_self_approval_cannot_satisfy_independence() -> None:
    req = request()
    req["approval_reference"] = {
        "approval_id": "APPROVAL-001",
        "actor_id": "user-1",
        "approval_class": "independent_human_review",
        "revision": "abcdef123456",
        "status": "active",
        "expires_at": None,
    }
    value = policy()
    value["human_approval_required"] = True
    result = IdentityAuthorizationKernel().evaluate(request=req, policy=value, now=NOW)
    assert not result.passed
    assert "SELF_APPROVAL_NOT_INDEPENDENT" in result.reason_codes
