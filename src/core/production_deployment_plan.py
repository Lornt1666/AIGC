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
DEFAULT_CONFIG = ROOT / "config" / "production_deployment_baseline.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "production_deployment_baseline.schema.json"
DEFAULT_RELEASE_GATE_RECEIPT_SCHEMA = (
    ROOT / "schemas" / "production_release_gate_receipt.schema.json"
)
DEFAULT_TERRAFORM_ROOT = ROOT / "infra" / "terraform" / "gcp"
_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


class ProductionDeploymentPlanError(ValueError):
    pass


@dataclass(frozen=True)
class DeploymentPlanEvaluation:
    receipt: dict[str, Any]
    policy: dict[str, Any]

    @property
    def plan_eligible(self) -> bool:
        return self.receipt["result"] == "PLAN_ELIGIBLE"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return _utc(parsed)


def _strict_validate(schema_path: Path, value: Mapping[str, Any]) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(dict(value)),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        raise ProductionDeploymentPlanError(
            "Deployment contract validation failed: "
            + "; ".join(error.message for error in errors[:10])
        )


def load_deployment_policy(
    config_path: str | Path = DEFAULT_CONFIG,
    schema_path: str | Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    policy = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(policy, dict):
        raise ProductionDeploymentPlanError("Deployment policy must be an object")
    _strict_validate(Path(schema_path), policy)
    return policy


def terraform_fingerprint(terraform_root: str | Path = DEFAULT_TERRAFORM_ROOT) -> str:
    root = Path(terraform_root)
    files = sorted(root.glob("*.tf"))
    if not files:
        raise ProductionDeploymentPlanError("Terraform baseline contains no .tf files")
    material: list[str] = []
    joined = ""
    for path in files:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            raise ProductionDeploymentPlanError(f"Terraform file is empty: {path.name}")
        material.append(f"{path.name}:{sha256(content.encode('utf-8')).hexdigest()}")
        joined += "\n" + content
    required_fragments = (
        "resource_creation_requires_release_permit",
        "release_gate_result == \"PERMIT\"",
        "var.deployment_authorized",
        "local.resource_creation_effective",
        "resource_creation_default",
    )
    # resource_creation_default exists in the JSON policy, not Terraform. The
    # remaining guard fragments must exist in the Terraform baseline.
    for fragment in required_fragments[:-1]:
        if fragment not in joined:
            raise ProductionDeploymentPlanError(
                f"Terraform release guard is missing: {fragment}"
            )
    if re.search(r'^\s*resource\s+"google_', joined, flags=re.MULTILINE):
        raise ProductionDeploymentPlanError(
            "No-resource baseline must not define Google Cloud resources"
        )
    return sha256("|".join(material).encode("utf-8")).hexdigest()


def evaluate_deployment_plan(
    *,
    policy: Mapping[str, Any],
    environment: str,
    exact_revision: str | None,
    project_id: str | None,
    image_digest: str | None,
    release_gate_receipt: Mapping[str, Any] | None,
    production_domain: str | None,
    terraform_root: str | Path = DEFAULT_TERRAFORM_ROOT,
    now: datetime | None = None,
) -> DeploymentPlanEvaluation:
    value = dict(policy)
    reasons: list[str] = []
    current = _utc(now or datetime.now(timezone.utc))
    if environment not in {"staging", "production"}:
        reasons.append("ENVIRONMENT_INVALID")
    if not exact_revision or not _HEX40.fullmatch(exact_revision):
        reasons.append("REVISION_UNBOUND")
    if not project_id or not _PROJECT_ID.fullmatch(project_id):
        reasons.append("PROJECT_ID_UNRESOLVED")
    if not image_digest or not _IMAGE_DIGEST.fullmatch(image_digest):
        reasons.append("IMAGE_DIGEST_UNRESOLVED")
    if environment == "production" and not str(production_domain or "").strip():
        reasons.append("PRODUCTION_DOMAIN_UNRESOLVED")

    gate_id: str | None = None
    gate_valid_until: str | None = None
    if release_gate_receipt is None:
        reasons.append("RELEASE_GATE_RECEIPT_MISSING")
    else:
        gate = dict(release_gate_receipt)
        try:
            _strict_validate(DEFAULT_RELEASE_GATE_RECEIPT_SCHEMA, gate)
        except ProductionDeploymentPlanError:
            reasons.append("RELEASE_GATE_RECEIPT_INVALID")
        else:
            gate_id = str(gate["gate_receipt_id"])
            gate_evaluated_at = _parse_time(gate["evaluated_at"])
            gate_valid_until_time = _parse_time(gate["valid_until"])
            gate_valid_until = gate_valid_until_time.isoformat()
            if gate_evaluated_at > current:
                reasons.append("RELEASE_GATE_EVALUATED_IN_FUTURE")
            if gate_valid_until_time <= gate_evaluated_at:
                reasons.append("RELEASE_GATE_VALIDITY_WINDOW_INVALID")
            if current >= gate_valid_until_time:
                reasons.append("RELEASE_GATE_EXPIRED")
            if gate["result"] != "PERMIT" or gate["deployment_authorized"] is not True:
                reasons.append("RELEASE_GATE_DENIED")
            if gate["exact_revision"] != exact_revision:
                reasons.append("RELEASE_GATE_REVISION_MISMATCH")
            if gate["release_artifact_digest"] != image_digest:
                reasons.append("RELEASE_GATE_ARTIFACT_MISMATCH")

    authority = dict(value["authority"])
    if environment == "staging":
        if authority.get("staging_resource_creation_authorized") is not True:
            reasons.append("STAGING_RESOURCE_CREATION_UNAUTHORIZED")
        if authority.get("staging_apply_authorized") is not True:
            reasons.append("STAGING_APPLY_UNAUTHORIZED")
    else:
        if authority.get("production_resource_creation_authorized") is not True:
            reasons.append("PRODUCTION_RESOURCE_CREATION_UNAUTHORIZED")
        if authority.get("production_apply_authorized") is not True:
            reasons.append("PRODUCTION_APPLY_UNAUTHORIZED")
        if authority.get("production_deployment_authorized") is not True:
            reasons.append("PRODUCTION_DEPLOYMENT_UNAUTHORIZED")
        if authority.get("dns_change_authorized") is not True:
            reasons.append("DNS_CHANGE_UNAUTHORIZED")

    fingerprint = terraform_fingerprint(terraform_root)
    reason_codes = tuple(dict.fromkeys(reasons))
    receipt_material = "|".join(
        (
            environment,
            exact_revision or "",
            project_id or "",
            image_digest or "",
            gate_id or "",
            gate_valid_until or "",
            fingerprint,
            ",".join(reason_codes),
        )
    )
    receipt = {
        "contract_id": "AIGC-DEPLOYMENT-PLAN-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "DPR-"
        + sha256(receipt_material.encode("utf-8")).hexdigest()[:24].upper(),
        "environment": environment if environment in {"staging", "production"} else "staging",
        "exact_revision": exact_revision or "unbound",
        "result": "PLAN_ELIGIBLE" if not reason_codes else "DENY",
        "reason_codes": list(reason_codes),
        "resource_creation_effective": False,
        "release_gate_receipt_id": gate_id,
        "release_gate_valid_until": gate_valid_until,
        "image_digest": image_digest,
        "project_id": project_id,
        "production_domain": production_domain,
        "terraform_fingerprint": fingerprint,
        "created_at": current.isoformat(),
        "operator_review_required": True,
        "external_action_performed": False,
    }
    _strict_validate(ROOT / "schemas" / "deployment_plan_receipt.schema.json", receipt)
    return DeploymentPlanEvaluation(receipt=receipt, policy=value)
