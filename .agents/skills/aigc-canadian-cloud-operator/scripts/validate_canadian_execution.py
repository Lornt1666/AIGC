from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


SCHEMA_VERSION = "aigc.canadian-execution-contract.v1"
REPOSITORY = "Lornt1666/AIGC"
PRIMARY_REGION = "northamerica-northeast1"
APPROVED_REGIONS = {
    "northamerica-northeast1": "Montréal, Quebec, Canada",
    "northamerica-northeast2": "Toronto, Ontario, Canada",
}
TASK_TYPES = {
    "repository_only",
    "canadian_staging_plan",
    "canadian_staging_execution",
}
ENVIRONMENTS = {"PLAN", "CI", "STAGING"}
CODEX_INPUT_CLASS = "SANITIZED_NON_PERSONAL"
RESIDENCY_CLAIM = "canadian_external_execution_and_storage_plane_only"
SHA40 = re.compile(r"^[a-f0-9]{40}$")
FORBIDDEN_VALUE_KEYS = {
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "private_key",
    "service_account_key",
    "credential_value",
    "secret_value",
    "authorization_header",
    "cookie",
}
ALWAYS_FALSE_AUTHORITIES = (
    "production_activation_authorized",
    "live_model_call_authorized",
    "external_business_action_authorized",
    "gmail_send_authorized",
    "github_runtime_mutation_authorized",
    "merge_authorized",
    "judge_publication_authorized",
    "financial_action_authorized",
)


class ContractError(ValueError):
    """Raised when a Canadian execution contract fails closed."""


def _mapping(payload: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = payload.get(name)
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _boolean(payload: Mapping[str, Any], name: str, *, prefix: str) -> bool:
    value = payload.get(name)
    if not isinstance(value, bool):
        raise ContractError(f"{prefix}.{name} must be boolean")
    return value


def _text(payload: Mapping[str, Any], name: str, *, prefix: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise ContractError(f"{prefix}.{name} must be text")
    return value.strip()


def _timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"authorization.{name} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"authorization.{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"authorization.{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reject_secret_value_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_VALUE_KEYS:
                raise ContractError(
                    f"raw secret-bearing field is forbidden at {path}.{key}"
                )
            _reject_secret_value_fields(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_value_fields(item, path=f"{path}[{index}]")


def validate_contract(
    payload: Mapping[str, Any],
    *,
    gate: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if gate not in {"plan", "ci", "staging"}:
        raise ContractError("gate must be plan, ci, or staging")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("unsupported contract schema")
    if payload.get("repository") != REPOSITORY:
        raise ContractError("contract targets another repository")
    _reject_secret_value_fields(payload)

    contract_id = _text(payload, "contract_id", prefix="contract")
    if not contract_id or len(contract_id) > 160:
        raise ContractError("contract_id must contain 1..160 characters")
    task_type = _text(payload, "task_type", prefix="contract")
    if task_type not in TASK_TYPES:
        raise ContractError("task_type is unsupported")
    environment = _text(payload, "environment", prefix="contract")
    if environment not in ENVIRONMENTS:
        raise ContractError("environment is unsupported")

    branch = _text(payload, "requested_branch", prefix="contract")
    requested_sha = _text(payload, "requested_sha", prefix="contract")
    tree_sha = _text(payload, "requested_tree_sha", prefix="contract")
    if gate in {"ci", "staging"}:
        if not branch:
            raise ContractError("requested_branch is required for this gate")
        if not SHA40.fullmatch(requested_sha):
            raise ContractError("requested_sha must be an exact Git SHA")
        if not SHA40.fullmatch(tree_sha):
            raise ContractError("requested_tree_sha must be an exact Git tree SHA")

    codex = _mapping(payload, "codex")
    if _boolean(codex, "local_laptop_required", prefix="codex") is not False:
        raise ContractError("this skill requires a laptop-independent Codex path")
    if _boolean(codex, "cloud_region_verified_canada", prefix="codex") is not False:
        raise ContractError(
            "Codex cloud must not be represented as Canadian without independent evidence"
        )
    if _text(codex, "input_classification", prefix="codex") != CODEX_INPUT_CLASS:
        raise ContractError("Codex input must remain sanitized and non-personal")
    if _boolean(codex, "raw_secrets_permitted", prefix="codex") is not False:
        raise ContractError("raw secrets are prohibited in Codex inputs")

    execution = _mapping(payload, "canadian_execution_plane")
    execution_required = _boolean(execution, "required", prefix="canadian_execution_plane")
    if _text(execution, "country", prefix="canadian_execution_plane") != "CA":
        raise ContractError("the external execution plane must be Canadian")
    primary_region = _text(
        execution,
        "primary_region",
        prefix="canadian_execution_plane",
    )
    if primary_region not in APPROVED_REGIONS:
        raise ContractError("primary_region is not an approved Canadian region")
    fallback = execution.get("fallback_region")
    fallback_approved = _boolean(
        execution,
        "fallback_explicitly_approved",
        prefix="canadian_execution_plane",
    )
    if fallback is not None:
        if not isinstance(fallback, str) or fallback not in APPROVED_REGIONS:
            raise ContractError("fallback_region is not an approved Canadian region")
        if fallback == primary_region:
            raise ContractError("fallback_region must differ from primary_region")
        if fallback_approved is not True:
            raise ContractError("fallback_region requires explicit approval")
    elif fallback_approved:
        raise ContractError("fallback approval cannot exist without a fallback region")
    if _boolean(
        execution,
        "silent_failover_allowed",
        prefix="canadian_execution_plane",
    ) is not False:
        raise ContractError("silent failover is prohibited")

    privacy = _mapping(payload, "privacy")
    runtime_personal = _boolean(
        privacy,
        "canadian_runtime_contains_personal_information",
        prefix="privacy",
    )
    runtime_sensitive = _boolean(
        privacy,
        "canadian_runtime_contains_sensitive_information",
        prefix="privacy",
    )
    pia_required = _boolean(
        privacy,
        "privacy_impact_assessment_required",
        prefix="privacy",
    )
    pia_completed = _boolean(
        privacy,
        "privacy_impact_assessment_completed",
        prefix="privacy",
    )
    if runtime_sensitive and not runtime_personal:
        raise ContractError(
            "sensitive information must also be classified as personal information"
        )
    if (runtime_personal or runtime_sensitive) and not pia_required:
        raise ContractError("personal or sensitive runtime data requires a PIA")
    if pia_completed and not pia_required:
        raise ContractError("PIA completion cannot be true when no PIA is required")
    if _boolean(
        privacy,
        "cross_border_assessment_required",
        prefix="privacy",
    ) is not True:
        raise ContractError(
            "cross-border assessment is required while Codex region is unverified"
        )
    if _boolean(
        privacy,
        "human_oversight_required",
        prefix="privacy",
    ) is not True:
        raise ContractError("human oversight is mandatory")

    spending = _mapping(payload, "spending")
    if _text(spending, "currency", prefix="spending") != "CAD":
        raise ContractError("spending ceiling must be recorded in CAD")

    authorization = _mapping(payload, "authorization")
    if _boolean(
        authorization,
        "human_approval_required",
        prefix="authorization",
    ) is not True:
        raise ContractError("human approval is mandatory")
    for name in ALWAYS_FALSE_AUTHORITIES:
        if _boolean(authorization, name, prefix="authorization") is not False:
            raise ContractError(f"authorization.{name} must remain false")

    ready_for_gate = gate == "plan"
    if gate == "ci":
        if environment != "CI":
            raise ContractError("CI gate requires environment=CI")
        if _boolean(
            authorization,
            "staging_execution_authorized",
            prefix="authorization",
        ):
            raise ContractError("CI validation must not authorize staging execution")
        if _boolean(
            authorization,
            "deployment_authorized",
            prefix="authorization",
        ):
            raise ContractError("CI validation must not authorize deployment")
        ready_for_gate = True

    if gate == "staging":
        if task_type != "canadian_staging_execution":
            raise ContractError(
                "staging gate requires task_type=canadian_staging_execution"
            )
        if environment != "STAGING":
            raise ContractError("staging gate requires environment=STAGING")
        if execution_required is not True:
            raise ContractError("staging requires the Canadian execution plane")
        if primary_region != PRIMARY_REGION and fallback_approved is not True:
            raise ContractError(
                "non-Montréal staging requires explicit fallback approval"
            )
        for name in (
            "service_location_availability_reviewed",
            "region_lock_reviewed",
            "resource_inventory_complete",
            "logging_region_reviewed",
            "backup_region_reviewed",
            "evidence_region_reviewed",
            "secret_manager_exact_versions_reviewed",
        ):
            if _boolean(execution, name, prefix="canadian_execution_plane") is not True:
                raise ContractError(
                    f"canadian_execution_plane.{name} must be reviewed"
                )
        for name in (
            "cross_border_assessment_completed",
            "purpose_limitation_recorded",
            "data_minimization_reviewed",
            "retention_schedule_recorded",
        ):
            if _boolean(privacy, name, prefix="privacy") is not True:
                raise ContractError(f"privacy.{name} must be complete")
        if pia_required and not pia_completed:
            raise ContractError("required PIA must be complete before staging")
        ceiling = spending.get("authorized_ceiling")
        if (
            isinstance(ceiling, bool)
            or not isinstance(ceiling, (int, float))
            or ceiling <= 0
            or ceiling > 200
        ):
            raise ContractError(
                "authorized_ceiling must be greater than zero and no more than CAD 200"
            )
        if _boolean(
            spending,
            "budget_and_quota_reviewed",
            prefix="spending",
        ) is not True:
            raise ContractError("budget and quota controls must be reviewed")
        for name in (
            "human_approval_recorded",
            "staging_execution_authorized",
            "deployment_authorized",
        ):
            if _boolean(authorization, name, prefix="authorization") is not True:
                raise ContractError(f"authorization.{name} must be true")
        authorized_by = _text(
            authorization,
            "authorized_by",
            prefix="authorization",
        )
        if not authorized_by:
            raise ContractError("authorization.authorized_by is required")
        authorized_at = _timestamp(
            authorization.get("authorized_at"),
            "authorized_at",
        )
        expires_at = _timestamp(
            authorization.get("expires_at"),
            "expires_at",
        )
        reference_now = now or datetime.now(timezone.utc)
        if expires_at <= reference_now:
            raise ContractError("staging authorization is expired")
        if authorized_at >= expires_at:
            raise ContractError("authorization expiry must follow authorization time")
        ready_for_gate = True

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": contract_id,
        "gate": gate,
        "valid": True,
        "ready_for_gate": ready_for_gate,
        "repository": REPOSITORY,
        "task_type": task_type,
        "environment": environment,
        "requested_branch": branch or None,
        "requested_sha": requested_sha or None,
        "requested_tree_sha": tree_sha or None,
        "codex_local_laptop_required": False,
        "codex_cloud_region_verified_canada": False,
        "codex_input_classification": CODEX_INPUT_CLASS,
        "canadian_execution_plane_required": execution_required,
        "approved_region": primary_region,
        "approved_region_label": APPROVED_REGIONS[primary_region],
        "data_residency_claim": RESIDENCY_CLAIM,
        "runtime_personal_information": runtime_personal,
        "runtime_sensitive_information": runtime_sensitive,
        "production_activation_authorized": False,
        "live_model_call_authorized": False,
        "external_business_action_authorized": False,
        "gmail_send_authorized": False,
        "github_runtime_mutation_authorized": False,
        "merge_authorized": False,
        "judge_publication_authorized": False,
        "financial_action_authorized": False,
        "contract_sha256": _canonical_sha256(payload),
    }


def _load(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("contract is not readable JSON") from exc
    if not isinstance(payload, Mapping):
        raise ContractError("contract must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a default-deny Canadian AIGC execution contract."
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--gate", choices=("plan", "ci", "staging"), required=True)
    args = parser.parse_args()
    try:
        result = validate_contract(_load(args.contract), gate=args.gate)
    except ContractError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
