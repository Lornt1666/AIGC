from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_ROOT = ROOT / "infra" / "terraform" / "gcp"
PLAN_SCHEMA = ROOT / "schemas" / "staging_infrastructure_plan_authorization.schema.json"
APPLY_SCHEMA = ROOT / "schemas" / "staging_infrastructure_apply_authorization.schema.json"
DISCOVERY_SCHEMA = ROOT / "schemas" / "provider_discovery_evidence_receipt.schema.json"


class StagingInfrastructureAuthorizationError(ValueError):
    """Raised when staging infrastructure authority is invalid or ineffective."""


@dataclass(frozen=True)
class AuthorizationEvaluation:
    effective: bool
    reason_codes: tuple[str, ...]
    exact_revision: str
    project_id: str
    terraform_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective": self.effective,
            "reason_codes": list(self.reason_codes),
            "exact_revision": self.exact_revision,
            "project_id": self.project_id,
            "terraform_fingerprint": self.terraform_fingerprint,
            "operator_review_required": True,
            "external_action_performed": False,
        }


def utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def parse_time(value: Any) -> datetime:
    return utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StagingInfrastructureAuthorizationError(
            f"Unable to load JSON artifact: {resolved}"
        ) from exc
    if not isinstance(value, dict):
        raise StagingInfrastructureAuthorizationError(
            f"JSON artifact must be an object: {resolved}"
        )
    return value


def canonical_digest(value: Mapping[str, Any]) -> str:
    material = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256(material.encode("utf-8")).hexdigest()


def file_digest(path: str | Path, *, prefixed: bool = True) -> str:
    digest = sha256(Path(path).read_bytes()).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


def validate_schema(schema_path: str | Path, value: Mapping[str, Any]) -> dict[str, Any]:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(dict(value)),
        key=lambda error: list(error.absolute_path),
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
        raise StagingInfrastructureAuthorizationError(
            "Contract validation failed: " + "; ".join(messages)
        )
    return dict(value)


def repository_revision(project_root: str | Path = ROOT) -> str:
    root = Path(project_root)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StagingInfrastructureAuthorizationError(
            "Unable to resolve the exact Git revision"
        ) from exc
    revision = result.stdout.strip()
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise StagingInfrastructureAuthorizationError("Git revision is not an exact SHA-1")
    return revision


def recursive_terraform_fingerprint(terraform_root: str | Path = TERRAFORM_ROOT) -> str:
    root = Path(terraform_root)
    files = sorted(
        path
        for path in root.rglob("*.tf")
        if path.is_file() and ".terraform" not in path.relative_to(root).parts
    )
    if not files:
        raise StagingInfrastructureAuthorizationError("Terraform root contains no .tf files")
    material = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        material.append(f"{relative}:{sha256(path.read_bytes()).hexdigest()}")
    return sha256("|".join(material).encode("utf-8")).hexdigest()


def _time_reasons(
    authorization: Mapping[str, Any],
    *,
    now: datetime,
    max_hours: int,
    prefix: str,
) -> list[str]:
    reasons: list[str] = []
    issued = parse_time(authorization["issued_at"])
    expires = parse_time(authorization["expires_at"])
    if issued > now:
        reasons.append(f"{prefix}_ISSUED_IN_FUTURE")
    if expires <= issued:
        reasons.append(f"{prefix}_LIFETIME_INVALID")
    if now >= expires:
        reasons.append(f"{prefix}_EXPIRED")
    if (expires - issued).total_seconds() > max_hours * 3600:
        reasons.append(f"{prefix}_TTL_EXCEEDED")
    return reasons


def validate_plan_authorization(
    *,
    authorization: Mapping[str, Any],
    discovery_evidence: Mapping[str, Any],
    project_root: str | Path = ROOT,
    terraform_root: str | Path = TERRAFORM_ROOT,
    exact_revision: str | None = None,
    evaluated_at: datetime | None = None,
) -> AuthorizationEvaluation:
    auth = validate_schema(PLAN_SCHEMA, authorization)
    discovery = validate_schema(DISCOVERY_SCHEMA, discovery_evidence)
    current = utc(evaluated_at)
    revision = exact_revision or repository_revision(project_root)
    fingerprint = recursive_terraform_fingerprint(terraform_root)
    project_id = str(auth["project_id"])
    reasons: list[str] = []

    if auth["decision"] != "APPROVED":
        reasons.append("PLAN_OPERATOR_DENIED")
    if auth["exact_revision"] != revision:
        reasons.append("PLAN_REVISION_MISMATCH")
    if auth["terraform_fingerprint"] != fingerprint:
        reasons.append("PLAN_TERRAFORM_FINGERPRINT_MISMATCH")
    if auth["monthly_budget_cad"] > 50:
        reasons.append("PLAN_STAGING_BUDGET_EXCEEDED")
    if auth["resource_creation_authorized"] is not True:
        reasons.append("PLAN_RESOURCE_DEFINITION_NOT_AUTHORIZED")
    if auth["cloud_sql_enabled"] is not True:
        reasons.append("PLAN_CLOUD_SQL_NOT_AUTHORIZED")
    if auth["terraform_plan_authorized"] is not True:
        reasons.append("PLAN_TERRAFORM_NOT_AUTHORIZED")

    discovery_digest = canonical_digest(discovery)
    if auth["provider_discovery_evidence_receipt_id"] != discovery["receipt_id"]:
        reasons.append("PLAN_DISCOVERY_RECEIPT_MISMATCH")
    if auth["provider_discovery_evidence_digest"] != discovery_digest:
        reasons.append("PLAN_DISCOVERY_DIGEST_MISMATCH")
    if discovery["exact_revision"] != revision:
        reasons.append("PLAN_DISCOVERY_REVISION_MISMATCH")
    if discovery["target_project_reference"] != f"gcp_project://{project_id}":
        reasons.append("PLAN_DISCOVERY_PROJECT_MISMATCH")
    if discovery["result"] not in {"SUCCESS", "PARTIAL"}:
        reasons.append("PLAN_DISCOVERY_FAILED")
    if discovery["review_status"] != "ACCEPTED":
        reasons.append("PLAN_DISCOVERY_NOT_ACCEPTED")
    if discovery["provider_read_performed"] is not True:
        reasons.append("PLAN_DISCOVERY_PROVIDER_READ_NOT_OBSERVED")
    if discovery["mutation_performed"] is not False:
        reasons.append("PLAN_DISCOVERY_MUTATION_OBSERVED")
    if discovery["raw_secret_values_present"] is not False:
        reasons.append("PLAN_DISCOVERY_SECRET_VALUE_PRESENT")

    reasons.extend(_time_reasons(auth, now=current, max_hours=4, prefix="PLAN_AUTHORIZATION"))
    unique = tuple(dict.fromkeys(reasons))
    return AuthorizationEvaluation(
        effective=not unique,
        reason_codes=unique,
        exact_revision=revision,
        project_id=project_id,
        terraform_fingerprint=fingerprint,
    )


def validate_apply_authorization(
    *,
    authorization: Mapping[str, Any],
    plan_authorization: Mapping[str, Any],
    saved_plan_path: str | Path,
    project_root: str | Path = ROOT,
    terraform_root: str | Path = TERRAFORM_ROOT,
    exact_revision: str | None = None,
    evaluated_at: datetime | None = None,
) -> AuthorizationEvaluation:
    auth = validate_schema(APPLY_SCHEMA, authorization)
    plan_auth = validate_schema(PLAN_SCHEMA, plan_authorization)
    current = utc(evaluated_at)
    revision = exact_revision or repository_revision(project_root)
    fingerprint = recursive_terraform_fingerprint(terraform_root)
    project_id = str(auth["project_id"])
    reasons: list[str] = []

    if auth["decision"] != "APPROVED":
        reasons.append("APPLY_OPERATOR_DENIED")
    if auth["exact_revision"] != revision:
        reasons.append("APPLY_REVISION_MISMATCH")
    if auth["project_id"] != plan_auth["project_id"]:
        reasons.append("APPLY_PROJECT_MISMATCH")
    if auth["terraform_fingerprint"] != fingerprint:
        reasons.append("APPLY_TERRAFORM_FINGERPRINT_MISMATCH")
    if auth["terraform_fingerprint"] != plan_auth["terraform_fingerprint"]:
        reasons.append("APPLY_PLAN_FINGERPRINT_MISMATCH")
    if auth["plan_authorization_receipt_id"] != plan_auth["receipt_id"]:
        reasons.append("APPLY_PLAN_AUTHORIZATION_ID_MISMATCH")
    if auth["plan_authorization_digest"] != canonical_digest(plan_auth):
        reasons.append("APPLY_PLAN_AUTHORIZATION_DIGEST_MISMATCH")
    if auth["saved_plan_digest"] != file_digest(saved_plan_path):
        reasons.append("APPLY_SAVED_PLAN_DIGEST_MISMATCH")
    if auth["provider_mutation_authorized"] is not True:
        reasons.append("APPLY_PROVIDER_MUTATION_NOT_AUTHORIZED")
    if auth["terraform_apply_authorized"] is not True:
        reasons.append("APPLY_TERRAFORM_NOT_AUTHORIZED")

    reasons.extend(_time_reasons(auth, now=current, max_hours=1, prefix="APPLY_AUTHORIZATION"))
    unique = tuple(dict.fromkeys(reasons))
    return AuthorizationEvaluation(
        effective=not unique,
        reason_codes=unique,
        exact_revision=revision,
        project_id=project_id,
        terraform_fingerprint=fingerprint,
    )
