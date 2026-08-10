from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
import pytest

import scripts.publish_nexus_canary_receipts as publisher
from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.domain.nexus.contracts import AuthorityAttestation, ExecutionPermit


PROJECT = "aigc-stage"
PROJECT_NUMBER = "170151535592"
PREFIX = "aigc"
REGION = publisher.REGION
RELEASE = "a" * 40
TREE = "b" * 40
PROVIDER = "google_vertex_gemini"
JOB = "aigc-gemini-123456789abc"
EXECUTION = JOB + "-abc123"
IMAGE = (
    f"{REGION}-docker.pkg.dev/{PROJECT}/{PREFIX}-runtime/"
    "aigc-nexus@sha256:" + "1" * 64
)
BUCKET = f"{PROJECT}-{PREFIX}-receipts"
NOW = datetime(2026, 8, 10, 14, 0, tzinfo=timezone.utc)
KMS_KEY_VERSION = publisher.expected_canary_authority_key_version(
    project_id=PROJECT,
    resource_prefix=PREFIX,
)
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY_PEM = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")
PUBLIC_KEY_SHA256 = publisher.authority_public_key_sha256(PUBLIC_KEY_PEM)
PUBLICATION_SOURCE = (
    f"{PREFIX}-can-bind@{PROJECT}.iam.gserviceaccount.com"
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _sign(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).digest()
    signature = PRIVATE_KEY.sign(
        digest,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        utils.Prehashed(hashes.SHA256()),
    )
    return base64.b64encode(signature).decode("ascii")


def _resign(value: dict[str, Any]) -> dict[str, Any]:
    unsigned = {key: item for key, item in value.items() if key != "signature_b64"}
    return {**unsigned, "signature_b64": _sign(unsigned)}


def governed_provisioning_permit() -> dict[str, Any]:
    value = {
        "schema_version": publisher.GOVERNED_PROVISIONING_PERMIT_SCHEMA,
        "permit_id": "CJP-CANARY001",
        "nonce": _digest("governed-provisioning-nonce"),
        "repository": publisher.REPOSITORY,
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": REGION,
        "release_sha": RELEASE,
        "provider_id": PROVIDER,
        "job_name": JOB,
        "target": f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}",
        "immutable_image_uri": IMAGE,
        "reserved_usage_units": 128,
        "maximum_input_units": 64,
        "maximum_output_units": 64,
        "request_timeout_seconds": 30,
        "runtime_service_account": (
            f"{PREFIX}-can-gem@{PROJECT}.iam.gserviceaccount.com"
        ),
        "provisioner_principal": (
            f"{PREFIX}-can-prov@{PROJECT}.iam.gserviceaccount.com"
        ),
        "executor_principal": (
            f"{PREFIX}-can-exec@{PROJECT}.iam.gserviceaccount.com"
        ),
        "signer_principal": (
            f"{PREFIX}-signer@{PROJECT}.iam.gserviceaccount.com"
        ),
        "receipt_bucket": BUCKET,
        "procurement_sha256": _digest("procurement"),
        "deployment_sha256": _digest("deployment"),
        "plan_sha256": _digest("plan"),
        "governance_decision_sha256": _digest("governance"),
        "execution_permit_sha256": _digest("execution-permit-placeholder"),
        "authority_attestation_sha256": _digest("attestation-placeholder"),
        "authority_environment_sha256": _digest("authority-environment"),
        "job_spec_sha256": _digest("job-spec"),
        "maximum_mutations": 1,
        "automatic_retry": False,
        "consumption_mode": "gcs_if_generation_match_zero",
        "job_execution_authorized": False,
        "live_model_call_authorized": False,
        "production_activation": False,
        "kms_key_version": KMS_KEY_VERSION,
        "signing_algorithm": publisher.CANARY_AUTHORITY_ALGORITHM,
        "public_key_sha256": PUBLIC_KEY_SHA256,
        "issued_at": (NOW - timedelta(minutes=2)).isoformat(),
        "not_before": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
    }
    return _resign(value)


def provisioning_receipt(
    governed_permit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    governed = governed_permit or governed_provisioning_permit()
    provisioner = f"{PREFIX}-can-prov@{PROJECT}.iam.gserviceaccount.com"
    executor = f"{PREFIX}-can-exec@{PROJECT}.iam.gserviceaccount.com"
    runtime = f"{PREFIX}-can-gem@{PROJECT}.iam.gserviceaccount.com"
    authority_environment_sha256 = governed["authority_environment_sha256"]
    receipt = {
        "schema_version": publisher.PROVISIONING_RECEIPT_SCHEMA,
        "repository": publisher.REPOSITORY,
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": REGION,
        "release_sha": RELEASE,
        "provider_id": PROVIDER,
        "job_name": JOB,
        "target": f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}",
        "immutable_image_uri": IMAGE,
        "reserved_usage_units": 128,
        "maximum_input_units": 64,
        "maximum_output_units": 64,
        "request_timeout_seconds": 30,
        "runtime_service_account": runtime,
        "provisioner_principal": provisioner,
        "executor_principal": executor,
        "job_spec_sha256": governed["job_spec_sha256"],
        "authority_environment_sha256": authority_environment_sha256,
        "identity_evidence": {
            "attached_service_account": provisioner,
            "attached_service_account_verified": True,
            "credential_source": "gce_metadata_server",
            "client_impersonation_used": False,
            "workload_identity_federation_used": False,
            "project_wide_permanent_mutation_authority": False,
            "broker_authority_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
            "account_level_impersonation_grant_claimed": False,
            "service_account_key_used": False,
        },
        "permission_evidence": {
            "job_execution_authority_absent": True,
        },
        "job_target": {
            "job_name": JOB,
            "immutable_image_uri": IMAGE,
            "service_account": runtime,
            "authority_environment_sha256": authority_environment_sha256,
            "cloud_sql_connection": f"{PROJECT}:{REGION}:{PREFIX}-control",
            "cloud_sql_volume_verified": True,
            "cloud_sql_annotation_verified": False,
            "job_description_sha256": _digest("job-description"),
        },
        "provisioning_permit_id": governed["permit_id"],
        "provisioning_permit_sha256": canonical_sha256(governed),
        "permit_consumption_uri": (
            f"gs://{BUCKET}/canary-job-provisioning/{RELEASE}/"
            f"{governed['permit_id']}.json"
        ),
        "permit_consumption_generation": "7",
        "permit_consumption_record_sha256": _digest("permit-consumption"),
        "job_deployment_performed": True,
        "job_execution_performed": False,
        "execution_overrides_authorized": False,
        "provider_call_performed": False,
        "cloud_run_mutation_count": 1,
        "captured_at": NOW.isoformat(),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def execution_authority() -> tuple[dict[str, Any], dict[str, Any]]:
    request_digest = _digest("provider-request")
    plan_sha256 = _digest("execution-plan")
    permit = ExecutionPermit(
        permit_id="PERMIT-CANARY001",
        governance_decision_id="GOV-CANARY001",
        principal="operator:aigc-canary",
        capability="generate.text",
        resource_scope=(f"provider://{PROVIDER}/bound/{_digest('resource')}",),
        exact_revision=RELEASE,
        change_set_hash=_digest("change-set"),
        request_digest=request_digest,
        expires_at=NOW + timedelta(minutes=5),
        maximum_invocations=1,
    )
    permit_sha256 = canonical_sha256(permit.model_dump(mode="json"))
    provisional = AuthorityAttestation(
        attestation_id="AUTH-CANARY001",
        issuer=f"gcp-kms:{KMS_KEY_VERSION}",
        subject="operator:test",
        kms_key_version=KMS_KEY_VERSION,
        signing_algorithm=publisher.CANARY_AUTHORITY_ALGORITHM,
        public_key_sha256=PUBLIC_KEY_SHA256,
        procurement_sha256=_digest("procurement"),
        deployment_sha256=_digest("deployment"),
        plan_sha256=plan_sha256,
        governance_decision_sha256=_digest("governance"),
        execution_permit_sha256=permit_sha256,
        request_digest=request_digest,
        permit_id=permit.permit_id,
        job_name=JOB,
        execution_nonce=_digest("execution-nonce"),
        issued_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=10),
        signature_b64="A" * 32,
    )
    attestation = provisional.model_copy(
        update={"signature_b64": _sign(provisional.signed_payload())}
    )
    return permit.model_dump(mode="json"), attestation.model_dump(mode="json")


def execution_receipt(
    predecessor: dict[str, Any],
    execution_permit: dict[str, Any],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    provider_receipt = {
        "schema_version": publisher.LIVE_RECEIPT_SCHEMA,
        "provider_id": PROVIDER,
        "project_id": PROJECT,
        "region": REGION,
        "execution_region": REGION,
        "provider_location": REGION,
        "model": "example-model",
        "reserved_usage_units": 128,
        "maximum_input_units": 64,
        "maximum_output_units": 64,
        "request_timeout_seconds": 30,
        "exact_revision": RELEASE,
        "plan_sha256": attestation["plan_sha256"],
        "authority_attestation_sha256": canonical_sha256(attestation),
        "permit_id": execution_permit["permit_id"],
        "request_digest": execution_permit["request_digest"],
        "job_name": JOB,
        "execution_name": EXECUTION,
        "invocation_id": "PINV-CANARY-1234567890ABCDEF",
        "attempt": {
            "invocation_id": "PINV-CANARY-1234567890ABCDEF",
            "provider_id": PROVIDER,
            "status": "succeeded",
            "provider_request_id": "provider-request-1",
            "model_or_resource": "example-model",
            "latency_ms": 25,
            "usage_units": 16,
            "input_usage_units": 8,
            "output_usage_units": 8,
            "cost_cad": "0.01",
            "cost_known": True,
            "finish_status": "STOP",
            "response_digest": "8" * 64,
            "response_payload": None,
            "external_action_performed": True,
            "outcome_known": True,
        },
        "receipt": {
            "receipt_id": "EXEC-CANARY1234567890ABCDEF",
            "permit_id": execution_permit["permit_id"],
            "change_set_id": "CHG-CANARY001",
            "parent_state_hash": "b" * 64,
            "execution_status": "succeeded",
            "operations": [
                {
                    "operation_id": "PINV-CANARY-1234567890ABCDEF",
                    "status": "succeeded",
                    "resource_ref": "provider://example/bound/resource",
                    "after_hash": "8" * 64,
                    "evidence_refs": [],
                }
            ],
            "external_action_performed": True,
            "reconciliation_required": False,
        },
        "audit": {
            "adapter_invocations": 1,
            "provider_api_calls_performed": 1,
            "network_calls_performed": 1,
            "credentials_used": 1,
            "external_actions_performed": 1,
            "spend_cad": "0.01",
            "spend_known": True,
        },
        "replayed": False,
        "response_payload_retained": False,
        "captured_at": NOW.isoformat(),
    }
    provider_receipt["canary_receipt_id"] = (
        "CANARY-" + canonical_sha256(provider_receipt)[:24].upper()
    )
    executor = predecessor["executor_principal"]
    receipt = {
        "schema_version": publisher.EXECUTION_RECEIPT_SCHEMA,
        "project_id": PROJECT,
        "region": REGION,
        "job_name": JOB,
        "execution_name": EXECUTION,
        "executor_identity": executor,
        "executor_identity_evidence": {
            "adc_impersonation_target": executor,
            "adc_impersonation_target_verified": True,
            "adc_source_principal": PUBLICATION_SOURCE,
            "adc_source_credential_type": "google.auth.compute_engine.credentials.Credentials",
            "adc_source_keyless_verified": True,
            "attached_metadata_source_verified": True,
            "bounded_token_lifetime_seconds": 120,
            "bounded_token_expires_at": (NOW + timedelta(minutes=2)).isoformat(),
            "bounded_token_refresh_permitted": False,
            "account_level_impersonation_grant_claimed": False,
            "service_account_key_used": False,
            "jit_grant_receipt_id": "JIT-CANARYEXEC001",
            "jit_grant_receipt_sha256": "8" * 64,
            "jit_source_principal": PUBLICATION_SOURCE,
            "jit_target_principal": executor,
            "jit_target_resource": (
                f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}"
            ),
            "jit_grant_scope": "exact_target_service_account",
            "jit_account_level_grant": False,
            "jit_service_account_key_used": False,
            "jit_wif_used": False,
            "jit_revocation_required": True,
            "jit_expires_at": (NOW + timedelta(minutes=3)).isoformat(),
            "jit_grant_condition_expression": (
                'request.time < timestamp("'
                + (NOW + timedelta(minutes=3)).isoformat().replace(
                    "+00:00", "Z"
                )
                + '")'
            ),
        },
        "execution_binding_receipt_sha256": "7" * 64,
        "immutable_image_uri": IMAGE,
        "reserved_usage_units": 128,
        "maximum_input_units": 64,
        "maximum_output_units": 64,
        "request_timeout_seconds": 30,
        "job_target": {
            "job_name": JOB,
            "immutable_image_uri": IMAGE,
            "service_account": predecessor["runtime_service_account"],
            "authority_environment_sha256": predecessor[
                "authority_environment_sha256"
            ],
        },
        "execution_target": {
            "execution_name": EXECUTION,
            "immutable_image_uri": IMAGE,
            "service_account": predecessor["runtime_service_account"],
        },
        "provider_receipt": provider_receipt,
        "automatic_retry": False,
        "job_max_retries": 0,
        "job_deployment_performed": False,
        "execution_overrides_supplied": False,
        "cloud_run_mutation_count": 1,
        "captured_at": NOW.isoformat(),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def publication_permit(
    context: publisher.PublicationContext,
) -> dict[str, Any]:
    permit = {
        **publisher._expected_permit_fields(context),
        "source_principal": PUBLICATION_SOURCE,
        "permit_id": (
            "CPUB-P-CANARY001"
            if context.kind == "canary_job_provisioning"
            else "CPUB-E-CANARY001"
        ),
        "nonce": _digest("publication-" + context.kind),
        "public_key_sha256": PUBLIC_KEY_SHA256,
        "issued_at": (NOW - timedelta(minutes=2)).isoformat(),
        "not_before": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
    }
    return _resign(permit)


def material():
    governed = governed_provisioning_permit()
    predecessor = provisioning_receipt(governed)
    execution_permit, attestation = execution_authority()
    execution = execution_receipt(predecessor, execution_permit, attestation)
    provisioning_context = publisher._provisioning_context(
        predecessor,
        governed,
        release_tree_sha=TREE,
    )
    execution_context = publisher._execution_context(
        execution,
        predecessor,
        execution_permit,
        attestation,
        release_tree_sha=TREE,
    )
    return {
        "governed": governed,
        "predecessor": predecessor,
        "execution_permit": execution_permit,
        "attestation": attestation,
        "execution": execution,
        "provisioning_context": provisioning_context,
        "execution_context": execution_context,
        "provisioning_publication_permit": publication_permit(
            provisioning_context
        ),
        "execution_publication_permit": publication_permit(execution_context),
    }


def _kms_public_key() -> publisher.KmsAuthorityPublicKey:
    return publisher.KmsAuthorityPublicKey(
        kms_key_version=KMS_KEY_VERSION,
        algorithm=publisher.CANARY_AUTHORITY_ALGORITHM,
        public_key_pem=PUBLIC_KEY_PEM,
        public_key_sha256=PUBLIC_KEY_SHA256,
    )


def _success(context: publisher.PublicationContext) -> dict[str, Any]:
    return {
        "bucket": context.receipt_bucket,
        "name": context.object_name,
        "generation": "123456789",
        "metageneration": "1",
        "size": str(len(context.receipt_content)),
        "contentType": "application/json",
        "md5Hash": publisher._md5_b64(context.receipt_content),
        "crc32c": publisher._crc32c_b64(context.receipt_content),
    }


def _admit_boundary(monkeypatch, context, uploads):
    session = object()
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda principal, **kwargs: session
        if (
            principal == f"{PREFIX}-can-pub@{PROJECT}.iam.gserviceaccount.com"
            and kwargs["expected_source"] == PUBLICATION_SOURCE
        )
        else (_ for _ in ()).throw(AssertionError(principal)),
    )
    monkeypatch.setattr(
        publisher,
        "_fetch_kms_public_key",
        lambda **kwargs: _kms_public_key()
        if kwargs == {"session": session, "kms_key_version": KMS_KEY_VERSION}
        else (_ for _ in ()).throw(AssertionError(kwargs)),
    )

    def create_only(**kwargs):
        uploads.append(kwargs)
        return 200, _success(context)

    monkeypatch.setattr(publisher, "_storage_create_only", create_only)
    return session


def test_provisioning_receipt_publishes_one_exact_canonical_object(monkeypatch):
    values = material()
    context = values["provisioning_context"]
    uploads: list[dict[str, Any]] = []
    session = _admit_boundary(monkeypatch, context, uploads)
    result = publisher.publish_provisioning_receipt(
        values["predecessor"],
        values["governed"],
        values["provisioning_publication_permit"],
        release_tree_sha=TREE,
        authoritative_now=NOW,
    )
    assert len(uploads) == 1
    assert uploads[0] == {
        "session": session,
        "bucket": BUCKET,
        "object_name": context.object_name,
        "content": canonical_json_bytes(values["predecessor"]),
    }
    assert result["receipt_kind"] == "canary_job_provisioning"
    assert result["execution_name"] is None
    assert result["predecessor_sha256"] == values["governed"][
        "deployment_sha256"
    ]
    assert result["object_generation"] == "123456789"
    assert result["automatic_retry"] is False


def test_execution_receipt_publishes_one_exact_predecessor_bound_object(monkeypatch):
    values = material()
    context = values["execution_context"]
    uploads: list[dict[str, Any]] = []
    _admit_boundary(monkeypatch, context, uploads)
    result = publisher.publish_execution_receipt(
        values["execution"],
        values["predecessor"],
        values["execution_permit"],
        values["attestation"],
        values["execution_publication_permit"],
        release_tree_sha=TREE,
        authoritative_now=NOW,
    )
    assert len(uploads) == 1
    assert uploads[0]["content"] == canonical_json_bytes(values["execution"])
    assert result["receipt_kind"] == "canary_job_execution"
    assert result["execution_name"] == EXECUTION
    assert result["predecessor_sha256"] == values["predecessor"][
        "receipt_sha256"
    ]
    assert result["governed_permit_id"] == values["execution_permit"][
        "permit_id"
    ]


def test_legacy_caller_controlled_active_account_evidence_is_rejected() -> None:
    receipt = provisioning_receipt()
    receipt["identity_evidence"] = {
        "active_account": receipt["provisioner_principal"],
        "gcloud_base_principal": "operator-test@example.com",
        "gcloud_impersonation_target": receipt["provisioner_principal"],
        "service_account_key_used": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    with pytest.raises(
        publisher.CanaryReceiptPublicationError, match="internally inconsistent"
    ):
        publisher._validate_provisioning_receipt(receipt)


def test_execution_receipt_rejects_extra_identity_evidence() -> None:
    values = material()
    receipt = deepcopy(values["execution"])
    receipt["executor_identity_evidence"]["raw_secret"] = "must-not-publish"
    receipt["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    with pytest.raises(
        publisher.CanaryReceiptPublicationError,
        match="executor identity evidence",
    ):
        publisher._execution_context(
            receipt,
            values["predecessor"],
            values["execution_permit"],
            values["attestation"],
            release_tree_sha=TREE,
        )


def test_receipt_type_confusion_fails_before_identity_or_upload(monkeypatch):
    values = material()
    boundary_calls: list[None] = []
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda _principal, **_kwargs: boundary_calls.append(None),
    )
    with pytest.raises(publisher.CanaryReceiptPublicationError, match="receipt type"):
        publisher.publish_provisioning_receipt(
            values["execution"],
            values["governed"],
            values["provisioning_publication_permit"],
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    with pytest.raises(publisher.CanaryReceiptPublicationError, match="receipt type"):
        publisher.publish_execution_receipt(
            values["predecessor"],
            values["predecessor"],
            values["execution_permit"],
            values["attestation"],
            values["execution_publication_permit"],
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    assert boundary_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("receipt_kind", "canary_job_execution"),
        ("release_tree_sha", "f" * 40),
        ("predecessor_sha256", "e" * 64),
        ("governed_permit_sha256", "d" * 64),
        ("receipt_content_length", 1),
        ("object_name", "canary-provisioning-receipts/attacker.json"),
        (
            "publisher_principal",
            f"{PREFIX}-deployer@{PROJECT}.iam.gserviceaccount.com",
        ),
        (
            "source_principal",
            f"{PREFIX}-can-pub@{PROJECT}.iam.gserviceaccount.com",
        ),
    ],
)
def test_signed_but_misbound_publication_permit_fails_before_identity(
    monkeypatch, field, value
):
    values = material()
    permit = dict(values["provisioning_publication_permit"])
    permit[field] = value
    permit = _resign(permit)
    identity_calls: list[None] = []
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda _principal, **_kwargs: identity_calls.append(None),
    )
    with pytest.raises(publisher.CanaryReceiptPublicationError):
        publisher.publish_provisioning_receipt(
            values["predecessor"],
            values["governed"],
            permit,
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    assert identity_calls == []


def test_receipt_and_governed_permit_tampering_fail_before_identity(monkeypatch):
    values = material()
    identity_calls: list[None] = []
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda _principal, **_kwargs: identity_calls.append(None),
    )
    tampered_receipt = deepcopy(values["predecessor"])
    tampered_receipt["job_name"] = "attacker-job"
    with pytest.raises(publisher.CanaryReceiptPublicationError, match="SHA-256"):
        publisher.publish_provisioning_receipt(
            tampered_receipt,
            values["governed"],
            values["provisioning_publication_permit"],
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    tampered_governed = dict(values["governed"])
    tampered_governed["deployment_sha256"] = "f" * 64
    tampered_governed = _resign(tampered_governed)
    with pytest.raises(publisher.CanaryReceiptPublicationError, match="SHA-256"):
        publisher.publish_provisioning_receipt(
            values["predecessor"],
            tampered_governed,
            values["provisioning_publication_permit"],
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    assert identity_calls == []


def test_execution_permit_substitution_fails_before_identity(monkeypatch):
    values = material()
    changed = dict(values["execution_permit"])
    changed["maximum_invocations"] = 2
    identity_calls: list[None] = []
    monkeypatch.setattr(
        publisher,
        "_authorized_session_for_principal",
        lambda _principal, **_kwargs: identity_calls.append(None),
    )
    with pytest.raises(publisher.CanaryReceiptPublicationError, match="authority/permit"):
        publisher.publish_execution_receipt(
            values["execution"],
            values["predecessor"],
            changed,
            values["attestation"],
            values["execution_publication_permit"],
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    assert identity_calls == []


def test_publication_signature_tampering_fails_before_upload(monkeypatch):
    values = material()
    context = values["provisioning_context"]
    permit = dict(values["provisioning_publication_permit"])
    signature = bytearray(base64.b64decode(permit["signature_b64"]))
    signature[0] ^= 1
    permit["signature_b64"] = base64.b64encode(signature).decode("ascii")
    uploads: list[dict[str, Any]] = []
    _admit_boundary(monkeypatch, context, uploads)
    with pytest.raises(publisher.CanaryReceiptPublicationError, match="signature"):
        publisher.publish_provisioning_receipt(
            values["predecessor"],
            values["governed"],
            permit,
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    assert uploads == []


def test_governed_provisioning_signature_tampering_fails_before_upload(
    monkeypatch,
):
    governed = governed_provisioning_permit()
    signature = bytearray(base64.b64decode(governed["signature_b64"]))
    signature[0] ^= 1
    governed["signature_b64"] = base64.b64encode(signature).decode("ascii")
    receipt = provisioning_receipt(governed)
    context = publisher._provisioning_context(
        receipt,
        governed,
        release_tree_sha=TREE,
    )
    permit = publication_permit(context)
    uploads: list[dict[str, Any]] = []
    _admit_boundary(monkeypatch, context, uploads)
    with pytest.raises(publisher.CanaryReceiptPublicationError, match="signature"):
        publisher.publish_provisioning_receipt(
            receipt,
            governed,
            permit,
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    assert uploads == []


def test_execution_attestation_signature_tampering_fails_before_upload(
    monkeypatch,
):
    governed = governed_provisioning_permit()
    predecessor = provisioning_receipt(governed)
    execution_permit, attestation = execution_authority()
    signature = bytearray(base64.b64decode(attestation["signature_b64"]))
    signature[0] ^= 1
    attestation["signature_b64"] = base64.b64encode(signature).decode("ascii")
    receipt = execution_receipt(predecessor, execution_permit, attestation)
    context = publisher._execution_context(
        receipt,
        predecessor,
        execution_permit,
        attestation,
        release_tree_sha=TREE,
    )
    permit = publication_permit(context)
    uploads: list[dict[str, Any]] = []
    _admit_boundary(monkeypatch, context, uploads)
    with pytest.raises(publisher.CanaryReceiptPublicationError, match="signature"):
        publisher.publish_execution_receipt(
            receipt,
            predecessor,
            execution_permit,
            attestation,
            permit,
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    assert uploads == []


@pytest.mark.parametrize("status", [412, 500, "exception", "bad_checksum"])
def test_replay_and_indeterminate_results_are_terminal_single_attempt(
    monkeypatch, status
):
    values = material()
    context = values["provisioning_context"]
    calls: list[None] = []
    _admit_boundary(monkeypatch, context, calls)

    def outcome(**_kwargs):
        calls.append(None)
        if status == "exception":
            raise TimeoutError("response lost")
        if status == "bad_checksum":
            response = _success(context)
            response["crc32c"] = "attacker"
            return 200, response
        return status, {}

    calls.clear()
    monkeypatch.setattr(publisher, "_storage_create_only", outcome)
    error = (
        publisher.CanaryReceiptAlreadyPublished
        if status == 412
        else publisher.CanaryReceiptPublicationIndeterminate
    )
    with pytest.raises(error):
        publisher.publish_provisioning_receipt(
            values["predecessor"],
            values["governed"],
            values["provisioning_publication_permit"],
            release_tree_sha=TREE,
            authoritative_now=NOW,
        )
    assert calls == [None]


def test_storage_boundary_is_one_fixed_host_create_only_media_upload():
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    content = b'{"canonical":"receipt"}'

    class Response:
        status_code = 201

        @staticmethod
        def json():
            return {}

    class Session:
        @staticmethod
        def request(*args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    publisher._storage_create_only(
        session=Session(),
        bucket=BUCKET,
        object_name=(
            f"canary-provisioning-receipts/{RELEASE}/{PROVIDER}/"
            f"{JOB}/{'f' * 64}.json"
        ),
        content=content,
    )
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (
        "POST",
        f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o",
    )
    assert kwargs["params"]["uploadType"] == "media"
    assert kwargs["params"]["ifGenerationMatch"] == "0"
    assert kwargs["allow_redirects"] is False
    assert kwargs["headers"]["Content-MD5"] == publisher._md5_b64(content)
    assert publisher._crc32c_b64(content) in kwargs["headers"]["X-Goog-Hash"]


def test_publisher_uses_bounded_keyless_impersonation_session(
    monkeypatch,
):
    expected = f"{PREFIX}-can-pub@{PROJECT}.iam.gserviceaccount.com"
    calls = []
    monkeypatch.setattr(
        publisher,
        "bounded_impersonated_session",
        lambda **kwargs: (calls.append(kwargs) or ("bounded-session", {})),
    )
    expiry = NOW + timedelta(minutes=5)
    assert publisher._authorized_session_for_principal(
        expected,
        expected_source=PUBLICATION_SOURCE,
        authority_expires_at=expiry,
    ) == "bounded-session"
    assert calls == [{
        "expected_target": expected,
        "expected_source": PUBLICATION_SOURCE,
        "authority_expires_at": expiry,
        "error_type": publisher.CanaryReceiptPublicationError,
    }]


def test_kms_read_uses_exact_montreal_v1_host_without_redirect():
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "name": KMS_KEY_VERSION,
                "algorithm": publisher.CANARY_AUTHORITY_ALGORITHM,
                "pem": PUBLIC_KEY_PEM,
                "pemCrc32c": str(
                    publisher._crc32c(PUBLIC_KEY_PEM.encode("utf-8"))
                ),
            }

    class Session:
        @staticmethod
        def request(*args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    evidence = publisher._fetch_kms_public_key(
        session=Session(), kms_key_version=KMS_KEY_VERSION
    )
    assert evidence.public_key_sha256 == PUBLIC_KEY_SHA256
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (
        "GET",
        f"https://{REGION}-cloudkms.googleapis.com/v1/"
        f"{KMS_KEY_VERSION}/publicKey",
    )
    assert kwargs["allow_redirects"] is False


def test_cli_is_inert_without_explicit_execute(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "publish_nexus_canary_receipts.py",
            "provisioning",
            "missing-receipt.json",
            "missing-governed.json",
            "missing-publication.json",
            "--release-tree-sha",
            TREE,
        ],
    )
    with pytest.raises(
        publisher.CanaryReceiptPublicationError,
        match="never implicit",
    ):
        publisher.main()
