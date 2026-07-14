from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema

from src.core.staging_identity_procurement_readiness import (
    REQUIRED_APIS,
    canonical_digest,
    evaluate_apply_authorization,
    evaluate_plan_authorization,
    evaluate_procurement_pack,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_template_validates_and_remains_not_ready():
    pack = load("config/staging_identity_procurement_readiness_pack.json")
    schema = load("schemas/staging_identity_procurement_readiness_pack.schema.json")
    jsonschema.Draft202012Validator(schema).validate(pack)
    result = evaluate_procurement_pack(pack)
    assert result["ready_for_operator_review"] is False
    assert result["plan_authorization_effective"] is False
    assert result["apply_authorization_effective"] is False
    assert result["external_action_performed"] is False


def test_public_github_numeric_identity_is_exactly_bound():
    pack = load("config/staging_identity_procurement_readiness_pack.json")
    wif = pack["workload_identity"]
    assert wif["github_repository_id"] == 1287333065
    assert wif["github_repository_owner_id"] == 236225491
    assert wif["allowed_repository"] == "Lornt1666/AIGC"
    assert wif["allowed_ref"] == "refs/heads/main"
    assert wif["user_managed_keys_present"] is False


def test_template_cannot_claim_any_live_action():
    pack = load("config/staging_identity_procurement_readiness_pack.json")
    for key in (
        "authorization_receipt_issued",
        "provider_action_performed",
        "terraform_apply_performed",
        "external_action_performed",
        "automatic_apply_allowed",
        "raw_secret_values_present",
    ):
        assert pack[key] is False


def test_required_api_set_is_explicit():
    assert {
        "iam.googleapis.com",
        "cloudresourcemanager.googleapis.com",
        "iamcredentials.googleapis.com",
        "sts.googleapis.com",
        "identitytoolkit.googleapis.com",
        "secretmanager.googleapis.com",
    } == REQUIRED_APIS


def test_canonical_digest_is_order_independent():
    assert canonical_digest({"b": 2, "a": 1}) == canonical_digest({"a": 1, "b": 2})


def test_plan_receipt_schema_forbids_mutation():
    schema = load("schemas/staging_plan_authorization_receipt.schema.json")
    receipt = _plan_receipt()
    jsonschema.Draft202012Validator(schema).validate(receipt)
    bad = copy.deepcopy(receipt)
    bad["terraform_apply_authorized"] = True
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(bad))


def test_plan_authorization_requires_exact_binding_and_four_hour_maximum():
    receipt = _plan_receipt()
    now = datetime(2026, 7, 14, 18, 30, tzinfo=timezone.utc)
    result = evaluate_plan_authorization(
        receipt,
        exact_revision="a" * 40,
        procurement_pack_digest="b" * 64,
        evaluated_at=now,
    )
    assert result["effective"] is True
    receipt["expires_at"] = (now + timedelta(hours=5)).isoformat()
    assert evaluate_plan_authorization(
        receipt,
        exact_revision="a" * 40,
        procurement_pack_digest="b" * 64,
        evaluated_at=now,
    )["effective"] is False


def test_apply_authorization_requires_plan_digest_and_one_hour_maximum():
    receipt = _apply_receipt()
    now = datetime(2026, 7, 14, 18, 30, tzinfo=timezone.utc)
    result = evaluate_apply_authorization(
        receipt,
        exact_revision="a" * 40,
        procurement_pack_digest="b" * 64,
        plan_artifact_digest="sha256:" + "c" * 64,
        evaluated_at=now,
    )
    assert result["effective"] is True
    receipt["plan_artifact_digest"] = "sha256:" + "d" * 64
    assert evaluate_apply_authorization(
        receipt,
        exact_revision="a" * 40,
        procurement_pack_digest="b" * 64,
        plan_artifact_digest="sha256:" + "c" * 64,
        evaluated_at=now,
    )["effective"] is False


def test_apply_receipt_is_authorization_not_execution_evidence():
    schema = load("schemas/staging_apply_authorization_receipt.schema.json")
    receipt = _apply_receipt()
    jsonschema.Draft202012Validator(schema).validate(receipt)
    assert receipt["provider_action_performed"] is False
    assert receipt["terraform_apply_performed"] is False
    assert receipt["external_action_performed"] is False


def _plan_receipt():
    return {
        "contract_id": "AIGC-STAGING-PLAN-AUTHORIZATION-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "SPA-EXAMPLE-0001",
        "decision": "APPROVED",
        "exact_revision": "a" * 40,
        "procurement_pack_digest": "b" * 64,
        "issued_at": "2026-07-14T18:00:00+00:00",
        "expires_at": "2026-07-14T22:00:00+00:00",
        "project_reference": "gcp_project://aigc-staging-001",
        "allowed_actions": [
            "READ_PROJECT_METADATA",
            "VALIDATE_REQUIRED_APIS",
            "VALIDATE_EXISTING_RESOURCES",
            "GENERATE_TERRAFORM_PLAN",
            "CALCULATE_TARGET_DIGEST",
            "CALCULATE_PLAN_DIGEST",
        ],
        "single_use": True,
        "mutation_authorized": False,
        "terraform_apply_authorized": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "provider_action_performed": False,
        "external_action_performed": False,
    }


def _apply_receipt():
    return {
        "contract_id": "AIGC-STAGING-APPLY-AUTHORIZATION-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "SAA-EXAMPLE-0001",
        "decision": "APPROVED",
        "exact_revision": "a" * 40,
        "procurement_pack_digest": "b" * 64,
        "plan_artifact_digest": "sha256:" + "c" * 64,
        "issued_at": "2026-07-14T18:00:00+00:00",
        "expires_at": "2026-07-14T19:00:00+00:00",
        "project_reference": "gcp_project://aigc-staging-001",
        "resource_manifest_digest": "d" * 64,
        "iam_delta_digest": "e" * 64,
        "origin_redirect_digest": "f" * 64,
        "secret_reference_digest": "1" * 64,
        "rollback_instructions_digest": "2" * 64,
        "single_use": True,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "provider_action_performed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }
