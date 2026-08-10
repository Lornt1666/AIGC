from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Sequence


REGION = "northamerica-northeast1"
PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
PROJECT_NUMBER_RE = re.compile(r"^[1-9][0-9]{5,20}$")
BILLING_RE = re.compile(r"^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
AUTHORITY_FLAGS = (
    "read_only_discovery_authorized",
    "state_backend_bootstrap_authorized",
    "terraform_plan_authorized",
    "resource_creation_authorized",
    "terraform_apply_authorized",
    "secret_version_creation_authorized",
    "gemini_canary_authorized",
    "openai_canary_authorized",
    "staging_deployment_authorized",
    "load_validation_authorized",
    "fault_injection_authorized",
    "mark_pr_ready_authorized",
    "merge_authorized",
    "production_activation_authorized",
)


class ProcurementError(RuntimeError):
    pass


class ProcurementMutationIndeterminate(ProcurementError):
    pass


def _utc(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ProcurementError(f"{name} is required for an executable procurement packet")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProcurementError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProcurementError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ExternalReleaseContract:
    payload: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> "ExternalReleaseContract":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ProcurementError("procurement contract must be a JSON object")
        contract = cls(payload=payload)
        contract.validate()
        return contract

    def validate(self, *, now: datetime | None = None) -> None:
        p = self.payload
        if p.get("schema_version") != "aigc.external-release-procurement.v1":
            raise ProcurementError("unsupported procurement contract")
        if not isinstance(p.get("template_only", False), bool):
            raise ProcurementError("template_only must be boolean")
        if p.get("repository") != "Lornt1666/AIGC":
            raise ProcurementError("repository binding mismatch")
        if not PROJECT_RE.fullmatch(str(p.get("project_id") or "")):
            raise ProcurementError("invalid project_id")
        if not PROJECT_NUMBER_RE.fullmatch(str(p.get("project_number") or "")):
            raise ProcurementError("invalid project_number")
        if not BILLING_RE.fullmatch(str(p.get("billing_account_id") or "")):
            raise ProcurementError("invalid billing_account_id")
        if p.get("region") != REGION:
            raise ProcurementError(f"region must equal {REGION}")
        if not SHA_RE.fullmatch(str(p.get("release_sha") or "")):
            raise ProcurementError("release_sha must be exact Git SHA")
        if not SHA_RE.fullmatch(str(p.get("release_tree_sha") or "")):
            raise ProcurementError("release_tree_sha must be exact Git tree SHA")
        for name in ("monthly_budget_cad", "provider_canary_spend_cad"):
            value = p.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ProcurementError(f"{name} must be non-negative")
        authority = p.get("authority")
        if not isinstance(authority, dict):
            raise ProcurementError("authority must be an object")
        expected_authority_keys = set(AUTHORITY_FLAGS) | {
            "authorized_by",
            "authorized_at",
            "expires_at",
        }
        if set(authority) != expected_authority_keys:
            raise ProcurementError("authority inventory is incomplete or contains unknown fields")
        for flag in AUTHORITY_FLAGS:
            if not isinstance(authority.get(flag), bool):
                raise ProcurementError(f"authority.{flag} must be boolean")
        if authority["production_activation_authorized"] is not False:
            raise ProcurementError("production activation is prohibited by this procurement contract")
        if authority["merge_authorized"] and not authority["mark_pr_ready_authorized"]:
            raise ProcurementError("merge authority requires ready-for-review authority first")
        if authority["terraform_apply_authorized"] and not authority["resource_creation_authorized"]:
            raise ProcurementError("Terraform apply authority requires resource-creation authority")
        if authority["resource_creation_authorized"] and not authority["terraform_plan_authorized"]:
            raise ProcurementError("resource-creation intent requires Terraform plan authority")
        if authority["staging_deployment_authorized"] and not authority["resource_creation_authorized"]:
            raise ProcurementError("staging deployment authority requires foundational resource authority")

        if p.get("template_only") is True:
            mutation_flags = [
                key
                for key in AUTHORITY_FLAGS
                if key != "read_only_discovery_authorized" and authority[key] is not False
            ]
            if mutation_flags:
                raise ProcurementError("template-only procurement cannot contain consequential authority")
            if p.get("monthly_budget_cad") != 0 or p.get("provider_canary_spend_cad") != 0:
                raise ProcurementError("template-only procurement must remain zero-spend")
            if authority["authorized_by"] not in {"", None}:
                raise ProcurementError("template-only procurement cannot name an authority actor")
            if authority["authorized_at"] is not None or authority["expires_at"] is not None:
                raise ProcurementError("template-only procurement cannot contain an authority window")
            return

        actor = authority.get("authorized_by")
        if not isinstance(actor, str) or not actor.strip():
            raise ProcurementError("authority.authorized_by is required")
        reference_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        authorized_at = _utc(authority.get("authorized_at"), "authority.authorized_at")
        expires_at = _utc(authority.get("expires_at"), "authority.expires_at")
        if authorized_at > reference_now:
            raise ProcurementError("external procurement authority starts in the future")
        if expires_at <= authorized_at:
            raise ProcurementError("external procurement authority expiry must follow authorization time")
        if expires_at <= reference_now:
            raise ProcurementError("external procurement authority is expired")

    @property
    def project_id(self) -> str:
        return str(self.payload["project_id"])

    @property
    def project_number(self) -> str:
        return str(self.payload["project_number"])

    @property
    def billing_account_id(self) -> str:
        return str(self.payload["billing_account_id"])

    @property
    def prefix(self) -> str:
        return str(self.payload["resource_prefix"])

    @property
    def authority(self) -> dict[str, Any]:
        return dict(self.payload["authority"])

    @property
    def template_only(self) -> bool:
        return bool(self.payload.get("template_only", False))


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _run(command: Sequence[str], *, capture: bool = True, mutating: bool = False) -> str:
    completed = subprocess.run(
        list(command), capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        error = ProcurementMutationIndeterminate if mutating else ProcurementError
        raise error(f"command failed: {' '.join(command[:3])}")
    return completed.stdout.strip() if capture else ""


def _json(command: Sequence[str]) -> dict[str, Any]:
    raw = _run(command)
    value = json.loads(raw or "{}")
    if not isinstance(value, dict):
        raise ProcurementError("provider discovery returned non-object JSON")
    return value


def _require_executable(contract: ExternalReleaseContract) -> None:
    if contract.template_only:
        raise ProcurementError("copy the template into a reviewed non-template execution packet first")


def assert_git_identity(contract: ExternalReleaseContract) -> None:
    _require_executable(contract)
    observed_sha = _run(["git", "rev-parse", "HEAD"])
    observed_tree = _run(["git", "rev-parse", "HEAD^{tree}"])
    if observed_sha != contract.payload["release_sha"]:
        raise ProcurementError("checkout SHA does not equal procurement release_sha")
    if observed_tree != contract.payload["release_tree_sha"]:
        raise ProcurementError("checkout tree does not equal procurement release_tree_sha")
    if _run(["git", "status", "--porcelain", "--untracked-files=all"]):
        raise ProcurementError("procurement requires a clean checkout")


def resource_names(contract: ExternalReleaseContract) -> dict[str, Any]:
    p = contract.prefix
    project = contract.project_id
    return {
        "artifact_registry_repository": f"{p}-runtime",
        "operator_service": f"{p}-operator",
        "judge_service": f"{p}-judge",
        "cloud_sql_instance": f"{p}-control",
        "database_name": "aigc_control",
        "evidence_bucket": f"{project}-{p}-evidence",
        "judge_bucket": f"{project}-{p}-judge",
        "receipt_bucket": f"{project}-{p}-receipts",
        "build_source_bucket": f"{project}-{p}-build-source",
        "log_bucket": f"{p}-logs",
        "kms_key_ring": f"{p}-keys",
        "wif_pool": f"{p}-gha",
        "wif_provider": "github",
        "service_accounts": {
            role: f"{p}-{suffix}@{project}.iam.gserviceaccount.com"
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
        },
        "regional_secret_ids": {
            purpose: f"{p}-{suffix}"
            for purpose, suffix in {
                "runtime_control_dsn": "runtime-control-dsn",
                "operator_token": "operator-token",
                "operator_binding_key": "operator-binding-key",
                "runtime_admin_token": "runtime-admin-token",
                "runtime_admin_binding_key": "runtime-admin-binding-key",
                "judge_token": "judge-token",
                "judge_binding_key": "judge-binding-key",
                "openai_api_key": "openai-api-key",
            }.items()
        },
    }


def build_resource_manifest(contract: ExternalReleaseContract) -> dict[str, Any]:
    names = resource_names(contract)
    project = contract.project_id
    return {
        "schema_version": "aigc.quebec-resource-manifest.v1",
        "provider": "google_cloud",
        "project_id": project,
        "project_number": contract.project_number,
        "region": REGION,
        "resource_prefix": contract.prefix,
        "resources": [
            {"kind": "artifact_registry", "name": names["artifact_registry_repository"], "location": REGION},
            {"kind": "cloud_sql_postgresql", "name": names["cloud_sql_instance"], "location": REGION, "availability_type": "REGIONAL"},
            {"kind": "storage_bucket", "name": names["evidence_bucket"], "location": REGION.upper(), "public_access_prevention": "enforced"},
            {"kind": "storage_bucket", "name": names["judge_bucket"], "location": REGION.upper(), "public_access_prevention": "enforced"},
            {"kind": "storage_bucket", "name": names["receipt_bucket"], "location": REGION.upper(), "public_access_prevention": "enforced"},
            {"kind": "storage_bucket", "name": names["build_source_bucket"], "location": REGION.upper(), "public_access_prevention": "enforced"},
            {"kind": "cloud_run_service", "name": names["operator_service"], "location": REGION},
            {"kind": "cloud_run_service", "name": names["judge_service"], "location": REGION},
            {"kind": "regional_secret_manager", "name": f"{contract.prefix}-secret-set", "location": REGION},
            {"kind": "kms_key_ring", "name": names["kms_key_ring"], "location": REGION},
            {"kind": "logging_bucket", "name": names["log_bucket"], "location": REGION},
        ],
        "control_plane_resources": [
            {"kind": "google_cloud_project", "name": project, "location": "global", "classification": "CONTROL_PLANE_METADATA", "customer_content": False, "residency_status": "VERIFIED_WITH_LIMITATION"},
            {"kind": "iam_and_service_accounts", "name": names["wif_pool"], "location": "global", "classification": "CONTROL_PLANE_METADATA", "customer_content": False, "residency_status": "VERIFIED_WITH_LIMITATION"},
            {"kind": "billing_and_budget", "name": contract.billing_account_id, "location": "global", "classification": "CONTROL_PLANE_METADATA", "customer_content": False, "residency_status": "VERIFIED_WITH_LIMITATION"},
            {"kind": "vpc_network", "name": f"{contract.prefix}-vpc", "location": "global", "classification": "CONTROL_PLANE_METADATA", "customer_content": False, "residency_status": "VERIFIED_WITH_LIMITATION"},
            {"kind": "private_service_access", "name": f"{contract.prefix}-private-services", "location": "global", "classification": "CONTROL_PLANE_METADATA", "customer_content": False, "residency_status": "VERIFIED_WITH_LIMITATION"},
        ],
        "authorization_bindings": {
            "resources": {
                name: names[name]
                for name in (
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
            },
            "service_accounts": names["service_accounts"],
            "exact_secret_version_refs": {},
        },
        "cross_region_replication": False,
        "public_resources": False,
        "production_resources": False,
        "service_account_keys": False,
        "strict_quebec_data_residency_verified": False,
    }


def discover(contract: ExternalReleaseContract) -> dict[str, Any]:
    if contract.authority.get("read_only_discovery_authorized") is not True:
        raise ProcurementError("read-only discovery is not authorized")
    project = _json(["gcloud", "projects", "describe", contract.project_id, "--format=json"])
    billing = _json(["gcloud", "billing", "projects", "describe", contract.project_id, "--format=json"])
    observed_project_number = str(project.get("projectNumber") or "")
    billing_name = str(billing.get("billingAccountName") or "")
    expected_billing_name = f"billingAccounts/{contract.billing_account_id}"
    names = resource_names(contract)

    def exists(command: Sequence[str]) -> bool:
        try:
            _run(command)
            return True
        except ProcurementError:
            return False

    receipt = {
        "schema_version": "aigc.external-release-discovery.v1",
        "repository": "Lornt1666/AIGC",
        "project_id": contract.project_id,
        "project_number_expected": contract.project_number,
        "project_number_observed": observed_project_number,
        "project_number_matches": observed_project_number == contract.project_number,
        "billing_account_expected": contract.billing_account_id,
        "billing_account_name_observed": billing_name,
        "billing_link_enabled": billing.get("billingEnabled") is True,
        "billing_link_matches": billing_name == expected_billing_name,
        "wif_pool_exists": exists(["gcloud", "iam", "workload-identity-pools", "describe", names["wif_pool"], "--project", contract.project_id, "--location", "global", "--format=value(name)"]),
        "wif_provider_exists": exists(["gcloud", "iam", "workload-identity-pools", "providers", "describe", names["wif_provider"], "--workload-identity-pool", names["wif_pool"], "--project", contract.project_id, "--location", "global", "--format=value(name)"]),
        "service_accounts": {
            role: exists(["gcloud", "iam", "service-accounts", "describe", email, "--project", contract.project_id, "--format=value(email)"])
            for role, email in names["service_accounts"].items()
        },
        "artifact_registry_exists": exists(["gcloud", "artifacts", "repositories", "describe", names["artifact_registry_repository"], "--project", contract.project_id, "--location", REGION, "--format=value(name)"]),
        "cloud_sql_exists": exists(["gcloud", "sql", "instances", "describe", names["cloud_sql_instance"], "--project", contract.project_id, "--format=value(name)"]),
        "regional_secret_metadata": {
            purpose: exists(["gcloud", "secrets", "describe", secret_id, "--project", contract.project_id, "--location", REGION, "--format=value(name)"])
            for purpose, secret_id in names["regional_secret_ids"].items()
        },
        "resource_creation_performed": False,
        "secret_value_accessed": False,
        "provider_call_performed": False,
        "deployment_performed": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    receipt["discovery_digest"] = canonical_sha256(receipt)
    return receipt


def terraform_inputs(contract: ExternalReleaseContract, manifest: dict[str, Any]) -> dict[str, Any]:
    _require_executable(contract)
    if contract.authority["terraform_plan_authorized"] is not True:
        raise ProcurementError("Terraform plan is not authorized")
    if contract.authority["resource_creation_authorized"] is not True:
        raise ProcurementError("material Terraform plan requires reviewed resource-creation intent")
    if contract.payload["monthly_budget_cad"] <= 0:
        raise ProcurementError("nonzero reviewed monthly_budget_cad is required before Terraform plan")
    if not contract.payload.get("budget_notification_channels"):
        raise ProcurementError("at least one reviewed Monitoring notification channel is required")
    inventory = {
        "project_id": contract.project_id,
        "project_number": contract.project_number,
        "region": REGION,
        "resource_prefix": contract.prefix,
        **manifest["authorization_bindings"],
    }
    return {
        "project_id": contract.project_id,
        "project_number": contract.project_number,
        "billing_account_id": contract.billing_account_id,
        "region": REGION,
        "resource_prefix": contract.prefix,
        "resource_creation_authorized": True,
        "staging_deployment_authorized": False,
        "production_activation_authorized": False,
        "public_access_authorized": False,
        "live_model_call_authorized": False,
        "cross_region_replication_authorized": False,
        "service_account_key_creation_authorized": False,
        "monthly_budget_cad": contract.payload["monthly_budget_cad"],
        "budget_notification_channels": list(contract.payload["budget_notification_channels"]),
        "release_sha": contract.payload["release_sha"],
        "release_tree_sha": contract.payload["release_tree_sha"],
        "resource_manifest_sha256": canonical_sha256(manifest),
        "authorization_inventory_sha256": canonical_sha256(inventory),
        "exact_secret_version_refs": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("--mode", choices=("manifest", "discover", "terraform-inputs"), default="manifest")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = ExternalReleaseContract.load(args.contract)
    manifest = build_resource_manifest(contract)
    if args.mode == "manifest":
        result = manifest
    elif args.mode == "discover":
        result = discover(contract)
    else:
        result = terraform_inputs(contract, manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProcurementError as exc:
        raise SystemExit(f"AIGC external procurement blocked: {exc}") from exc
