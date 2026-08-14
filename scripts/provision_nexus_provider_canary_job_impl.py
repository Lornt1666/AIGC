from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import time
from typing import Any, Sequence
from urllib.parse import quote

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from jsonschema import Draft202012Validator, FormatChecker

from scripts.aigc_external_release_procurement import ExternalReleaseContract
from scripts.launch_nexus_provider_canary_job import (
    CanaryLaunchError,
    _authority_environment,
    _expected_job_name,
    _validate_authority,
    _validate_job_description,
)
from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.domain.nexus.contracts import (
    AuthorityAttestation,
    ExecutionPermit,
    GovernanceDecision,
)
from src.operations.nexus_provider_canary import (
    CANARY_AUTHORITY_ALGORITHM,
    KmsAuthorityPublicKey,
    ProviderCanaryPlan,
    authority_public_key_sha256,
    expected_canary_authority_key_version,
    fetch_kms_authority_public_key,
)


ROOT = Path(__file__).resolve().parents[1]
REGION = "northamerica-northeast1"
REPOSITORY = "Lornt1666/AIGC"
PERMIT_SCHEMA_VERSION = "aigc.nexus-canary-job-provisioning-permit.v1"
RECEIPT_SCHEMA_VERSION = "aigc.nexus-canary-job-provisioning-receipt.v1"
PERMIT_SCHEMA_PATH = (
    ROOT / "schemas" / "nexus_canary_job_provisioning_permit.schema.json"
)
IMMUTABLE_IMAGE = re.compile(
    r"^[a-z0-9.-]+-docker\.pkg\.dev/.+@sha256:[a-f0-9]{64}$"
)
SERVICE_ACCOUNT = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$"
)
SHA256 = re.compile(r"^[a-f0-9]{64}$")
MAXIMUM_PERMIT_LIFETIME = timedelta(minutes=15)

_PROVISIONER_JOB_PERMISSIONS = (
    "run.jobs.create",
    "run.jobs.update",
    "run.jobs.get",
    "run.jobs.run",
    "run.jobs.runWithOverrides",
    "run.jobs.delete",
    "run.jobs.setIamPolicy",
)
_REQUIRED_PROVISIONER_JOB_PERMISSIONS = frozenset(
    {"run.jobs.create", "run.jobs.update", "run.jobs.get"}
)
_FORBIDDEN_PROVISIONER_JOB_PERMISSIONS = frozenset(
    {
        "run.jobs.run",
        "run.jobs.runWithOverrides",
        "run.jobs.delete",
        "run.jobs.setIamPolicy",
    }
)


class CanaryJobProvisioningError(RuntimeError):
    pass


class CanaryJobProvisioningIndeterminate(CanaryJobProvisioningError):
    pass


class CanaryJobProvisioningPermitConsumed(CanaryJobProvisioningError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_new_output(output: Path) -> None:
    if output.exists():
        raise CanaryJobProvisioningError(
            "provisioning receipt output already exists and will not be overwritten"
        )


def _write_new_receipt(output: Path, receipt: dict[str, Any]) -> None:
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    except OSError as exc:
        raise CanaryJobProvisioningIndeterminate(
            "job was provisioned but its create-only local receipt could not be written"
        ) from exc


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanaryJobProvisioningError(f"{path} must contain a JSON object")
    return value


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise CanaryJobProvisioningError(
            f"provisioning permit {field} must be an RFC 3339 timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CanaryJobProvisioningError(
            f"provisioning permit {field} must be an RFC 3339 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CanaryJobProvisioningError(
            f"provisioning permit {field} must include a UTC offset"
        )
    return parsed.astimezone(timezone.utc)


def expected_canary_job_identities(
    *, prefix: str, project: str, provider_id: str
) -> dict[str, str]:
    runtime_suffix = (
        "can-gem" if provider_id == "google_vertex_gemini" else "can-oai"
    )
    identities = {
        "provisioner": f"{prefix}-can-prov@{project}.iam.gserviceaccount.com",
        "binder": f"{prefix}-can-bind@{project}.iam.gserviceaccount.com",
        "executor": f"{prefix}-can-exec@{project}.iam.gserviceaccount.com",
        "publisher": f"{prefix}-can-pub@{project}.iam.gserviceaccount.com",
        "runtime": f"{prefix}-{runtime_suffix}@{project}.iam.gserviceaccount.com",
        "signer": f"{prefix}-signer@{project}.iam.gserviceaccount.com",
    }
    if any(not SERVICE_ACCOUNT.fullmatch(identity) for identity in identities.values()):
        raise CanaryJobProvisioningError(
            "derived canary provisioning identities are invalid"
        )
    return identities


def expected_canary_job_spec(
    *,
    project: str,
    prefix: str,
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    execution_permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    immutable_image: str,
) -> dict[str, Any]:
    job_name = _expected_job_name(
        prefix=prefix,
        provider_id=plan.provider_id,
        permit_id=execution_permit.permit_id,
    )
    identities = expected_canary_job_identities(
        prefix=prefix,
        project=project,
        provider_id=plan.provider_id,
    )
    provider_label = (
        "gemini" if plan.provider_id == "google_vertex_gemini" else "openai"
    )
    environment = _authority_environment(
        plan=plan,
        decision=decision,
        permit=execution_permit,
        attestation=attestation,
    )
    return {
        "target": f"projects/{project}/locations/{REGION}/jobs/{job_name}",
        "job_name": job_name,
        "provider_id": plan.provider_id,
        "provider_label": provider_label,
        "immutable_image_uri": immutable_image,
        "reserved_usage_units": plan.reserved_usage_units,
        "maximum_input_units": plan.maximum_input_units,
        "maximum_output_units": plan.maximum_output_units,
        "request_timeout_seconds": plan.request_timeout_seconds,
        "runtime_service_account": identities["runtime"],
        "provisioner_principal": identities["provisioner"],
        "executor_principal": identities["executor"],
        "authority_environment": environment,
        "network": f"{prefix}-vpc",
        "subnet": f"{prefix}-subnet",
        "vpc_egress": "private-ranges-only",
        "cloud_sql_connection": f"{project}:{REGION}:{prefix}-control",
        "command": ["python"],
        "args": ["-m", "src.operations.nexus_provider_canary"],
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "timeout_seconds": 180,
        "clear_inherited_secrets": True,
        "clear_inherited_volumes": True,
        "labels": {
            "aigc-release-sha": plan.exact_revision,
            "aigc-provider": provider_label,
            "aigc-dormant-canary": "true",
        },
    }


def _validate_permit_schema(permit: dict[str, Any]) -> None:
    schema = json.loads(PERMIT_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(permit),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise CanaryJobProvisioningError(
            f"provisioning permit schema mismatch at {path}: {errors[0].message}"
        )


def _verify_permit_signature(
    permit: dict[str, Any], *, kms_public_key: KmsAuthorityPublicKey
) -> None:
    if permit["kms_key_version"] != kms_public_key.kms_key_version:
        raise CanaryJobProvisioningError(
            "provisioning permit KMS key-version evidence mismatch"
        )
    if permit["signing_algorithm"] != kms_public_key.algorithm:
        raise CanaryJobProvisioningError(
            "provisioning permit KMS algorithm evidence mismatch"
        )
    try:
        public_key = serialization.load_pem_public_key(
            kms_public_key.public_key_pem.encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise CanaryJobProvisioningError(
            "provisioning permit KMS public key is invalid"
        ) from exc
    if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size != 2048:
        raise CanaryJobProvisioningError(
            "provisioning permit KMS public key must be RSA 2048"
        )
    observed_public_key_sha256 = authority_public_key_sha256(
        kms_public_key.public_key_pem
    )
    if not hmac.compare_digest(
        observed_public_key_sha256, kms_public_key.public_key_sha256
    ) or not hmac.compare_digest(
        observed_public_key_sha256, permit["public_key_sha256"]
    ):
        raise CanaryJobProvisioningError(
            "provisioning permit KMS public-key digest mismatch"
        )
    try:
        signature = base64.b64decode(permit["signature_b64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CanaryJobProvisioningError(
            "provisioning permit signature is not canonical base64"
        ) from exc
    if base64.b64encode(signature).decode("ascii") != permit["signature_b64"]:
        raise CanaryJobProvisioningError(
            "provisioning permit signature is not canonical base64"
        )
    signed = {key: value for key, value in permit.items() if key != "signature_b64"}
    digest = hashlib.sha256(canonical_json_bytes(signed)).digest()
    try:
        public_key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise CanaryJobProvisioningError(
            "provisioning permit KMS signature verification failed"
        ) from exc


def validate_provisioning_permit(
    raw_permit: dict[str, Any],
    *,
    procurement: ExternalReleaseContract,
    deployment: dict[str, Any],
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    execution_permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    job_spec: dict[str, Any],
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    permit = dict(raw_permit)
    _validate_permit_schema(permit)
    now = (authoritative_now or datetime.now(timezone.utc)).astimezone(
        timezone.utc
    )
    prefix = procurement.prefix
    identities = expected_canary_job_identities(
        prefix=prefix,
        project=procurement.project_id,
        provider_id=plan.provider_id,
    )
    expected_key_version = expected_canary_authority_key_version(
        project_id=procurement.project_id,
        resource_prefix=prefix,
    )
    expected = {
        "schema_version": PERMIT_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "project_id": procurement.project_id,
        "project_number": procurement.project_number,
        "region": REGION,
        "release_sha": plan.exact_revision,
        "provider_id": plan.provider_id,
        "job_name": job_spec["job_name"],
        "target": job_spec["target"],
        "immutable_image_uri": job_spec["immutable_image_uri"],
        "reserved_usage_units": plan.reserved_usage_units,
        "maximum_input_units": plan.maximum_input_units,
        "maximum_output_units": plan.maximum_output_units,
        "request_timeout_seconds": plan.request_timeout_seconds,
        "runtime_service_account": identities["runtime"],
        "provisioner_principal": identities["provisioner"],
        "executor_principal": identities["executor"],
        "signer_principal": identities["signer"],
        "receipt_bucket": f"{procurement.project_id}-{prefix}-receipts",
        "procurement_sha256": canonical_sha256(procurement.payload),
        "deployment_sha256": canonical_sha256(deployment),
        "plan_sha256": canonical_sha256(plan.model_dump(mode="json")),
        "governance_decision_sha256": canonical_sha256(
            decision.model_dump(mode="json")
        ),
        "execution_permit_sha256": canonical_sha256(
            execution_permit.model_dump(mode="json")
        ),
        "authority_attestation_sha256": canonical_sha256(
            attestation.model_dump(mode="json")
        ),
        "authority_environment_sha256": canonical_sha256(
            job_spec["authority_environment"]
        ),
        "job_spec_sha256": canonical_sha256(job_spec),
        "maximum_mutations": 1,
        "automatic_retry": False,
        "consumption_mode": "gcs_if_generation_match_zero",
        "job_execution_authorized": False,
        "live_model_call_authorized": False,
        "production_activation": False,
        "kms_key_version": expected_key_version,
        "signing_algorithm": CANARY_AUTHORITY_ALGORITHM,
    }
    for field, value in expected.items():
        if permit.get(field) != value:
            raise CanaryJobProvisioningError(
                f"provisioning permit is not bound to exact {field}"
            )
    issued_at = _aware_datetime(permit["issued_at"], field="issued_at")
    not_before = _aware_datetime(permit["not_before"], field="not_before")
    expires_at = _aware_datetime(permit["expires_at"], field="expires_at")
    if not (issued_at <= not_before <= now < expires_at):
        raise CanaryJobProvisioningError(
            "provisioning permit is outside its active authority window"
        )
    if expires_at - issued_at > MAXIMUM_PERMIT_LIFETIME:
        raise CanaryJobProvisioningError(
            "provisioning permit lifetime exceeds 15 minutes"
        )
    kms_public_key = fetch_kms_authority_public_key(expected_key_version)
    _verify_permit_signature(permit, kms_public_key=kms_public_key)
    permit["permit_sha256"] = canonical_sha256(permit)
    return permit


def _trusted_broker_session(expected_principal: str):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession, Request

    credentials, _project = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",)
    )
    credential_type = f"{type(credentials).__module__}.{type(credentials).__qualname__}"
    if credential_type != "google.auth.compute_engine.credentials.Credentials":
        raise CanaryJobProvisioningError(
            "BLOCKED_PENDING_TRUSTED_BROKER: provisioner must be an attached "
            "metadata service account"
        )
    if any(
        getattr(credentials, field, None)
        for field in ("target_principal", "_target_principal", "_source_credentials")
    ):
        raise CanaryJobProvisioningError(
            "BLOCKED_PENDING_TRUSTED_BROKER: client impersonation is forbidden"
        )
    try:
        credentials.refresh(Request())
    except Exception as exc:
        raise CanaryJobProvisioningError(
            "BLOCKED_PENDING_TRUSTED_BROKER: attached identity is unverifiable"
        ) from exc
    observed = str(getattr(credentials, "service_account_email", "") or "")
    if observed != expected_principal:
        raise CanaryJobProvisioningError("attached provisioner identity mismatch")
    return AuthorizedSession(
        credentials, refresh_status_codes=(), max_refresh_attempts=0
    ), {
        "attached_service_account": observed,
        "attached_service_account_verified": True,
        "credential_source": "gce_metadata_server",
        "client_impersonation_used": False,
        "workload_identity_federation_used": False,
        "service_account_key_used": False,
    }


def _authorized_test_permissions(
    *,
    url: str,
    permissions: Sequence[str],
    expected_principal: str,
) -> tuple[int, dict[str, Any]]:
    session, _evidence = _trusted_broker_session(expected_principal)
    response = session.post(
        url,
        json={"permissions": list(permissions)},
        timeout=10,
    )
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = {}
    return int(response.status_code), payload if isinstance(payload, dict) else {}


def _preflight_provisioner_permissions(
    *,
    project: str,
    job_name: str,
    runtime_service_account: str,
    receipt_bucket: str,
    provisioner_principal: str,
    session: Any | None = None,
) -> dict[str, Any]:
    job_resource = f"projects/{project}/locations/{REGION}/jobs/{job_name}"
    checks = (
        (
            "job",
            f"https://run.googleapis.com/v2/{job_resource}:testIamPermissions",
            _PROVISIONER_JOB_PERMISSIONS,
        ),
        (
            "runtime_service_account",
            "https://iam.googleapis.com/v1/projects/"
            f"{quote(project, safe='')}/serviceAccounts/"
            f"{quote(runtime_service_account, safe='@.')}:testIamPermissions",
            ("iam.serviceAccounts.actAs",),
        ),
        (
            "receipt_bucket",
            "https://storage.googleapis.com/storage/v1/b/"
            f"{quote(receipt_bucket, safe='')}/iam/testPermissions",
            ("storage.objects.create",),
        ),
    )
    responses: dict[str, set[str]] = {}
    evidence: dict[str, Any] = {}
    for name, url, permissions in checks:
        try:
            if session is None:
                status_code, payload = _authorized_test_permissions(
                    url=url,
                    permissions=permissions,
                    expected_principal=provisioner_principal,
                )
            else:
                response = session.post(
                    url, json={"permissions": list(permissions)}, timeout=10
                )
                status_code = int(response.status_code)
                payload = response.json()
        except Exception as exc:
            raise CanaryJobProvisioningError(
                f"{name} provisioning permission preflight could not be verified"
            ) from exc
        granted = payload.get("permissions")
        if status_code != 200 or not isinstance(granted, list) or any(
            not isinstance(item, str) for item in granted
        ):
            raise CanaryJobProvisioningError(
                f"{name} provisioning permission evidence is invalid"
            )
        responses[name] = set(granted)
        evidence[name] = {
            "permissions": sorted(responses[name]),
            "evidence_sha256": canonical_sha256(payload),
        }
    if not _REQUIRED_PROVISIONER_JOB_PERMISSIONS.issubset(responses["job"]):
        raise CanaryJobProvisioningError(
            "canary job provisioner lacks exact create/update/get authority"
        )
    if _FORBIDDEN_PROVISIONER_JOB_PERMISSIONS.intersection(responses["job"]):
        raise CanaryJobProvisioningError(
            "canary job provisioner has prohibited job execution or destructive authority"
        )
    if responses["runtime_service_account"] != {"iam.serviceAccounts.actAs"}:
        raise CanaryJobProvisioningError(
            "canary job provisioner lacks exact runtime actAs authority"
        )
    if responses["receipt_bucket"] != {"storage.objects.create"}:
        raise CanaryJobProvisioningError(
            "canary job provisioner lacks exact create-only receipt authority"
        )
    evidence["job_execution_authority_absent"] = True
    return evidence


def _verify_expiring_broker_authority(
    *, session: Any, permit: dict[str, Any], runtime_service_account: str,
    prefix: str,
) -> dict[str, Any]:
    expiry = _aware_datetime(permit["expires_at"], field="expires_at")
    expiry_z = expiry.isoformat().replace("+00:00", "Z")
    suffix = re.sub(r"[^a-z0-9]", "_", permit["permit_id"].lower()).strip("_")
    expression = f'request.time < timestamp("{expiry_z}")'
    member = f"serviceAccount:{permit['provisioner_principal']}"
    expected_project_binding = {
        "role": (
            f"projects/{permit['project_id']}/roles/"
            f"{prefix.replace('-', '_')}_canary_job_provisioner"
        ),
        "members": [member],
        "condition": {
            "title": f"aigc_provision_{suffix}"[:79],
            "description": "One dormant-job provisioning permit",
            "expression": expression,
        },
    }
    expected_act_as = {
        "role": "roles/iam.serviceAccountUser",
        "members": [member],
        "condition": {
            "title": f"aigc_provision_actas_{suffix}"[:79],
            "description": "Act as one canary runtime for one dormant job",
            "expression": expression,
        },
    }
    project_response = session.post(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/"
        f"{permit['project_id']}:getIamPolicy",
        json={"options": {"requestedPolicyVersion": 3}}, timeout=10,
    )
    runtime_response = session.get(
        "https://iam.googleapis.com/v1/projects/"
        f"{quote(permit['project_id'], safe='')}/serviceAccounts/"
        f"{quote(runtime_service_account, safe='@.')}:getIamPolicy",
        params={"options.requestedPolicyVersion": "3"}, timeout=10,
    )
    try:
        project_policy = project_response.json()
        runtime_policy = runtime_response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryJobProvisioningError(
            "trusted provisioner broker IAM evidence is invalid"
        ) from exc
    if project_response.status_code != 200 or runtime_response.status_code != 200:
        raise CanaryJobProvisioningError(
            "BLOCKED_PENDING_TRUSTED_BROKER: conditional authority is not observable"
        )
    project_bindings = [
        item for item in project_policy.get("bindings", [])
        if isinstance(item, dict) and member in (item.get("members") or [])
        and item.get("role") == expected_project_binding["role"]
    ]
    runtime_bindings = [
        item for item in runtime_policy.get("bindings", [])
        if isinstance(item, dict) and member in (item.get("members") or [])
        and item.get("role") == "roles/iam.serviceAccountUser"
    ]
    if project_bindings != [expected_project_binding] or runtime_bindings != [expected_act_as]:
        raise CanaryJobProvisioningError(
            "BLOCKED_PENDING_TRUSTED_BROKER: exact expiring broker authority is absent"
        )
    return {
        "broker_authority_expires_at": expiry.isoformat(),
        "project_binding_sha256": canonical_sha256(expected_project_binding),
        "runtime_act_as_binding_sha256": canonical_sha256(expected_act_as),
        "project_wide_permanent_mutation_authority": False,
    }


def _authorized_storage_create_only(
    *,
    bucket: str,
    object_name: str,
    content: bytes,
    expected_principal: str,
    session: Any | None = None,
) -> tuple[int, dict[str, Any]]:
    if session is None:
        session, _evidence = _trusted_broker_session(expected_principal)
    response = session.post(
        f"https://storage.googleapis.com/upload/storage/v1/b/"
        f"{quote(bucket, safe='')}/o",
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


def _consume_provisioning_permit(
    permit: dict[str, Any], *, authoritative_now: datetime | None = None,
    session: Any | None = None,
) -> dict[str, str]:
    now = (authoritative_now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if now < _aware_datetime(permit["not_before"], field="not_before"):
        raise CanaryJobProvisioningError(
            "provisioning permit is not active at dispatch"
        )
    if now >= _aware_datetime(permit["expires_at"], field="expires_at"):
        raise CanaryJobProvisioningError(
            "provisioning permit expired before dispatch"
        )
    object_name = (
        f"canary-job-provisioning/{permit['release_sha']}/"
        f"{permit['permit_id']}.json"
    )
    record = {
        "schema_version": "aigc.nexus-canary-job-provisioning-consumption.v1",
        "permit_id": permit["permit_id"],
        "permit_sha256": permit["permit_sha256"],
        "target": permit["target"],
        "job_spec_sha256": permit["job_spec_sha256"],
        "state": "consumed_before_dispatch",
        "maximum_mutations": 1,
        "automatic_retry": False,
        "job_execution_authorized": False,
        "live_model_call_authorized": False,
        "consumed_at": now.isoformat(),
    }
    content = canonical_json_bytes(record)
    try:
        kwargs: dict[str, Any] = {
            "bucket": permit["receipt_bucket"],
            "object_name": object_name,
            "content": content,
            "expected_principal": permit["provisioner_principal"],
        }
        if session is not None:
            kwargs["session"] = session
        status_code, response = _authorized_storage_create_only(**kwargs)
    except Exception as exc:
        raise CanaryJobProvisioningIndeterminate(
            "provisioning permit consumption is indeterminate; treat it as burned"
        ) from exc
    if status_code in {409, 412}:
        raise CanaryJobProvisioningPermitConsumed(
            "provisioning permit was already consumed; job was not deployed"
        )
    if status_code not in {200, 201}:
        raise CanaryJobProvisioningIndeterminate(
            "provisioning permit consumption is indeterminate; treat it as burned"
        )
    generation = str(response.get("generation") or "")
    if (
        response.get("bucket") != permit["receipt_bucket"]
        or response.get("name") != object_name
        or not generation.isdigit()
        or int(generation) <= 0
    ):
        raise CanaryJobProvisioningIndeterminate(
            "provisioning permit receipt is invalid; treat it as burned"
        )
    return {
        "provisioning_permit_id": permit["permit_id"],
        "provisioning_permit_sha256": permit["permit_sha256"],
        "permit_consumption_uri": (
            f"gs://{permit['receipt_bucket']}/{object_name}"
        ),
        "permit_consumption_generation": generation,
        "permit_consumption_record_sha256": hashlib.sha256(content).hexdigest(),
    }


def _cloud_run_job_payload(job_spec: dict[str, Any]) -> dict[str, Any]:
    """Build the exact dormant Cloud Run v2 Job representation.

    The execution permit is carried as inert environment data.  Provisioning never
    calls :run and the provisioner role has no run permission.
    """
    container = {
        "image": job_spec["immutable_image_uri"],
        "command": ["python"],
        "args": ["-m", "src.operations.nexus_provider_canary"],
        "env": [
            {"name": key, "value": value}
            for key, value in sorted(job_spec["authority_environment"].items())
        ],
        "volumeMounts": [{"name": "cloudsql", "mountPath": "/cloudsql"}],
    }
    return {
        "name": job_spec["target"],
        "labels": job_spec["labels"],
        "template": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {
                "serviceAccount": job_spec["runtime_service_account"],
                "containers": [container],
                "maxRetries": 0,
                "timeout": "180s",
                "vpcAccess": {
                    "networkInterfaces": [{
                        "network": job_spec["network"],
                        "subnetwork": job_spec["subnet"],
                    }],
                    "egress": "PRIVATE_RANGES_ONLY",
                },
                "volumes": [{
                    "name": "cloudsql",
                    "cloudSqlInstance": {
                        "instances": [job_spec["cloud_sql_connection"]]
                    },
                }],
            },
        },
    }


def _json_response(response: Any, *, label: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryJobProvisioningIndeterminate(
            f"{label} returned invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise CanaryJobProvisioningIndeterminate(f"{label} returned invalid evidence")
    return payload


def _wait_operation(session: Any, operation: dict[str, Any]) -> dict[str, Any]:
    operation_name = str(operation.get("name") or "")
    if not operation_name.startswith("projects/") or "/operations/" not in operation_name:
        raise CanaryJobProvisioningIndeterminate("Cloud Run mutation operation is unbound")
    deadline = time.monotonic() + 180
    while not operation.get("done"):
        if time.monotonic() >= deadline:
            raise CanaryJobProvisioningIndeterminate("Cloud Run mutation timed out")
        time.sleep(1)
        response = session.get(
            f"https://run.googleapis.com/v2/{operation_name}", timeout=10
        )
        operation = _json_response(response, label="Cloud Run operation readback")
        if response.status_code != 200:
            raise CanaryJobProvisioningIndeterminate(
                "Cloud Run operation readback failed"
            )
    if operation.get("error"):
        raise CanaryJobProvisioningIndeterminate("Cloud Run job mutation failed")
    return operation


def _provision_job(
    *, session: Any | None, project: str, job_spec: dict[str, Any]
) -> None:
    if session is None:
        raise CanaryJobProvisioningError("bounded provisioner REST session is required")
    target_url = f"https://run.googleapis.com/v2/{job_spec['target']}"
    before = session.get(target_url, timeout=10)
    payload = _cloud_run_job_payload(job_spec)
    if before.status_code == 404:
        response = session.post(
            f"https://run.googleapis.com/v2/projects/{project}/locations/{REGION}/jobs",
            params={"jobId": job_spec["job_name"]}, json=payload, timeout=10,
        )
    elif before.status_code == 200:
        observed = _json_response(before, label="Cloud Run pre-mutation readback")
        etag = observed.get("etag")
        if not isinstance(etag, str) or not etag:
            raise CanaryJobProvisioningError("Cloud Run job etag is required for update")
        payload["etag"] = etag
        response = session.patch(
            target_url,
            params={"updateMask": "labels,template"},
            json=payload,
            timeout=10,
        )
    else:
        raise CanaryJobProvisioningError("Cloud Run pre-mutation readback failed")
    operation = _json_response(response, label="Cloud Run job mutation")
    if response.status_code not in {200, 201}:
        raise CanaryJobProvisioningIndeterminate("Cloud Run job mutation is indeterminate")
    _wait_operation(session, operation)


def _describe_provisioned_job(
    *, session: Any | None, project: str, job_spec: dict[str, Any]
) -> dict[str, Any]:
    if session is None:
        raise CanaryJobProvisioningError("bounded provisioner REST session is required")
    response = session.get(
        f"https://run.googleapis.com/v2/{job_spec['target']}", timeout=10
    )
    payload = _json_response(response, label="Cloud Run exact-job readback")
    if response.status_code != 200:
        raise CanaryJobProvisioningIndeterminate("Cloud Run exact-job readback failed")
    return payload


def provision(
    *,
    procurement: ExternalReleaseContract,
    deployment: dict[str, Any],
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    execution_permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    provisioning_permit: dict[str, Any],
    output: Path,
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    _require_new_output(output)
    project = procurement.project_id
    prefix = procurement.prefix
    now = authoritative_now or _utc_now()
    immutable_image = str(deployment.get("immutable_image_uri") or "")
    if not IMMUTABLE_IMAGE.fullmatch(immutable_image):
        raise CanaryJobProvisioningError(
            "deployment receipt has no exact immutable image URI"
        )
    job_name = _expected_job_name(
        prefix=prefix,
        provider_id=plan.provider_id,
        permit_id=execution_permit.permit_id,
    )
    expected_key_version = expected_canary_authority_key_version(
        project_id=project,
        resource_prefix=prefix,
    )
    identities = expected_canary_job_identities(
        prefix=prefix,
        project=project,
        provider_id=plan.provider_id,
    )
    try:
        _validate_authority(
            procurement,
            deployment,
            plan,
            decision,
            execution_permit,
            attestation,
            expected_kms_key_version=expected_key_version,
            authoritative_now=now,
            expected_job_name=job_name,
        )
    except CanaryLaunchError as exc:
        raise CanaryJobProvisioningError(str(exc)) from exc
    job_spec = expected_canary_job_spec(
        project=project,
        prefix=prefix,
        plan=plan,
        decision=decision,
        execution_permit=execution_permit,
        attestation=attestation,
        immutable_image=immutable_image,
    )
    permit = validate_provisioning_permit(
        provisioning_permit,
        procurement=procurement,
        deployment=deployment,
        plan=plan,
        decision=decision,
        execution_permit=execution_permit,
        attestation=attestation,
        job_spec=job_spec,
        authoritative_now=now,
    )
    session, broker_identity_evidence = _trusted_broker_session(
        job_spec["provisioner_principal"]
    )
    broker_authority_evidence = _verify_expiring_broker_authority(
        session=session,
        permit=permit,
        runtime_service_account=job_spec["runtime_service_account"],
        prefix=prefix,
    )
    identity_evidence = {
        **broker_identity_evidence,
        **broker_authority_evidence,
        "account_level_impersonation_grant_claimed": False,
    }
    permission_evidence = _preflight_provisioner_permissions(
        project=project,
        job_name=job_name,
        runtime_service_account=job_spec["runtime_service_account"],
        receipt_bucket=permit["receipt_bucket"],
        provisioner_principal=job_spec["provisioner_principal"],
        session=session,
    )
    dispatch_now = _utc_now()
    try:
        _validate_authority(
            procurement,
            deployment,
            plan,
            decision,
            execution_permit,
            attestation,
            expected_kms_key_version=expected_key_version,
            authoritative_now=dispatch_now,
            expected_job_name=job_name,
        )
    except CanaryLaunchError as exc:
        raise CanaryJobProvisioningError(str(exc)) from exc
    permit = validate_provisioning_permit(
        provisioning_permit,
        procurement=procurement,
        deployment=deployment,
        plan=plan,
        decision=decision,
        execution_permit=execution_permit,
        attestation=attestation,
        job_spec=job_spec,
        authoritative_now=dispatch_now,
    )
    _verify_expiring_broker_authority(
        session=session,
        permit=permit,
        runtime_service_account=job_spec["runtime_service_account"],
        prefix=prefix,
    )
    consumption = _consume_provisioning_permit(
        permit, authoritative_now=dispatch_now, session=session
    )
    try:
        _provision_job(session=session, project=project, job_spec=job_spec)
    except CanaryJobProvisioningIndeterminate:
        raise
    except (OSError, CanaryJobProvisioningError) as exc:
        raise CanaryJobProvisioningIndeterminate(
            "provisioning permit was burned but exact job mutation is indeterminate"
        ) from exc
    try:
        described = _describe_provisioned_job(
            session=session, project=project, job_spec=job_spec
        )
        job_target = _validate_job_description(
            described,
            job_name=job_name,
            immutable_image=immutable_image,
            service_account=job_spec["runtime_service_account"],
            expected_environment=job_spec["authority_environment"],
            expected_network=job_spec["network"],
            expected_subnet=job_spec["subnet"],
            expected_cloud_sql=job_spec["cloud_sql_connection"],
            release_sha=plan.exact_revision,
            provider_label=job_spec["provider_label"],
        )
    except (
        CanaryLaunchError,
        CanaryJobProvisioningError,
        json.JSONDecodeError,
    ) as exc:
        raise CanaryJobProvisioningIndeterminate(
            "canary job mutation completed but exact target readback failed"
        ) from exc
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "project_id": project,
        "project_number": procurement.project_number,
        "region": REGION,
        "release_sha": plan.exact_revision,
        "provider_id": plan.provider_id,
        "job_name": job_name,
        "target": job_spec["target"],
        "immutable_image_uri": immutable_image,
        "reserved_usage_units": plan.reserved_usage_units,
        "maximum_input_units": plan.maximum_input_units,
        "maximum_output_units": plan.maximum_output_units,
        "request_timeout_seconds": plan.request_timeout_seconds,
        "runtime_service_account": job_spec["runtime_service_account"],
        "provisioner_principal": job_spec["provisioner_principal"],
        "executor_principal": job_spec["executor_principal"],
        "job_spec_sha256": canonical_sha256(job_spec),
        "authority_environment_sha256": canonical_sha256(
            job_spec["authority_environment"]
        ),
        "identity_evidence": identity_evidence,
        "permission_evidence": permission_evidence,
        "job_target": job_target,
        **consumption,
        "job_deployment_performed": True,
        "job_execution_performed": False,
        "execution_overrides_authorized": False,
        "provider_call_performed": False,
        "cloud_run_mutation_count": 1,
        "captured_at": now.astimezone(timezone.utc).isoformat(),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    _write_new_receipt(output, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--procurement", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--governance", type=Path, required=True)
    parser.add_argument("--permit", type=Path, required=True)
    parser.add_argument("--authority-attestation", type=Path, required=True)
    parser.add_argument("--provisioning-permit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise CanaryJobProvisioningError(
            "canary job provisioning is inert unless --execute is supplied"
        )
    procurement = ExternalReleaseContract.load(args.procurement)
    deployment = _object(args.deployment_receipt)
    plan = ProviderCanaryPlan.model_validate(_object(args.plan))
    decision = GovernanceDecision.model_validate(_object(args.governance))
    execution_permit = ExecutionPermit.model_validate(_object(args.permit))
    attestation = AuthorityAttestation.model_validate(
        _object(args.authority_attestation)
    )
    provision(
        procurement=procurement,
        deployment=deployment,
        plan=plan,
        decision=decision,
        execution_permit=execution_permit,
        attestation=attestation,
        provisioning_permit=_object(args.provisioning_permit),
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CanaryJobProvisioningError as exc:
        raise SystemExit(f"Nexus canary job provisioning blocked: {exc}") from exc
