from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker
import jwt

from src.domain.identity import (
    AuthenticationAssuranceLevel,
    EvidenceMaturity,
    FederationAssuranceLevel,
    IdentityAssuranceLevel,
    IdentityDenialReason,
    IdentityProviderClass,
    ProviderVerification,
    RuntimeAuthority,
)
from src.domain.identity.production_sessions import (
    ProviderRevocationResolver,
    ProviderSubjectBindingResolver,
    ProviderSubjectState,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = ROOT / "config" / "production_identity_platform_baseline.json"
DEFAULT_SCHEMA_PATH = ROOT / "schemas" / "production_identity_platform_baseline.schema.json"
_CACHE_MAX_AGE = re.compile(r"(?:^|,)\s*max-age=(\d+)\s*(?:,|$)", flags=re.IGNORECASE)
_ALLOWED_ASSERTION_KEYS = {"signed_assertion"}
_MAX_ASSERTION_BYTES = 65536


class IdentityPlatformConfigurationError(ValueError):
    """Raised when Identity Platform configuration cannot safely verify assertions."""


@dataclass(frozen=True)
class IdentityPlatformSettings:
    project_id: str | None
    provider_tenant_id: str | None
    issuer_template: str
    public_keys_endpoint: str
    algorithm: str
    accepted_sign_in_providers: tuple[str, ...]
    clock_skew_seconds: int
    max_token_age_seconds: int
    evidence_maturity: EvidenceMaturity
    aigc_tenant_id: str

    @classmethod
    def from_policy(cls, policy: Mapping[str, Any]) -> "IdentityPlatformSettings":
        provider = dict(policy["provider"])
        tenant = dict(policy["tenant_isolation"])
        return cls(
            project_id=(
                str(provider["project_id"])
                if provider.get("project_id") is not None
                else None
            ),
            provider_tenant_id=(
                str(provider["provider_tenant_id"])
                if provider.get("provider_tenant_id") is not None
                else None
            ),
            issuer_template=str(provider["issuer_template"]),
            public_keys_endpoint=str(provider["public_keys_endpoint"]),
            algorithm=str(provider["algorithm"]),
            accepted_sign_in_providers=tuple(
                str(value) for value in provider["accepted_sign_in_providers"]
            ),
            clock_skew_seconds=int(provider["clock_skew_seconds"]),
            max_token_age_seconds=int(provider["max_token_age_seconds"]),
            evidence_maturity=EvidenceMaturity(str(provider["evidence_maturity"])),
            aigc_tenant_id=str(tenant["aigc_tenant_id"]),
        )

    @property
    def configured(self) -> bool:
        return bool(self.project_id)

    @property
    def issuer(self) -> str:
        if not self.project_id:
            raise IdentityPlatformConfigurationError(
                "Identity Platform project ID remains unresolved"
            )
        return self.issuer_template.format(project_id=self.project_id)

    @property
    def provider_binding_id(self) -> str:
        return (
            f"identity-platform:{self.project_id}"
            if self.project_id
            else "identity-platform:unconfigured"
        )


@dataclass(frozen=True)
class PublicKeyEvidence:
    key_id: str
    certificate_pem: str
    evidence_id: str
    expires_at: datetime


class PublicKeyProvider(Protocol):
    def resolve_key(self, *, key_id: str, now: datetime) -> PublicKeyEvidence: ...


class PublicKeyTransport(Protocol):
    def fetch(self, endpoint: str) -> tuple[dict[str, str], int]: ...


class GoogleX509Transport:
    """Fetch Google Secure Token public certificates without credentials."""

    def __init__(self, *, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, endpoint: str) -> tuple[dict[str, str], int]:
        if not endpoint.startswith("https://www.googleapis.com/"):
            raise IdentityPlatformConfigurationError(
                "Identity Platform public-key endpoint is not allowlisted"
            )
        request = Request(
            endpoint,
            method="GET",
            headers={"Accept": "application/json", "User-Agent": "AIGC/1.0"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                cache_control = str(response.headers.get("Cache-Control") or "")
        except Exception as exc:
            raise IdentityPlatformConfigurationError(
                "Identity Platform public keys could not be retrieved"
            ) from exc
        if not isinstance(payload, dict) or not payload:
            raise IdentityPlatformConfigurationError(
                "Identity Platform public-key response is invalid"
            )
        certificates = {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(key, str)
            and isinstance(value, str)
            and value.startswith("-----BEGIN CERTIFICATE-----")
        }
        if not certificates:
            raise IdentityPlatformConfigurationError(
                "Identity Platform public-key response contains no certificates"
            )
        match = _CACHE_MAX_AGE.search(cache_control)
        max_age = int(match.group(1)) if match else 300
        return certificates, max(60, min(max_age, 86400))


class CachedGooglePublicKeyProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        transport: PublicKeyTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.transport = transport or GoogleX509Transport()
        self._certificates: dict[str, str] = {}
        self._expires_at = datetime.fromtimestamp(0, timezone.utc)

    def resolve_key(self, *, key_id: str, now: datetime) -> PublicKeyEvidence:
        current = _utc(now)
        if current >= self._expires_at or key_id not in self._certificates:
            certificates, max_age = self.transport.fetch(self.endpoint)
            self._certificates = certificates
            self._expires_at = current + timedelta(seconds=max_age)
        certificate = self._certificates.get(key_id)
        if certificate is None:
            raise IdentityPlatformConfigurationError(
                "Identity Platform assertion key ID is not trusted"
            )
        evidence_id = "EVID-GIP-KEY-" + sha256(
            (key_id + "|" + certificate).encode("utf-8")
        ).hexdigest()[:20].upper()
        return PublicKeyEvidence(
            key_id=key_id,
            certificate_pem=certificate,
            evidence_id=evidence_id,
            expires_at=self._expires_at,
        )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timestamp(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value), timezone.utc)


def _digest_mapping(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def load_identity_platform_policy(
    policy_path: str | Path = DEFAULT_POLICY_PATH,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    try:
        policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityPlatformConfigurationError(
            "Unable to load the Identity Platform production baseline"
        ) from exc
    if not isinstance(policy, dict) or not isinstance(schema, dict):
        raise IdentityPlatformConfigurationError(
            "Identity Platform policy and schema must be JSON objects"
        )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(policy), key=lambda item: list(item.absolute_path))
    if errors:
        messages: list[str] = []
        for error in errors[:10]:
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        raise IdentityPlatformConfigurationError(
            "Identity Platform production baseline validation failed: "
            + "; ".join(messages)
        )
    return policy


@dataclass(frozen=True)
class ProductionIdentityEvaluation:
    status: str
    implemented_internal: bool
    production_complete: bool
    configured_project: bool
    blocking_evidence: tuple[str, ...]
    unresolved_configuration: tuple[str, ...]
    provider_configuration_authorized: bool
    secret_access_authorized: bool
    user_onboarding_authorized: bool
    production_identity_activation_authorized: bool
    production_deployment_authorized: bool
    external_action_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-PRODUCTION-IDENTITY-EVALUATION-001",
            "contract_version": "1.0.0",
            "status": self.status,
            "implemented_internal": self.implemented_internal,
            "production_complete": self.production_complete,
            "configured_project": self.configured_project,
            "blocking_evidence": list(self.blocking_evidence),
            "unresolved_configuration": list(self.unresolved_configuration),
            "provider_configuration_authorized": self.provider_configuration_authorized,
            "secret_access_authorized": self.secret_access_authorized,
            "user_onboarding_authorized": self.user_onboarding_authorized,
            "production_identity_activation_authorized": (
                self.production_identity_activation_authorized
            ),
            "production_deployment_authorized": self.production_deployment_authorized,
            "external_action_performed": self.external_action_performed,
        }


def evaluate_identity_platform_policy(
    policy: Mapping[str, Any],
) -> ProductionIdentityEvaluation:
    value = dict(policy)
    provider = dict(value["provider"])
    evidence = dict(value["operational_evidence"])
    authority = dict(value["authority"])
    blocking = tuple(
        name
        for name, observed in evidence.items()
        if observed is not True
    )
    unresolved: list[str] = []
    if provider.get("project_id") is None:
        unresolved.append("identity_platform_project_id")
    if "TBD_" in value["sessions"]["pepper_reference"]:
        unresolved.append("session_pepper_secret_project")
    if value["subject_mapping"]["mapping_repository_status"] != "VERIFIED":
        unresolved.append("provider_subject_mapping_repository")
    if value["sessions"]["repository_status"] != "VERIFIED":
        unresolved.append("production_session_repository")

    implemented = (
        value.get("status")
        == "IMPLEMENTED_INTERNAL_PENDING_PROVIDER_AND_STAGING_EVIDENCE"
        and authority.get("adapter_implementation_authorized") is True
        and authority.get("offline_cryptographic_testing_authorized") is True
        and value.get("external_action_performed") is False
    )
    complete = implemented and not blocking and not unresolved
    return ProductionIdentityEvaluation(
        status="complete" if complete else "implemented_internal",
        implemented_internal=implemented,
        production_complete=complete,
        configured_project=provider.get("project_id") is not None,
        blocking_evidence=blocking,
        unresolved_configuration=tuple(unresolved),
        provider_configuration_authorized=bool(
            authority.get("provider_configuration_authorized")
        ),
        secret_access_authorized=bool(authority.get("secret_access_authorized")),
        user_onboarding_authorized=bool(authority.get("user_onboarding_authorized")),
        production_identity_activation_authorized=bool(
            authority.get("production_identity_activation_authorized")
        ),
        production_deployment_authorized=bool(
            authority.get("production_deployment_authorized")
        ),
    )


class GoogleIdentityPlatformAdapter:
    provider_class = IdentityProviderClass.OIDC

    def __init__(
        self,
        *,
        settings: IdentityPlatformSettings,
        public_key_provider: PublicKeyProvider,
        subject_resolver: ProviderSubjectBindingResolver,
        revocation_resolver: ProviderRevocationResolver,
    ) -> None:
        self.settings = settings
        self.public_key_provider = public_key_provider
        self.subject_resolver = subject_resolver
        self.revocation_resolver = revocation_resolver
        self.provider_binding_id = settings.provider_binding_id

    def verify(
        self,
        raw_assertion: Mapping[str, Any],
        *,
        now: datetime,
    ) -> ProviderVerification:
        current = _utc(now)
        assertion = dict(raw_assertion) if isinstance(raw_assertion, Mapping) else {}
        unknown = set(assertion) - _ALLOWED_ASSERTION_KEYS
        signed_assertion = assertion.get("signed_assertion")
        assertion_digest = sha256(
            str(signed_assertion or "missing").encode("utf-8")
        ).hexdigest()
        assertion_id = "gip-" + assertion_digest[:24]
        if unknown or not isinstance(signed_assertion, str):
            reasons = [IdentityDenialReason.MALFORMED_ASSERTION]
            if unknown:
                reasons.append(IdentityDenialReason.ROLE_SOURCE_UNTRUSTED)
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=tuple(reasons),
            )
        if not signed_assertion or len(signed_assertion.encode("utf-8")) > _MAX_ASSERTION_BYTES:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.MALFORMED_ASSERTION,),
            )
        if not self.settings.configured:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,),
            )

        try:
            header = jwt.get_unverified_header(signed_assertion)
            if header.get("alg") != self.settings.algorithm:
                raise IdentityPlatformConfigurationError(
                    "Identity Platform assertion algorithm is not allowed"
                )
            key_id = str(header.get("kid") or "")
            if not key_id:
                raise IdentityPlatformConfigurationError(
                    "Identity Platform assertion lacks a key ID"
                )
            key_evidence = self.public_key_provider.resolve_key(
                key_id=key_id,
                now=current,
            )
            claims = jwt.decode(
                signed_assertion,
                key_evidence.certificate_pem,
                algorithms=[self.settings.algorithm],
                audience=self.settings.project_id,
                issuer=self.settings.issuer,
                leeway=self.settings.clock_skew_seconds,
                options={
                    "require": [
                        "exp",
                        "iat",
                        "sub",
                        "auth_time",
                        "firebase",
                        "email",
                        "email_verified",
                    ]
                },
            )
        except jwt.ExpiredSignatureError:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_ASSERTION_EXPIRED,),
            )
        except Exception:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,),
            )

        subject = str(claims.get("sub") or "")
        if not subject or len(subject) > 128:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,),
            )
        issued_at = _timestamp(claims["iat"])
        expires_at = _timestamp(claims["exp"])
        authentication_time = _timestamp(claims["auth_time"])
        if issued_at > current + timedelta(seconds=self.settings.clock_skew_seconds):
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,),
            )
        if authentication_time > current + timedelta(seconds=self.settings.clock_skew_seconds):
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,),
            )
        if (current - authentication_time).total_seconds() > self.settings.max_token_age_seconds:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.SESSION_TOO_OLD,),
            )

        firebase_claim = claims.get("firebase")
        if not isinstance(firebase_claim, Mapping):
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,),
            )
        sign_in_provider = str(firebase_claim.get("sign_in_provider") or "")
        if sign_in_provider not in set(self.settings.accepted_sign_in_providers):
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_NOT_ALLOWED,),
            )
        provider_tenant = firebase_claim.get("tenant")
        if self.settings.provider_tenant_id is not None and provider_tenant != self.settings.provider_tenant_id:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.TENANT_MISMATCH,),
            )
        if claims.get("email_verified") is not True or not str(claims.get("email") or ""):
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,),
            )

        binding = self.subject_resolver.resolve_subject(
            provider_binding_id=self.provider_binding_id,
            provider_subject=subject,
        )
        if binding is None or binding.state is not ProviderSubjectState.ACTIVE:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.MEMBERSHIP_MISSING,),
            )
        if binding.tenant_id != self.settings.aigc_tenant_id:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.TENANT_MISMATCH,),
            )

        revocation = self.revocation_resolver.check_subject(
            provider_binding_id=self.provider_binding_id,
            provider_subject=subject,
            authentication_time=authentication_time,
            now=current,
        )
        if not revocation.active:
            return self._denied(
                current=current,
                assertion_id=assertion_id,
                reasons=(IdentityDenialReason.MEMBERSHIP_REVOKED,),
            )

        minimum_claims = {
            "iss": str(claims.get("iss") or ""),
            "aud": claims.get("aud"),
            "sub_digest": sha256(subject.encode("utf-8")).hexdigest(),
            "iat": int(claims["iat"]),
            "exp": int(claims["exp"]),
            "auth_time": int(claims["auth_time"]),
            "sign_in_provider": sign_in_provider,
            "provider_tenant": provider_tenant,
            "email_verified": True,
        }
        nonce_digest = (
            sha256(str(claims["nonce"]).encode("utf-8")).hexdigest()
            if claims.get("nonce") is not None
            else None
        )
        audience = claims.get("aud")
        audiences = (
            tuple(str(value) for value in audience)
            if isinstance(audience, list)
            else (str(audience),)
        )
        evidence_ids = tuple(
            dict.fromkeys(
                (
                    key_evidence.evidence_id,
                    *binding.evidence_ids,
                    revocation.evidence_id,
                )
            )
        )
        return ProviderVerification(
            provider_class=self.provider_class,
            provider_binding_id=self.provider_binding_id,
            assertion_id=assertion_id,
            issuer=self.settings.issuer,
            subject=subject,
            principal_id=binding.principal_id,
            audiences=audiences,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce_digest=nonce_digest,
            claims_digest=_digest_mapping(minimum_claims),
            identity_assurance=IdentityAssuranceLevel.IAL1,
            authentication_assurance=AuthenticationAssuranceLevel.AAL1,
            federation_assurance=FederationAssuranceLevel.FAL1,
            evidence_maturity=self.settings.evidence_maturity,
            runtime_authority=RuntimeAuthority.PRODUCTION_VERIFIED,
            verified=True,
            evidence_ids=evidence_ids,
        )

    def _denied(
        self,
        *,
        current: datetime,
        assertion_id: str,
        reasons: tuple[IdentityDenialReason, ...],
    ) -> ProviderVerification:
        return ProviderVerification(
            provider_class=self.provider_class,
            provider_binding_id=self.provider_binding_id,
            assertion_id=assertion_id,
            issuer=(self.settings.issuer if self.settings.configured else ""),
            subject="unknown",
            principal_id=None,
            audiences=(),
            issued_at=current,
            expires_at=current,
            nonce_digest=None,
            claims_digest=sha256(assertion_id.encode("utf-8")).hexdigest(),
            identity_assurance=IdentityAssuranceLevel.IAL0,
            authentication_assurance=AuthenticationAssuranceLevel.AAL0,
            federation_assurance=FederationAssuranceLevel.FAL0,
            evidence_maturity=EvidenceMaturity.EA0_CLAIMED,
            runtime_authority=RuntimeAuthority.LOCAL_SIMULATION,
            verified=False,
            evidence_ids=(),
            denial_reasons=tuple(dict.fromkeys(reasons)),
        )
