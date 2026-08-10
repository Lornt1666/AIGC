from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Sequence
from urllib.parse import quote

from jsonschema import Draft202012Validator, FormatChecker

from scripts.aigc_external_release_procurement import ExternalReleaseContract, ProcurementError
from scripts.nexus_canary_impersonation import (
    bounded_impersonated_session,
    jit_request_sha256,
    validate_jit_impersonation_receipt,
    verify_kms_signed_payload,
)
from src.core.epistemic.canonicalization import canonical_sha256
from src.operations.nexus_provider_canary import (
    CanaryConfigurationError,
    ProviderCanaryPlan,
    build_invocation,
    expected_canary_authority_key_version,
    fetch_kms_authority_public_key,
    validate_canary_authority,
)
from src.domain.nexus.contracts import (
    AuthorityAttestation,
    ExecutionReceipt,
    ExecutionPermit,
    GovernanceDecision,
)
from src.domain.nexus.provider_runtime import (
    ProviderAttemptResult,
    ProviderRuntimeAudit,
)


REGION = "northamerica-northeast1"
ROOT = Path(__file__).resolve().parents[1]
IMMUTABLE_IMAGE = re.compile(r"^[a-z0-9.-]+-docker\.pkg\.dev/.+@sha256:[a-f0-9]{64}$")
MARKER = "AIGC_CANARY_RECEIPT:"
EXECUTION_NAME = re.compile(r"^[a-z](?:[a-z0-9-]{0,126}[a-z0-9])?$")
_LIVE_RECEIPT_KEYS = {
    "schema_version", "provider_id", "project_id", "region",
    "execution_region", "provider_location", "model", "reserved_usage_units",
    "maximum_input_units", "maximum_output_units", "request_timeout_seconds",
    "exact_revision", "plan_sha256", "authority_attestation_sha256",
    "permit_id", "request_digest", "job_name", "execution_name",
    "invocation_id", "attempt", "receipt", "audit", "replayed",
    "response_payload_retained", "captured_at", "canary_receipt_id",
}
_BINDING_RECEIPT_KEYS = {
    "schema_version", "project_id", "project_number", "region", "release_sha",
    "provider_id", "job_name", "target", "binder_principal",
    "executor_principal", "provisioning_receipt_sha256", "binding_permit_id",
    "binding_permit_sha256", "identity_evidence", "permission_evidence",
    "provisioner_quiescence_evidence",
    "binding", "policy_before_sha256", "policy_after_sha256",
    "permit_consumption_uri", "permit_consumption_generation",
    "permit_consumption_record_sha256", "permit_consumption_readback_verified",
    "iam_mutation_count",
    "project_wide_binding", "run_with_overrides_authorized", "automatic_retry",
    "binder_authority_expires_at", "binding_expires_at", "captured_at",
    "receipt_sha256",
}


class CanaryLaunchError(RuntimeError):
    pass


class CanaryLaunchIndeterminate(CanaryLaunchError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_new_output(output: Path) -> None:
    if output.exists():
        raise CanaryLaunchError(
            "canary receipt output already exists and will not be overwritten"
        )


def _write_new_receipt(output: Path, receipt: dict[str, Any]) -> None:
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    except OSError as exc:
        raise CanaryLaunchIndeterminate(
            "canary executed but its create-only local receipt could not be written"
        ) from exc


def _run(command: Sequence[str], *, mutating: bool = False) -> str:
    completed = subprocess.run(
        list(command), capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        error = CanaryLaunchIndeterminate if mutating else CanaryLaunchError
        raise error(f"command failed: {' '.join(command[:4])}")
    return completed.stdout.strip()


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanaryLaunchError(f"{path} must contain a JSON object")
    return value


def _validate_authority(
    procurement: ExternalReleaseContract,
    deployment: dict[str, Any],
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    *,
    expected_kms_key_version: str,
    authoritative_now: datetime,
    expected_job_name: str,
) -> None:
    flag = (
        "gemini_canary_authorized"
        if plan.provider_id == "google_vertex_gemini"
        else "openai_canary_authorized"
    )
    if procurement.authority.get(flag) is not True:
        raise CanaryLaunchError(f"{flag} is not authorized")
    spend = Decimal(str(procurement.payload.get("provider_canary_spend_cad", 0)))
    if spend <= 0 or plan.maximum_cost_cad > spend:
        raise CanaryLaunchError("provider canary cost exceeds the procurement spend ceiling")
    invocation = build_invocation(plan, permit_id=permit.permit_id)
    if permit.request_digest != invocation.request_digest:
        raise CanaryLaunchError("permit request digest does not match the canary plan")
    if permit.maximum_invocations != 1:
        raise CanaryLaunchError("canary permit must be one-use")
    if decision.decision != "approved" or decision.decision_id != permit.governance_decision_id:
        raise CanaryLaunchError("canonical governance/permit binding is not approved")
    if procurement.project_id != plan.project_id or procurement.payload.get("region") != plan.location:
        raise CanaryLaunchError("procurement project/region does not match the canary plan")
    if procurement.payload.get("release_sha") != plan.exact_revision:
        raise CanaryLaunchError("procurement release SHA does not match the canary plan")
    procurement_sha256 = canonical_sha256(procurement.payload)
    deployment_sha256 = canonical_sha256(deployment)
    if plan.procurement_sha256 != procurement_sha256:
        raise CanaryLaunchError("canary plan procurement digest mismatch")
    if plan.deployment_sha256 != deployment_sha256:
        raise CanaryLaunchError("canary plan deployment digest mismatch")
    if procurement.authority.get("authorized_by") != decision.authority_actor:
        raise CanaryLaunchError("procurement authority actor does not match governance authority")
    try:
        validate_canary_authority(
            plan,
            invocation,
            decision,
            permit,
            attestation,
            expected_kms_key_version=expected_kms_key_version,
            authoritative_now=authoritative_now,
            expected_job_name=expected_job_name,
        )
    except (CanaryConfigurationError, ValueError) as exc:
        raise CanaryLaunchError(str(exc)) from exc


def _expected_job_name(
    *,
    prefix: str,
    provider_id: str,
    permit_id: str,
) -> str:
    short_provider = "gemini" if provider_id == "google_vertex_gemini" else "openai"
    permit_binding = hashlib.sha256(permit_id.encode("utf-8")).hexdigest()[:12]
    value = f"{prefix}-{short_provider}-{permit_binding}"
    if not re.fullmatch(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$", value):
        raise CanaryLaunchError("derived canary job name is invalid")
    return value


def _expected_executor_identity(*, prefix: str, project: str) -> str:
    identity = f"{prefix}-can-exec@{project}.iam.gserviceaccount.com"
    if not re.fullmatch(
        r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]"
        r"\.iam\.gserviceaccount\.com$",
        identity,
    ):
        raise CanaryLaunchError("derived canary executor identity is invalid")
    return identity


def _authority_environment(
    *,
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
) -> dict[str, str]:
    return {
        "AIGC_CANARY_PLAN_JSON": json.dumps(
            plan.model_dump(mode="json"), sort_keys=True
        ),
        "AIGC_CANARY_GOVERNANCE_JSON": json.dumps(
            decision.model_dump(mode="json"), sort_keys=True
        ),
        "AIGC_CANARY_PERMIT_JSON": json.dumps(
            permit.model_dump(mode="json"), sort_keys=True
        ),
        "AIGC_CANARY_AUTHORITY_ATTESTATION_JSON": json.dumps(
            attestation.model_dump(mode="json"), sort_keys=True
        ),
    }


def _nested(mapping: dict[str, Any], *paths: Sequence[str]) -> Any:
    observed: list[Any] = []
    for path in paths:
        value: Any = mapping
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value is not None:
            observed.append(value)
    if not observed:
        return None
    if any(candidate != observed[0] for candidate in observed[1:]):
        raise CanaryLaunchError("Cloud Run execution contains conflicting field representations")
    return observed[0]


def _containers(described: dict[str, Any]) -> list[dict[str, Any]]:
    containers = _nested(
        described,
        ("spec", "template", "spec", "template", "spec", "containers"),
        ("spec", "template", "spec", "containers"),
        ("spec", "template", "containers"),
        ("template", "template", "containers"),
        ("template", "containers"),
    ) or []
    if len(containers) != 1 or not isinstance(containers[0], dict):
        raise CanaryLaunchError("Cloud Run target must contain exactly one container")
    return containers


def _plain_environment(container: dict[str, Any]) -> dict[str, str]:
    raw_environment = container.get("env") or []
    if not isinstance(raw_environment, list):
        raise CanaryLaunchError("Cloud Run target environment is invalid")
    observed_environment: dict[str, str] = {}
    for item in raw_environment:
        if not isinstance(item, dict) or "valueSource" in item or "valueFrom" in item:
            raise CanaryLaunchError("Cloud Run target contains a sourced environment value")
        name = item.get("name")
        value = item.get("value")
        if not isinstance(name, str) or not isinstance(value, str) or name in observed_environment:
            raise CanaryLaunchError("Cloud Run target environment is ambiguous")
        observed_environment[name] = value
    return observed_environment


def _cloud_sql_attachment(
    described: dict[str, Any],
    container: dict[str, Any],
    *,
    expected_cloud_sql: str,
) -> dict[str, Any]:
    volumes = _nested(
        described,
        ("spec", "template", "spec", "template", "spec", "volumes"),
        ("spec", "template", "spec", "volumes"),
        ("spec", "template", "volumes"),
        ("template", "template", "volumes"),
        ("template", "volumes"),
    ) or []
    mounts = container.get("volumeMounts") or container.get("volume_mounts") or []
    if not isinstance(volumes, list) or not isinstance(mounts, list):
        raise CanaryLaunchError("Cloud Run target has invalid volume evidence")
    volume_proof = False
    if volumes:
        if len(volumes) != 1 or not isinstance(volumes[0], dict):
            raise CanaryLaunchError("Cloud Run target contains an unauthorized volume")
        volume = volumes[0]
        source = volume.get("cloudSqlInstance") or volume.get("cloud_sql_instance")
        instances = source.get("instances") if isinstance(source, dict) else None
        volume_name = volume.get("name")
        if instances != [expected_cloud_sql] or not isinstance(volume_name, str):
            raise CanaryLaunchError("Cloud Run target Cloud SQL volume mismatch")
        if len(mounts) != 1 or not isinstance(mounts[0], dict):
            raise CanaryLaunchError("Cloud Run target Cloud SQL mount mismatch")
        mount = mounts[0]
        mount_name = mount.get("name") or mount.get("volume")
        mount_path = mount.get("mountPath") or mount.get("mount_path")
        if mount_name != volume_name or mount_path != "/cloudsql":
            raise CanaryLaunchError("Cloud Run target Cloud SQL mount mismatch")
        volume_proof = True
    elif mounts:
        raise CanaryLaunchError("Cloud Run target contains an orphaned volume mount")

    annotation_values: list[str] = []
    for path in (
        ("metadata", "annotations"),
        ("spec", "template", "metadata", "annotations"),
        ("spec", "template", "spec", "template", "metadata", "annotations"),
        ("template", "annotations"),
        ("template", "template", "annotations"),
    ):
        value: Any = described
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise CanaryLaunchError("Cloud Run target annotations are invalid")
        annotation = value.get("run.googleapis.com/cloudsql-instances")
        if annotation is not None:
            annotation_values.append(str(annotation))
    if any(value != expected_cloud_sql for value in annotation_values):
        raise CanaryLaunchError("Cloud Run target Cloud SQL annotation mismatch")
    annotation_proof = bool(annotation_values)
    if not volume_proof and not annotation_proof:
        raise CanaryLaunchError("Cloud Run target lacks the exact Cloud SQL attachment")
    return {
        "cloud_sql_connection": expected_cloud_sql,
        "cloud_sql_volume_verified": volume_proof,
        "cloud_sql_annotation_verified": annotation_proof,
    }


def _direct_vpc_attachment(
    described: dict[str, Any],
    *,
    expected_network: str,
    expected_subnet: str,
) -> None:
    vpc_access = _nested(
        described,
        ("spec", "template", "spec", "template", "spec", "vpcAccess"),
        ("spec", "template", "spec", "vpcAccess"),
        ("spec", "template", "vpcAccess"),
        ("template", "template", "vpcAccess"),
        ("template", "vpcAccess"),
    )
    if not isinstance(vpc_access, dict) or vpc_access.get("connector"):
        raise CanaryLaunchError("Cloud Run target does not use the exact direct VPC attachment")
    interfaces = vpc_access.get("networkInterfaces") or []
    if len(interfaces) != 1 or not isinstance(interfaces[0], dict):
        raise CanaryLaunchError("Cloud Run target direct VPC attachment is ambiguous")
    interface = interfaces[0]
    observed_network = str(interface.get("network") or "").rsplit("/", 1)[-1]
    observed_subnet = str(interface.get("subnetwork") or "").rsplit("/", 1)[-1]
    observed_egress = str(vpc_access.get("egress") or "").lower().replace("_", "-")
    if (
        observed_network != expected_network
        or observed_subnet != expected_subnet
        or observed_egress != "private-ranges-only"
        or interface.get("tags")
    ):
        raise CanaryLaunchError("Cloud Run target direct VPC scope mismatch")


def _validate_job_description(
    described: dict[str, Any],
    *,
    job_name: str,
    immutable_image: str,
    service_account: str,
    expected_environment: dict[str, str],
    expected_network: str,
    expected_subnet: str,
    expected_cloud_sql: str,
    release_sha: str,
    provider_label: str,
) -> dict[str, Any]:
    if not isinstance(described, dict):
        raise CanaryLaunchError("Cloud Run returned invalid preprovisioned-job evidence")
    observed_name = str(_nested(described, ("metadata", "name"), ("name",)) or "")
    container = _containers(described)[0]
    observed_account = _nested(
        described,
        ("spec", "template", "spec", "template", "spec", "serviceAccountName"),
        ("spec", "template", "spec", "serviceAccountName"),
        ("template", "template", "serviceAccount"),
        ("template", "serviceAccount"),
    )
    labels = _nested(described, ("metadata", "labels"), ("labels",)) or {}
    if observed_name.rsplit("/", 1)[-1] != job_name:
        raise CanaryLaunchError("dormant Cloud Run job identity mismatch")
    if container.get("image") != immutable_image or observed_account != service_account:
        raise CanaryLaunchError("dormant Cloud Run job image/service-account mismatch")
    if _plain_environment(container) != expected_environment:
        raise CanaryLaunchError(
            "preprovisioned Cloud Run job authority environment mismatch"
        )
    if container.get("command") != ["python"] or container.get("args") != [
        "-m",
        "src.operations.nexus_provider_canary",
    ]:
        raise CanaryLaunchError("preprovisioned Cloud Run job command mismatch")
    if not isinstance(labels, dict) or (
        labels.get("aigc-release-sha") != release_sha
        or labels.get("aigc-provider") != provider_label
        or labels.get("aigc-dormant-canary") != "true"
    ):
        raise CanaryLaunchError("preprovisioned Cloud Run job labels mismatch")
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
    max_retries = _nested(
        described,
        ("spec", "template", "spec", "template", "spec", "maxRetries"),
        ("template", "template", "maxRetries"),
    )
    timeout = _nested(
        described,
        ("spec", "template", "spec", "template", "spec", "timeout"),
        ("template", "template", "timeout"),
    )
    retry_count = -1 if max_retries is None else int(max_retries)
    if (int(task_count or 0), int(parallelism or 0), retry_count) != (1, 1, 0):
        raise CanaryLaunchError("preprovisioned Cloud Run job task/retry bounds mismatch")
    if str(timeout or "").lower() not in {"180s", "180.0s"}:
        raise CanaryLaunchError("preprovisioned Cloud Run job timeout mismatch")
    _direct_vpc_attachment(
        described,
        expected_network=expected_network,
        expected_subnet=expected_subnet,
    )
    cloud_sql = _cloud_sql_attachment(
        described,
        container,
        expected_cloud_sql=expected_cloud_sql,
    )
    return {
        "job_name": job_name,
        "immutable_image_uri": immutable_image,
        "service_account": service_account,
        "authority_environment_sha256": canonical_sha256(expected_environment),
        **cloud_sql,
        "job_description_sha256": canonical_sha256(described),
    }


def _job_target(
    *,
    project: str,
    region: str,
    job_name: str,
    immutable_image: str,
    service_account: str,
    expected_environment: dict[str, str],
    expected_network: str,
    expected_subnet: str,
    expected_cloud_sql: str,
    release_sha: str,
    provider_label: str,
    reader_service_account: str,
    session: Any | None = None,
) -> dict[str, Any]:
    if session is None:
        raise CanaryLaunchError("bounded executor REST session is required")
    response = session.get(
        f"https://run.googleapis.com/v2/projects/{project}/locations/"
        f"{region}/jobs/{job_name}",
        timeout=10,
    )
    try:
        described = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryLaunchError("Cloud Run job readback is invalid JSON") from exc
    if response.status_code != 200:
        raise CanaryLaunchError("Cloud Run job readback failed")
    return _validate_job_description(
        described,
        job_name=job_name,
        immutable_image=immutable_image,
        service_account=service_account,
        expected_environment=expected_environment,
        expected_network=expected_network,
        expected_subnet=expected_subnet,
        expected_cloud_sql=expected_cloud_sql,
        release_sha=release_sha,
        provider_label=provider_label,
    )


def _execution_target(
    *,
    project: str,
    region: str,
    execution_name: str,
    job_name: str | None = None,
    immutable_image: str,
    service_account: str,
    expected_environment: dict[str, str],
    expected_network: str,
    expected_subnet: str,
    expected_cloud_sql: str,
    reader_service_account: str,
    session: Any | None = None,
) -> dict[str, Any]:
    if session is None:
        raise CanaryLaunchError("bounded executor REST session is required")
    if job_name is None:
        raise CanaryLaunchError("exact execution job name is required")
    response = session.get(
        f"https://run.googleapis.com/v2/projects/{project}/locations/"
        f"{region}/jobs/{job_name}/executions/{execution_name}",
        timeout=10,
    )
    try:
        described = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryLaunchError("Cloud Run execution readback is invalid JSON") from exc
    if response.status_code != 200:
        raise CanaryLaunchError("Cloud Run execution readback failed")
    if not isinstance(described, dict):
        raise CanaryLaunchError("Cloud Run returned invalid execution evidence")
    observed_name = str(_nested(described, ("metadata", "name"), ("name",)) or "")
    container = _containers(described)[0]
    observed_account = _nested(
        described,
        ("spec", "template", "spec", "serviceAccountName"),
        ("spec", "template", "serviceAccountName"),
        ("template", "serviceAccount"),
        ("template", "serviceAccountName"),
    )
    observed_environment = _plain_environment(container)
    _direct_vpc_attachment(
        described,
        expected_network=expected_network,
        expected_subnet=expected_subnet,
    )
    cloud_sql = _cloud_sql_attachment(
        described,
        container,
        expected_cloud_sql=expected_cloud_sql,
    )
    if observed_name.rsplit("/", 1)[-1] != execution_name:
        raise CanaryLaunchError("Cloud Run execution description identity mismatch")
    if container.get("image") != immutable_image or observed_account != service_account:
        raise CanaryLaunchError("Cloud Run execution image/service-account mismatch")
    if observed_environment != expected_environment:
        raise CanaryLaunchError("Cloud Run execution authority environment mismatch")
    return {
        "execution_name": execution_name,
        "immutable_image_uri": immutable_image,
        "service_account": service_account,
        "network": expected_network,
        "subnet": expected_subnet,
        "vpc_egress": "private-ranges-only",
        **cloud_sql,
        "sourced_environment_values_present": False,
        "execution_description_sha256": canonical_sha256(described),
    }


def _receipt_from_logs(
    *,
    project: str,
    region: str,
    job_name: str,
    execution_name: str,
    reader_service_account: str | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    filter_expr = (
        'resource.type="cloud_run_job" '
        f'AND resource.labels.job_name="{job_name}" '
        f'AND resource.labels.location="{region}" '
        f'AND labels."run.googleapis.com/execution_name"="{execution_name}" '
        f'AND textPayload:"{MARKER}"'
    )
    if session is None:
        raise CanaryLaunchError("bounded executor REST session is required")
    response = session.post(
            "https://logging.googleapis.com/v2/entries:list",
            json={
                "resourceNames": [f"projects/{project}"],
                "filter": filter_expr,
                "orderBy": "timestamp desc",
                "pageSize": 20,
            },
            timeout=10,
    )
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryLaunchError("Cloud Logging returned invalid JSON") from exc
    if response.status_code != 200 or not isinstance(payload, dict):
        raise CanaryLaunchError("Cloud Logging read failed")
    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        raise CanaryLaunchError("Cloud Logging returned invalid canary evidence")
    matches: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource_labels = (entry.get("resource") or {}).get("labels") or {}
        execution_label = (entry.get("labels") or {}).get(
            "run.googleapis.com/execution_name"
        )
        if (
            resource_labels.get("project_id") != project
            or resource_labels.get("location") != region
            or resource_labels.get("job_name") != job_name
            or execution_label != execution_name
        ):
            continue
        text = str(entry.get("textPayload") or "")
        index = text.find(MARKER)
        if index < 0:
            continue
        candidate = text[index + len(MARKER):].strip()
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            matches[canonical_sha256(payload)] = payload
    if len(matches) != 1:
        raise CanaryLaunchError(
            "exactly one execution-bound canary receipt marker is required in Cloud Logging"
        )
    return next(iter(matches.values()))


def _validate_provider_receipt(
    receipt: dict[str, Any],
    *,
    plan: ProviderCanaryPlan,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    job_name: str,
    execution_name: str,
) -> None:
    if set(receipt) != _LIVE_RECEIPT_KEYS:
        raise CanaryLaunchError(
            "live provider receipt fields do not match the exact redacted contract"
        )
    try:
        captured_at = datetime.fromisoformat(
            str(receipt["captured_at"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise CanaryLaunchError("live provider receipt captured_at is invalid") from exc
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise CanaryLaunchError("live provider receipt captured_at is not timezone-aware")
    captured_at = captured_at.astimezone(timezone.utc)
    if not (attestation.issued_at <= captured_at < attestation.expires_at):
        raise CanaryLaunchError(
            "live provider receipt captured_at is outside signed execution authority"
        )
    receipt_id = receipt.get("canary_receipt_id")
    unsigned = dict(receipt)
    unsigned.pop("canary_receipt_id", None)
    expected_receipt_id = "CANARY-" + canonical_sha256(unsigned)[:24].upper()
    if receipt_id != expected_receipt_id:
        raise CanaryLaunchError("canonical canary receipt ID mismatch")
    invocation = build_invocation(plan, permit_id=permit.permit_id)
    exact_fields = {
        "schema_version": "aigc.nexus-live-provider-canary-receipt.v2",
        "provider_id": plan.provider_id,
        "project_id": plan.project_id,
        "region": plan.location,
        "execution_region": plan.location,
        "provider_location": plan.provider_location,
        "model": plan.model,
        "reserved_usage_units": plan.reserved_usage_units,
        "maximum_input_units": plan.maximum_input_units,
        "maximum_output_units": plan.maximum_output_units,
        "request_timeout_seconds": plan.request_timeout_seconds,
        "exact_revision": plan.exact_revision,
        "plan_sha256": canonical_sha256(plan.model_dump(mode="json")),
        "authority_attestation_sha256": canonical_sha256(
            attestation.model_dump(mode="json")
        ),
        "permit_id": permit.permit_id,
        "request_digest": invocation.request_digest,
        "job_name": job_name,
        "execution_name": execution_name,
        "invocation_id": invocation.invocation_id,
        "replayed": False,
        "response_payload_retained": False,
    }
    for field, expected in exact_fields.items():
        if receipt.get(field) != expected:
            raise CanaryLaunchError(f"retrieved canary receipt {field} mismatch")

    try:
        attempt = ProviderAttemptResult.model_validate(receipt.get("attempt"))
        core_receipt = ExecutionReceipt.model_validate(receipt.get("receipt"))
        audit = ProviderRuntimeAudit.model_validate(receipt.get("audit"))
    except ValueError as exc:
        raise CanaryLaunchError(
            "retrieved canary receipt has invalid nested evidence"
        ) from exc
    if attempt.response_payload is not None:
        raise CanaryLaunchError("retrieved canary receipt contains raw provider output")
    if (
        attempt.status != "succeeded"
        or attempt.invocation_id != invocation.invocation_id
        or attempt.provider_id != plan.provider_id
        or attempt.model_or_resource != plan.model
        or attempt.provider_request_id is None
        or attempt.response_digest is None
        or attempt.external_action_performed is not True
        or attempt.outcome_known is not True
        or attempt.cost_known is not True
    ):
        raise CanaryLaunchError("live provider attempt correlation/status mismatch")
    if (
        core_receipt.permit_id != permit.permit_id
        or core_receipt.change_set_id != plan.change_set_id
        or core_receipt.parent_state_hash != plan.parent_state_hash
        or core_receipt.execution_status != attempt.status
        or core_receipt.external_action_performed is not True
        or core_receipt.reconciliation_required is not False
    ):
        raise CanaryLaunchError("live provider core receipt correlation mismatch")
    operations = core_receipt.operations
    if len(operations) != 1:
        raise CanaryLaunchError("live provider core receipt must contain one operation")
    operation = operations[0]
    if (
        operation.operation_id != invocation.invocation_id
        or operation.resource_ref != plan.resource_ref
        or operation.status != attempt.status
        or operation.after_hash != attempt.response_digest
    ):
        raise CanaryLaunchError("live provider operation receipt mismatch")
    if (
        attempt.usage_units is None
        or attempt.input_usage_units is None
        or attempt.output_usage_units is None
        or attempt.input_usage_units > plan.maximum_input_units
        or attempt.output_usage_units > plan.maximum_output_units
        or attempt.usage_units > plan.reserved_usage_units
        or attempt.usage_units
        < attempt.input_usage_units + attempt.output_usage_units
    ):
        raise CanaryLaunchError("live provider measured usage exceeds signed plan")
    if attempt.cost_cad > plan.maximum_cost_cad:
        raise CanaryLaunchError("live provider measured cost exceeds signed plan")
    if audit.spend_known is not True or audit.spend_cad != attempt.cost_cad:
        raise CanaryLaunchError("live provider spend evidence is inconsistent")
    if (
        audit.adapter_invocations != 1
        or audit.provider_api_calls_performed != 1
        or audit.network_calls_performed != 1
        or audit.credentials_used != 1
        or audit.external_actions_performed != 1
    ):
        raise CanaryLaunchError(
            "live canary receipt does not prove exactly one credentialed provider network call"
        )
    core_payload = {
        "invocation_id": invocation.invocation_id,
        "request_digest": invocation.request_digest,
        "attempt": attempt.model_dump(mode="json"),
        "change_set_id": plan.change_set_id,
        "parent_state_hash": plan.parent_state_hash,
    }
    expected_core_id = "EXEC-" + canonical_sha256(core_payload)[:24].upper()
    if core_receipt.receipt_id != expected_core_id:
        raise CanaryLaunchError("live provider core receipt ID mismatch")


def _validate_execution_binding(
    receipt: dict[str, Any],
    permit: dict[str, Any],
    *,
    project: str,
    release_sha: str,
    provider_id: str,
    job_name: str,
    executor_identity: str,
    expected_kms_key_version: str,
    authoritative_now: datetime,
) -> dict[str, Any]:
    schema = json.loads(
        (ROOT / "schemas" / "nexus_canary_job_execution_binding_permit.schema.json")
        .read_text(encoding="utf-8")
    )
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(permit),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise CanaryLaunchError("executor binding permit schema is invalid")
    observed_receipt_sha = receipt.get("receipt_sha256")
    receipt_unsigned = {
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    }
    target = f"projects/{project}/locations/{REGION}/jobs/{job_name}"
    binding = receipt.get("binding")
    expected_member = f"serviceAccount:{executor_identity}"
    if set(receipt) != _BINDING_RECEIPT_KEYS:
        raise CanaryLaunchError("executor binding receipt fields are not exact")
    if (
        receipt.get("schema_version")
        != "aigc.nexus-canary-job-execution-binding-receipt.v1"
        or observed_receipt_sha != canonical_sha256(receipt_unsigned)
        or receipt.get("project_id") != project
        or receipt.get("region") != REGION
        or receipt.get("release_sha") != release_sha
        or receipt.get("provider_id") != provider_id
        or receipt.get("job_name") != job_name
        or receipt.get("target") != target
        or receipt.get("executor_principal") != executor_identity
        or receipt.get("binding_permit_id") != permit.get("permit_id")
        or receipt.get("binding_permit_sha256") != canonical_sha256(permit)
        or receipt.get("project_wide_binding") is not False
        or receipt.get("run_with_overrides_authorized") is not False
        or receipt.get("iam_mutation_count") != 1
        or receipt.get("automatic_retry") is not False
        or receipt.get("permit_consumption_readback_verified") is not True
        or not isinstance(binding, dict)
        or binding.get("role") != "roles/run.invoker"
        or binding.get("members") != [expected_member]
        or binding.get("condition", {}).get("title")
        != permit.get("condition_title")
        or binding.get("condition", {}).get("expression")
        != permit.get("condition_expression")
        or permit.get("target") != target
        or permit.get("executor_principal") != executor_identity
        or permit.get("member") != expected_member
        or permit.get("role") != "roles/run.invoker"
        or permit.get("project_wide_binding") is not False
        or permit.get("run_with_overrides_authorized") is not False
        or permit.get("kms_key_version") != expected_kms_key_version
    ):
        raise CanaryLaunchError("exact-job executor binding evidence is inconsistent")
    try:
        issued_at = datetime.fromisoformat(
            str(permit.get("issued_at") or "").replace("Z", "+00:00")
        )
        not_before = datetime.fromisoformat(
            str(permit.get("not_before") or "").replace("Z", "+00:00")
        )
        binder_expiry = datetime.fromisoformat(
            str(receipt.get("binder_authority_expires_at") or "").replace(
                "Z", "+00:00"
            )
        )
        binding_expiry = datetime.fromisoformat(
            str(receipt.get("binding_expires_at") or "").replace("Z", "+00:00")
        )
        permit_binder_expiry = datetime.fromisoformat(
            str(permit.get("expires_at") or "").replace("Z", "+00:00")
        )
        permit_binding_expiry = datetime.fromisoformat(
            str(permit.get("binding_expires_at") or "").replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise CanaryLaunchError("exact-job executor binding expiry is invalid") from exc
    if (
        issued_at.tzinfo is None
        or not_before.tzinfo is None
        or binder_expiry.tzinfo is None
        or binding_expiry.tzinfo is None
        or binding_expiry.utcoffset() is None
        or not (
            issued_at.astimezone(timezone.utc)
            <= not_before.astimezone(timezone.utc)
            < binder_expiry.astimezone(timezone.utc)
            <= authoritative_now.astimezone(timezone.utc)
            < binding_expiry.astimezone(timezone.utc)
        )
        or binder_expiry != permit_binder_expiry
        or binding_expiry != permit_binding_expiry
        or binding_expiry.astimezone(timezone.utc)
        - issued_at.astimezone(timezone.utc)
        > timedelta(minutes=15)
    ):
        raise CanaryLaunchError(
            "binder must be expired and the exact-job executor binding must be active"
        )
    verify_kms_signed_payload(
        permit,
        expected_kms_key_version=expected_kms_key_version,
        fetch_public_key=fetch_kms_authority_public_key,
        error_type=CanaryLaunchError,
        label="executor binding permit",
    )
    identity = receipt.get("identity_evidence")
    if (
        not isinstance(identity, dict)
        or identity.get("attached_service_account")
        != receipt.get("binder_principal")
        or identity.get("attached_service_account_verified") is not True
        or identity.get("credential_source") != "gce_metadata_server"
        or identity.get("client_impersonation_used") is not False
        or identity.get("workload_identity_federation_used") is not False
        or identity.get("account_level_impersonation_grant_claimed") is not False
        or identity.get("service_account_key_used") is not False
    ):
        raise CanaryLaunchError("executor binding identity evidence is invalid")
    return binding


def _job_iam_policy(
    *, project: str, job_name: str, executor_identity: str, session: Any | None = None
) -> dict[str, Any]:
    if session is None:
        raise CanaryLaunchError("bounded executor session is required")
    response = session.get(
        f"https://run.googleapis.com/v2/projects/{project}/locations/"
        f"{REGION}/jobs/{job_name}:getIamPolicy",
        params={"options.requestedPolicyVersion": "3"},
        timeout=10,
    )
    try:
        policy = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryLaunchError("exact-job IAM readback is invalid JSON") from exc
    if response.status_code != 200:
        raise CanaryLaunchError("exact-job IAM readback failed")
    if not isinstance(policy, dict) or not isinstance(policy.get("bindings"), list):
        raise CanaryLaunchError("exact-job IAM readback is invalid")
    return policy


def _validate_binding_consumption(
    receipt: dict[str, Any],
    permit: dict[str, Any],
    *,
    executor_identity: str,
    expected_source_principal: str,
    session: Any | None = None,
) -> None:
    uri = str(receipt.get("permit_consumption_uri") or "")
    prefix = f"gs://{permit['receipt_bucket']}/"
    generation = str(receipt.get("permit_consumption_generation") or "")
    if not uri.startswith(prefix) or not generation.isdigit():
        raise CanaryLaunchError("binding permit consumption reference is invalid")
    object_name = uri[len(prefix):]
    expected_object = (
        f"canary-job-execution-bindings/{permit['release_sha']}/"
        f"{permit['permit_id']}.json"
    )
    if object_name != expected_object:
        raise CanaryLaunchError("binding permit consumption target mismatch")
    if session is None:
        raise CanaryLaunchError("bounded executor session is required")
    response = session.get(
        f"https://storage.googleapis.com/storage/v1/b/"
        f"{quote(permit['receipt_bucket'], safe='')}/o/"
        f"{quote(object_name, safe='')}",
        params={"alt": "media", "generation": generation},
        timeout=10,
    )
    if response.status_code != 200:
        raise CanaryLaunchError("binding permit consumption could not be read back")
    try:
        record = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryLaunchError("binding permit consumption is invalid JSON") from exc
    expected = {
        "schema_version": "aigc.nexus-canary-job-execution-binding-consumption.v1",
        "permit_id": permit["permit_id"],
        "permit_sha256": canonical_sha256(permit),
        "target": permit["target"],
        "member": permit["member"],
        "state": "consumed_before_dispatch",
        "maximum_mutations": 1,
        "automatic_retry": False,
    }
    if (
        record != expected
        or receipt.get("permit_consumption_record_sha256")
        != canonical_sha256(expected)
    ):
        raise CanaryLaunchError("binding permit consumption evidence mismatch")


def _execute_job(
    *, session: Any, project: str, job_name: str
) -> str:
    try:
        response = session.post(
            f"https://run.googleapis.com/v2/projects/{project}/locations/"
            f"{REGION}/jobs/{job_name}:run",
            json={},
            timeout=10,
        )
    except Exception as exc:
        raise CanaryLaunchIndeterminate("Cloud Run execution dispatch is indeterminate") from exc
    try:
        operation = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryLaunchIndeterminate("Cloud Run execution dispatch is invalid") from exc
    if response.status_code not in {200, 201} or not isinstance(operation, dict):
        raise CanaryLaunchIndeterminate("Cloud Run execution dispatch is indeterminate")
    operation_name = str(operation.get("name") or "")
    if not operation_name.startswith(f"projects/{project}/locations/{REGION}/operations/"):
        raise CanaryLaunchIndeterminate("Cloud Run execution operation is unbound")
    deadline = time.monotonic() + 180
    while not operation.get("done"):
        if time.monotonic() >= deadline:
            raise CanaryLaunchIndeterminate("Cloud Run execution operation timed out")
        time.sleep(1)
        poll = session.get(
            f"https://run.googleapis.com/v2/{operation_name}", timeout=10
        )
        try:
            operation = poll.json()
        except (TypeError, ValueError) as exc:
            raise CanaryLaunchIndeterminate("Cloud Run operation readback is invalid") from exc
        if poll.status_code != 200 or not isinstance(operation, dict):
            raise CanaryLaunchIndeterminate("Cloud Run operation readback failed")
    if operation.get("error"):
        raise CanaryLaunchIndeterminate("Cloud Run execution failed after dispatch")
    execution_name = str((operation.get("response") or {}).get("name") or "")
    return execution_name


def launch(
    *,
    procurement: ExternalReleaseContract,
    deployment: dict[str, Any],
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    execution_binding_receipt: dict[str, Any],
    execution_binding_permit: dict[str, Any],
    jit_impersonation_receipt: dict[str, Any],
    output: Path,
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    _require_new_output(output)
    now = authoritative_now or _utc_now()
    project = procurement.project_id
    if deployment.get("project_id") != project or deployment.get("region") != REGION:
        raise CanaryLaunchError("deployment receipt project/region mismatch")
    if deployment.get("release_sha") != plan.exact_revision:
        raise CanaryLaunchError("deployment receipt release SHA does not match canary plan")
    immutable_image = str(deployment.get("immutable_image_uri") or "")
    if not IMMUTABLE_IMAGE.fullmatch(immutable_image):
        raise CanaryLaunchError("deployment receipt does not contain an immutable image URI")

    prefix = procurement.prefix
    short_provider = "gemini" if plan.provider_id == "google_vertex_gemini" else "openai"
    executor_identity = _expected_executor_identity(prefix=prefix, project=project)
    job_name = _expected_job_name(
        prefix=prefix,
        provider_id=plan.provider_id,
        permit_id=permit.permit_id,
    )
    expected_kms_key_version = expected_canary_authority_key_version(
        project_id=project,
        resource_prefix=prefix,
    )
    _validate_authority(
        procurement,
        deployment,
        plan,
        decision,
        permit,
        attestation,
        expected_kms_key_version=expected_kms_key_version,
        authoritative_now=now,
        expected_job_name=job_name,
    )
    runtime_suffix = "can-gem" if plan.provider_id == "google_vertex_gemini" else "can-oai"
    canary_runtime = f"{prefix}-{runtime_suffix}@{project}.iam.gserviceaccount.com"
    network = f"{prefix}-vpc"
    subnet = f"{prefix}-subnet"
    cloud_sql = f"{project}:{REGION}:{prefix}-control"

    job_resource = f"projects/{project}/locations/{REGION}/jobs/{job_name}"
    jit_evidence = validate_jit_impersonation_receipt(
        jit_impersonation_receipt,
        action="execute_job",
        project_id=project,
        target_principal=executor_identity,
        target_resource=job_resource,
        governed_permit_id=permit.permit_id,
        request_sha256=jit_request_sha256(
            action="execute_job",
            project_id=project,
            target_principal=executor_identity,
            target_resource=job_resource,
            governed_permit_id=permit.permit_id,
        ),
        expected_kms_key_version=expected_kms_key_version,
        fetch_public_key=fetch_kms_authority_public_key,
        error_type=CanaryLaunchError,
        authoritative_now=now,
    )
    expected_attached_source = (
        f"{prefix}-can-bind@{project}.iam.gserviceaccount.com"
    )
    if jit_evidence.get("jit_source_principal") != expected_attached_source:
        raise CanaryLaunchError(
            "canary execution JIT source must be the attached canary binder identity"
        )

    authority_expiries = [
        permit.expires_at,
        attestation.expires_at,
        datetime.fromisoformat(jit_evidence["jit_expires_at"]),
    ]
    if decision.expires_at is not None:
        authority_expiries.append(decision.expires_at)
    session, bounded_adc_evidence = bounded_impersonated_session(
        expected_target=executor_identity,
        expected_source=jit_evidence["jit_source_principal"],
        authority_expires_at=min(authority_expiries),
        error_type=CanaryLaunchError,
    )

    executor_evidence = {
        **bounded_adc_evidence,
        **jit_evidence,
        "account_level_impersonation_grant_claimed": False,
    }
    environment = _authority_environment(
        plan=plan,
        decision=decision,
        permit=permit,
        attestation=attestation,
    )
    binding = _validate_execution_binding(
        execution_binding_receipt,
        execution_binding_permit,
        project=project,
        release_sha=plan.exact_revision,
        provider_id=plan.provider_id,
        job_name=job_name,
        executor_identity=executor_identity,
        expected_kms_key_version=expected_kms_key_version,
        authoritative_now=now,
    )
    _validate_binding_consumption(
        execution_binding_receipt,
        execution_binding_permit,
        executor_identity=executor_identity,
        expected_source_principal=jit_evidence["jit_source_principal"],
        session=session,
    )
    iam_policy = _job_iam_policy(
        project=project,
        job_name=job_name,
        executor_identity=executor_identity,
        session=session,
    )
    matching_bindings = [
        item
        for item in iam_policy["bindings"]
        if isinstance(item, dict)
        and f"serviceAccount:{executor_identity}" in (item.get("members") or [])
    ]
    if matching_bindings != [binding]:
        raise CanaryLaunchError(
            "executor lacks the exact conditional job-level run.invoker binding"
        )
    prefix_for_role = executor_identity.split("-can-exec@", 1)[0]
    binder_member = f"serviceAccount:{execution_binding_permit['binder_principal']}"
    binder_suffix = re.sub(
        r"[^a-z0-9]", "_", execution_binding_permit["permit_id"].lower()
    ).strip("_")
    binder_expiry = datetime.fromisoformat(
        execution_binding_permit["expires_at"].replace("Z", "+00:00")
    ).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    expected_expired_binder = {
        "role": (
            f"projects/{project}/roles/"
            f"{prefix_for_role.replace('-', '_')}_canary_job_iam_binder"
        ),
        "members": [binder_member],
        "condition": {
            "title": f"aigc_binder_{binder_suffix}"[:79],
            "description": "One trusted-broker exact-job IAM mutation",
            "expression": f'request.time < timestamp("{binder_expiry}")',
        },
    }
    observed_binder = [
        item for item in iam_policy["bindings"]
        if isinstance(item, dict) and binder_member in (item.get("members") or [])
    ]
    if observed_binder != [expected_expired_binder]:
        raise CanaryLaunchError(
            "binder mutation authority is absent, ambiguous, or still mutable"
        )
    job_target = _job_target(
        project=project,
        region=REGION,
        job_name=job_name,
        immutable_image=immutable_image,
        service_account=canary_runtime,
        expected_environment=environment,
        expected_network=network,
        expected_subnet=subnet,
        expected_cloud_sql=cloud_sql,
        release_sha=plan.exact_revision,
        provider_label=short_provider,
        reader_service_account=executor_identity,
        session=session,
    )
    dispatch_now = _utc_now()
    _validate_authority(
        procurement,
        deployment,
        plan,
        decision,
        permit,
        attestation,
        expected_kms_key_version=expected_kms_key_version,
        authoritative_now=dispatch_now,
        expected_job_name=job_name,
    )
    validate_jit_impersonation_receipt(
        jit_impersonation_receipt,
        action="execute_job",
        project_id=project,
        target_principal=executor_identity,
        target_resource=job_resource,
        governed_permit_id=permit.permit_id,
        request_sha256=jit_request_sha256(
            action="execute_job",
            project_id=project,
            target_principal=executor_identity,
            target_resource=job_resource,
            governed_permit_id=permit.permit_id,
        ),
        expected_kms_key_version=expected_kms_key_version,
        fetch_public_key=fetch_kms_authority_public_key,
        error_type=CanaryLaunchError,
        authoritative_now=dispatch_now,
    )
    _validate_execution_binding(
        execution_binding_receipt,
        execution_binding_permit,
        project=project,
        release_sha=plan.exact_revision,
        provider_id=plan.provider_id,
        job_name=job_name,
        executor_identity=executor_identity,
        expected_kms_key_version=expected_kms_key_version,
        authoritative_now=dispatch_now,
    )
    final_job_target = _job_target(
        project=project,
        region=REGION,
        job_name=job_name,
        immutable_image=immutable_image,
        service_account=canary_runtime,
        expected_environment=environment,
        expected_network=network,
        expected_subnet=subnet,
        expected_cloud_sql=cloud_sql,
        release_sha=plan.exact_revision,
        provider_label=short_provider,
        reader_service_account=executor_identity,
        session=session,
    )
    final_iam_policy = _job_iam_policy(
        project=project,
        job_name=job_name,
        executor_identity=executor_identity,
        session=session,
    )
    if (
        final_job_target != job_target
        or canonical_sha256(final_iam_policy) != canonical_sha256(iam_policy)
    ):
        raise CanaryLaunchError(
            "job or exact-job IAM policy changed before dispatch"
        )
    execution_resource = _execute_job(
        session=session,
        project=project,
        job_name=job_name,
    )

    try:
        execution_name = execution_resource.rsplit("/", 1)[-1]
        if (
            not EXECUTION_NAME.fullmatch(execution_name)
            or not execution_name.startswith(job_name + "-")
        ):
            raise CanaryLaunchError(
                "Cloud Run returned an execution outside the launched job"
            )
        execution_target = _execution_target(
            project=project,
            region=REGION,
            execution_name=execution_name,
            job_name=job_name,
            immutable_image=immutable_image,
            service_account=canary_runtime,
            expected_environment=environment,
            expected_network=network,
            expected_subnet=subnet,
            expected_cloud_sql=cloud_sql,
            reader_service_account=executor_identity,
            session=session,
        )
        receipt = _receipt_from_logs(
            project=project,
            region=REGION,
            job_name=job_name,
            execution_name=execution_name,
            reader_service_account=executor_identity,
            session=session,
        )
        _validate_provider_receipt(
            receipt,
            plan=plan,
            permit=permit,
            attestation=attestation,
            job_name=job_name,
            execution_name=execution_name,
        )
    except CanaryLaunchIndeterminate:
        raise
    except (CanaryLaunchError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CanaryLaunchIndeterminate(
            "canary job was dispatched but exact execution outcome evidence is unavailable; "
            "do not retry this permit"
        ) from exc
    result = {
        "schema_version": "aigc.nexus-provider-canary-job-receipt.v1",
        "project_id": project,
        "region": REGION,
        "job_name": job_name,
        "execution_name": execution_name,
        "executor_identity": executor_identity,
        "executor_identity_evidence": executor_evidence,
        "execution_binding_receipt_sha256": execution_binding_receipt[
            "receipt_sha256"
        ],
        "immutable_image_uri": immutable_image,
        "reserved_usage_units": plan.reserved_usage_units,
        "maximum_input_units": plan.maximum_input_units,
        "maximum_output_units": plan.maximum_output_units,
        "request_timeout_seconds": plan.request_timeout_seconds,
        "job_target": job_target,
        "execution_target": execution_target,
        "provider_receipt": receipt,
        "automatic_retry": False,
        "job_max_retries": 0,
        "job_deployment_performed": False,
        "execution_overrides_supplied": False,
        "cloud_run_mutation_count": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    result["receipt_sha256"] = canonical_sha256(result)
    _write_new_receipt(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--procurement", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--governance", type=Path, required=True)
    parser.add_argument("--permit", type=Path, required=True)
    parser.add_argument("--authority-attestation", type=Path, required=True)
    parser.add_argument("--execution-binding-receipt", type=Path, required=True)
    parser.add_argument("--execution-binding-permit", type=Path, required=True)
    parser.add_argument("--jit-impersonation-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    procurement = ExternalReleaseContract.load(args.procurement)
    plan = ProviderCanaryPlan.model_validate(_object(args.plan))
    decision = GovernanceDecision.model_validate(_object(args.governance))
    permit = ExecutionPermit.model_validate(_object(args.permit))
    attestation = AuthorityAttestation.model_validate(_object(args.authority_attestation))
    result = launch(
        procurement=procurement,
        deployment=_object(args.deployment_receipt),
        plan=plan,
        decision=decision,
        permit=permit,
        attestation=attestation,
        execution_binding_receipt=_object(args.execution_binding_receipt),
        execution_binding_permit=_object(args.execution_binding_permit),
        jit_impersonation_receipt=_object(args.jit_impersonation_receipt),
        output=args.output,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProcurementError, CanaryLaunchError, ValueError) as exc:
        raise SystemExit(f"Nexus provider canary job blocked: {exc}") from exc
