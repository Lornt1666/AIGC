from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


REQUIRED_APIS = {
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "identitytoolkit.googleapis.com",
    "secretmanager.googleapis.com",
}

REQUIRED_PLAN_ACTIONS = {
    "READ_PROJECT_METADATA",
    "VALIDATE_REQUIRED_APIS",
    "VALIDATE_EXISTING_RESOURCES",
    "GENERATE_TERRAFORM_PLAN",
    "CALCULATE_TARGET_DIGEST",
    "CALCULATE_PLAN_DIGEST",
}


def canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_procurement_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if pack.get("artifact_kind") != "SUBMISSION":
        reasons.append("TEMPLATE_NOT_SUBMISSION")
    project = pack.get("project", {})
    if not project.get("project_id") or not project.get("project_number"):
        reasons.append("PROJECT_UNRESOLVED")
    if not REQUIRED_APIS.issubset(set(project.get("enabled_api_service_names", []))):
        reasons.append("REQUIRED_APIS_UNVERIFIED")
    if project.get("billing_enabled_attestation") is not True:
        reasons.append("BILLING_UNVERIFIED")
    if project.get("identity_platform_enabled_attestation") is not True:
        reasons.append("IDENTITY_PLATFORM_UNVERIFIED")

    wif = pack.get("workload_identity", {})
    for key in (
        "pool_resource_name",
        "provider_resource_name",
        "plan_service_account_reference",
        "apply_service_account_reference",
        "runtime_service_account_reference",
        "attribute_mapping_fingerprint",
        "attribute_condition_fingerprint",
    ):
        if not wif.get(key):
            reasons.append(f"{key.upper()}_UNRESOLVED")
    if wif.get("github_repository_id") != 1287333065:
        reasons.append("GITHUB_REPOSITORY_ID_MISMATCH")
    if wif.get("github_repository_owner_id") != 236225491:
        reasons.append("GITHUB_OWNER_ID_MISMATCH")
    if wif.get("allowed_repository") != "Lornt1666/AIGC":
        reasons.append("GITHUB_REPOSITORY_MISMATCH")
    if wif.get("allowed_ref") != "refs/heads/main":
        reasons.append("GITHUB_REF_NOT_MAIN")
    if wif.get("user_managed_keys_present") is not False:
        reasons.append("USER_MANAGED_KEYS_PRESENT")

    provider = pack.get("identity_provider", {})
    for key in (
        "google_oauth_web_client_id",
        "google_oauth_web_client_secret_reference",
        "oauth_consent_configuration_reference",
        "authorized_domain",
        "authorized_origin",
        "authorized_redirect_uri",
    ):
        if not provider.get(key):
            reasons.append(f"{key.upper()}_UNRESOLVED")

    secrets = pack.get("secrets", {})
    for key in ("session_pepper_secret_reference", "oauth_client_secret_reference"):
        value = secrets.get(key)
        if not value or value.endswith("/latest"):
            reasons.append(f"{key.upper()}_UNRESOLVED_OR_MUTABLE")

    state = pack.get("state_backend", {})
    for key in ("remote_state_reference", "rollback_version_reference"):
        if not state.get(key):
            reasons.append(f"{key.upper()}_UNRESOLVED")
    for key in (
        "bucket_exists",
        "uniform_bucket_level_access",
        "public_access_prevention",
        "object_versioning_enabled",
        "retention_policy_documented",
        "state_locking_verified",
    ):
        if state.get(key) is not True:
            reasons.append(f"{key.upper()}_UNVERIFIED")

    subject = pack.get("test_subject", {})
    if not subject.get("reference"):
        reasons.append("TEST_SUBJECT_UNRESOLVED")
    if subject.get("production_identity") is not False or subject.get("email_committed") is not False:
        reasons.append("TEST_SUBJECT_BOUNDARY_VIOLATION")
    if pack.get("unresolved_items"):
        reasons.append("UNRESOLVED_ITEMS_REMAIN")
    for key in (
        "raw_secret_values_present",
        "automatic_apply_allowed",
        "authorization_receipt_issued",
        "provider_action_performed",
        "terraform_apply_performed",
        "external_action_performed",
    ):
        if pack.get(key) is not False:
            reasons.append(f"{key.upper()}_MUST_BE_FALSE")

    return {
        "pack_digest": canonical_digest(pack),
        "ready_for_operator_review": not reasons,
        "reason_codes": sorted(set(reasons)),
        "plan_authorization_effective": False,
        "apply_authorization_effective": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "external_action_performed": False,
    }


def evaluate_plan_authorization(
    receipt: Mapping[str, Any],
    *,
    exact_revision: str,
    procurement_pack_digest: str,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    now = evaluated_at or datetime.now(timezone.utc)
    reasons: list[str] = []
    issued = _parse_time(receipt.get("issued_at"))
    expires = _parse_time(receipt.get("expires_at"))
    if receipt.get("decision") != "APPROVED":
        reasons.append("DECISION_NOT_APPROVED")
    if receipt.get("exact_revision") != exact_revision:
        reasons.append("REVISION_MISMATCH")
    if receipt.get("procurement_pack_digest") != procurement_pack_digest:
        reasons.append("PACK_DIGEST_MISMATCH")
    if not issued or not expires or expires <= issued or expires - issued > timedelta(hours=4):
        reasons.append("INVALID_AUTHORIZATION_WINDOW")
    elif now < issued or now >= expires:
        reasons.append("AUTHORIZATION_NOT_CURRENT")
    if not REQUIRED_PLAN_ACTIONS.issubset(set(receipt.get("allowed_actions", []))):
        reasons.append("PLAN_SCOPE_INCOMPLETE")
    if receipt.get("mutation_authorized") is not False or receipt.get("terraform_apply_authorized") is not False:
        reasons.append("MUTATION_SCOPE_PRESENT")
    return {
        "effective": not reasons,
        "reason_codes": sorted(set(reasons)),
        "provider_action_performed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }


def evaluate_apply_authorization(
    receipt: Mapping[str, Any],
    *,
    exact_revision: str,
    procurement_pack_digest: str,
    plan_artifact_digest: str,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    now = evaluated_at or datetime.now(timezone.utc)
    reasons: list[str] = []
    issued = _parse_time(receipt.get("issued_at"))
    expires = _parse_time(receipt.get("expires_at"))
    if receipt.get("decision") != "APPROVED":
        reasons.append("DECISION_NOT_APPROVED")
    if receipt.get("exact_revision") != exact_revision:
        reasons.append("REVISION_MISMATCH")
    if receipt.get("procurement_pack_digest") != procurement_pack_digest:
        reasons.append("PACK_DIGEST_MISMATCH")
    if receipt.get("plan_artifact_digest") != plan_artifact_digest:
        reasons.append("PLAN_DIGEST_MISMATCH")
    if not issued or not expires or expires <= issued or expires - issued > timedelta(hours=1):
        reasons.append("INVALID_AUTHORIZATION_WINDOW")
    elif now < issued or now >= expires:
        reasons.append("AUTHORIZATION_NOT_CURRENT")
    for key in (
        "resource_manifest_digest",
        "iam_delta_digest",
        "origin_redirect_digest",
        "secret_reference_digest",
        "rollback_instructions_digest",
    ):
        if not receipt.get(key):
            reasons.append(f"{key.upper()}_MISSING")
    return {
        "effective": not reasons,
        "reason_codes": sorted(set(reasons)),
        "provider_action_performed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
