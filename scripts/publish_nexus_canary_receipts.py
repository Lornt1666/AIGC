from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any, Literal
from urllib.parse import quote

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from jsonschema import Draft202012Validator, FormatChecker

from scripts.nexus_canary_impersonation import (
    bounded_impersonated_session,
)

from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.domain.nexus.contracts import AuthorityAttestation, ExecutionPermit
from src.domain.nexus.contracts import ExecutionReceipt
from src.domain.nexus.provider_runtime import (
    ProviderAttemptResult,
    ProviderRuntimeAudit,
)
from src.operations.nexus_provider_canary import (
    CANARY_AUTHORITY_ALGORITHM,
    CanaryConfigurationError,
    KmsAuthorityPublicKey,
    authority_public_key_sha256,
    expected_canary_authority_key_version,
)


ROOT = Path(__file__).resolve().parents[1]
REGION = "northamerica-northeast1"
REPOSITORY = "Lornt1666/AIGC"
PROVISIONING_RECEIPT_SCHEMA = "aigc.nexus-canary-job-provisioning-receipt.v1"
EXECUTION_RECEIPT_SCHEMA = "aigc.nexus-provider-canary-job-receipt.v1"
LIVE_RECEIPT_SCHEMA = "aigc.nexus-live-provider-canary-receipt.v2"
PROVISIONING_PERMIT_SCHEMA = (
    "aigc.nexus-canary-provisioning-receipt-publication-permit.v1"
)
EXECUTION_PERMIT_SCHEMA = (
    "aigc.nexus-canary-execution-receipt-publication-permit.v1"
)
PROVISIONING_PUBLICATION_SCHEMA = (
    "aigc.nexus-canary-provisioning-receipt-publication.v1"
)
EXECUTION_PUBLICATION_SCHEMA = (
    "aigc.nexus-canary-execution-receipt-publication.v1"
)
GOVERNED_PROVISIONING_PERMIT_SCHEMA = (
    "aigc.nexus-canary-job-provisioning-permit.v1"
)
GOVERNED_EXECUTION_PERMIT_SCHEMA = "aigc.nexus-execution-permit.v1"
PROVISIONING_PUBLICATION_PERMIT_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "nexus_canary_provisioning_receipt_publication_permit.schema.json"
)
EXECUTION_PUBLICATION_PERMIT_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "nexus_canary_execution_receipt_publication_permit.schema.json"
)
GOVERNED_PROVISIONING_PERMIT_SCHEMA_PATH = (
    ROOT / "schemas" / "nexus_canary_job_provisioning_permit.schema.json"
)
MAXIMUM_PERMIT_LIFETIME = timedelta(minutes=15)
MAXIMUM_RECEIPT_BYTES = 1024 * 1024
SHA256 = re.compile(r"^[a-f0-9]{64}$")
GIT_SHA = re.compile(r"^[a-f0-9]{40}$")
PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
RESOURCE_PREFIX = re.compile(r"^[a-z][a-z0-9-]{2,18}$")
JOB_NAME = re.compile(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")
EXECUTION_NAME = re.compile(r"^[a-z](?:[a-z0-9-]{0,126}[a-z0-9])?$")
IMMUTABLE_IMAGE = re.compile(
    r"^[a-z0-9.-]+-docker\.pkg\.dev/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$"
)
PROVIDERS = {"google_vertex_gemini", "openai_responses"}


class CanaryReceiptPublicationError(RuntimeError):
    pass


class CanaryReceiptPublicationIndeterminate(CanaryReceiptPublicationError):
    pass


class CanaryReceiptAlreadyPublished(CanaryReceiptPublicationError):
    pass


@dataclass(frozen=True)
class PublicationContext:
    kind: Literal["canary_job_provisioning", "canary_job_execution"]
    receipt_schema_version: str
    publication_permit_schema: str
    publication_schema: str
    project_id: str
    project_number: str
    resource_prefix: str
    provider_id: str
    job_name: str
    execution_name: str | None
    release_sha: str
    release_tree_sha: str
    immutable_image_uri: str
    receipt_sha256: str
    receipt_content: bytes
    receipt_bucket: str
    object_name: str
    predecessor_kind: str
    predecessor_sha256: str
    governed_permit_schema_version: str
    governed_permit_id: str
    governed_permit_sha256: str
    authority_attestation_sha256: str | None
    governed_provisioning_permit: dict[str, Any] | None = None
    authority_attestation: AuthorityAttestation | None = None


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanaryReceiptPublicationError(f"{path} must contain a JSON object")
    return value


def _schema_validate(value: Any, *, schema_path: Path, label: str) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise CanaryReceiptPublicationError(
            f"{label} schema mismatch at {path}: {errors[0].message}"
        )


def _require_exact_keys(
    value: dict[str, Any], *, expected: set[str], label: str
) -> None:
    if set(value) != expected:
        raise CanaryReceiptPublicationError(
            f"{label} fields do not match its exact receipt type"
        )


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise CanaryReceiptPublicationError(
            f"publication permit {field} must be an RFC 3339 timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CanaryReceiptPublicationError(
            f"publication permit {field} must be an RFC 3339 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CanaryReceiptPublicationError(
            f"publication permit {field} must include a UTC offset"
        )
    return parsed.astimezone(timezone.utc)


def _active_time_window(
    permit: dict[str, Any], *, authoritative_now: datetime | None
) -> datetime:
    now = authoritative_now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise CanaryReceiptPublicationError(
            "authoritative publication time must include a UTC offset"
        )
    now = now.astimezone(timezone.utc)
    issued = _aware_datetime(permit["issued_at"], field="issued_at")
    not_before = _aware_datetime(permit["not_before"], field="not_before")
    expires = _aware_datetime(permit["expires_at"], field="expires_at")
    if not (issued <= not_before <= now < expires):
        raise CanaryReceiptPublicationError(
            "publication permit is outside its active authority window"
        )
    if expires - issued > MAXIMUM_PERMIT_LIFETIME:
        raise CanaryReceiptPublicationError(
            "publication permit lifetime exceeds 15 minutes"
        )
    return now


def _crc32c(value: bytes) -> int:
    crc = 0xFFFFFFFF
    for octet in value:
        crc ^= octet
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def _crc32c_b64(value: bytes) -> str:
    return base64.b64encode(_crc32c(value).to_bytes(4, "big")).decode("ascii")


def _md5_b64(value: bytes) -> str:
    return base64.b64encode(
        hashlib.md5(value, usedforsecurity=False).digest()
    ).decode("ascii")


def _validate_hashed_receipt(
    receipt: dict[str, Any], *, schema_version: str, label: str
) -> bytes:
    if receipt.get("schema_version") != schema_version:
        raise CanaryReceiptPublicationError(
            f"{label} has the wrong receipt type"
        )
    observed = str(receipt.get("receipt_sha256") or "")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    expected = canonical_sha256(unsigned)
    if not hmac.compare_digest(observed, expected):
        raise CanaryReceiptPublicationError(
            f"{label} SHA-256 does not match its canonical content"
        )
    content = canonical_json_bytes(receipt)
    if len(content) > MAXIMUM_RECEIPT_BYTES:
        raise CanaryReceiptPublicationError(f"{label} exceeds 1 MiB")
    return content


def _resource_prefix_from_provisioner(
    principal: Any, *, project_id: str
) -> str:
    match = re.fullmatch(
        rf"(?P<prefix>[a-z][a-z0-9-]{{2,18}})-can-prov@"
        rf"{re.escape(project_id)}\.iam\.gserviceaccount\.com",
        str(principal or ""),
    )
    if match is None:
        raise CanaryReceiptPublicationError(
            "provisioning receipt has no deterministic provisioner identity"
        )
    return match.group("prefix")


_PROVISIONING_RECEIPT_KEYS = {
    "schema_version",
    "repository",
    "project_id",
    "project_number",
    "region",
    "release_sha",
    "provider_id",
    "job_name",
    "target",
    "immutable_image_uri",
    "reserved_usage_units",
    "maximum_input_units",
    "maximum_output_units",
    "request_timeout_seconds",
    "runtime_service_account",
    "provisioner_principal",
    "executor_principal",
    "job_spec_sha256",
    "authority_environment_sha256",
    "identity_evidence",
    "permission_evidence",
    "job_target",
    "provisioning_permit_id",
    "provisioning_permit_sha256",
    "permit_consumption_uri",
    "permit_consumption_generation",
    "permit_consumption_record_sha256",
    "job_deployment_performed",
    "job_execution_performed",
    "execution_overrides_authorized",
    "provider_call_performed",
    "cloud_run_mutation_count",
    "captured_at",
    "receipt_sha256",
}


def _validate_provisioning_receipt(
    receipt: dict[str, Any],
) -> tuple[dict[str, Any], bytes]:
    _require_exact_keys(
        receipt,
        expected=_PROVISIONING_RECEIPT_KEYS,
        label="canary provisioning receipt",
    )
    content = _validate_hashed_receipt(
        receipt,
        schema_version=PROVISIONING_RECEIPT_SCHEMA,
        label="canary provisioning receipt",
    )
    project = str(receipt.get("project_id") or "")
    project_number = str(receipt.get("project_number") or "")
    provider = str(receipt.get("provider_id") or "")
    job = str(receipt.get("job_name") or "")
    release = str(receipt.get("release_sha") or "")
    image = str(receipt.get("immutable_image_uri") or "")
    if (
        receipt.get("repository") != REPOSITORY
        or not PROJECT_ID.fullmatch(project)
        or not re.fullmatch(r"[0-9]{6,20}", project_number)
        or receipt.get("region") != REGION
        or provider not in PROVIDERS
        or not JOB_NAME.fullmatch(job)
        or not GIT_SHA.fullmatch(release)
        or not IMMUTABLE_IMAGE.fullmatch(image)
    ):
        raise CanaryReceiptPublicationError(
            "canary provisioning receipt resource binding is invalid"
        )
    prefix = _resource_prefix_from_provisioner(
        receipt.get("provisioner_principal"), project_id=project
    )
    provider_suffix = "can-gem" if provider == "google_vertex_gemini" else "can-oai"
    expected_runtime = f"{prefix}-{provider_suffix}@{project}.iam.gserviceaccount.com"
    expected_executor = f"{prefix}-can-exec@{project}.iam.gserviceaccount.com"
    expected_target = f"projects/{project}/locations/{REGION}/jobs/{job}"
    bucket = f"{project}-{prefix}-receipts"
    permit_id = str(receipt.get("provisioning_permit_id") or "")
    expected_consumption = (
        f"gs://{bucket}/canary-job-provisioning/{release}/{permit_id}.json"
    )
    job_target = receipt.get("job_target")
    identity = receipt.get("identity_evidence")
    permissions = receipt.get("permission_evidence")
    budgets = (
        receipt.get("reserved_usage_units"),
        receipt.get("maximum_input_units"),
        receipt.get("maximum_output_units"),
        receipt.get("request_timeout_seconds"),
    )
    if (
        receipt.get("target") != expected_target
        or receipt.get("runtime_service_account") != expected_runtime
        or receipt.get("executor_principal") != expected_executor
        or receipt.get("permit_consumption_uri") != expected_consumption
        or not re.fullmatch(r"CJP-[A-Z0-9_-]{8,64}", permit_id)
        or not all(SHA256.fullmatch(str(receipt.get(field) or "")) for field in (
            "job_spec_sha256",
            "authority_environment_sha256",
            "provisioning_permit_sha256",
            "permit_consumption_record_sha256",
        ))
        or not str(receipt.get("permit_consumption_generation") or "").isdigit()
        or not all(isinstance(value, int) and value > 0 for value in budgets)
        or budgets[1] + budgets[2] > budgets[0]
        or not isinstance(job_target, dict)
        or job_target.get("job_name") != job
        or job_target.get("immutable_image_uri") != image
        or job_target.get("service_account") != expected_runtime
        or job_target.get("authority_environment_sha256")
        != receipt.get("authority_environment_sha256")
        or not isinstance(identity, dict)
        or identity.get("attached_service_account")
        != receipt.get("provisioner_principal")
        or identity.get("attached_service_account_verified") is not True
        or identity.get("credential_source") != "gce_metadata_server"
        or identity.get("client_impersonation_used") is not False
        or identity.get("workload_identity_federation_used") is not False
        or identity.get("project_wide_permanent_mutation_authority") is not False
        or not isinstance(identity.get("broker_authority_expires_at"), str)
        or identity.get("account_level_impersonation_grant_claimed") is not False
        or identity.get("service_account_key_used") is not False
        or not isinstance(permissions, dict)
        or permissions.get("job_execution_authority_absent") is not True
        or receipt.get("job_deployment_performed") is not True
        or receipt.get("job_execution_performed") is not False
        or receipt.get("execution_overrides_authorized") is not False
        or receipt.get("provider_call_performed") is not False
        or receipt.get("cloud_run_mutation_count") != 1
    ):
        raise CanaryReceiptPublicationError(
            "canary provisioning receipt is internally inconsistent"
        )
    return {
        "project_id": project,
        "project_number": project_number,
        "resource_prefix": prefix,
        "provider_id": provider,
        "job_name": job,
        "release_sha": release,
        "immutable_image_uri": image,
        "runtime_service_account": expected_runtime,
        "provisioner_principal": receipt["provisioner_principal"],
        "executor_principal": expected_executor,
        "target": expected_target,
        "receipt_bucket": bucket,
        "receipt_sha256": receipt["receipt_sha256"],
        "authority_environment_sha256": receipt["authority_environment_sha256"],
        "job_spec_sha256": receipt["job_spec_sha256"],
        "provisioning_permit_id": permit_id,
        "provisioning_permit_sha256": receipt["provisioning_permit_sha256"],
        "budgets": budgets,
    }, content


_EXECUTION_RECEIPT_KEYS = {
    "schema_version",
    "project_id",
    "region",
    "job_name",
    "execution_name",
    "executor_identity",
    "executor_identity_evidence",
    "execution_binding_receipt_sha256",
    "immutable_image_uri",
    "reserved_usage_units",
    "maximum_input_units",
    "maximum_output_units",
    "request_timeout_seconds",
    "job_target",
    "execution_target",
    "provider_receipt",
    "automatic_retry",
    "job_max_retries",
    "job_deployment_performed",
    "execution_overrides_supplied",
    "cloud_run_mutation_count",
    "captured_at",
    "receipt_sha256",
}
_EXECUTOR_IDENTITY_EVIDENCE_KEYS = {
    "adc_impersonation_target",
    "adc_impersonation_target_verified",
    "adc_source_principal",
    "adc_source_credential_type",
    "adc_source_keyless_verified",
    "attached_metadata_source_verified",
    "bounded_token_lifetime_seconds",
    "bounded_token_expires_at",
    "bounded_token_refresh_permitted",
    "service_account_key_used",
    "jit_grant_receipt_id",
    "jit_grant_receipt_sha256",
    "jit_source_principal",
    "jit_target_principal",
    "jit_target_resource",
    "jit_grant_scope",
    "jit_account_level_grant",
    "jit_service_account_key_used",
    "jit_wif_used",
    "jit_revocation_required",
    "jit_expires_at",
    "jit_grant_condition_expression",
    "account_level_impersonation_grant_claimed",
}


def _validate_execution_receipt(
    receipt: dict[str, Any], *, predecessor: dict[str, Any]
) -> tuple[dict[str, Any], bytes]:
    predecessor_binding, _predecessor_content = _validate_provisioning_receipt(
        predecessor
    )
    _require_exact_keys(
        receipt,
        expected=_EXECUTION_RECEIPT_KEYS,
        label="canary execution receipt",
    )
    content = _validate_hashed_receipt(
        receipt,
        schema_version=EXECUTION_RECEIPT_SCHEMA,
        label="canary execution receipt",
    )
    provider_receipt = receipt.get("provider_receipt")
    job_target = receipt.get("job_target")
    execution_target = receipt.get("execution_target")
    identity = receipt.get("executor_identity_evidence")
    if not all(
        isinstance(value, dict)
        for value in (provider_receipt, job_target, execution_target, identity)
    ):
        raise CanaryReceiptPublicationError(
            "canary execution receipt contains invalid nested evidence"
        )
    _require_exact_keys(
        identity,
        expected=_EXECUTOR_IDENTITY_EVIDENCE_KEYS,
        label="canary executor identity evidence",
    )
    provider_unsigned = dict(provider_receipt)
    provider_receipt_id = provider_unsigned.pop("canary_receipt_id", None)
    expected_provider_id = (
        "CANARY-" + canonical_sha256(provider_unsigned)[:24].upper()
    )
    try:
        attempt = ProviderAttemptResult.model_validate(
            provider_receipt.get("attempt")
        )
        audit = ProviderRuntimeAudit.model_validate(provider_receipt.get("audit"))
        core_receipt = ExecutionReceipt.model_validate(
            provider_receipt.get("receipt")
        )
    except ValueError as exc:
        raise CanaryReceiptPublicationError(
            "canary execution receipt nested evidence is invalid"
        ) from exc
    project = predecessor_binding["project_id"]
    job = predecessor_binding["job_name"]
    execution = str(receipt.get("execution_name") or "")
    budgets = predecessor_binding["budgets"]
    exact_budget_fields = (
        receipt.get("reserved_usage_units"),
        receipt.get("maximum_input_units"),
        receipt.get("maximum_output_units"),
        receipt.get("request_timeout_seconds"),
    )
    try:
        bounded_expiry = _aware_datetime(
            identity.get("bounded_token_expires_at"),
            field="bounded_token_expires_at",
        )
        jit_expiry = _aware_datetime(
            identity.get("jit_expires_at"), field="jit_expires_at"
        )
    except CanaryReceiptPublicationError:
        raise
    if (
        receipt.get("project_id") != project
        or receipt.get("region") != REGION
        or receipt.get("job_name") != job
        or not EXECUTION_NAME.fullmatch(execution)
        or not execution.startswith(job + "-")
        or receipt.get("executor_identity")
        != predecessor_binding["executor_principal"]
        or identity.get("adc_impersonation_target")
        != receipt.get("executor_identity")
        or identity.get("adc_impersonation_target_verified") is not True
        or identity.get("adc_source_principal")
        != identity.get("jit_source_principal")
        or identity.get("adc_source_keyless_verified") is not True
        or identity.get("adc_source_credential_type")
        != "google.auth.compute_engine.credentials.Credentials"
        or identity.get("attached_metadata_source_verified") is not True
        or identity.get("bounded_token_refresh_permitted") is not False
        or isinstance(identity.get("bounded_token_lifetime_seconds"), bool)
        or not isinstance(identity.get("bounded_token_lifetime_seconds"), int)
        or not (1 <= identity.get("bounded_token_lifetime_seconds") <= 900)
        or bounded_expiry > jit_expiry
        or identity.get("account_level_impersonation_grant_claimed") is not False
        or identity.get("service_account_key_used") is not False
        or not re.fullmatch(
            r"^JIT-[A-Z0-9_-]{8,64}$",
            str(identity.get("jit_grant_receipt_id") or ""),
        )
        or not re.fullmatch(
            r"^[a-f0-9]{64}$",
            str(identity.get("jit_grant_receipt_sha256") or ""),
        )
        or identity.get("jit_target_principal") != receipt.get("executor_identity")
        or identity.get("jit_target_resource")
        != f"projects/{project}/locations/{REGION}/jobs/{job}"
        or identity.get("jit_grant_scope") != "exact_target_service_account"
        or identity.get("jit_account_level_grant") is not False
        or identity.get("jit_service_account_key_used") is not False
        or identity.get("jit_wif_used") is not False
        or identity.get("jit_revocation_required") is not True
        or identity.get("jit_grant_condition_expression")
        != (
            'request.time < timestamp("'
            + jit_expiry.isoformat().replace("+00:00", "Z")
            + '")'
        )
        or not re.fullmatch(
            r"[a-f0-9]{64}",
            str(receipt.get("execution_binding_receipt_sha256") or ""),
        )
        or receipt.get("immutable_image_uri")
        != predecessor_binding["immutable_image_uri"]
        or exact_budget_fields != budgets
        or job_target.get("job_name") != job
        or job_target.get("immutable_image_uri")
        != predecessor_binding["immutable_image_uri"]
        or job_target.get("service_account")
        != predecessor_binding["runtime_service_account"]
        or job_target.get("authority_environment_sha256")
        != predecessor_binding["authority_environment_sha256"]
        or execution_target.get("execution_name") != execution
        or execution_target.get("immutable_image_uri")
        != predecessor_binding["immutable_image_uri"]
        or execution_target.get("service_account")
        != predecessor_binding["runtime_service_account"]
        or provider_receipt.get("schema_version") != LIVE_RECEIPT_SCHEMA
        or provider_receipt_id != expected_provider_id
        or provider_receipt.get("provider_id")
        != predecessor_binding["provider_id"]
        or provider_receipt.get("project_id") != project
        or provider_receipt.get("region") != REGION
        or provider_receipt.get("exact_revision")
        != predecessor_binding["release_sha"]
        or provider_receipt.get("job_name") != job
        or provider_receipt.get("execution_name") != execution
        or tuple(provider_receipt.get(field) for field in (
            "reserved_usage_units",
            "maximum_input_units",
            "maximum_output_units",
            "request_timeout_seconds",
        ))
        != budgets
        or provider_receipt.get("replayed") is not False
        or provider_receipt.get("response_payload_retained") is not False
        or attempt.status != "succeeded"
        or attempt.response_payload is not None
        or attempt.cost_known is not True
        or attempt.usage_units is None
        or attempt.input_usage_units is None
        or attempt.output_usage_units is None
        or attempt.input_usage_units > budgets[1]
        or attempt.output_usage_units > budgets[2]
        or attempt.usage_units > budgets[0]
        or audit.provider_api_calls_performed != 1
        or audit.network_calls_performed != 1
        or audit.credentials_used != 1
        or audit.adapter_invocations != 1
        or audit.spend_known is not True
        or audit.spend_cad != attempt.cost_cad
        or core_receipt.permit_id != provider_receipt.get("permit_id")
        or receipt.get("automatic_retry") is not False
        or receipt.get("job_max_retries") != 0
        or receipt.get("job_deployment_performed") is not False
        or receipt.get("execution_overrides_supplied") is not False
        or receipt.get("cloud_run_mutation_count") != 1
    ):
        raise CanaryReceiptPublicationError(
            "canary execution receipt is internally inconsistent"
        )
    return {
        **predecessor_binding,
        "execution_name": execution,
        "receipt_sha256": receipt["receipt_sha256"],
        "execution_permit_id": provider_receipt["permit_id"],
        "request_digest": provider_receipt["request_digest"],
        "plan_sha256": provider_receipt["plan_sha256"],
        "authority_attestation_sha256": provider_receipt[
            "authority_attestation_sha256"
        ],
    }, content


def _validate_governed_provisioning_permit(
    permit: dict[str, Any], *, binding: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    _schema_validate(
        permit,
        schema_path=GOVERNED_PROVISIONING_PERMIT_SCHEMA_PATH,
        label="governed canary provisioning permit",
    )
    permit_sha256 = canonical_sha256(permit)
    expected = {
        "schema_version": GOVERNED_PROVISIONING_PERMIT_SCHEMA,
        "project_id": binding["project_id"],
        "project_number": binding["project_number"],
        "region": REGION,
        "release_sha": binding["release_sha"],
        "provider_id": binding["provider_id"],
        "job_name": binding["job_name"],
        "target": binding["target"],
        "immutable_image_uri": binding["immutable_image_uri"],
        "reserved_usage_units": binding["budgets"][0],
        "maximum_input_units": binding["budgets"][1],
        "maximum_output_units": binding["budgets"][2],
        "request_timeout_seconds": binding["budgets"][3],
        "runtime_service_account": binding["runtime_service_account"],
        "provisioner_principal": binding["provisioner_principal"],
        "executor_principal": binding["executor_principal"],
        "signer_principal": (
            f"{binding['resource_prefix']}-signer@{binding['project_id']}."
            "iam.gserviceaccount.com"
        ),
        "receipt_bucket": binding["receipt_bucket"],
        "permit_id": binding["provisioning_permit_id"],
        "authority_environment_sha256": binding["authority_environment_sha256"],
        "job_spec_sha256": binding["job_spec_sha256"],
        "maximum_mutations": 1,
        "automatic_retry": False,
        "job_execution_authorized": False,
        "live_model_call_authorized": False,
        "production_activation": False,
    }
    for field, expected_value in expected.items():
        if permit.get(field) != expected_value:
            raise CanaryReceiptPublicationError(
                f"governed provisioning permit is not bound to exact {field}"
            )
    if not hmac.compare_digest(
        permit_sha256, binding["provisioning_permit_sha256"]
    ):
        raise CanaryReceiptPublicationError(
            "governed provisioning permit SHA-256 mismatch"
        )
    return permit, permit_sha256


def _validate_execution_authority(
    raw_permit: dict[str, Any],
    raw_attestation: dict[str, Any],
    *,
    binding: dict[str, Any],
) -> tuple[ExecutionPermit, AuthorityAttestation, str, str]:
    try:
        permit = ExecutionPermit.model_validate(raw_permit)
        attestation = AuthorityAttestation.model_validate(raw_attestation)
    except ValueError as exc:
        raise CanaryReceiptPublicationError(
            "execution authority artifacts are invalid"
        ) from exc
    permit_sha256 = canonical_sha256(permit.model_dump(mode="json"))
    attestation_sha256 = canonical_sha256(attestation.model_dump(mode="json"))
    if (
        permit.permit_id != binding["execution_permit_id"]
        or permit.exact_revision != binding["release_sha"]
        or permit.request_digest != binding["request_digest"]
        or permit.maximum_invocations != 1
        or attestation.permit_id != permit.permit_id
        or attestation.execution_permit_sha256 != permit_sha256
        or attestation.plan_sha256 != binding["plan_sha256"]
        or attestation.request_digest != binding["request_digest"]
        or attestation.job_name != binding["job_name"]
        or attestation_sha256 != binding["authority_attestation_sha256"]
    ):
        raise CanaryReceiptPublicationError(
            "execution receipt authority/permit binding is inconsistent"
        )
    return permit, attestation, permit_sha256, attestation_sha256


def _validate_release_tree(release_tree_sha: str) -> str:
    if not GIT_SHA.fullmatch(release_tree_sha):
        raise CanaryReceiptPublicationError(
            "release tree SHA must be an exact lowercase Git SHA"
        )
    return release_tree_sha


def _provisioning_context(
    receipt: dict[str, Any],
    governed_permit: dict[str, Any],
    *,
    release_tree_sha: str,
) -> PublicationContext:
    binding, content = _validate_provisioning_receipt(receipt)
    governed_permit, governed_sha = _validate_governed_provisioning_permit(
        governed_permit, binding=binding
    )
    tree = _validate_release_tree(release_tree_sha)
    receipt_sha = binding["receipt_sha256"]
    object_name = (
        f"canary-provisioning-receipts/{binding['release_sha']}/"
        f"{binding['provider_id']}/{binding['job_name']}/{receipt_sha}.json"
    )
    return PublicationContext(
        kind="canary_job_provisioning",
        receipt_schema_version=PROVISIONING_RECEIPT_SCHEMA,
        publication_permit_schema=PROVISIONING_PERMIT_SCHEMA,
        publication_schema=PROVISIONING_PUBLICATION_SCHEMA,
        project_id=binding["project_id"],
        project_number=binding["project_number"],
        resource_prefix=binding["resource_prefix"],
        provider_id=binding["provider_id"],
        job_name=binding["job_name"],
        execution_name=None,
        release_sha=binding["release_sha"],
        release_tree_sha=tree,
        immutable_image_uri=binding["immutable_image_uri"],
        receipt_sha256=receipt_sha,
        receipt_content=content,
        receipt_bucket=binding["receipt_bucket"],
        object_name=object_name,
        predecessor_kind="canary_deployment_receipt",
        predecessor_sha256=governed_permit["deployment_sha256"],
        governed_permit_schema_version=GOVERNED_PROVISIONING_PERMIT_SCHEMA,
        governed_permit_id=governed_permit["permit_id"],
        governed_permit_sha256=governed_sha,
        authority_attestation_sha256=None,
        governed_provisioning_permit=governed_permit,
    )


def _execution_context(
    receipt: dict[str, Any],
    predecessor: dict[str, Any],
    execution_permit: dict[str, Any],
    authority_attestation: dict[str, Any],
    *,
    release_tree_sha: str,
) -> PublicationContext:
    binding, content = _validate_execution_receipt(
        receipt, predecessor=predecessor
    )
    _permit, attestation, permit_sha, attestation_sha = (
        _validate_execution_authority(
            execution_permit,
            authority_attestation,
            binding=binding,
        )
    )
    tree = _validate_release_tree(release_tree_sha)
    receipt_sha = binding["receipt_sha256"]
    object_name = (
        f"canary-execution-receipts/{binding['release_sha']}/"
        f"{binding['provider_id']}/{binding['job_name']}/"
        f"{binding['execution_name']}/{receipt_sha}.json"
    )
    return PublicationContext(
        kind="canary_job_execution",
        receipt_schema_version=EXECUTION_RECEIPT_SCHEMA,
        publication_permit_schema=EXECUTION_PERMIT_SCHEMA,
        publication_schema=EXECUTION_PUBLICATION_SCHEMA,
        project_id=binding["project_id"],
        project_number=binding["project_number"],
        resource_prefix=binding["resource_prefix"],
        provider_id=binding["provider_id"],
        job_name=binding["job_name"],
        execution_name=binding["execution_name"],
        release_sha=binding["release_sha"],
        release_tree_sha=tree,
        immutable_image_uri=binding["immutable_image_uri"],
        receipt_sha256=receipt_sha,
        receipt_content=content,
        receipt_bucket=binding["receipt_bucket"],
        object_name=object_name,
        predecessor_kind="canary_job_provisioning_receipt",
        predecessor_sha256=predecessor["receipt_sha256"],
        governed_permit_schema_version=GOVERNED_EXECUTION_PERMIT_SCHEMA,
        governed_permit_id=binding["execution_permit_id"],
        governed_permit_sha256=permit_sha,
        authority_attestation_sha256=attestation_sha,
        authority_attestation=attestation,
    )


def _expected_permit_fields(context: PublicationContext) -> dict[str, Any]:
    return {
        "schema_version": context.publication_permit_schema,
        "receipt_kind": context.kind,
        "receipt_schema_version": context.receipt_schema_version,
        "repository": REPOSITORY,
        "project_id": context.project_id,
        "project_number": context.project_number,
        "region": REGION,
        "resource_prefix": context.resource_prefix,
        "provider_id": context.provider_id,
        "job_name": context.job_name,
        "execution_name": context.execution_name,
        "release_sha": context.release_sha,
        "release_tree_sha": context.release_tree_sha,
        "immutable_image_uri": context.immutable_image_uri,
        "receipt_sha256": context.receipt_sha256,
        "receipt_content_sha256": hashlib.sha256(
            context.receipt_content
        ).hexdigest(),
        "receipt_content_length": len(context.receipt_content),
        "receipt_bucket": context.receipt_bucket,
        "object_name": context.object_name,
        "content_type": "application/json",
        "predecessor_kind": context.predecessor_kind,
        "predecessor_sha256": context.predecessor_sha256,
        "governed_permit_schema_version": context.governed_permit_schema_version,
        "governed_permit_id": context.governed_permit_id,
        "governed_permit_sha256": context.governed_permit_sha256,
        "authority_attestation_sha256": context.authority_attestation_sha256,
        "maximum_mutations": 1,
        "automatic_retry": False,
        "consumption_mode": "gcs_media_upload_if_generation_match_zero",
        "public_traffic": False,
        "live_model_call": False,
        "production_activation": False,
        "signer_principal": (
            f"{context.resource_prefix}-signer@{context.project_id}."
            "iam.gserviceaccount.com"
        ),
        "publisher_principal": (
            f"{context.resource_prefix}-can-pub@{context.project_id}."
            "iam.gserviceaccount.com"
        ),
        "kms_key_version": expected_canary_authority_key_version(
            project_id=context.project_id,
            resource_prefix=context.resource_prefix,
        ),
        "signing_algorithm": CANARY_AUTHORITY_ALGORITHM,
    }


def _validate_publication_permit(
    permit: dict[str, Any],
    *,
    context: PublicationContext,
    authoritative_now: datetime | None,
) -> dict[str, Any]:
    if not isinstance(permit, dict):
        raise CanaryReceiptPublicationError(
            "receipt publication permit must be a JSON object"
        )
    permit = dict(permit)
    schema_path = (
        PROVISIONING_PUBLICATION_PERMIT_SCHEMA_PATH
        if context.kind == "canary_job_provisioning"
        else EXECUTION_PUBLICATION_PERMIT_SCHEMA_PATH
    )
    _schema_validate(
        permit,
        schema_path=schema_path,
        label=f"{context.kind} publication permit",
    )
    for field, expected in _expected_permit_fields(context).items():
        if permit.get(field) != expected:
            raise CanaryReceiptPublicationError(
                f"publication permit is not bound to exact {field}"
            )
    source_principal = str(permit.get("source_principal") or "")
    if (
        source_principal == permit.get("publisher_principal")
        or not source_principal.endswith(
            f"@{context.project_id}.iam.gserviceaccount.com"
        )
    ):
        raise CanaryReceiptPublicationError(
            "publication permit is not bound to a distinct project-local attached source"
        )
    _active_time_window(permit, authoritative_now=authoritative_now)
    return permit


def _signature_bytes(signature_b64: Any, *, label: str) -> bytes:
    try:
        signature = base64.b64decode(str(signature_b64), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CanaryReceiptPublicationError(
            f"{label} signature is not canonical base64"
        ) from exc
    if base64.b64encode(signature).decode("ascii") != signature_b64:
        raise CanaryReceiptPublicationError(
            f"{label} signature is not canonical base64"
        )
    return signature


def _public_rsa_key(kms_public_key: KmsAuthorityPublicKey) -> rsa.RSAPublicKey:
    try:
        key = serialization.load_pem_public_key(
            kms_public_key.public_key_pem.encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise CanaryReceiptPublicationError(
            "KMS publication public key is invalid"
        ) from exc
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size != 2048:
        raise CanaryReceiptPublicationError(
            "KMS publication public key must be RSA 2048"
        )
    return key


def _verify_signed_payload(
    *,
    public_key: rsa.RSAPublicKey,
    payload: dict[str, Any],
    signature_b64: Any,
    label: str,
) -> None:
    signature = _signature_bytes(signature_b64, label=label)
    digest = hashlib.sha256(canonical_json_bytes(payload)).digest()
    try:
        public_key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise CanaryReceiptPublicationError(
            f"{label} signature verification failed"
        ) from exc


def _verify_kms_signatures(
    *,
    context: PublicationContext,
    permit: dict[str, Any],
    kms_public_key: KmsAuthorityPublicKey,
) -> None:
    expected_key_version = _expected_permit_fields(context)["kms_key_version"]
    try:
        observed_public_key_sha = authority_public_key_sha256(
            kms_public_key.public_key_pem
        )
    except CanaryConfigurationError as exc:
        raise CanaryReceiptPublicationError(
            "publication permit KMS public-key evidence is invalid"
        ) from exc
    if (
        kms_public_key.kms_key_version != expected_key_version
        or kms_public_key.algorithm != CANARY_AUTHORITY_ALGORITHM
        or not hmac.compare_digest(
            kms_public_key.public_key_sha256, observed_public_key_sha
        )
        or permit.get("kms_key_version") != expected_key_version
        or permit.get("signing_algorithm") != CANARY_AUTHORITY_ALGORITHM
        or not hmac.compare_digest(
            str(permit.get("public_key_sha256") or ""), observed_public_key_sha
        )
    ):
        raise CanaryReceiptPublicationError(
            "publication permit KMS trust-root evidence mismatch"
        )
    public_key = _public_rsa_key(kms_public_key)
    _verify_signed_payload(
        public_key=public_key,
        payload={key: value for key, value in permit.items() if key != "signature_b64"},
        signature_b64=permit["signature_b64"],
        label="publication permit",
    )
    if context.governed_provisioning_permit is not None:
        governed = context.governed_provisioning_permit
        if (
            governed.get("kms_key_version") != expected_key_version
            or governed.get("signing_algorithm") != CANARY_AUTHORITY_ALGORITHM
            or governed.get("public_key_sha256") != observed_public_key_sha
        ):
            raise CanaryReceiptPublicationError(
                "governed provisioning permit KMS trust-root mismatch"
            )
        _verify_signed_payload(
            public_key=public_key,
            payload={
                key: value
                for key, value in governed.items()
                if key != "signature_b64"
            },
            signature_b64=governed["signature_b64"],
            label="governed provisioning permit",
        )
    if context.authority_attestation is not None:
        attestation = context.authority_attestation
        if (
            attestation.kms_key_version != expected_key_version
            or attestation.signing_algorithm != CANARY_AUTHORITY_ALGORITHM
            or attestation.public_key_sha256 != observed_public_key_sha
        ):
            raise CanaryReceiptPublicationError(
                "execution authority attestation KMS trust-root mismatch"
            )
        _verify_signed_payload(
            public_key=public_key,
            payload=attestation.signed_payload(),
            signature_b64=attestation.signature_b64,
            label="execution authority attestation",
        )


def _authorized_session_for_principal(
    expected_principal: str,
    *,
    expected_source: str,
    authority_expires_at: datetime,
):
    session, _evidence = bounded_impersonated_session(
        expected_target=expected_principal,
        expected_source=expected_source,
        authority_expires_at=authority_expires_at,
        error_type=CanaryReceiptPublicationError,
    )
    return session


def _fetch_kms_public_key(
    *, session: Any, kms_key_version: str
) -> KmsAuthorityPublicKey:
    try:
        response = session.request(
            "GET",
            f"https://{REGION}-cloudkms.googleapis.com/v1/"
            f"{kms_key_version}/publicKey",
            timeout=10,
            allow_redirects=False,
        )
    except Exception as exc:
        raise CanaryReceiptPublicationError(
            "deterministic Montréal KMS v1 public-key request failed"
        ) from exc
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = {}
    if (
        response.status_code != 200
        or not isinstance(payload, dict)
        or payload.get("name") != kms_key_version
        or payload.get("algorithm") != CANARY_AUTHORITY_ALGORITHM
        or not isinstance(payload.get("pem"), str)
        or str(payload.get("pemCrc32c") or "")
        != str(_crc32c(payload["pem"].encode("utf-8")))
    ):
        raise CanaryReceiptPublicationError(
            "deterministic Montréal KMS v1 public key could not be verified"
        )
    try:
        public_key_sha256 = authority_public_key_sha256(payload["pem"])
    except CanaryConfigurationError as exc:
        raise CanaryReceiptPublicationError(
            "deterministic Montréal KMS v1 public key is invalid"
        ) from exc
    return KmsAuthorityPublicKey(
        kms_key_version=kms_key_version,
        algorithm=payload["algorithm"],
        public_key_pem=payload["pem"],
        public_key_sha256=public_key_sha256,
    )


def _storage_create_only(
    *, session: Any, bucket: str, object_name: str, content: bytes
) -> tuple[int, dict[str, Any]]:
    expected_crc32c = _crc32c_b64(content)
    expected_md5 = _md5_b64(content)
    response = session.request(
        "POST",
        f"https://storage.googleapis.com/upload/storage/v1/b/"
        f"{quote(bucket, safe='')}/o",
        params={
            "uploadType": "media",
            "name": object_name,
            "ifGenerationMatch": "0",
            "projection": "full",
        },
        data=content,
        headers={
            "Content-Type": "application/json",
            "Content-MD5": expected_md5,
            "X-Goog-Hash": f"crc32c={expected_crc32c},md5={expected_md5}",
        },
        timeout=10,
        allow_redirects=False,
    )
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = {}
    return int(response.status_code), payload if isinstance(payload, dict) else {}


def _validate_upload_response(
    *, response: dict[str, Any], context: PublicationContext
) -> dict[str, str]:
    generation = str(response.get("generation") or "")
    metageneration = str(response.get("metageneration") or "")
    size = str(response.get("size") or "")
    expected_md5 = _md5_b64(context.receipt_content)
    expected_crc32c = _crc32c_b64(context.receipt_content)
    if (
        response.get("bucket") != context.receipt_bucket
        or response.get("name") != context.object_name
        or not generation.isdigit()
        or int(generation) <= 0
        or metageneration != "1"
        or size != str(len(context.receipt_content))
        or response.get("contentType") != "application/json"
        or not hmac.compare_digest(
            str(response.get("md5Hash") or ""), expected_md5
        )
        or not hmac.compare_digest(
            str(response.get("crc32c") or ""), expected_crc32c
        )
    ):
        raise CanaryReceiptPublicationIndeterminate(
            "publication response is ambiguous; permit and target are consumed"
        )
    return {
        "object_generation": generation,
        "object_metageneration": metageneration,
        "object_size": size,
        "object_md5": expected_md5,
        "object_crc32c": expected_crc32c,
    }


def _publish(
    *,
    context: PublicationContext,
    permit: dict[str, Any],
    authoritative_now: datetime | None,
) -> dict[str, Any]:
    validated_permit = _validate_publication_permit(
        permit,
        context=context,
        authoritative_now=authoritative_now,
    )
    session = _authorized_session_for_principal(
        validated_permit["publisher_principal"],
        expected_source=validated_permit["source_principal"],
        authority_expires_at=_aware_datetime(
            validated_permit["expires_at"], field="expires_at"
        ),
    )
    kms_public_key = _fetch_kms_public_key(
        session=session,
        kms_key_version=validated_permit["kms_key_version"],
    )
    _verify_kms_signatures(
        context=context,
        permit=validated_permit,
        kms_public_key=kms_public_key,
    )
    _active_time_window(
        validated_permit, authoritative_now=authoritative_now
    )
    validated_permit["permit_sha256"] = canonical_sha256(validated_permit)
    try:
        status_code, response = _storage_create_only(
            session=session,
            bucket=context.receipt_bucket,
            object_name=context.object_name,
            content=context.receipt_content,
        )
    except Exception as exc:
        raise CanaryReceiptPublicationIndeterminate(
            "publication result is indeterminate; permit and target are consumed"
        ) from exc
    if status_code in {409, 412}:
        raise CanaryReceiptAlreadyPublished(
            "canary receipt or publication permit was already consumed; no retry"
        )
    if status_code not in {200, 201}:
        raise CanaryReceiptPublicationIndeterminate(
            "publication result is indeterminate; permit and target are consumed"
        )
    object_evidence = _validate_upload_response(
        response=response, context=context
    )
    return {
        "schema_version": context.publication_schema,
        "receipt_kind": context.kind,
        "permit_id": validated_permit["permit_id"],
        "permit_sha256": validated_permit["permit_sha256"],
        "repository": REPOSITORY,
        "project_id": context.project_id,
        "project_number": context.project_number,
        "region": REGION,
        "provider_id": context.provider_id,
        "job_name": context.job_name,
        "execution_name": context.execution_name,
        "release_sha": context.release_sha,
        "release_tree_sha": context.release_tree_sha,
        "receipt_sha256": context.receipt_sha256,
        "receipt_content_sha256": hashlib.sha256(
            context.receipt_content
        ).hexdigest(),
        "predecessor_kind": context.predecessor_kind,
        "predecessor_sha256": context.predecessor_sha256,
        "governed_permit_id": context.governed_permit_id,
        "governed_permit_sha256": context.governed_permit_sha256,
        "authority_attestation_sha256": context.authority_attestation_sha256,
        "publisher_principal": validated_permit["publisher_principal"],
        "source_principal": validated_permit["source_principal"],
        "object_uri": f"gs://{context.receipt_bucket}/{context.object_name}",
        **object_evidence,
        "maximum_mutations": 1,
        "automatic_retry": False,
        "redirect_followed": False,
        "storage_read_or_list_performed": False,
        "storage_overwrite_or_delete_performed": False,
        "public_traffic": False,
        "live_model_call": False,
        "production_activation": False,
    }


def publish_provisioning_receipt(
    receipt: dict[str, Any],
    governed_provisioning_permit: dict[str, Any],
    publication_permit: dict[str, Any],
    *,
    release_tree_sha: str,
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    context = _provisioning_context(
        receipt,
        governed_provisioning_permit,
        release_tree_sha=release_tree_sha,
    )
    return _publish(
        context=context,
        permit=publication_permit,
        authoritative_now=authoritative_now,
    )


def publish_execution_receipt(
    receipt: dict[str, Any],
    predecessor_provisioning_receipt: dict[str, Any],
    execution_permit: dict[str, Any],
    authority_attestation: dict[str, Any],
    publication_permit: dict[str, Any],
    *,
    release_tree_sha: str,
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    context = _execution_context(
        receipt,
        predecessor_provisioning_receipt,
        execution_permit,
        authority_attestation,
        release_tree_sha=release_tree_sha,
    )
    return _publish(
        context=context,
        permit=publication_permit,
        authoritative_now=authoritative_now,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="receipt_kind", required=True)

    provisioning = subparsers.add_parser("provisioning")
    provisioning.add_argument("receipt", type=Path)
    provisioning.add_argument("governed_provisioning_permit", type=Path)
    provisioning.add_argument("publication_permit", type=Path)
    provisioning.add_argument("--release-tree-sha", required=True)
    provisioning.add_argument("--execute", action="store_true")

    execution = subparsers.add_parser("execution")
    execution.add_argument("receipt", type=Path)
    execution.add_argument("predecessor_provisioning_receipt", type=Path)
    execution.add_argument("execution_permit", type=Path)
    execution.add_argument("authority_attestation", type=Path)
    execution.add_argument("publication_permit", type=Path)
    execution.add_argument("--release-tree-sha", required=True)
    execution.add_argument("--execute", action="store_true")

    args = parser.parse_args()
    if not args.execute:
        raise CanaryReceiptPublicationError(
            "--execute is required; canary receipt publication is never implicit"
        )
    if args.receipt_kind == "provisioning":
        result = publish_provisioning_receipt(
            _object(args.receipt),
            _object(args.governed_provisioning_permit),
            _object(args.publication_permit),
            release_tree_sha=args.release_tree_sha,
        )
    else:
        result = publish_execution_receipt(
            _object(args.receipt),
            _object(args.predecessor_provisioning_receipt),
            _object(args.execution_permit),
            _object(args.authority_attestation),
            _object(args.publication_permit),
            release_tree_sha=args.release_tree_sha,
        )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CanaryReceiptPublicationError as exc:
        raise SystemExit(f"Nexus canary receipt publication blocked: {exc}") from exc
