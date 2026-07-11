from __future__ import annotations

import json
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

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
MATRIX = ROOT / "governance" / "identity" / "principal_authority_binding_mutation_matrix.json"
SCHEMA_ROOT = ROOT / "governance" / "schemas" / "identity"


def bundle() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def refresh_digest(value: dict) -> None:
    value["request"]["request_digest"] = Kernel.request_digest(value["request"])


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


def require_approval(value: dict) -> dict:
    value["policies"][0]["approval_rules"] = [{
        "approval_class": "independent_human_review",
        "required": True,
        "independent": True,
    }]
    value["request"]["approval_reference_ids"] = ["approval-a"]
    refresh_digest(value)
    approval = {
        "approval_id": "approval-a",
        "actor_id": "reviewer-b",
        "approval_class": "independent_human_review",
        "revision": value["request"]["exact_revision"],
        "request_digest": value["request"]["request_digest"],
        "status": "ACTIVE",
        "expires_at": "2027-07-11T00:00:00Z",
    }
    value["approvals"] = [approval]
    return approval


def mutate(case_id: str, value: dict) -> None:
    request = value["request"]
    principal = value["principals"][0]
    membership = value["memberships"][0]
    session = value["sessions"][0]
    policy = value["policies"][0]

    if case_id == "M01":
        request["principal_id"] = "principal-b"
        refresh_digest(value)
    elif case_id == "M02":
        request["tenant_id"] = "tenant-b"
        request["resource"]["tenant_id"] = "tenant-b"
        refresh_digest(value)
    elif case_id == "M03":
        value["memberships"] = []
    elif case_id == "M04":
        session["principal_id"] = "principal-b"
    elif case_id == "M05":
        session["active_project_id"] = "project-b"
    elif case_id == "M06":
        policy["subject_selectors"] = {"principal_ids": ["principal-b"], "role_ids": []}
    elif case_id == "M07":
        policy["tenant_id"] = "tenant-b"
    elif case_id == "M08":
        policy["policy_revision"] = "f" * 40
    elif case_id == "M09":
        require_approval(value)["revision"] = "f" * 40
    elif case_id in {"M10", "M11"}:
        value["revocations"] = [{"target_type": "principal", "target_id": "principal-a", "status": "ACTIVE"}]
    elif case_id == "M12":
        request["principal_id"] = "principal-unknown"
        refresh_digest(value)
    elif case_id == "M13":
        principal["principal_status"] = "SUSPENDED"
    elif case_id == "M14":
        membership["status"] = "EXPIRED"
    elif case_id == "M15":
        membership["project_ids"] = []
    elif case_id == "M16":
        session["membership_id"] = "membership-b"
    elif case_id == "M17":
        session["tenant_id"] = "tenant-b"
    elif case_id == "M18":
        session["session_state"] = "STEP_UP_REQUIRED"
    elif case_id == "M19":
        session["idle_expires_at"] = "2026-07-11T18:59:59Z"
    elif case_id == "M20":
        session["absolute_expires_at"] = "2026-07-11T18:59:59Z"
    elif case_id == "M21":
        policy.pop("subject_selectors")
    elif case_id == "M22":
        request.pop("purpose")
        refresh_digest(value)
    elif case_id == "M23":
        request["purpose"] = "unpermitted-purpose"
        refresh_digest(value)
    elif case_id == "M24":
        request["context"].pop("jurisdiction")
        refresh_digest(value)
    elif case_id == "M25":
        policy["minimum_assurance"]["ial"] = "IAL1"
    elif case_id == "M26":
        policy["minimum_assurance"]["aal"] = "AAL1"
    elif case_id == "M27":
        policy["minimum_assurance"]["fal"] = "FAL1"
    elif case_id == "M28":
        policy["minimum_assurance"]["evidence_maturity"] = "EA1_SCHEMA_VALID"
    elif case_id == "M29":
        require_approval(value)["request_digest"] = "0" * 64
    elif case_id == "M30":
        approval = require_approval(value)
        approval["approval_class"] = "ai_advisory_review"
    elif case_id == "M31":
        require_approval(value)["actor_id"] = "principal-a"
    elif case_id == "M32":
        value["revocations"] = [{"target_type": "membership", "target_id": "membership-a", "status": "ACTIVE"}]
    elif case_id == "M33":
        value["revocations"] = [{"target_type": "session", "target_id": "session-a", "status": "ACTIVE"}]
    elif case_id == "M34":
        value["revocations"] = [{"target_type": "policy", "target_id": "policy-a", "status": "ACTIVE"}]
    elif case_id == "M35":
        request["assurance"]["aal"] = "not-a-valid-assurance"
        refresh_digest(value)
    elif case_id == "M36":
        request["resource"] = "resource-a"
        refresh_digest(value)
    else:
        raise AssertionError(f"Unknown matrix case {case_id}")


def test_valid_subject_bound_request_permits_with_schema_valid_receipt() -> None:
    value = bundle()
    result = evaluate(value)
    assert result.passed
    assert result.result == "PERMIT"
    assert result.receipt["principal_id"] == "principal-a"
    assert result.receipt["policy_id"] == "policy-a"
    schema = json.loads((SCHEMA_ROOT / "authorization_decision_receipt.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result.receipt))
    assert not errors


def test_fixture_records_conform_to_all_six_procured_contracts() -> None:
    value = bundle()
    validator = MODULE.IdentityContractValidator()
    assert validator.is_valid("request", value["request"])
    assert all(validator.is_valid("principal", item) for item in value["principals"])
    assert all(validator.is_valid("membership", item) for item in value["memberships"])
    assert all(validator.is_valid("session", item) for item in value["sessions"])
    assert all(validator.is_valid("policy", item) for item in value["policies"])


MATRIX_EXPECTATIONS = {
    item["id"]: (item["expected_state"], item["reason_code"])
    for item in json.loads(MATRIX.read_text(encoding="utf-8"))["mutations"]
}


@pytest.mark.parametrize("case_id", sorted(MATRIX_EXPECTATIONS))
def test_subject_binding_mutation_matrix(case_id: str) -> None:
    value = bundle()
    mutate(case_id, value)
    result = evaluate(value)
    expected_state, reason_code = MATRIX_EXPECTATIONS[case_id]
    assert result.result == expected_state
    assert reason_code in result.reason_codes
    assert result.receipt["data_accessed"] is False
    assert result.receipt["state_changed"] is False
    assert result.receipt["external_action_performed"] is False


def test_request_digest_is_computed_and_caller_mismatch_denies() -> None:
    value = bundle()
    value["request"]["request_digest"] = "0" * 64
    result = evaluate(value)
    assert result.result == "DENY"
    assert "REQUEST_DIGEST_MISMATCH" in result.reason_codes
    assert result.receipt["request_digest"] == Kernel.request_digest(value["request"])


def test_request_cannot_select_an_unbound_policy() -> None:
    value = bundle()
    value["request"]["policy_id"] = "policy-attacker-selected"
    refresh_digest(value)
    result = evaluate(value)
    assert result.result == "DENY"
    assert "MALFORMED_REQUEST" in result.reason_codes


def test_authoritative_principal_assurance_caps_request_claim() -> None:
    value = bundle()
    value["request"]["assurance"]["ial"] = "IAL3"
    value["policies"][0]["minimum_assurance"]["ial"] = "IAL1"
    refresh_digest(value)
    result = evaluate(value)
    assert result.result == "DENY"
    assert "INSUFFICIENT_IAL" in result.reason_codes


def test_production_mode_requires_security_privacy_adapter() -> None:
    value = bundle()
    value["request"]["context"]["operator_mode"] = "production"
    refresh_digest(value)
    result = evaluate(value)
    assert result.result == "REVIEW_REQUIRED"
    assert "SECURITY_PRIVACY_REVIEW_REQUIRED" in result.reason_codes


def test_observer_purpose_requires_observer_authority_adapter() -> None:
    value = bundle()
    value["request"]["purpose"] = "observer_access"
    refresh_digest(value)
    result = evaluate(value)
    assert result.result == "REVIEW_REQUIRED"
    assert "OBSERVER_AUTHORITY_REQUIRED" in result.reason_codes


def test_required_approval_missing_is_review_required() -> None:
    value = bundle()
    value["policies"][0]["approval_rules"] = [{
        "approval_class": "independent_human_review",
        "required": True,
        "independent": True,
    }]
    refresh_digest(value)
    result = evaluate(value)
    assert result.result == "REVIEW_REQUIRED"
    assert "APPROVAL_MISSING" in result.reason_codes
    assert result.receipt["approval_obligations"]


def test_malformed_request_returns_deterministic_receipt() -> None:
    result = Kernel().evaluate(
        request={},
        principals=[],
        memberships=[],
        sessions=[],
        policies=[],
        now=NOW,
    )
    assert result.result == "DENY"
    assert "MALFORMED_REQUEST" in result.reason_codes
    assert result.receipt["exact_revision"] == "0" * 40
