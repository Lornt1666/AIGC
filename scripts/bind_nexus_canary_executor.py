from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

from jsonschema import Draft202012Validator, FormatChecker

from scripts.provision_nexus_provider_canary_job import (
    _verify_permit_signature,
)
from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.operations.nexus_provider_canary import (
    expected_canary_authority_key_version,
    fetch_kms_authority_public_key,
)


ROOT = Path(__file__).resolve().parents[1]
REGION = "northamerica-northeast1"
REPOSITORY = "Lornt1666/AIGC"
PERMIT_SCHEMA = "aigc.nexus-canary-job-execution-binding-permit.v1"
RECEIPT_SCHEMA = "aigc.nexus-canary-job-execution-binding-receipt.v1"
SCHEMA_PATH = ROOT / "schemas" / "nexus_canary_job_execution_binding_permit.schema.json"
MAXIMUM_PERMIT_LIFETIME = timedelta(minutes=15)
SERVICE_ACCOUNT = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$"
)


class CanaryExecutorBindingError(RuntimeError):
    pass


class CanaryExecutorBindingIndeterminate(CanaryExecutorBindingError):
    pass


class CanaryExecutorBindingPermitConsumed(CanaryExecutorBindingError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanaryExecutorBindingError(f"{path} must contain a JSON object")
    return value


def _aware(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise CanaryExecutorBindingError(f"binding permit {field} must be RFC 3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CanaryExecutorBindingError(f"binding permit {field} must be RFC 3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CanaryExecutorBindingError(f"binding permit {field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def expected_binding_identities(*, prefix: str, project: str) -> dict[str, str]:
    identities = {
        "binder": f"{prefix}-can-bind@{project}.iam.gserviceaccount.com",
        "executor": f"{prefix}-can-exec@{project}.iam.gserviceaccount.com",
    }
    if any(not SERVICE_ACCOUNT.fullmatch(value) for value in identities.values()):
        raise CanaryExecutorBindingError("derived binding identities are invalid")
    return identities


def expected_condition(*, permit_id: str, expires_at: str) -> tuple[str, str]:
    parsed = _aware(expires_at, field="binding_expires_at")
    canonical_expiry = parsed.isoformat().replace("+00:00", "Z")
    suffix = re.sub(r"[^a-z0-9]", "_", permit_id.lower()).strip("_")
    return (
        f"aigc_canary_{suffix}"[:79],
        f'request.time < timestamp("{canonical_expiry}")',
    )


def _validate_provisioning_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    observed = receipt.get("receipt_sha256")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if (
        receipt.get("schema_version") != "aigc.nexus-canary-job-provisioning-receipt.v1"
        or observed != canonical_sha256(unsigned)
        or receipt.get("repository") != REPOSITORY
        or receipt.get("region") != REGION
        or receipt.get("job_deployment_performed") is not True
        or receipt.get("job_execution_performed") is not False
        or receipt.get("provider_call_performed") is not False
    ):
        raise CanaryExecutorBindingError("provisioning receipt is invalid")
    return receipt


def _validate_permit(
    permit: dict[str, Any],
    *,
    provisioning: dict[str, Any],
    prefix: str,
    authoritative_now: datetime,
) -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(permit),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise CanaryExecutorBindingError(
            f"binding permit schema mismatch at {path}: {errors[0].message}"
        )
    project = provisioning["project_id"]
    identities = expected_binding_identities(prefix=prefix, project=project)
    title, expression = expected_condition(
        permit_id=permit["permit_id"], expires_at=permit["binding_expires_at"]
    )
    expected = {
        "schema_version": PERMIT_SCHEMA,
        "repository": REPOSITORY,
        "project_id": project,
        "project_number": provisioning["project_number"],
        "region": REGION,
        "release_sha": provisioning["release_sha"],
        "provider_id": provisioning["provider_id"],
        "job_name": provisioning["job_name"],
        "target": provisioning["target"],
        "binder_principal": identities["binder"],
        "executor_principal": identities["executor"],
        "receipt_bucket": f"{project}-{prefix}-receipts",
        "provisioning_receipt_sha256": provisioning["receipt_sha256"],
        "role": "roles/run.invoker",
        "member": f"serviceAccount:{identities['executor']}",
        "condition_title": title,
        "condition_expression": expression,
        "maximum_mutations": 1,
        "automatic_retry": False,
        "consumption_mode": "gcs_if_generation_match_zero",
        "project_wide_binding": False,
        "run_with_overrides_authorized": False,
        "kms_key_version": expected_canary_authority_key_version(
            project_id=project, resource_prefix=prefix
        ),
    }
    for field, value in expected.items():
        if permit.get(field) != value:
            raise CanaryExecutorBindingError(f"binding permit is not bound to exact {field}")
    issued = _aware(permit["issued_at"], field="issued_at")
    not_before = _aware(permit["not_before"], field="not_before")
    expires = _aware(permit["expires_at"], field="expires_at")
    binding_expires = _aware(
        permit["binding_expires_at"], field="binding_expires_at"
    )
    if not (issued <= not_before <= authoritative_now < expires):
        raise CanaryExecutorBindingError("binding permit is outside its active window")
    if not (expires < binding_expires):
        raise CanaryExecutorBindingError(
            "executor binding must outlive the binder mutation authority"
        )
    if binding_expires - issued > MAXIMUM_PERMIT_LIFETIME:
        raise CanaryExecutorBindingError(
            "binding permit and executor binding window exceed 15 minutes"
        )
    public_key = fetch_kms_authority_public_key(expected["kms_key_version"])
    try:
        _verify_permit_signature(permit, kms_public_key=public_key)
    except RuntimeError as exc:
        raise CanaryExecutorBindingError(str(exc)) from exc
    return {**permit, "permit_sha256": canonical_sha256(permit)}


def _adc_session(expected_target: str):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession, Request

    credentials, _ = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",)
    )
    credential_type = f"{type(credentials).__module__}.{type(credentials).__qualname__}"
    if credential_type != "google.auth.compute_engine.credentials.Credentials":
        raise CanaryExecutorBindingError(
            "binder requires a non-impersonable attached metadata service account"
        )
    if any(
        getattr(credentials, field, None)
        for field in ("target_principal", "_target_principal", "_source_credentials")
    ):
        raise CanaryExecutorBindingError("client-impersonated binder credentials are forbidden")
    try:
        credentials.refresh(Request())
    except Exception as exc:
        raise CanaryExecutorBindingError("attached binder identity could not be verified") from exc
    observed = str(getattr(credentials, "service_account_email", "") or "")
    if observed != expected_target:
        raise CanaryExecutorBindingError("attached binder identity mismatch")
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


def _json_response(response: Any, *, label: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryExecutorBindingError(f"{label} response is not JSON") from exc
    if not isinstance(payload, dict):
        raise CanaryExecutorBindingError(f"{label} response is invalid")
    return payload


def _permission_preflight(session: Any, *, target: str) -> dict[str, Any]:
    queried = (
        "run.jobs.get", "run.jobs.getIamPolicy", "run.jobs.setIamPolicy",
        "run.jobs.run", "run.jobs.runWithOverrides", "run.jobs.create",
        "run.jobs.update", "run.jobs.delete", "run.executions.cancel",
    )
    response = session.post(
        f"https://run.googleapis.com/v2/{target}:testIamPermissions",
        json={"permissions": list(queried)}, timeout=10,
    )
    payload = _json_response(response, label="binder permission preflight")
    granted = set(payload.get("permissions") or [])
    required = {"run.jobs.get", "run.jobs.getIamPolicy", "run.jobs.setIamPolicy"}
    if response.status_code != 200 or granted != required:
        raise CanaryExecutorBindingError(
            "binder must have only exact job read/IAM-policy mutation authority"
        )
    return {"permissions": sorted(granted), "evidence_sha256": canonical_sha256(payload)}


def _get_policy(session: Any, *, target: str) -> dict[str, Any]:
    response = session.get(
        f"https://run.googleapis.com/v2/{target}:getIamPolicy",
        params={"options.requestedPolicyVersion": "3"}, timeout=10,
    )
    payload = _json_response(response, label="job IAM readback")
    if response.status_code != 200 or not isinstance(payload.get("bindings", []), list):
        raise CanaryExecutorBindingError("job IAM readback is invalid")
    return payload


def _executor_bindings(policy: dict[str, Any], *, member: str) -> list[dict[str, Any]]:
    return [
        binding for binding in policy.get("bindings", [])
        if isinstance(binding, dict) and member in (binding.get("members") or [])
    ]


def _binder_binding(*, permit: dict[str, Any], prefix: str) -> dict[str, Any]:
    expiry = _aware(permit["expires_at"], field="expires_at")
    canonical_expiry = expiry.isoformat().replace("+00:00", "Z")
    suffix = re.sub(r"[^a-z0-9]", "_", permit["permit_id"].lower()).strip("_")
    return {
        "role": (
            f"projects/{permit['project_id']}/roles/"
            f"{prefix.replace('-', '_')}_canary_job_iam_binder"
        ),
        "members": [f"serviceAccount:{permit['binder_principal']}"],
        "condition": {
            "title": f"aigc_binder_{suffix}"[:79],
            "description": "One trusted-broker exact-job IAM mutation",
            "expression": f'request.time < timestamp("{canonical_expiry}")',
        },
    }


def _require_quiescent_provisioner(
    provisioning: dict[str, Any], *, authoritative_now: datetime
) -> dict[str, str]:
    identity = provisioning.get("identity_evidence")
    if not isinstance(identity, dict):
        raise CanaryExecutorBindingError("provisioner authority evidence is missing")
    try:
        broker_expiry = _aware(
            identity["broker_authority_expires_at"],
            field="broker_authority_expires_at",
        )
    except KeyError as exc:
        raise CanaryExecutorBindingError(
            "provisioner authority expiry evidence is missing"
        ) from exc
    if (
        identity.get("attached_service_account")
        != provisioning.get("provisioner_principal")
        or identity.get("attached_service_account_verified") is not True
        or identity.get("credential_source") != "gce_metadata_server"
        or identity.get("client_impersonation_used") is not False
        or identity.get("project_wide_permanent_mutation_authority") is not False
        or identity.get("service_account_key_used") is not False
        or authoritative_now < broker_expiry
    ):
        raise CanaryExecutorBindingError(
            "provisioner mutation authority is not provably quiescent"
        )
    return {
        "provisioner_broker_authority_expired_at": broker_expiry.isoformat(),
    }


def _consume(session: Any, *, permit: dict[str, Any]) -> dict[str, str]:
    object_name = (
        f"canary-job-execution-bindings/{permit['release_sha']}/{permit['permit_id']}.json"
    )
    record = {
        "schema_version": "aigc.nexus-canary-job-execution-binding-consumption.v1",
        "permit_id": permit["permit_id"], "permit_sha256": permit["permit_sha256"],
        "target": permit["target"], "member": permit["member"],
        "state": "consumed_before_dispatch", "maximum_mutations": 1,
        "automatic_retry": False,
    }
    response = session.post(
        f"https://storage.googleapis.com/upload/storage/v1/b/"
        f"{quote(permit['receipt_bucket'], safe='')}/o",
        params={"uploadType": "media", "name": object_name, "ifGenerationMatch": "0"},
        data=canonical_json_bytes(record),
        headers={"Content-Type": "application/json; charset=utf-8"}, timeout=10,
    )
    if response.status_code in {409, 412}:
        raise CanaryExecutorBindingPermitConsumed("binding permit was already consumed")
    payload = _json_response(response, label="binding permit consumption")
    generation = str(payload.get("generation") or "")
    if (
        response.status_code not in {200, 201}
        or payload.get("bucket") != permit["receipt_bucket"]
        or payload.get("name") != object_name
        or not generation.isdigit()
    ):
        raise CanaryExecutorBindingIndeterminate("binding permit consumption is indeterminate")
    readback = session.get(
        f"https://storage.googleapis.com/storage/v1/b/"
        f"{quote(permit['receipt_bucket'], safe='')}/o/"
        f"{quote(object_name, safe='')}",
        params={"alt": "media", "generation": generation}, timeout=10,
    )
    try:
        observed_record = readback.json()
    except (TypeError, ValueError) as exc:
        raise CanaryExecutorBindingIndeterminate(
            "binding permit consumption readback is indeterminate"
        ) from exc
    if readback.status_code != 200 or observed_record != record:
        raise CanaryExecutorBindingIndeterminate(
            "binding permit consumption readback is indeterminate"
        )
    return {
        "permit_consumption_uri": f"gs://{permit['receipt_bucket']}/{object_name}",
        "permit_consumption_generation": generation,
        "permit_consumption_record_sha256": canonical_sha256(record),
        "permit_consumption_readback_verified": True,
    }


def bind_executor(
    *,
    provisioning_receipt: dict[str, Any],
    binding_permit: dict[str, Any],
    output: Path,
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    if output.exists():
        raise CanaryExecutorBindingError("binding receipt output already exists")
    provisioning = _validate_provisioning_receipt(provisioning_receipt)
    project = provisioning["project_id"]
    prefix = provisioning["provisioner_principal"].split("-can-prov@", 1)[0]
    now = (authoritative_now or _utc_now()).astimezone(timezone.utc)
    permit = _validate_permit(
        binding_permit, provisioning=provisioning, prefix=prefix, authoritative_now=now
    )
    provisioner_quiescence = _require_quiescent_provisioner(
        provisioning, authoritative_now=now
    )
    session, adc_evidence = _adc_session(permit["binder_principal"])
    permissions = _permission_preflight(session, target=permit["target"])
    before = _get_policy(session, target=permit["target"])
    expected_binder = _binder_binding(permit=permit, prefix=prefix)
    binder_member = f"serviceAccount:{permit['binder_principal']}"
    observed_binder = [
        item for item in before.get("bindings", [])
        if isinstance(item, dict) and binder_member in (item.get("members") or [])
    ]
    if observed_binder != [expected_binder]:
        raise CanaryExecutorBindingError(
            "trusted binder lacks the exact expiring job-level authority"
        )
    if _executor_bindings(before, member=permit["member"]):
        raise CanaryExecutorBindingError("executor already has authority on the target job")
    consumption = _consume(session, permit=permit)
    dispatch_now = _utc_now()
    permit = _validate_permit(
        binding_permit,
        provisioning=provisioning,
        prefix=prefix,
        authoritative_now=dispatch_now,
    )
    _require_quiescent_provisioner(provisioning, authoritative_now=dispatch_now)
    binding = {
        "role": permit["role"], "members": [permit["member"]],
        "condition": {
            "title": permit["condition_title"],
            "description": f"One governed execution under {permit['permit_id']}",
            "expression": permit["condition_expression"],
        },
    }
    policy = {**before, "version": 3, "bindings": [*before.get("bindings", []), binding]}
    try:
        response = session.post(
            f"https://run.googleapis.com/v2/{permit['target']}:setIamPolicy",
            json={"policy": policy, "updateMask": "bindings,etag,version"}, timeout=10,
        )
    except Exception as exc:
        raise CanaryExecutorBindingIndeterminate("binding mutation is indeterminate") from exc
    if response.status_code != 200:
        raise CanaryExecutorBindingIndeterminate("binding mutation is indeterminate")
    after = _get_policy(session, target=permit["target"])
    observed = _executor_bindings(after, member=permit["member"])
    if observed != [binding]:
        raise CanaryExecutorBindingIndeterminate("exact job binding readback failed")
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "project_id": project, "project_number": provisioning["project_number"],
        "region": REGION, "release_sha": provisioning["release_sha"],
        "provider_id": provisioning["provider_id"], "job_name": provisioning["job_name"],
        "target": permit["target"], "binder_principal": permit["binder_principal"],
        "executor_principal": permit["executor_principal"],
        "provisioning_receipt_sha256": provisioning["receipt_sha256"],
        "binding_permit_id": permit["permit_id"],
        "binding_permit_sha256": permit["permit_sha256"],
        "identity_evidence": {
            **adc_evidence,
            "account_level_impersonation_grant_claimed": False,
        },
        "provisioner_quiescence_evidence": provisioner_quiescence,
        "permission_evidence": permissions, "binding": binding,
        "policy_before_sha256": canonical_sha256(before),
        "policy_after_sha256": canonical_sha256(after),
        **consumption, "iam_mutation_count": 1, "project_wide_binding": False,
        "run_with_overrides_authorized": False, "automatic_retry": False,
        "binder_authority_expires_at": _aware(
            permit["expires_at"], field="expires_at"
        ).isoformat(),
        "binding_expires_at": _aware(
            permit["binding_expires_at"], field="binding_expires_at"
        ).isoformat(),
        "captured_at": dispatch_now.isoformat(),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    except OSError as exc:
        raise CanaryExecutorBindingIndeterminate("binding succeeded but receipt write failed") from exc
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provisioning-receipt", type=Path, required=True)
    parser.add_argument("--binding-permit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise CanaryExecutorBindingError("binding is inert unless --execute is supplied")
    bind_executor(
        provisioning_receipt=_object(args.provisioning_receipt),
        binding_permit=_object(args.binding_permit),
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CanaryExecutorBindingError as exc:
        raise SystemExit(f"Nexus canary executor binding blocked: {exc}") from exc
