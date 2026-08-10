from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
import pytest

import scripts.provision_nexus_provider_canary_job as provisioner
import src.operations.nexus_provider_canary as canary_runtime
from scripts.aigc_external_release_procurement import ExternalReleaseContract
from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.domain.nexus.contracts import (
    AuthorityAttestation,
    ExecutionPermit,
    GovernanceDecision,
)
from src.operations.nexus_provider_canary import (
    KmsAuthorityPublicKey,
    ProviderCanaryPlan,
    authority_public_key_sha256,
    build_invocation,
    credential_reference_sha256,
)


REVISION = "a" * 40
STATE_HASH = "b" * 64
CHANGE_HASH = "c" * 64
REPORT_HASH = "d" * 64
NOW = datetime(2026, 8, 8, 14, 0, tzinfo=timezone.utc)
SOURCE_PRINCIPAL = "operator-test@example.com"
TEST_SESSION = object()
PROJECT = "aigc-stage"
PROJECT_NUMBER = "170151535592"
PREFIX = "aigc"
REGION = "northamerica-northeast1"
DSN_REF = (
    "projects/aigc-stage/locations/northamerica-northeast1/"
    "secrets/runtime-control-dsn/versions/7"
)
OPENAI_REF = (
    "projects/aigc-stage/locations/northamerica-northeast1/"
    "secrets/openai-api-key/versions/3"
)
IMAGE = (
    "northamerica-northeast1-docker.pkg.dev/aigc-stage/runtime/"
    "nexus@sha256:" + "1" * 64
)
KMS_KEY_VERSION = (
    "projects/aigc-stage/locations/northamerica-northeast1/keyRings/"
    "aigc-keys/cryptoKeys/aigc-canary-authority/cryptoKeyVersions/1"
)
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY_PEM = PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("utf-8")
PUBLIC_KEY_SHA256 = authority_public_key_sha256(PUBLIC_KEY_PEM)


@pytest.fixture(autouse=True)
def exact_kms_public_key(monkeypatch):
    def fetch(key_version: str) -> KmsAuthorityPublicKey:
        assert key_version == KMS_KEY_VERSION
        return KmsAuthorityPublicKey(
            kms_key_version=key_version,
            algorithm="RSA_SIGN_PSS_2048_SHA256",
            public_key_pem=PUBLIC_KEY_PEM,
            public_key_sha256=PUBLIC_KEY_SHA256,
        )

    monkeypatch.setattr(canary_runtime, "fetch_kms_authority_public_key", fetch)
    monkeypatch.setattr(provisioner, "fetch_kms_authority_public_key", fetch)
    monkeypatch.setattr(
        provisioner,
        "_trusted_broker_session",
        lambda identity: (TEST_SESSION, {
            "attached_service_account": identity,
            "attached_service_account_verified": True,
            "credential_source": "gce_metadata_server",
            "client_impersonation_used": False,
            "workload_identity_federation_used": False,
            "service_account_key_used": False,
        }),
    )
    monkeypatch.setattr(
        provisioner,
        "_verify_expiring_broker_authority",
        lambda **kwargs: {
            "broker_authority_expires_at": kwargs["permit"]["expires_at"],
            "project_binding_sha256": "1" * 64,
            "runtime_act_as_binding_sha256": "2" * 64,
            "project_wide_permanent_mutation_authority": False,
        },
    )
    monkeypatch.setattr(provisioner, "_utc_now", lambda: NOW)


def _sign(payload: dict) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).digest()
    signature = PRIVATE_KEY.sign(
        digest,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        utils.Prehashed(hashes.SHA256()),
    )
    return base64.b64encode(signature).decode("ascii")


def _material(provider_id: str = "google_vertex_gemini"):
    procurement_payload = {
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": REGION,
        "release_sha": REVISION,
        "resource_prefix": PREFIX,
        "provider_canary_spend_cad": 0.05,
        "authority": {
            "authorized_by": "operator:test",
            "gemini_canary_authorized": provider_id == "google_vertex_gemini",
            "openai_canary_authorized": provider_id == "openai_responses",
        },
    }
    procurement = ExternalReleaseContract(payload=procurement_payload)
    deployment = {
        "project_id": PROJECT,
        "region": REGION,
        "release_sha": REVISION,
        "immutable_image_uri": IMAGE,
    }
    plan = ProviderCanaryPlan(
        provider_id=provider_id,
        project_id=PROJECT,
        location=REGION,
        model=(
            "gemini-2.5-flash"
            if provider_id == "google_vertex_gemini"
            else "example-model"
        ),
        exact_revision=REVISION,
        procurement_sha256=canonical_sha256(procurement_payload),
        deployment_sha256=canonical_sha256(deployment),
        principal="operator:aigc-canary",
        change_set_id="CHG-CANARY001",
        change_set_hash=CHANGE_HASH,
        parent_state_hash=STATE_HASH,
        purpose="One governed provider canary",
        input_payload="Return exactly: AIGC CANARY OK",
        reserved_usage_units=128,
        maximum_input_units=64,
        maximum_output_units=64,
        request_timeout_seconds=30,
        maximum_cost_cad=Decimal("0.05"),
        input_cad_per_million=Decimal("1.00"),
        output_cad_per_million=Decimal("2.00"),
        pricing_evidence_sha256="9" * 64,
        runtime_control_dsn_secret_ref=DSN_REF,
        runtime_control_dsn_secret_ref_sha256=credential_reference_sha256(DSN_REF),
        openai_api_key_secret_ref=(
            OPENAI_REF if provider_id == "openai_responses" else None
        ),
        openai_api_key_secret_ref_sha256=(
            credential_reference_sha256(OPENAI_REF)
            if provider_id == "openai_responses"
            else None
        ),
    )
    invocation = build_invocation(plan)
    decision = GovernanceDecision(
        decision_id="GOV-CANARY001",
        decision="approved",
        authority_source="HUMAN",
        authority_actor="operator:test",
        artifact_state_hash=STATE_HASH,
        change_set_hash=CHANGE_HASH,
        verifier_report_hash=REPORT_HASH,
        exact_revision=REVISION,
        conditions=plan.required_governance_conditions,
        expires_at=NOW + timedelta(minutes=10),
    )
    execution_permit = ExecutionPermit(
        permit_id="PERMIT-CANARY001",
        governance_decision_id=decision.decision_id,
        principal=plan.principal,
        capability=plan.capability,
        resource_scope=(plan.resource_ref,),
        exact_revision=REVISION,
        change_set_hash=CHANGE_HASH,
        request_digest=invocation.request_digest,
        expires_at=NOW + timedelta(minutes=5),
        maximum_invocations=1,
    )
    job_name = provisioner._expected_job_name(
        prefix=PREFIX,
        provider_id=plan.provider_id,
        permit_id=execution_permit.permit_id,
    )
    provisional_attestation = AuthorityAttestation(
        attestation_id="AUTH-CANARY001",
        issuer=f"gcp-kms:{KMS_KEY_VERSION}",
        subject=decision.authority_actor,
        kms_key_version=KMS_KEY_VERSION,
        signing_algorithm="RSA_SIGN_PSS_2048_SHA256",
        public_key_sha256=PUBLIC_KEY_SHA256,
        procurement_sha256=plan.procurement_sha256,
        deployment_sha256=plan.deployment_sha256,
        plan_sha256=canonical_sha256(plan.model_dump(mode="json")),
        governance_decision_sha256=canonical_sha256(
            decision.model_dump(mode="json")
        ),
        execution_permit_sha256=canonical_sha256(
            execution_permit.model_dump(mode="json")
        ),
        request_digest=invocation.request_digest,
        permit_id=execution_permit.permit_id,
        job_name=job_name,
        execution_nonce="9" * 64,
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=15),
        signature_b64="A" * 32,
    )
    attestation = provisional_attestation.model_copy(
        update={"signature_b64": _sign(provisional_attestation.signed_payload())}
    )
    job_spec = provisioner.expected_canary_job_spec(
        project=PROJECT,
        prefix=PREFIX,
        plan=plan,
        decision=decision,
        execution_permit=execution_permit,
        attestation=attestation,
        immutable_image=IMAGE,
    )
    identities = provisioner.expected_canary_job_identities(
        prefix=PREFIX,
        project=PROJECT,
        provider_id=plan.provider_id,
    )
    provisioning_permit = {
        "schema_version": provisioner.PERMIT_SCHEMA_VERSION,
        "permit_id": "CJP-CANARY001",
        "nonce": "8" * 64,
        "repository": provisioner.REPOSITORY,
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": REGION,
        "release_sha": REVISION,
        "provider_id": plan.provider_id,
        "job_name": job_name,
        "target": job_spec["target"],
        "immutable_image_uri": IMAGE,
        "reserved_usage_units": plan.reserved_usage_units,
        "maximum_input_units": plan.maximum_input_units,
        "maximum_output_units": plan.maximum_output_units,
        "request_timeout_seconds": plan.request_timeout_seconds,
        "runtime_service_account": identities["runtime"],
        "provisioner_principal": identities["provisioner"],
        "executor_principal": identities["executor"],
        "signer_principal": identities["signer"],
        "receipt_bucket": f"{PROJECT}-{PREFIX}-receipts",
        "procurement_sha256": canonical_sha256(procurement_payload),
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
        "kms_key_version": KMS_KEY_VERSION,
        "signing_algorithm": "RSA_SIGN_PSS_2048_SHA256",
        "public_key_sha256": PUBLIC_KEY_SHA256,
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "not_before": (NOW - timedelta(seconds=30)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
    }
    provisioning_permit["signature_b64"] = _sign(provisioning_permit)
    return (
        procurement,
        deployment,
        plan,
        decision,
        execution_permit,
        attestation,
        job_spec,
        provisioning_permit,
    )


def test_openai_provisioning_target_uses_the_dedicated_openai_runtime():
    material = _material("openai_responses")
    job_spec = material[6]
    permit = provisioner.validate_provisioning_permit(
        material[7],
        procurement=material[0],
        deployment=material[1],
        plan=material[2],
        decision=material[3],
        execution_permit=material[4],
        attestation=material[5],
        job_spec=job_spec,
        authoritative_now=NOW,
    )
    assert job_spec["job_name"].startswith("aigc-openai-")
    assert job_spec["runtime_service_account"] == (
        "aigc-can-oai@aigc-stage.iam.gserviceaccount.com"
    )
    assert permit["provider_id"] == "openai_responses"


def _job_description(job_spec: dict) -> dict:
    return {
        "metadata": {
            "name": job_spec["job_name"],
            "labels": job_spec["labels"],
        },
        "template": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {
                "serviceAccount": job_spec["runtime_service_account"],
                "maxRetries": 0,
                "timeout": "180s",
                "vpcAccess": {
                    "egress": "PRIVATE_RANGES_ONLY",
                    "networkInterfaces": [
                        {
                            "network": job_spec["network"],
                            "subnetwork": job_spec["subnet"],
                        }
                    ],
                },
                "volumes": [
                    {
                        "name": "cloudsql",
                        "cloudSqlInstance": {
                            "instances": [job_spec["cloud_sql_connection"]]
                        },
                    }
                ],
                "containers": [
                    {
                        "image": job_spec["immutable_image_uri"],
                        "command": job_spec["command"],
                        "args": job_spec["args"],
                        "env": [
                            {"name": key, "value": value}
                            for key, value in job_spec[
                                "authority_environment"
                            ].items()
                        ],
                        "volumeMounts": [
                            {"name": "cloudsql", "mountPath": "/cloudsql"}
                        ],
                    }
                ],
            },
        },
    }


def test_provisioning_permit_target_substitution_stops_before_cloud_boundary(
    monkeypatch, tmp_path
):
    material = _material()
    provisioning_permit = dict(material[-1])
    provisioning_permit["immutable_image_uri"] = provisioning_permit[
        "immutable_image_uri"
    ].replace("1" * 64, "2" * 64)
    unsigned = dict(provisioning_permit)
    unsigned.pop("signature_b64")
    provisioning_permit["signature_b64"] = _sign(unsigned)
    calls: list[object] = []
    monkeypatch.setattr(
        provisioner, "_provision_job", lambda **kwargs: calls.append(kwargs)
    )
    monkeypatch.setattr(
        provisioner,
        "_authorized_storage_create_only",
        lambda **kwargs: calls.append(kwargs),
    )
    with pytest.raises(
        provisioner.CanaryJobProvisioningError,
        match="exact immutable_image_uri",
    ):
        provisioner.provision(
            procurement=material[0],
            deployment=material[1],
            plan=material[2],
            decision=material[3],
            execution_permit=material[4],
            attestation=material[5],
            provisioning_permit=provisioning_permit,
            output=tmp_path / "receipt.json",
            authoritative_now=NOW,
        )
    assert calls == []


def test_provisioner_never_overwrites_an_existing_receipt(monkeypatch, tmp_path):
    material = _material()
    output = tmp_path / "accepted-receipt.json"
    output.write_text("accepted-history\n", encoding="utf-8")
    calls: list[object] = []
    monkeypatch.setattr(
        provisioner, "_provision_job", lambda **kwargs: calls.append(kwargs)
    )
    with pytest.raises(
        provisioner.CanaryJobProvisioningError,
        match="will not be overwritten",
    ):
        provisioner.provision(
            procurement=material[0],
            deployment=material[1],
            plan=material[2],
            decision=material[3],
            execution_permit=material[4],
            attestation=material[5],
            provisioning_permit=material[7],
            output=output,
            authoritative_now=NOW,
        )
    assert calls == []
    assert output.read_text(encoding="utf-8") == "accepted-history\n"


def test_provisioner_rejects_client_identity_before_mutation(
    monkeypatch, tmp_path
):
    material = _material()
    calls: list[object] = []

    def reject_broker(_identity):
        raise provisioner.CanaryJobProvisioningError(
            "BLOCKED_PENDING_TRUSTED_BROKER"
        )

    monkeypatch.setattr(provisioner, "_trusted_broker_session", reject_broker)
    with pytest.raises(
        provisioner.CanaryJobProvisioningError,
        match="BLOCKED_PENDING_TRUSTED_BROKER",
    ):
        provisioner.provision(
            procurement=material[0],
            deployment=material[1],
            plan=material[2],
            decision=material[3],
            execution_permit=material[4],
            attestation=material[5],
            provisioning_permit=material[7],
            output=tmp_path / "receipt.json",
            authoritative_now=NOW,
        )
    assert calls == []


def test_provisioner_rejects_any_job_execution_authority(monkeypatch):
    material = _material()
    job_spec = material[6]

    def fake_permissions(*, url, permissions, expected_principal):
        assert expected_principal == job_spec["provisioner_principal"]
        if "run.googleapis.com" in url:
            granted = [
                "run.jobs.create",
                "run.jobs.update",
                "run.jobs.get",
                "run.jobs.run",
            ]
        elif "iam.googleapis.com" in url:
            granted = ["iam.serviceAccounts.actAs"]
        else:
            granted = ["storage.objects.create"]
        return 200, {"permissions": granted}

    monkeypatch.setattr(
        provisioner, "_authorized_test_permissions", fake_permissions
    )
    with pytest.raises(
        provisioner.CanaryJobProvisioningError,
        match="prohibited job execution",
    ):
        provisioner._preflight_provisioner_permissions(
            project=PROJECT,
            job_name=job_spec["job_name"],
            runtime_service_account=job_spec["runtime_service_account"],
            receipt_bucket=f"{PROJECT}-{PREFIX}-receipts",
            provisioner_principal=job_spec["provisioner_principal"],
        )


def test_consumption_replay_stops_before_job_mutation(monkeypatch, tmp_path):
    material = _material()
    job_spec = material[6]
    events: list[str] = []
    monkeypatch.setattr(
        provisioner,
        "_preflight_provisioner_permissions",
        lambda **_kwargs: {"job_execution_authority_absent": True},
    )
    monkeypatch.setattr(
        provisioner,
        "_authorized_storage_create_only",
        lambda **_kwargs: (events.append("consume") or (412, {})),
    )
    monkeypatch.setattr(
        provisioner,
        "_provision_job",
        lambda **_kwargs: pytest.fail("job mutation must not be attempted"),
    )
    with pytest.raises(
        provisioner.CanaryJobProvisioningPermitConsumed,
        match="already consumed",
    ):
        provisioner.provision(
            procurement=material[0],
            deployment=material[1],
            plan=material[2],
            decision=material[3],
            execution_permit=material[4],
            attestation=material[5],
            provisioning_permit=material[7],
            output=tmp_path / "receipt.json",
            authoritative_now=NOW,
        )
    assert events == ["consume"]
    assert job_spec["executor_principal"] != job_spec["provisioner_principal"]


def test_legitimate_provisioning_burns_one_use_permit_before_exact_job_mutation(
    monkeypatch, tmp_path
):
    material = _material()
    job_spec = material[6]
    events: list[str] = []

    def fake_permissions(**_kwargs):
        events.append("permissions")
        return {"job_execution_authority_absent": True}

    def fake_storage(*, bucket, object_name, content, expected_principal, session):
        events.append("consume")
        assert session is TEST_SESSION
        assert bucket == f"{PROJECT}-{PREFIX}-receipts"
        assert expected_principal == job_spec["provisioner_principal"]
        assert json.loads(content)["state"] == "consumed_before_dispatch"
        return 200, {"bucket": bucket, "name": object_name, "generation": "7"}

    def fake_provision(*, session, project, job_spec):
        events.append("deploy")
        assert session is TEST_SESSION
        payload = provisioner._cloud_run_job_payload(job_spec)
        assert payload["template"]["template"]["containers"][0]["env"]

    def fake_describe(**_kwargs):
        events.append("describe")
        return _job_description(job_spec)

    monkeypatch.setattr(
        provisioner, "_preflight_provisioner_permissions", fake_permissions
    )
    monkeypatch.setattr(
        provisioner, "_authorized_storage_create_only", fake_storage
    )
    monkeypatch.setattr(provisioner, "_provision_job", fake_provision)
    monkeypatch.setattr(provisioner, "_describe_provisioned_job", fake_describe)
    output = tmp_path / "provisioning-receipt.json"
    receipt = provisioner.provision(
        procurement=material[0],
        deployment=material[1],
        plan=material[2],
        decision=material[3],
        execution_permit=material[4],
        attestation=material[5],
        provisioning_permit=material[7],
        output=output,
        authoritative_now=NOW,
    )

    assert events == ["permissions", "consume", "deploy", "describe"]
    assert "gcloud" not in Path(provisioner.__file__).read_text(encoding="utf-8")
    assert receipt["cloud_run_mutation_count"] == 1
    assert receipt["reserved_usage_units"] == 128
    assert receipt["maximum_input_units"] == 64
    assert receipt["maximum_output_units"] == 64
    assert receipt["request_timeout_seconds"] == 30
    assert receipt["job_deployment_performed"] is True
    assert receipt["job_execution_performed"] is False
    assert receipt["provider_call_performed"] is False
    assert receipt["permission_evidence"]["job_execution_authority_absent"] is True
    assert receipt["identity_evidence"][
        "attached_service_account_verified"
    ] is True
    assert receipt["identity_evidence"][
        "client_impersonation_used"
    ] is False
    assert receipt["permit_consumption_generation"] == "7"
    assert receipt["provisioner_principal"] != receipt["executor_principal"]
    assert output.is_file()


def test_post_mutation_authority_environment_substitution_is_indeterminate(
    monkeypatch, tmp_path
):
    material = _material()
    job_spec = material[6]
    described = _job_description(job_spec)
    described["template"]["template"]["containers"][0]["env"][0][
        "value"
    ] = "attacker"
    events: list[str] = []

    monkeypatch.setattr(
        provisioner,
        "_preflight_provisioner_permissions",
        lambda **_kwargs: {"job_execution_authority_absent": True},
    )

    def fake_storage(*, bucket, object_name, **_kwargs):
        events.append("consume")
        return 200, {"bucket": bucket, "name": object_name, "generation": "8"}

    def fake_provision(**_kwargs):
        events.append("deploy")

    def fake_describe(**_kwargs):
        events.append("describe")
        return described

    monkeypatch.setattr(
        provisioner, "_authorized_storage_create_only", fake_storage
    )
    monkeypatch.setattr(provisioner, "_provision_job", fake_provision)
    monkeypatch.setattr(provisioner, "_describe_provisioned_job", fake_describe)
    output = tmp_path / "receipt.json"
    with pytest.raises(
        provisioner.CanaryJobProvisioningIndeterminate,
        match="exact target readback failed",
    ):
        provisioner.provision(
            procurement=material[0],
            deployment=material[1],
            plan=material[2],
            decision=material[3],
            execution_permit=material[4],
            attestation=material[5],
            provisioning_permit=material[7],
            output=output,
            authoritative_now=NOW,
        )
    assert events == ["consume", "deploy", "describe"]
    assert not output.exists()
