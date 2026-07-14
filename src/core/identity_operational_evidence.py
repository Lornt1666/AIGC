from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE_CONFIG = ROOT / "config" / "production_identity_platform_baseline.json"
DEFAULT_BASELINE_SCHEMA = ROOT / "schemas" / "production_identity_platform_baseline.schema.json"
DEFAULT_STAGING_RECEIPT_SCHEMA = ROOT / "schemas" / "identity_platform_staging_receipt.schema.json"
DEFAULT_EVALUATION_SCHEMA = ROOT / "schemas" / "identity_operational_evidence_evaluation.schema.json"
_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_PROJECT_REFERENCE = re.compile(
    r"^gcp_project://[a-z][a-z0-9-]{4,28}[a-z0-9]$"
)


class IdentityOperationalEvidenceError(ValueError):
    """Raised when identity operational evidence cannot be evaluated safely."""


@dataclass(frozen=True)
class IdentityOperationalEvidenceEvaluation:
    receipt: dict[str, Any]
    baseline: dict[str, Any]

    @property
    def staging_evidence_accepted(self) -> bool:
        return bool(self.receipt["staging_evidence_accepted"])

    @property
    def readiness_review_eligible(self) -> bool:
        return bool(self.receipt["readiness_review_eligible"])


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: object) -> datetime:
    try:
        return _utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError as exc:
        raise IdentityOperationalEvidenceError("Identity evidence time is invalid") from exc


def _strict_validate(schema_path: Path, value: Mapping[str, Any]) -> None:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityOperationalEvidenceError(
            f"Unable to load identity evidence schema: {schema_path.name}"
        ) from exc
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(dict(value)),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        messages: list[str] = []
        for error in errors[:10]:
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        raise IdentityOperationalEvidenceError(
            f"Identity evidence contract validation failed: {'; '.join(messages)}"
        )


def load_identity_platform_baseline(
    config_path: str | Path = DEFAULT_BASELINE_CONFIG,
    schema_path: str | Path = DEFAULT_BASELINE_SCHEMA,
) -> dict[str, Any]:
    try:
        value = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityOperationalEvidenceError(
            "Unable to load production identity platform baseline"
        ) from exc
    if not isinstance(value, dict):
        raise IdentityOperationalEvidenceError(
            "Production identity platform baseline must be an object"
        )
    _strict_validate(Path(schema_path), value)
    return value


def _baseline_project_reference(policy: Mapping[str, Any]) -> str | None:
    provider = dict(policy["provider"])
    project_id = provider.get("project_id")
    if project_id is None:
        return None
    return f"gcp_project://{project_id}"


def _operational_evidence_codes(
    policy: Mapping[str, Any],
    staging_receipt: Mapping[str, Any] | None,
    *,
    project_observed: bool,
) -> list[str]:
    evidence = dict(policy["operational_evidence"])
    receipt_checks = dict(staging_receipt.get("checks", {})) if staging_receipt else {}
    requirements = {
        "identity_platform_project_configured": None,
        "google_sign_in_observed": "google_sign_in",
        "jwks_rotation_observed": "public_key_rotation",
        "revocation_observed": "revocation",
        "session_rotation_observed": "session_rotation",
        "logout_observed": "logout_revocation",
        "restart_persistence_observed": "restart_persistence",
        "cross_tenant_negative_passed": "cross_tenant_denied",
        "cross_project_negative_passed": "cross_project_denied",
        "provider_outage_test_passed": "provider_outage_fail_closed",
        "redaction_review_passed": "redaction_review",
    }
    missing: list[str] = []
    for evidence_key, receipt_check in requirements.items():
        observed = evidence.get(evidence_key) is True
        if evidence_key == "identity_platform_project_configured":
            observed = observed or project_observed
        elif receipt_check is not None:
            observed = observed or receipt_checks.get(receipt_check) is True
        if not observed:
            missing.append(evidence_key.upper())
    return missing


def evaluate_identity_operational_evidence(
    *,
    policy: Mapping[str, Any],
    exact_revision: str | None,
    staging_receipt: Mapping[str, Any] | None = None,
    expected_project_reference: str | None = None,
    now: datetime | None = None,
) -> IdentityOperationalEvidenceEvaluation:
    value = dict(policy)
    _strict_validate(DEFAULT_BASELINE_SCHEMA, value)
    current = _utc(now or datetime.now(timezone.utc))

    authority = dict(value["authority"])
    sessions = dict(value["sessions"])
    baseline_project_reference = _baseline_project_reference(value)
    if expected_project_reference is not None and not _PROJECT_REFERENCE.fullmatch(
        expected_project_reference
    ):
        raise IdentityOperationalEvidenceError(
            "Expected Identity Platform project reference is malformed"
        )
    project_reference = baseline_project_reference or expected_project_reference
    revision = exact_revision if exact_revision and _HEX40.fullmatch(exact_revision) else "unbound"

    implemented_internal = (
        value.get("status")
        == "IMPLEMENTED_INTERNAL_PENDING_PROVIDER_AND_STAGING_EVIDENCE"
        and authority.get("adapter_implementation_authorized") is True
        and authority.get("offline_cryptographic_testing_authorized") is True
        and value.get("external_action_performed") is False
    )

    unresolved_configuration: list[str] = []
    if baseline_project_reference is None:
        unresolved_configuration.append("IDENTITY_PLATFORM_BASELINE_PROJECT_UNBOUND")
    if project_reference is None:
        unresolved_configuration.append("IDENTITY_PLATFORM_PROJECT_REFERENCE_MISSING")
    if "TBD_PROJECT" in str(sessions.get("pepper_reference", "")):
        unresolved_configuration.append("SESSION_PEPPER_PROJECT_UNRESOLVED")

    authority_blockers: list[str] = []
    authority_names = {
        "provider_configuration_authorized": "PROVIDER_CONFIGURATION_UNAUTHORIZED",
        "secret_access_authorized": "SECRET_ACCESS_UNAUTHORIZED",
        "user_onboarding_authorized": "USER_ONBOARDING_UNAUTHORIZED",
        "production_identity_activation_authorized": (
            "PRODUCTION_IDENTITY_ACTIVATION_UNAUTHORIZED"
        ),
    }
    for key, code in authority_names.items():
        if authority.get(key) is not True:
            authority_blockers.append(code)

    receipt_value: dict[str, Any] | None = None
    staging_receipt_id: str | None = None
    receipt_reasons: list[str] = []
    receipt_contract_valid = False
    if staging_receipt is None:
        receipt_reasons.append("STAGING_RECEIPT_MISSING")
    else:
        receipt_value = dict(staging_receipt)
        try:
            _strict_validate(DEFAULT_STAGING_RECEIPT_SCHEMA, receipt_value)
        except IdentityOperationalEvidenceError:
            receipt_reasons.append("STAGING_RECEIPT_INVALID")
        else:
            receipt_contract_valid = True
            staging_receipt_id = str(receipt_value["receipt_id"])
            if revision == "unbound":
                receipt_reasons.append("REVISION_UNBOUND")
            elif receipt_value["exact_revision"] != revision:
                receipt_reasons.append("STAGING_RECEIPT_REVISION_MISMATCH")
            if project_reference is None:
                receipt_reasons.append("STAGING_RECEIPT_PROJECT_UNRESOLVED")
            elif receipt_value["project_reference"] != project_reference:
                receipt_reasons.append("STAGING_RECEIPT_PROJECT_MISMATCH")
            if receipt_value["result"] != "PASS":
                receipt_reasons.append("STAGING_RECEIPT_FAILED")
            if _parse_time(receipt_value["created_at"]) > current:
                receipt_reasons.append("STAGING_RECEIPT_FUTURE_DATED")

    accepted = receipt_contract_valid and not receipt_reasons
    missing_operational_evidence = _operational_evidence_codes(
        value,
        receipt_value if accepted else None,
        project_observed=accepted and project_reference is not None,
    )

    readiness_review_eligible = (
        accepted
        and not unresolved_configuration
        and not missing_operational_evidence
        and implemented_internal
    )
    if accepted:
        status = "STAGING_EVIDENCE_ACCEPTED_PENDING_OPERATOR_REVIEW"
    elif staging_receipt is not None:
        status = "STAGING_EVIDENCE_REJECTED"
    else:
        status = "INTERNAL_ONLY"

    reason_codes = list(
        dict.fromkeys(
            unresolved_configuration
            + missing_operational_evidence
            + authority_blockers
            + receipt_reasons
        )
    )
    evaluation_material = "|".join(
        (
            revision,
            staging_receipt_id or "",
            status,
            ",".join(reason_codes),
        )
    )
    receipt = {
        "contract_id": "AIGC-IDENTITY-OPERATIONAL-EVIDENCE-EVALUATION-001",
        "contract_version": "1.0.0",
        "evaluation_id": "IOE-"
        + sha256(evaluation_material.encode("utf-8")).hexdigest()[:24].upper(),
        "status": status,
        "exact_revision": revision,
        "implemented_internal": implemented_internal,
        "staging_evidence_accepted": accepted,
        "readiness_review_eligible": readiness_review_eligible,
        "production_complete": False,
        "production_activation_authorized": bool(
            authority.get("production_identity_activation_authorized")
        ),
        "project_reference": project_reference,
        "staging_receipt_id": staging_receipt_id,
        "unresolved_configuration": unresolved_configuration,
        "missing_operational_evidence": missing_operational_evidence,
        "authority_blockers": authority_blockers,
        "reason_codes": reason_codes,
        "evaluated_at": current.isoformat(),
        "operator_review_required": True,
        "external_action_performed": False,
    }
    _strict_validate(DEFAULT_EVALUATION_SCHEMA, receipt)
    return IdentityOperationalEvidenceEvaluation(receipt=receipt, baseline=value)
