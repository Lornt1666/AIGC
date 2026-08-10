from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
import google.auth
import google.auth.transport.requests
import pytest

import scripts.publish_nexus_deployment_receipt as publisher


PROJECT = "aigc-stage"
PROJECT_NUMBER = "170151535592"
PREFIX = "aigc"
BUCKET = f"{PROJECT}-{PREFIX}-receipts"
EVIDENCE_BUCKET = f"{PROJECT}-{PREFIX}-evidence"
RELEASE = "a" * 40
TREE = "b" * 40
IMAGE_DIGEST = "sha256:" + "c" * 64
IMMUTABLE_IMAGE = (
    f"{publisher.REGION}-docker.pkg.dev/{PROJECT}/{PREFIX}-runtime/"
    f"aigc-nexus@{IMAGE_DIGEST}"
)
TAGGED_IMAGE = (
    f"{publisher.REGION}-docker.pkg.dev/{PROJECT}/{PREFIX}-runtime/"
    f"aigc-nexus:{RELEASE}"
)
SBOM_GENERATOR_IMAGE = "anchore/syft@sha256:" + "4" * 64
AUTHORIZATION_SHA256 = "d" * 64
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY_PEM = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")
PUBLIC_KEY_SHA256 = publisher.authority_public_key_sha256(PUBLIC_KEY_PEM)
KMS_KEY_VERSION = publisher.expected_canary_authority_key_version(
    project_id=PROJECT,
    resource_prefix=PREFIX,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _authority(index: int, previous_sha256: str) -> dict[str, Any]:
    permit_id = f"ACT-DEPLOY{index:04d}"
    return {
        "action_permit_id": permit_id,
        "action_permit_sha256": _digest(f"action-permit-{index}"),
        "predecessor_permit_sha256": previous_sha256,
        "permit_consumption_uri": (
            f"gs://{BUCKET}/staging-action-permits/{RELEASE}/"
            f"{index:02d}-{permit_id}.json"
        ),
        "permit_consumption_generation": str(1000 + index),
        "permit_consumption_record_sha256": _digest(f"consumption-{index}"),
    }


def _migration() -> dict[str, Any]:
    return {
        "job_name": f"{PREFIX}-migrate-{RELEASE[:8]}",
        "execution_name": "migration-execution-1",
        "immutable_image_uri": IMMUTABLE_IMAGE,
        "service_account": f"{PREFIX}-operator@{PROJECT}.iam.gserviceaccount.com",
        "exact_execution_log_verified": True,
        "migration_receipt": {
            "schema_version": "aigc.nexus-runtime-control-migration-receipt.v2",
            "migrations": [
                {
                    "name": "003_nexus_provider_runtime_controls.sql",
                    "sha256": _digest("migration-003"),
                },
                {
                    "name": "004_nexus_persisted_authority.sql",
                    "sha256": _digest("migration-004"),
                },
            ],
            "migration_bundle_sha256": _digest("migration-bundle"),
            "runtime_control_singleton_verified": True,
            "persisted_authority_table_verified": True,
            "secret_value_emitted": False,
            "provider_call_performed": False,
            "captured_at": "2026-08-10T00:05:00+00:00",
        },
    }


def _service(role: str) -> dict[str, Any]:
    revision = f"{PREFIX}-{role}-00001"
    provider_capable = role == "operator"
    return {
        "service": f"{PREFIX}-{role}",
        "service_url": f"https://{role}.example.invalid",
        "candidate_tag": f"candidate-{role}-{RELEASE[:8]}",
        "candidate_url": f"https://candidate-{role}.example.invalid",
        "revision": revision,
        "runtime_role": role,
        "service_account": f"{PREFIX}-{role}@{PROJECT}.iam.gserviceaccount.com",
        "immutable_image_uri": IMMUTABLE_IMAGE,
        "private_iam_verified": True,
        "inherited_deployer_invoker_verified": True,
        "readiness": {
            "ready": True,
            "project_id": PROJECT,
            "runtime_role": role,
            "release_revision": RELEASE,
            "image_digest": IMAGE_DIGEST,
            "region": publisher.REGION,
            "deployment_authorization_sha256": AUTHORIZATION_SHA256,
            "provider_capable": provider_capable,
            "live_provider_execution_enabled": False,
            "production_activation": False,
            "runtime_control_backend": (
                "postgresql" if provider_capable else "not_applicable"
            ),
            "emergency_active": False,
            "stop_epoch": 0 if provider_capable else None,
        },
    }


def deployment_receipt() -> dict[str, Any]:
    migration = _migration()
    operator = _service("operator")
    judge = _service("judge")
    authorities: list[dict[str, Any]] = []
    previous = "0" * 64
    for index in range(6):
        authority = _authority(index, previous)
        authorities.append(authority)
        previous = authority["action_permit_sha256"]
    build_security = {
        "provenance_sha256": _digest("provenance"),
        "provenance_builder_id": "https://cloudbuild.googleapis.com/GoogleHostedWorker",
        "provenance_build_id": "build-123",
        "sbom_generator_image": SBOM_GENERATOR_IMAGE,
        "sbom_source_image_uri": IMMUTABLE_IMAGE,
        "sbom_local_sha256": _digest("local-sbom"),
        "sbom_format": "SPDX-2.3",
        "sbom_package_count": 7,
        "sbom_document_namespace_sha256": _digest("sbom-namespace"),
        "sbom_reference_count": 1,
        "sbom_metadata_sha256": _digest("sbom"),
        "sbom_gcs_uri": f"gs://{EVIDENCE_BUCKET}/sboms/exact.spdx.json",
        "sbom_gcs_bucket": EVIDENCE_BUCKET,
        "sbom_gcs_location": publisher.REGION,
        "sbom_occurrence_name": (
            f"projects/{PROJECT}/locations/{publisher.REGION}/occurrences/sbom-1"
        ),
        "vulnerability_finding_count": 0,
        "release_blocking_vulnerability_count": 0,
        "vulnerability_metadata_sha256": _digest("vulnerabilities"),
        "vulnerability_scan_status": "FINISHED_SUCCESS",
        "vulnerability_scan_note": (
            "projects/goog-analysis/notes/PACKAGE_VULNERABILITY"
        ),
        "vulnerability_scan_occurrence_name": (
            f"projects/{PROJECT}/locations/{publisher.REGION}/occurrences/scan-1"
        ),
        "vulnerability_scan_metadata_sha256": _digest("vulnerability-scan"),
    }
    actions = [
        {
            "action": "cloud_build_submit",
            "target": TAGGED_IMAGE,
            "mutation_count": 1,
            "automatic_retry": False,
            "status": "succeeded",
            "evidence": {
                "build_id": "build-123",
                "tagged_image_uri": TAGGED_IMAGE,
                "image_digest": IMAGE_DIGEST,
                "source_bucket": f"{PROJECT}-{PREFIX}-build-source",
                "service_account": f"{PREFIX}-build@{PROJECT}.iam.gserviceaccount.com",
                "docker_builder_image": "gcr.io/cloud-builders/docker@sha256:" + "1" * 64,
                "python_base_image": "python:3.12-slim@sha256:" + "2" * 64,
                "build_context_manifest_sha256": _digest("build-context"),
                "immutable_image_uri": IMMUTABLE_IMAGE,
                **build_security,
                **authorities[0],
            },
        },
        {
            "action": "sbom_export",
            "target": IMMUTABLE_IMAGE,
            "mutation_count": 1,
            "automatic_retry": False,
            "status": "succeeded",
            "evidence": {
                "immutable_image_uri": IMMUTABLE_IMAGE,
                **{
                    key: build_security[key]
                    for key in (
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
                **authorities[1],
            },
        },
        {
            "action": "migration_job_deploy",
            "target": migration["job_name"],
            "mutation_count": 1,
            "automatic_retry": False,
            "status": "succeeded",
            "evidence": {
                "job_name": migration["job_name"],
                "immutable_image_uri": IMMUTABLE_IMAGE,
                **authorities[2],
            },
        },
        {
            "action": "migration_execute",
            "target": migration["execution_name"],
            "mutation_count": 1,
            "automatic_retry": False,
            "status": "succeeded",
            "evidence": {**migration, **authorities[3]},
        },
        {
            "action": "operator_deploy",
            "target": operator["service"],
            "mutation_count": 1,
            "automatic_retry": False,
            "status": "succeeded",
            "evidence": {
                "revision": operator["revision"],
                "candidate_tag": operator["candidate_tag"],
                "immutable_image_uri": IMMUTABLE_IMAGE,
                "readiness_verified": True,
                **authorities[4],
            },
        },
        {
            "action": "judge_deploy",
            "target": judge["service"],
            "mutation_count": 1,
            "automatic_retry": False,
            "status": "succeeded",
            "evidence": {
                "revision": judge["revision"],
                "candidate_tag": judge["candidate_tag"],
                "immutable_image_uri": IMMUTABLE_IMAGE,
                "readiness_verified": True,
                **authorities[5],
            },
        },
    ]
    receipt = {
        "schema_version": "aigc.quebec-deployment-receipt.v1",
        "repository": publisher.REPOSITORY,
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": publisher.REGION,
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
        "ci_run_id": "31264978346",
        "ci_admission": {
            "workflow_run_id": "31264978346",
            "workflow_run_url": "https://github.com/Lornt1666/AIGC/actions/runs/31264978346",
            "artifact_id": "9023893562",
            "artifact_digest": "sha256:" + "3" * 64,
            "ci_admission_sha256": _digest("ci-admission"),
            "stage_count": 15,
            "container_receipt_sha256": _digest("container-receipt"),
        },
        "authorization_sha256": AUTHORIZATION_SHA256,
        "resource_manifest_sha256": _digest("resource-manifest"),
        "build_id": "build-123",
        "build_context_manifest_sha256": _digest("build-context"),
        "build_source_bucket": f"{PROJECT}-{PREFIX}-build-source",
        "tagged_image_uri": TAGGED_IMAGE,
        "image_digest": IMAGE_DIGEST,
        "immutable_image_uri": IMMUTABLE_IMAGE,
        "foundation": {
            "artifact_repository_sha256": _digest("artifact-repository"),
            "cloud_sql_sha256": _digest("cloud-sql"),
            "network_sha256": _digest("network"),
            "subnet_sha256": _digest("subnet"),
            "service_account_metadata_sha256": {
                f"identity-{index}": _digest(f"identity-{index}")
                for index in range(5)
            },
            "cloud_sql_connection_name": (
                f"{PROJECT}:{publisher.REGION}:{PREFIX}-control"
            ),
            "region": publisher.REGION,
            "action_permission_preflight_sha256": _digest("permission-preflight"),
        },
        "supply_chain": {
            "docker_builder_image": actions[0]["evidence"]["docker_builder_image"],
            "python_base_image": actions[0]["evidence"]["python_base_image"],
            **build_security,
        },
        "operator_revision": operator["revision"],
        "judge_revision": judge["revision"],
        "migration": migration,
        "services": {"operator": operator, "judge": judge},
        "actions": actions,
        "public_traffic": False,
        "public_access_enabled": False,
        "traffic_migration_performed": False,
        "live_model_call_performed": False,
        "production_activation": False,
        "resource_locations": {
            "cloud_build": publisher.REGION,
            "artifact_registry": publisher.REGION,
            "cloud_run": publisher.REGION,
            "cloud_sql": publisher.REGION,
            "secret_manager": publisher.REGION,
            "build_source_bucket": publisher.REGION,
            "sbom_bucket": publisher.REGION,
        },
        "captured_at": "2026-08-10T00:10:00+00:00",
    }
    receipt["receipt_sha256"] = publisher._canonical_sha256(receipt)
    return receipt


def _resign(permit: dict[str, Any]) -> dict[str, Any]:
    permit = {key: value for key, value in permit.items() if key != "signature_b64"}
    digest = hashlib.sha256(publisher._canonical_json_bytes(permit)).digest()
    signature = PRIVATE_KEY.sign(
        digest,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        utils.Prehashed(hashes.SHA256()),
    )
    permit["signature_b64"] = base64.b64encode(signature).decode("ascii")
    return permit


def publication_permit(
    receipt: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    authoritative_now = now or datetime(2026, 8, 10, 0, 12, tzinfo=timezone.utc)
    content = publisher.validate_deployment_receipt(receipt)
    permit = {
        "schema_version": publisher.PERMIT_SCHEMA,
        "permit_id": "PUB-RECEIPT0001",
        "nonce": _digest("publication-nonce"),
        "repository": publisher.REPOSITORY,
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": publisher.REGION,
        "resource_prefix": PREFIX,
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
        "receipt_sha256": receipt["receipt_sha256"],
        "receipt_content_sha256": hashlib.sha256(content).hexdigest(),
        "receipt_content_length": len(content),
        "receipt_bucket": BUCKET,
        "object_name": (
            f"deployment-receipts/{RELEASE}/{receipt['receipt_sha256']}.json"
        ),
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
        "signer_principal": f"{PREFIX}-signer@{PROJECT}.iam.gserviceaccount.com",
        "executor_principal": f"{PREFIX}-deployer@{PROJECT}.iam.gserviceaccount.com",
        "kms_key_version": KMS_KEY_VERSION,
        "signing_algorithm": publisher.CANARY_AUTHORITY_ALGORITHM,
        "public_key_sha256": PUBLIC_KEY_SHA256,
        "issued_at": (authoritative_now - timedelta(minutes=2)).isoformat(),
        "not_before": (authoritative_now - timedelta(minutes=1)).isoformat(),
        "expires_at": (authoritative_now + timedelta(minutes=5)).isoformat(),
    }
    return _resign(permit)


def kms_public_key() -> publisher.KmsAuthorityPublicKey:
    return publisher.KmsAuthorityPublicKey(
        kms_key_version=KMS_KEY_VERSION,
        algorithm=publisher.CANARY_AUTHORITY_ALGORITHM,
        public_key_pem=PUBLIC_KEY_PEM,
        public_key_sha256=PUBLIC_KEY_SHA256,
    )


def _admit_kms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        publisher,
        "fetch_kms_authority_public_key",
        lambda key_version: kms_public_key()
        if key_version == KMS_KEY_VERSION
        else (_ for _ in ()).throw(AssertionError(key_version)),
    )


def _success_response(content: bytes, *, object_name: str) -> dict[str, Any]:
    return {
        "bucket": BUCKET,
        "name": object_name,
        "generation": "123456789",
        "metageneration": "1",
        "size": str(len(content)),
        "contentType": "application/json",
        "md5Hash": publisher._md5_b64(content),
        "crc32c": publisher._crc32c_b64(content),
    }


def test_valid_permit_publishes_exact_canonical_receipt_once(monkeypatch):
    receipt = deployment_receipt()
    now = datetime(2026, 8, 10, 0, 12, tzinfo=timezone.utc)
    permit = publication_permit(receipt, now=now)
    _admit_kms(monkeypatch)
    session = object()
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda **kwargs: session
        if kwargs["expected_principal"]
        == f"{PREFIX}-deployer@{PROJECT}.iam.gserviceaccount.com"
        else (_ for _ in ()).throw(AssertionError(kwargs)),
    )
    uploads: list[dict[str, Any]] = []

    def create_only(**kwargs):
        uploads.append(kwargs)
        return 200, _success_response(
            kwargs["content"],
            object_name=kwargs["object_name"],
        )

    monkeypatch.setattr(publisher, "_storage_create_only", create_only)
    result = publisher.publish_deployment_receipt(
        receipt,
        permit,
        authoritative_now=now,
    )

    assert len(uploads) == 1
    assert uploads[0]["session"] is session
    assert uploads[0]["bucket"] == BUCKET
    assert uploads[0]["content"] == publisher._canonical_json_bytes(receipt)
    assert uploads[0]["object_name"] == (
        f"deployment-receipts/{RELEASE}/{receipt['receipt_sha256']}.json"
    )
    assert result["object_generation"] == "123456789"
    assert result["receipt_sha256"] == receipt["receipt_sha256"]
    assert result["maximum_mutations"] == 1
    assert result["automatic_retry"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "attacker-project"),
        ("region", "us-central1"),
        ("release_sha", "f" * 40),
        ("release_tree_sha", "e" * 40),
        ("receipt_bucket", "attacker-receipts"),
        ("executor_principal", "attacker@aigc-stage.iam.gserviceaccount.com"),
        ("kms_key_version", KMS_KEY_VERSION.replace("/1", "/2")),
        ("predecessor_action_permit_sha256", "0" * 64),
    ],
)
def test_signed_but_misbound_permit_fails_before_upload(monkeypatch, field, value):
    receipt = deployment_receipt()
    now = datetime(2026, 8, 10, 0, 12, tzinfo=timezone.utc)
    permit = publication_permit(receipt, now=now)
    permit[field] = value
    permit = _resign(permit)
    uploads: list[None] = []
    monkeypatch.setattr(
        publisher,
        "_storage_create_only",
        lambda **_kwargs: uploads.append(None),
    )
    with pytest.raises(publisher.NexusReceiptPublicationError):
        publisher.publish_deployment_receipt(
            receipt,
            permit,
            authoritative_now=now,
        )
    assert uploads == []


def test_receipt_hash_tampering_fails_before_kms_or_upload(monkeypatch):
    receipt = deployment_receipt()
    permit = publication_permit(receipt)
    receipt["build_id"] = "attacker-build"
    kms_calls: list[None] = []
    uploads: list[None] = []
    monkeypatch.setattr(
        publisher,
        "fetch_kms_authority_public_key",
        lambda _key: kms_calls.append(None),
    )
    monkeypatch.setattr(
        publisher,
        "_storage_create_only",
        lambda **_kwargs: uploads.append(None),
    )
    with pytest.raises(publisher.NexusReceiptPublicationError, match="SHA-256"):
        publisher.publish_deployment_receipt(receipt, permit)
    assert kms_calls == []
    assert uploads == []


def test_schema_valid_but_semantically_rebound_receipt_is_rejected(monkeypatch):
    receipt = deployment_receipt()
    receipt["services"]["judge"]["readiness"]["project_id"] = "other-project"
    receipt["receipt_sha256"] = publisher._canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    permit = publication_permit(receipt)
    uploads: list[None] = []
    monkeypatch.setattr(
        publisher,
        "_storage_create_only",
        lambda **_kwargs: uploads.append(None),
    )
    with pytest.raises(publisher.NexusReceiptPublicationError, match="judge"):
        publisher.publish_deployment_receipt(receipt, permit)
    assert uploads == []


def test_signature_tampering_fails_before_identity_or_upload(monkeypatch):
    receipt = deployment_receipt()
    now = datetime(2026, 8, 10, 0, 12, tzinfo=timezone.utc)
    permit = publication_permit(receipt, now=now)
    signature = bytearray(base64.b64decode(permit["signature_b64"]))
    signature[0] ^= 1
    permit["signature_b64"] = base64.b64encode(signature).decode("ascii")
    _admit_kms(monkeypatch)
    identity_calls: list[None] = []
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda **_kwargs: identity_calls.append(None),
    )
    with pytest.raises(publisher.NexusReceiptPublicationError, match="signature"):
        publisher.publish_deployment_receipt(
            receipt,
            permit,
            authoritative_now=now,
        )
    assert identity_calls == []


@pytest.mark.parametrize("offset", [timedelta(hours=-1), timedelta(hours=1)])
def test_expired_or_not_yet_active_permit_never_uploads(monkeypatch, offset):
    receipt = deployment_receipt()
    permit_time = datetime(2026, 8, 10, 0, 12, tzinfo=timezone.utc)
    permit = publication_permit(receipt, now=permit_time + offset)
    uploads: list[None] = []
    monkeypatch.setattr(
        publisher,
        "_storage_create_only",
        lambda **_kwargs: uploads.append(None),
    )
    with pytest.raises(publisher.NexusReceiptPublicationError):
        publisher.publish_deployment_receipt(
            receipt,
            permit,
            authoritative_now=permit_time,
        )
    assert uploads == []


def test_replay_is_terminal_and_never_retried(monkeypatch):
    receipt = deployment_receipt()
    now = datetime(2026, 8, 10, 0, 12, tzinfo=timezone.utc)
    permit = publication_permit(receipt, now=now)
    _admit_kms(monkeypatch)
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda **_kwargs: object(),
    )
    calls: list[None] = []

    def replay(**_kwargs):
        calls.append(None)
        return 412, {"error": {"message": "conditionNotMet"}}

    monkeypatch.setattr(publisher, "_storage_create_only", replay)
    with pytest.raises(publisher.NexusReceiptAlreadyPublished, match="no retry"):
        publisher.publish_deployment_receipt(
            receipt,
            permit,
            authoritative_now=now,
        )
    assert len(calls) == 1


@pytest.mark.parametrize("outcome", ["server_error", "ambiguous_success", "exception"])
def test_indeterminate_outcome_is_terminal_and_never_retried(monkeypatch, outcome):
    receipt = deployment_receipt()
    now = datetime(2026, 8, 10, 0, 12, tzinfo=timezone.utc)
    permit = publication_permit(receipt, now=now)
    _admit_kms(monkeypatch)
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda **_kwargs: object(),
    )
    calls: list[None] = []

    def indeterminate(**kwargs):
        calls.append(None)
        if outcome == "server_error":
            return 500, {}
        if outcome == "ambiguous_success":
            return 200, {
                "bucket": BUCKET,
                "name": kwargs["object_name"],
                "generation": "123",
            }
        raise TimeoutError("response lost")

    monkeypatch.setattr(publisher, "_storage_create_only", indeterminate)
    with pytest.raises(publisher.NexusReceiptPublicationIndeterminate, match="consumed"):
        publisher.publish_deployment_receipt(
            receipt,
            permit,
            authoritative_now=now,
        )
    assert len(calls) == 1


def test_storage_boundary_uses_fixed_destination_and_create_only_precondition():
    content = b'{"receipt":"canonical"}'
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    class Response:
        status_code = 201

        @staticmethod
        def json():
            return {"name": "unused"}

    class Session:
        @staticmethod
        def request(*args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    status, _response = publisher._storage_create_only(
        session=Session(),
        bucket=BUCKET,
        object_name=f"deployment-receipts/{RELEASE}/{'f' * 64}.json",
        content=content,
    )
    assert status == 201
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (
        "POST",
        f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o",
    )
    assert kwargs["params"]["uploadType"] == "media"
    assert kwargs["params"]["ifGenerationMatch"] == "0"
    assert kwargs["data"] == content
    assert kwargs["allow_redirects"] is False


def test_authorized_session_refreshes_before_dispatch_and_disables_http_retry(
    monkeypatch,
):
    expected_principal = f"{PREFIX}-deployer@{PROJECT}.iam.gserviceaccount.com"

    class Credentials:
        service_account_email = expected_principal
        signer_email = None
        _target_principal = None
        service_account_impersonation_url = ""
        valid = False
        token = None

        def refresh(self, request):
            assert request == "auth-request"
            self.valid = True
            self.token = object()

    credentials = Credentials()
    monkeypatch.setattr(
        google.auth,
        "default",
        lambda **kwargs: (credentials, PROJECT)
        if kwargs["scopes"]
        == ("https://www.googleapis.com/auth/devstorage.read_write",)
        else (_ for _ in ()).throw(AssertionError(kwargs)),
    )
    monkeypatch.setattr(
        google.auth.transport.requests,
        "Request",
        lambda: "auth-request",
    )
    constructor_calls: list[tuple[Any, dict[str, Any]]] = []

    def authorized_session(value, **kwargs):
        constructor_calls.append((value, kwargs))
        return "non-retrying-session"

    monkeypatch.setattr(
        google.auth.transport.requests,
        "AuthorizedSession",
        authorized_session,
    )
    session = publisher._authorized_session_for_principal(
        expected_principal=expected_principal,
        scopes=("https://www.googleapis.com/auth/devstorage.read_write",),
    )
    assert session == "non-retrying-session"
    assert constructor_calls == [
        (
            credentials,
            {"refresh_status_codes": (), "max_refresh_attempts": 0},
        )
    ]
