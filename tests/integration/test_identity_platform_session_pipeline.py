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

from src.application import (
    HmacSessionCredentialDigester,
    ProductionSessionService,
)
from src.domain.identity import ProviderSubjectBinding, ProviderSubjectState
from src.infrastructure.identity import (
    GoogleIdentityPlatformAdapter,
    IdentityPlatformSettings,
    PublicKeyEvidence,
    load_identity_platform_policy,
)
from src.infrastructure.persistence.sqlite import (
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteProductionSessionRepository,
    SQLiteProviderRevocationRepository,
    SQLiteProviderSubjectBindingRepository,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "sqlite"
POLICY_PATH = ROOT / "config" / "production_identity_platform_baseline.json"
SCHEMA_PATH = ROOT / "schemas" / "production_identity_platform_baseline.schema.json"
NOW = datetime.now(timezone.utc).replace(microsecond=0)
SESSION_CREDENTIAL = "session-credential-foxtrot-0123456789-abcdefghijklmnopqrstuvwxyz"


def signing_material() -> tuple[Any, str]:
    private_signing_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "AIGC Offline Pipeline Test")]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_signing_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - timedelta(minutes=5))
        .not_valid_after(NOW + timedelta(days=1))
        .sign(private_signing_key, hashes.SHA256())
    )
    return private_signing_key, certificate.public_bytes(
        serialization.Encoding.PEM
    ).decode("utf-8")


class StaticKeyProvider:
    def __init__(self, certificate_pem: str) -> None:
        self.certificate_pem = certificate_pem

    def resolve_key(self, *, key_id: str, now: datetime) -> PublicKeyEvidence:
        assert key_id == "offline-pipeline-key"
        return PublicKeyEvidence(
            key_id=key_id,
            certificate_pem=self.certificate_pem,
            evidence_id="EVID-GIP-KEY-PIPELINE",
            expires_at=now + timedelta(hours=1),
        )


def test_signed_assertion_to_durable_session_survives_restart(tmp_path: Path) -> None:
    factory = SQLiteConnectionFactory(tmp_path / "identity-pipeline.sqlite3")
    SQLiteMigrator(factory, MIGRATIONS).apply_all()
    subject_repository = SQLiteProviderSubjectBindingRepository(factory)
    revocation_repository = SQLiteProviderRevocationRepository(factory)
    session_repository = SQLiteProductionSessionRepository(factory)

    policy = load_identity_platform_policy(POLICY_PATH, SCHEMA_PATH)
    settings = replace(
        IdentityPlatformSettings.from_policy(policy),
        project_id="aigc-test-project",
    )
    subject_repository.put(
        ProviderSubjectBinding(
            provider_binding_id=settings.provider_binding_id,
            provider_subject="provider-subject-pipeline",
            principal_id="principal-a",
            membership_id="membership-a",
            tenant_id="tenant-primary",
            project_id="project-a",
            state=ProviderSubjectState.ACTIVE,
            evidence_ids=("EVID-SUBJECT-PIPELINE",),
        ),
        now=NOW,
    )
    revocation_repository.put(
        provider_binding_id=settings.provider_binding_id,
        provider_subject="provider-subject-pipeline",
        disabled=False,
        valid_after=NOW - timedelta(hours=1),
        checked_at=NOW,
    )

    private_signing_key, certificate_pem = signing_material()
    claims = {
        "aud": "aigc-test-project",
        "iss": "https://securetoken.google.com/aigc-test-project",
        "sub": "provider-subject-pipeline",
        "iat": int((NOW - timedelta(seconds=30)).timestamp()),
        "exp": int((NOW + timedelta(minutes=10)).timestamp()),
        "auth_time": int((NOW - timedelta(minutes=1)).timestamp()),
        "email": "operator@example.invalid",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    signed_assertion = jwt.encode(
        claims,
        private_signing_key,
        algorithm="RS256",
        headers={"kid": "offline-pipeline-key"},
    )
    adapter = GoogleIdentityPlatformAdapter(
        settings=settings,
        public_key_provider=StaticKeyProvider(certificate_pem),
        subject_resolver=subject_repository,
        revocation_resolver=revocation_repository,
    )
    verification = adapter.verify(
        {"signed_assertion": signed_assertion},
        now=NOW,
    )
    assert verification.verified is True

    resolved_binding = subject_repository.resolve_subject(
        provider_binding_id=settings.provider_binding_id,
        provider_subject="provider-subject-pipeline",
    )
    assert resolved_binding is not None
    session_service = ProductionSessionService(
        repository=session_repository,
        digester=HmacSessionCredentialDigester(bytes(range(32))),
        credential_factory=lambda: SESSION_CREDENTIAL,
    )
    issued = session_service.issue(
        verification=verification,
        binding=resolved_binding,
        now=NOW,
    )

    assert issued.record.principal_id == "principal-a"
    assert issued.record.tenant_id == "tenant-primary"
    assert issued.record.project_id == "project-a"
    assert issued.record.credential_digest != issued.session_credential
    assert "operator@example.invalid" not in str(issued.record)
    assert signed_assertion not in str(issued.record)

    restarted_factory = SQLiteConnectionFactory(factory.database_path)
    restarted_service = ProductionSessionService(
        repository=SQLiteProductionSessionRepository(restarted_factory),
        digester=HmacSessionCredentialDigester(bytes(range(32))),
    )
    recovered = restarted_service.authenticate(
        issued.session_credential,
        now=NOW + timedelta(minutes=5),
        expected_tenant_id="tenant-primary",
        expected_project_id="project-a",
    )

    assert recovered.session_id == issued.record.session_id
    assert recovered.revision == 2
