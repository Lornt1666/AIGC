from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from src.core.staging_procurement_contracts import strict_validate as validate_staging_contract

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas"
DEFAULT_CATALOG_PATH = ROOT / "config/provider_discovery_command_catalog.json"
DEFAULT_FIXTURE_PATH = ROOT / "config/provider_discovery_mock_fixture.json"
DEFAULT_TEMPLATE_PATH = ROOT / "config/staging_identity_procurement_readiness_pack.json"

PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,254}$")
WIF_RE = re.compile(r"^[A-Za-z0-9_-]{4,100}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._-]{6,100}@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$")
BUCKET_RE = re.compile(r"^gs://[A-Za-z0-9._-]{3,222}$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")

ALLOWED_PREFIXES = (
    ("gcloud", "projects", "describe"),
    ("gcloud", "services", "list"),
    ("gcloud", "projects", "get-iam-policy"),
    ("gcloud", "iam", "service-accounts", "list"),
    ("gcloud", "iam", "service-accounts", "keys", "list"),
    ("gcloud", "iam", "workload-identity-pools", "list"),
    ("gcloud", "iam", "workload-identity-pools", "providers", "list"),
    ("gcloud", "secrets", "list"),
    ("gcloud", "secrets", "versions", "list"),
    ("gcloud", "storage", "buckets", "describe"),
)
FORBIDDEN_WORDS = {
    "create", "update", "delete", "set-iam-policy", "add-iam-policy-binding",
    "remove-iam-policy-binding", "enable", "disable", "access", "add-version",
    "destroy", "undelete", "deploy", "apply", "import", "replace", "patch", "write",
}
SENSITIVE_KEYS = {
    "access_token", "refresh_token", "id_token", "private_key", "private_key_data",
    "password", "secret_value", "client_secret_value", "authorization_header",
    "credential", "credentials",
}
SENSITIVE_MARKERS = (
    "-----BEGIN " + "PRIVATE KEY-----",
    "-----BEGIN RSA " + "PRIVATE KEY-----",
    "ya" + "29.",
)


class ProviderDiscoveryAutomationError(ValueError):
    pass


class ProviderExecutionDisabled(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def strict_validate(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.schema.json"
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderDiscoveryAutomationError(f"Unable to load schema: {path.name}") from exc
    Draft202012Validator.check_schema(schema)
    value = dict(payload)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = []
        for error in errors[:10]:
            location = "$" + "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}"
                for part in error.absolute_path
            )
            details.append(f"{location}: {error.message}")
        raise ProviderDiscoveryAutomationError(f"{name} validation failed: {'; '.join(details)}")
    return value


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    try:
        value = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderDiscoveryAutomationError(f"Unable to load JSON: {file_path}") from exc
    if not isinstance(value, dict):
        raise ProviderDiscoveryAutomationError(f"{file_path} must contain an object")
    return value


def scan_for_sensitive_material(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                raise ProviderDiscoveryAutomationError(f"Sensitive key prohibited at {path}.{key}")
            scan_for_sensitive_material(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_for_sensitive_material(child, f"{path}[{index}]")
    elif isinstance(value, str) and any(marker in value for marker in SENSITIVE_MARKERS):
        raise ProviderDiscoveryAutomationError(f"Sensitive string marker prohibited at {path}")


def load_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> dict[str, Any]:
    value = strict_validate("provider_discovery_command_catalog", load_json(path))
    scan_for_sensitive_material(value)
    validate_catalog_commands(value)
    return value


def load_fixture(path: str | Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    value = strict_validate("provider_discovery_mock_fixture", load_json(path))
    scan_for_sensitive_material(value)
    return value


def load_template(path: str | Path = DEFAULT_TEMPLATE_PATH) -> dict[str, Any]:
    return load_json(path)


def validate_gcloud_argv(argv: Sequence[str], *, template: bool = False) -> None:
    if isinstance(argv, (str, bytes)) or not argv:
        raise ProviderDiscoveryAutomationError("argv must be a non-empty sequence")
    tokens = [str(item) for item in argv]
    if tokens[0] != "gcloud":
        raise ProviderDiscoveryAutomationError("Only gcloud is permitted")
    if any(any(char in token for char in (";", "|", "&", "\n", "\r", "`")) for token in tokens):
        raise ProviderDiscoveryAutomationError("Shell metacharacters are prohibited")
    if not any(tuple(tokens[:len(prefix)]) == prefix for prefix in ALLOWED_PREFIXES):
        raise ProviderDiscoveryAutomationError(f"Unapproved command prefix: {tokens[:5]}")
    words = [token.lower() for token in tokens[1:] if not token.startswith("-")]
    if any(word in FORBIDDEN_WORDS for word in words):
        raise ProviderDiscoveryAutomationError("Mutation or secret access is prohibited")
    if any("access-token" in token.lower() for token in tokens):
        raise ProviderDiscoveryAutomationError("Access-token flags are prohibited")
    if "--format=json" not in tokens:
        raise ProviderDiscoveryAutomationError("--format=json is mandatory")
    if not template and any("{" in token or "}" in token for token in tokens):
        raise ProviderDiscoveryAutomationError("Rendered argv contains placeholders")


def validate_catalog_commands(catalog: Mapping[str, Any]) -> None:
    if catalog.get("execution_mode") != "MOCK_ONLY" or catalog.get("live_execution_enabled") is not False:
        raise ProviderDiscoveryAutomationError("Catalog must remain mock-only")
    ids, fixtures = set(), set()
    for command in catalog.get("commands", []):
        command_id, fixture = command["command_id"], command["fixture_key"]
        if command_id in ids or fixture in fixtures:
            raise ProviderDiscoveryAutomationError("Duplicate command or fixture key")
        ids.add(command_id)
        fixtures.add(fixture)
        if command["classification"] != "READ_ONLY":
            raise ProviderDiscoveryAutomationError(f"{command_id} is not read-only")
        if command["mutation_performed"] is not False or command["secret_value_access"] is not False:
            raise ProviderDiscoveryAutomationError(f"{command_id} expands authority")
        validate_gcloud_argv(command["argv_template"], template=True)


def validate_parameters(parameters: Mapping[str, str]) -> dict[str, str]:
    required = {
        "project_id", "project_reference", "wif_pool_id", "wif_provider_id",
        "plan_service_account_id", "apply_service_account_id", "runtime_service_account_id",
        "plan_service_account_email", "apply_service_account_email",
        "runtime_service_account_email", "oauth_secret_id", "session_pepper_secret_id",
        "state_bucket_url", "state_bucket_reference", "staging_domain_reference",
    }
    if required - set(parameters):
        raise ProviderDiscoveryAutomationError("Target parameters are incomplete")
    value = {key: str(item) for key, item in parameters.items()}
    project = value["project_id"]
    if not PROJECT_RE.fullmatch(project) or value["project_reference"] != f"gcp_project://{project}":
        raise ProviderDiscoveryAutomationError("Invalid project target")
    account_ids = [value[key] for key in (
        "plan_service_account_id", "apply_service_account_id", "runtime_service_account_id"
    )]
    if any(not PROJECT_RE.fullmatch(item) for item in account_ids) or len(set(account_ids)) != 3:
        raise ProviderDiscoveryAutomationError("Service-account IDs are invalid or not distinct")
    for key in ("plan_service_account_email", "apply_service_account_email", "runtime_service_account_email"):
        if not EMAIL_RE.fullmatch(value[key]) or not value[key].endswith(f"@{project}.iam.gserviceaccount.com"):
            raise ProviderDiscoveryAutomationError(f"Invalid {key}")
    if any(not WIF_RE.fullmatch(value[key]) for key in ("wif_pool_id", "wif_provider_id")):
        raise ProviderDiscoveryAutomationError("Invalid WIF identifier")
    if any(not ID_RE.fullmatch(value[key]) for key in ("oauth_secret_id", "session_pepper_secret_id")):
        raise ProviderDiscoveryAutomationError("Invalid secret identifier")
    if value["oauth_secret_id"] == value["session_pepper_secret_id"]:
        raise ProviderDiscoveryAutomationError("OAuth and session secrets must be separate")
    if not BUCKET_RE.fullmatch(value["state_bucket_url"]):
        raise ProviderDiscoveryAutomationError("Invalid bucket URL")
    expected_bucket = f"gcs_bucket://{project}/{value['state_bucket_url'].removeprefix('gs://')}"
    if value["state_bucket_reference"] != expected_bucket:
        raise ProviderDiscoveryAutomationError("Bucket reference mismatch")
    if not value["staging_domain_reference"].startswith("dns_name://"):
        raise ProviderDiscoveryAutomationError("Invalid domain reference")
    scan_for_sensitive_material(value)
    return value


def render_command_plan(catalog: Mapping[str, Any], parameters: Mapping[str, str]) -> list[dict[str, Any]]:
    validate_catalog_commands(catalog)
    values, plan = validate_parameters(parameters), []
    for command in catalog["commands"]:
        try:
            argv = [str(token).format_map(values) for token in command["argv_template"]]
        except KeyError as exc:
            raise ProviderDiscoveryAutomationError(f"Missing placeholder: {exc.args[0]}") from exc
        validate_gcloud_argv(argv)
        plan.append({
            "command_id": command["command_id"],
            "authorization_action": command["authorization_action"],
            "argv": argv,
            "argv_digest": canonical_digest(argv),
            "classification": "READ_ONLY",
            "network_required": True,
            "mutation_performed": False,
            "secret_value_access": False,
            "timeout_seconds": command["timeout_seconds"],
            "max_attempts": command["max_attempts"],
            "fixture_key": command["fixture_key"],
            "output_sensitivity": command["output_sensitivity"],
        })
    return plan


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return utc(value).isoformat().replace("+00:00", "Z")


def build_target_specification_submission(
    template: Mapping[str, Any], *, parameters: Mapping[str, str],
    repository_revision: str, created_at: datetime,
) -> dict[str, Any]:
    if not SHA_RE.fullmatch(repository_revision):
        raise ProviderDiscoveryAutomationError("Invalid repository revision")
    values, current = validate_parameters(parameters), utc(created_at)
    pack = copy.deepcopy(dict(template))
    pack.update({
        "artifact_kind": "SUBMISSION",
        "pack_id": "SIP-" + canonical_digest({
            "revision": repository_revision, "parameters": values, "created_at": iso(current)
        })[:24].upper(),
        "status": "TARGET_SPECIFICATION",
        "transition": {
            "previous_status": None, "transition_reason": None, "transition_evidence_digest": None
        },
        "lifecycle": {
            "created_at": iso(current), "expires_at": iso(current + timedelta(days=1)),
            "supersedes_pack_id": None, "revoked": False,
            "revoked_at": None, "revocation_reason": None,
        },
    })
    for phase in pack["phase_consumption"].values():
        phase.update({"status": "UNUSED", "consumed_at": None, "consumed_by_receipt_id": None})
    pack["target_specification"].update({
        "project_reference": values["project_reference"],
        "project_id": values["project_id"],
        "proposed_wif_pool_id": values["wif_pool_id"],
        "proposed_wif_provider_id": values["wif_provider_id"],
        "proposed_plan_service_account_id": values["plan_service_account_id"],
        "proposed_apply_service_account_id": values["apply_service_account_id"],
        "proposed_runtime_service_account_id": values["runtime_service_account_id"],
        "proposed_state_bucket_reference": values["state_bucket_reference"],
        "proposed_staging_domain_reference": values["staging_domain_reference"],
    })
    pack["unresolved_requirements"] = [
        "provider_discovery_evidence", "state_backend_bootstrap_evidence",
        "identity_bootstrap_evidence", "google_oauth_client",
        "oauth_client_secret_numeric_version", "session_pepper_numeric_version",
        "operator_controlled_test_subject",
    ]
    for flag in (
        "raw_secret_values_present", "automatic_apply_allowed",
        "authorization_receipt_issued", "provider_action_performed",
        "terraform_plan_performed", "terraform_apply_performed", "external_action_performed",
    ):
        pack[flag] = False
    pack["operator_review_required"] = True
    return validate_staging_contract("staging_identity_procurement_readiness_pack", pack)


def build_provenance_envelope(
    *, node_type: str, artifact: Mapping[str, Any], repository_revision: str,
    created_at: datetime, predecessor_ids: Sequence[str] = (),
    ci_run_id: str | None = None, rollback_reference: str,
) -> dict[str, Any]:
    digest = canonical_digest(artifact)
    material = {
        "node_type": node_type, "artifact_digest": digest,
        "repository_revision": repository_revision, "created_at": iso(created_at),
        "predecessor_ids": list(predecessor_ids),
    }
    return strict_validate("evidence_provenance_envelope", {
        "contract_id": "AIGC-EVIDENCE-PROVENANCE-ENVELOPE-001",
        "contract_version": "1.0.0",
        "node_id": "PROV-" + canonical_digest(material)[:24].upper(),
        "node_type": node_type, "artifact_digest": "sha256:" + digest,
        "repository_revision": repository_revision, "created_at": iso(created_at),
        "predecessor_ids": list(predecessor_ids),
        "authorization_receipt_id": None, "evidence_receipt_id": None,
        "operator_approval_reference": None, "ci_run_id": ci_run_id,
        "rollback_reference": rollback_reference, "external_action_performed": False,
    })


def execute_live(*_: Any, **__: Any) -> None:
    raise ProviderExecutionDisabled(
        "Live provider execution is disabled in Provider Discovery Automation Kit v1"
    )
