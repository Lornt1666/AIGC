from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import jwt

from src.domain.identity import (
    IdentityDenialReason,
    ProviderRevocationEvidence,
    ProviderSubjectBinding,
    ProviderSubjectState,
    RuntimeAuthority,
)
from src.infrastructure.identity import (
    CachedGooglePublicKeyProvider,
    GoogleIdentityPlatformAdapter,
    IdentityPlatformConfigurationError,
    IdentityPlatformSettings,
    PublicKeyEvidence,
    evaluate_identity_platform_policy,
    load_identity_platform_policy,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "production_identity_platform_baseline.json"
SCHEMA_PATH = ROOT / "schemas" / "production_identity_platform_baseline.schema.json"


def certificate_material() -> tuple[Any, str]:
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "AIGC Offline Identity Test")]
    )
    current = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(signing_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(current - timedelta(minutes=5))
        .not_valid_after(current + timedelta(days=1))
        .sign(signing_key, hashes.SHA256())
    )
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM).decode(
        "utf-8"
    )
    return signing_key, certificate_pem


class StaticKeyProvider:
    def __init__(self, certificate_pem: str) -> None:
        self.certificate_pem = certificate_pem
        self.requests: list[str] = []

    def resolve_key(self, *, key_id: str, now: datetime) -> PublicKeyEvidence:
        self.requests.append(key_id)
        return PublicKeyEvidence(
            key_id=key_id,
            certificate_pem=self.certificate_pem,
            evidence_id="EVID-GIP-KEY-OFFLINE",
            expires_at=now + timedelta(hours=1),
        )


class StaticSubjectResolver:
    def __init__(self, binding: ProviderSubjectBinding | None) -> None:
        self.binding = binding
        self.requests: list[tuple[str, str]] = []

    def resolve_subject(
        self,
        *,
        provider_binding_id: str,
        provider_subject: str,
    ) -> ProviderSubjectBinding | None:
        self.requests.append((provider_binding_id, provider_subject))
        return self.binding


class StaticRevocationResolver:
    def __init__(self, *, active: bool) -> None:
        self.active = active
        self.requests: list[tuple[str, str]] = []

    def check_subject(
        self,
        *,
        provider_binding_id: str,
        provider_subject: str,
        authentication_time: datetime,
        now: datetime,
    ) -> ProviderRevocationEvidence:
        del authentication_time
        self.requests.append((provider_binding_id, provider_subject))
        return ProviderRevocationEvidence(
            provider_binding_id=provider_binding_id,
            provider_subject=provider_subject,
            active=self.active,
            checked_at=now,
            evidence_id="EVID-GIP-REVOCATION-OFFLINE",
        )


def settings(*, configured: bool = True) -> IdentityPlatformSettings:
    policy = load_identity_platform_policy(POLICY_PATH, SCHEMA_PATH)
    value = IdentityPlatformSettings.from_policy(policy)
    return replace(value, project_id="aigc-test-project" if configured else None)


def binding(*, state: ProviderSubjectState = ProviderSubjectState.ACTIVE) -> ProviderSubjectBinding:
    return ProviderSubjectBinding(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-001",
        principal_id="principal-a",
        membership_id="membership-a",
        tenant_id="tenant-primary",
        project_id="project-a",
        state=state,
        evidence_ids=("EVID-SUBJECT-MAPPING-OFFLINE",),
    )


def claims(
    now: datetime,
    *,
    audience: str = "aigc-test-project",
    issuer: str = "https://securetoken.google.com/aigc-test-project",
    sign_in_provider: str = "google.com",
    expires_delta: timedelta = timedelta(minutes=10),
) -> dict[str, Any]:
    return {
        "aud": audience,
        "iss": issuer,
        "sub": "provider-subject-001",
        "iat": int((now - timedelta(seconds=30)).timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "auth_time": int((now - timedelta(minutes=1)).timestamp()),
        "email": "operator@example.invalid",
        "email_verified": True,
        "firebase": {"sign_in_provider": sign_in_provider},
        "roles": ["administrator"],
        "scopes": ["untrusted:scope"],
    }


def signed_assertion(
    signing_key: Any,
    value: dict[str, Any],
    *,
    key_id: str = "offline-key-1",
) -> str:
    return jwt.encode(
        value,
        signing_key,
        algorithm="RS256",
        headers={"kid": key_id},
    )


def adapter(
    certificate_pem: str,
    *,
    configured: bool = True,
    subject_binding: ProviderSubjectBinding | None = None,
    active: bool = True,
) -> GoogleIdentityPlatformAdapter:
    return GoogleIdentityPlatformAdapter(
        settings=settings(configured=configured),
        public_key_provider=StaticKeyProvider(certificate_pem),
        subject_resolver=StaticSubjectResolver(
            binding() if subject_binding is None else subject_binding
        ),
        revocation_resolver=StaticRevocationResolver(active=active),
    )


def test_identity_policy_is_internal_and_provider_unconfigured() -> None:
    policy = load_identity_platform_policy(POLICY_PATH, SCHEMA_PATH)
    evaluation = evaluate_identity_platform_policy(policy)

    assert evaluation.implemented_internal is True
    assert evaluation.production_complete is False
    assert evaluation.configured_project is False
    assert "identity_platform_project_id" in evaluation.unresolved_configuration
    assert "session_pepper_secret_project" in evaluation.unresolved_configuration
    assert "provider_subject_mapping_repository" in evaluation.unresolved_configuration
    assert "production_session_repository" in evaluation.unresolved_configuration
    assert evaluation.provider_configuration_authorized is False
    assert evaluation.secret_access_authorized is False
    assert evaluation.user_onboarding_authorized is False
    assert evaluation.production_identity_activation_authorized is False
    assert evaluation.production_deployment_authorized is False
    assert evaluation.external_action_performed is False


def test_valid_google_assertion_returns_minimum_necessary_provider_evidence() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signing_key, certificate_pem = certificate_material()
    verification = adapter(certificate_pem).verify(
        {
            "signed_assertion": signed_assertion(
                signing_key,
                claims(now),
            )
        },
        now=now,
    )

    assert verification.verified is True
    assert verification.principal_id == "principal-a"
    assert verification.provider_binding_id == "identity-platform:aigc-test-project"
    assert verification.runtime_authority is RuntimeAuthority.PRODUCTION_VERIFIED
    assert verification.identity_assurance.value == "IAL1"
    assert verification.authentication_assurance.value == "AAL1"
    assert verification.federation_assurance.value == "FAL1"
    assert verification.evidence_maturity.value == "EA2_SEMANTICALLY_TESTED"
    serialized = str(verification)
    assert "operator@example.invalid" not in serialized
    assert "administrator" not in serialized
    assert "untrusted:scope" not in serialized
    assert "signed_assertion" not in serialized


def test_unconfigured_project_fails_before_public_key_resolution() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signing_key, certificate_pem = certificate_material()
    key_provider = StaticKeyProvider(certificate_pem)
    value = GoogleIdentityPlatformAdapter(
        settings=settings(configured=False),
        public_key_provider=key_provider,
        subject_resolver=StaticSubjectResolver(binding()),
        revocation_resolver=StaticRevocationResolver(active=True),
    ).verify(
        {"signed_assertion": signed_assertion(signing_key, claims(now))},
        now=now,
    )

    assert value.verified is False
    assert IdentityDenialReason.PROVIDER_VERIFICATION_FAILED in value.denial_reasons
    assert key_provider.requests == []


def test_wrong_audience_provider_expiry_mapping_and_revocation_fail_closed() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signing_key, certificate_pem = certificate_material()

    wrong_audience = adapter(certificate_pem).verify(
        {
            "signed_assertion": signed_assertion(
                signing_key,
                claims(now, audience="other-project"),
            )
        },
        now=now,
    )
    wrong_provider = adapter(certificate_pem).verify(
        {
            "signed_assertion": signed_assertion(
                signing_key,
                claims(now, sign_in_provider="password"),
            )
        },
        now=now,
    )
    expired = adapter(certificate_pem).verify(
        {
            "signed_assertion": signed_assertion(
                signing_key,
                claims(now, expires_delta=timedelta(seconds=-1)),
            )
        },
        now=now,
    )
    missing_mapping = adapter(
        certificate_pem,
        subject_binding=ProviderSubjectBinding(
            provider_binding_id="identity-platform:aigc-test-project",
            provider_subject="provider-subject-001",
            principal_id="principal-a",
            membership_id="membership-a",
            tenant_id="tenant-primary",
            project_id="project-a",
            state=ProviderSubjectState.REVOKED,
            evidence_ids=("EVID-SUBJECT-MAPPING-REVOKED",),
        ),
    ).verify(
        {"signed_assertion": signed_assertion(signing_key, claims(now))},
        now=now,
    )
    revoked = adapter(certificate_pem, active=False).verify(
        {"signed_assertion": signed_assertion(signing_key, claims(now))},
        now=now,
    )

    assert wrong_audience.verified is False
    assert wrong_provider.verified is False
    assert IdentityDenialReason.PROVIDER_NOT_ALLOWED in wrong_provider.denial_reasons
    assert expired.verified is False
    assert IdentityDenialReason.PROVIDER_ASSERTION_EXPIRED in expired.denial_reasons
    assert missing_mapping.verified is False
    assert IdentityDenialReason.MEMBERSHIP_MISSING in missing_mapping.denial_reasons
    assert revoked.verified is False
    assert IdentityDenialReason.MEMBERSHIP_REVOKED in revoked.denial_reasons


class FakeTransport:
    def __init__(self, certificate_pem: str) -> None:
        self.certificate_pem = certificate_pem
        self.calls = 0

    def fetch(self, endpoint: str) -> tuple[dict[str, str], int]:
        assert endpoint.startswith("https://www.googleapis.com/")
        self.calls += 1
        return {"offline-key-1": self.certificate_pem}, 3600


def test_public_key_provider_caches_certificates_and_rejects_unknown_key() -> None:
    _, certificate_pem = certificate_material()
    transport = FakeTransport(certificate_pem)
    provider = CachedGooglePublicKeyProvider(
        endpoint=(
            "https://www.googleapis.com/robot/v1/metadata/x509/"
            "securetoken@system.gserviceaccount.com"
        ),
        transport=transport,
    )
    now = datetime.now(timezone.utc)

    first = provider.resolve_key(key_id="offline-key-1", now=now)
    second = provider.resolve_key(
        key_id="offline-key-1",
        now=now + timedelta(minutes=5),
    )

    assert first.certificate_pem == second.certificate_pem
    assert first.evidence_id == second.evidence_id
    assert transport.calls == 1

    try:
        provider.resolve_key(key_id="unknown-key", now=now + timedelta(minutes=6))
    except IdentityPlatformConfigurationError:
        pass
    else:
        raise AssertionError("Unknown Identity Platform key ID must fail closed")
    assert transport.calls == 2
