from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
import pytest
import scripts.launch_nexus_provider_canary_job as launcher
import src.operations.nexus_provider_canary as canary_runtime
from scripts.aigc_external_release_procurement import ExternalReleaseContract
from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.core.nexus.provider_runtime import NexusProviderRuntime
from src.domain.nexus.autonomy import ConsequenceAssessment
from src.domain.nexus.contracts import (
    AuthorityAttestation,
    ExecutionPermit,
    GovernanceDecision,
)
from src.operations.nexus_provider_canary import (
    CanaryConfigurationError,
    KmsAuthorityPublicKey,
    ProviderCanaryPlan,
    _validate_authority,
    authority_public_key_sha256,
    build_invocation,
    canary_execution_receipt,
    credential_reference_sha256,
    execute_canary,
    expected_canary_authority_key_version,
    plan_receipt,
)
from src.domain.nexus.provider_runtime import (
    ProviderAttemptResult,
    ProviderRuntimeAudit,
    ProviderRuntimeExecution,
)


REVISION = "a" * 40
STATE_HASH = "b" * 64
CHANGE_HASH = "c" * 64
REPORT_HASH = "d" * 64
DSN_REF = "projects/aigc-stage/locations/northamerica-northeast1/secrets/runtime-control-dsn/versions/7"
OPENAI_REF = "projects/aigc-stage/locations/northamerica-northeast1/secrets/openai-api-key/versions/3"
NOW = datetime(2026, 8, 8, 14, 0, tzinfo=timezone.utc)
SOURCE_PRINCIPAL = "aigc-can-bind@aigc-stage.iam.gserviceaccount.com"
TEST_SESSION = object()
JOB_NAME = launcher._expected_job_name(
    prefix="aigc",
    provider_id="google_vertex_gemini",
    permit_id="PERMIT-CANARY001",
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
REAL_KMS_PUBLIC_KEY_FETCH = canary_runtime.fetch_kms_authority_public_key


class _RestResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class _RestSession:
    def __init__(self, payload):
        self.payload = payload

    def get(self, *_args, **_kwargs):
        return _RestResponse(self.payload)

    def post(self, *_args, **_kwargs):
        return _RestResponse(self.payload)


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

    monkeypatch.setattr(
        "src.operations.nexus_provider_canary.fetch_kms_authority_public_key",
        fetch,
    )
    monkeypatch.setattr(launcher, "fetch_kms_authority_public_key", fetch)
    monkeypatch.setattr(
        launcher,
        "bounded_impersonated_session",
        lambda **kwargs: (TEST_SESSION, {
            "adc_impersonation_target": kwargs["expected_target"],
            "adc_impersonation_target_verified": True,
            "adc_source_principal": SOURCE_PRINCIPAL,
            "adc_source_credential_type": "test.SourceCredentials",
            "adc_source_keyless_verified": True,
            "bounded_token_lifetime_seconds": 120,
            "bounded_token_expires_at": (NOW + timedelta(minutes=2)).isoformat(),
            "service_account_key_used": False,
        }),
    )
    monkeypatch.setattr(launcher, "_utc_now", lambda: NOW)
    monkeypatch.setattr(
        launcher, "_validate_binding_consumption", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        launcher,
        "_job_iam_policy",
        lambda **_kwargs: {
            "bindings": _execution_policy_bindings(plan(), authority(plan())[2])
        },
    )


def plan(provider: str = "google_vertex_gemini") -> ProviderCanaryPlan:
    return ProviderCanaryPlan(
        provider_id=provider,
        project_id="aigc-stage",
        location="northamerica-northeast1",
        model=(
            "gemini-2.5-flash"
            if provider == "google_vertex_gemini"
            else "example-model"
        ),
        exact_revision=REVISION,
        procurement_sha256="e" * 64,
        deployment_sha256="f" * 64,
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
        openai_api_key_secret_ref=OPENAI_REF if provider == "openai_responses" else None,
        openai_api_key_secret_ref_sha256=(
            credential_reference_sha256(OPENAI_REF)
            if provider == "openai_responses"
            else None
        ),
    )


def authority(plan_value: ProviderCanaryPlan):
    invocation = build_invocation(plan_value)
    decision = GovernanceDecision(
        decision_id="GOV-CANARY001",
        decision="approved",
        authority_source="HUMAN",
        authority_actor="operator:test",
        artifact_state_hash=STATE_HASH,
        change_set_hash=CHANGE_HASH,
        verifier_report_hash=REPORT_HASH,
        exact_revision=REVISION,
        conditions=plan_value.required_governance_conditions,
        expires_at=NOW + timedelta(minutes=10),
    )
    permit = ExecutionPermit(
        permit_id="PERMIT-CANARY001",
        governance_decision_id=decision.decision_id,
        principal=plan_value.principal,
        capability=plan_value.capability,
        resource_scope=(plan_value.resource_ref,),
        exact_revision=REVISION,
        change_set_hash=CHANGE_HASH,
        request_digest=invocation.request_digest,
        expires_at=NOW + timedelta(minutes=5),
        maximum_invocations=1,
    )
    provisional = AuthorityAttestation(
        attestation_id="AUTH-CANARY001",
        issuer=f"gcp-kms:{KMS_KEY_VERSION}",
        subject=decision.authority_actor,
        kms_key_version=KMS_KEY_VERSION,
        signing_algorithm="RSA_SIGN_PSS_2048_SHA256",
        public_key_sha256=PUBLIC_KEY_SHA256,
        procurement_sha256=plan_value.procurement_sha256,
        deployment_sha256=plan_value.deployment_sha256,
        plan_sha256=canonical_sha256(plan_value.model_dump(mode="json")),
        governance_decision_sha256=canonical_sha256(decision.model_dump(mode="json")),
        execution_permit_sha256=canonical_sha256(permit.model_dump(mode="json")),
        request_digest=invocation.request_digest,
        permit_id=permit.permit_id,
        job_name=JOB_NAME,
        execution_nonce="9" * 64,
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=15),
        signature_b64="A" * 32,
    )
    digest = hashlib.sha256(canonical_json_bytes(provisional.signed_payload())).digest()
    signature = PRIVATE_KEY.sign(
        digest,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        utils.Prehashed(hashes.SHA256()),
    )
    attestation = provisional.model_copy(
        update={"signature_b64": base64.b64encode(signature).decode("ascii")}
    )
    return invocation, decision, permit, attestation


def validate_authority(
    plan_value: ProviderCanaryPlan,
    invocation,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
) -> None:
    _validate_authority(
        plan_value,
        invocation,
        decision,
        permit,
        attestation,
        expected_kms_key_version=KMS_KEY_VERSION,
        authoritative_now=NOW,
        expected_job_name=JOB_NAME,
    )


def test_canary_plan_is_deterministic_and_performs_no_provider_work():
    first = plan_receipt(plan())
    second = plan_receipt(plan())
    assert first == second
    assert first["provider_call_performed"] is False
    assert first["network_call_performed"] is False
    assert first["credential_used"] is False
    assert first["required_maximum_invocations"] == 1
    assert first["required_governance_conditions"] == (
        "MAX_COST_CAD=0.05",
        "WORST_CASE_TOKEN_COST_CAD=0.000192",
        "INPUT_CAD_PER_MILLION=1.00",
        "OUTPUT_CAD_PER_MILLION=2.00",
        "PRICING_EVIDENCE_SHA256=" + "9" * 64,
        "MAX_INPUT_UNITS=64",
        "MAX_OUTPUT_UNITS=64",
        "REQUEST_TIMEOUT_SECONDS=30",
        "PROJECT_ID=aigc-stage",
        "EXECUTION_REGION=northamerica-northeast1",
        "PROVIDER_LOCATION=northamerica-northeast1",
        "MODEL=gemini-2.5-flash",
        "THINKING_DISABLED_REQUIRED=true",
        "THINKING_BUDGET=0",
    )
    assert first["project_id"] == "aigc-stage"
    assert first["reserved_usage_units"] == 128
    assert first["maximum_input_units"] == 64
    assert first["maximum_output_units"] == 64
    assert first["request_timeout_seconds"] == 30
    assert first["runtime_control_dsn_secret_ref_sha256"] == credential_reference_sha256(
        DSN_REF
    )
    assert first["detached_authority_attestation_required"] is True
    assert first["resource_ref"].endswith(first["resource_binding_sha256"])


def test_openai_plan_records_provider_managed_location_without_claiming_montreal():
    receipt = plan_receipt(plan("openai_responses"))
    assert receipt["execution_region"] == "northamerica-northeast1"
    assert receipt["provider_location"] == "provider-managed"
    assert "PROVIDER_LOCATION=provider-managed" in receipt["required_governance_conditions"]


def test_gemini_plan_rejects_models_without_hard_thinking_disable():
    with pytest.raises(ValueError, match="thinking-disabled model"):
        ProviderCanaryPlan(**{**plan().model_dump(), "model": "gemini-2.5-pro"})


def test_canary_plan_rejects_unpartitioned_or_undersized_usage_authority():
    with pytest.raises(ValueError, match="exceed reserved usage"):
        ProviderCanaryPlan(
            **{
                **plan().model_dump(),
                "maximum_input_units": 65,
                "maximum_output_units": 64,
            }
        )


@pytest.mark.parametrize("field", ["input_cad_per_million", "output_cad_per_million"])
def test_canary_plan_rejects_zero_pricing_authority(field):
    with pytest.raises(ValueError, match="greater than 0"):
        ProviderCanaryPlan(
            **{
                **plan().model_dump(),
                field: Decimal("0.00"),
            }
        )


def test_canary_plan_rejects_worst_case_token_cost_above_signed_ceiling():
    with pytest.raises(ValueError, match="worst-case signed token cost"):
        ProviderCanaryPlan(
            **{
                **plan().model_dump(),
                "maximum_cost_cad": Decimal("0.000001"),
                "input_cad_per_million": Decimal("10000.00"),
                "output_cad_per_million": Decimal("10000.00"),
            }
        )


def test_canary_invocation_digest_binds_input_output_and_timeout_limits():
    baseline = build_invocation(plan())
    changed_plan = ProviderCanaryPlan(
        **{
            **plan().model_dump(),
            "maximum_input_units": 65,
            "maximum_output_units": 63,
            "request_timeout_seconds": 29,
        }
    )
    changed = build_invocation(changed_plan)
    assert baseline.maximum_input_units == 64
    assert baseline.maximum_output_units == 64
    assert baseline.request_timeout_seconds == 30
    assert baseline.request_digest != changed.request_digest
    with pytest.raises(ValueError, match="conservative maximum input"):
        ProviderCanaryPlan(
            **{
                **plan().model_dump(),
                "maximum_input_units": 61,
                "maximum_output_units": 64,
            }
        )


def test_canary_authority_trust_root_is_deterministic_and_montreal():
    assert expected_canary_authority_key_version(
        project_id="aigc-stage",
        resource_prefix="aigc",
    ) == KMS_KEY_VERSION
    with pytest.raises(CanaryConfigurationError, match="resource prefix"):
        expected_canary_authority_key_version(
            project_id="aigc-stage",
            resource_prefix="../../attacker",
        )


def test_canary_job_name_binds_the_complete_execution_permit_id():
    first = launcher._expected_job_name(
        prefix="aigc",
        provider_id="google_vertex_gemini",
        permit_id="PERMIT-FIRST-COLLIDE001",
    )
    second = launcher._expected_job_name(
        prefix="aigc",
        provider_id="google_vertex_gemini",
        permit_id="PERMIT-SECOND-COLLIDE001",
    )
    assert first != second
    assert first.startswith("aigc-gemini-")


def test_kms_public_key_fetch_verifies_response_identity_algorithm_and_crc(monkeypatch):
    class Response:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    valid = {
        "name": KMS_KEY_VERSION,
        "algorithm": "RSA_SIGN_PSS_2048_SHA256",
        "pem": PUBLIC_KEY_PEM,
        "pemCrc32c": str(canary_runtime._crc32c(PUBLIC_KEY_PEM.encode("utf-8"))),
    }
    monkeypatch.setattr(
        canary_runtime,
        "_authorized_kms_public_key_response",
        lambda _name: Response(valid),
    )
    observed = REAL_KMS_PUBLIC_KEY_FETCH(KMS_KEY_VERSION)
    assert observed.kms_key_version == KMS_KEY_VERSION
    assert observed.public_key_sha256 == PUBLIC_KEY_SHA256

    for changed, message in (
        ({**valid, "name": KMS_KEY_VERSION.replace("/1", "/2")}, "identity mismatch"),
        ({**valid, "algorithm": "RSA_SIGN_PKCS1_2048_SHA256"}, "algorithm"),
        ({**valid, "pemCrc32c": "0"}, "CRC32C"),
    ):
        monkeypatch.setattr(
            canary_runtime,
            "_authorized_kms_public_key_response",
            lambda _name, payload=changed: Response(payload),
        )
        with pytest.raises(CanaryConfigurationError, match=message):
            REAL_KMS_PUBLIC_KEY_FETCH(KMS_KEY_VERSION)


def test_canary_rejects_cross_project_regional_secret_reference():
    foreign = DSN_REF.replace("projects/aigc-stage/", "projects/foreign-stage/")
    with pytest.raises(ValueError, match="project mismatch"):
        ProviderCanaryPlan(
            **{
                **plan().model_dump(),
                "runtime_control_dsn_secret_ref": foreign,
                "runtime_control_dsn_secret_ref_sha256": credential_reference_sha256(foreign),
            }
        )


def test_canary_requires_exact_regional_secret_versions():
    with pytest.raises(ValueError):
        ProviderCanaryPlan(
            **{
                **plan().model_dump(),
                "runtime_control_dsn_secret_ref": "projects/aigc-stage/secrets/runtime/versions/latest",
            }
        )


def test_openai_plan_requires_separate_exact_api_key_reference():
    with pytest.raises(ValueError, match="OpenAI canary requires"):
        ProviderCanaryPlan(**{**plan("openai_responses").model_dump(), "openai_api_key_secret_ref": None})


def test_canonical_human_decision_and_one_use_permit_bind_canary():
    p = plan()
    invocation, decision, permit, attestation = authority(p)
    validate_authority(p, invocation, decision, permit, attestation)


def test_wrong_cost_condition_is_rejected_before_provider_execution():
    p = plan()
    invocation, decision, permit, attestation = authority(p)
    wrong = decision.model_copy(update={"conditions": ("MAX_COST_CAD=0.10",)})
    with pytest.raises(CanaryConfigurationError, match="governance_decision_sha256"):
        validate_authority(p, invocation, wrong, permit, attestation)


def test_reusable_permit_is_rejected_for_first_live_canary():
    p = plan()
    invocation, decision, permit, attestation = authority(p)
    reusable = permit.model_copy(update={"maximum_invocations": 2})
    with pytest.raises(CanaryConfigurationError, match="execution_permit_sha256"):
        validate_authority(p, invocation, decision, reusable, attestation)


def test_caller_created_human_json_and_self_signed_key_cannot_authorize():
    p = plan()
    invocation, decision, permit, attestation = authority(p)
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attacker_pem = attacker_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    attacker_attestation = attestation.model_copy(
        update={"public_key_sha256": authority_public_key_sha256(attacker_pem)}
    )
    digest = hashlib.sha256(
        canonical_json_bytes(attacker_attestation.signed_payload())
    ).digest()
    attacker_attestation = attacker_attestation.model_copy(
        update={
            "signature_b64": base64.b64encode(
                attacker_key.sign(
                    digest,
                    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                    utils.Prehashed(hashes.SHA256()),
                )
            ).decode("ascii")
        }
    )
    with pytest.raises(CanaryConfigurationError, match="public-key digest mismatch"):
        _validate_authority(
            p,
            invocation,
            decision,
            permit,
            attacker_attestation,
            expected_kms_key_version=KMS_KEY_VERSION,
            authoritative_now=NOW,
            expected_job_name=JOB_NAME,
        )


def test_attestation_bit_flip_and_job_substitution_fail_closed():
    p = plan()
    invocation, decision, permit, attestation = authority(p)
    tampered = attestation.model_copy(update={"deployment_sha256": "0" * 64})
    with pytest.raises(CanaryConfigurationError, match="signature verification"):
        validate_authority(p, invocation, decision, permit, tampered)
    with pytest.raises(CanaryConfigurationError, match="job binding"):
        _validate_authority(
            p,
            invocation,
            decision,
            permit,
            attestation,
            expected_kms_key_version=KMS_KEY_VERSION,
            authoritative_now=NOW,
            expected_job_name="different-gemini-canary001",
        )


def test_attestation_cannot_select_an_alternate_same_project_kms_key():
    p = plan()
    invocation, decision, permit, attestation = authority(p)
    attacker_key_version = KMS_KEY_VERSION.replace(
        "/cryptoKeys/aigc-canary-authority/",
        "/cryptoKeys/attacker-authority/",
    )
    substituted = attestation.model_copy(
        update={
            "issuer": f"gcp-kms:{attacker_key_version}",
            "kms_key_version": attacker_key_version,
        }
    )
    with pytest.raises(CanaryConfigurationError, match="deterministic KMS trust root"):
        _validate_authority(
            p,
            invocation,
            decision,
            permit,
            substituted,
            expected_kms_key_version=KMS_KEY_VERSION,
            authoritative_now=NOW,
            expected_job_name=JOB_NAME,
        )


def test_plan_rejects_credential_reference_digest_substitution():
    with pytest.raises(ValueError, match="credential-reference digest mismatch"):
        ProviderCanaryPlan(
            **{
                **plan().model_dump(),
                "runtime_control_dsn_secret_ref_sha256": "0" * 64,
            }
        )


def launch_material():
    procurement_payload = {
        "project_id": "aigc-stage",
        "region": "northamerica-northeast1",
        "release_sha": REVISION,
        "resource_prefix": "aigc",
        "provider_canary_spend_cad": 0.05,
        "authority": {
            "authorized_by": "operator:test",
            "gemini_canary_authorized": True,
            "openai_canary_authorized": False,
        },
    }
    procurement = ExternalReleaseContract(payload=procurement_payload)
    deployment = {
        "project_id": "aigc-stage",
        "region": "northamerica-northeast1",
        "release_sha": REVISION,
        "immutable_image_uri": (
            "northamerica-northeast1-docker.pkg.dev/aigc-stage/runtime/nexus@sha256:"
            + "1" * 64
        ),
    }
    p = ProviderCanaryPlan(
        **{
            **plan().model_dump(),
            "procurement_sha256": canonical_sha256(procurement_payload),
            "deployment_sha256": canonical_sha256(deployment),
        }
    )
    invocation, decision, permit, attestation = authority(p)
    expected_job = launcher._expected_job_name(
        prefix="aigc",
        provider_id=p.provider_id,
        permit_id=permit.permit_id,
    )
    if expected_job != JOB_NAME:
        provisional = attestation.model_copy(update={"job_name": expected_job})
        digest = hashlib.sha256(canonical_json_bytes(provisional.signed_payload())).digest()
        attestation = provisional.model_copy(
            update={
                "signature_b64": base64.b64encode(
                    PRIVATE_KEY.sign(
                        digest,
                        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                        utils.Prehashed(hashes.SHA256()),
                    )
                ).decode("ascii")
            }
        )
    return (
        procurement,
        deployment,
        p,
        build_invocation(p, permit_id=permit.permit_id),
        decision,
        permit,
        attestation,
    )


def _sign_dict(payload: dict) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).digest()
    return base64.b64encode(
        PRIVATE_KEY.sign(
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    ).decode("ascii")


def execution_boundary(
    p: ProviderCanaryPlan, permit: ExecutionPermit
) -> tuple[dict, dict, dict]:
    project = p.project_id
    executor = f"aigc-can-exec@{project}.iam.gserviceaccount.com"
    binder = f"aigc-can-bind@{project}.iam.gserviceaccount.com"
    job = launcher._expected_job_name(
        prefix="aigc", provider_id=p.provider_id, permit_id=permit.permit_id
    )
    target = f"projects/{project}/locations/{p.location}/jobs/{job}"
    binder_expires = NOW.isoformat()
    binding_expires = (NOW + timedelta(minutes=4)).isoformat()
    condition_title = "aigc_canary_cjb_canary001"
    condition_expression = (
        'request.time < timestamp("'
        + (NOW + timedelta(minutes=4)).isoformat().replace("+00:00", "Z")
        + '")'
    )
    binding_permit = {
        "schema_version": "aigc.nexus-canary-job-execution-binding-permit.v1",
        "permit_id": "CJB-CANARY001",
        "nonce": "7" * 64,
        "repository": "Lornt1666/AIGC",
        "project_id": project,
        "project_number": "170151535592",
        "region": p.location,
        "release_sha": p.exact_revision,
        "provider_id": p.provider_id,
        "job_name": job,
        "target": target,
        "binder_principal": binder,
        "executor_principal": executor,
        "receipt_bucket": f"{project}-aigc-receipts",
        "provisioning_receipt_sha256": "6" * 64,
        "role": "roles/run.invoker",
        "member": f"serviceAccount:{executor}",
        "condition_title": condition_title,
        "condition_expression": condition_expression,
        "maximum_mutations": 1,
        "automatic_retry": False,
        "consumption_mode": "gcs_if_generation_match_zero",
        "project_wide_binding": False,
        "run_with_overrides_authorized": False,
        "kms_key_version": KMS_KEY_VERSION,
        "signing_algorithm": "RSA_SIGN_PSS_2048_SHA256",
        "public_key_sha256": PUBLIC_KEY_SHA256,
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "not_before": (NOW - timedelta(seconds=30)).isoformat(),
        "expires_at": binder_expires,
        "binding_expires_at": binding_expires,
    }
    binding_permit["signature_b64"] = _sign_dict(binding_permit)
    binding = {
        "role": "roles/run.invoker",
        "members": [f"serviceAccount:{executor}"],
        "condition": {
            "title": condition_title,
            "description": "One governed execution under CJB-CANARY001",
            "expression": condition_expression,
        },
    }
    consumption = {
        "schema_version": "aigc.nexus-canary-job-execution-binding-consumption.v1",
        "permit_id": binding_permit["permit_id"],
        "permit_sha256": canonical_sha256(binding_permit),
        "target": target,
        "member": f"serviceAccount:{executor}",
        "state": "consumed_before_dispatch",
        "maximum_mutations": 1,
        "automatic_retry": False,
    }
    binding_receipt = {
        "schema_version": "aigc.nexus-canary-job-execution-binding-receipt.v1",
        "project_id": project,
        "project_number": "170151535592",
        "region": p.location,
        "release_sha": p.exact_revision,
        "provider_id": p.provider_id,
        "job_name": job,
        "target": target,
        "binder_principal": binder,
        "executor_principal": executor,
        "provisioning_receipt_sha256": "6" * 64,
        "binding_permit_id": binding_permit["permit_id"],
        "binding_permit_sha256": canonical_sha256(binding_permit),
        "identity_evidence": {
            "attached_service_account": binder,
            "attached_service_account_verified": True,
            "credential_source": "gce_metadata_server",
            "client_impersonation_used": False,
            "workload_identity_federation_used": False,
            "account_level_impersonation_grant_claimed": False,
            "service_account_key_used": False,
        },
        "provisioner_quiescence_evidence": {
            "provisioner_jit_expired_at": (NOW - timedelta(minutes=1)).isoformat(),
            "provisioner_token_expired_at": (NOW - timedelta(minutes=1)).isoformat(),
        },
        "permission_evidence": {
            "permissions": [
                "run.jobs.get",
                "run.jobs.getIamPolicy",
                "run.jobs.setIamPolicy",
            ]
        },
        "binding": binding,
        "policy_before_sha256": "4" * 64,
        "policy_after_sha256": "5" * 64,
        "permit_consumption_uri": (
            f"gs://{project}-aigc-receipts/canary-job-execution-bindings/"
            f"{p.exact_revision}/{binding_permit['permit_id']}.json"
        ),
        "permit_consumption_generation": "7",
        "permit_consumption_record_sha256": canonical_sha256(consumption),
        "permit_consumption_readback_verified": True,
        "iam_mutation_count": 1,
        "project_wide_binding": False,
        "run_with_overrides_authorized": False,
        "automatic_retry": False,
        "binder_authority_expires_at": binder_expires,
        "binding_expires_at": binding_expires,
        "captured_at": (NOW - timedelta(seconds=1)).isoformat(),
    }
    binding_receipt["receipt_sha256"] = canonical_sha256(binding_receipt)
    jit = {
        "schema_version": "aigc.nexus-canary-jit-impersonation-receipt.v1",
        "receipt_id": "JIT-EXECUTOR001",
        "action": "execute_job",
        "project_id": project,
        "region": p.location,
        "source_principal": SOURCE_PRINCIPAL,
        "target_principal": executor,
        "target_service_account_resource": f"projects/-/serviceAccounts/{executor}",
        "target_resource": target,
        "governed_permit_id": permit.permit_id,
        "request_sha256": launcher.jit_request_sha256(
            action="execute_job", project_id=project,
            target_principal=executor, target_resource=target,
            governed_permit_id=permit.permit_id,
        ),
        "role": "roles/iam.serviceAccountTokenCreator",
        "grant_scope": "exact_target_service_account",
        "grant_observed": True,
        "source_authority_verified": True,
        "account_level_grant": False,
        "service_account_key_used": False,
        "workload_identity_federation_used": False,
        "revocation_required": True,
        "revoked_at": None,
        "kms_key_version": KMS_KEY_VERSION,
        "signing_algorithm": "RSA_SIGN_PSS_2048_SHA256",
        "public_key_sha256": PUBLIC_KEY_SHA256,
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "not_before": (NOW - timedelta(seconds=30)).isoformat(),
        "expires_at": binding_expires,
    }
    jit["grant_condition_expression"] = (
        'request.time < timestamp("'
        + (NOW + timedelta(minutes=4)).isoformat().replace("+00:00", "Z")
        + '")'
    )
    jit["signature_b64"] = _sign_dict(jit)
    return binding_receipt, binding_permit, jit


def execution_boundary_kwargs(p: ProviderCanaryPlan, permit: ExecutionPermit) -> dict:
    receipt, binding_permit, jit = execution_boundary(p, permit)
    return {
        "execution_binding_receipt": receipt,
        "execution_binding_permit": binding_permit,
        "jit_impersonation_receipt": jit,
    }


def _execution_policy_bindings(
    p: ProviderCanaryPlan, permit: ExecutionPermit
) -> list[dict]:
    receipt, binding_permit, _jit = execution_boundary(p, permit)
    binder = binding_permit["binder_principal"]
    suffix = "cjb_canary001"
    binder_expiry = binding_permit["expires_at"].replace("+00:00", "Z")
    return [
        receipt["binding"],
        {
            "role": f"projects/{p.project_id}/roles/aigc_canary_job_iam_binder",
            "members": [f"serviceAccount:{binder}"],
            "condition": {
                "title": f"aigc_binder_{suffix}",
                "description": "One trusted-broker exact-job IAM mutation",
                "expression": f'request.time < timestamp("{binder_expiry}")',
            },
        },
    ]


def successful_runtime_receipt(
    p: ProviderCanaryPlan,
    invocation,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    *,
    job_name: str,
    execution_name: str,
) -> dict:
    attempt = ProviderAttemptResult(
        invocation_id=invocation.invocation_id,
        provider_id=p.provider_id,
        status="succeeded",
        provider_request_id="provider-request-1",
        model_or_resource=p.model,
        latency_ms=25,
        usage_units=16,
        input_usage_units=8,
        output_usage_units=8,
        cost_cad=Decimal("0.01"),
        finish_status="STOP",
        response_digest="8" * 64,
        response_payload=None,
        external_action_performed=True,
        outcome_known=True,
    )
    result = ProviderRuntimeExecution(
        invocation_id=invocation.invocation_id,
        consequence_assessment=ConsequenceAssessment(
            assessment_id="AUTO-CANARY001",
            intent_id="ACT-CANARY001",
            consequence_class="EXTERNAL_READ",
            material_consequence=True,
            authority_requirement="EXISTING_EXPLICIT",
            disposition="AUTONOMOUS_WITHIN_EXISTING_AUTHORITY",
            execution_may_continue_without_new_authority=True,
        ),
        attempt=attempt,
        receipt=NexusProviderRuntime._receipt(invocation, attempt),
        audit=ProviderRuntimeAudit(
            adapter_invocations=1,
            provider_api_calls_performed=1,
            network_calls_performed=1,
            credentials_used=1,
            external_actions_performed=1,
            spend_cad=Decimal("0.01"),
        ),
    )
    return canary_execution_receipt(
        p,
        invocation=invocation,
        permit=permit,
        attestation=attestation,
        result=result,
        job_name=job_name,
        execution_name=execution_name,
        captured_at=NOW,
    )


def test_launcher_rejects_invalid_attestation_before_any_gcloud_call(monkeypatch, tmp_path):
    procurement, deployment, p, _invocation, decision, permit, attestation = launch_material()
    signature = bytearray(base64.b64decode(attestation.signature_b64))
    signature[0] ^= 1
    tampered = attestation.model_copy(
        update={"signature_b64": base64.b64encode(bytes(signature)).decode("ascii")}
    )
    calls = []
    monkeypatch.setattr(launcher, "_run", lambda *args, **kwargs: calls.append((args, kwargs)))
    with pytest.raises(launcher.CanaryLaunchError, match="signature verification"):
        launcher.launch(
            procurement=procurement,
            deployment=deployment,
            plan=p,
            decision=decision,
                permit=permit,
                attestation=tampered,
                **execution_boundary_kwargs(p, permit),
            output=tmp_path / "receipt.json",
            authoritative_now=NOW,
        )
    assert calls == []


def test_launcher_requires_separately_admitted_dormant_job_before_execution(
    monkeypatch,
    tmp_path,
):
    procurement, deployment, p, _invocation, decision, permit, attestation = launch_material()
    calls = []
    def reject_job(**_kwargs):
        calls.append("readback")
        raise launcher.CanaryLaunchError("preprovisioned Cloud Run job image/service-account mismatch")
    monkeypatch.setattr(launcher, "_job_target", reject_job)
    with pytest.raises(launcher.CanaryLaunchError, match="image/service-account mismatch"):
        launcher.launch(
            procurement=procurement,
            deployment=deployment,
            plan=p,
            decision=decision,
                permit=permit,
                attestation=attestation,
                **execution_boundary_kwargs(p, permit),
            output=tmp_path / "receipt.json",
            authoritative_now=NOW,
        )
    assert calls == ["readback"]


def test_launcher_rejects_mismatched_impersonation_source_before_job_readback(
    monkeypatch,
    tmp_path,
):
    procurement, deployment, p, _invocation, decision, permit, attestation = launch_material()
    calls = []

    monkeypatch.setattr(
        launcher,
        "bounded_impersonated_session",
        lambda **_kwargs: (_ for _ in ()).throw(
            launcher.CanaryLaunchError(
                "ADC source/target impersonation provenance mismatch"
            )
        ),
    )
    monkeypatch.setattr(
        launcher, "_run", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    with pytest.raises(launcher.CanaryLaunchError, match="provenance mismatch"):
        launcher.launch(
            procurement=procurement,
            deployment=deployment,
            plan=p,
            decision=decision,
                permit=permit,
                attestation=attestation,
                **execution_boundary_kwargs(p, permit),
            output=tmp_path / "receipt.json",
            authoritative_now=NOW,
        )
    assert calls == []


def test_launcher_rejects_non_executor_adc_before_rest_readback(
    monkeypatch,
    tmp_path,
):
    procurement, deployment, p, _invocation, decision, permit, attestation = launch_material()
    calls = []

    def reject_adc(**_kwargs):
        raise launcher.CanaryLaunchError(
            "ADC identity is not the dedicated canary executor"
        )

    monkeypatch.setattr(launcher, "bounded_impersonated_session", reject_adc)
    monkeypatch.setattr(launcher, "_run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(launcher.CanaryLaunchError, match="ADC identity"):
        launcher.launch(
            procurement=procurement,
            deployment=deployment,
            plan=p,
            decision=decision,
                permit=permit,
                attestation=attestation,
                **execution_boundary_kwargs(p, permit),
            output=tmp_path / "receipt.json",
            authoritative_now=NOW,
        )
    assert calls == []


def test_launcher_never_overwrites_an_existing_receipt(monkeypatch, tmp_path):
    procurement, deployment, p, _invocation, decision, permit, attestation = launch_material()
    output = tmp_path / "accepted-receipt.json"
    output.write_text("accepted-history\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(launcher, "_run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(launcher.CanaryLaunchError, match="will not be overwritten"):
        launcher.launch(
            procurement=procurement,
            deployment=deployment,
            plan=p,
            decision=decision,
                permit=permit,
                attestation=attestation,
                **execution_boundary_kwargs(p, permit),
            output=output,
            authoritative_now=NOW,
        )
    assert calls == []
    assert output.read_text(encoding="utf-8") == "accepted-history\n"


def test_launcher_never_retries_after_dispatch_with_indeterminate_readback(
    monkeypatch,
    tmp_path,
):
    procurement, deployment, p, _invocation, decision, permit, attestation = launch_material()
    environment = launcher._authority_environment(
        plan=p,
        decision=decision,
        permit=permit,
        attestation=attestation,
    )
    executor = "aigc-can-exec@aigc-stage.iam.gserviceaccount.com"
    cloud_sql = f"{p.project_id}:{p.location}:aigc-control"
    job = attestation.job_name
    calls = []

    def fake_run(command, *, mutating=False):
        command = list(command)
        calls.append((command, mutating))
        if command[:4] == ["gcloud", "config", "get-value", "account"]:
            return executor
        if command[:4] == ["gcloud", "run", "jobs", "describe"]:
            return json.dumps(
                {
                    "metadata": {
                        "name": job,
                        "labels": {
                            "aigc-release-sha": p.exact_revision,
                            "aigc-provider": "gemini",
                            "aigc-dormant-canary": "true",
                        },
                    },
                    "template": {
                        "taskCount": 1,
                        "parallelism": 1,
                        "template": {
                            "serviceAccount": (
                                "aigc-can-gem@aigc-stage.iam.gserviceaccount.com"
                            ),
                            "maxRetries": 0,
                            "timeout": "180s",
                            "vpcAccess": {
                                "egress": "PRIVATE_RANGES_ONLY",
                                "networkInterfaces": [
                                    {
                                        "network": "aigc-vpc",
                                        "subnetwork": "aigc-subnet",
                                    }
                                ],
                            },
                            "volumes": [
                                {
                                    "name": "cloudsql",
                                    "cloudSqlInstance": {
                                        "instances": [cloud_sql]
                                    },
                                }
                            ],
                            "containers": [
                                {
                                    "image": deployment["immutable_image_uri"],
                                    "command": ["python"],
                                    "args": [
                                        "-m",
                                        "src.operations.nexus_provider_canary",
                                    ],
                                    "env": [
                                        {"name": key, "value": value}
                                        for key, value in environment.items()
                                    ],
                                    "volumeMounts": [
                                        {
                                            "name": "cloudsql",
                                            "mountPath": "/cloudsql",
                                        }
                                    ],
                                }
                            ],
                        },
                    },
                }
            )
        if command[:4] == ["gcloud", "run", "jobs", "execute"]:
            return "unbound-execution"
        raise AssertionError(command)

    valid_job = {
        "job_name": job,
        "immutable_image_uri": deployment["immutable_image_uri"],
        "service_account": "aigc-can-gem@aigc-stage.iam.gserviceaccount.com",
        "authority_environment_sha256": canonical_sha256(environment),
        "cloud_sql_connection": cloud_sql,
        "job_description_sha256": "1" * 64,
    }
    monkeypatch.setattr(launcher, "_job_target", lambda **_kwargs: valid_job)
    monkeypatch.setattr(
        launcher,
        "_execute_job",
        lambda **_kwargs: (calls.append((["REST", "run"], True)) or "unbound-execution"),
    )
    with pytest.raises(
        launcher.CanaryLaunchIndeterminate,
        match="do not retry this permit",
    ):
        launcher.launch(
            procurement=procurement,
            deployment=deployment,
            plan=p,
            decision=decision,
            permit=permit,
            attestation=attestation,
            **execution_boundary_kwargs(p, permit),
            output=tmp_path / "receipt.json",
            authoritative_now=NOW,
        )
    mutations = [command for command, mutating in calls if mutating]
    assert len(mutations) == 1
    assert mutations[0] == ["REST", "run"]


def test_runtime_rejects_invalid_attestation_before_secret_or_provider_access(monkeypatch):
    p = plan()
    _invocation, decision, permit, attestation = authority(p)
    tampered = attestation.model_copy(update={"plan_sha256": "0" * 64})

    class ForbiddenResolver:
        def __init__(self, *args, **kwargs):
            raise AssertionError("secret resolver must not be constructed")

    monkeypatch.setattr(
        "src.operations.nexus_provider_canary.RegionalSecretManagerResolver",
        ForbiddenResolver,
    )
    with pytest.raises(CanaryConfigurationError, match="signature verification"):
        execute_canary(
            p,
            decision=decision,
            permit=permit,
            attestation=tampered,
            job_name=JOB_NAME,
            execution_name=JOB_NAME + "-abc123",
            authoritative_now=NOW,
        )


def test_log_receipt_lookup_requires_exact_project_region_job_and_execution(monkeypatch):
    project = "aigc-stage"
    region = "northamerica-northeast1"
    job = "aigc-gemini-canary001"
    execution = job + "-abc123"
    stale = {
        "labels": {"run.googleapis.com/execution_name": job + "-stale"},
        "resource": {
            "labels": {"project_id": project, "location": region, "job_name": job}
        },
        "textPayload": launcher.MARKER + json.dumps({"receipt": "stale"}),
    }
    exact = {
        "labels": {"run.googleapis.com/execution_name": execution},
        "resource": {
            "labels": {"project_id": project, "location": region, "job_name": job}
        },
        "textPayload": launcher.MARKER + json.dumps({"receipt": "exact"}),
    }
    assert launcher._receipt_from_logs(
        project=project,
        region=region,
        job_name=job,
        execution_name=execution,
        session=_RestSession({"entries": [stale, exact]}),
    ) == {"receipt": "exact"}


def test_log_receipt_lookup_deduplicates_identical_delivery_but_rejects_conflict(monkeypatch):
    project = "aigc-stage"
    region = "northamerica-northeast1"
    job = "aigc-gemini-canary001"
    execution = job + "-abc123"

    def entry(payload: dict) -> dict:
        return {
            "labels": {"run.googleapis.com/execution_name": execution},
            "resource": {
                "labels": {
                    "project_id": project,
                    "location": region,
                    "job_name": job,
                }
            },
            "textPayload": launcher.MARKER + json.dumps(payload),
        }

    exact = {"receipt": "exact"}
    assert launcher._receipt_from_logs(
        project=project,
        region=region,
        job_name=job,
        execution_name=execution,
        session=_RestSession({"entries": [entry(exact), entry(exact)]}),
    ) == exact

    with pytest.raises(launcher.CanaryLaunchError, match="exactly one"):
        launcher._receipt_from_logs(
            project=project,
            region=region,
            job_name=job,
            execution_name=execution,
            session=_RestSession({
                "entries": [entry(exact), entry({"receipt": "conflict"})]
            }),
        )


@pytest.mark.parametrize(
    ("container_update", "template_update", "message"),
    [
        (
            {
                "env": [
                    {
                        "name": "AIGC_CANARY_PLAN_JSON",
                        "valueSource": {"secretKeyRef": {"secret": "attacker"}},
                    }
                ]
            },
            {},
            "sourced environment value",
        ),
        ({}, {"volumes": [{"name": "attacker"}]}, "Cloud SQL volume mismatch"),
        ({"volumeMounts": [{"name": "attacker"}]}, {}, "Cloud SQL mount mismatch"),
        (
            {"volumeMounts": []},
            {"volumes": []},
            "lacks the exact Cloud SQL attachment",
        ),
    ],
)
def test_execution_readback_rejects_inherited_secret_and_volume_sources(
    monkeypatch,
    container_update,
    template_update,
    message,
):
    environment = {"AIGC_CANARY_PLAN_JSON": "{}"}
    cloud_sql = "aigc-stage:northamerica-northeast1:aigc-control"
    container = {
        "image": "northamerica-northeast1-docker.pkg.dev/aigc-stage/runtime/nexus@sha256:"
        + "1" * 64,
        "env": [{"name": key, "value": value} for key, value in environment.items()],
        "volumeMounts": [{"name": "cloudsql", "mountPath": "/cloudsql"}],
        **container_update,
    }
    template = {
        "serviceAccount": "aigc-can-gem@aigc-stage.iam.gserviceaccount.com",
        "vpcAccess": {
            "egress": "PRIVATE_RANGES_ONLY",
            "networkInterfaces": [
                {"network": "aigc-vpc", "subnetwork": "aigc-subnet"}
            ],
        },
        "containers": [container],
        "volumes": [
            {
                "name": "cloudsql",
                "cloudSqlInstance": {"instances": [cloud_sql]},
            }
        ],
        **template_update,
    }
    with pytest.raises(launcher.CanaryLaunchError, match=message):
        launcher._execution_target(
            project="aigc-stage",
            region="northamerica-northeast1",
            execution_name="aigc-gemini-canary001-abc123",
            job_name="aigc-gemini-canary001",
            immutable_image=container["image"],
            service_account="aigc-can-gem@aigc-stage.iam.gserviceaccount.com",
            expected_environment=environment,
            expected_network="aigc-vpc",
            expected_subnet="aigc-subnet",
            expected_cloud_sql=cloud_sql,
            reader_service_account="aigc-can-exec@aigc-stage.iam.gserviceaccount.com",
            session=_RestSession({
                "metadata": {"name": "aigc-gemini-canary001-abc123"},
                "template": template,
            }),
        )


def test_launcher_legitimate_path_carries_signed_authority_and_exact_execution_receipt(
    monkeypatch,
    tmp_path,
):
    procurement, deployment, p, invocation, decision, permit, attestation = launch_material()
    job = attestation.job_name
    execution = job + "-abc123"
    provider_receipt = successful_runtime_receipt(
        p,
        invocation,
        permit,
        attestation,
        job_name=job,
        execution_name=execution,
    )
    commands = []
    execution_environment = launcher._authority_environment(
        plan=p,
        decision=decision,
        permit=permit,
        attestation=attestation,
    )
    executor_identity = "aigc-can-exec@aigc-stage.iam.gserviceaccount.com"
    cloud_sql = f"{p.project_id}:{p.location}:aigc-control"

    def fake_run(command, *, mutating=False):
        command = list(command)
        commands.append((command, mutating))
        if command[:4] == ["gcloud", "config", "get-value", "account"]:
            return executor_identity
        if command[:4] == ["gcloud", "run", "jobs", "describe"]:
            return json.dumps(
                {
                    "metadata": {
                        "name": job,
                        "labels": {
                            "aigc-release-sha": p.exact_revision,
                            "aigc-provider": "gemini",
                            "aigc-dormant-canary": "true",
                        },
                    },
                    "template": {
                        "taskCount": 1,
                        "parallelism": 1,
                        "template": {
                            "serviceAccount": (
                                "aigc-can-gem@aigc-stage.iam.gserviceaccount.com"
                            ),
                            "maxRetries": 0,
                            "timeout": "180s",
                            "vpcAccess": {
                                "egress": "PRIVATE_RANGES_ONLY",
                                "networkInterfaces": [
                                    {
                                        "network": "aigc-vpc",
                                        "subnetwork": "aigc-subnet",
                                    }
                                ],
                            },
                            "volumes": [
                                {
                                    "name": "cloudsql",
                                    "cloudSqlInstance": {"instances": [cloud_sql]},
                                }
                            ],
                            "containers": [
                                {
                                    "image": deployment["immutable_image_uri"],
                                    "command": ["python"],
                                    "args": [
                                        "-m",
                                        "src.operations.nexus_provider_canary",
                                    ],
                                    "env": [
                                        {"name": key, "value": value}
                                        for key, value in execution_environment.items()
                                    ],
                                    "volumeMounts": [
                                        {
                                            "name": "cloudsql",
                                            "mountPath": "/cloudsql",
                                        }
                                    ],
                                }
                            ],
                        },
                    },
                }
            )
        if command[:4] == ["gcloud", "run", "jobs", "execute"]:
            return (
                f"projects/{p.project_id}/locations/{p.location}/jobs/{job}/"
                f"executions/{execution}"
            )
        if command[:5] == ["gcloud", "run", "jobs", "executions", "describe"]:
            return json.dumps(
                {
                    "metadata": {"name": execution},
                    "template": {
                        "serviceAccount": "aigc-can-gem@aigc-stage.iam.gserviceaccount.com",
                        "vpcAccess": {
                            "egress": "PRIVATE_RANGES_ONLY",
                            "networkInterfaces": [
                                {
                                    "network": "aigc-vpc",
                                    "subnetwork": "aigc-subnet",
                                }
                            ],
                        },
                        "volumes": [
                            {
                                "name": "cloudsql",
                                "cloudSqlInstance": {"instances": [cloud_sql]},
                            }
                        ],
                        "containers": [
                            {
                                "image": deployment["immutable_image_uri"],
                                "env": [
                                    {"name": key, "value": value}
                                    for key, value in execution_environment.items()
                                ],
                                "volumeMounts": [
                                    {"name": "cloudsql", "mountPath": "/cloudsql"}
                                ],
                            }
                        ],
                    },
                }
            )
        if command[:3] == ["gcloud", "logging", "read"]:
            return json.dumps(
                [
                    {
                        "labels": {"run.googleapis.com/execution_name": execution},
                        "resource": {
                            "labels": {
                                "project_id": p.project_id,
                                "location": p.location,
                                "job_name": job,
                            }
                        },
                        "textPayload": launcher.MARKER + json.dumps(provider_receipt),
                    }
                ]
            )
        raise AssertionError(command)

    valid_job = {
        "job_name": job,
        "immutable_image_uri": deployment["immutable_image_uri"],
        "service_account": "aigc-can-gem@aigc-stage.iam.gserviceaccount.com",
        "authority_environment_sha256": canonical_sha256(execution_environment),
        "cloud_sql_connection": cloud_sql,
        "job_description_sha256": "1" * 64,
    }
    valid_execution = {
        "execution_name": execution,
        "immutable_image_uri": deployment["immutable_image_uri"],
        "service_account": "aigc-can-gem@aigc-stage.iam.gserviceaccount.com",
        "network": "aigc-vpc",
        "subnet": "aigc-subnet",
        "vpc_egress": "private-ranges-only",
        "cloud_sql_connection": cloud_sql,
        "sourced_environment_values_present": False,
        "execution_description_sha256": "2" * 64,
    }
    monkeypatch.setattr(launcher, "_job_target", lambda **_kwargs: valid_job)
    monkeypatch.setattr(
        launcher,
        "_execute_job",
        lambda **_kwargs: (commands.append((["REST", "run"], True)) or execution),
    )
    monkeypatch.setattr(
        launcher, "_execution_target", lambda **_kwargs: valid_execution
    )
    monkeypatch.setattr(
        launcher, "_receipt_from_logs", lambda **_kwargs: provider_receipt
    )
    output = tmp_path / "canary-job-receipt.json"
    result = launcher.launch(
        procurement=procurement,
        deployment=deployment,
        plan=p,
        decision=decision,
        permit=permit,
        attestation=attestation,
        **execution_boundary_kwargs(p, permit),
        output=output,
        authoritative_now=NOW,
    )
    assert result["job_name"] == job
    assert result["execution_name"] == execution
    assert result["execution_target"]["execution_name"] == execution
    assert result["job_target"]["cloud_sql_connection"] == cloud_sql
    assert result["execution_target"]["cloud_sql_connection"] == cloud_sql
    assert result["provider_receipt"]["canary_receipt_id"] == provider_receipt[
        "canary_receipt_id"
    ]
    assert output.is_file()
    assert execution_environment["AIGC_CANARY_AUTHORITY_ATTESTATION_JSON"]
    assert "AIGC_CANARY_AUTHORITY_PUBLIC_KEY_PEM" not in execution_environment
    assert "AIGC_CANARY_AUTHORITY_PUBLIC_KEY_SHA256" not in execution_environment
    assert all("deploy" not in command for command, _ in commands)
    mutating_commands = [command for command, mutating in commands if mutating]
    assert len(mutating_commands) == 1
    assert mutating_commands[0] == ["REST", "run"]
    assert result["job_deployment_performed"] is False
    assert result["execution_overrides_supplied"] is False
    assert result["executor_identity"] == executor_identity
    assert result["executor_identity_evidence"][
        "adc_impersonation_target_verified"
    ] is True
    assert result["executor_identity_evidence"][
        "adc_source_keyless_verified"
    ] is True
    assert result["executor_identity_evidence"][
        "bounded_token_lifetime_seconds"
    ] <= 900
    assert result["maximum_input_units"] == 64
    assert result["maximum_output_units"] == 64
    assert result["request_timeout_seconds"] == 30
    assert result["cloud_run_mutation_count"] == 1
    assert commands == [(["REST", "run"], True)]


def test_launcher_validates_wrapper_and_core_receipt_ids_and_rejects_raw_output():
    _procurement, _deployment, p, invocation, _decision, permit, attestation = launch_material()
    job = attestation.job_name
    execution = job + "-abc123"
    receipt = successful_runtime_receipt(
        p,
        invocation,
        permit,
        attestation,
        job_name=job,
        execution_name=execution,
    )
    launcher._validate_provider_receipt(
        receipt,
        plan=p,
        permit=permit,
        attestation=attestation,
        job_name=job,
        execution_name=execution,
    )

    wrong_core = deepcopy(receipt)
    wrong_core["receipt"]["receipt_id"] = "EXEC-" + "A" * 24
    unsigned = dict(wrong_core)
    unsigned.pop("canary_receipt_id")
    wrong_core["canary_receipt_id"] = "CANARY-" + canonical_sha256(unsigned)[:24].upper()
    with pytest.raises(launcher.CanaryLaunchError, match="core receipt ID mismatch"):
        launcher._validate_provider_receipt(
            wrong_core,
            plan=p,
            permit=permit,
            attestation=attestation,
            job_name=job,
            execution_name=execution,
        )

    raw = deepcopy(receipt)
    raw["attempt"]["response_payload"] = "raw provider output"
    unsigned = dict(raw)
    unsigned.pop("canary_receipt_id")
    raw["canary_receipt_id"] = "CANARY-" + canonical_sha256(unsigned)[:24].upper()
    with pytest.raises(launcher.CanaryLaunchError, match="raw provider output"):
        launcher._validate_provider_receipt(
            raw,
            plan=p,
            permit=permit,
            attestation=attestation,
            job_name=job,
            execution_name=execution,
        )

    unexpected = deepcopy(receipt)
    unexpected["raw_provider_output"] = "must never be persisted"
    unsigned = dict(unexpected)
    unsigned.pop("canary_receipt_id")
    unexpected["canary_receipt_id"] = (
        "CANARY-" + canonical_sha256(unsigned)[:24].upper()
    )
    with pytest.raises(launcher.CanaryLaunchError, match="exact redacted contract"):
        launcher._validate_provider_receipt(
            unexpected, plan=p, permit=permit, attestation=attestation,
            job_name=job, execution_name=execution,
        )

    duplicate_call = deepcopy(receipt)
    duplicate_call["audit"]["provider_api_calls_performed"] = 2
    unsigned = dict(duplicate_call)
    unsigned.pop("canary_receipt_id")
    duplicate_call["canary_receipt_id"] = (
        "CANARY-" + canonical_sha256(unsigned)[:24].upper()
    )
    with pytest.raises(launcher.CanaryLaunchError, match="exactly one"):
        launcher._validate_provider_receipt(
            duplicate_call, plan=p, permit=permit, attestation=attestation,
            job_name=job, execution_name=execution,
        )

    unknown_cost = deepcopy(receipt)
    unknown_cost["attempt"]["cost_known"] = False
    unsigned = dict(unknown_cost)
    unsigned.pop("canary_receipt_id")
    unknown_cost["canary_receipt_id"] = (
        "CANARY-" + canonical_sha256(unsigned)[:24].upper()
    )
    with pytest.raises(launcher.CanaryLaunchError, match="invalid nested evidence"):
        launcher._validate_provider_receipt(
            unknown_cost, plan=p, permit=permit, attestation=attestation,
            job_name=job, execution_name=execution,
        )


def test_bounded_impersonation_rejects_service_account_key_source(monkeypatch):
    import google.auth
    from scripts.nexus_canary_impersonation import bounded_impersonated_session

    KeySource = type(
        "Credentials",
        (),
        {"__module__": "google.oauth2.service_account"},
    )
    source = KeySource()
    source.service_account_email = "key-source@aigc-stage.iam.gserviceaccount.com"
    outer = type("Outer", (), {})()
    outer.target_principal = "aigc-can-exec@aigc-stage.iam.gserviceaccount.com"
    outer._target_principal = outer.target_principal
    outer._source_credentials = source
    monkeypatch.setattr(google.auth, "default", lambda **_kwargs: (outer, "aigc-stage"))
    with pytest.raises(launcher.CanaryLaunchError, match="key-backed"):
        bounded_impersonated_session(
            expected_target=outer.target_principal,
            expected_source=source.service_account_email,
            authority_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            error_type=launcher.CanaryLaunchError,
        )


def test_bounded_impersonation_uses_attached_metadata_and_never_refreshes_session(
    monkeypatch,
):
    import google.auth
    from google.auth import impersonated_credentials
    from google.auth.compute_engine.credentials import Credentials as ComputeCredentials
    import requests
    from scripts.nexus_canary_impersonation import bounded_impersonated_session

    source_email = "aigc-can-source@aigc-stage.iam.gserviceaccount.com"
    target_email = "aigc-can-exec@aigc-stage.iam.gserviceaccount.com"
    source = ComputeCredentials(service_account_email=source_email)
    source_refreshes = []
    monkeypatch.setattr(
        ComputeCredentials,
        "refresh",
        lambda self, request: source_refreshes.append((self, request)),
    )
    monkeypatch.setattr(
        google.auth,
        "default",
        lambda **kwargs: (source, "aigc-stage"),
    )

    minted = []

    class BoundedCredentials:
        token = None
        expiry = None

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def refresh(self, _request):
            minted.append(self.kwargs)
            setattr(self, "token", "test_only_bounded_token")
            self.expiry = datetime.now(timezone.utc) + timedelta(minutes=4)

    monkeypatch.setattr(
        impersonated_credentials,
        "Credentials",
        BoundedCredentials,
    )
    session, evidence = bounded_impersonated_session(
        expected_target=target_email,
        expected_source=source_email,
        authority_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        error_type=launcher.CanaryLaunchError,
    )

    assert isinstance(session, requests.Session)
    assert session.headers["Authorization"] == "Bearer test_only_bounded_token"
    assert evidence["attached_metadata_source_verified"] is True
    assert evidence["bounded_token_refresh_permitted"] is False
    assert len(source_refreshes) == 1
    assert len(minted) == 1
    assert minted[0]["target_principal"] == target_email
    assert 1 <= minted[0]["lifetime"] <= 300
    session.prepare_request(requests.Request("GET", "https://example.invalid"))
    assert len(minted) == 1
