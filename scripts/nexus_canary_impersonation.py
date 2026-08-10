from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Callable, TypeVar

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from jsonschema import Draft202012Validator, FormatChecker

from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.operations.nexus_provider_canary import (
    CANARY_AUTHORITY_ALGORITHM,
    KmsAuthorityPublicKey,
    authority_public_key_sha256,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "nexus_canary_jit_impersonation_receipt.schema.json"
SCHEMA_VERSION = "aigc.nexus-canary-jit-impersonation-receipt.v1"
REGION = "northamerica-northeast1"
MAXIMUM_GRANT_LIFETIME = timedelta(minutes=15)
ErrorT = TypeVar("ErrorT", bound=RuntimeError)


def adc_source_principal(
    credentials: Any, *, error_type: type[ErrorT]
) -> tuple[Any, str]:
    from google.auth.compute_engine.credentials import Credentials as ComputeCredentials

    if not isinstance(credentials, ComputeCredentials):
        raise _fail(
            error_type,
            "ADC source is not a directly attached keyless Compute metadata identity; "
            "key-backed, workforce, and delegated sources are prohibited",
        )
    source_type = f"{type(credentials).__module__}.{type(credentials).__qualname__}"
    if source_type != "google.auth.compute_engine.credentials.Credentials":
        raise _fail(error_type, "ADC metadata source credential type is not canonical")
    principal = str(getattr(credentials, "service_account_email", None) or "")
    if not principal.endswith(".iam.gserviceaccount.com") or "@" not in principal:
        raise _fail(
            error_type,
            "attached metadata source service-account identity is not observable",
        )
    return credentials, principal


def bounded_impersonated_session(
    *,
    expected_target: str,
    expected_source: str,
    authority_expires_at: datetime,
    error_type: type[ErrorT],
) -> tuple[Any, dict[str, Any]]:
    import google.auth
    from google.auth import impersonated_credentials
    from google.auth.compute_engine.credentials import Credentials as ComputeCredentials
    from google.auth.transport.requests import Request
    import requests
    from requests.adapters import HTTPAdapter

    credentials, _ = google.auth.default(
        scopes=("https://www.googleapis.com/auth/cloud-platform",)
    )
    if (
        not isinstance(credentials, ComputeCredentials)
        or f"{type(credentials).__module__}.{type(credentials).__qualname__}"
        != "google.auth.compute_engine.credentials.Credentials"
    ):
        adc_source_principal(credentials, error_type=error_type)
    try:
        credentials.refresh(Request())
    except Exception as exc:
        raise _fail(error_type, "attached metadata source refresh failed", exc)
    source, source_principal = adc_source_principal(
        credentials, error_type=error_type
    )
    if source_principal != expected_source:
        raise _fail(error_type, "ADC source/target impersonation provenance mismatch")
    now = datetime.now(timezone.utc)
    expiry = authority_expires_at.astimezone(timezone.utc)
    remaining = int((expiry - now).total_seconds())
    if remaining < 1:
        raise _fail(error_type, "impersonation authority expired before token mint")
    lifetime = min(900, remaining)
    bounded = impersonated_credentials.Credentials(
        source_credentials=source,
        target_principal=expected_target,
        target_scopes=("https://www.googleapis.com/auth/cloud-platform",),
        lifetime=lifetime,
    )
    try:
        bounded.refresh(Request())
    except Exception as exc:
        raise _fail(error_type, "bounded impersonated token mint failed", exc)
    token_expiry = getattr(bounded, "expiry", None)
    if (
        token_expiry is None
        or token_expiry.tzinfo is None
        or token_expiry.astimezone(timezone.utc) > expiry
        or (token_expiry.astimezone(timezone.utc) - now).total_seconds() > 900
    ):
        raise _fail(error_type, "impersonated token lifetime exceeds signed authority")
    token = str(getattr(bounded, "token", None) or "")
    if not token:
        raise _fail(error_type, "bounded impersonated token mint returned no token")
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=0))
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session, {
        "adc_impersonation_target": expected_target,
        "adc_impersonation_target_verified": True,
        "adc_source_principal": source_principal,
        "adc_source_credential_type": (
            f"{type(source).__module__}.{type(source).__qualname__}"
        ),
        "adc_source_keyless_verified": True,
        "attached_metadata_source_verified": True,
        "bounded_token_lifetime_seconds": lifetime,
        "bounded_token_expires_at": token_expiry.astimezone(timezone.utc).isoformat(),
        "bounded_token_refresh_permitted": False,
        "service_account_key_used": False,
    }


def jit_request_sha256(
    *,
    action: str,
    project_id: str,
    target_principal: str,
    target_resource: str,
    governed_permit_id: str,
) -> str:
    return canonical_sha256(
        {
            "action": action,
            "project_id": project_id,
            "region": REGION,
            "target_principal": target_principal,
            "target_resource": target_resource,
            "governed_permit_id": governed_permit_id,
        }
    )


def verify_kms_signed_payload(
    payload: dict[str, Any],
    *,
    expected_kms_key_version: str,
    fetch_public_key: Callable[[str], KmsAuthorityPublicKey],
    error_type: type[ErrorT],
    label: str,
) -> None:
    try:
        public = fetch_public_key(expected_kms_key_version)
        observed_public_sha = authority_public_key_sha256(public.public_key_pem)
        key = serialization.load_pem_public_key(public.public_key_pem.encode("utf-8"))
    except Exception as exc:
        raise _fail(error_type, f"{label} KMS public key is invalid", exc)
    if (
        public.kms_key_version != expected_kms_key_version
        or public.algorithm != CANARY_AUTHORITY_ALGORITHM
        or not isinstance(key, rsa.RSAPublicKey)
        or key.key_size != 2048
        or not hmac.compare_digest(public.public_key_sha256, observed_public_sha)
        or not hmac.compare_digest(
            str(payload.get("public_key_sha256") or ""), observed_public_sha
        )
        or payload.get("kms_key_version") != expected_kms_key_version
        or payload.get("signing_algorithm") != CANARY_AUTHORITY_ALGORITHM
    ):
        raise _fail(error_type, f"{label} KMS trust-root evidence mismatch")
    try:
        signature = base64.b64decode(str(payload.get("signature_b64") or ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _fail(error_type, f"{label} signature is not canonical base64", exc)
    if base64.b64encode(signature).decode("ascii") != payload.get("signature_b64"):
        raise _fail(error_type, f"{label} signature is not canonical base64")
    signed = {key_: value for key_, value in payload.items() if key_ != "signature_b64"}
    digest = hashlib.sha256(canonical_json_bytes(signed)).digest()
    try:
        key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise _fail(error_type, f"{label} KMS signature verification failed", exc)


def _fail(error_type: type[ErrorT], message: str, cause: Exception | None = None) -> ErrorT:
    error = error_type(message)
    if cause is not None:
        error.__cause__ = cause
    return error


def _aware(value: Any, *, field: str, error_type: type[ErrorT]) -> datetime:
    if not isinstance(value, str):
        raise _fail(error_type, f"JIT impersonation receipt {field} must be RFC 3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _fail(
            error_type,
            f"JIT impersonation receipt {field} must be RFC 3339",
            exc,
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _fail(error_type, f"JIT impersonation receipt {field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def validate_jit_impersonation_receipt(
    receipt: dict[str, Any],
    *,
    action: str,
    project_id: str,
    target_principal: str,
    target_resource: str,
    governed_permit_id: str,
    request_sha256: str,
    expected_kms_key_version: str,
    fetch_public_key: Callable[[str], KmsAuthorityPublicKey],
    error_type: type[ErrorT],
    authoritative_now: datetime | None = None,
) -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(receipt),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise _fail(
            error_type,
            f"JIT impersonation receipt schema mismatch at {path}: {errors[0].message}",
        )
    expected = {
        "schema_version": SCHEMA_VERSION,
        "action": action,
        "project_id": project_id,
        "region": REGION,
        "target_principal": target_principal,
        "target_service_account_resource": f"projects/-/serviceAccounts/{target_principal}",
        "target_resource": target_resource,
        "governed_permit_id": governed_permit_id,
        "request_sha256": request_sha256,
        "role": "roles/iam.serviceAccountTokenCreator",
        "grant_scope": "exact_target_service_account",
        "grant_observed": True,
        "source_authority_verified": True,
        "account_level_grant": False,
        "service_account_key_used": False,
        "workload_identity_federation_used": False,
        "revocation_required": True,
        "revoked_at": None,
        "kms_key_version": expected_kms_key_version,
        "signing_algorithm": CANARY_AUTHORITY_ALGORITHM,
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise _fail(error_type, f"JIT impersonation receipt is not bound to exact {field}")
    if receipt["source_principal"] == target_principal:
        raise _fail(error_type, "JIT impersonation source and target must be distinct")
    now = (authoritative_now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    issued = _aware(receipt["issued_at"], field="issued_at", error_type=error_type)
    not_before = _aware(receipt["not_before"], field="not_before", error_type=error_type)
    expires = _aware(receipt["expires_at"], field="expires_at", error_type=error_type)
    expected_condition = (
        'request.time < timestamp("'
        + expires.isoformat().replace("+00:00", "Z")
        + '")'
    )
    if receipt.get("grant_condition_expression") != expected_condition:
        raise _fail(
            error_type,
            "JIT impersonation grant is not conditionally bounded to its expiry",
        )
    if not (issued <= not_before <= now < expires):
        raise _fail(error_type, "JIT impersonation receipt is outside its active window")
    if expires - issued > MAXIMUM_GRANT_LIFETIME:
        raise _fail(error_type, "JIT impersonation grant lifetime exceeds 15 minutes")
    try:
        public = fetch_public_key(expected_kms_key_version)
        observed_public_sha = authority_public_key_sha256(public.public_key_pem)
        key = serialization.load_pem_public_key(public.public_key_pem.encode("utf-8"))
    except Exception as exc:
        raise _fail(error_type, "JIT impersonation KMS public key is invalid", exc)
    if (
        public.kms_key_version != expected_kms_key_version
        or public.algorithm != CANARY_AUTHORITY_ALGORITHM
        or not isinstance(key, rsa.RSAPublicKey)
        or key.key_size != 2048
        or not hmac.compare_digest(public.public_key_sha256, observed_public_sha)
        or not hmac.compare_digest(receipt["public_key_sha256"], observed_public_sha)
    ):
        raise _fail(error_type, "JIT impersonation KMS trust-root evidence mismatch")
    try:
        signature = base64.b64decode(receipt["signature_b64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _fail(error_type, "JIT impersonation signature is not canonical base64", exc)
    if base64.b64encode(signature).decode("ascii") != receipt["signature_b64"]:
        raise _fail(error_type, "JIT impersonation signature is not canonical base64")
    signed = {key_: value for key_, value in receipt.items() if key_ != "signature_b64"}
    digest = hashlib.sha256(canonical_json_bytes(signed)).digest()
    try:
        key.verify(
            signature,
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise _fail(error_type, "JIT impersonation KMS signature verification failed", exc)
    return {
        "jit_grant_receipt_id": receipt["receipt_id"],
        "jit_grant_receipt_sha256": canonical_sha256(receipt),
        "jit_source_principal": receipt["source_principal"],
        "jit_target_principal": target_principal,
        "jit_target_resource": target_resource,
        "jit_grant_scope": "exact_target_service_account",
        "jit_account_level_grant": False,
        "jit_service_account_key_used": False,
        "jit_wif_used": False,
        "jit_revocation_required": True,
        "jit_expires_at": expires.isoformat(),
        "jit_grant_condition_expression": expected_condition,
    }
