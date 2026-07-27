from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Literal


class StagingAuthorizationError(RuntimeError):
    """Raised when a staging authorization is incomplete or mismatched."""


Gate = Literal["configuration", "deploy", "live", "judge"]
CANADIAN_INFRA_REGIONS = {
    "northamerica-northeast1",
    "northamerica-northeast2",
}
# The current Google model endpoint table lists Montréal for regional Gemini
# endpoints and does not list Toronto. Keep this narrower than the general
# infrastructure region set and re-review it against the official table before
# changing it.
CANADIAN_GEMINI_VERTEX_LOCATIONS = {
    "northamerica-northeast1",
}
_SHA = re.compile(r"^[a-f0-9]{40}$")
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_RESOURCE = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_DATABASE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,199}$")
_SERVICE_ACCOUNT = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$"
)
_SECRET_REF = re.compile(
    r"^projects/(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])/"
    r"secrets/[A-Za-z0-9_-]{1,255}/versions/[1-9][0-9]*$"
)
_IAM_ROLE = re.compile(r"^roles/[A-Za-z0-9_.]+$")
_JUDGE_RUNTIME_ALLOWED_ROLES = {
    "roles/storage.objectViewer",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
}


def validate_authorization(
    payload: dict[str, Any],
    *,
    gate: Gate,
    now: datetime | None = None,
) -> dict[str, Any]:
    if payload.get("schema_version") != (
        "aigc.gemini-staging-authorization.v1"
    ):
        raise StagingAuthorizationError(
            "Unsupported staging authorization schema"
        )
    if payload.get("environment") != "staging":
        raise StagingAuthorizationError("Authorization must target staging")
    if payload.get("business_identity") != "RegenExcalibur":
        raise StagingAuthorizationError(
            "Authorization must retain the RegenExcalibur business identity"
        )
    if payload.get("repository") != "Lornt1666/AIGC":
        raise StagingAuthorizationError(
            "Authorization must target Lornt1666/AIGC"
        )

    release_revision = _required_text(payload, "release_revision")
    if not _SHA.fullmatch(release_revision):
        raise StagingAuthorizationError(
            "release_revision must be an exact lowercase 40-character Git SHA"
        )
    gemini_model = _required_text(payload, "gemini_model")
    if not _MODEL.fullmatch(gemini_model):
        raise StagingAuthorizationError("gemini_model is invalid")

    cloud = _mapping(payload, "cloud")
    project_id = _required_text(cloud, "project_id")
    if not _PROJECT.fullmatch(project_id):
        raise StagingAuthorizationError("cloud.project_id is invalid")
    primary_region = _required_text(cloud, "primary_region")
    vertex_location = _required_text(cloud, "vertex_location")
    if primary_region not in CANADIAN_INFRA_REGIONS:
        raise StagingAuthorizationError(
            "Cloud Run staging region must be an approved Canadian region"
        )
    if vertex_location not in CANADIAN_GEMINI_VERTEX_LOCATIONS:
        raise StagingAuthorizationError(
            "Vertex location must be a currently supported Canadian regional "
            "Gemini endpoint"
        )
    if cloud.get("vertex_model_location_table") != (
        "https://docs.cloud.google.com/"
        "gemini-enterprise-agent-platform/resources/locations"
    ):
        raise StagingAuthorizationError(
            "cloud.vertex_model_location_table must identify the reviewed "
            "official Google model endpoint table"
        )
    if cloud.get("vertex_model_availability_reviewed") is not True:
        raise StagingAuthorizationError(
            "The exact Gemini model and Vertex location have not been "
            "explicitly reviewed against the official endpoint table"
        )
    resolved_references: list[str] = []
    for name in (
        "artifact_registry_repository",
        "operator_service_name",
        "judge_service_name",
    ):
        if not _RESOURCE.fullmatch(_required_text(cloud, name)):
            raise StagingAuthorizationError(f"cloud.{name} is invalid")
    if cloud["operator_service_name"] == cloud["judge_service_name"]:
        raise StagingAuthorizationError(
            "Operator and judge must use separate Cloud Run services"
        )
    if not _DATABASE.fullmatch(_required_text(cloud, "database_name")):
        raise StagingAuthorizationError("cloud.database_name is invalid")
    for name in ("evidence_bucket", "judge_receipt_bucket"):
        bucket = _required_text(cloud, name)
        if (
            not _BUCKET.fullmatch(bucket)
            or ".." in bucket
            or ".-" in bucket
            or "-." in bucket
        ):
            raise StagingAuthorizationError(f"cloud.{name} is invalid")
    _required_text(cloud, "cloud_sql_instance_connection_name")
    connection_name = str(cloud["cloud_sql_instance_connection_name"])
    if not connection_name.startswith(f"{project_id}:"):
        raise StagingAuthorizationError(
            "Cloud SQL connection name must belong to the authorized project"
        )

    accounts = _mapping(payload, "service_accounts")
    account_values: dict[str, str] = {}
    for name in (
        "deployer",
        "cloud_build",
        "operator_runtime",
        "judge_runtime",
    ):
        value = _required_text(accounts, name)
        if not _SERVICE_ACCOUNT.fullmatch(value):
            raise StagingAuthorizationError(
                f"service_accounts.{name} is not a service-account email"
            )
        if not value.endswith(f"@{project_id}.iam.gserviceaccount.com"):
            raise StagingAuthorizationError(
                f"service_accounts.{name} belongs to another project"
            )
        account_values[name] = value
    if account_values["operator_runtime"] == account_values["judge_runtime"]:
        raise StagingAuthorizationError(
            "Operator and judge must use separate service accounts"
        )

    secret_refs = _mapping(
        payload,
        "secret_manager_exact_version_refs",
    )
    for name in (
        "runtime_control_dsn",
        "operator_token",
        "operator_binding_key",
        "runtime_admin_token",
        "runtime_admin_binding_key",
        "judge_token",
        "judge_binding_key",
    ):
        reference = _required_text(secret_refs, name)
        match = _SECRET_REF.fullmatch(reference)
        if match is None or match.group("project") != project_id:
            raise StagingAuthorizationError(
                f"Secret reference {name} must use an exact numeric version "
                "in the authorized project"
            )
        resolved_references.append(reference)
    if len(resolved_references) != len(set(resolved_references)):
        raise StagingAuthorizationError(
            "Every runtime role and binding must use a distinct exact secret "
            "version reference"
        )

    iam = _mapping(payload, "iam_review")
    for name in (
        "operator_runtime_roles",
        "judge_runtime_roles",
        "deployer_roles",
        "cloud_build_roles",
    ):
        roles = iam.get(name)
        if (
            not isinstance(roles, list)
            or not roles
            or any(not isinstance(role, str) or not role for role in roles)
        ):
            raise StagingAuthorizationError(
                f"iam_review.{name} must record the reviewed roles"
            )
        if any(not _IAM_ROLE.fullmatch(role) for role in roles):
            raise StagingAuthorizationError(
                f"iam_review.{name} contains an invalid IAM role"
            )
        if any(
            role in {"roles/owner", "roles/editor", "roles/viewer"}
            or role.lower().endswith("admin")
            for role in roles
        ):
            raise StagingAuthorizationError(
                f"iam_review.{name} contains a primitive or administrative "
                "role"
            )
    if not set(iam["judge_runtime_roles"]).issubset(
        _JUDGE_RUNTIME_ALLOWED_ROLES
    ):
        raise StagingAuthorizationError(
            "Judge runtime roles exceed the read-only observability and "
            "sanitized-object allowlist"
        )
    _require_true_flags(
        iam,
        (
            "least_privilege_reviewed",
            "no_primitive_or_admin_roles",
            "secret_access_is_exact_secret_scoped",
            "storage_access_is_bucket_or_prefix_scoped",
            "cloud_run_invoker_bindings_reviewed",
            "judge_has_no_vertex_permission",
            "judge_has_no_control_store_write_permission",
            "judge_has_sanitized_prefix_read_only",
        ),
        prefix="iam_review",
    )

    evidence = _mapping(payload, "evidence_controls")
    _require_true_flags(
        evidence,
        (
            "uniform_bucket_level_access",
            "public_access_prevention",
            "versioning_enabled",
            "retention_policy_reviewed",
            "create_only_runtime_permission_reviewed",
            "exact_readiness_sentinel_reviewed",
            "gcs_generation_receipts_required",
        ),
        prefix="evidence_controls",
    )

    spending = _mapping(payload, "spending_control")
    if spending.get("currency") != "CAD":
        raise StagingAuthorizationError("Spending ceiling must be recorded in CAD")
    ceiling = spending.get("authorized_monthly_ceiling")
    if (
        isinstance(ceiling, bool)
        or not isinstance(ceiling, (int, float))
        or ceiling <= 0
        or ceiling > 200
    ):
        raise StagingAuthorizationError(
            "Authorized monthly ceiling must be greater than zero and no more "
            "than the accepted CAD 200 production ceiling"
        )
    _require_true_flags(
        spending,
        (
            "billing_budget_configured",
            "vertex_quota_reviewed",
            "application_limits_reviewed",
            "acknowledges_budget_is_not_a_hard_cap",
        ),
        prefix="spending_control",
    )

    authorization = _mapping(payload, "authorization")
    if not authorization.get("configuration_reviewed"):
        raise StagingAuthorizationError(
            "Staging configuration has not been explicitly reviewed"
        )
    if gate in {"deploy", "live", "judge"}:
        _require_true_flags(
            authorization,
            (
                "resource_creation_authorized",
                "staging_deployment_authorized",
            ),
            prefix="authorization",
        )
    if gate in {"live", "judge"} and not authorization.get(
        "one_live_gemini_call_authorized"
    ):
        raise StagingAuthorizationError(
            "One controlled live Gemini call is not authorized"
        )
    if gate == "judge" and not authorization.get(
        "judge_receipt_publication_authorized"
    ):
        raise StagingAuthorizationError(
            "Judge receipt publication is not authorized"
        )

    _required_text(authorization, "authorized_by")
    _parse_datetime(authorization.get("authorized_at"), "authorized_at")
    expires_at = _parse_datetime(
        authorization.get("expires_at"),
        "expires_at",
    )
    reference_now = now or datetime.now(timezone.utc)
    if expires_at <= reference_now:
        raise StagingAuthorizationError("Staging authorization is expired")

    expected_phrase = (
        "AUTHORIZE AIGC GEMINI STAGING "
        f"{project_id} {primary_region} {release_revision} "
        f"CEILING CAD {_format_amount(ceiling)}"
    )
    if authorization.get("approval_phrase") != expected_phrase:
        raise StagingAuthorizationError(
            "Approval phrase does not bind the exact project, region, release "
            "SHA and spending ceiling"
        )

    return {
        "valid": True,
        "gate": gate,
        "project_id": project_id,
        "region": primary_region,
        "vertex_location": vertex_location,
        "release_revision": release_revision,
        "gemini_model": gemini_model,
        "authorized_monthly_ceiling_cad": ceiling,
        "operator_service_name": cloud["operator_service_name"],
        "judge_service_name": cloud["judge_service_name"],
        "secret_values_read": False,
        "external_action_performed": False,
    }


def _mapping(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise StagingAuthorizationError(f"{name} must be an object")
    return value


def _required_text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise StagingAuthorizationError(f"{name} is required")
    return value.strip()


def _require_true_flags(
    payload: dict[str, Any],
    names: tuple[str, ...],
    *,
    prefix: str,
) -> None:
    missing = [name for name in names if payload.get(name) is not True]
    if missing:
        raise StagingAuthorizationError(
            f"{prefix} must explicitly confirm: " + ", ".join(missing)
        )


def _parse_datetime(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise StagingAuthorizationError(f"authorization.{name} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StagingAuthorizationError(
            f"authorization.{name} must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StagingAuthorizationError(
            f"authorization.{name} must include a timezone"
        )
    return parsed.astimezone(timezone.utc)


def _format_amount(value: int | float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.2f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("authorization", type=Path)
    parser.add_argument(
        "--gate",
        choices=("configuration", "deploy", "live", "judge"),
        default="configuration",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.authorization.read_text(encoding="utf-8"))
    summary = validate_authorization(payload, gate=args.gate)
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
