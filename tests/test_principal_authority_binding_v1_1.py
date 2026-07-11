from __future__ import annotations

import copy
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "core" / "identity" / "principal_authority_binding.py"
SPEC = importlib.util.spec_from_file_location("principal_authority_binding", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

Kernel = MODULE.PrincipalAuthorityBindingKernel
NOW = datetime(2026, 7, 11, 19, 0, tzinfo=timezone.utc)
FIXTURE = ROOT / "governance" / "identity" / "local_identity_simulation.json"


def bundle() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def evaluate(value: dict):
    return Kernel().evaluate(
        request=value["request"],
        principals=value["principals"],
        memberships=value["memberships"],
        sessions=value["sessions"],
        policies=value["policies"],
        approvals=value.get("approvals", []),
        revocations=value.get("revocations", []),
        now=NOW,
    )


def assert_denied(value: dict, reason: str) -> None:
    result = evaluate(value)
    assert not result.passed
    assert result.result == "deny"
    assert reason in result.reason_codes
    assert result.receipt["data_accessed"] is False
    assert result.receipt["state_changed"] is False
    assert result.receipt["external_action_performed"] is False


def test_valid_subject_bound_request_permits() -> None:
    result = evaluate(bundle())
    assert result.passed
    assert result.result == "permit"
    assert result.receipt["principal_id"] == "principal-a"
    assert result.receipt["membership_id"] == "membership-a"
    assert result.receipt["policy_revision"] == "policy-v1"


def test_actor_cannot_change_request_and_resource_tenant_together() -> None:
    value = bundle()
    value["request"]["tenant_id"] = "tenant-b"
    value["request"]["resource"]["tenant_id"] = "tenant-b"
    assert_denied(value, "TENANT_MEMBERSHIP_MISMATCH")


def test_project_must_come_from_membership() -> None:
    value = bundle()
    value["request"]["project_id"] = "project-b"
    value["request"]["resource"]["project_id"] = "project-b"
    value["sessions"][0]["active_project_id"] = "project-b"
    assert_denied(value, "PROJECT_MEMBERSHIP_MISSING")


def test_session_principal_substitution_denies() -> None:
    value = bundle()
    value["sessions"][0]["principal_id"] = "principal-b"
    assert_denied(value, "SESSION_PRINCIPAL_MISMATCH")


def test_policy_subject_substitution_denies() -> None:
    value = bundle()
    value["policies"][0]["subject_principal_ids"] = ["principal-b"]
    assert_denied(value, "POLICY_SUBJECT_MISMATCH")


def test_policy_revision_mismatch_denies() -> None:
    value = bundle()
    value["request"]["policy_revision"] = "policy-v2"
    assert_denied(value, "POLICY_REVISION_MISMATCH")


def test_missing_purpose_denies() -> None:
    value = bundle()
    value["request"].pop("purpose")
    assert_denied(value, "PURPOSE_NOT_PERMITTED")


def test_malformed_assurance_denies_without_raising() -> None:
    value = bundle()
    value["request"]["assurance"]["aal"] = "not-a-number"
    assert_denied(value, "ASSURANCE_INVALID")


def test_non_object_resource_denies_without_raising() -> None:
    value = bundle()
    value["request"]["resource"] = "resource-a"
    assert_denied(value, "RESOURCE_INVALID")


def test_principal_revocation_cannot_be_bypassed_by_request_omission() -> None:
    value = bundle()
    value["revocations"] = [{"target_type": "principal", "target_id": "principal-a", "status": "active"}]
    assert_denied(value, "PRINCIPAL_REVOKED")


def test_membership_revocation_denies() -> None:
    value = bundle()
    value["revocations"] = [{"target_type": "membership", "target_id": "membership-a", "status": "active"}]
    assert_denied(value, "MEMBERSHIP_REVOKED")


def test_session_revocation_denies() -> None:
    value = bundle()
    value["revocations"] = [{"target_type": "session", "target_id": "session-a", "status": "active"}]
    assert_denied(value, "SESSION_REVOKED")


def test_approval_revision_and_digest_are_bound() -> None:
    value = bundle()
    value["policies"][0]["required_approval_class"] = "independent_human_review"
    value["request"]["approval_id"] = "approval-a"
    value["approvals"] = [{
        "approval_id": "approval-a",
        "actor_id": "reviewer-b",
        "approval_class": "independent_human_review",
        "revision": "wrong-revision",
        "request_digest": "wrong-digest",
        "status": "active",
        "expires_at": "2027-07-11T00:00:00Z"
    }]
    result = evaluate(value)
    assert "APPROVAL_REVISION_MISMATCH" in result.reason_codes
    assert "APPROVAL_REQUEST_DIGEST_MISMATCH" in result.reason_codes


def test_self_approval_denies() -> None:
    value = bundle()
    value["policies"][0]["required_approval_class"] = "independent_human_review"
    value["request"]["approval_id"] = "approval-a"
    digest = Kernel()._request_digest(value["request"])
    value["approvals"] = [{
        "approval_id": "approval-a",
        "actor_id": "principal-a",
        "approval_class": "independent_human_review",
        "revision": value["request"]["revision"],
        "request_digest": digest,
        "status": "active",
        "expires_at": "2027-07-11T00:00:00Z"
    }]
    assert_denied(value, "SELF_APPROVAL_NOT_INDEPENDENT")
