from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Callable, Sequence
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from jsonschema import Draft202012Validator, FormatChecker

from scripts.prepare_nexus_build_context import prepare_build_context
from scripts.validate_quebec_cloud_authorization import (
    AuthorizationError,
    validate as validate_quebec_authorization,
)
from src.operations.nexus_provider_canary import (
    CANARY_AUTHORITY_ALGORITHM,
    KmsAuthorityPublicKey,
    authority_public_key_sha256,
    expected_canary_authority_key_version,
    fetch_kms_authority_public_key,
)


REGION = "northamerica-northeast1"
REPOSITORY = "Lornt1666/AIGC"
PLAN_SCHEMA = "aigc.nexus-staging-plan.v2"
RECEIPT_SCHEMA = "aigc.quebec-deployment-receipt.v1"
ACTION_PERMIT_SCHEMA = "aigc.nexus-staging-action-permit.v2"
ACTION_CHECKPOINT_SCHEMA = "aigc.nexus-staging-action-checkpoint.v1"
ACTION_CHECKPOINT_ENVELOPE_SCHEMA = (
    "aigc.nexus-staging-action-checkpoint-envelope.v1"
)
ROOT = Path(__file__).resolve().parents[1]
BUILD_CONTEXT_ALLOWLIST = ROOT / "config" / "nexus_build_context_allowlist.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "quebec_deployment_receipt.schema.json"
ACTION_PERMIT_SCHEMA_PATH = ROOT / "schemas" / "nexus_staging_action_permit.schema.json"
ACTION_CHECKPOINT_SCHEMA_PATH = (
    ROOT / "schemas" / "nexus_staging_action_checkpoint.schema.json"
)
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_IMMUTABLE_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[a-f0-9]{64}$"
)
_PINNED_SYFT_IMAGE = re.compile(
    r"^(?:docker\.io/)?anchore/syft@sha256:[a-f0-9]{64}$"
)
_MIGRATION_MARKER = "AIGC_NEXUS_MIGRATION_RECEIPT:"
_CLOUD_BUILD_BUILDER_ID = "https://cloudbuild.googleapis.com/GoogleHostedWorker"
_PACKAGE_VULNERABILITY_NOTE = "projects/goog-analysis/notes/PACKAGE_VULNERABILITY"
_REGIONAL_PACKAGE_VULNERABILITY_NOTE = (
    f"projects/goog-analysis/locations/{REGION}/notes/PACKAGE_VULNERABILITY"
)
_SBOM_MAX_BYTES = 64 * 1024 * 1024
_ACTION_NAMES = (
    "cloud_build_submit",
    "sbom_export",
    "migration_job_deploy",
    "migration_execute",
    "operator_deploy",
    "judge_deploy",
)
_ACTION_TARGET_RULES = (
    "exact_immutable_release_tag",
    "verified_predecessor_image_digest",
    "exact_migration_job",
    "exact_migration_job_execution",
    "exact_private_no_traffic_service",
    "exact_private_no_traffic_service",
)
_MAX_ACTION_PERMIT_ACTIVE_WINDOW = timedelta(minutes=15)
_MAX_ACTION_PERMIT_ISSUANCE_AGE = timedelta(minutes=5)
_MAX_ACTION_PERMIT_TOTAL_LIFETIME = timedelta(minutes=15)
_ACTION_PERMIT_WAIT_POLL_SECONDS = 1.0
_SBOM_LOAD_PROJECT_PERMISSIONS = (
    "containeranalysis.notes.attachOccurrence",
    "containeranalysis.notes.create",
    "containeranalysis.notes.get",
    "containeranalysis.notes.list",
    "containeranalysis.occurrences.create",
    "containeranalysis.occurrences.get",
    "containeranalysis.occurrences.list",
)
_SBOM_BUCKET_PERMISSIONS = (
    "storage.buckets.get",
    "storage.objects.create",
)
_IMAGE_PULL_REPOSITORY_PERMISSIONS = (
    "artifactregistry.dockerimages.get",
    "artifactregistry.dockerimages.list",
    "artifactregistry.repositories.downloadArtifacts",
    "artifactregistry.repositories.get",
)
_EXPECTED_CI_STAGES = (
    "pip_check",
    "python_compilation",
    "contracts",
    "orchestration_schema_validation",
    "orchestration_round_trip_validation",
    "redaction",
    "release_secret_scan",
    "procurement_smoke",
    "provider_discovery",
    "terraform_inert",
    "quebec_terraform_validate",
    "nexus_supply_chain",
    "tests",
    "false_authority",
    "readiness",
)


class NexusStagingDeploymentError(RuntimeError):
    pass


class NexusStagingMutationIndeterminate(NexusStagingDeploymentError):
    pass


class NexusStagingPermitAlreadyConsumed(NexusStagingDeploymentError):
    pass


def _run(command: Sequence[str], *, capture: bool = False, mutating: bool = False) -> str:
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        error_type = NexusStagingMutationIndeterminate if mutating else NexusStagingDeploymentError
        raise error_type(f"command failed: {command[0]} {command[1] if len(command) > 1 else ''}")
    return completed.stdout.strip() if capture else ""


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(value)
    ).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _git_identity(expected_sha: str, expected_tree: str) -> None:
    observed_sha = _run(["git", "rev-parse", "HEAD"], capture=True)
    observed_tree = _run(["git", "rev-parse", "HEAD^{tree}"], capture=True)
    if observed_sha != expected_sha or observed_tree != expected_tree:
        raise NexusStagingDeploymentError("authorized release SHA/tree does not match checkout")
    dirty = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture=True,
    )
    if dirty:
        raise NexusStagingDeploymentError("staging deployment requires a clean checkout")


def _authorization_hash(payload: dict[str, Any]) -> str:
    return _canonical_sha256(payload)


def _validate_ci_admission(
    admission: dict[str, Any],
    *,
    release_sha: str,
    release_tree_sha: str,
    expected_sha256: str,
    expected_python_base_image: str,
) -> dict[str, Any]:
    if (
        admission.get("schema_version") != "aigc.exact-head-ci-admission.v2"
        or _canonical_sha256(admission) != expected_sha256
    ):
        raise NexusStagingDeploymentError(
            "CI admission does not match the authorization-bound digest"
        )
    run = admission.get("workflow_run")
    artifact = admission.get("artifact")
    exact_head = admission.get("exact_head_receipt")
    container = admission.get("container_build")
    stages = admission.get("stage_records")
    if not all(isinstance(value, dict) for value in (run, artifact, exact_head, container)):
        raise NexusStagingDeploymentError("CI admission has invalid nested evidence")
    if not isinstance(stages, list):
        raise NexusStagingDeploymentError("CI admission stage records must be an array")
    run_id = run.get("id")
    if (
        run.get("repository") != REPOSITORY
        or run.get("workflow_path") != ".github/workflows/aigc-ci.yml"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("head_sha") != release_sha
        or run.get("event") != "push"
        or run.get("head_branch") != "main"
        or run.get("head_repository_full_name") != REPOSITORY
        or run.get("protected_branch_verified") is not True
        or isinstance(run_id, bool)
        or not isinstance(run_id, int)
        or run_id <= 0
    ):
        raise NexusStagingDeploymentError(
            "CI workflow receipt is not a successful exact-head AIGC CI run"
        )
    artifact_digest = artifact.get("digest")
    if (
        isinstance(artifact.get("id"), bool)
        or not isinstance(artifact.get("id"), int)
        or artifact["id"] <= 0
        or artifact.get("expired") is not False
        or artifact.get("name")
        != f"aigc-colosseum-orchestration-exact-head-{release_sha}"
        or not isinstance(artifact_digest, str)
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", artifact_digest)
    ):
        raise NexusStagingDeploymentError("CI artifact identity/digest is invalid")
    if (
        exact_head.get("schema_version") != "aigc.exact-head-admission-receipt.v2"
        or exact_head.get("receipt_sha256")
        != _canonical_sha256(
            {key: value for key, value in exact_head.items() if key != "receipt_sha256"}
        )
        or exact_head.get("repository") != REPOSITORY
        or exact_head.get("requested_head_sha") != release_sha
        or exact_head.get("observed_head_sha") != release_sha
        or exact_head.get("tested_tree_sha") != release_tree_sha
        or exact_head.get("workflow_run_id") != run_id
        or exact_head.get("workflow_event") != run.get("event")
        or exact_head.get("artifact_name") != artifact.get("name")
        or exact_head.get("job_status") != "success"
        or exact_head.get("all_canonical_stages_success") is not True
        or exact_head.get("expected_stage_ids") != list(_EXPECTED_CI_STAGES)
        or exact_head.get("successful_stage_ids") != list(_EXPECTED_CI_STAGES)
        or exact_head.get("quebec_provider_lockfile_committed") is not True
        or not _SHA256.fullmatch(
            str(exact_head.get("quebec_provider_lockfile_sha256") or "")
        )
        or exact_head.get("external_action_performed") is not False
        or any(
            exact_head.get(flag) is not False
            for flag in (
                "external_authority_granted",
                "merge_authority_granted",
                "deployment_authority_granted",
                "live_model_call_authority_granted",
                "financial_authority_granted",
            )
        )
    ):
        raise NexusStagingDeploymentError("exact-head receipt is not bound to the release SHA/tree")
    if (
        isinstance(exact_head.get("workflow_run_number"), bool)
        or not isinstance(exact_head.get("workflow_run_number"), int)
        or exact_head["workflow_run_number"] <= 0
        or isinstance(exact_head.get("workflow_run_attempt"), bool)
        or not isinstance(exact_head.get("workflow_run_attempt"), int)
        or exact_head["workflow_run_attempt"] <= 0
        or not _SHA256.fullmatch(str(exact_head.get("canonical_contract_sha256") or ""))
        or not re.fullmatch(r"^[a-f0-9]{40}$", str(exact_head.get("workflow_revision") or ""))
    ):
        raise NexusStagingDeploymentError("exact-head receipt run/toolchain identity is invalid")
    toolchain = exact_head.get("toolchain")
    if (
        not isinstance(toolchain, dict)
        or set(toolchain) != {"runner", "python", "terraform", "postgres_service_image"}
        or toolchain.get("runner") != "ubuntu-24.04"
        or toolchain.get("python") != "3.12.13"
        or toolchain.get("terraform") != "1.10.5"
        or toolchain.get("postgres_service_image")
        != (
            "postgres:16.14-alpine3.24@sha256:"
            "57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777"
        )
    ):
        raise NexusStagingDeploymentError("exact-head receipt toolchain is not canonical")
    observed_stage_ids = tuple(
        record.get("stage_id") for record in stages if isinstance(record, dict)
    )
    if len(stages) != len(_EXPECTED_CI_STAGES) or observed_stage_ids != _EXPECTED_CI_STAGES:
        raise NexusStagingDeploymentError("CI admission stage set/order is incomplete")
    for record in stages:
        if not isinstance(record, dict):
            raise NexusStagingDeploymentError("CI stage receipt is invalid")
        recorded_hash = record.get("record_sha256")
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        if (
            record.get("status") != "success"
            or record.get("target_sha") != release_sha
            or record.get("tested_tree_sha") != release_tree_sha
            or record.get("run_id") != run_id
            or recorded_hash != _canonical_sha256(unsigned)
        ):
            raise NexusStagingDeploymentError(
                f"CI stage is not an exact successful receipt: {record.get('stage_id')}"
            )
    exact_stage_receipts = exact_head.get("stage_receipts")
    if (
        not isinstance(exact_stage_receipts, dict)
        or set(exact_stage_receipts) != set(_EXPECTED_CI_STAGES)
    ):
        raise NexusStagingDeploymentError("exact-head stage receipt inventory is incomplete")
    for record in stages:
        retained = exact_stage_receipts.get(record["stage_id"])
        if (
            not isinstance(retained, dict)
            or set(retained)
            != {"present", "status", "receipt_sha256", "record_sha256"}
            or retained.get("present") is not True
            or retained.get("status") != "success"
            or retained.get("record_sha256") != record.get("record_sha256")
            or not _SHA256.fullmatch(str(retained.get("receipt_sha256") or ""))
        ):
            raise NexusStagingDeploymentError(
                f"exact-head retained stage evidence is invalid: {record['stage_id']}"
            )
    runtime_smoke = container.get("runtime_smoke")
    if (
        container.get("schema_version") != "aigc.nexus-local-container-build.v2"
        or container.get("receipt_sha256")
        != _canonical_sha256(
            {key: value for key, value in container.items() if key != "receipt_sha256"}
        )
        or container.get("repository_revision") != release_sha
        or container.get("tested_tree_sha") != release_tree_sha
        or not re.fullmatch(r"^sha256:[a-f0-9]{64}$", str(container.get("image_id") or ""))
        or container.get("image_config_user") != "aigc"
        or container.get("dockerfile") != "Dockerfile.nexus"
        or container.get("release_base_image_status")
        != "immutable_default_verified"
        or container.get("python_base_image") != expected_python_base_image
        or any(
            not _SHA256.fullmatch(str(container.get(field) or ""))
            for field in (
                "source_context_sha256",
                "source_context_receipt_sha256",
                "dependency_lock_sha256",
                "dockerfile_sha256",
            )
        )
        or container.get("image_identity_labels")
        != {
            "org.opencontainers.image.revision": release_sha,
            "ai.aigc.source-context-sha256": container.get("source_context_sha256"),
        }
        or not isinstance(runtime_smoke, dict)
        or set(runtime_smoke)
        != {
            "health_contract_passed",
            "health_response_sha256",
            "non_root",
            "runtime_uid",
            "read_only_root_filesystem",
            "network_mode",
            "capabilities_dropped",
            "no_new_privileges",
            "live_provider_execution_enabled",
            "production_activation",
            "live_model_call_performed",
        }
        or runtime_smoke.get("health_contract_passed") is not True
        or not _SHA256.fullmatch(str(runtime_smoke.get("health_response_sha256") or ""))
        or runtime_smoke.get("non_root") is not True
        or isinstance(runtime_smoke.get("runtime_uid"), bool)
        or not isinstance(runtime_smoke.get("runtime_uid"), int)
        or runtime_smoke["runtime_uid"] <= 0
        or runtime_smoke.get("read_only_root_filesystem") is not True
        or runtime_smoke.get("network_mode") != "none"
        or runtime_smoke.get("capabilities_dropped") != ["ALL"]
        or runtime_smoke.get("no_new_privileges") is not True
        or runtime_smoke.get("live_provider_execution_enabled") is not False
        or runtime_smoke.get("production_activation") is not False
        or runtime_smoke.get("live_model_call_performed") is not False
        or container.get("registry_push_performed") is not False
        or container.get("cloud_build_performed") is not False
        or container.get("deployment_performed") is not False
        or container.get("external_action_performed") is not False
    ):
        raise NexusStagingDeploymentError(
            "local container receipt is not a successful exact-tree hardened smoke test"
        )
    return {
        "workflow_run_id": str(run_id),
        "workflow_run_url": str(run.get("html_url") or ""),
        "artifact_id": str(artifact["id"]),
        "artifact_digest": artifact_digest,
        "ci_admission_sha256": expected_sha256,
        "stage_count": len(stages),
        "container_receipt_sha256": _canonical_sha256(container),
    }


def _action_plan(action: str, target: str, *, prerequisites: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "action": action,
        "target": target,
        "effect": "cloud_mutation",
        "mutation_count": 1,
        "automatic_retry": False,
        "authorization_required": True,
        "prerequisites": list(prerequisites),
    }


def build_plan(payload: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    summary = validate_quebec_authorization(payload, gate="staging", manifest=manifest)
    scope = summary["authorized_scope"]
    resources = scope["resources"]
    project = summary["project_id"]
    release_sha = summary["release_sha"]
    image_base = (
        f"{REGION}-docker.pkg.dev/{project}/"
        f"{resources['artifact_registry_repository']}/aigc-nexus"
    )
    prefix = resources["artifact_registry_repository"].removesuffix("-runtime")
    migration_job = f"{prefix}-migrate-{release_sha[:8]}"
    actions = [
        _action_plan("cloud_build_submit", f"{image_base}:{release_sha}"),
        _action_plan("sbom_export", f"{image_base}@sha256:<cloud-build-result>", prerequisites=("cloud_build_submit",)),
        _action_plan("migration_job_deploy", migration_job, prerequisites=("sbom_export",)),
        _action_plan("migration_execute", migration_job, prerequisites=("migration_job_deploy",)),
        _action_plan(
            "operator_deploy",
            resources["operator_service"],
            prerequisites=("migration_execute",),
        ),
        _action_plan(
            "judge_deploy",
            resources["judge_service"],
            prerequisites=("operator_deploy",),
        ),
    ]
    return {
        "schema_version": PLAN_SCHEMA,
        "repository": REPOSITORY,
        "project_id": project,
        "region": REGION,
        "release_sha": release_sha,
        "release_tree_sha": summary["release_tree_sha"],
        "authorization_sha256": _authorization_hash(payload),
        "build_context_allowlist": str(BUILD_CONTEXT_ALLOWLIST.relative_to(ROOT)),
        "supply_chain": scope["supply_chain"],
        "build_source_bucket": resources["build_source_bucket"],
        "sbom_bucket": resources["evidence_bucket"],
        "build_tag": f"{image_base}:{release_sha}",
        "deployment_image_form": f"{image_base}@sha256:<registry-resolved>",
        "operator_service": resources["operator_service"],
        "judge_service": resources["judge_service"],
        "cloud_sql_instance": f"{project}:{REGION}:{resources['cloud_sql_instance']}",
        "network": f"{prefix}-vpc",
        "subnet": f"{prefix}-subnet",
        "vpc_egress": "private-ranges-only",
        "runtime_migration_required": True,
        "migration_before_service_deploy": True,
        "health_path": "/health",
        "readiness_path": "/ready",
        "observability_path": "/observability",
        "public_traffic": False,
        "traffic_migration": False,
        "live_model_call": False,
        "production_activation": False,
        "action_authorization": {
            "schema_version": ACTION_PERMIT_SCHEMA,
            "execution_mode": "one_action_per_invocation",
            "fresh_permit_count_per_invocation": 1,
            "total_ordered_actions": len(actions),
            "maximum_target_mutations_per_permit": 1,
            "automatic_retry": False,
            "atomic_consumption": "gcs_if_generation_match_zero",
            "durable_checkpoint_chain": ACTION_CHECKPOINT_SCHEMA,
            "predecessor_checkpoint_required_after_first_action": True,
            "reconciliation_permit_required_after_indeterminate_mutation": True,
            "monolithic_execution_enabled": False,
            "deterministic_montreal_kms_trust_root": True,
            "required_deployer_permissions": {
                "receipt_bucket": ["storage.objects.create"],
                "sbom_bucket": list(_SBOM_BUCKET_PERMISSIONS),
                "sbom_metadata_project": list(_SBOM_LOAD_PROJECT_PERMISSIONS),
                "image_pull_repository": list(_IMAGE_PULL_REPOSITORY_PERMISSIONS),
            },
        },
        "actions": actions,
    }


def _action_permit_sha256(permit: dict[str, Any]) -> str:
    return _canonical_sha256(permit)


def _action_permit_signed_payload(permit: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in permit.items() if key != "signature_b64"}


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise NexusStagingDeploymentError(f"action permit {field} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NexusStagingDeploymentError(
            f"action permit {field} must be an RFC 3339 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NexusStagingDeploymentError(f"action permit {field} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _validate_action_permit_schema(permit: dict[str, Any]) -> None:
    schema = json.loads(ACTION_PERMIT_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(permit),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise NexusStagingDeploymentError(
            f"action permit schema mismatch at {path}: {errors[0].message}"
        )


def _verify_action_permit_signature(
    permit: dict[str, Any],
    *,
    kms_public_key: KmsAuthorityPublicKey,
) -> None:
    if permit["kms_key_version"] != kms_public_key.kms_key_version:
        raise NexusStagingDeploymentError("action permit KMS key-version evidence mismatch")
    if permit["signing_algorithm"] != kms_public_key.algorithm:
        raise NexusStagingDeploymentError("action permit KMS algorithm evidence mismatch")
    try:
        public_key = serialization.load_pem_public_key(
            kms_public_key.public_key_pem.encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise NexusStagingDeploymentError("action permit KMS public key is invalid") from exc
    if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size != 2048:
        raise NexusStagingDeploymentError("action permit KMS public key must be RSA 2048")
    observed_public_key_sha256 = authority_public_key_sha256(
        kms_public_key.public_key_pem
    )
    if not hmac.compare_digest(
        observed_public_key_sha256,
        kms_public_key.public_key_sha256,
    ) or not hmac.compare_digest(
        observed_public_key_sha256,
        permit["public_key_sha256"],
    ):
        raise NexusStagingDeploymentError("action permit KMS public-key digest mismatch")
    try:
        signature = base64.b64decode(permit["signature_b64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise NexusStagingDeploymentError(
            "action permit signature is not canonical base64"
        ) from exc
    if base64.b64encode(signature).decode("ascii") != permit["signature_b64"]:
        raise NexusStagingDeploymentError("action permit signature is not canonical base64")
    digest = hashlib.sha256(
        _canonical_json_bytes(_action_permit_signed_payload(permit))
    ).digest()
    try:
        public_key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise NexusStagingDeploymentError(
            "action permit KMS signature verification failed"
        ) from exc


def _validate_document_schema(
    document: dict[str, Any],
    *,
    schema_path: Path,
    label: str,
) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise NexusStagingDeploymentError(
            f"{label} schema mismatch at {path}: {errors[0].message}"
        )


def _validate_deployment_receipt_fragment(
    value: Any,
    *,
    fragment: dict[str, Any],
    label: str,
) -> None:
    receipt_schema = json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": receipt_schema["$defs"],
        "type": "object",
        "additionalProperties": False,
        "required": ["value"],
        "properties": {"value": fragment},
    }
    errors = sorted(
        Draft202012Validator(
            wrapper,
            format_checker=FormatChecker(),
        ).iter_errors({"value": value}),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "value"
        raise NexusStagingDeploymentError(
            f"checkpoint {label} schema mismatch at {path}: {errors[0].message}"
        )


def _action_receipt_sha256(receipt: dict[str, Any]) -> str:
    return _canonical_sha256(receipt)


def _checkpoint_predecessor_binding(envelope: dict[str, Any]) -> dict[str, Any]:
    checkpoint = envelope["checkpoint"]
    action = checkpoint["completed_actions"][-1]
    return {
        "action_index": checkpoint["action_index"],
        "action_name": checkpoint["action_name"],
        "action_receipt_sha256": _action_receipt_sha256(action),
        "action_permit_sha256": action["evidence"]["action_permit_sha256"],
        "checkpoint_sha256": checkpoint["checkpoint_sha256"],
        "checkpoint_object_uri": envelope["checkpoint_object_uri"],
        "checkpoint_object_generation": envelope["checkpoint_object_generation"],
        "checkpoint_object_sha256": envelope["checkpoint_object_sha256"],
    }


def _parse_gcs_uri(value: str, *, label: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise NexusStagingDeploymentError(f"{label} is not a canonical gs:// URI") from exc
    object_name = unquote(parsed.path.lstrip("/"))
    if (
        parsed.scheme != "gs"
        or not parsed.netloc
        or not object_name
        or parsed.query
        or parsed.fragment
        or quote(object_name, safe="/-_.~") != parsed.path.lstrip("/")
        or any(part in {"", ".", ".."} for part in object_name.split("/"))
        or any(ord(character) < 0x20 or character.isspace() for character in object_name)
    ):
        raise NexusStagingDeploymentError(f"{label} is not a canonical gs:// URI")
    return parsed.netloc, object_name


def _authorized_storage_read_exact(
    *,
    bucket: str,
    object_name: str,
    generation: str,
    expected_principal: str,
) -> tuple[int, bytes]:
    """Read one immutable generation; callers validate its exact bytes."""

    session = _authorized_session_for_principal(
        expected_principal=expected_principal,
        scopes=("https://www.googleapis.com/auth/devstorage.read_only",),
    )
    response = session.request(
        "GET",
        (
            "https://storage.googleapis.com/download/storage/v1/b/"
            f"{quote(bucket, safe='')}/o/{quote(object_name, safe='')}"
        ),
        params={"alt": "media", "generation": generation},
        timeout=10,
    )
    return int(response.status_code), bytes(response.content)


def _validate_checkpoint_release_state(
    checkpoint: dict[str, Any],
    *,
    summary: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    """Validate cumulative evidence independently of the checkpoint hash."""

    action_index = checkpoint["action_index"]
    state = checkpoint["release_state"]
    if not isinstance(state, dict):
        raise NexusStagingDeploymentError("checkpoint release_state must be an object")
    required_state = {
        "ci_evidence",
        "foundation",
        "build_id",
        "build_context_manifest_sha256",
        "build_substitutions",
        "image_digest",
        "immutable_image_uri",
    }
    if action_index >= 1:
        required_state.add("artifact_security")
    if action_index >= 2:
        required_state.add("migration_job")
    if action_index >= 3:
        required_state.add("migration")
    if action_index >= 4:
        required_state.update({"targets", "readiness"})
    if set(state) != required_state:
        raise NexusStagingDeploymentError(
            "checkpoint release_state has missing or undeclared evidence fields"
        )
    scope = summary["authorized_scope"]
    supply_chain = scope["supply_chain"]
    receipt_schema = json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    context_sha = state["build_context_manifest_sha256"]
    digest = state["image_digest"]
    immutable_image = state["immutable_image_uri"]
    expected_substitutions = {
        "_IMAGE_URI": plan["build_tag"],
        "_DOCKER_BUILDER_IMAGE": supply_chain["docker_builder_image"],
        "_PYTHON_BASE_IMAGE": supply_chain["python_base_image"],
        "_RELEASE_SHA": summary["release_sha"],
        "_SOURCE_CONTEXT_SHA256": context_sha,
    }
    expected_immutable_prefix = plan["deployment_image_form"].removesuffix(
        "<registry-resolved>"
    )
    _validate_deployment_receipt_fragment(
        state["ci_evidence"],
        fragment=receipt_schema["properties"]["ci_admission"],
        label="ci_evidence",
    )
    _validate_deployment_receipt_fragment(
        state["foundation"],
        fragment=receipt_schema["properties"]["foundation"],
        label="foundation",
    )
    if (
        state["ci_evidence"].get("ci_admission_sha256")
        != scope["ci_admission_sha256"]
        or state["foundation"].get("region") != REGION
        or set(state["foundation"]["service_account_metadata_sha256"])
        != set(scope["service_accounts"].values())
        or state["foundation"].get("cloud_sql_connection_name")
        != plan["cloud_sql_instance"]
        or not isinstance(state["build_id"], str)
        or not state["build_id"]
        or not _SHA256.fullmatch(str(context_sha or ""))
        or state["build_substitutions"] != expected_substitutions
        or not _DIGEST.fullmatch(str(digest or ""))
        or not _IMMUTABLE_IMAGE.fullmatch(str(immutable_image or ""))
        or not immutable_image.startswith(expected_immutable_prefix)
        or not immutable_image.endswith("@" + digest)
    ):
        raise NexusStagingDeploymentError(
            "checkpoint build state is not bound to the exact admitted release"
        )
    completed = checkpoint["completed_actions"]
    authority_fields = {
        "action_permit_id",
        "action_permit_sha256",
        "predecessor_permit_sha256",
        "permit_consumption_uri",
        "permit_consumption_generation",
        "permit_consumption_record_sha256",
    }
    action_specific_fields = (
        {
            "build_id",
            "tagged_image_uri",
            "image_digest",
            "source_bucket",
            "service_account",
            "docker_builder_image",
            "python_base_image",
            "build_context_manifest_sha256",
            "immutable_image_uri",
        },
        {
            "immutable_image_uri",
            "sbom_generator_image",
            "sbom_source_image_uri",
            "sbom_local_sha256",
            "sbom_format",
            "sbom_package_count",
            "sbom_document_namespace_sha256",
            "sbom_reference_count",
            "sbom_metadata_sha256",
            "sbom_gcs_uri",
            "sbom_gcs_bucket",
            "sbom_gcs_location",
            "sbom_occurrence_name",
        },
        {"job_name", "immutable_image_uri"},
        {
            "job_name",
            "execution_name",
            "immutable_image_uri",
            "service_account",
            "exact_execution_log_verified",
            "migration_receipt",
        },
        {"revision", "candidate_tag", "immutable_image_uri", "readiness_verified"},
        {"revision", "candidate_tag", "immutable_image_uri", "readiness_verified"},
    )
    for index, action in enumerate(completed):
        evidence = action["evidence"]
        if set(evidence) != authority_fields | action_specific_fields[index]:
            raise NexusStagingDeploymentError(
                f"checkpoint action {index} has missing or undeclared evidence fields"
            )
        permit_id = str(evidence["action_permit_id"])
        expected_uri = (
            f"gs://{scope['resources']['receipt_bucket']}/staging-action-permits/"
            f"{summary['release_sha']}/{index:02d}-{permit_id}.json"
        )
        expected_predecessor = (
            "0" * 64
            if index == 0
            else completed[index - 1]["evidence"]["action_permit_sha256"]
        )
        if (
            not re.fullmatch(r"^ACT-[A-Z0-9_-]{8,64}$", permit_id)
            or not _SHA256.fullmatch(str(evidence["action_permit_sha256"] or ""))
            or evidence["predecessor_permit_sha256"] != expected_predecessor
            or evidence["permit_consumption_uri"] != expected_uri
            or not str(evidence["permit_consumption_generation"]).isdigit()
            or int(evidence["permit_consumption_generation"]) <= 0
            or not _SHA256.fullmatch(
                str(evidence["permit_consumption_record_sha256"] or "")
            )
        ):
            raise NexusStagingDeploymentError(
                f"checkpoint action {index} permit-consumption chain is invalid"
            )
        expected_target = (
            immutable_image if index == 1 else plan["actions"][index]["target"]
        )
        if action["target"] != expected_target:
            raise NexusStagingDeploymentError(
                f"checkpoint action {index} target is not exact"
            )
    build_evidence = completed[0]["evidence"]
    if (
        build_evidence.get("build_id") != state["build_id"]
        or build_evidence.get("tagged_image_uri") != plan["build_tag"]
        or build_evidence.get("image_digest") != digest
        or build_evidence.get("immutable_image_uri") != immutable_image
        or build_evidence.get("build_context_manifest_sha256") != context_sha
    ):
        raise NexusStagingDeploymentError("checkpoint build receipt does not match release_state")
    if action_index >= 1:
        security = state["artifact_security"]
        sbom = completed[1]["evidence"]
        required_security = {
            "provenance_sha256",
            "provenance_builder_id",
            "provenance_build_id",
            "sbom_generator_image",
            "sbom_source_image_uri",
            "sbom_local_sha256",
            "sbom_format",
            "sbom_package_count",
            "sbom_document_namespace_sha256",
            "sbom_reference_count",
            "sbom_metadata_sha256",
            "sbom_gcs_uri",
            "sbom_gcs_bucket",
            "sbom_gcs_location",
            "sbom_occurrence_name",
            "vulnerability_finding_count",
            "release_blocking_vulnerability_count",
            "vulnerability_metadata_sha256",
            "vulnerability_scan_status",
            "vulnerability_scan_note",
            "vulnerability_scan_occurrence_name",
            "vulnerability_scan_metadata_sha256",
        }
        if (
            not isinstance(security, dict)
            or set(security) != required_security
            or security.get("provenance_builder_id") != _CLOUD_BUILD_BUILDER_ID
            or security.get("provenance_build_id") != state["build_id"]
            or security.get("sbom_source_image_uri") != immutable_image
            or security.get("sbom_reference_count") != 1
            or security.get("release_blocking_vulnerability_count") != 0
            or security.get("vulnerability_scan_status") != "FINISHED_SUCCESS"
            or sbom.get("immutable_image_uri") != immutable_image
            or any(sbom.get(name) != security.get(name) for name in required_security if name.startswith("sbom_"))
        ):
            raise NexusStagingDeploymentError(
                "checkpoint SBOM/provenance/scan evidence is not exact"
            )
        _validate_deployment_receipt_fragment(
            {**supply_chain, **security},
            fragment=receipt_schema["properties"]["supply_chain"],
            label="artifact_security",
        )
    if action_index >= 2:
        migration_job = state["migration_job"]
        if (
            migration_job
            != {
                "job_name": plan["actions"][2]["target"],
                "immutable_image_uri": immutable_image,
                "service_account": scope["service_accounts"]["operator"],
            }
            or completed[2]["evidence"].get("job_name")
            != plan["actions"][2]["target"]
            or completed[2]["evidence"].get("immutable_image_uri") != immutable_image
        ):
            raise NexusStagingDeploymentError("checkpoint migration-job evidence is not exact")
    if action_index >= 3:
        migration = state["migration"]
        _validate_deployment_receipt_fragment(
            migration,
            fragment={"$ref": "#/$defs/migration"},
            label="migration",
        )
        if (
            not isinstance(migration, dict)
            or migration.get("job_name") != plan["actions"][3]["target"]
            or migration.get("immutable_image_uri") != immutable_image
            or migration.get("service_account") != scope["service_accounts"]["operator"]
            or migration.get("exact_execution_log_verified") is not True
            or migration.get("migration_receipt", {}).get(
                "runtime_control_singleton_verified"
            )
            is not True
        ):
            raise NexusStagingDeploymentError("checkpoint migration execution evidence is not exact")
    if action_index >= 4:
        roles = ("operator",) if action_index == 4 else ("operator", "judge")
        targets = state["targets"]
        readiness = state["readiness"]
        if set(targets) != set(roles) or set(readiness) != set(roles):
            raise NexusStagingDeploymentError("checkpoint service evidence role set is invalid")
        for offset, role in enumerate(roles, start=4):
            target = targets[role]
            ready = readiness[role]
            _validate_deployment_receipt_fragment(
                {**target, "readiness": ready},
                fragment={"$ref": "#/$defs/serviceTarget"},
                label=f"{role}_service",
            )
            if (
                target.get("service") != scope["resources"][f"{role}_service"]
                or target.get("runtime_role") != role
                or target.get("immutable_image_uri") != immutable_image
                or target.get("private_iam_verified") is not True
                or target.get("inherited_deployer_invoker_verified") is not True
                or ready.get("ready") is not True
                or ready.get("runtime_role") != role
                or ready.get("release_revision") != summary["release_sha"]
                or ready.get("image_digest") != digest
                or completed[offset]["evidence"].get("revision") != target.get("revision")
                or completed[offset]["evidence"].get("readiness_verified") is not True
            ):
                raise NexusStagingDeploymentError(
                    f"checkpoint {role} service evidence is not exact"
                )


def _validated_checkpoint(
    envelope: dict[str, Any] | None,
    *,
    payload: dict[str, Any],
    summary: dict[str, Any],
    plan: dict[str, Any],
    verify_remote: bool = True,
) -> dict[str, Any] | None:
    if envelope is None:
        return None
    if not isinstance(envelope, dict):
        raise NexusStagingDeploymentError("predecessor checkpoint must be a JSON object")
    _validate_document_schema(
        envelope,
        schema_path=ACTION_CHECKPOINT_SCHEMA_PATH,
        label="staging action checkpoint",
    )
    checkpoint = envelope["checkpoint"]
    unsigned = {
        key: value for key, value in checkpoint.items() if key != "checkpoint_sha256"
    }
    if checkpoint["checkpoint_sha256"] != _canonical_sha256(unsigned):
        raise NexusStagingDeploymentError("predecessor checkpoint canonical hash is invalid")
    checkpoint_bytes = _canonical_json_bytes(checkpoint)
    if envelope["checkpoint_object_sha256"] != hashlib.sha256(checkpoint_bytes).hexdigest():
        raise NexusStagingDeploymentError("predecessor checkpoint object hash is invalid")
    expected_common = {
        "repository": REPOSITORY,
        "project_id": summary["project_id"],
        "project_number": str(summary["authorized_scope"]["project_number"]),
        "region": REGION,
        "release_sha": summary["release_sha"],
        "release_tree_sha": summary["release_tree_sha"],
        "resource_manifest_sha256": payload["resource_manifest_sha256"],
        "ci_admission_sha256": summary["authorized_scope"]["ci_admission_sha256"],
        "authorization_sha256": _authorization_hash(payload),
        "plan_sha256": _canonical_sha256(plan),
        "status": "succeeded",
        "reconciliation_required": False,
    }
    for field, expected in expected_common.items():
        if checkpoint.get(field) != expected:
            raise NexusStagingDeploymentError(
                f"predecessor checkpoint is not bound to exact {field}"
            )
    action_index = checkpoint["action_index"]
    completed = checkpoint["completed_actions"]
    if (
        action_index >= len(_ACTION_NAMES)
        or checkpoint["action_name"] != _ACTION_NAMES[action_index]
        or len(completed) != action_index + 1
        or tuple(item.get("action") for item in completed)
        != _ACTION_NAMES[: action_index + 1]
        or any(
            item.get("status") != "succeeded"
            or item.get("mutation_count") != 1
            or item.get("automatic_retry") is not False
            or not isinstance(item.get("evidence"), dict)
            or not _SHA256.fullmatch(
                str(item.get("evidence", {}).get("action_permit_sha256") or "")
            )
            for item in completed
        )
    ):
        raise NexusStagingDeploymentError(
            "predecessor checkpoint action sequence is incomplete or unordered"
        )
    _validate_checkpoint_release_state(
        checkpoint,
        summary=summary,
        plan=plan,
    )
    last_action = completed[-1]
    last_action_permit = last_action["evidence"]["action_permit_sha256"]
    reconciliation_authority = checkpoint["reconciliation_authority"]
    if checkpoint["permit_kind"] == "execute":
        if (
            checkpoint["permit_sha256"] != last_action_permit
            or reconciliation_authority is not None
        ):
            raise NexusStagingDeploymentError(
                "execute checkpoint is not linked to its exact action permit"
            )
    else:
        expected_reconciliation_fields = {
            "action_permit_id",
            "action_permit_sha256",
            "predecessor_permit_sha256",
            "permit_consumption_uri",
            "permit_consumption_generation",
            "permit_consumption_record_sha256",
        }
        if (
            not isinstance(reconciliation_authority, dict)
            or set(reconciliation_authority) != expected_reconciliation_fields
            or checkpoint["permit_sha256"]
            != reconciliation_authority.get("action_permit_sha256")
            or checkpoint["permit_sha256"] == last_action_permit
            or reconciliation_authority.get("predecessor_permit_sha256")
            != (
                "0" * 64
                if action_index == 0
                else completed[-2]["evidence"]["action_permit_sha256"]
            )
            or reconciliation_authority.get("permit_consumption_uri")
            != (
                f"gs://{summary['authorized_scope']['resources']['receipt_bucket']}/"
                f"staging-action-permits/{summary['release_sha']}/{action_index:02d}-"
                f"{reconciliation_authority.get('action_permit_id')}.json"
            )
        ):
            raise NexusStagingDeploymentError(
                "reconciliation checkpoint is not linked to its fresh permit and original action"
            )
    if (action_index == 0) != (checkpoint["predecessor_checkpoint_sha256"] is None):
        raise NexusStagingDeploymentError(
            "checkpoint predecessor digest nullability does not match its action index"
        )
    terminal_receipt = checkpoint["terminal_deployment_receipt"]
    terminal_digest = checkpoint["terminal_deployment_receipt_sha256"]
    if action_index < len(_ACTION_NAMES) - 1 and (
        terminal_receipt is not None or terminal_digest is not None
    ):
        raise NexusStagingDeploymentError(
            "nonterminal predecessor checkpoint claims a deployment receipt"
        )
    if action_index == len(_ACTION_NAMES) - 1:
        if (
            not isinstance(terminal_receipt, dict)
            or not _SHA256.fullmatch(str(terminal_digest or ""))
            or terminal_receipt.get("receipt_sha256") != terminal_digest
        ):
            raise NexusStagingDeploymentError(
                "terminal predecessor checkpoint lacks its exact deployment receipt"
            )
        _validate_receipt(terminal_receipt)
    expected_object = (
        f"staging-action-checkpoints/{summary['release_sha']}/"
        f"{action_index:02d}-{checkpoint['checkpoint_sha256']}.json"
    )
    bucket, object_name = _parse_gcs_uri(
        envelope["checkpoint_object_uri"],
        label="checkpoint_object_uri",
    )
    if (
        bucket != summary["authorized_scope"]["resources"]["receipt_bucket"]
        or object_name != expected_object
    ):
        raise NexusStagingDeploymentError(
            "predecessor checkpoint URI is not the exact immutable release object"
        )
    if verify_remote:
        try:
            status_code, observed = _authorized_storage_read_exact(
                bucket=bucket,
                object_name=object_name,
                generation=envelope["checkpoint_object_generation"],
                expected_principal=summary["authorized_scope"]["service_accounts"][
                    "deployer"
                ],
            )
        except Exception as exc:
            raise NexusStagingDeploymentError(
                "predecessor checkpoint immutable generation could not be read"
            ) from exc
        if status_code != 200 or not hmac.compare_digest(observed, checkpoint_bytes):
            raise NexusStagingDeploymentError(
                "predecessor checkpoint immutable generation does not match its signed binding"
            )
    return envelope


def _expected_action_target(
    *,
    action_index: int,
    plan: dict[str, Any],
    predecessor: dict[str, Any] | None,
) -> str:
    if action_index == 1:
        if predecessor is None:
            raise NexusStagingDeploymentError("SBOM action requires the build checkpoint")
        target = predecessor["checkpoint"]["release_state"].get("immutable_image_uri")
        planned_prefix = plan["actions"][1]["target"].removesuffix(
            "<cloud-build-result>"
        )
        if (
            not isinstance(target, str)
            or not _IMMUTABLE_IMAGE.fullmatch(target)
            or not target.startswith(planned_prefix)
        ):
            raise NexusStagingDeploymentError(
                "SBOM action target is not the exact predecessor image digest"
            )
        return target
    return str(plan["actions"][action_index]["target"])


def validate_action_permit(
    raw_permit: dict[str, Any],
    *,
    payload: dict[str, Any],
    summary: dict[str, Any],
    plan: dict[str, Any],
    predecessor: dict[str, Any] | None,
    reconciliation_hint: dict[str, Any] | None = None,
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    """Validate exactly one active, predecessor-bound JIT action permit."""

    if not isinstance(raw_permit, dict):
        raise NexusStagingDeploymentError("action permit must be a JSON object")
    permit = dict(raw_permit)
    _validate_action_permit_schema(permit)
    now = authoritative_now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise NexusStagingDeploymentError("authoritative permit time must include a UTC offset")
    now = now.astimezone(timezone.utc)
    scope = summary["authorized_scope"]
    resources = scope["resources"]
    action_index = 0 if predecessor is None else predecessor["checkpoint"]["action_index"] + 1
    if action_index >= len(_ACTION_NAMES):
        raise NexusStagingDeploymentError("all six staging actions already have checkpoints")
    expected_key_version = expected_canary_authority_key_version(
        project_id=summary["project_id"],
        resource_prefix=scope["resource_prefix"],
    )
    expected_common = {
        "repository": REPOSITORY,
        "project_id": summary["project_id"],
        "project_number": str(scope["project_number"]),
        "region": REGION,
        "release_sha": summary["release_sha"],
        "release_tree_sha": summary["release_tree_sha"],
        "resource_manifest_sha256": payload["resource_manifest_sha256"],
        "ci_admission_sha256": scope["ci_admission_sha256"],
        "authorization_sha256": _authorization_hash(payload),
        "plan_sha256": _canonical_sha256(plan),
        "action_index": action_index,
        "action_name": _ACTION_NAMES[action_index],
        "target": _expected_action_target(
            action_index=action_index,
            plan=plan,
            predecessor=predecessor,
        ),
        "target_rule": _ACTION_TARGET_RULES[action_index],
        "predecessor": (
            None if predecessor is None else _checkpoint_predecessor_binding(predecessor)
        ),
        "receipt_bucket": resources["receipt_bucket"],
        "automatic_retry": False,
        "consumption_mode": "gcs_if_generation_match_zero",
        "public_traffic": False,
        "live_model_call": False,
        "production_activation": False,
        "signer_principal": scope["service_accounts"]["authority_signer"],
        "executor_principal": scope["service_accounts"]["deployer"],
        "kms_key_version": expected_key_version,
        "signing_algorithm": CANARY_AUTHORITY_ALGORITHM,
    }
    for field, expected in expected_common.items():
        if permit.get(field) != expected:
            raise NexusStagingDeploymentError(
                f"action permit is not bound to exact {field}"
            )
    if permit["permit_kind"] == "execute":
        if permit["maximum_target_mutations"] != 1 or permit["reconciliation"] is not None:
            raise NexusStagingDeploymentError("execute permit must authorize exactly one target mutation")
        if reconciliation_hint is not None:
            raise NexusStagingDeploymentError("execute permit cannot accept reconciliation evidence")
    else:
        if permit["maximum_target_mutations"] != 0 or not isinstance(
            permit["reconciliation"], dict
        ):
            raise NexusStagingDeploymentError("reconciliation permit cannot authorize a target mutation")
        if not isinstance(reconciliation_hint, dict):
            raise NexusStagingDeploymentError(
                "reconciliation permit requires the exact readback-hint document"
            )
        if permit["reconciliation"]["readback_hint_sha256"] != _canonical_sha256(
            reconciliation_hint
        ):
            raise NexusStagingDeploymentError(
                "reconciliation permit does not bind the readback-hint digest"
            )
        expected_original_predecessor = (
            "0" * 64
            if predecessor is None
            else predecessor["checkpoint"]["completed_actions"][-1]["evidence"][
                "action_permit_sha256"
            ]
        )
        if (
            permit["reconciliation"][
                "original_predecessor_action_permit_sha256"
            ]
            != expected_original_predecessor
        ):
            raise NexusStagingDeploymentError(
                "reconciliation permit does not bind the exact original predecessor action"
            )
    issued_at = _aware_datetime(permit["issued_at"], field="issued_at")
    not_before = _aware_datetime(permit["not_before"], field="not_before")
    expires_at = _aware_datetime(permit["expires_at"], field="expires_at")
    if not (issued_at <= not_before <= now < expires_at):
        raise NexusStagingDeploymentError(
            "JIT action permit is not active at this invocation"
        )
    if expires_at - not_before > _MAX_ACTION_PERMIT_ACTIVE_WINDOW:
        raise NexusStagingDeploymentError("action permit active window exceeds 15 minutes")
    if (
        now - issued_at > _MAX_ACTION_PERMIT_ISSUANCE_AGE
        or expires_at - issued_at > _MAX_ACTION_PERMIT_TOTAL_LIFETIME
    ):
        raise NexusStagingDeploymentError(
            "action permit is not a freshly issued 15-minute JIT authority"
        )
    kms_public_key = fetch_kms_authority_public_key(expected_key_version)
    _verify_action_permit_signature(permit, kms_public_key=kms_public_key)
    permit["permit_sha256"] = _action_permit_sha256(permit)
    return permit


def validate_action_permits(
    permits: Sequence[dict[str, Any]],
    *,
    payload: dict[str, Any],
    summary: dict[str, Any],
    plan: dict[str, Any],
    authoritative_now: datetime | None = None,
) -> tuple[dict[str, Any], ...]:
    """Reject the retired six-permit monolithic execution contract.

    This compatibility symbol remains so old automation fails closed with an
    actionable message instead of importing a missing function.
    """

    raise NexusStagingDeploymentError(
        "six-permit monolithic execution is disabled; use one fresh JIT permit "
        "and the exact predecessor checkpoint"
    )

    if len(permits) != len(_ACTION_NAMES):
        raise NexusStagingDeploymentError(
            "staging execution requires exactly six independently signed action permits"
        )
    now = authoritative_now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise NexusStagingDeploymentError("authoritative permit time must include a UTC offset")
    now = now.astimezone(timezone.utc)
    scope = summary["authorized_scope"]
    resources = scope["resources"]
    expected_key_version = expected_canary_authority_key_version(
        project_id=summary["project_id"],
        resource_prefix=scope["resource_prefix"],
    )
    expected_common = {
        "repository": REPOSITORY,
        "project_id": summary["project_id"],
        "project_number": str(scope["project_number"]),
        "region": REGION,
        "release_sha": summary["release_sha"],
        "release_tree_sha": summary["release_tree_sha"],
        "resource_manifest_sha256": payload["resource_manifest_sha256"],
        "ci_admission_sha256": scope["ci_admission_sha256"],
        "authorization_sha256": _authorization_hash(payload),
        "plan_sha256": _canonical_sha256(plan),
        "receipt_bucket": resources["receipt_bucket"],
        "maximum_mutations": 1,
        "automatic_retry": False,
        "consumption_mode": "gcs_if_generation_match_zero",
        "public_traffic": False,
        "live_model_call": False,
        "production_activation": False,
        "signer_principal": scope["service_accounts"]["authority_signer"],
        "executor_principal": scope["service_accounts"]["deployer"],
        "kms_key_version": expected_key_version,
        "signing_algorithm": CANARY_AUTHORITY_ALGORITHM,
    }
    seen_permit_ids: set[str] = set()
    seen_nonces: set[str] = set()
    validated: list[dict[str, Any]] = []
    first_not_before: datetime | None = None
    previous_not_before: datetime | None = None
    previous_expires_at: datetime | None = None
    for index, raw_permit in enumerate(permits):
        if not isinstance(raw_permit, dict):
            raise NexusStagingDeploymentError("each action permit must be a JSON object")
        permit = dict(raw_permit)
        _validate_action_permit_schema(permit)
        for field, expected in expected_common.items():
            if permit.get(field) != expected:
                raise NexusStagingDeploymentError(
                    f"action permit {index} is not bound to exact {field}"
                )
        action = plan["actions"][index]
        exact_action_fields = {
            "action_index": index,
            "action_name": _ACTION_NAMES[index],
            "target_rule": _ACTION_TARGET_RULES[index],
        }
        for field, expected in exact_action_fields.items():
            if permit.get(field) != expected:
                raise NexusStagingDeploymentError(
                    f"action permit {index} is not bound to exact {field}"
                )
        if permit.get("target") != action["target"]:
            raise NexusStagingDeploymentError(
                f"action permit {index} is not bound to exact target"
            )
        expected_predecessor = None
        if index:
            previous = validated[index - 1]
            expected_predecessor = {
                "action_index": index - 1,
                "action_name": _ACTION_NAMES[index - 1],
                "permit_sha256": previous["permit_sha256"],
            }
        if permit.get("predecessor") != expected_predecessor:
            raise NexusStagingDeploymentError(
                f"action permit {index} does not bind the exact predecessor permit"
            )
        if permit["permit_id"] in seen_permit_ids or permit["nonce"] in seen_nonces:
            raise NexusStagingDeploymentError("action permit IDs and nonces must be unique")
        seen_permit_ids.add(permit["permit_id"])
        seen_nonces.add(permit["nonce"])
        issued_at = _aware_datetime(permit["issued_at"], field="issued_at")
        not_before = _aware_datetime(permit["not_before"], field="not_before")
        expires_at = _aware_datetime(permit["expires_at"], field="expires_at")
        if not (issued_at <= not_before < expires_at):
            raise NexusStagingDeploymentError(
                "action permit temporal ordering must be issued_at <= not_before < expires_at"
            )
        if expires_at - not_before > _MAX_ACTION_PERMIT_ACTIVE_WINDOW:
            raise NexusStagingDeploymentError(
                "action permit active window exceeds 15 minutes"
            )
        if issued_at > now:
            raise NexusStagingDeploymentError("action permit was issued in the future")
        if not_before - issued_at > _MAX_ACTION_PERMIT_SCHEDULE_HORIZON:
            raise NexusStagingDeploymentError(
                "action permit activation exceeds the 90-minute signed schedule horizon"
            )
        if expires_at <= now:
            raise NexusStagingDeploymentError("action permit is expired")
        if index == 0:
            if not_before > now:
                raise NexusStagingDeploymentError(
                    "first action permit is not active yet"
                )
            first_not_before = not_before
        else:
            assert first_not_before is not None
            assert previous_not_before is not None
            assert previous_expires_at is not None
            if not_before < previous_not_before:
                raise NexusStagingDeploymentError(
                    "action permit activation windows are not monotonically ordered"
                )
            if not_before >= previous_expires_at:
                raise NexusStagingDeploymentError(
                    "adjacent action permit activation windows must overlap"
                )
            if expires_at - first_not_before > _MAX_ACTION_PERMIT_SCHEDULE_HORIZON:
                raise NexusStagingDeploymentError(
                    "action permit chain exceeds the 90-minute signed schedule horizon"
                )
        previous_not_before = not_before
        previous_expires_at = expires_at
        permit["permit_sha256"] = _action_permit_sha256(permit)
        validated.append(permit)

    kms_public_key = fetch_kms_authority_public_key(expected_key_version)
    for permit in validated:
        permit_without_local_digest = {
            key: value for key, value in permit.items() if key != "permit_sha256"
        }
        _verify_action_permit_signature(
            permit_without_local_digest,
            kms_public_key=kms_public_key,
        )
    return tuple(validated)


def _wait_for_action_permit_window(
    permit: dict[str, Any],
    *,
    now_fn: Callable[[], datetime] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> None:
    """Wait only for a signed activation instant; never retry a mutation.

    The validated schedule requires adjacent windows to overlap.  Therefore an
    action that arrives early can wait at most one short active window.  Any
    expiry or clock anomaly fails closed before permit consumption.
    """

    clock = now_fn or (lambda: datetime.now(timezone.utc))
    not_before = _aware_datetime(permit["not_before"], field="not_before")
    expires_at = _aware_datetime(permit["expires_at"], field="expires_at")
    first_observed = clock()
    if first_observed.tzinfo is None or first_observed.utcoffset() is None:
        raise NexusStagingDeploymentError(
            "action permit dispatch clock must include a UTC offset"
        )
    initial_wait = max(
        0.0,
        (not_before - first_observed.astimezone(timezone.utc)).total_seconds(),
    )
    monotonic_deadline = monotonic_fn() + min(
        initial_wait + _ACTION_PERMIT_WAIT_POLL_SECONDS,
        _MAX_ACTION_PERMIT_ACTIVE_WINDOW.total_seconds(),
    )
    while True:
        observed = clock()
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise NexusStagingDeploymentError(
                "action permit dispatch clock must include a UTC offset"
            )
        now = observed.astimezone(timezone.utc)
        if now >= expires_at:
            raise NexusStagingDeploymentError(
                "action permit expired before dispatch; target mutation was not sent"
            )
        remaining = (not_before - now).total_seconds()
        if remaining <= 0:
            return
        if monotonic_fn() >= monotonic_deadline:
            raise NexusStagingDeploymentError(
                "action permit activation clock did not advance within the bounded wait"
            )
        sleep_fn(min(remaining, _ACTION_PERMIT_WAIT_POLL_SECONDS))


def _authorized_storage_create_only(
    *,
    bucket: str,
    object_name: str,
    content: bytes,
    expected_principal: str,
) -> tuple[int, dict[str, Any]]:
    """Create an immutable Cloud Storage object with no application retry."""

    session = _authorized_session_for_principal(
        expected_principal=expected_principal,
        scopes=("https://www.googleapis.com/auth/devstorage.read_write",),
    )
    response = session.request(
        "POST",
        f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket, safe='')}/o",
        params={
            "uploadType": "media",
            "name": object_name,
            "ifGenerationMatch": "0",
        },
        data=content,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=10,
    )
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = {}
    return int(response.status_code), payload if isinstance(payload, dict) else {}


def _authorized_test_iam_permissions(
    *,
    url: str,
    permissions: Sequence[str],
    expected_principal: str,
) -> tuple[int, dict[str, Any]]:
    session = _authorized_session_for_principal(
        expected_principal=expected_principal,
        scopes=("https://www.googleapis.com/auth/cloud-platform",),
    )
    response = session.request(
        "POST",
        url,
        json={"permissions": list(permissions)},
        timeout=10,
    )
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = {}
    return int(response.status_code), payload if isinstance(payload, dict) else {}


def _authorized_session_for_principal(
    *,
    expected_principal: str,
    scopes: Sequence[str],
):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _default_project = google.auth.default(scopes=tuple(scopes))
    candidates = {
        str(value)
        for value in (
            getattr(credentials, "service_account_email", None),
            getattr(credentials, "signer_email", None),
            getattr(credentials, "_target_principal", None),
        )
        if value
    }
    impersonation_url = str(
        getattr(credentials, "service_account_impersonation_url", "") or ""
    )
    match = re.search(r"/serviceAccounts/([^/:]+@[^/:]+):generateAccessToken$", impersonation_url)
    if match:
        candidates.add(match.group(1))
    if candidates != {expected_principal}:
        raise NexusStagingDeploymentError(
            "ADC identity is not the exact authorized deployer service account"
        )
    return AuthorizedSession(credentials)


def _preflight_deployer_action_permissions(
    *,
    project: str,
    receipt_bucket: str,
    sbom_bucket: str,
    artifact_repository: str,
    deployer_service_account: str,
) -> dict[str, Any]:
    active_account = _run(
        ["gcloud", "config", "get-value", "account"],
        capture=True,
    )
    if active_account != deployer_service_account:
        raise NexusStagingDeploymentError(
            "active gcloud identity is not the exact authorized deployer service account"
        )
    checks = (
        (
            "receipt_bucket",
            (
                "https://storage.googleapis.com/storage/v1/b/"
                f"{quote(receipt_bucket, safe='')}/iam/testPermissions"
            ),
            ("storage.objects.create",),
        ),
        (
            "sbom_bucket",
            (
                "https://storage.googleapis.com/storage/v1/b/"
                f"{quote(sbom_bucket, safe='')}/iam/testPermissions"
            ),
            _SBOM_BUCKET_PERMISSIONS,
        ),
        (
            "sbom_metadata_project",
            (
                "https://cloudresourcemanager.googleapis.com/v1/projects/"
                f"{quote(project, safe='')}:testIamPermissions"
            ),
            _SBOM_LOAD_PROJECT_PERMISSIONS,
        ),
        (
            "image_pull_repository",
            (
                "https://artifactregistry.googleapis.com/v1/projects/"
                f"{quote(project, safe='')}/locations/{REGION}/repositories/"
                f"{quote(artifact_repository, safe='')}:testIamPermissions"
            ),
            _IMAGE_PULL_REPOSITORY_PERMISSIONS,
        ),
    )
    evidence: dict[str, Any] = {}
    for name, url, required in checks:
        try:
            status_code, response = _authorized_test_iam_permissions(
                url=url,
                permissions=required,
                expected_principal=deployer_service_account,
            )
        except Exception as exc:
            raise NexusStagingDeploymentError(
                f"{name} permission preflight could not be verified"
            ) from exc
        granted = response.get("permissions")
        if status_code != 200 or not isinstance(granted, list) or set(granted) != set(required):
            raise NexusStagingDeploymentError(
                f"{name} lacks the exact required preflight permissions"
            )
        evidence[name] = {
            "permissions": sorted(granted),
            "evidence_sha256": _canonical_sha256(response),
        }
    return evidence


def _consume_action_permit(
    permit: dict[str, Any],
    *,
    resolved_target: str | None = None,
    authoritative_now: datetime | None = None,
) -> dict[str, str]:
    """Burn one action permit atomically before its target mutation is sent."""

    now = (authoritative_now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    not_before = _aware_datetime(permit["not_before"], field="not_before")
    expires_at = _aware_datetime(permit["expires_at"], field="expires_at")
    if now < not_before:
        raise NexusStagingDeploymentError(
            "action permit is not active at dispatch; target mutation was not sent"
        )
    if now >= expires_at:
        raise NexusStagingDeploymentError(
            "action permit expired before dispatch; target mutation was not sent"
        )
    permit_sha256 = permit["permit_sha256"]
    object_name = (
        f"staging-action-permits/{permit['release_sha']}/"
        f"{permit['action_index']:02d}-{permit['permit_id']}.json"
    )
    target = resolved_target or permit["target"]
    consumption_record = {
        "schema_version": "aigc.nexus-staging-action-permit-consumption.v1",
        "permit_id": permit["permit_id"],
        "permit_sha256": permit_sha256,
        "permit_kind": permit["permit_kind"],
        "action_index": permit["action_index"],
        "action_name": permit["action_name"],
        "target_rule": permit["target_rule"],
        "resolved_target_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
        "release_sha": permit["release_sha"],
        "state": "consumed_before_dispatch",
        "maximum_target_mutations": permit["maximum_target_mutations"],
        "automatic_retry": False,
        "consumed_at": now.isoformat(),
    }
    content = _canonical_json_bytes(consumption_record)
    try:
        status_code, response = _authorized_storage_create_only(
            bucket=permit["receipt_bucket"],
            object_name=object_name,
            content=content,
            expected_principal=permit["executor_principal"],
        )
    except Exception as exc:
        raise NexusStagingMutationIndeterminate(
            "action permit consumption result is indeterminate; permit must be treated as burned"
        ) from exc
    if status_code in {409, 412}:
        raise NexusStagingPermitAlreadyConsumed(
            "action permit was already consumed; target mutation was not dispatched"
        )
    if status_code not in {200, 201}:
        raise NexusStagingMutationIndeterminate(
            "action permit consumption result is indeterminate; permit must be treated as burned"
        )
    generation = str(response.get("generation") or "")
    if (
        response.get("bucket") != permit["receipt_bucket"]
        or response.get("name") != object_name
        or not generation.isdigit()
        or int(generation) <= 0
    ):
        raise NexusStagingMutationIndeterminate(
            "action permit consumption receipt is invalid; permit must be treated as burned"
        )
    return {
        "action_permit_id": permit["permit_id"],
        "action_permit_sha256": permit_sha256,
        "predecessor_permit_sha256": (
            permit["predecessor"]["action_permit_sha256"]
            if permit["predecessor"] is not None
            else "0" * 64
        ),
        "permit_consumption_uri": f"gs://{permit['receipt_bucket']}/{object_name}",
        "permit_consumption_generation": generation,
        "permit_consumption_record_sha256": hashlib.sha256(content).hexdigest(),
    }


def _verify_original_consumption(
    permit: dict[str, Any],
    *,
    actual_target: str,
) -> dict[str, str]:
    reconciliation = permit.get("reconciliation")
    if permit.get("permit_kind") != "reconcile" or not isinstance(
        reconciliation, dict
    ):
        raise NexusStagingDeploymentError(
            "original consumption verification requires a reconciliation permit"
        )
    bucket, object_name = _parse_gcs_uri(
        reconciliation["original_consumption_uri"],
        label="original_consumption_uri",
    )
    if bucket != permit["receipt_bucket"]:
        raise NexusStagingDeploymentError(
            "original permit consumption is outside the authorized receipt bucket"
        )
    try:
        status_code, content = _authorized_storage_read_exact(
            bucket=bucket,
            object_name=object_name,
            generation=reconciliation["original_consumption_generation"],
            expected_principal=permit["executor_principal"],
        )
    except Exception as exc:
        raise NexusStagingDeploymentError(
            "original permit consumption generation could not be read"
        ) from exc
    if (
        status_code != 200
        or hashlib.sha256(content).hexdigest()
        != reconciliation["original_consumption_record_sha256"]
    ):
        raise NexusStagingDeploymentError(
            "original permit consumption record digest is invalid"
        )
    try:
        record = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NexusStagingDeploymentError(
            "original permit consumption record is not canonical JSON"
        ) from exc
    if _canonical_json_bytes(record) != content:
        raise NexusStagingDeploymentError(
            "original permit consumption record is not canonical JSON"
        )
    expected = {
        "schema_version": "aigc.nexus-staging-action-permit-consumption.v1",
        "permit_id": reconciliation["original_permit_id"],
        "permit_sha256": reconciliation["original_permit_sha256"],
        "permit_kind": "execute",
        "action_index": permit["action_index"],
        "action_name": permit["action_name"],
        "target_rule": permit["target_rule"],
        "resolved_target_sha256": hashlib.sha256(actual_target.encode("utf-8")).hexdigest(),
        "release_sha": permit["release_sha"],
        "state": "consumed_before_dispatch",
        "maximum_target_mutations": 1,
        "automatic_retry": False,
    }
    consumed_at = record.get("consumed_at") if isinstance(record, dict) else None
    if (
        not isinstance(record, dict)
        or set(record) != set(expected) | {"consumed_at"}
        or any(record.get(key) != value for key, value in expected.items())
        or not isinstance(consumed_at, str)
    ):
        raise NexusStagingDeploymentError(
            "original permit consumption record is not bound to the exact action"
        )
    _aware_datetime(consumed_at, field="consumed_at")
    expected_object = (
        f"staging-action-permits/{permit['release_sha']}/"
        f"{permit['action_index']:02d}-{reconciliation['original_permit_id']}.json"
    )
    if object_name != expected_object:
        raise NexusStagingDeploymentError(
            "original permit consumption URI is not the exact action object"
        )
    return {
        "action_permit_id": reconciliation["original_permit_id"],
        "action_permit_sha256": reconciliation["original_permit_sha256"],
        "predecessor_permit_sha256": reconciliation[
            "original_predecessor_action_permit_sha256"
        ],
        "permit_consumption_uri": reconciliation["original_consumption_uri"],
        "permit_consumption_generation": reconciliation[
            "original_consumption_generation"
        ],
        "permit_consumption_record_sha256": reconciliation[
            "original_consumption_record_sha256"
        ],
    }


def _consume_permit_for_dispatch(
    permits: Sequence[dict[str, Any]],
    *,
    action_index: int,
    completed_actions: Sequence[dict[str, Any]],
    actual_target: str,
) -> dict[str, str]:
    if len(completed_actions) != action_index:
        raise NexusStagingDeploymentError(
            "action wrapper stopped because the exact predecessor did not succeed"
        )
    permit = permits[action_index]
    if action_index == 1:
        predecessor_target = (
            completed_actions[-1].get("evidence", {}).get("immutable_image_uri")
            if completed_actions
            else None
        )
        planned_prefix = permit["target"].removesuffix("<cloud-build-result>")
        if (
            permit["target_rule"] != "verified_predecessor_image_digest"
            or predecessor_target != actual_target
            or not actual_target.startswith(planned_prefix)
            or not re.fullmatch(r".+@sha256:[a-f0-9]{64}", actual_target)
        ):
            raise NexusStagingDeploymentError(
                "derived SBOM target does not match the verified predecessor build receipt"
            )
    elif permit["target"] != actual_target:
        raise NexusStagingDeploymentError(
            "signed action permit target does not match the exact mutation target"
        )
    if action_index:
        predecessor = completed_actions[-1]
        predecessor_sha256 = predecessor["evidence"].get("action_permit_sha256")
        if predecessor_sha256 != permit["predecessor"]["permit_sha256"]:
            raise NexusStagingDeploymentError(
                "action wrapper predecessor receipt does not match the signed permit chain"
            )
    _wait_for_action_permit_window(permit)
    authority = _consume_action_permit(permit, resolved_target=actual_target)
    expires_at = _aware_datetime(permit["expires_at"], field="expires_at")
    if datetime.now(timezone.utc) >= expires_at:
        raise NexusStagingMutationIndeterminate(
            "permit expired during atomic consumption; consumption is burned and target was not dispatched"
        )
    return authority


def _authenticated_json(
    url: str,
    *,
    audience: str,
    expected_identity: str,
) -> dict[str, Any]:
    token = _run(
        [
            "gcloud", "auth", "print-identity-token",
            f"--audiences={audience}",
            "--include-email",
        ],
        capture=True,
    )
    if not token:
        raise NexusStagingDeploymentError("gcloud did not return an identity token")
    try:
        encoded_claims = token.split(".")[1]
        encoded_claims += "=" * (-len(encoded_claims) % 4)
        claims = json.loads(base64.urlsafe_b64decode(encoded_claims).decode("utf-8"))
    except (
        IndexError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as exc:
        raise NexusStagingDeploymentError("gcloud returned an invalid identity token") from exc
    if claims.get("aud") != audience or claims.get("email") != expected_identity:
        raise NexusStagingDeploymentError(
            "identity token is not bound to the exact service audience and deployer identity"
        )
    request = Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        token = ""
    if not isinstance(payload, dict):
        raise NexusStagingDeploymentError("candidate probe returned invalid JSON")
    return payload


def _verified_cloud_run_origin(value: str, *, name: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise NexusStagingDeploymentError(
            f"{name} must be an HTTPS origin without credentials, path, query, fragment, or port"
        )
    host = parsed.hostname.lower()
    if not host.endswith(".run.app"):
        raise NexusStagingDeploymentError(
            f"{name} must be a Google-managed Cloud Run origin"
        )
    return f"https://{host}", host


def _deployer_invoker_binding(
    *,
    project: str,
    deployer_service_account: str,
    service: str,
) -> bool:
    """Require the documented per-service Cloud Run IAM binding.

    Project-level ``roles/run.invoker`` conditions are intentionally rejected:
    that role also carries job execution authority, and Cloud Run invocation
    conditions do not support ``resource.name`` as a reliable service scope.
    """

    try:
        policy = json.loads(
            _run(
                [
                    "gcloud",
                    "run",
                    "services",
                    "get-iam-policy",
                    service,
                    "--project",
                    project,
                    "--region",
                    REGION,
                    "--format",
                    "json",
                ],
                capture=True,
            )
        )
    except (NexusStagingDeploymentError, json.JSONDecodeError) as exc:
        raise NexusStagingDeploymentError(
            "BLOCKED_PENDING_TRUSTED_BROKER: exact per-service Cloud Run invoker "
            "policy is not available"
        ) from exc
    expected_member = f"serviceAccount:{deployer_service_account}"
    exact = [
        binding
        for binding in policy.get("bindings") or []
        if isinstance(binding, dict)
        and binding.get("role") == "roles/run.invoker"
        and binding.get("members") == [expected_member]
        and binding.get("condition") in (None, {})
    ]
    if len(exact) != 1:
        raise NexusStagingDeploymentError(
            "BLOCKED_PENDING_TRUSTED_BROKER: deployer lacks the exact per-service "
            "private Cloud Run invoker binding"
        )
    return True


def _nested(mapping: dict[str, Any], *paths: Sequence[str]) -> Any:
    for path in paths:
        value: Any = mapping
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value is not None:
            return value
    return None


def _build_evidence(
    *,
    project: str,
    build_id: str,
    build_service_account: str,
    tagged_image: str,
    build_source_bucket: str,
    expected_substitutions: dict[str, str],
) -> dict[str, str]:
    described = json.loads(
        _run(
            [
                "gcloud", "builds", "describe", build_id,
                "--project", project,
                "--region", REGION,
                "--format", "json",
            ],
            capture=True,
        )
    )
    if described.get("id") != build_id or described.get("status") != "SUCCESS":
        raise NexusStagingDeploymentError("Cloud Build evidence does not identify a successful exact build")
    expected_account = f"projects/{project}/serviceAccounts/{build_service_account}"
    if described.get("serviceAccount") != expected_account:
        raise NexusStagingDeploymentError("Cloud Build service account does not match authorization")
    substitutions = described.get("substitutions") or {}
    if not isinstance(substitutions, dict) or any(
        substitutions.get(name) != value
        for name, value in expected_substitutions.items()
    ):
        raise NexusStagingDeploymentError(
            "Cloud Build substitutions do not match the authorized release inputs"
        )
    if _nested(described, ("options", "requestedVerifyOption")) != "VERIFIED":
        raise NexusStagingDeploymentError(
            "Cloud Build did not require verified provenance generation"
        )
    steps = described.get("steps") or []
    if (
        not isinstance(steps, list)
        or len(steps) != 1
        or not isinstance(steps[0], dict)
        or steps[0].get("name") != expected_substitutions["_DOCKER_BUILDER_IMAGE"]
    ):
        raise NexusStagingDeploymentError(
            "Cloud Build did not use the exact authorized builder image"
        )
    source_bucket = _nested(described, ("source", "storageSource", "bucket"))
    if source_bucket != build_source_bucket:
        raise NexusStagingDeploymentError("Cloud Build source bucket does not match the regional authorization")
    images = _nested(described, ("results", "images")) or []
    exact_images = [
        item for item in images
        if isinstance(item, dict) and item.get("name") == tagged_image
    ]
    if len(exact_images) != 1 or not _DIGEST.fullmatch(str(exact_images[0].get("digest") or "")):
        raise NexusStagingDeploymentError("Cloud Build result does not bind the exact tag to one digest")
    return {
        "build_id": build_id,
        "tagged_image_uri": tagged_image,
        "image_digest": str(exact_images[0]["digest"]),
        "source_bucket": build_source_bucket,
        "service_account": build_service_account,
        "docker_builder_image": expected_substitutions["_DOCKER_BUILDER_IMAGE"],
        "python_base_image": expected_substitutions["_PYTHON_BASE_IMAGE"],
    }


def _registry_digest(*, project: str, tagged_image: str, expected_digest: str) -> str:
    described = json.loads(
        _run(
            [
                "gcloud", "artifacts", "docker", "images", "describe", tagged_image,
                "--project", project,
                "--format", "json",
            ],
            capture=True,
        )
    )
    digest = _nested(
        described,
        ("image_summary", "digest"),
        ("imageSummary", "digest"),
    )
    if digest != expected_digest or not _DIGEST.fullmatch(str(digest or "")):
        raise NexusStagingDeploymentError("Artifact Registry tag/digest does not match Cloud Build evidence")
    return str(digest)


def _provenance_statement(record: dict[str, Any]) -> dict[str, Any] | None:
    build = record.get("build")
    if not isinstance(build, dict):
        return None
    statement = build.get("inTotoSlsaProvenanceV1")
    return statement if isinstance(statement, dict) else None


def _run_sbom_local(
    command: Sequence[str],
    *,
    env: dict[str, str],
    capture: bool = False,
) -> str:
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if completed.returncode != 0:
        raise NexusStagingDeploymentError(
            f"local SBOM preparation failed: {command[0]} "
            f"{command[1] if len(command) > 1 else ''}"
        )
    return completed.stdout.strip() if capture else ""


def _canonical_container_reference(value: str) -> str:
    return value.removeprefix("docker.io/")


def _require_pulled_digest(
    *,
    image: str,
    docker_env: dict[str, str],
) -> None:
    try:
        repo_digests = json.loads(
            _run_sbom_local(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format={{json .RepoDigests}}",
                    image,
                ],
                env=docker_env,
                capture=True,
            )
        )
    except (TypeError, ValueError) as exc:
        raise NexusStagingDeploymentError(
            "Docker did not return canonical repository-digest evidence"
        ) from exc
    expected = _canonical_container_reference(image)
    if not isinstance(repo_digests, list) or expected not in {
        _canonical_container_reference(value)
        for value in repo_digests
        if isinstance(value, str)
    }:
        raise NexusStagingDeploymentError(
            "pulled container content is not bound to the authorized immutable digest"
        )


def _validate_generated_spdx(
    *,
    sbom_path: Path,
    immutable_image: str,
) -> dict[str, Any]:
    if sbom_path.is_symlink() or not sbom_path.is_file():
        raise NexusStagingDeploymentError("SBOM generator did not create a regular file")
    size = sbom_path.stat().st_size
    if size <= 0 or size > _SBOM_MAX_BYTES:
        raise NexusStagingDeploymentError("generated SBOM violates the bounded file-size policy")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result

    def reject_non_finite(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    try:
        raw = sbom_path.read_bytes()
        document = json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=reject_non_finite,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise NexusStagingDeploymentError("generated SBOM is not canonical JSON") from exc
    if not isinstance(document, dict):
        raise NexusStagingDeploymentError("generated SBOM root must be an object")
    creation = document.get("creationInfo")
    creators = creation.get("creators") if isinstance(creation, dict) else None
    packages = document.get("packages")
    described = document.get("documentDescribes")
    package_items = packages if isinstance(packages, list) else []
    package_id_values = [
        package.get("SPDXID")
        for package in package_items
        if isinstance(package, dict)
    ]
    package_ids = set(package_id_values)
    namespace = document.get("documentNamespace")
    if (
        document.get("spdxVersion") not in {"SPDX-2.2", "SPDX-2.3"}
        or document.get("dataLicense") != "CC0-1.0"
        or document.get("SPDXID") != "SPDXRef-DOCUMENT"
        or document.get("name") != immutable_image
        or not isinstance(namespace, str)
        or not namespace.startswith(("https://", "urn:"))
        or not isinstance(creators, list)
        or not any(
            isinstance(creator, str) and creator.lower().startswith("tool: syft-")
            for creator in creators
        )
        or not isinstance(packages, list)
        or not packages
        or len(package_id_values) != len(packages)
        or any(
            not isinstance(package_id, str) or not package_id.startswith("SPDXRef-")
            for package_id in package_id_values
        )
        or len(package_ids) != len(package_id_values)
        or not isinstance(described, list)
        or not described
        or any(not isinstance(item, str) or item not in package_ids for item in described)
    ):
        raise NexusStagingDeploymentError(
            "generated SBOM is not a Syft-produced SPDX 2.2/2.3 document for the exact image"
        )
    return {
        "sbom_local_sha256": hashlib.sha256(raw).hexdigest(),
        "sbom_format": str(document["spdxVersion"]),
        "sbom_package_count": len(packages),
        "sbom_document_namespace_sha256": hashlib.sha256(
            namespace.encode("utf-8")
        ).hexdigest(),
    }


def _generate_pinned_sbom(
    *,
    immutable_image: str,
    generator_image: str,
    deployer_service_account: str,
    work_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    if not _IMMUTABLE_IMAGE.fullmatch(immutable_image):
        raise NexusStagingDeploymentError("SBOM source image is not immutable")
    if not _PINNED_SYFT_IMAGE.fullmatch(generator_image):
        raise NexusStagingDeploymentError(
            "SBOM generator must be an authorization-bound anchore/syft digest"
        )
    registry_host = immutable_image.split("/", 1)[0]
    input_dir = work_dir / "input"
    output_dir = work_dir / "output"
    docker_config = work_dir / "docker-config"
    input_dir.mkdir(parents=True, mode=0o755)
    output_dir.mkdir(parents=True, mode=0o733)
    docker_config.mkdir(parents=True, mode=0o700)
    input_dir.chmod(0o755)
    output_dir.chmod(0o733)
    docker_config.chmod(0o700)
    docker_env = dict(os.environ)
    docker_env["DOCKER_CONFIG"] = str(docker_config)

    _run_sbom_local(
        [
            "gcloud",
            "auth",
            "configure-docker",
            registry_host,
            "--account",
            deployer_service_account,
            "--quiet",
        ],
        env=docker_env,
    )
    for image in (immutable_image, generator_image):
        _run_sbom_local(
            ["docker", "pull", "--platform=linux/amd64", image],
            env=docker_env,
        )
        _require_pulled_digest(image=image, docker_env=docker_env)

    archive_path = input_dir / "image.tar"
    _run_sbom_local(
        [
            "docker",
            "image",
            "save",
            "--output",
            str(archive_path),
            immutable_image,
        ],
        env=docker_env,
    )
    if archive_path.is_symlink() or not archive_path.is_file():
        raise NexusStagingDeploymentError("Docker did not create the exact image archive")
    archive_path.chmod(0o444)
    sbom_path = output_dir / "sbom.spdx.json"
    _run_sbom_local(
        [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--platform=linux/amd64",
            "--network=none",
            "--read-only",
            "--cpus=2",
            "--memory=1g",
            "--memory-swap=1g",
            "--pids-limit=256",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--user=65532:65532",
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--env=SYFT_CHECK_FOR_APP_UPDATE=false",
            "--env=SYFT_CACHE_DIR=/tmp/syft",
            f"--mount=type=bind,src={input_dir},dst=/input,readonly",
            f"--mount=type=bind,src={output_dir},dst=/output",
            generator_image,
            "scan",
            "docker-archive:/input/image.tar",
            "--quiet",
            "--source-name",
            immutable_image,
            "--output",
            "spdx-json=/output/sbom.spdx.json",
        ],
        env=docker_env,
    )
    metadata = _validate_generated_spdx(
        sbom_path=sbom_path,
        immutable_image=immutable_image,
    )
    metadata.update(
        {
            "sbom_generator_image": generator_image,
            "sbom_source_image_uri": immutable_image,
        }
    )
    return sbom_path, metadata


def _list_regional_occurrences(
    *,
    project: str,
    filter_expression: str,
    expected_principal: str,
) -> list[dict[str, Any]]:
    session = _authorized_session_for_principal(
        expected_principal=expected_principal,
        scopes=("https://www.googleapis.com/auth/cloud-platform",),
    )
    url = (
        f"https://containeranalysis.{REGION}.rep.googleapis.com/v1/projects/"
        f"{quote(project, safe='')}/locations/{REGION}/occurrences"
    )
    result: list[dict[str, Any]] = []
    page_token = ""
    seen_tokens: set[str] = set()
    for _page in range(100):
        params = {"filter": filter_expression, "pageSize": "1000"}
        if page_token:
            params["pageToken"] = page_token
        response = session.request("GET", url, params=params, timeout=10)
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise NexusStagingDeploymentError(
                "regional Artifact Analysis occurrence response is not JSON"
            ) from exc
        occurrences = payload.get("occurrences", []) if isinstance(payload, dict) else None
        if int(response.status_code) != 200 or not isinstance(occurrences, list):
            raise NexusStagingDeploymentError(
                "regional Artifact Analysis occurrence query failed"
            )
        if any(not isinstance(item, dict) for item in occurrences):
            raise NexusStagingDeploymentError(
                "regional Artifact Analysis occurrence payload is invalid"
            )
        result.extend(occurrences)
        next_token = payload.get("nextPageToken")
        if next_token in (None, ""):
            return result
        if not isinstance(next_token, str) or next_token in seen_tokens:
            raise NexusStagingDeploymentError(
                "regional Artifact Analysis pagination token is invalid"
            )
        seen_tokens.add(next_token)
        page_token = next_token
    raise NexusStagingDeploymentError(
        "regional Artifact Analysis occurrence query exceeded the page bound"
    )


def _occurrences_for_exact_resource(
    *,
    project: str,
    immutable_image: str,
    filter_suffix: str,
    expected_principal: str,
) -> list[dict[str, Any]]:
    if not _IMMUTABLE_IMAGE.fullmatch(immutable_image):
        raise NexusStagingDeploymentError("Artifact Analysis resource is not immutable")
    found: dict[str, dict[str, Any]] = {}
    for resource_uri in (immutable_image, f"https://{immutable_image}"):
        records = _list_regional_occurrences(
            project=project,
            filter_expression=(
                f'resourceUrl="{resource_uri}" AND {filter_suffix}'
            ),
            expected_principal=expected_principal,
        )
        for record in records:
            name = record.get("name")
            if not isinstance(name, str) or not name:
                raise NexusStagingDeploymentError(
                    "Artifact Analysis occurrence has no immutable name"
                )
            found[name] = record
    return list(found.values())


def _resource_uri_matches(value: Any, immutable_image: str) -> bool:
    return value in {immutable_image, f"https://{immutable_image}"}


def _sbom_reference_evidence(
    *,
    project: str,
    immutable_image: str,
    image_digest: str,
    sbom_bucket: str,
    sbom_local_sha256: str,
    expected_principal: str,
) -> dict[str, Any]:
    if immutable_image.rsplit("@", 1)[-1] != image_digest:
        raise NexusStagingDeploymentError(
            "SBOM reference image URI and registry digest do not match"
        )
    if not _SHA256.fullmatch(sbom_local_sha256):
        raise NexusStagingDeploymentError("SBOM reference local SHA-256 is not canonical")
    records = _occurrences_for_exact_resource(
        project=project,
        immutable_image=immutable_image,
        filter_suffix='kind="SBOM_REFERENCE"',
        expected_principal=expected_principal,
    )
    raw_image_digest = image_digest.removeprefix("sha256:")
    expected_occurrence = re.compile(
        rf"^projects/{re.escape(project)}/locations/{REGION}/occurrences/[^/]+$"
    )
    expected_note = re.compile(
        rf"^projects/{re.escape(project)}/(?:locations/{REGION}/)?notes/[^/]+$"
    )
    matches: list[tuple[dict[str, Any], str]] = []
    for record in records:
        reference = record.get("sbomReference")
        payload = reference.get("payload") if isinstance(reference, dict) else None
        predicate = payload.get("predicate") if isinstance(payload, dict) else None
        subjects = payload.get("subject") if isinstance(payload, dict) else None
        location = predicate.get("location") if isinstance(predicate, dict) else None
        digest = predicate.get("digest") if isinstance(predicate, dict) else None
        try:
            parsed = urlsplit(location) if isinstance(location, str) else None
        except ValueError:
            parsed = None
        exact_subject = isinstance(subjects, list) and any(
            isinstance(subject, dict)
            and _resource_uri_matches(subject.get("name"), immutable_image)
            and _nested(subject, ("digest", "sha256")) == raw_image_digest
            for subject in subjects
        )
        decoded_segments = (
            unquote(parsed.path).split("/") if parsed is not None else []
        )
        decoded_path = unquote(parsed.path) if parsed is not None else ""
        exact_location = (
            parsed is not None
            and parsed.scheme == "gs"
            and parsed.netloc == sbom_bucket
            and bool(parsed.path.removeprefix("/"))
            and all(segment not in {".", ".."} for segment in decoded_segments)
            and not any(
                character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
                for character in decoded_path
            )
            and not parsed.query
            and not parsed.fragment
        )
        if (
            _resource_uri_matches(record.get("resourceUri"), immutable_image)
            and record.get("kind") == "SBOM_REFERENCE"
            and isinstance(record.get("noteName"), str)
            and expected_note.fullmatch(record["noteName"])
            and isinstance(record.get("name"), str)
            and expected_occurrence.fullmatch(record["name"])
            and isinstance(reference, dict)
            and reference.get("payloadType") == "application/vnd.in-toto+json"
            and exact_subject
            and exact_location
            and isinstance(digest, dict)
            and digest.get("sha256") == sbom_local_sha256
        ):
            matches.append((record, str(location)))
    if len(matches) != 1:
        raise NexusStagingDeploymentError(
            "exactly one regional SBOM reference must bind the image, Montréal bucket, and local SHA-256"
        )
    record, location = matches[0]
    return {
        "sbom_reference_count": 1,
        "sbom_metadata_sha256": _canonical_sha256(record),
        "sbom_gcs_uri": location,
        "sbom_gcs_bucket": sbom_bucket,
        "sbom_gcs_location": REGION,
        "sbom_occurrence_name": str(record["name"]),
    }


def _package_vulnerability_scan_evidence(
    *,
    project: str,
    immutable_image: str,
    expected_principal: str,
) -> dict[str, str]:
    records = _occurrences_for_exact_resource(
        project=project,
        immutable_image=immutable_image,
        filter_suffix=(
            'noteProjectId="goog-analysis" AND '
            'noteId="PACKAGE_VULNERABILITY"'
        ),
        expected_principal=expected_principal,
    )
    expected_name = re.compile(
        rf"^projects/{re.escape(project)}/locations/{REGION}/occurrences/[^/]+$"
    )
    matches = [
        record
        for record in records
        if _resource_uri_matches(record.get("resourceUri"), immutable_image)
        and record.get("kind") == "DISCOVERY"
        and record.get("noteName") in {
            _PACKAGE_VULNERABILITY_NOTE,
            _REGIONAL_PACKAGE_VULNERABILITY_NOTE,
        }
        and isinstance(record.get("name"), str)
        and expected_name.fullmatch(record["name"])
        and _nested(record, ("discovery", "analysisStatus")) == "FINISHED_SUCCESS"
    ]
    if len(matches) != 1:
        raise NexusStagingDeploymentError(
            "Artifact Analysis has no unique exact PACKAGE_VULNERABILITY discovery occurrence in FINISHED_SUCCESS"
        )
    record = matches[0]
    return {
        "vulnerability_scan_status": "FINISHED_SUCCESS",
        "vulnerability_scan_note": str(record["noteName"]),
        "vulnerability_scan_occurrence_name": str(record["name"]),
        "vulnerability_scan_metadata_sha256": _canonical_sha256(record),
    }


def _artifact_security_evidence(
    *,
    project: str,
    immutable_image: str,
    image_digest: str,
    build_id: str,
    expected_substitutions: dict[str, str],
    sbom_bucket: str,
    sbom_local_metadata: dict[str, Any],
    deployer_service_account: str,
) -> dict[str, Any]:
    described = json.loads(
        _run(
            [
                "gcloud", "artifacts", "docker", "images", "describe",
                immutable_image,
                "--project", project,
                "--show-provenance",
                "--format", "json",
            ],
            capture=True,
        )
    )
    if _nested(described, ("image_summary", "digest"), ("imageSummary", "digest")) != image_digest:
        raise NexusStagingDeploymentError("provenance metadata identifies another image digest")
    provenance = _nested(
        described,
        ("provenance_summary", "provenance"),
        ("provenanceSummary", "provenance"),
    ) or []
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for record in provenance if isinstance(provenance, list) else []:
        if not isinstance(record, dict):
            continue
        statement = _provenance_statement(record)
        if statement is None:
            continue
        predicate = statement.get("predicate") or {}
        build_definition = predicate.get("buildDefinition") or {}
        internal = build_definition.get("internalParameters") or {}
        system = internal.get("systemSubstitutions") or {}
        if system.get("BUILD_ID") == build_id:
            matches.append((record, statement))
    if len(matches) != 1:
        raise NexusStagingDeploymentError(
            "exactly one signed SLSA provenance record must match the Cloud Build ID"
        )
    record, statement = matches[0]
    predicate = statement.get("predicate") or {}
    build_definition = predicate.get("buildDefinition") or {}
    run_details = predicate.get("runDetails") or {}
    external = build_definition.get("externalParameters") or {}
    substitutions = external.get("substitutions") or {}
    if any(
        substitutions.get(name) != value
        for name, value in expected_substitutions.items()
    ):
        raise NexusStagingDeploymentError(
            "provenance substitutions do not match the authorized release inputs"
        )
    if build_definition.get("buildType") != "https://cloud.google.com/build/gcb-buildtypes/google-worker/v1":
        raise NexusStagingDeploymentError("provenance uses an unexpected Cloud Build type")
    if _nested(run_details, ("builder", "id")) != _CLOUD_BUILD_BUILDER_ID:
        raise NexusStagingDeploymentError("provenance uses an unexpected builder identity")
    invocation = _nested(run_details, ("metadata", "invocationId"))
    if not isinstance(invocation, str) or not invocation.endswith(f"/builds/{build_id}"):
        raise NexusStagingDeploymentError("provenance invocation does not match the exact build")
    raw_digest = image_digest.removeprefix("sha256:")
    subjects = statement.get("subject") or []
    if not any(
        isinstance(subject, dict)
        and _nested(subject, ("digest", "sha256")) == raw_digest
        for subject in subjects if isinstance(subjects, list)
    ):
        raise NexusStagingDeploymentError("provenance subject does not match the image digest")
    signatures = _nested(record, ("envelope", "signatures")) or []
    if not isinstance(signatures, list) or not signatures:
        raise NexusStagingDeploymentError("provenance has no retained signature")

    local_sha256 = sbom_local_metadata.get("sbom_local_sha256")
    if not isinstance(local_sha256, str) or not _SHA256.fullmatch(local_sha256):
        raise NexusStagingDeploymentError("local SBOM metadata has no canonical SHA-256")
    sbom_reference = _sbom_reference_evidence(
        project=project,
        immutable_image=immutable_image,
        image_digest=image_digest,
        sbom_bucket=sbom_bucket,
        sbom_local_sha256=local_sha256,
        expected_principal=deployer_service_account,
    )
    vulnerabilities = json.loads(
        _run(
            [
                "gcloud", "artifacts", "vulnerabilities", "list",
                immutable_image,
                f"--location={REGION}",
                "--project", project,
                "--format", "json",
            ],
            capture=True,
        )
    )
    if not isinstance(vulnerabilities, list):
        raise NexusStagingDeploymentError("Artifact Analysis vulnerability output is invalid")
    severities: list[str] = []
    for finding in vulnerabilities:
        if not isinstance(finding, dict):
            continue
        severity = finding.get("effectiveSeverity") or finding.get("effective_severity")
        if severity is None:
            severity = finding.get("severity")
        if isinstance(severity, str):
            severities.append(severity.upper())
    release_blocking = sorted(
        severity for severity in severities if severity in {"CRITICAL", "HIGH"}
    )
    if release_blocking:
        raise NexusStagingDeploymentError(
            "Artifact Analysis reports release-blocking vulnerabilities: "
            + ", ".join(release_blocking)
        )
    scan_evidence = _package_vulnerability_scan_evidence(
        project=project,
        immutable_image=immutable_image,
        expected_principal=deployer_service_account,
    )
    return {
        "provenance_sha256": _canonical_sha256(record),
        "provenance_builder_id": _CLOUD_BUILD_BUILDER_ID,
        "provenance_build_id": build_id,
        **sbom_local_metadata,
        **sbom_reference,
        "vulnerability_finding_count": len(vulnerabilities),
        "release_blocking_vulnerability_count": 0,
        "vulnerability_metadata_sha256": _canonical_sha256(vulnerabilities),
        **scan_evidence,
    }


def _regional_bucket(*, project: str, bucket: str) -> dict[str, str]:
    described = json.loads(
        _run(
            [
                "gcloud", "storage", "buckets", "describe", f"gs://{bucket}",
                "--project", project,
                "--format", "json",
            ],
            capture=True,
        )
    )
    observed_name = str(described.get("name") or "").removeprefix("gs://")
    observed_location = str(described.get("location") or "").lower()
    if observed_name != bucket or observed_location != REGION:
        raise NexusStagingDeploymentError("Cloud Storage bucket is not the exact Montréal resource")
    return {"name": bucket, "location": REGION}


def _foundation_evidence(
    *,
    project: str,
    repository: str,
    cloud_sql_instance: str,
    network: str,
    subnet: str,
    service_accounts: Sequence[str],
) -> dict[str, Any]:
    repository_metadata = json.loads(
        _run(
            [
                "gcloud", "artifacts", "repositories", "describe", repository,
                "--project", project,
                "--location", REGION,
                "--format", "json",
            ],
            capture=True,
        )
    )
    expected_repository_name = (
        f"projects/{project}/locations/{REGION}/repositories/{repository}"
    )
    if (
        repository_metadata.get("name") != expected_repository_name
        or repository_metadata.get("format") != "DOCKER"
        or _nested(
            repository_metadata,
            ("dockerConfig", "immutableTags"),
            ("docker_config", "immutable_tags"),
        )
        is not True
    ):
        raise NexusStagingDeploymentError(
            "Artifact Registry repository is not the exact immutable Montréal repository"
        )

    sql_metadata = json.loads(
        _run(
            [
                "gcloud", "sql", "instances", "describe", cloud_sql_instance,
                "--project", project,
                "--format", "json",
            ],
            capture=True,
        )
    )
    expected_connection = f"{project}:{REGION}:{cloud_sql_instance}"
    ip_configuration = _nested(sql_metadata, ("settings", "ipConfiguration")) or {}
    expected_network_suffix = f"/projects/{project}/global/networks/{network}"
    if (
        sql_metadata.get("name") != cloud_sql_instance
        or sql_metadata.get("project") != project
        or sql_metadata.get("region") != REGION
        or sql_metadata.get("connectionName") != expected_connection
        or ip_configuration.get("ipv4Enabled") is not False
        or not str(ip_configuration.get("privateNetwork") or "").endswith(
            expected_network_suffix
        )
    ):
        raise NexusStagingDeploymentError(
            "Cloud SQL instance is not the exact private Montréal control database"
        )

    network_metadata = json.loads(
        _run(
            [
                "gcloud", "compute", "networks", "describe", network,
                "--project", project,
                "--format", "json",
            ],
            capture=True,
        )
    )
    if (
        network_metadata.get("name") != network
        or network_metadata.get("autoCreateSubnetworks") is not False
        or network_metadata.get("routingConfig", {}).get("routingMode") != "REGIONAL"
    ):
        raise NexusStagingDeploymentError("VPC network is not the exact regional custom network")
    subnet_metadata = json.loads(
        _run(
            [
                "gcloud", "compute", "networks", "subnets", "describe", subnet,
                "--project", project,
                "--region", REGION,
                "--format", "json",
            ],
            capture=True,
        )
    )
    if (
        subnet_metadata.get("name") != subnet
        or not str(subnet_metadata.get("region") or "").endswith(
            f"/regions/{REGION}"
        )
        or not str(subnet_metadata.get("network") or "").endswith(
            f"/projects/{project}/global/networks/{network}"
        )
        or subnet_metadata.get("privateIpGoogleAccess") is not True
    ):
        raise NexusStagingDeploymentError("subnet is not the exact private Montréal subnet")

    account_hashes: dict[str, str] = {}
    for account in service_accounts:
        account_metadata = json.loads(
            _run(
                [
                    "gcloud", "iam", "service-accounts", "describe", account,
                    "--project", project,
                    "--format", "json",
                ],
                capture=True,
            )
        )
        if (
            account_metadata.get("email") != account
            or account_metadata.get("disabled") is True
            or not str(account_metadata.get("name") or "").endswith(
                f"/serviceAccounts/{account}"
            )
            or not str(account_metadata.get("uniqueId") or "").isdigit()
        ):
            raise NexusStagingDeploymentError(
                "service-account evidence does not match the authorized identity inventory"
            )
        account_hashes[account] = _canonical_sha256(account_metadata)

    return {
        "artifact_repository_sha256": _canonical_sha256(repository_metadata),
        "cloud_sql_sha256": _canonical_sha256(sql_metadata),
        "network_sha256": _canonical_sha256(network_metadata),
        "subnet_sha256": _canonical_sha256(subnet_metadata),
        "service_account_metadata_sha256": account_hashes,
        "cloud_sql_connection_name": expected_connection,
        "region": REGION,
    }


def _revision_environment(revision: dict[str, Any]) -> dict[str, str]:
    containers = _nested(
        revision,
        ("spec", "containers"),
        ("spec", "template", "spec", "containers"),
    ) or []
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(containers[0], dict):
        raise NexusStagingDeploymentError("Cloud Run revision must contain exactly one runtime container")
    environment: dict[str, str] = {}
    for item in containers[0].get("env") or []:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and "value" in item:
            environment[item["name"]] = str(item["value"])
    return environment


def _candidate_target(
    *,
    project: str,
    service: str,
    candidate_tag: str,
    immutable_image: str,
    service_account: str,
    runtime_role: str,
    release_sha: str,
    digest: str,
    authorization_sha256: str,
    expected_secret_reference: str | None,
) -> dict[str, Any]:
    described = json.loads(
        _run(
            [
                "gcloud", "run", "services", "describe", service,
                "--project", project,
                "--region", REGION,
                "--format", "json",
            ],
            capture=True,
        )
    )
    status = described.get("status") or {}
    service_url = str(status.get("url") or "")
    traffic = status.get("traffic") or []
    tagged = [
        item for item in traffic
        if isinstance(item, dict) and item.get("tag") == candidate_tag
    ]
    if len(tagged) != 1:
        raise NexusStagingDeploymentError("Cloud Run did not return one exact candidate tag")
    candidate = tagged[0]
    if candidate.get("percent") not in (None, 0):
        raise NexusStagingDeploymentError("Cloud Run candidate unexpectedly receives traffic")
    revision_name = str(candidate.get("revisionName") or "")
    if any(
        isinstance(item, dict)
        and item.get("revisionName") == revision_name
        and isinstance(item.get("percent"), (int, float))
        and item["percent"] > 0
        for item in traffic
    ):
        raise NexusStagingDeploymentError("Cloud Run candidate revision unexpectedly receives traffic")
    candidate_url = str(candidate.get("url") or "")
    if not revision_name:
        raise NexusStagingDeploymentError("Cloud Run candidate target is incomplete")
    service_url, service_host = _verified_cloud_run_origin(
        service_url,
        name="service_url",
    )
    candidate_url, candidate_host = _verified_cloud_run_origin(
        candidate_url,
        name="candidate_url",
    )
    if candidate_host != service_host and not candidate_host.endswith("---" + service_host):
        raise NexusStagingDeploymentError(
            "candidate_url is not bound to the audience Cloud Run service"
        )
    revision = json.loads(
        _run(
            [
                "gcloud", "run", "revisions", "describe", revision_name,
                "--project", project,
                "--region", REGION,
                "--format", "json",
            ],
            capture=True,
        )
    )
    observed_account = _nested(
        revision,
        ("spec", "serviceAccountName"),
        ("spec", "template", "spec", "serviceAccountName"),
    )
    containers = _nested(
        revision,
        ("spec", "containers"),
        ("spec", "template", "spec", "containers"),
    ) or []
    observed_image = containers[0].get("image") if len(containers) == 1 and isinstance(containers[0], dict) else None
    labels = _nested(revision, ("metadata", "labels")) or {}
    environment = _revision_environment(revision)
    required_environment = {
        "AIGC_ENV": "staging",
        "AIGC_PROJECT_ID": project,
        "AIGC_RUNTIME_ROLE": runtime_role,
        "AIGC_RELEASE_REVISION": release_sha,
        "AIGC_IMAGE_DIGEST": digest,
        "AIGC_REGION": REGION,
        "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256": authorization_sha256,
        "AIGC_LIVE_PROVIDER_EXECUTION_ENABLED": "false",
        "AIGC_PRODUCTION_ACTIVATION": "false",
    }
    if observed_account != service_account or observed_image != immutable_image:
        raise NexusStagingDeploymentError("Cloud Run revision identity/image does not match deployment target")
    if labels.get("aigc-release-sha") != release_sha or labels.get("aigc-runtime-role") != runtime_role:
        raise NexusStagingDeploymentError("Cloud Run revision labels do not bind release and role")
    expected_environment = dict(required_environment)
    if runtime_role == "operator" and expected_secret_reference is not None:
        expected_environment[
            "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF"
        ] = expected_secret_reference
    if environment != expected_environment:
        raise NexusStagingDeploymentError("Cloud Run revision environment does not match the exact role allowlist")
    raw_environment = containers[0].get("env") or []
    volumes = _nested(
        revision,
        ("spec", "volumes"),
        ("spec", "template", "spec", "volumes"),
    ) or []
    if any(
        isinstance(item, dict) and ("valueFrom" in item or "valueSource" in item)
        for item in raw_environment
    ) or volumes:
        raise NexusStagingDeploymentError("Cloud Run revision retains a secret source or volume")
    if runtime_role == "judge":
        annotations = _nested(revision, ("metadata", "annotations")) or {}
        forbidden_annotations = {
            "run.googleapis.com/cloudsql-instances",
            "run.googleapis.com/network-interfaces",
            "run.googleapis.com/vpc-access-connector",
        }
        if any(name in annotations for name in forbidden_annotations):
            raise NexusStagingDeploymentError("provider-free judge revision retains a VPC or Cloud SQL attachment")
    return {
        "service": service,
        "service_url": service_url,
        "candidate_tag": candidate_tag,
        "candidate_url": candidate_url,
        "revision": revision_name,
        "runtime_role": runtime_role,
        "service_account": service_account,
        "immutable_image_uri": immutable_image,
    }


def _private_service_iam(*, project: str, service: str) -> bool:
    policy = json.loads(
        _run(
            [
                "gcloud", "run", "services", "get-iam-policy", service,
                "--project", project,
                "--region", REGION,
                "--format", "json",
            ],
            capture=True,
        )
        or "{}"
    )
    for binding in policy.get("bindings") or []:
        members = binding.get("members") or [] if isinstance(binding, dict) else []
        if "allUsers" in members or "allAuthenticatedUsers" in members:
            raise NexusStagingDeploymentError("Cloud Run service IAM policy permits public invocation")
    return True


def _migration_receipt(*, project: str, job_name: str, execution_name: str) -> dict[str, Any]:
    short_execution = execution_name.rsplit("/", 1)[-1]
    if not short_execution:
        raise NexusStagingDeploymentError("Cloud Run migration execution name is empty")
    filter_expr = (
        'resource.type="cloud_run_job" '
        f'AND resource.labels.job_name="{job_name}" '
        f'AND labels."run.googleapis.com/execution_name"="{short_execution}" '
        f'AND textPayload:"{_MIGRATION_MARKER}"'
    )
    entries = json.loads(
        _run(
            [
                "gcloud", "logging", "read", filter_expr,
                "--project", project,
                "--limit", "20",
                "--order", "desc",
                "--format", "json",
            ],
            capture=True,
        )
        or "[]"
    )
    if not isinstance(entries, list):
        raise NexusStagingDeploymentError("Cloud Logging returned invalid migration evidence")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        labels = entry.get("labels") or {}
        if labels.get("run.googleapis.com/execution_name") != short_execution:
            continue
        resource_labels = _nested(entry, ("resource", "labels")) or {}
        if resource_labels.get("job_name") != job_name:
            continue
        text = str(entry.get("textPayload") or "")
        index = text.find(_MIGRATION_MARKER)
        if index < 0:
            continue
        try:
            payload = json.loads(text[index + len(_MIGRATION_MARKER):].strip())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("runtime_control_singleton_verified") is True:
            return {
                "job_name": job_name,
                "execution_name": execution_name,
                "exact_execution_log_verified": True,
                "migration_receipt": payload,
            }
    raise NexusStagingDeploymentError("exact migration execution receipt was not found")


def _migration_execution_target(
    *,
    project: str,
    execution_name: str,
    immutable_image: str,
    service_account: str,
    runtime_control_dsn_secret_ref: str,
    cloud_sql: str,
    network: str,
    subnet: str,
) -> dict[str, str]:
    short_execution = execution_name.rsplit("/", 1)[-1]
    described = json.loads(
        _run(
            [
                "gcloud", "run", "jobs", "executions", "describe", short_execution,
                "--project", project,
                "--region", REGION,
                "--format", "json",
            ],
            capture=True,
        )
    )
    observed_name = str(
        _nested(described, ("metadata", "name"), ("name",)) or ""
    )
    containers = _nested(
        described,
        ("spec", "template", "spec", "containers"),
        ("spec", "template", "containers"),
        ("template", "containers"),
    ) or []
    observed_image = containers[0].get("image") if len(containers) == 1 and isinstance(containers[0], dict) else None
    raw_environment = (
        containers[0].get("env") or []
        if len(containers) == 1 and isinstance(containers[0], dict)
        else []
    )
    if any(
        not isinstance(item, dict)
        or set(item) != {"name", "value"}
        or not isinstance(item.get("name"), str)
        or not isinstance(item.get("value"), str)
        or "valueSource" in item
        or "valueFrom" in item
        for item in raw_environment
    ):
        raise NexusStagingDeploymentError(
            "migration execution retains an inherited secret/value source"
        )
    environment = {item["name"]: item["value"] for item in raw_environment}
    if len(environment) != len(raw_environment):
        raise NexusStagingDeploymentError("migration execution contains duplicate environment names")
    observed_account = _nested(
        described,
        ("spec", "template", "spec", "serviceAccountName"),
        ("spec", "template", "serviceAccountName"),
        ("template", "serviceAccount"),
        ("template", "serviceAccountName"),
    )
    if observed_name.rsplit("/", 1)[-1] != short_execution:
        raise NexusStagingDeploymentError("migration execution description does not match the exact execution")
    if observed_image != immutable_image or observed_account != service_account:
        raise NexusStagingDeploymentError("migration execution does not match the immutable image and identity")
    if environment != {
        "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF": runtime_control_dsn_secret_ref
    }:
        raise NexusStagingDeploymentError("migration execution does not bind the exact regional secret reference")
    volume_mounts = containers[0].get("volumeMounts") or containers[0].get("volume_mounts") or []
    volumes = _nested(
        described,
        ("spec", "template", "spec", "volumes"),
        ("spec", "template", "volumes"),
        ("template", "volumes"),
        ("volumes",),
    ) or []
    if volume_mounts or volumes:
        raise NexusStagingDeploymentError("migration execution retains an arbitrary volume or mount")

    annotation_candidates = (
        _nested(described, ("metadata", "annotations")),
        _nested(described, ("spec", "template", "metadata", "annotations")),
        _nested(described, ("template", "annotations")),
    )
    annotations: dict[str, Any] = {}
    for candidate in annotation_candidates:
        if isinstance(candidate, dict):
            annotations.update(candidate)
    observed_cloud_sql = str(annotations.get("run.googleapis.com/cloudsql-instances") or "")
    if observed_cloud_sql != cloud_sql:
        raise NexusStagingDeploymentError("migration execution Cloud SQL binding is not exact")

    network_interfaces = _nested(
        described,
        ("spec", "template", "vpcAccess", "networkInterfaces"),
        ("template", "vpcAccess", "networkInterfaces"),
        ("vpcAccess", "networkInterfaces"),
    )
    if network_interfaces is None:
        raw_interfaces = annotations.get("run.googleapis.com/network-interfaces")
        try:
            network_interfaces = json.loads(raw_interfaces) if isinstance(raw_interfaces, str) else None
        except json.JSONDecodeError as exc:
            raise NexusStagingDeploymentError(
                "migration execution network binding is invalid JSON"
            ) from exc
    if (
        not isinstance(network_interfaces, list)
        or len(network_interfaces) != 1
        or not isinstance(network_interfaces[0], dict)
    ):
        raise NexusStagingDeploymentError("migration execution network binding is not exact")
    interface = network_interfaces[0]
    observed_network = str(interface.get("network") or "")
    observed_subnet = str(interface.get("subnetwork") or interface.get("subnet") or "")
    if (
        observed_network.rsplit("/", 1)[-1] != network
        or observed_subnet.rsplit("/", 1)[-1] != subnet
    ):
        raise NexusStagingDeploymentError("migration execution VPC/subnet binding is not exact")
    return {
        "execution_name": execution_name,
        "immutable_image_uri": immutable_image,
        "service_account": service_account,
    }


def _migration_job_target(
    *,
    project: str,
    job_name: str,
    immutable_image: str,
    service_account: str,
    runtime_control_dsn_secret_ref: str,
    cloud_sql: str,
    network: str,
    subnet: str,
    release_sha: str,
) -> dict[str, str]:
    """Read back the exact inert migration-job template after deploy/reconcile."""

    described = json.loads(
        _run(
            [
                "gcloud",
                "run",
                "jobs",
                "describe",
                job_name,
                "--project",
                project,
                "--region",
                REGION,
                "--format",
                "json",
            ],
            capture=True,
        )
    )
    observed_name = str(_nested(described, ("metadata", "name"), ("name",)) or "")
    template = _nested(
        described,
        ("spec", "template", "spec", "template", "spec"),
        ("spec", "template", "spec", "template"),
        ("spec", "template", "spec"),
        ("template", "template"),
        ("template",),
    )
    if not isinstance(template, dict):
        raise NexusStagingDeploymentError("migration job template is missing")
    containers = template.get("containers") or []
    container = containers[0] if len(containers) == 1 and isinstance(containers[0], dict) else None
    if observed_name.rsplit("/", 1)[-1] != job_name or container is None:
        raise NexusStagingDeploymentError("migration job readback does not match the exact job")
    observed_account = (
        template.get("serviceAccount")
        or template.get("serviceAccountName")
        or _nested(
            described,
            ("spec", "template", "spec", "serviceAccountName"),
            ("template", "serviceAccount"),
        )
    )
    raw_environment = container.get("env") or []
    if any(
        not isinstance(item, dict)
        or set(item) != {"name", "value"}
        or not isinstance(item.get("name"), str)
        or not isinstance(item.get("value"), str)
        for item in raw_environment
    ):
        raise NexusStagingDeploymentError(
            "migration job retains an inherited secret/value source"
        )
    environment = {item["name"]: item["value"] for item in raw_environment}
    if len(environment) != len(raw_environment):
        raise NexusStagingDeploymentError("migration job contains duplicate environment names")
    labels = _nested(described, ("metadata", "labels")) or {}
    if (
        observed_account != service_account
        or container.get("image") != immutable_image
        or container.get("command") not in (["python"], "python")
        or container.get("args") != ["-m", "src.operations.nexus_postgres_migrate"]
        or environment
        != {"AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF": runtime_control_dsn_secret_ref}
        or labels.get("aigc-release-sha") != release_sha
        or labels.get("aigc-purpose") != "migration"
    ):
        raise NexusStagingDeploymentError(
            "migration job image, identity, command, environment or labels are not exact"
        )
    if container.get("volumeMounts") or template.get("volumes"):
        raise NexusStagingDeploymentError("migration job retains an arbitrary volume or mount")
    max_retries = _nested(
        described,
        ("spec", "template", "spec", "template", "maxRetries"),
        ("spec", "template", "spec", "maxRetries"),
        ("template", "maxRetries"),
    )
    task_count = _nested(
        described,
        ("spec", "template", "spec", "taskCount"),
        ("template", "taskCount"),
    )
    parallelism = _nested(
        described,
        ("spec", "template", "spec", "parallelism"),
        ("template", "parallelism"),
    )
    if max_retries not in (0, "0") or task_count not in (1, "1") or parallelism not in (1, "1"):
        raise NexusStagingDeploymentError(
            "migration job retry/task concurrency is not the exact one-shot policy"
        )
    annotation_candidates = (
        _nested(described, ("metadata", "annotations")),
        _nested(described, ("spec", "template", "metadata", "annotations")),
        template.get("annotations"),
    )
    annotations: dict[str, Any] = {}
    for candidate in annotation_candidates:
        if isinstance(candidate, dict):
            annotations.update(candidate)
    if str(annotations.get("run.googleapis.com/cloudsql-instances") or "") != cloud_sql:
        raise NexusStagingDeploymentError("migration job Cloud SQL binding is not exact")
    network_interfaces: Any = _nested(
        described,
        ("spec", "template", "vpcAccess", "networkInterfaces"),
        ("template", "vpcAccess", "networkInterfaces"),
    )
    if network_interfaces is None:
        raw_interfaces = annotations.get("run.googleapis.com/network-interfaces")
        try:
            network_interfaces = json.loads(raw_interfaces) if isinstance(raw_interfaces, str) else None
        except json.JSONDecodeError as exc:
            raise NexusStagingDeploymentError(
                "migration job network binding is invalid JSON"
            ) from exc
    if (
        not isinstance(network_interfaces, list)
        or len(network_interfaces) != 1
        or not isinstance(network_interfaces[0], dict)
        or str(network_interfaces[0].get("network") or "").rsplit("/", 1)[-1] != network
        or str(
            network_interfaces[0].get("subnetwork")
            or network_interfaces[0].get("subnet")
            or ""
        ).rsplit("/", 1)[-1]
        != subnet
    ):
        raise NexusStagingDeploymentError("migration job VPC/subnet binding is not exact")
    return {
        "job_name": job_name,
        "immutable_image_uri": immutable_image,
        "service_account": service_account,
    }


def _migration_job_command(
    *,
    project: str,
    job_name: str,
    immutable_image: str,
    operator_service_account: str,
    executor_service_account: str,
    cloud_sql: str,
    network: str,
    subnet: str,
    runtime_control_dsn_secret_ref: str,
    release_sha: str,
    env_path: Path,
) -> list[str]:
    env_path.write_text(
        "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF: "
        + json.dumps(runtime_control_dsn_secret_ref)
        + "\n",
        encoding="utf-8",
    )
    return [
        "gcloud", "run", "jobs", "deploy", job_name,
        "--project", project,
        "--account", executor_service_account,
        "--region", REGION,
        "--image", immutable_image,
        "--service-account", operator_service_account,
        "--tasks", "1",
        "--parallelism", "1",
        "--max-retries", "0",
        "--task-timeout", "180s",
        "--network", network,
        "--subnet", subnet,
        "--vpc-egress", "private-ranges-only",
        "--set-cloudsql-instances", cloud_sql,
        "--command", "python",
        "--args", "-m,src.operations.nexus_postgres_migrate",
        "--env-vars-file", str(env_path),
        "--clear-secrets",
        "--clear-volumes",
        "--labels", f"aigc-release-sha={release_sha},aigc-purpose=migration",
        "--quiet",
    ]


def _service_environment(
    *,
    project: str,
    role: str,
    release_sha: str,
    digest: str,
    authorization_sha256: str,
    runtime_control_dsn_secret_ref: str | None = None,
) -> dict[str, str]:
    environment = {
        "AIGC_ENV": "staging",
        "AIGC_PROJECT_ID": project,
        "AIGC_RUNTIME_ROLE": role,
        "AIGC_RELEASE_REVISION": release_sha,
        "AIGC_IMAGE_DIGEST": digest,
        "AIGC_REGION": REGION,
        "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256": authorization_sha256,
        "AIGC_LIVE_PROVIDER_EXECUTION_ENABLED": "false",
        "AIGC_PRODUCTION_ACTIVATION": "false",
    }
    if runtime_control_dsn_secret_ref is not None:
        environment["AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF"] = runtime_control_dsn_secret_ref
    return environment


def _write_env_file(environment: dict[str, str], path: Path) -> None:
    path.write_text(
        "".join(f"{key}: {json.dumps(value)}\n" for key, value in sorted(environment.items())),
        encoding="utf-8",
    )


def _service_deploy_command(
    *,
    project: str,
    service: str,
    role: str,
    immutable_image: str,
    service_account: str,
    executor_service_account: str,
    candidate_tag: str,
    release_sha: str,
    env_path: Path,
    network: str | None = None,
    subnet: str | None = None,
    cloud_sql: str | None = None,
) -> list[str]:
    command = [
        "gcloud", "run", "deploy", service,
        "--project", project,
        "--account", executor_service_account,
        "--region", REGION,
        "--platform", "managed",
        "--image", immutable_image,
        "--service-account", service_account,
        "--no-allow-unauthenticated",
        "--no-traffic",
        "--tag", candidate_tag,
        "--min-instances", "0",
        "--max-instances", "2" if role == "operator" else "1",
        "--concurrency", "8" if role == "operator" else "4",
        "--timeout", "60",
        "--env-vars-file", str(env_path),
        "--deploy-health-check",
        "--startup-probe", "httpGet.path=/health,httpGet.port=8080,timeoutSeconds=2,periodSeconds=5,failureThreshold=24",
        "--liveness-probe", "httpGet.path=/health,httpGet.port=8080,timeoutSeconds=2,periodSeconds=10,failureThreshold=3",
        "--readiness-probe", "httpGet.path=/ready,httpGet.port=8080,timeoutSeconds=2,periodSeconds=5,failureThreshold=3",
        "--labels", f"aigc-release-sha={release_sha},aigc-runtime-role={role}",
        "--quiet",
    ]
    if role == "operator":
        if not network or not subnet or not cloud_sql:
            raise NexusStagingDeploymentError("operator deployment requires private network and Cloud SQL")
        command.extend(
            [
                "--network", network,
                "--subnet", subnet,
                "--vpc-egress", "private-ranges-only",
                "--clear-vpc-connector",
                "--set-cloudsql-instances", cloud_sql,
                "--clear-secrets",
            ]
        )
    else:
        command.extend(
            [
                "--clear-network",
                "--clear-vpc-connector",
                "--clear-cloudsql-instances",
                "--clear-secrets",
            ]
        )
    return command


def _action_receipt(action: str, target: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "target": target,
        "mutation_count": 1,
        "automatic_retry": False,
        "status": "succeeded",
        "evidence": evidence,
    }


def _validate_receipt(receipt: dict[str, Any]) -> None:
    schema = json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(receipt),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise NexusStagingDeploymentError(
            f"deployment receipt schema mismatch at {path}: {errors[0].message}"
        )
    expected_hash = _canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    if receipt.get("receipt_sha256") != expected_hash:
        raise NexusStagingDeploymentError("deployment receipt SHA-256 does not match its canonical content")


def _require_reconciliation_hint(
    hint: dict[str, Any] | None,
    *,
    action_index: int,
) -> dict[str, Any]:
    if not isinstance(hint, dict):
        raise NexusStagingDeploymentError("reconciliation readback hint must be a JSON object")
    required: dict[str, Any] = {
        "action_index": action_index,
        "action_name": _ACTION_NAMES[action_index],
    }
    expected_keys = set(required)
    if action_index == 0:
        expected_keys.add("build_id")
    if action_index == 3:
        expected_keys.add("execution_name")
    if set(hint) != expected_keys or any(hint.get(key) != value for key, value in required.items()):
        raise NexusStagingDeploymentError(
            "reconciliation readback hint is not the exact action-specific allowlist"
        )
    for key in expected_keys - set(required):
        value = hint.get(key)
        if not isinstance(value, str) or not value or len(value) > 512:
            raise NexusStagingDeploymentError(
                f"reconciliation readback hint {key} is invalid"
            )
    return hint


def _fresh_release_state(
    predecessor: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if predecessor is None:
        return [], {}
    checkpoint = predecessor["checkpoint"]
    return (
        json.loads(json.dumps(checkpoint["completed_actions"])),
        json.loads(json.dumps(checkpoint["release_state"])),
    )


def _require_release_state(
    state: dict[str, Any],
    *names: str,
) -> None:
    missing = [name for name in names if name not in state]
    if missing:
        raise NexusStagingDeploymentError(
            "predecessor checkpoint lacks required release state: " + ", ".join(missing)
        )


def _service_readback(
    *,
    project: str,
    role: str,
    service: str,
    service_account: str,
    immutable_image: str,
    release_sha: str,
    digest: str,
    authorization_sha256: str,
    runtime_control_dsn_secret_ref: str | None,
    deployer_service_account: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_tag = f"candidate-{role}-{release_sha[:8]}"
    target = _candidate_target(
        project=project,
        service=service,
        candidate_tag=candidate_tag,
        immutable_image=immutable_image,
        service_account=service_account,
        runtime_role=role,
        release_sha=release_sha,
        digest=digest,
        authorization_sha256=authorization_sha256,
        expected_secret_reference=runtime_control_dsn_secret_ref,
    )
    target["private_iam_verified"] = _private_service_iam(
        project=project,
        service=service,
    )
    target["inherited_deployer_invoker_verified"] = _deployer_invoker_binding(
        project=project,
        deployer_service_account=deployer_service_account,
        service=service,
    )
    ready = _authenticated_json(
        target["candidate_url"].rstrip("/") + "/ready",
        audience=target["service_url"],
        expected_identity=deployer_service_account,
    )
    if (
        ready.get("ready") is not True
        or ready.get("release_revision") != release_sha
        or ready.get("image_digest") != digest
        or ready.get("project_id") != project
        or ready.get("region") != REGION
        or ready.get("deployment_authorization_sha256") != authorization_sha256
        or ready.get("runtime_role") != role
        or ready.get("live_provider_execution_enabled") is not False
        or ready.get("production_activation") is not False
    ):
        raise NexusStagingDeploymentError(
            f"{role} readiness is not bound to the exact private release target"
        )
    if role == "judge" and ready.get("provider_capable") is not False:
        raise NexusStagingDeploymentError(
            "judge readiness did not prove the provider-free role"
        )
    return target, ready


def _execute_or_reconcile_action(
    *,
    permit: dict[str, Any],
    predecessor: dict[str, Any] | None,
    reconciliation_hint: dict[str, Any] | None,
    summary: dict[str, Any],
    plan: dict[str, Any],
    payload: dict[str, Any],
    ci_evidence: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str] | None]:
    """Burn one permit, perform at most one target mutation, then read it back."""

    scope = summary["authorized_scope"]
    resources = scope["resources"]
    accounts = scope["service_accounts"]
    refs = scope["exact_secret_version_refs"]
    supply_chain = scope["supply_chain"]
    project = summary["project_id"]
    release_sha = summary["release_sha"]
    repository = resources["artifact_registry_repository"]
    prefix = repository.removesuffix("-runtime")
    network = f"{prefix}-vpc"
    subnet = f"{prefix}-subnet"
    cloud_sql = f"{project}:{REGION}:{resources['cloud_sql_instance']}"
    image_base = f"{REGION}-docker.pkg.dev/{project}/{repository}/aigc-nexus"
    tagged_image = f"{image_base}:{release_sha}"
    authorization_sha256 = _authorization_hash(payload)
    action_index = permit["action_index"]
    actual_target = permit["target"]
    execute = permit["permit_kind"] == "execute"
    if not execute:
        reconciliation_hint = _require_reconciliation_hint(
            reconciliation_hint,
            action_index=action_index,
        )
    completed_actions, state = _fresh_release_state(predecessor)
    action_permission_preflight = _preflight_deployer_action_permissions(
        project=project,
        receipt_bucket=resources["receipt_bucket"],
        sbom_bucket=resources["evidence_bucket"],
        artifact_repository=repository,
        deployer_service_account=accounts["deployer"],
    )
    _regional_bucket(project=project, bucket=resources["build_source_bucket"])
    _regional_bucket(project=project, bucket=resources["evidence_bucket"])

    prepared: dict[str, Any] = {}
    temp_context: tempfile.TemporaryDirectory[str] | None = None
    temp_sbom: tempfile.TemporaryDirectory[str] | None = None
    temp_env_path: Path | None = None
    try:
        if action_index == 0:
            if predecessor is not None or completed_actions or state:
                raise NexusStagingDeploymentError("build action must start from an empty checkpoint chain")
            foundation = _foundation_evidence(
                project=project,
                repository=repository,
                cloud_sql_instance=resources["cloud_sql_instance"],
                network=network,
                subnet=subnet,
                service_accounts=tuple(accounts.values()),
            )
            foundation["action_permission_preflight_sha256"] = _canonical_sha256(
                action_permission_preflight
            )
            temp_context = tempfile.TemporaryDirectory(prefix="aigc-nexus-build-")
            context_dir = Path(temp_context.name) / "context"
            context_manifest = prepare_build_context(
                expected_sha=release_sha,
                expected_tree=summary["release_tree_sha"],
                allowlist_path=BUILD_CONTEXT_ALLOWLIST,
                output_dir=context_dir,
            )
            context_manifest_sha256 = str(context_manifest.get("manifest_sha256") or "")
            if not _SHA256.fullmatch(context_manifest_sha256):
                raise NexusStagingDeploymentError(
                    "build-context manifest did not return a canonical SHA-256"
                )
            build_substitutions = {
                "_IMAGE_URI": tagged_image,
                "_DOCKER_BUILDER_IMAGE": supply_chain["docker_builder_image"],
                "_PYTHON_BASE_IMAGE": supply_chain["python_base_image"],
                "_RELEASE_SHA": release_sha,
                "_SOURCE_CONTEXT_SHA256": context_manifest_sha256,
            }
            prepared.update(
                {
                    "foundation": foundation,
                    "context_dir": context_dir,
                    "context_manifest_sha256": context_manifest_sha256,
                    "build_substitutions": build_substitutions,
                }
            )
        elif action_index == 1:
            _require_release_state(
                state,
                "immutable_image_uri",
                "image_digest",
                "build_id",
                "build_substitutions",
            )
            temp_sbom = tempfile.TemporaryDirectory(prefix="aigc-nexus-sbom-")
            sbom_path, sbom_local_metadata = _generate_pinned_sbom(
                immutable_image=state["immutable_image_uri"],
                generator_image=supply_chain["sbom_generator_image"],
                deployer_service_account=accounts["deployer"],
                work_dir=Path(temp_sbom.name),
            )
            prepared.update(
                {"sbom_path": sbom_path, "sbom_local_metadata": sbom_local_metadata}
            )
        elif action_index == 2:
            _require_release_state(state, "immutable_image_uri")
            handle = tempfile.NamedTemporaryFile(
                "w",
                suffix=".yaml",
                encoding="utf-8",
                delete=False,
            )
            handle.close()
            temp_env_path = Path(handle.name)
        elif action_index in (3, 4, 5):
            _require_release_state(state, "immutable_image_uri", "image_digest")
            if action_index in (4, 5):
                role = "operator" if action_index == 4 else "judge"
                prepared["exact_service_invoker_verified"] = (
                    _deployer_invoker_binding(
                        project=project,
                        deployer_service_account=accounts["deployer"],
                        service=resources[f"{role}_service"],
                    )
                )

        fresh_authority = _consume_action_permit(
            permit,
            resolved_target=actual_target,
        )
        if datetime.now(timezone.utc) >= _aware_datetime(
            permit["expires_at"], field="expires_at"
        ):
            raise NexusStagingMutationIndeterminate(
                "permit expired during atomic consumption; it is burned and no target retry is allowed"
            )
        if execute:
            action_authority = fresh_authority
            reconciliation_authority: dict[str, str] | None = None
        else:
            action_authority = _verify_original_consumption(
                permit,
                actual_target=actual_target,
            )
            reconciliation_authority = fresh_authority

        try:
            if action_index == 0:
                build_substitutions = prepared["build_substitutions"]
                if execute:
                    build_id = _run(
                        [
                            "gcloud",
                            "builds",
                            "submit",
                            str(prepared["context_dir"]),
                            "--project",
                            project,
                            "--account",
                            accounts["deployer"],
                            "--region",
                            REGION,
                            "--config",
                            str(prepared["context_dir"] / "cloudbuild.nexus.yaml"),
                            "--gcs-source-staging-dir",
                            f"gs://{resources['build_source_bucket']}/nexus/{release_sha}",
                            "--service-account",
                            f"projects/{project}/serviceAccounts/{accounts['cloud_build']}",
                            "--substitutions",
                            ",".join(
                                f"{name}={value}"
                                for name, value in build_substitutions.items()
                            ),
                            "--format",
                            "value(id)",
                        ],
                        capture=True,
                        mutating=True,
                    )
                else:
                    assert reconciliation_hint is not None
                    build_id = reconciliation_hint["build_id"]
                build = _build_evidence(
                    project=project,
                    build_id=build_id,
                    build_service_account=accounts["cloud_build"],
                    tagged_image=tagged_image,
                    build_source_bucket=resources["build_source_bucket"],
                    expected_substitutions=build_substitutions,
                )
                digest = _registry_digest(
                    project=project,
                    tagged_image=tagged_image,
                    expected_digest=build["image_digest"],
                )
                immutable_image = f"{image_base}@{digest}"
                state.update(
                    {
                        "ci_evidence": ci_evidence,
                        "foundation": prepared["foundation"],
                        "build_id": build_id,
                        "build_context_manifest_sha256": prepared[
                            "context_manifest_sha256"
                        ],
                        "build_substitutions": build_substitutions,
                        "image_digest": digest,
                        "immutable_image_uri": immutable_image,
                    }
                )
                evidence = {
                    **build,
                    "build_context_manifest_sha256": prepared[
                        "context_manifest_sha256"
                    ],
                    "immutable_image_uri": immutable_image,
                    **action_authority,
                }
            elif action_index == 1:
                immutable_image = state["immutable_image_uri"]
                if execute:
                    _run(
                        [
                            "gcloud",
                            "artifacts",
                            "sbom",
                            "load",
                            f"--source={prepared['sbom_path']}",
                            f"--uri={immutable_image}",
                            f"--destination=gs://{resources['evidence_bucket']}",
                            f"--location={REGION}",
                            "--project",
                            project,
                            "--account",
                            accounts["deployer"],
                            "--quiet",
                        ],
                        mutating=True,
                    )
                artifact_security = _artifact_security_evidence(
                    project=project,
                    immutable_image=immutable_image,
                    image_digest=state["image_digest"],
                    build_id=state["build_id"],
                    expected_substitutions=state["build_substitutions"],
                    sbom_bucket=resources["evidence_bucket"],
                    sbom_local_metadata=prepared["sbom_local_metadata"],
                    deployer_service_account=accounts["deployer"],
                )
                state["artifact_security"] = artifact_security
                evidence = {
                    "immutable_image_uri": immutable_image,
                    **{
                        name: artifact_security[name]
                        for name in (
                            "sbom_generator_image",
                            "sbom_source_image_uri",
                            "sbom_local_sha256",
                            "sbom_format",
                            "sbom_package_count",
                            "sbom_document_namespace_sha256",
                            "sbom_reference_count",
                            "sbom_metadata_sha256",
                            "sbom_gcs_uri",
                            "sbom_gcs_bucket",
                            "sbom_gcs_location",
                            "sbom_occurrence_name",
                        )
                    },
                    **action_authority,
                }
            elif action_index == 2:
                job_name = permit["target"]
                if execute:
                    assert temp_env_path is not None
                    _run(
                        _migration_job_command(
                            project=project,
                            job_name=job_name,
                            immutable_image=state["immutable_image_uri"],
                            operator_service_account=accounts["operator"],
                            executor_service_account=accounts["deployer"],
                            cloud_sql=cloud_sql,
                            network=network,
                            subnet=subnet,
                            runtime_control_dsn_secret_ref=refs["runtime_control_dsn"],
                            release_sha=release_sha,
                            env_path=temp_env_path,
                        ),
                        mutating=True,
                    )
                job_target = _migration_job_target(
                    project=project,
                    job_name=job_name,
                    immutable_image=state["immutable_image_uri"],
                    service_account=accounts["operator"],
                    runtime_control_dsn_secret_ref=refs["runtime_control_dsn"],
                    cloud_sql=cloud_sql,
                    network=network,
                    subnet=subnet,
                    release_sha=release_sha,
                )
                state["migration_job"] = job_target
                evidence = {
                    "job_name": job_target["job_name"],
                    "immutable_image_uri": job_target["immutable_image_uri"],
                    **action_authority,
                }
            elif action_index == 3:
                job_name = permit["target"]
                if execute:
                    execution_result = json.loads(
                        _run(
                            [
                                "gcloud",
                                "run",
                                "jobs",
                                "execute",
                                job_name,
                                "--project",
                                project,
                                "--account",
                                accounts["deployer"],
                                "--region",
                                REGION,
                                "--wait",
                                "--format",
                                "json",
                                "--quiet",
                            ],
                            capture=True,
                            mutating=True,
                        )
                    )
                    execution_name = str(
                        _nested(execution_result, ("metadata", "name"), ("name",)) or ""
                    )
                else:
                    assert reconciliation_hint is not None
                    execution_name = reconciliation_hint["execution_name"]
                if not execution_name:
                    raise NexusStagingDeploymentError(
                        "Cloud Run did not identify the exact migration execution"
                    )
                migration_target = _migration_execution_target(
                    project=project,
                    execution_name=execution_name,
                    immutable_image=state["immutable_image_uri"],
                    service_account=accounts["operator"],
                    runtime_control_dsn_secret_ref=refs["runtime_control_dsn"],
                    cloud_sql=cloud_sql,
                    network=network,
                    subnet=subnet,
                )
                migration = _migration_receipt(
                    project=project,
                    job_name=job_name,
                    execution_name=execution_name,
                )
                migration.update(migration_target)
                state["migration"] = migration
                evidence = {**migration, **action_authority}
            else:
                role = "operator" if action_index == 4 else "judge"
                service = resources[f"{role}_service"]
                service_account = accounts[role]
                candidate_tag = f"candidate-{role}-{release_sha[:8]}"
                if execute:
                    environment = _service_environment(
                        project=project,
                        role=role,
                        release_sha=release_sha,
                        digest=state["image_digest"],
                        authorization_sha256=authorization_sha256,
                        runtime_control_dsn_secret_ref=(
                            refs["runtime_control_dsn"] if role == "operator" else None
                        ),
                    )
                    handle = tempfile.NamedTemporaryFile(
                        "w", suffix=".yaml", encoding="utf-8", delete=False
                    )
                    handle.close()
                    temp_env_path = Path(handle.name)
                    _write_env_file(environment, temp_env_path)
                    _run(
                        _service_deploy_command(
                            project=project,
                            service=service,
                            role=role,
                            immutable_image=state["immutable_image_uri"],
                            service_account=service_account,
                            executor_service_account=accounts["deployer"],
                            candidate_tag=candidate_tag,
                            release_sha=release_sha,
                            env_path=temp_env_path,
                            network=network if role == "operator" else None,
                            subnet=subnet if role == "operator" else None,
                            cloud_sql=cloud_sql if role == "operator" else None,
                        ),
                        mutating=True,
                    )
                target, ready = _service_readback(
                    project=project,
                    role=role,
                    service=service,
                    service_account=service_account,
                    immutable_image=state["immutable_image_uri"],
                    release_sha=release_sha,
                    digest=state["image_digest"],
                    authorization_sha256=authorization_sha256,
                    runtime_control_dsn_secret_ref=(
                        refs["runtime_control_dsn"] if role == "operator" else None
                    ),
                    deployer_service_account=accounts["deployer"],
                )
                state.setdefault("targets", {})[role] = target
                state.setdefault("readiness", {})[role] = ready
                evidence = {
                    "revision": target["revision"],
                    "candidate_tag": candidate_tag,
                    "immutable_image_uri": state["immutable_image_uri"],
                    "readiness_verified": True,
                    **action_authority,
                }
        except Exception as exc:
            if execute:
                raise NexusStagingMutationIndeterminate(
                    "target mutation or readback is indeterminate; the execute permit is burned, "
                    "automatic retry is forbidden, and an explicit reconciliation permit is required"
                ) from exc
            raise NexusStagingDeploymentError(
                "reconciliation did not prove exact target success; no target mutation was "
                "dispatched and a new explicit reconciliation decision is required"
            ) from exc

        completed_actions.append(
            _action_receipt(
                _ACTION_NAMES[action_index],
                actual_target,
                evidence,
            )
        )
        return completed_actions, state, reconciliation_authority
    finally:
        if temp_env_path is not None:
            temp_env_path.unlink(missing_ok=True)
        if temp_sbom is not None:
            temp_sbom.cleanup()
        if temp_context is not None:
            temp_context.cleanup()


def _assemble_resumable_deployment_receipt(
    *,
    payload: dict[str, Any],
    summary: dict[str, Any],
    completed_actions: Sequence[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    if tuple(item.get("action") for item in completed_actions) != _ACTION_NAMES:
        raise NexusStagingDeploymentError(
            "terminal receipt requires six exact successful action checkpoints"
        )
    _require_release_state(
        state,
        "ci_evidence",
        "foundation",
        "build_id",
        "build_context_manifest_sha256",
        "image_digest",
        "immutable_image_uri",
        "artifact_security",
        "migration",
        "targets",
        "readiness",
    )
    actions = json.loads(json.dumps(completed_actions))
    actions[0]["evidence"].update(state["artifact_security"])
    scope = summary["authorized_scope"]
    resources = scope["resources"]
    supply_chain = scope["supply_chain"]
    targets = state["targets"]
    readiness = state["readiness"]
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "repository": REPOSITORY,
        "project_id": summary["project_id"],
        "project_number": str(scope["project_number"]),
        "region": REGION,
        "release_sha": summary["release_sha"],
        "release_tree_sha": summary["release_tree_sha"],
        "ci_run_id": state["ci_evidence"]["workflow_run_id"],
        "ci_admission": state["ci_evidence"],
        "authorization_sha256": _authorization_hash(payload),
        "resource_manifest_sha256": payload["resource_manifest_sha256"],
        "build_id": state["build_id"],
        "build_context_manifest_sha256": state["build_context_manifest_sha256"],
        "build_source_bucket": resources["build_source_bucket"],
        "tagged_image_uri": actions[0]["target"],
        "image_digest": state["image_digest"],
        "immutable_image_uri": state["immutable_image_uri"],
        "foundation": state["foundation"],
        "supply_chain": {**supply_chain, **state["artifact_security"]},
        "operator_revision": targets["operator"]["revision"],
        "judge_revision": targets["judge"]["revision"],
        "migration": state["migration"],
        "services": {
            "operator": {**targets["operator"], "readiness": readiness["operator"]},
            "judge": {**targets["judge"], "readiness": readiness["judge"]},
        },
        "actions": actions,
        "public_traffic": False,
        "public_access_enabled": False,
        "traffic_migration_performed": False,
        "live_model_call_performed": False,
        "production_activation": False,
        "resource_locations": {
            "cloud_build": REGION,
            "artifact_registry": REGION,
            "cloud_run": REGION,
            "cloud_sql": REGION,
            "secret_manager": REGION,
            "build_source_bucket": REGION,
            "sbom_bucket": REGION,
        },
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    _validate_receipt(receipt)
    return receipt


def _publish_action_checkpoint(
    *,
    payload: dict[str, Any],
    summary: dict[str, Any],
    plan: dict[str, Any],
    permit: dict[str, Any],
    predecessor: dict[str, Any] | None,
    completed_actions: list[dict[str, Any]],
    state: dict[str, Any],
    reconciliation_authority: dict[str, str] | None,
    deployment_receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    checkpoint = {
        "schema_version": ACTION_CHECKPOINT_SCHEMA,
        "repository": REPOSITORY,
        "project_id": summary["project_id"],
        "project_number": str(summary["authorized_scope"]["project_number"]),
        "region": REGION,
        "release_sha": summary["release_sha"],
        "release_tree_sha": summary["release_tree_sha"],
        "resource_manifest_sha256": payload["resource_manifest_sha256"],
        "ci_admission_sha256": summary["authorized_scope"]["ci_admission_sha256"],
        "authorization_sha256": _authorization_hash(payload),
        "plan_sha256": _canonical_sha256(plan),
        "action_index": permit["action_index"],
        "action_name": permit["action_name"],
        "permit_kind": permit["permit_kind"],
        "permit_sha256": permit["permit_sha256"],
        "predecessor_checkpoint_sha256": (
            None
            if predecessor is None
            else predecessor["checkpoint"]["checkpoint_sha256"]
        ),
        "completed_actions": completed_actions,
        "release_state": state,
        "status": "succeeded",
        "reconciliation_required": False,
        "reconciliation_authority": reconciliation_authority,
        "terminal_deployment_receipt": deployment_receipt,
        "terminal_deployment_receipt_sha256": (
            deployment_receipt["receipt_sha256"] if deployment_receipt is not None else None
        ),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    checkpoint["checkpoint_sha256"] = _canonical_sha256(checkpoint)
    content = _canonical_json_bytes(checkpoint)
    object_name = (
        f"staging-action-checkpoints/{summary['release_sha']}/"
        f"{permit['action_index']:02d}-{checkpoint['checkpoint_sha256']}.json"
    )
    bucket = summary["authorized_scope"]["resources"]["receipt_bucket"]
    try:
        status_code, response = _authorized_storage_create_only(
            bucket=bucket,
            object_name=object_name,
            content=content,
            expected_principal=permit["executor_principal"],
        )
    except Exception as exc:
        raise NexusStagingMutationIndeterminate(
            "checkpoint publication is indeterminate after a burned permit; explicit "
            "reconciliation is required"
        ) from exc
    generation = str(response.get("generation") or "")
    if (
        status_code not in {200, 201}
        or response.get("bucket") != bucket
        or response.get("name") != object_name
        or not generation.isdigit()
        or int(generation) <= 0
    ):
        raise NexusStagingMutationIndeterminate(
            "checkpoint publication was not proven create-only after a burned permit; "
            "explicit reconciliation is required"
        )
    envelope = {
        "schema_version": ACTION_CHECKPOINT_ENVELOPE_SCHEMA,
        "checkpoint": checkpoint,
        "checkpoint_object_uri": f"gs://{bucket}/{object_name}",
        "checkpoint_object_generation": generation,
        "checkpoint_object_sha256": hashlib.sha256(content).hexdigest(),
    }
    _validate_document_schema(
        envelope,
        schema_path=ACTION_CHECKPOINT_SCHEMA_PATH,
        label="staging action checkpoint",
    )
    return envelope


def _prepare_create_only_local_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise NexusStagingDeploymentError(
            f"refusing to overwrite existing local evidence file: {path}"
        )


def _write_json_create_only(path: Path, value: dict[str, Any]) -> None:
    content = json.dumps(value, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def execute_staging_action(
    payload: dict[str, Any],
    manifest: dict[str, Any],
    *,
    ci_admission: dict[str, Any],
    action_permit: dict[str, Any],
    predecessor_checkpoint: dict[str, Any] | None,
    checkpoint_output: Path,
    deployment_receipt_output: Path,
    reconciliation_hint: dict[str, Any] | None = None,
    verify_checkpoint_remote: bool = True,
) -> dict[str, Any]:
    """Execute or reconcile one exact staging action, persist a checkpoint, stop."""

    _prepare_create_only_local_path(checkpoint_output)
    summary = validate_quebec_authorization(payload, gate="staging", manifest=manifest)
    ci_evidence = _validate_ci_admission(
        ci_admission,
        release_sha=summary["release_sha"],
        release_tree_sha=summary["release_tree_sha"],
        expected_sha256=summary["authorized_scope"]["ci_admission_sha256"],
        expected_python_base_image=summary["authorized_scope"]["supply_chain"][
            "python_base_image"
        ],
    )
    _git_identity(summary["release_sha"], summary["release_tree_sha"])
    plan = build_plan(payload, manifest)
    predecessor = _validated_checkpoint(
        predecessor_checkpoint,
        payload=payload,
        summary=summary,
        plan=plan,
        verify_remote=verify_checkpoint_remote,
    )
    permit = validate_action_permit(
        action_permit,
        payload=payload,
        summary=summary,
        plan=plan,
        predecessor=predecessor,
        reconciliation_hint=reconciliation_hint,
    )
    if permit["action_index"] == len(_ACTION_NAMES) - 1:
        _prepare_create_only_local_path(deployment_receipt_output)
    completed_actions, state, reconciliation_authority = _execute_or_reconcile_action(
        permit=permit,
        predecessor=predecessor,
        reconciliation_hint=reconciliation_hint,
        summary=summary,
        plan=plan,
        payload=payload,
        ci_evidence=ci_evidence,
    )
    deployment_receipt = None
    if permit["action_index"] == len(_ACTION_NAMES) - 1:
        deployment_receipt = _assemble_resumable_deployment_receipt(
            payload=payload,
            summary=summary,
            completed_actions=completed_actions,
            state=state,
        )
    checkpoint = _publish_action_checkpoint(
        payload=payload,
        summary=summary,
        plan=plan,
        permit=permit,
        predecessor=predecessor,
        completed_actions=completed_actions,
        state=state,
        reconciliation_authority=reconciliation_authority,
        deployment_receipt=deployment_receipt,
    )
    try:
        _write_json_create_only(checkpoint_output, checkpoint)
        if deployment_receipt is not None:
            _write_json_create_only(deployment_receipt_output, deployment_receipt)
    except Exception as exc:
        raise NexusStagingMutationIndeterminate(
            "target action and immutable remote checkpoint succeeded, but local evidence "
            "finalization failed; do not retry the target. Recover the checkpoint from "
            f"{checkpoint['checkpoint_object_uri']} generation "
            f"{checkpoint['checkpoint_object_generation']} with SHA-256 "
            f"{checkpoint['checkpoint_object_sha256']}"
        ) from exc
    return {
        "checkpoint": checkpoint,
        "deployment_receipt": deployment_receipt,
        "target_mutations_dispatched": 1 if permit["permit_kind"] == "execute" else 0,
        "automatic_retry": False,
        "next_action_requires_fresh_permit": permit["action_index"] < len(_ACTION_NAMES) - 1,
    }


def deploy(
    payload: dict[str, Any],
    manifest: dict[str, Any],
    *,
    ci_admission: dict[str, Any],
    action_permits: Sequence[dict[str, Any]],
    output: Path,
) -> dict[str, Any]:
    del payload, manifest, ci_admission, action_permits, output
    raise NexusStagingDeploymentError(
        "six-permit monolithic deployment is disabled; invoke execute_staging_action "
        "with one fresh permit and the exact predecessor checkpoint"
    )

    summary = validate_quebec_authorization(payload, gate="staging", manifest=manifest)
    ci_evidence = _validate_ci_admission(
        ci_admission,
        release_sha=summary["release_sha"],
        release_tree_sha=summary["release_tree_sha"],
        expected_sha256=summary["authorized_scope"]["ci_admission_sha256"],
        expected_python_base_image=summary["authorized_scope"]["supply_chain"]["python_base_image"],
    )
    _git_identity(summary["release_sha"], summary["release_tree_sha"])
    plan = build_plan(payload, manifest)
    permits = validate_action_permits(
        action_permits,
        payload=payload,
        summary=summary,
        plan=plan,
    )
    scope = summary["authorized_scope"]
    resources = scope["resources"]
    accounts = scope["service_accounts"]
    refs = scope["exact_secret_version_refs"]
    supply_chain = scope["supply_chain"]
    project = summary["project_id"]
    release_sha = summary["release_sha"]
    repository = resources["artifact_registry_repository"]
    prefix = repository.removesuffix("-runtime")
    network = f"{prefix}-vpc"
    subnet = f"{prefix}-subnet"
    cloud_sql = f"{project}:{REGION}:{resources['cloud_sql_instance']}"
    image_base = f"{REGION}-docker.pkg.dev/{project}/{repository}/aigc-nexus"
    tagged_image = f"{image_base}:{release_sha}"
    authorization_sha256 = _authorization_hash(payload)
    build_source_bucket = resources["build_source_bucket"]

    action_permission_preflight = _preflight_deployer_action_permissions(
        project=project,
        receipt_bucket=resources["receipt_bucket"],
        sbom_bucket=resources["evidence_bucket"],
        artifact_repository=repository,
        deployer_service_account=accounts["deployer"],
    )
    foundation = _foundation_evidence(
        project=project,
        repository=repository,
        cloud_sql_instance=resources["cloud_sql_instance"],
        network=network,
        subnet=subnet,
        service_accounts=tuple(accounts.values()),
    )
    foundation["action_permission_preflight_sha256"] = _canonical_sha256(
        action_permission_preflight
    )
    _regional_bucket(
        project=project,
        bucket=build_source_bucket,
    )
    _regional_bucket(
        project=project,
        bucket=resources["evidence_bucket"],
    )
    inherited_invoker_verified = all(
        _deployer_invoker_binding(
            project=project,
            deployer_service_account=accounts["deployer"],
            service=service,
        )
        for service in (
            resources["operator_service"],
            resources["judge_service"],
        )
    )

    action_receipts: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="aigc-nexus-build-") as temp_dir:
        context_dir = Path(temp_dir) / "context"
        context_manifest = prepare_build_context(
            expected_sha=release_sha,
            expected_tree=summary["release_tree_sha"],
            allowlist_path=BUILD_CONTEXT_ALLOWLIST,
            output_dir=context_dir,
        )
        context_manifest_sha256 = str(context_manifest.get("manifest_sha256") or "")
        if not _SHA256.fullmatch(context_manifest_sha256):
            raise NexusStagingDeploymentError("build-context manifest did not return a canonical SHA-256")
        build_substitutions = {
            "_IMAGE_URI": tagged_image,
            "_DOCKER_BUILDER_IMAGE": supply_chain["docker_builder_image"],
            "_PYTHON_BASE_IMAGE": supply_chain["python_base_image"],
            "_RELEASE_SHA": release_sha,
            "_SOURCE_CONTEXT_SHA256": context_manifest_sha256,
        }
        build_service_account = f"projects/{project}/serviceAccounts/{accounts['cloud_build']}"
        build_authority = _consume_permit_for_dispatch(
            permits,
            action_index=0,
            completed_actions=action_receipts,
            actual_target=tagged_image,
        )
        build_id = _run(
            [
                "gcloud", "builds", "submit", str(context_dir),
                "--project", project,
                "--account", accounts["deployer"],
                "--region", REGION,
                "--config", str(context_dir / "cloudbuild.nexus.yaml"),
                "--gcs-source-staging-dir", f"gs://{build_source_bucket}/nexus/{release_sha}",
                "--service-account", build_service_account,
                "--substitutions", ",".join(
                    f"{name}={value}"
                    for name, value in build_substitutions.items()
                ),
                "--format", "value(id)",
            ],
            capture=True,
            mutating=True,
        )
        build = _build_evidence(
            project=project,
            build_id=build_id,
            build_service_account=accounts["cloud_build"],
            tagged_image=tagged_image,
            build_source_bucket=build_source_bucket,
            expected_substitutions=build_substitutions,
        )
        digest = _registry_digest(
            project=project,
            tagged_image=tagged_image,
            expected_digest=build["image_digest"],
        )
        immutable_image = f"{image_base}@{digest}"
        action_receipts.append(
            _action_receipt(
                "cloud_build_submit",
                tagged_image,
                {
                    **build,
                    "build_context_manifest_sha256": context_manifest_sha256,
                    "immutable_image_uri": immutable_image,
                    **build_authority,
                },
            )
        )

    with tempfile.TemporaryDirectory(prefix="aigc-nexus-sbom-") as sbom_temp:
        sbom_path, sbom_local_metadata = _generate_pinned_sbom(
            immutable_image=immutable_image,
            generator_image=supply_chain["sbom_generator_image"],
            deployer_service_account=accounts["deployer"],
            work_dir=Path(sbom_temp),
        )
        sbom_authority = _consume_permit_for_dispatch(
            permits,
            action_index=1,
            completed_actions=action_receipts,
            actual_target=immutable_image,
        )
        _run(
            [
                "gcloud", "artifacts", "sbom", "load",
                f"--source={sbom_path}",
                f"--uri={immutable_image}",
                f"--destination=gs://{resources['evidence_bucket']}",
                f"--location={REGION}",
                "--project", project,
                "--account", accounts["deployer"],
                "--quiet",
            ],
            mutating=True,
        )
        artifact_security = _artifact_security_evidence(
            project=project,
            immutable_image=immutable_image,
            image_digest=digest,
            build_id=build_id,
            expected_substitutions=build_substitutions,
            sbom_bucket=resources["evidence_bucket"],
            sbom_local_metadata=sbom_local_metadata,
            deployer_service_account=accounts["deployer"],
        )
    action_receipts[0]["evidence"].update(artifact_security)
    action_receipts.append(
        _action_receipt(
            "sbom_export",
            immutable_image,
            {
                "immutable_image_uri": immutable_image,
                **{
                    name: artifact_security[name]
                    for name in (
                        "sbom_generator_image",
                        "sbom_source_image_uri",
                        "sbom_local_sha256",
                        "sbom_format",
                        "sbom_package_count",
                        "sbom_document_namespace_sha256",
                        "sbom_reference_count",
                        "sbom_metadata_sha256",
                        "sbom_gcs_uri",
                        "sbom_gcs_bucket",
                        "sbom_gcs_location",
                        "sbom_occurrence_name",
                    )
                },
                **sbom_authority,
            },
        )
    )

    job_name = f"{prefix}-migrate-{release_sha[:8]}"
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
        migration_env_path = Path(handle.name)
    try:
        migration_deploy_authority = _consume_permit_for_dispatch(
            permits,
            action_index=2,
            completed_actions=action_receipts,
            actual_target=job_name,
        )
        _run(
            _migration_job_command(
                project=project,
                job_name=job_name,
                immutable_image=immutable_image,
                operator_service_account=accounts["operator"],
                executor_service_account=accounts["deployer"],
                cloud_sql=cloud_sql,
                network=network,
                subnet=subnet,
                runtime_control_dsn_secret_ref=refs["runtime_control_dsn"],
                release_sha=release_sha,
                env_path=migration_env_path,
            ),
            mutating=True,
        )
    finally:
        migration_env_path.unlink(missing_ok=True)
    action_receipts.append(
        _action_receipt(
            "migration_job_deploy",
            job_name,
            {
                "job_name": job_name,
                "immutable_image_uri": immutable_image,
                **migration_deploy_authority,
            },
        )
    )
    migration_execute_authority = _consume_permit_for_dispatch(
        permits,
        action_index=3,
        completed_actions=action_receipts,
        actual_target=job_name,
    )
    execution_result = json.loads(
        _run(
        [
            "gcloud", "run", "jobs", "execute", job_name,
            "--project", project,
            "--account", accounts["deployer"],
            "--region", REGION,
            "--wait",
            "--format", "json",
            "--quiet",
        ],
        capture=True,
        mutating=True,
        )
    )
    execution_name = str(
        _nested(execution_result, ("metadata", "name"), ("name",)) or ""
    )
    if not execution_name:
        raise NexusStagingDeploymentError("Cloud Run did not return the exact migration execution name")
    migration_target = _migration_execution_target(
        project=project,
        execution_name=execution_name,
        immutable_image=immutable_image,
        service_account=accounts["operator"],
        runtime_control_dsn_secret_ref=refs["runtime_control_dsn"],
        cloud_sql=cloud_sql,
        network=network,
        subnet=subnet,
    )
    migration = _migration_receipt(
        project=project,
        job_name=job_name,
        execution_name=execution_name,
    )
    migration.update(migration_target)
    action_receipts.append(
        _action_receipt(
            "migration_execute",
            execution_name,
            {**migration, **migration_execute_authority},
        )
    )

    targets: dict[str, dict[str, Any]] = {}
    readiness: dict[str, dict[str, Any]] = {}
    for role, service, service_account in (
        ("operator", resources["operator_service"], accounts["operator"]),
        ("judge", resources["judge_service"], accounts["judge"]),
    ):
        candidate_tag = f"candidate-{role}-{release_sha[:8]}"
        environment = _service_environment(
            project=project,
            role=role,
            release_sha=release_sha,
            digest=digest,
            authorization_sha256=authorization_sha256,
            runtime_control_dsn_secret_ref=(refs["runtime_control_dsn"] if role == "operator" else None),
        )
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
            env_path = Path(handle.name)
        try:
            _write_env_file(environment, env_path)
            action_index = 4 if role == "operator" else 5
            service_authority = _consume_permit_for_dispatch(
                permits,
                action_index=action_index,
                completed_actions=action_receipts,
                actual_target=service,
            )
            _run(
                _service_deploy_command(
                    project=project,
                    service=service,
                    role=role,
                    immutable_image=immutable_image,
                    service_account=service_account,
                    executor_service_account=accounts["deployer"],
                    candidate_tag=candidate_tag,
                    release_sha=release_sha,
                    env_path=env_path,
                    network=network if role == "operator" else None,
                    subnet=subnet if role == "operator" else None,
                    cloud_sql=cloud_sql if role == "operator" else None,
                ),
                mutating=True,
            )
        finally:
            env_path.unlink(missing_ok=True)
        target = _candidate_target(
            project=project,
            service=service,
            candidate_tag=candidate_tag,
            immutable_image=immutable_image,
            service_account=service_account,
            runtime_role=role,
            release_sha=release_sha,
            digest=digest,
            authorization_sha256=authorization_sha256,
            expected_secret_reference=(refs["runtime_control_dsn"] if role == "operator" else None),
        )
        target["private_iam_verified"] = _private_service_iam(
            project=project,
            service=service,
        )
        target["inherited_deployer_invoker_verified"] = inherited_invoker_verified
        ready = _authenticated_json(
            target["candidate_url"].rstrip("/") + "/ready",
            audience=target["service_url"],
            expected_identity=accounts["deployer"],
        )
        if ready.get("ready") is not True:
            raise NexusStagingDeploymentError(f"{role} candidate deployed but readiness proof failed")
        if ready.get("release_revision") != release_sha or ready.get("image_digest") != digest:
            raise NexusStagingDeploymentError(f"{role} readiness is not bound to the exact release target")
        if (
            ready.get("project_id") != project
            or ready.get("region") != REGION
            or ready.get("deployment_authorization_sha256") != authorization_sha256
        ):
            raise NexusStagingDeploymentError(f"{role} readiness is not bound to the exact deployment authority")
        if (
            ready.get("runtime_role") != role
            or ready.get("live_provider_execution_enabled") is not False
            or ready.get("production_activation") is not False
        ):
            raise NexusStagingDeploymentError(f"{role} readiness returned an invalid runtime capability binding")
        if role == "judge" and ready.get("provider_capable") is not False:
            raise NexusStagingDeploymentError("judge readiness did not prove the provider-free role")
        targets[role] = target
        readiness[role] = ready
        action_receipts.append(
            _action_receipt(
                f"{role}_deploy",
                service,
                {
                    "revision": target["revision"],
                    "candidate_tag": candidate_tag,
                    "immutable_image_uri": immutable_image,
                    "readiness_verified": True,
                    **service_authority,
                },
            )
        )

    observed_actions = tuple(item["action"] for item in action_receipts)
    if observed_actions != _ACTION_NAMES:
        raise NexusStagingDeploymentError("deployment mutations were not executed in the declared order")
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "repository": REPOSITORY,
        "project_id": project,
        "project_number": str(scope["project_number"]),
        "region": REGION,
        "release_sha": release_sha,
        "release_tree_sha": summary["release_tree_sha"],
        "ci_run_id": ci_evidence["workflow_run_id"],
        "ci_admission": ci_evidence,
        "authorization_sha256": authorization_sha256,
        "resource_manifest_sha256": payload["resource_manifest_sha256"],
        "build_id": build_id,
        "build_context_manifest_sha256": context_manifest_sha256,
        "build_source_bucket": build_source_bucket,
        "tagged_image_uri": tagged_image,
        "image_digest": digest,
        "immutable_image_uri": immutable_image,
        "foundation": foundation,
        "supply_chain": {
            **supply_chain,
            **artifact_security,
        },
        "operator_revision": targets["operator"]["revision"],
        "judge_revision": targets["judge"]["revision"],
        "migration": migration,
        "services": {
            "operator": {**targets["operator"], "readiness": readiness["operator"]},
            "judge": {**targets["judge"], "readiness": readiness["judge"]},
        },
        "actions": action_receipts,
        "public_traffic": False,
        "public_access_enabled": False,
        "traffic_migration_performed": False,
        "live_model_call_performed": False,
        "production_activation": False,
        "resource_locations": {
            "cloud_build": REGION,
            "artifact_registry": REGION,
            "cloud_run": REGION,
            "cloud_sql": REGION,
            "secret_manager": REGION,
            "build_source_bucket": REGION,
            "sbom_bucket": REGION,
        },
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    _validate_receipt(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan staging or execute exactly one checkpoint-chained staging action. "
            "Every action invocation requires one fresh active KMS-signed permit."
        )
    )
    parser.add_argument("authorization", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--ci-admission", type=Path)
    parser.add_argument(
        "--action-permit",
        type=Path,
        help="one fresh active KMS-signed execute or reconciliation permit",
    )
    parser.add_argument(
        "--predecessor-checkpoint",
        type=Path,
        help="exact preceding immutable checkpoint envelope; omit only for action zero",
    )
    parser.add_argument(
        "--reconciliation-hint",
        type=Path,
        help="permit-bound readback hint; valid only with a reconciliation permit",
    )
    parser.add_argument(
        "--checkpoint-output",
        type=Path,
        help="new local checkpoint-envelope path; existing files are never overwritten",
    )
    parser.add_argument(
        "--deployment-receipt-output",
        type=Path,
        default=Path("reports/artifacts/nexus_staging/deployment-receipt.json"),
        help="terminal action only; receipt remains separate from its publication permit",
    )
    parser.add_argument("--execute-action", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.authorization.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.execute_action:
        missing = [
            name
            for name, value in (
                ("--ci-admission", args.ci_admission),
                ("--action-permit", args.action_permit),
                ("--checkpoint-output", args.checkpoint_output),
            )
            if value is None
        ]
        if missing:
            raise NexusStagingDeploymentError(
                "--execute-action requires " + ", ".join(missing)
            )
        result = execute_staging_action(
            payload,
            manifest,
            ci_admission=json.loads(args.ci_admission.read_text(encoding="utf-8")),
            action_permit=json.loads(args.action_permit.read_text(encoding="utf-8")),
            predecessor_checkpoint=(
                json.loads(args.predecessor_checkpoint.read_text(encoding="utf-8"))
                if args.predecessor_checkpoint is not None
                else None
            ),
            checkpoint_output=args.checkpoint_output,
            deployment_receipt_output=args.deployment_receipt_output,
            reconciliation_hint=(
                json.loads(args.reconciliation_hint.read_text(encoding="utf-8"))
                if args.reconciliation_hint is not None
                else None
            ),
        )
    else:
        if any(
            value is not None
            for value in (
                args.ci_admission,
                args.action_permit,
                args.predecessor_checkpoint,
                args.reconciliation_hint,
                args.checkpoint_output,
            )
        ):
            raise NexusStagingDeploymentError(
                "execution evidence arguments require --execute-action"
            )
        result = build_plan(payload, manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AuthorizationError, NexusStagingDeploymentError) as exc:
        raise SystemExit(f"Nexus staging deployment blocked: {exc}") from exc
