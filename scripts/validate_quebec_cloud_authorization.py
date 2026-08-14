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
    r"locations/northamerica-northeast1/secrets/(?P<secret>[A-Za-z0-9_-]{1,255})/"
    r"versions/(?P<version>[1-9][0-9]*)$"
)
RESOURCE_PREFIX = re.compile(r"^[a-z][a-z0-9-]{2,18}$")
IMMUTABLE_CONTAINER_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[a-f0-9]{64}$"
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
REQUIRED_RESOURCES = (
    "artifact_registry_repository",
    "operator_service",
    "judge_service",
    "cloud_sql_instance",
    "database_name",
    "evidence_bucket",
    "judge_bucket",
    "receipt_bucket",
    "build_source_bucket",
    "log_bucket",
    "kms_key_ring",
)
REQUIRED_SUPPLY_CHAIN = (
    "docker_builder_image",
    "python_base_image",
    "sbom_generator_image",
)
FALSE_AUTHORITIES = (
    "production_activation_authorized",
    "public_access_authorized",
    "live_model_call_authorized",
    "judge_publication_authorized",
    "devpost_submission_authorized",
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


def authorization_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": payload.get("project_id"),
        "project_number": payload.get("project_number"),
        "region": payload.get("region"),
        "resource_prefix": payload.get("resource_prefix"),
        "resources": payload.get("resources"),
        "service_accounts": payload.get("service_accounts"),
        "exact_secret_version_refs": payload.get("exact_secret_version_refs"),
        "supply_chain": payload.get("supply_chain"),
        "ci_admission_sha256": payload.get("ci_admission_sha256"),
    }


def _verify_manifest_authorization_bindings(
    payload: dict[str, Any], manifest: dict[str, Any]
) -> str:
    for name in ("project_id", "project_number", "region"):
        if manifest.get(name) != payload.get(name):
            raise AuthorizationError(f"resource manifest {name} does not match authorization")
    if manifest.get("resource_prefix") != payload.get("resource_prefix"):
        raise AuthorizationError("resource manifest resource_prefix does not match authorization")
    bindings = _mapping(manifest, "authorization_bindings")
    for name in ("resources", "service_accounts", "exact_secret_version_refs"):
        if bindings.get(name) != payload.get(name):
            raise AuthorizationError(
                f"resource manifest authorization_bindings.{name} does not match authorization"
            )
    scope = deterministic_authorized_scope(payload)
    resources = scope["resources"]
    expected_resource_pairs = {
        ("artifact_registry", resources["artifact_registry_repository"]),
        ("cloud_sql_postgresql", resources["cloud_sql_instance"]),
        ("cloud_run_service", resources["operator_service"]),
        ("cloud_run_service", resources["judge_service"]),
        ("storage_bucket", resources["evidence_bucket"]),
        ("storage_bucket", resources["judge_bucket"]),
        ("storage_bucket", resources["receipt_bucket"]),
        ("storage_bucket", resources["build_source_bucket"]),
        ("regional_secret_manager", f"{scope['resource_prefix']}-secret-set"),
        ("kms_key_ring", resources["kms_key_ring"]),
        ("logging_bucket", resources["log_bucket"]),
    }
    resource_items = manifest.get("resources")
    if not isinstance(resource_items, list):
        raise AuthorizationError("resource manifest resources must be an array")
    observed_resource_pairs = [
        (item.get("kind"), item.get("name"))
        for item in resource_items
        if isinstance(item, dict)
    ]
    if (
        len(observed_resource_pairs) != len(expected_resource_pairs)
        or set(observed_resource_pairs) != expected_resource_pairs
    ):
        raise AuthorizationError(
            "resource manifest resources do not match the deterministic authorized inventory"
        )
    expected_control_pairs = {
        ("google_cloud_project", scope["project_id"]),
        ("iam_and_service_accounts", f"{scope['resource_prefix']}-gha"),
        ("billing_and_budget", payload.get("billing_account_id")),
        ("vpc_network", f"{scope['resource_prefix']}-vpc"),
        ("private_service_access", f"{scope['resource_prefix']}-private-services"),
    }
    control_items = manifest.get("control_plane_resources")
    if not isinstance(control_items, list):
        raise AuthorizationError(
            "resource manifest control_plane_resources must be an array"
        )
    observed_control_pairs = [
        (item.get("kind"), item.get("name"))
        for item in control_items
        if isinstance(item, dict)
    ]
    if (
        len(observed_control_pairs) != len(expected_control_pairs)
        or set(observed_control_pairs) != expected_control_pairs
    ):
        raise AuthorizationError(
            "resource manifest control plane does not match the deterministic authorized inventory"
        )
    inventory_digest = canonical_sha256(authorization_inventory(payload))
    if payload.get("authorization_inventory_sha256") != inventory_digest:
        raise AuthorizationError(
            "authorization_inventory_sha256 does not match the exact project/resource/identity/secret inventory"
        )
    return inventory_digest


def deterministic_authorized_scope(payload: dict[str, Any]) -> dict[str, Any]:
    project = _text(payload, "project_id")
    prefix = _text(payload, "resource_prefix")
    if not RESOURCE_PREFIX.fullmatch(prefix):
        raise AuthorizationError("resource_prefix is invalid")
    resources = {
        "artifact_registry_repository": f"{prefix}-runtime",
        "operator_service": f"{prefix}-operator",
        "judge_service": f"{prefix}-judge",
        "cloud_sql_instance": f"{prefix}-control",
        "database_name": "aigc_control",
        "evidence_bucket": f"{project}-{prefix}-evidence",
        "judge_bucket": f"{project}-{prefix}-judge",
        "receipt_bucket": f"{project}-{prefix}-receipts",
        "build_source_bucket": f"{project}-{prefix}-build-source",
        "log_bucket": f"{prefix}-logs",
        "kms_key_ring": f"{prefix}-keys",
    }
    service_accounts = {
        role: f"{prefix}-{suffix}@{project}.iam.gserviceaccount.com"
        for role, suffix in {
            "deployer": "deployer",
            "cloud_build": "build",
            "operator": "operator",
            "canary_gemini": "can-gem",
            "canary_openai": "can-oai",
            "canary_provisioner": "can-prov",
            "canary_binder": "can-bind",
            "canary_executor": "can-exec",
            "canary_publisher": "can-pub",
            "judge": "judge",
            "security_review": "security",
            "authority_signer": "signer",
        }.items()
    }
    secret_ids = {
        purpose: f"{prefix}-{suffix}"
        for purpose, suffix in {
            "runtime_control_dsn": "runtime-control-dsn",
            "operator_token": "operator-token",
            "operator_binding_key": "operator-binding-key",
            "runtime_admin_token": "runtime-admin-token",
            "runtime_admin_binding_key": "runtime-admin-binding-key",
            "judge_token": "judge-token",
            "judge_binding_key": "judge-binding-key",
        }.items()
    }
    return {
        "project_id": project,
        "project_number": payload.get("project_number"),
        "region": REGION,
        "resource_prefix": prefix,
        "resources": resources,
        "service_accounts": service_accounts,
        "regional_secret_ids": secret_ids,
    }


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
    prefix = _text(payload, "resource_prefix")
    if not RESOURCE_PREFIX.fullmatch(prefix):
        raise AuthorizationError("resource_prefix is invalid")
    if payload.get("billing_account_currency") != costs.get("currency"):
        raise AuthorizationError(
            "billing-account currency must match the authorized budget currency"
        )
    if not SHA.fullmatch(_text(payload, "release_sha")):
        raise AuthorizationError("release_sha is invalid")
    if not SHA.fullmatch(_text(payload, "release_tree_sha")):
        raise AuthorizationError("release_tree_sha is invalid")
    ci_admission_digest = _text(payload, "ci_admission_sha256")
    if not SHA256.fullmatch(ci_admission_digest) or ci_admission_digest == "0" * 64:
        raise AuthorizationError(
            "ci_admission_sha256 must bind a retained exact-head CI admission artifact"
        )
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

    inventory_digest = _text(payload, "authorization_inventory_sha256")
    if not SHA256.fullmatch(inventory_digest):
        raise AuthorizationError("authorization_inventory_sha256 is invalid")

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
        "canary_gemini",
        "canary_openai",
        "canary_provisioner",
        "canary_binder",
        "canary_executor",
        "canary_publisher",
        "judge",
        "security_review",
        "authority_signer",
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

    resources = _mapping(payload, "resources")
    if set(resources) != set(REQUIRED_RESOURCES):
        raise AuthorizationError("resource inventory is incomplete")
    for name, value in resources.items():
        if not isinstance(value, str) or not value.strip():
            raise AuthorizationError(f"resources.{name} is invalid")

    expected_scope = deterministic_authorized_scope(payload)
    if resources != expected_scope["resources"]:
        raise AuthorizationError(
            "resources do not match the deterministic authorized inventory"
        )
    if accounts != expected_scope["service_accounts"]:
        raise AuthorizationError(
            "service accounts do not match the deterministic authorized inventory"
        )

    supply_chain = _mapping(payload, "supply_chain")
    if set(supply_chain) != set(REQUIRED_SUPPLY_CHAIN):
        raise AuthorizationError("supply-chain image inventory is incomplete")
    for name, image in supply_chain.items():
        if not isinstance(image, str) or not IMMUTABLE_CONTAINER_IMAGE.fullmatch(image):
            raise AuthorizationError(
                f"supply_chain.{name} must be an immutable container image digest"
            )
        if image.endswith("@sha256:" + "0" * 64):
            raise AuthorizationError(
                f"supply_chain.{name} cannot use the inert placeholder digest"
            )

    refs = _mapping(payload, "exact_secret_version_refs")
    if set(refs) != set(REQUIRED_SECRETS):
        raise AuthorizationError("exact secret version inventory is incomplete")
    for name, reference in refs.items():
        if not isinstance(reference, str):
            raise AuthorizationError(
                f"exact_secret_version_refs.{name} is invalid"
            )
        match = SECRET_REF.fullmatch(reference)
        if (
            match is None
            or match.group("project") != project_id
            or match.group("secret")
            != expected_scope["regional_secret_ids"][name]
        ):
            raise AuthorizationError(
                f"exact_secret_version_refs.{name} must be a numeric Montréal version in the authorized project"
            )

    observed_inventory_digest = _verify_manifest_authorization_bindings(payload, manifest)

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
        f"INVENTORY-DIGEST {observed_inventory_digest} "
        f"MONTHLY-CEILING-CAD {_amount(ceiling)} NO-PUBLIC-TRAFFIC "
        "NO-LIVE-MODEL-CALL EXPIRES " + authority["expires_at"]
    )
    if authority.get("approval_phrase") != required_phrase:
        raise AuthorizationError(
            "approval phrase does not bind the exact project, release, resources, ceiling and expiry"
        )
    result = _summary(payload, gate)
    result["authorized_by"] = authorized_by
    result["authorized_scope"] = {
        **expected_scope,
        "exact_secret_version_refs": dict(refs),
        "supply_chain": dict(supply_chain),
        "ci_admission_sha256": ci_admission_digest,
    }
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
        "authorization_inventory_sha256": payload.get("authorization_inventory_sha256"),
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
