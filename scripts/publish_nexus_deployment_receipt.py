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
from typing import Any, Sequence
from urllib.parse import quote

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from jsonschema import Draft202012Validator, FormatChecker

from src.operations.nexus_provider_canary import (
    CANARY_AUTHORITY_ALGORITHM,
    CanaryConfigurationError,
    KmsAuthorityPublicKey,
    authority_public_key_sha256,
    expected_canary_authority_key_version,
    fetch_kms_authority_public_key,
)


REGION = "northamerica-northeast1"
REPOSITORY = "Lornt1666/AIGC"
PERMIT_SCHEMA = "aigc.nexus-deployment-receipt-publication-permit.v1"
PUBLICATION_SCHEMA = "aigc.nexus-deployment-receipt-publication.v1"
ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "quebec_deployment_receipt.schema.json"
PERMIT_SCHEMA_PATH = (
    ROOT / "schemas" / "nexus_deployment_receipt_publication_permit.schema.json"
)
_MAX_PERMIT_LIFETIME = timedelta(minutes=15)
_MAX_RECEIPT_BYTES = 1024 * 1024
_ACTION_NAMES = (
    "cloud_build_submit",
    "sbom_export",
    "migration_job_deploy",
    "migration_execute",
    "operator_deploy",
    "judge_deploy",
)
_RESOURCE_PREFIX = re.compile(r"^[a-z][a-z0-9-]{2,18}$")
_ACTION_CONSUMPTION_URI = re.compile(
    r"^gs://(?P<bucket>[a-z0-9][a-z0-9._-]{1,61}[a-z0-9])/"
    r"staging-action-permits/(?P<release>[a-f0-9]{40})/"
    r"(?P<index>[0-9]{2})-(?P<permit_id>ACT-[A-Z0-9_-]{8,64})\.json$"
)


class NexusReceiptPublicationError(RuntimeError):
    pass


class NexusReceiptPublicationIndeterminate(NexusReceiptPublicationError):
    pass


class NexusReceiptAlreadyPublished(NexusReceiptPublicationError):
    pass


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _schema_validate(value: Any, *, schema_path: Path, label: str) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise NexusReceiptPublicationError(
            f"{label} schema mismatch at {path}: {errors[0].message}"
        )


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise NexusReceiptPublicationError(
            f"publication permit {field} must be an RFC 3339 timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NexusReceiptPublicationError(
            f"publication permit {field} must be an RFC 3339 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NexusReceiptPublicationError(
            f"publication permit {field} must include a UTC offset"
        )
    return parsed.astimezone(timezone.utc)


def _active_time_window(
    permit: dict[str, Any],
    *,
    authoritative_now: datetime | None = None,
) -> datetime:
    now = authoritative_now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise NexusReceiptPublicationError(
            "authoritative publication-permit time must include a UTC offset"
        )
    now = now.astimezone(timezone.utc)
    issued_at = _aware_datetime(permit["issued_at"], field="issued_at")
    not_before = _aware_datetime(permit["not_before"], field="not_before")
    expires_at = _aware_datetime(permit["expires_at"], field="expires_at")
    if not (issued_at <= not_before < expires_at):
        raise NexusReceiptPublicationError(
            "publication permit temporal ordering must be issued_at <= not_before < expires_at"
        )
    if expires_at - issued_at > _MAX_PERMIT_LIFETIME:
        raise NexusReceiptPublicationError("publication permit lifetime exceeds 15 minutes")
    if issued_at > now or not_before > now:
        raise NexusReceiptPublicationError("publication permit is not active yet")
    if expires_at <= now:
        raise NexusReceiptPublicationError("publication permit is expired")
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


def validate_deployment_receipt(receipt: dict[str, Any]) -> bytes:
    if not isinstance(receipt, dict):
        raise NexusReceiptPublicationError("deployment receipt must be a JSON object")
    _schema_validate(
        receipt,
        schema_path=RECEIPT_SCHEMA_PATH,
        label="deployment receipt",
    )
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    observed_hash = _canonical_sha256(unsigned)
    if not hmac.compare_digest(str(receipt.get("receipt_sha256") or ""), observed_hash):
        raise NexusReceiptPublicationError(
            "deployment receipt SHA-256 does not match its canonical content"
        )
    content = _canonical_json_bytes(receipt)
    if len(content) > _MAX_RECEIPT_BYTES:
        raise NexusReceiptPublicationError("canonical deployment receipt exceeds 1 MiB")
    return content


def _receipt_binding_consistency(
    receipt: dict[str, Any],
    *,
    receipt_bucket: str,
) -> None:
    immutable_image = receipt["immutable_image_uri"]
    if not immutable_image.endswith(f"@{receipt['image_digest']}"):
        raise NexusReceiptPublicationError(
            "deployment receipt immutable image does not bind its image digest"
        )
    if receipt["ci_run_id"] != receipt["ci_admission"]["workflow_run_id"]:
        raise NexusReceiptPublicationError(
            "deployment receipt CI run identity is internally inconsistent"
        )

    services = receipt["services"]
    expected_service_bindings = (
        ("operator", receipt["operator_revision"]),
        ("judge", receipt["judge_revision"]),
    )
    for role, top_level_revision in expected_service_bindings:
        service = services[role]
        readiness = service["readiness"]
        if (
            service["revision"] != top_level_revision
            or service["runtime_role"] != role
            or service["immutable_image_uri"] != immutable_image
            or readiness["project_id"] != receipt["project_id"]
            or readiness["runtime_role"] != role
            or readiness["release_revision"] != receipt["release_sha"]
            or readiness["image_digest"] != receipt["image_digest"]
            or readiness["region"] != receipt["region"]
            or readiness["deployment_authorization_sha256"]
            != receipt["authorization_sha256"]
        ):
            raise NexusReceiptPublicationError(
                f"deployment receipt {role} service/readiness binding is inconsistent"
            )

    migration = receipt["migration"]
    if (
        migration["immutable_image_uri"] != immutable_image
        or migration["service_account"] != services["operator"]["service_account"]
    ):
        raise NexusReceiptPublicationError(
            "deployment receipt migration binding is internally inconsistent"
        )

    actions = receipt["actions"]
    if tuple(action["action"] for action in actions) != _ACTION_NAMES:
        raise NexusReceiptPublicationError(
            "deployment receipt does not contain the exact terminal action sequence"
        )
    expected_targets = (
        receipt["tagged_image_uri"],
        immutable_image,
        migration["job_name"],
        migration["execution_name"],
        services["operator"]["service"],
        services["judge"]["service"],
    )
    previous_permit_sha256 = "0" * 64
    for index, (action, expected_target) in enumerate(zip(actions, expected_targets)):
        evidence = action["evidence"]
        if action["target"] != expected_target:
            raise NexusReceiptPublicationError(
                f"deployment receipt action {index} target is internally inconsistent"
            )
        if evidence["predecessor_permit_sha256"] != previous_permit_sha256:
            raise NexusReceiptPublicationError(
                f"deployment receipt action {index} does not bind its predecessor"
            )
        expected_uri = (
            f"gs://{receipt_bucket}/staging-action-permits/{receipt['release_sha']}/"
            f"{index:02d}-{evidence['action_permit_id']}.json"
        )
        if evidence["permit_consumption_uri"] != expected_uri:
            raise NexusReceiptPublicationError(
                f"deployment receipt action {index} consumption URI is not exact"
            )
        previous_permit_sha256 = evidence["action_permit_sha256"]

    build_evidence = actions[0]["evidence"]
    if (
        build_evidence["build_id"] != receipt["build_id"]
        or build_evidence["tagged_image_uri"] != receipt["tagged_image_uri"]
        or build_evidence["image_digest"] != receipt["image_digest"]
        or build_evidence["immutable_image_uri"] != immutable_image
        or build_evidence["build_context_manifest_sha256"]
        != receipt["build_context_manifest_sha256"]
    ):
        raise NexusReceiptPublicationError(
            "deployment receipt build evidence is internally inconsistent"
        )
    supply_chain = receipt["supply_chain"]
    if any(
        build_evidence[field] != supply_chain[field]
        for field in (
            "docker_builder_image",
            "python_base_image",
            "provenance_sha256",
            "provenance_builder_id",
            "provenance_build_id",
            "sbom_reference_count",
            "sbom_metadata_sha256",
            "vulnerability_finding_count",
            "release_blocking_vulnerability_count",
            "vulnerability_metadata_sha256",
            "vulnerability_scan_status",
            "vulnerability_scan_metadata_sha256",
        )
    ):
        raise NexusReceiptPublicationError(
            "deployment receipt supply-chain evidence is internally inconsistent"
        )
    sbom_evidence = actions[1]["evidence"]
    if (
        sbom_evidence["immutable_image_uri"] != immutable_image
        or sbom_evidence["sbom_reference_count"]
        != supply_chain["sbom_reference_count"]
        or sbom_evidence["sbom_metadata_sha256"]
        != supply_chain["sbom_metadata_sha256"]
    ):
        raise NexusReceiptPublicationError(
            "deployment receipt SBOM evidence is internally inconsistent"
        )
    migration_job_evidence = actions[2]["evidence"]
    migration_execution_evidence = actions[3]["evidence"]
    if (
        migration_job_evidence["job_name"] != migration["job_name"]
        or migration_job_evidence["immutable_image_uri"] != immutable_image
        or any(
            migration_execution_evidence[field] != migration[field]
            for field in (
                "job_name",
                "execution_name",
                "immutable_image_uri",
                "service_account",
                "exact_execution_log_verified",
                "migration_receipt",
            )
        )
    ):
        raise NexusReceiptPublicationError(
            "deployment receipt migration action evidence is internally inconsistent"
        )
    for index, role in ((4, "operator"), (5, "judge")):
        service = services[role]
        evidence = actions[index]["evidence"]
        if (
            evidence["revision"] != service["revision"]
            or evidence["candidate_tag"] != service["candidate_tag"]
            or evidence["immutable_image_uri"] != immutable_image
            or evidence["readiness_verified"] is not True
        ):
            raise NexusReceiptPublicationError(
                f"deployment receipt {role} action evidence is internally inconsistent"
            )


def _receipt_resource_scope(receipt: dict[str, Any]) -> tuple[str, str]:
    first_consumption_uri = receipt["actions"][0]["evidence"]["permit_consumption_uri"]
    match = _ACTION_CONSUMPTION_URI.fullmatch(first_consumption_uri)
    if match is None:
        raise NexusReceiptPublicationError(
            "deployment receipt does not contain an exact first-action consumption URI"
        )
    bucket = match.group("bucket")
    project_prefix = f"{receipt['project_id']}-"
    suffix = "-receipts"
    if not bucket.startswith(project_prefix) or not bucket.endswith(suffix):
        raise NexusReceiptPublicationError(
            "deployment receipt bucket is not deterministically bound to its project"
        )
    resource_prefix = bucket[len(project_prefix) : -len(suffix)]
    if not _RESOURCE_PREFIX.fullmatch(resource_prefix):
        raise NexusReceiptPublicationError(
            "deployment receipt bucket contains an invalid resource prefix"
        )
    return resource_prefix, bucket


def _signed_permit_payload(permit: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in permit.items() if key != "signature_b64"}


def _verify_signature(
    permit: dict[str, Any],
    *,
    kms_public_key: KmsAuthorityPublicKey,
) -> None:
    if permit["kms_key_version"] != kms_public_key.kms_key_version:
        raise NexusReceiptPublicationError(
            "publication permit KMS key-version evidence mismatch"
        )
    if permit["signing_algorithm"] != kms_public_key.algorithm:
        raise NexusReceiptPublicationError(
            "publication permit KMS algorithm evidence mismatch"
        )
    try:
        public_key = serialization.load_pem_public_key(
            kms_public_key.public_key_pem.encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise NexusReceiptPublicationError(
            "publication permit KMS public key is invalid"
        ) from exc
    if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size != 2048:
        raise NexusReceiptPublicationError(
            "publication permit KMS public key must be RSA 2048"
        )
    try:
        observed_public_key_sha256 = authority_public_key_sha256(
            kms_public_key.public_key_pem
        )
    except CanaryConfigurationError as exc:
        raise NexusReceiptPublicationError(
            "publication permit KMS public-key evidence is invalid"
        ) from exc
    if not hmac.compare_digest(
        observed_public_key_sha256,
        kms_public_key.public_key_sha256,
    ) or not hmac.compare_digest(
        observed_public_key_sha256,
        permit["public_key_sha256"],
    ):
        raise NexusReceiptPublicationError(
            "publication permit KMS public-key digest mismatch"
        )
    try:
        signature = base64.b64decode(permit["signature_b64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise NexusReceiptPublicationError(
            "publication permit signature is not canonical base64"
        ) from exc
    if base64.b64encode(signature).decode("ascii") != permit["signature_b64"]:
        raise NexusReceiptPublicationError(
            "publication permit signature is not canonical base64"
        )
    digest = hashlib.sha256(_canonical_json_bytes(_signed_permit_payload(permit))).digest()
    try:
        public_key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise NexusReceiptPublicationError(
            "publication permit KMS signature verification failed"
        ) from exc


def validate_publication_permit(
    permit: dict[str, Any],
    *,
    receipt: dict[str, Any],
    authoritative_now: datetime | None = None,
) -> tuple[dict[str, Any], bytes]:
    content = validate_deployment_receipt(receipt)
    if not isinstance(permit, dict):
        raise NexusReceiptPublicationError("publication permit must be a JSON object")
    permit = dict(permit)
    _schema_validate(
        permit,
        schema_path=PERMIT_SCHEMA_PATH,
        label="publication permit",
    )

    project_id = receipt["project_id"]
    resource_prefix, expected_bucket = _receipt_resource_scope(receipt)
    expected_object_name = (
        f"deployment-receipts/{receipt['release_sha']}/"
        f"{receipt['receipt_sha256']}.json"
    )
    expected_key_version = expected_canary_authority_key_version(
        project_id=project_id,
        resource_prefix=resource_prefix,
    )
    expected_common = {
        "schema_version": PERMIT_SCHEMA,
        "repository": REPOSITORY,
        "project_id": project_id,
        "project_number": receipt["project_number"],
        "region": REGION,
        "resource_prefix": resource_prefix,
        "release_sha": receipt["release_sha"],
        "release_tree_sha": receipt["release_tree_sha"],
        "receipt_sha256": receipt["receipt_sha256"],
        "receipt_content_sha256": hashlib.sha256(content).hexdigest(),
        "receipt_content_length": len(content),
        "receipt_bucket": expected_bucket,
        "object_name": expected_object_name,
        "content_type": "application/json",
        "action_index": 6,
        "action_name": "deployment_receipt_publish",
        "predecessor_action_name": "judge_deploy",
        "predecessor_action_permit_sha256": receipt["actions"][-1]["evidence"][
            "action_permit_sha256"
        ],
        "maximum_mutations": 1,
        "automatic_retry": False,
        "consumption_mode": "gcs_receipt_upload_if_generation_match_zero",
        "public_traffic": False,
        "live_model_call": False,
        "production_activation": False,
        "signer_principal": (
            f"{resource_prefix}-signer@{project_id}.iam.gserviceaccount.com"
        ),
        "executor_principal": (
            f"{resource_prefix}-deployer@{project_id}.iam.gserviceaccount.com"
        ),
        "kms_key_version": expected_key_version,
        "signing_algorithm": CANARY_AUTHORITY_ALGORITHM,
    }
    for field, expected in expected_common.items():
        if permit.get(field) != expected:
            raise NexusReceiptPublicationError(
                f"publication permit is not bound to exact {field}"
            )

    _receipt_binding_consistency(receipt, receipt_bucket=expected_bucket)
    _active_time_window(permit, authoritative_now=authoritative_now)
    try:
        kms_public_key = fetch_kms_authority_public_key(expected_key_version)
    except CanaryConfigurationError as exc:
        raise NexusReceiptPublicationError(
            "publication permit exact KMS trust root could not be verified"
        ) from exc
    _verify_signature(permit, kms_public_key=kms_public_key)
    permit["permit_sha256"] = _canonical_sha256(permit)
    return permit, content


def _authorized_session_for_principal(
    *,
    expected_principal: str,
    scopes: Sequence[str],
):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession, Request

    try:
        credentials, _default_project = google.auth.default(scopes=tuple(scopes))
    except Exception as exc:
        raise NexusReceiptPublicationError(
            "ADC credentials for receipt publication are unavailable"
        ) from exc
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
    match = re.search(
        r"/serviceAccounts/([^/:]+@[^/:]+):generateAccessToken$",
        impersonation_url,
    )
    if match:
        candidates.add(match.group(1))
    if candidates != {expected_principal}:
        raise NexusReceiptPublicationError(
            "ADC identity is not the exact authorized receipt-publication executor"
        )
    try:
        credentials.refresh(Request())
    except Exception as exc:
        raise NexusReceiptPublicationError(
            "receipt-publication executor credentials could not be refreshed before dispatch"
        ) from exc
    if not getattr(credentials, "valid", False) or not getattr(credentials, "token", None):
        raise NexusReceiptPublicationError(
            "receipt-publication executor credentials are not valid before dispatch"
        )
    return AuthorizedSession(
        credentials,
        refresh_status_codes=(),
        max_refresh_attempts=0,
    )


def _storage_create_only(
    *,
    session: Any,
    bucket: str,
    object_name: str,
    content: bytes,
) -> tuple[int, dict[str, Any]]:
    """Send one create-only upload request; this function has no retry path."""

    response = session.request(
        "POST",
        f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket, safe='')}/o",
        params={
            "uploadType": "media",
            "name": object_name,
            "ifGenerationMatch": "0",
            "projection": "full",
        },
        data=content,
        headers={"Content-Type": "application/json"},
        timeout=10,
        allow_redirects=False,
    )
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = {}
    return int(response.status_code), payload if isinstance(payload, dict) else {}


def publish_deployment_receipt(
    receipt: dict[str, Any],
    permit: dict[str, Any],
    *,
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    validated_permit, content = validate_publication_permit(
        permit,
        receipt=receipt,
        authoritative_now=authoritative_now,
    )
    session = _authorized_session_for_principal(
        expected_principal=validated_permit["executor_principal"],
        scopes=("https://www.googleapis.com/auth/devstorage.read_write",),
    )
    _active_time_window(validated_permit, authoritative_now=authoritative_now)
    try:
        status_code, response = _storage_create_only(
            session=session,
            bucket=validated_permit["receipt_bucket"],
            object_name=validated_permit["object_name"],
            content=content,
        )
    except Exception as exc:
        raise NexusReceiptPublicationIndeterminate(
            "receipt publication result is indeterminate; the permit and target must be treated as consumed"
        ) from exc

    if status_code in {409, 412}:
        raise NexusReceiptAlreadyPublished(
            "deployment receipt or publication permit was already consumed; no retry is allowed"
        )
    if status_code not in {200, 201}:
        raise NexusReceiptPublicationIndeterminate(
            "receipt publication result is indeterminate; the permit and target must be treated as consumed"
        )

    generation = str(response.get("generation") or "")
    metageneration = str(response.get("metageneration") or "")
    size = str(response.get("size") or "")
    expected_md5 = _md5_b64(content)
    expected_crc32c = _crc32c_b64(content)
    if (
        response.get("bucket") != validated_permit["receipt_bucket"]
        or response.get("name") != validated_permit["object_name"]
        or not generation.isdigit()
        or int(generation) <= 0
        or metageneration != "1"
        or size != str(len(content))
        or response.get("contentType") != "application/json"
        or not hmac.compare_digest(str(response.get("md5Hash") or ""), expected_md5)
        or not hmac.compare_digest(str(response.get("crc32c") or ""), expected_crc32c)
    ):
        raise NexusReceiptPublicationIndeterminate(
            "receipt publication response is ambiguous; the permit and target must be treated as consumed"
        )

    return {
        "schema_version": PUBLICATION_SCHEMA,
        "permit_id": validated_permit["permit_id"],
        "permit_sha256": validated_permit["permit_sha256"],
        "repository": REPOSITORY,
        "project_id": receipt["project_id"],
        "project_number": receipt["project_number"],
        "region": REGION,
        "release_sha": receipt["release_sha"],
        "release_tree_sha": receipt["release_tree_sha"],
        "receipt_sha256": receipt["receipt_sha256"],
        "receipt_content_sha256": hashlib.sha256(content).hexdigest(),
        "object_uri": (
            f"gs://{validated_permit['receipt_bucket']}/"
            f"{validated_permit['object_name']}"
        ),
        "object_generation": generation,
        "object_metageneration": metageneration,
        "object_size": size,
        "object_md5": expected_md5,
        "object_crc32c": expected_crc32c,
        "maximum_mutations": 1,
        "automatic_retry": False,
        "public_traffic": False,
        "live_model_call": False,
        "production_activation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("publication_permit", type=Path)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform the single terminal create-only receipt upload",
    )
    args = parser.parse_args()
    if not args.execute:
        raise NexusReceiptPublicationError(
            "--execute is required; receipt publication never occurs implicitly"
        )
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    permit = json.loads(args.publication_permit.read_text(encoding="utf-8"))
    result = publish_deployment_receipt(receipt, permit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NexusReceiptPublicationError as exc:
        raise SystemExit(f"Nexus deployment-receipt publication blocked: {exc}") from exc
