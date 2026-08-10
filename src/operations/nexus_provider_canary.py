from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.core.nexus.live_provider_runtime import (
    GovernedLiveNexusProviderRuntime,
    LiveProviderExecutionPolicy,
)
from src.core.nexus.provider_registry import ProviderRegistry
from src.core.nexus.provider_runtime import bind_provider_request_digest
from src.domain.nexus.contracts import (
    AuthorityAttestation,
    ExecutionPermit,
    GovernanceDecision,
)
from src.domain.nexus.provider_runtime import (
    ProviderInvocation,
    ProviderRuntimeExecution,
    ProviderRuntimeLimits,
)
from src.infrastructure.credentials.regional_secret_manager import (
    REGION,
    RegionalSecretError,
    RegionalSecretManagerResolver,
)
from src.infrastructure.providers.google_vertex_gemini import (
    THINKING_DISABLED_GEMINI_MODELS,
    GoogleVertexGeminiAdapter,
)
from src.infrastructure.providers.openai_responses import OpenAIResponsesAdapter
from src.infrastructure.providers.pricing import TokenPricing
from src.infrastructure.runtime.postgres_control_store import PostgresRuntimeControlStore


class CanaryConfigurationError(RuntimeError):
    pass


def credential_reference_sha256(reference: str) -> str:
    return canonical_sha256({"regional_secret_reference": reference})


KMS_KEY_VERSION_PATTERN = re.compile(
    r"^projects/(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])/locations/"
    r"(?P<location>[a-z0-9-]+)/keyRings/(?P<key_ring>[A-Za-z0-9_-]{1,63})/"
    r"cryptoKeys/(?P<crypto_key>[A-Za-z0-9_-]{1,63})/cryptoKeyVersions/"
    r"(?P<version>[1-9][0-9]*)$"
)
CANARY_AUTHORITY_ALGORITHM = "RSA_SIGN_PSS_2048_SHA256"


@dataclass(frozen=True)
class KmsAuthorityPublicKey:
    """Public, authenticated KMS key material returned by the exact key version."""

    kms_key_version: str
    algorithm: str
    public_key_pem: str
    public_key_sha256: str


def expected_canary_authority_key_version(*, project_id: str, resource_prefix: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project_id):
        raise CanaryConfigurationError("canary authority project ID is invalid")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,18}", resource_prefix):
        raise CanaryConfigurationError("canary authority resource prefix is invalid")
    return (
        f"projects/{project_id}/locations/{REGION}/keyRings/{resource_prefix}-keys/"
        f"cryptoKeys/{resource_prefix}-canary-authority/cryptoKeyVersions/1"
    )


def _canary_resource_prefix(
    *,
    plan: "ProviderCanaryPlan",
    permit: ExecutionPermit,
    job_name: str,
) -> str:
    provider = "gemini" if plan.provider_id == "google_vertex_gemini" else "openai"
    permit_binding = hashlib.sha256(permit.permit_id.encode("utf-8")).hexdigest()[:12]
    suffix = f"-{provider}-{permit_binding}"
    if not job_name.endswith(suffix):
        raise CanaryConfigurationError("canary job name does not bind the provider permit")
    resource_prefix = job_name[: -len(suffix)]
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,18}", resource_prefix):
        raise CanaryConfigurationError("canary job contains an invalid resource prefix")
    return resource_prefix


class ProviderCanaryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["aigc.nexus-provider-canary.v2"] = "aigc.nexus-provider-canary.v2"
    provider_id: Literal["google_vertex_gemini", "openai_responses"]
    project_id: str = Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    location: str = REGION
    model: str = Field(min_length=1, max_length=200)
    exact_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    procurement_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    deployment_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    principal: str = Field(min_length=1, max_length=200)
    change_set_id: str = Field(pattern=r"^CHG-[A-Z0-9_-]{6,64}$")
    change_set_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parent_state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    purpose: str = Field(min_length=1, max_length=2000)
    input_payload: str = Field(min_length=1, max_length=12000)
    reserved_usage_units: int = Field(ge=1, le=4096)
    maximum_input_units: int = Field(ge=1, le=4096)
    maximum_output_units: int = Field(ge=1, le=4096)
    request_timeout_seconds: int = Field(ge=1, le=120)
    maximum_cost_cad: Decimal = Field(gt=Decimal("0.00"), le=Decimal("5.00"))
    input_cad_per_million: Decimal = Field(gt=Decimal("0.00"))
    output_cad_per_million: Decimal = Field(gt=Decimal("0.00"))
    pricing_evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime_control_dsn_secret_ref: str = Field(min_length=1, max_length=1000)
    runtime_control_dsn_secret_ref_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    openai_api_key_secret_ref: str | None = Field(default=None, max_length=1000)
    openai_api_key_secret_ref_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )

    @model_validator(mode="after")
    def provider_specific_requirements(self) -> "ProviderCanaryPlan":
        if self.location != REGION:
            raise ValueError(f"provider canary location must equal {REGION}")
        if (
            self.provider_id == "google_vertex_gemini"
            and self.model not in THINKING_DISABLED_GEMINI_MODELS
        ):
            raise ValueError(
                "Gemini canary requires an exact reviewed thinking-disabled model"
            )
        if (
            self.maximum_input_units + self.maximum_output_units
            > self.reserved_usage_units
        ):
            raise ValueError(
                "maximum input and output units exceed reserved usage units"
            )
        conservative_input_units = len(self.input_payload.encode("utf-8")) + 32
        if conservative_input_units > self.maximum_input_units:
            raise ValueError(
                "canary input exceeds its conservative maximum input units"
            )
        worst_case_cost = TokenPricing(
            input_cad_per_million=self.input_cad_per_million,
            output_cad_per_million=self.output_cad_per_million,
        ).cost_cad(
            input_tokens=self.maximum_input_units,
            output_tokens=self.maximum_output_units,
        )
        if worst_case_cost > self.maximum_cost_cad:
            raise ValueError(
                "canary worst-case signed token cost exceeds maximum_cost_cad"
            )
        validator = RegionalSecretManagerResolver(
            client_factory=lambda _endpoint: None,
            expected_project_id=self.project_id,
        )
        try:
            validator.parse_reference(self.runtime_control_dsn_secret_ref)
            if self.runtime_control_dsn_secret_ref_sha256 != credential_reference_sha256(
                self.runtime_control_dsn_secret_ref
            ):
                raise ValueError("runtime-control credential-reference digest mismatch")
            if self.provider_id == "openai_responses":
                if not self.openai_api_key_secret_ref:
                    raise ValueError("OpenAI canary requires an exact regional API-key secret reference")
                validator.parse_reference(self.openai_api_key_secret_ref)
                if self.openai_api_key_secret_ref_sha256 != credential_reference_sha256(
                    self.openai_api_key_secret_ref
                ):
                    raise ValueError("OpenAI credential-reference digest mismatch")
            elif self.openai_api_key_secret_ref is not None:
                raise ValueError("Gemini canary cannot carry an OpenAI secret reference")
            elif self.openai_api_key_secret_ref_sha256 is not None:
                raise ValueError("Gemini canary cannot carry an OpenAI credential-reference digest")
        except RegionalSecretError as exc:
            raise ValueError(str(exc)) from None
        return self

    @property
    def provider_location(self) -> str:
        return self.location if self.provider_id == "google_vertex_gemini" else "provider-managed"

    @property
    def resource_binding_sha256(self) -> str:
        return canonical_sha256(
            {
                "provider_id": self.provider_id,
                "project_id": self.project_id,
                "execution_region": self.location,
                "provider_location": self.provider_location,
                "model": self.model,
                "thinking_disabled_required": (
                    self.provider_id == "google_vertex_gemini"
                ),
                "thinking_budget": (
                    0 if self.provider_id == "google_vertex_gemini" else None
                ),
                "maximum_input_units": self.maximum_input_units,
                "maximum_output_units": self.maximum_output_units,
                "request_timeout_seconds": self.request_timeout_seconds,
                "runtime_control_dsn_secret_ref_sha256": (
                    self.runtime_control_dsn_secret_ref_sha256
                ),
                "openai_api_key_secret_ref_sha256": (
                    self.openai_api_key_secret_ref_sha256
                ),
            }
        )

    @property
    def resource_ref(self) -> str:
        return f"provider://{self.provider_id}/bound/{self.resource_binding_sha256}"

    @property
    def capability(self) -> str:
        return "generate.text"

    @property
    def required_governance_conditions(self) -> tuple[str, ...]:
        conditions = (
            f"MAX_COST_CAD={self.maximum_cost_cad}",
            f"WORST_CASE_TOKEN_COST_CAD={self.worst_case_token_cost_cad}",
            f"INPUT_CAD_PER_MILLION={self.input_cad_per_million}",
            f"OUTPUT_CAD_PER_MILLION={self.output_cad_per_million}",
            f"PRICING_EVIDENCE_SHA256={self.pricing_evidence_sha256}",
            f"MAX_INPUT_UNITS={self.maximum_input_units}",
            f"MAX_OUTPUT_UNITS={self.maximum_output_units}",
            f"REQUEST_TIMEOUT_SECONDS={self.request_timeout_seconds}",
            f"PROJECT_ID={self.project_id}",
            f"EXECUTION_REGION={self.location}",
            f"PROVIDER_LOCATION={self.provider_location}",
            f"MODEL={self.model}",
        )
        if self.provider_id == "google_vertex_gemini":
            conditions += (
                "THINKING_DISABLED_REQUIRED=true",
                "THINKING_BUDGET=0",
            )
        return conditions

    @property
    def worst_case_token_cost_cad(self) -> Decimal:
        return TokenPricing(
            input_cad_per_million=self.input_cad_per_million,
            output_cad_per_million=self.output_cad_per_million,
        ).cost_cad(
            input_tokens=self.maximum_input_units,
            output_tokens=self.maximum_output_units,
        )


def _load_json(path: Path | None, env_name: str) -> dict:
    if path is not None:
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            raise CanaryConfigurationError(f"{env_name} or a file argument is required")
        value = json.loads(raw)
    if not isinstance(value, dict):
        raise CanaryConfigurationError(f"{env_name} must decode to an object")
    return value


def _plan_seed(plan: ProviderCanaryPlan) -> str:
    return canonical_sha256(plan.model_dump(mode="json"))


def authority_public_key_sha256(public_key_pem: str) -> str:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise CanaryConfigurationError("authority public key is not valid PEM") from exc
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise CanaryConfigurationError("authority public key must be RSA")
    encoded = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(encoded).hexdigest()


def _crc32c(value: bytes) -> int:
    crc = 0xFFFFFFFF
    for octet in value:
        crc ^= octet
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def _authorized_kms_public_key_response(kms_key_version: str):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _project = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",)
    )
    session = AuthorizedSession(credentials)
    return session.get(
        f"https://{REGION}-cloudkms.googleapis.com/v1/{kms_key_version}/publicKey",
        timeout=10,
    )


def fetch_kms_authority_public_key(kms_key_version: str) -> KmsAuthorityPublicKey:
    """Fetch one exact public key from its regional KMS endpoint using ADC."""

    match = KMS_KEY_VERSION_PATTERN.fullmatch(kms_key_version)
    if match is None or match.group("location") != REGION:
        raise CanaryConfigurationError("authority KMS key version must be exact and in Montréal")
    try:
        response = _authorized_kms_public_key_response(kms_key_version)
    except Exception as exc:
        raise CanaryConfigurationError("exact KMS public-key retrieval failed") from exc
    if response.status_code != 200:
        raise CanaryConfigurationError("exact KMS public-key retrieval was not authorized")
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise CanaryConfigurationError("KMS public-key response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise CanaryConfigurationError("KMS public-key response must be an object")
    if payload.get("name") != kms_key_version:
        raise CanaryConfigurationError("KMS public-key response identity mismatch")
    algorithm = str(payload.get("algorithm") or "")
    if algorithm != CANARY_AUTHORITY_ALGORITHM:
        raise CanaryConfigurationError("KMS public-key algorithm is not the admitted algorithm")
    public_key_pem = str(payload.get("pem") or "")
    try:
        expected_crc32c = int(str(payload["pemCrc32c"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise CanaryConfigurationError("KMS public-key response has no valid CRC32C") from exc
    if _crc32c(public_key_pem.encode("utf-8")) != expected_crc32c:
        raise CanaryConfigurationError("KMS public-key CRC32C verification failed")
    public_key_sha256 = authority_public_key_sha256(public_key_pem)
    return KmsAuthorityPublicKey(
        kms_key_version=kms_key_version,
        algorithm=algorithm,
        public_key_pem=public_key_pem,
        public_key_sha256=public_key_sha256,
    )


def _verify_attestation_signature(
    attestation: AuthorityAttestation,
    *,
    kms_public_key: KmsAuthorityPublicKey,
) -> None:
    if kms_public_key.kms_key_version != attestation.kms_key_version:
        raise CanaryConfigurationError("AuthorityAttestation KMS key-version mismatch")
    if kms_public_key.algorithm != attestation.signing_algorithm:
        raise CanaryConfigurationError("AuthorityAttestation KMS algorithm mismatch")
    try:
        public_key = serialization.load_pem_public_key(
            kms_public_key.public_key_pem.encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise CanaryConfigurationError("KMS authority public key is not valid PEM") from exc
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise CanaryConfigurationError("KMS authority public key must be RSA")
    observed_sha256 = authority_public_key_sha256(kms_public_key.public_key_pem)
    if not hmac.compare_digest(observed_sha256, kms_public_key.public_key_sha256):
        raise CanaryConfigurationError("KMS authority public-key evidence is internally inconsistent")
    if not hmac.compare_digest(observed_sha256, attestation.public_key_sha256):
        raise CanaryConfigurationError("AuthorityAttestation public-key digest mismatch")

    expected_size = {
        "RSA_SIGN_PSS_2048_SHA256": 2048,
        "RSA_SIGN_PSS_3072_SHA256": 3072,
        "RSA_SIGN_PSS_4096_SHA256": 4096,
    }[attestation.signing_algorithm]
    if public_key.key_size != expected_size:
        raise CanaryConfigurationError("authority public-key size does not match KMS algorithm")
    try:
        signature = base64.b64decode(attestation.signature_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CanaryConfigurationError("AuthorityAttestation signature is not canonical base64") from exc
    digest = hashlib.sha256(canonical_json_bytes(attestation.signed_payload())).digest()
    try:
        public_key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise CanaryConfigurationError("AuthorityAttestation signature verification failed") from exc


def verify_authority_attestation(
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    *,
    expected_kms_key_version: str,
    authoritative_now: datetime,
    expected_job_name: str,
) -> None:
    attestation.verify_temporal_validity(authoritative_now=authoritative_now)
    if attestation.kms_key_version != expected_kms_key_version:
        raise CanaryConfigurationError("AuthorityAttestation does not use the deterministic KMS trust root")
    kms_public_key = fetch_kms_authority_public_key(expected_kms_key_version)
    _verify_attestation_signature(
        attestation,
        kms_public_key=kms_public_key,
    )
    expected_hashes = {
        "procurement_sha256": plan.procurement_sha256,
        "deployment_sha256": plan.deployment_sha256,
        "plan_sha256": canonical_sha256(plan.model_dump(mode="json")),
        "governance_decision_sha256": canonical_sha256(decision.model_dump(mode="json")),
        "execution_permit_sha256": canonical_sha256(permit.model_dump(mode="json")),
    }
    for field, expected in expected_hashes.items():
        if not hmac.compare_digest(getattr(attestation, field), expected):
            raise CanaryConfigurationError(f"AuthorityAttestation {field} mismatch")
    if attestation.permit_id != permit.permit_id:
        raise CanaryConfigurationError("AuthorityAttestation permit binding mismatch")
    if attestation.request_digest != permit.request_digest:
        raise CanaryConfigurationError("AuthorityAttestation request binding mismatch")
    if attestation.subject != decision.authority_actor:
        raise CanaryConfigurationError("AuthorityAttestation subject/authority actor mismatch")
    if attestation.job_name != expected_job_name:
        raise CanaryConfigurationError("AuthorityAttestation job binding mismatch")


def build_invocation(
    plan: ProviderCanaryPlan,
    *,
    permit_id: str | None = None,
) -> ProviderInvocation:
    seed = _plan_seed(plan)
    invocation = ProviderInvocation(
        invocation_id="PINV-CANARY-" + seed[:20].upper(),
        request_id="TREQ-CANARY-" + seed[20:40].upper(),
        change_set_id=plan.change_set_id,
        parent_state_hash=plan.parent_state_hash,
        principal=plan.principal,
        provider_id=plan.provider_id,
        capability=plan.capability,
        model_or_resource=plan.model,
        exact_revision=plan.exact_revision,
        request_digest="0" * 64,
        idempotency_key=canonical_sha256(
            {"canary_plan": plan.model_dump(mode="json"), "purpose": "provider-canary"}
        ),
        reserved_usage_units=plan.reserved_usage_units,
        maximum_input_units=plan.maximum_input_units,
        maximum_output_units=plan.maximum_output_units,
        request_timeout_seconds=plan.request_timeout_seconds,
        maximum_cost_cad=plan.maximum_cost_cad,
        resource_ref=plan.resource_ref,
        purpose=plan.purpose,
        requested_effect_class="READ_EXTERNAL",
        input_payload=plan.input_payload,
        permit_id=None,
    )
    invocation = bind_provider_request_digest(invocation)
    if permit_id is not None:
        invocation = invocation.model_copy(update={"permit_id": permit_id})
    return invocation


def plan_receipt(plan: ProviderCanaryPlan) -> dict:
    invocation = build_invocation(plan)
    return {
        "schema_version": "aigc.nexus-provider-canary-plan.v2",
        "provider_id": plan.provider_id,
        "project_id": plan.project_id,
        "location": plan.location,
        "execution_region": plan.location,
        "provider_location": plan.provider_location,
        "model": plan.model,
        "exact_revision": plan.exact_revision,
        "procurement_sha256": plan.procurement_sha256,
        "deployment_sha256": plan.deployment_sha256,
        "plan_sha256": canonical_sha256(plan.model_dump(mode="json")),
        "principal": plan.principal,
        "resource_ref": plan.resource_ref,
        "resource_binding_sha256": plan.resource_binding_sha256,
        "request_digest": invocation.request_digest,
        "idempotency_key": invocation.idempotency_key,
        "runtime_control_dsn_secret_ref_sha256": plan.runtime_control_dsn_secret_ref_sha256,
        "openai_api_key_secret_ref_sha256": plan.openai_api_key_secret_ref_sha256,
        "maximum_cost_cad": str(plan.maximum_cost_cad),
        "reserved_usage_units": plan.reserved_usage_units,
        "maximum_input_units": plan.maximum_input_units,
        "maximum_output_units": plan.maximum_output_units,
        "request_timeout_seconds": plan.request_timeout_seconds,
        "required_governance_conditions": plan.required_governance_conditions,
        "required_maximum_invocations": 1,
        "detached_authority_attestation_required": True,
        "provider_call_performed": False,
        "network_call_performed": False,
        "credential_used": False,
    }


def validate_canary_authority(
    plan: ProviderCanaryPlan,
    invocation: ProviderInvocation,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    *,
    expected_kms_key_version: str,
    authoritative_now: datetime,
    expected_job_name: str,
) -> None:
    verify_authority_attestation(
        plan,
        decision,
        permit,
        attestation,
        expected_kms_key_version=expected_kms_key_version,
        authoritative_now=authoritative_now,
        expected_job_name=expected_job_name,
    )
    if decision.decision != "approved":
        raise CanaryConfigurationError("provider canary requires an approved GovernanceDecision")
    if decision.authority_source != "HUMAN":
        raise CanaryConfigurationError("first live provider canary requires HUMAN governance authority")
    if permit.governance_decision_id != decision.decision_id:
        raise CanaryConfigurationError("ExecutionPermit is not bound to the supplied GovernanceDecision")
    if decision.exact_revision != plan.exact_revision or permit.exact_revision != plan.exact_revision:
        raise CanaryConfigurationError("provider canary exact revision authority mismatch")
    if decision.artifact_state_hash != plan.parent_state_hash:
        raise CanaryConfigurationError("GovernanceDecision parent state mismatch")
    if (
        permit.change_set_hash != decision.change_set_hash
        or permit.change_set_hash != plan.change_set_hash
    ):
        raise CanaryConfigurationError("GovernanceDecision/ExecutionPermit ChangeSet hash mismatch")
    if permit.principal != plan.principal:
        raise CanaryConfigurationError("ExecutionPermit principal mismatch")
    if permit.capability != plan.capability:
        raise CanaryConfigurationError("ExecutionPermit capability mismatch")
    if plan.resource_ref not in permit.resource_scope:
        raise CanaryConfigurationError("ExecutionPermit does not contain exact provider resource scope")
    if permit.request_digest != invocation.request_digest:
        raise CanaryConfigurationError("ExecutionPermit request digest mismatch")
    if permit.maximum_invocations != 1:
        raise CanaryConfigurationError("provider canary ExecutionPermit must be one-use")
    missing_conditions = set(plan.required_governance_conditions) - set(decision.conditions)
    if missing_conditions:
        raise CanaryConfigurationError(
            "GovernanceDecision does not bind the exact project/region/model/cost scope"
        )
    if decision.expires_at is None:
        raise CanaryConfigurationError("provider canary GovernanceDecision must expire")
    if decision.expires_at <= authoritative_now:
        raise CanaryConfigurationError("provider canary GovernanceDecision is expired")
    permit.verify_temporal_validity(authoritative_now=authoritative_now)
    if decision.expires_at > attestation.expires_at or permit.expires_at > attestation.expires_at:
        raise CanaryConfigurationError("authority artifacts outlive the signed AuthorityAttestation")


# Backward-compatible import name; the stronger signature intentionally requires
# detached authority material and a separately trusted public-key pin.
_validate_authority = validate_canary_authority


def _adapter(plan: ProviderCanaryPlan, resolver: RegionalSecretManagerResolver):
    pricing = TokenPricing(
        input_cad_per_million=plan.input_cad_per_million,
        output_cad_per_million=plan.output_cad_per_million,
    )
    if plan.provider_id == "google_vertex_gemini":
        return GoogleVertexGeminiAdapter(
            project=plan.project_id,
            location=plan.location,
            model=plan.model,
            pricing=pricing,
        )
    if plan.openai_api_key_secret_ref is None:
        raise CanaryConfigurationError("OpenAI secret reference is missing")
    return OpenAIResponsesAdapter(
        model=plan.model,
        pricing=pricing,
        api_key_supplier=lambda: resolver.resolve_text(plan.openai_api_key_secret_ref or ""),
    )


def _validate_cloud_run_execution(*, job_name: str, execution_name: str) -> None:
    if not re.fullmatch(r"[a-z](?:[a-z0-9-]{0,126}[a-z0-9])?", execution_name):
        raise CanaryConfigurationError("Cloud Run execution name is invalid")
    if not execution_name.startswith(job_name + "-"):
        raise CanaryConfigurationError("Cloud Run execution is not bound to the attested job")


def _canonical_execution_receipt_id(
    invocation: ProviderInvocation,
    result: ProviderRuntimeExecution,
) -> str:
    payload = {
        "invocation_id": invocation.invocation_id,
        "request_digest": invocation.request_digest,
        "attempt": result.attempt.model_dump(mode="json"),
        "change_set_id": invocation.change_set_id,
        "parent_state_hash": invocation.parent_state_hash,
    }
    return "EXEC-" + canonical_sha256(payload)[:24].upper()


def validate_canary_execution_result(
    *,
    invocation: ProviderInvocation,
    permit: ExecutionPermit,
    result: ProviderRuntimeExecution,
) -> None:
    if result.replayed:
        raise CanaryConfigurationError("one-use provider canary cannot return a replayed result")
    if result.invocation_id != invocation.invocation_id:
        raise CanaryConfigurationError("provider execution invocation mismatch")
    if result.attempt.invocation_id != invocation.invocation_id:
        raise CanaryConfigurationError("provider attempt invocation mismatch")
    if result.attempt.provider_id != invocation.provider_id:
        raise CanaryConfigurationError("provider attempt identity mismatch")
    if result.attempt.model_or_resource != invocation.model_or_resource:
        raise CanaryConfigurationError("provider attempt model mismatch")
    if result.attempt.response_payload is not None:
        raise CanaryConfigurationError("raw provider output reached persisted canary evidence")
    receipt = result.receipt
    if receipt.receipt_id != _canonical_execution_receipt_id(invocation, result):
        raise CanaryConfigurationError("provider execution receipt ID mismatch")
    if receipt.permit_id != permit.permit_id:
        raise CanaryConfigurationError("provider execution receipt permit mismatch")
    if receipt.change_set_id != invocation.change_set_id:
        raise CanaryConfigurationError("provider execution receipt ChangeSet mismatch")
    if receipt.parent_state_hash != invocation.parent_state_hash:
        raise CanaryConfigurationError("provider execution receipt parent state mismatch")
    if receipt.execution_status != result.attempt.status:
        raise CanaryConfigurationError("provider execution receipt status mismatch")
    if len(receipt.operations) != 1:
        raise CanaryConfigurationError("provider execution receipt must contain one operation")
    operation = receipt.operations[0]
    if operation.operation_id != invocation.invocation_id:
        raise CanaryConfigurationError("provider execution receipt operation mismatch")
    if operation.resource_ref != invocation.resource_ref or operation.status != result.attempt.status:
        raise CanaryConfigurationError("provider execution receipt resource/status mismatch")
    expected_after = (
        result.attempt.response_digest if result.attempt.status == "succeeded" else None
    )
    if operation.after_hash != expected_after:
        raise CanaryConfigurationError("provider execution receipt response digest mismatch")


def canary_execution_receipt(
    plan: ProviderCanaryPlan,
    *,
    invocation: ProviderInvocation,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    result: ProviderRuntimeExecution,
    job_name: str,
    execution_name: str,
    captured_at: datetime,
) -> dict:
    validate_canary_execution_result(invocation=invocation, permit=permit, result=result)
    payload = {
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
        "invocation_id": result.invocation_id,
        "attempt": result.attempt.model_dump(mode="json"),
        "receipt": result.receipt.model_dump(mode="json"),
        "audit": result.audit.model_dump(mode="json"),
        "replayed": result.replayed,
        "response_payload_retained": False,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
    }
    payload["canary_receipt_id"] = (
        "CANARY-" + canonical_sha256(payload)[:24].upper()
    )
    return payload


def execute_canary(
    plan: ProviderCanaryPlan,
    *,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    attestation: AuthorityAttestation,
    job_name: str,
    execution_name: str,
    authoritative_now: datetime | None = None,
):
    now = authoritative_now or datetime.now(timezone.utc)
    invocation = build_invocation(plan, permit_id=permit.permit_id)
    resource_prefix = _canary_resource_prefix(
        plan=plan,
        permit=permit,
        job_name=job_name,
    )
    expected_kms_key_version = expected_canary_authority_key_version(
        project_id=plan.project_id,
        resource_prefix=resource_prefix,
    )
    validate_canary_authority(
        plan,
        invocation,
        decision,
        permit,
        attestation,
        expected_kms_key_version=expected_kms_key_version,
        authoritative_now=now,
        expected_job_name=job_name,
    )
    _validate_cloud_run_execution(job_name=job_name, execution_name=execution_name)

    resolver = RegionalSecretManagerResolver(expected_project_id=plan.project_id)
    dsn = resolver.resolve_text(plan.runtime_control_dsn_secret_ref)
    try:
        control_store = PostgresRuntimeControlStore(dsn)
    finally:
        dsn = ""

    control_store.claim_canary_authority(
        permit_id=permit.permit_id,
        attestation_id=attestation.attestation_id,
        attestation_sha256=canonical_sha256(attestation.model_dump(mode="json")),
        execution_nonce=attestation.execution_nonce,
        procurement_sha256=attestation.procurement_sha256,
        deployment_sha256=attestation.deployment_sha256,
        plan_sha256=attestation.plan_sha256,
        governance_decision_sha256=attestation.governance_decision_sha256,
        execution_permit_sha256=attestation.execution_permit_sha256,
        request_digest=invocation.request_digest,
        principal=plan.principal,
        exact_revision=plan.exact_revision,
        job_name=job_name,
        execution_name=execution_name,
    )

    adapter = _adapter(plan, resolver)
    registry = ProviderRegistry((adapter,))
    limits = ProviderRuntimeLimits(
        principal_invocations_per_minute=2,
        principal_invocations_per_day=2,
        global_invocations_per_minute=2,
        global_invocations_per_day=2,
        principal_reserved_usage_per_day=8192,
        global_reserved_usage_per_day=8192,
        maximum_usage_per_invocation=plan.reserved_usage_units,
        maximum_cost_cad_per_invocation=plan.maximum_cost_cad,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=registry,
        control_store=control_store,
        limits=limits,
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({plan.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
            require_durable_control_store=True,
        ),
    )
    runtime.execute(invocation, authoritative_now=now, permit=permit)
    persisted = control_store.get_execution_result(invocation.invocation_id)
    if persisted is None:
        raise CanaryConfigurationError("durable canary execution result is missing")
    validate_canary_execution_result(
        invocation=invocation,
        permit=permit,
        result=persisted,
    )
    return persisted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--governance", type=Path)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--authority-attestation", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = ProviderCanaryPlan.model_validate(_load_json(args.plan, "AIGC_CANARY_PLAN_JSON"))
    if args.plan_only:
        payload = plan_receipt(plan)
    else:
        decision = GovernanceDecision.model_validate(
            _load_json(args.governance, "AIGC_CANARY_GOVERNANCE_JSON")
        )
        permit = ExecutionPermit.model_validate(
            _load_json(args.permit, "AIGC_CANARY_PERMIT_JSON")
        )
        attestation = AuthorityAttestation.model_validate(
            _load_json(
                args.authority_attestation,
                "AIGC_CANARY_AUTHORITY_ATTESTATION_JSON",
            )
        )
        job_name = os.environ.get("CLOUD_RUN_JOB", "").strip()
        execution_name = os.environ.get("CLOUD_RUN_EXECUTION", "").strip()
        if not job_name or not execution_name:
            raise CanaryConfigurationError(
                "live canary execution requires Cloud Run job/execution identity"
            )
        task_index = os.environ.get("CLOUD_RUN_TASK_INDEX", "")
        task_attempt = os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "")
        task_count = os.environ.get("CLOUD_RUN_TASK_COUNT", "")
        if (task_index, task_attempt, task_count) != ("0", "0", "1"):
            raise CanaryConfigurationError(
                "live canary requires exactly one first-attempt Cloud Run task"
            )
        now = datetime.now(timezone.utc)
        result = execute_canary(
            plan,
            decision=decision,
            permit=permit,
            attestation=attestation,
            job_name=job_name,
            execution_name=execution_name,
            authoritative_now=now,
        )
        invocation = build_invocation(plan, permit_id=permit.permit_id)
        payload = canary_execution_receipt(
            plan,
            invocation=invocation,
            permit=permit,
            attestation=attestation,
            result=result,
            job_name=job_name,
            execution_name=execution_name,
            captured_at=now,
        )

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("AIGC_CANARY_RECEIPT:" + encoded)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CanaryConfigurationError, ValueError) as exc:
        raise SystemExit(f"Nexus provider canary blocked: {exc}") from exc
