from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.application import (
    HmacSessionCredentialDigester,
    ProductionSessionError,
    ProductionSessionService,
)
from src.domain.identity import (
    AuthenticationAssuranceLevel,
    EvidenceMaturity,
    FederationAssuranceLevel,
    IdentityAssuranceLevel,
    IdentityProviderClass,
    ProviderSubjectBinding,
    ProviderSubjectState,
    ProviderVerification,
    RuntimeAuthority,
)
from src.infrastructure.persistence.sqlite import (
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteProductionSessionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "sqlite"
NOW = datetime(2026, 7, 14, 4, 0, tzinfo=timezone.utc)
SESSION_CREDENTIAL = "session-credential-echo-0123456789-abcdefghijklmnopqrstuvwxyz"


def repository(tmp_path: Path) -> SQLiteProductionSessionRepository:
    factory = SQLiteConnectionFactory(tmp_path / "session-evidence.sqlite3")
    SQLiteMigrator(factory, MIGRATIONS).apply_all()
    return SQLiteProductionSessionRepository(factory)


def binding() -> ProviderSubjectBinding:
    return ProviderSubjectBinding(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-001",
        principal_id="principal-a",
        membership_id="membership-a",
        tenant_id="tenant-primary",
        project_id="project-a",
        state=ProviderSubjectState.ACTIVE,
        evidence_ids=("EVID-SUBJECT-MAPPING-OFFLINE",),
    )


def verification() -> ProviderVerification:
    return ProviderVerification(
        provider_class=IdentityProviderClass.OIDC,
        provider_binding_id="identity-platform:aigc-test-project",
        assertion_id="gip-current-evidence",
        issuer="https://securetoken.google.com/aigc-test-project",
        subject="provider-subject-001",
        principal_id="principal-a",
        audiences=("aigc-test-project",),
        issued_at=NOW - timedelta(seconds=30),
        expires_at=NOW + timedelta(minutes=10),
        nonce_digest=None,
        claims_digest="b" * 64,
        identity_assurance=IdentityAssuranceLevel.IAL1,
        authentication_assurance=AuthenticationAssuranceLevel.AAL1,
        federation_assurance=FederationAssuranceLevel.FAL1,
        evidence_maturity=EvidenceMaturity.EA2_SEMANTICALLY_TESTED,
        runtime_authority=RuntimeAuthority.PRODUCTION_VERIFIED,
        verified=True,
        evidence_ids=("EVID-GIP-OFFLINE",),
    )


def service(tmp_path: Path) -> ProductionSessionService:
    return ProductionSessionService(
        repository=repository(tmp_path),
        digester=HmacSessionCredentialDigester(bytes(range(32))),
        idle_timeout_seconds=1800,
        absolute_timeout_seconds=3600,
        credential_factory=lambda: SESSION_CREDENTIAL,
    )


def test_authentication_renews_idle_window_and_revision(tmp_path: Path) -> None:
    current_service = service(tmp_path)
    issued = current_service.issue(
        verification=verification(),
        binding=binding(),
        now=NOW,
    )
    authenticated = current_service.authenticate(
        issued.session_credential,
        now=NOW + timedelta(minutes=10),
        expected_tenant_id="tenant-primary",
        expected_project_id="project-a",
    )

    assert authenticated.revision == 2
    assert authenticated.last_seen_at == NOW + timedelta(minutes=10)
    assert authenticated.idle_expires_at == NOW + timedelta(minutes=40)
    assert authenticated.absolute_expires_at == NOW + timedelta(minutes=60)


def test_idle_renewal_never_exceeds_absolute_expiry(tmp_path: Path) -> None:
    current_service = service(tmp_path)
    issued = current_service.issue(
        verification=verification(),
        binding=binding(),
        now=NOW,
    )
    first_renewal = current_service.authenticate(
        issued.session_credential,
        now=NOW + timedelta(minutes=25),
    )
    authenticated = current_service.authenticate(
        issued.session_credential,
        now=NOW + timedelta(minutes=50),
    )

    assert first_renewal.idle_expires_at == NOW + timedelta(minutes=55)
    assert authenticated.idle_expires_at == issued.record.absolute_expires_at
    assert authenticated.revision == 3


def test_expired_future_wrong_provider_and_wrong_subject_evidence_is_rejected(
    tmp_path: Path,
) -> None:
    current_service = service(tmp_path)
    cases = (
        (
            replace(verification(), expires_at=NOW),
            binding(),
            "expired",
        ),
        (
            replace(verification(), issued_at=NOW + timedelta(minutes=2)),
            binding(),
            "future",
        ),
        (
            replace(
                verification(),
                provider_binding_id="identity-platform:other-project",
            ),
            binding(),
            "binding",
        ),
        (
            replace(verification(), subject="provider-subject-other"),
            binding(),
            "subject",
        ),
    )

    for provider_evidence, subject_binding, expected_message in cases:
        with pytest.raises(ProductionSessionError, match=expected_message):
            current_service.issue(
                verification=provider_evidence,
                binding=subject_binding,
                now=NOW,
            )
