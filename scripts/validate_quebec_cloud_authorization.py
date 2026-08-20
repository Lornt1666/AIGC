from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal

try:
    from scripts.verify_quebec_resource_locations import (
        RegionVerificationError,
        verify as verify_resource_manifest,
    )
except ImportError:  # pragma: no cover - direct script fallback
    from verify_quebec_resource_locations import (
        RegionVerificationError,
        verify as verify_resource_manifest,
    )

Gate = Literal["plan", "ci", "staging"]
REGION = "northamerica-northeast1"
SCHEMA = "aigc.quebec-cloud-authorization.v1"
PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
PROJECT_NUMBER = re.compile(r"^[1-9][0-9]{5,20}$")
BILLING = re.compile(r"^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$")
SHA = re.compile(r"^[a-f0-9]{40}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
SERVICE_ACCOUNT = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$"
)
SECRET_REF = re.compile(
    r"^projects/(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])/"
    r"locations/northamerica-northeast1/secrets/[A-Za-z0-9_-]{1,255}/"
    r"versions/[1-9][0-9]*$"
)
REQUIRED_REVIEWS = (
    "cloud_run_montreal",
    "cloud_sql_montreal",
    "cloud_storage_montreal",
    "artifact_registry_montreal",
    "regional_secret_manager_montreal",
    "cloud_kms_montreal",
    "cloud_logging_montreal",
    "cloud_build_montreal",
    "gemini_model_montreal",
    "gemini_ml_processing_commitment_reviewed",
    "regional_endpoints_reviewed",
    "global_control_plane_metadata_reviewed",
    "legacy_github_credentials_reviewed_and_revoked_or_proven_inactive",
    "iam_least_privilege_reviewed",
    "no_service_account_keys_reviewed",
    "network_egress_reviewed",
    "backup_location_reviewed",
    "privacy_impact_assessment_completed",
    "cross_border_assessment_completed",
    "retention_and_deletion_reviewed",
    "incident_and_recovery_reviewed",
    "pricing_quote_reviewed",
)
REQUIRED_SECRETS = (
    "runtime_control_dsn",
    "operator_token",
    "operator_binding_key",
    "runtime_admin_token",
    "runtime_admin_binding_key",
    "judge_token",
    "judge_binding_key",
)
FALSE_AUTHORITIES = (
    "production_activation_authorized",
    "public_access_authorized",
    "live_model_call_authorized",
    "judge_publication_authorized",
    "gmail_send_authorized",
    "external_business_action_authorized",
    "financial_action_authorized",
    "cross_region_replication_authorized",
    "service_account_key_creation_authorized",
)


class AuthorizationError(RuntimeError):
    pass


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _mapping(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise AuthorizationError(f"{name} must be an object")
    return value


def _text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise AuthorizationError(f"{name} is required")
    return value.strip()


def _time(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise AuthorizationError(f"{name} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorizationError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise AuthorizationError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate(
    payload: dict[str, Any],
    *,
    gate: Gate,
    now: datetime | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA:
        raise AuthorizationError("unsupported authorization schema")
    fixed = {
        "environment": "STAGING",
        "provider": "google_cloud",
        "repository": "Lornt1666/AIGC",
        "billing_account_currency": "CAD",
        "region": REGION,
        "region_name": "Montréal, Québec, Canada",
        "data_classification": "SANITIZED_NON_PERSONAL",
        "codex_cloud_region_verified_canada": False,
        "local_laptop_required_for_runtime": False,
        "single_physical_server_dependency": False,
    }
    for name, expected in fixed.items():
        if payload.get(name) != expected:
            raise AuthorizationError(f"{name} must equal {expected!r}")

    authority = _mapping(payload, "authority")
    for name in FALSE_AUTHORITIES:
        if authority.get(name) is not False:
            raise AuthorizationError(f"authority.{name} must remain false")

    costs = _mapping(payload, "costs")
    if (
        costs.get("currency") != "CAD"
        or costs.get("budget_is_hard_cap") is not False
    ):
        raise AuthorizationError(
            "costs must use CAD and state that the budget is not a hard cap"
        )
    ceiling = costs.get("maximum_monthly_ceiling")
    if (
        isinstance(ceiling, bool)
        or not isinstance(ceiling, (int, float))
        or not 0 < ceiling <= 200
    ):
        raise AuthorizationError(
            "maximum monthly ceiling must be greater than zero and no more than CAD 200"
        )

    if gate == "plan":
        if authority.get("resource_creation_authorized") is not False:
            raise AuthorizationError("plan gate cannot authorize resource creation")
        if authority.get("staging_deployment_authorized") is not False:
            raise AuthorizationError("plan gate cannot authorize deployment")
        return _summary(payload, gate)

    project_id = _text(payload, "project_id")
    if not PROJECT.fullmatch(project_id):
        raise AuthorizationError("project_id is invalid")
    if not PROJECT_NUMBER.fullmatch(_text(payload, "project_number")):
        raise AuthorizationError("project_number is invalid")
    if not BILLING.fullmatch(_text(payload, "billing_account_id")):
        raise AuthorizationError("billing_account_id is invalid")
    if payload.get("billing_account_currency") != costs.get("currency"):
        raise AuthorizationError(
            "billing-account currency must match the authorized budget currency"
        )
    if not SHA.fullmatch(_text(payload, "release_sha")):
        raise AuthorizationError("release_sha is invalid")
    if not SHA.fullmatch(_text(payload, "release_tree_sha")):
        raise AuthorizationError("release_tree_sha is invalid")
    manifest_digest = _text(payload, "resource_manifest_sha256")
    if not SHA256.fullmatch(manifest_digest):
        raise AuthorizationError("resource_manifest_sha256 is invalid")
    if manifest is not None:
        if canonical_sha256(manifest) != manifest_digest:
            raise AuthorizationError(
                "resource_manifest_sha256 does not match the supplied manifest"
            )
        try:
            verify_resource_manifest(manifest)
        except RegionVerificationError as exc:
            raise AuthorizationError(
                "resource manifest failed the Québec customer-content and control-plane classification gate"
            ) from exc

    if gate == "ci":
        if authority.get("resource_creation_authorized") is not False:
            raise AuthorizationError("ci gate cannot authorize resource creation")
        if authority.get("staging_deployment_authorized") is not False:
            raise AuthorizationError("ci gate cannot authorize deployment")
        return _summary(payload, gate)

    if payload.get("task_type") != "canadian_staging_execution":
        raise AuthorizationError(
            "staging gate requires canadian_staging_execution"
        )
    if manifest is None:
        raise AuthorizationError(
            "staging gate requires the exact resource manifest"
        )
    estimated_monthly = costs.get("estimated_monthly")
    if (
        isinstance(estimated_monthly, bool)
        or not isinstance(estimated_monthly, (int, float))
        or estimated_monthly <= 0
    ):
        raise AuthorizationError(
            "staging gate requires a reviewed monthly cost estimate"
        )
    if estimated_monthly > ceiling:
        raise AuthorizationError(
            "estimated monthly cost exceeds the authorized ceiling"
        )

    reviews = _mapping(payload, "reviews")
    missing_reviews = [
        name for name in REQUIRED_REVIEWS if reviews.get(name) is not True
    ]
    if missing_reviews:
        raise AuthorizationError(
            "required reviews are incomplete: " + ", ".join(missing_reviews)
        )

    accounts = _mapping(payload, "service_accounts")
    expected_account_names = {
        "deployer",
        "cloud_build",
        "operator",
        "judge",
        "security_review",
    }
    if set(accounts) != expected_account_names:
        raise AuthorizationError("service account inventory is incomplete")
    values = []
    for name, value in accounts.items():
        if not isinstance(value, str) or not SERVICE_ACCOUNT.fullmatch(value):
            raise AuthorizationError(f"service_accounts.{name} is invalid")
        if not value.endswith(f"@{project_id}.iam.gserviceaccount.com"):
            raise AuthorizationError(
                f"service_accounts.{name} belongs to another project"
            )
        values.append(value)
    if len(values) != len(set(values)):
        raise AuthorizationError("service accounts must be distinct")

    refs = _mapping(payload, "exact_secret_version_refs")
    if set(refs) != set(REQUIRED_SECRETS):
        raise AuthorizationError("exact secret version inventory is incomplete")
    for name, reference in refs.items():
        if not isinstance(reference, str):
            raise AuthorizationError(
                f"exact_secret_version_refs.{name} is invalid"
            )
        match = SECRET_REF.fullmatch(reference)
        if match is None or match.group("project") != project_id:
            raise AuthorizationError(
                f"exact_secret_version_refs.{name} must be a numeric Montréal version in the authorized project"
            )

    if authority.get("configuration_reviewed") is not True:
        raise AuthorizationError("configuration has not been reviewed")
    if authority.get("resource_creation_authorized") is not True:
        raise AuthorizationError("resource creation is not authorized")
    if authority.get("staging_deployment_authorized") is not True:
        raise AuthorizationError("staging deployment is not authorized")
    authorized_by = _text(authority, "authorized_by")
    reference_now = now or datetime.now(timezone.utc)
    authorized_at = _time(
        authority.get("authorized_at"),
        "authority.authorized_at",
    )
    expires = _time(authority.get("expires_at"), "authority.expires_at")
    if authorized_at > reference_now:
        raise AuthorizationError("authorization timestamp is in the future")
    if expires <= authorized_at:
        raise AuthorizationError(
            "authorization expiry must follow authorization time"
        )
    if expires <= reference_now:
        raise AuthorizationError("authorization is expired")
    required_phrase = (
        "AUTHORIZE AIGC QUEBEC STAGING "
        f"PROJECT {project_id} REGION {REGION} RELEASE {payload['release_sha']} "
        f"RESOURCE-DIGEST {payload['resource_manifest_sha256']} "
        f"MONTHLY-CEILING-CAD {_amount(ceiling)} NO-PUBLIC-TRAFFIC "
        "NO-LIVE-MODEL-CALL EXPIRES " + authority["expires_at"]
    )
    if authority.get("approval_phrase") != required_phrase:
        raise AuthorizationError(
            "approval phrase does not bind the exact project, release, resources, ceiling and expiry"
        )
    result = _summary(payload, gate)
    result["authorized_by"] = authorized_by
    return result


def _amount(value: int | float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.2f}"


def _summary(payload: dict[str, Any], gate: Gate) -> dict[str, Any]:
    return {
        "valid": True,
        "gate": gate,
        "project_id": payload.get("project_id"),
        "billing_account_currency": payload.get("billing_account_currency"),
        "region": REGION,
        "release_sha": payload.get("release_sha"),
        "release_tree_sha": payload.get("release_tree_sha"),
        "contract_sha256": canonical_sha256(payload),
        "resource_creation_performed": False,
        "deployment_performed": False,
        "live_model_call_performed": False,
        "public_traffic_enabled": False,
        "production_activation_authorized": False,
        "strict_quebec_data_residency_verified": False,
        "codex_cloud_region_verified_canada": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument(
        "--gate",
        choices=("plan", "ci", "staging"),
        default="plan",
    )
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.contract.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AuthorizationError("contract must be a JSON object")
    manifest = None
    if args.manifest is not None:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise AuthorizationError("manifest must be a JSON object")
    print(
        json.dumps(
            validate(payload, gate=args.gate, manifest=manifest),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuthorizationError as exc:
        raise SystemExit(f"Québec cloud authorization blocked: {exc}") from exc
