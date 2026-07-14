from __future__ import annotations

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
from src.domain.identity.production_sessions import ProductionSessionState
from src.infrastructure.persistence.sqlite import (
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteProductionSessionRepository,
    SQLiteProviderSubjectBindingRepository,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "sqlite"
NOW = datetime(2026, 7, 14, 3, 0, tzinfo=timezone.utc)


def prepared(tmp_path: Path) -> SQLiteConnectionFactory:
    factory = SQLiteConnectionFactory(tmp_path / "identity-sessions.sqlite3")
    SQLiteMigrator(factory, MIGRATIONS).apply_all()
    return factory


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
        assertion_id="gip-assertion-offline",
        issuer="https://securetoken.google.com/aigc-test-project",
        subject="provider-subject-001",
        principal_id="principal-a",
        audiences=("aigc-test-project",),
        issued_at=NOW - timedelta(seconds=30),
        expires_at=NOW + timedelta(minutes=10),
        nonce_digest=None,
        claims_digest="a" * 64,
        identity_assurance=IdentityAssuranceLevel.IAL1,
        authentication_assurance=AuthenticationAssuranceLevel.AAL1,
        federation_assurance=FederationAssuranceLevel.FAL1,
        evidence_maturity=EvidenceMaturity.EA2_SEMANTICALLY_TESTED,
        runtime_authority=RuntimeAuthority.PRODUCTION_VERIFIED,
        verified=True,
        evidence_ids=("EVID-GIP-KEY-OFFLINE", "EVID-GIP-REVOCATION-OFFLINE"),
    )


def service(
    repository: SQLiteProductionSessionRepository,
    credentials: list[str],
) -> ProductionSessionService:
    iterator = iter(credentials)
    return ProductionSessionService(
        repository=repository,
        digester=HmacSessionCredentialDigester(bytes(range(32))),
        idle_timeout_seconds=1800,
        absolute_timeout_seconds=43200,
        credential_factory=lambda: next(iterator),
    )


def test_subject_mapping_and_session_survive_restart_without_raw_identity_claims(
    tmp_path: Path,
) -> None:
    factory = prepared(tmp_path)
    mappings = SQLiteProviderSubjectBindingRepository(factory)
    stored_binding = mappings.put(binding(), now=NOW)
    sessions = SQLiteProductionSessionRepository(factory)
    issued = service(
        sessions,
        ["session-credential-alpha-0123456789-abcdefghijklmnopqrstuvwxyz"],
    ).issue(
        verification=verification(),
        binding=stored_binding,
        now=NOW,
    )

    assert issued.record.state is ProductionSessionState.ACTIVE
    assert issued.record.credential_digest != issued.session_credential
    assert len(issued.record.credential_digest) == 64
    assert stored_binding.principal_id == "principal-a"

    with factory.connect() as connection:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(provider_subject_bindings)"
            ).fetchall()
        }
        session_row = connection.execute(
            "SELECT * FROM production_identity_sessions WHERE session_id = ?",
            (issued.record.session_id,),
        ).fetchone()
    assert "email" not in columns
    assert "provider_claims" not in columns
    assert issued.session_credential not in str(dict(session_row))

    restarted_factory = SQLiteConnectionFactory(factory.database_path)
    restarted_mappings = SQLiteProviderSubjectBindingRepository(restarted_factory)
    restarted_sessions = SQLiteProductionSessionRepository(restarted_factory)
    recovered_binding = restarted_mappings.resolve_subject(
        provider_binding_id=stored_binding.provider_binding_id,
        provider_subject=stored_binding.provider_subject,
    )
    recovered_session = ProductionSessionService(
        repository=restarted_sessions,
        digester=HmacSessionCredentialDigester(bytes(range(32))),
    ).authenticate(
        issued.session_credential,
        now=NOW + timedelta(minutes=5),
        expected_tenant_id="tenant-primary",
        expected_project_id="project-a",
    )

    assert recovered_binding == stored_binding
    assert recovered_session.session_id == issued.record.session_id


def test_session_rotation_invalidates_old_credential_and_binds_replacement(
    tmp_path: Path,
) -> None:
    factory = prepared(tmp_path)
    mappings = SQLiteProviderSubjectBindingRepository(factory)
    stored_binding = mappings.put(binding(), now=NOW)
    repository = SQLiteProductionSessionRepository(factory)
    session_service = service(
        repository,
        [
            "session-credential-alpha-0123456789-abcdefghijklmnopqrstuvwxyz",
            "session-credential-bravo-0123456789-abcdefghijklmnopqrstuvwxyz",
        ],
    )
    issued = session_service.issue(
        verification=verification(),
        binding=stored_binding,
        now=NOW,
    )
    rotated = session_service.rotate(
        issued.session_credential,
        verification=verification(),
        binding=stored_binding,
        now=NOW + timedelta(minutes=10),
    )

    old_record = repository.get(issued.record.session_id)
    assert old_record is not None
    assert old_record.state is ProductionSessionState.ROTATED
    assert old_record.revision == 2
    assert rotated.record.rotated_from_session_id == issued.record.session_id
    assert rotated.record.state is ProductionSessionState.ACTIVE

    with pytest.raises(ProductionSessionError, match="not active"):
        session_service.authenticate(
            issued.session_credential,
            now=NOW + timedelta(minutes=11),
        )
    assert session_service.authenticate(
        rotated.session_credential,
        now=NOW + timedelta(minutes=11),
    ).session_id == rotated.record.session_id


def test_session_revocation_expiry_and_context_mismatch_fail_closed(
    tmp_path: Path,
) -> None:
    factory = prepared(tmp_path)
    repository = SQLiteProductionSessionRepository(factory)
    session_service = service(
        repository,
        ["session-credential-charlie-0123456789-abcdefghijklmnopqrstuvwxyz"],
    )
    issued = session_service.issue(
        verification=verification(),
        binding=binding(),
        now=NOW,
    )

    with pytest.raises(ProductionSessionError, match="tenant mismatch"):
        session_service.authenticate(
            issued.session_credential,
            now=NOW + timedelta(minutes=1),
            expected_tenant_id="tenant-other",
        )
    with pytest.raises(ProductionSessionError, match="project mismatch"):
        session_service.authenticate(
            issued.session_credential,
            now=NOW + timedelta(minutes=1),
            expected_project_id="project-other",
        )
    with pytest.raises(ProductionSessionError, match="expired"):
        session_service.authenticate(
            issued.session_credential,
            now=NOW + timedelta(minutes=31),
        )

    revoked = session_service.revoke(
        issued.session_credential,
        reason="Accountable operator ended the local test session.",
        now=NOW + timedelta(minutes=5),
    )
    assert revoked.state is ProductionSessionState.REVOKED
    assert revoked.revision == 2
    assert revoked.revocation_reason

    with pytest.raises(ProductionSessionError, match="not active"):
        session_service.authenticate(
            issued.session_credential,
            now=NOW + timedelta(minutes=6),
        )


def test_unverified_or_mismatched_provider_evidence_cannot_issue_session(
    tmp_path: Path,
) -> None:
    repository = SQLiteProductionSessionRepository(prepared(tmp_path))
    session_service = service(
        repository,
        ["session-credential-delta-0123456789-abcdefghijklmnopqrstuvwxyz"],
    )
    invalid = verification()
    invalid = ProviderVerification(
        **{
            **invalid.__dict__,
            "verified": False,
            "runtime_authority": RuntimeAuthority.LOCAL_SIMULATION,
        }
    )

    with pytest.raises(ProductionSessionError, match="Verified provider evidence"):
        session_service.issue(
            verification=invalid,
            binding=binding(),
            now=NOW,
        )

    other_binding = ProviderSubjectBinding(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-001",
        principal_id="principal-other",
        membership_id="membership-other",
        tenant_id="tenant-primary",
        project_id="project-a",
        state=ProviderSubjectState.ACTIVE,
        evidence_ids=("EVID-SUBJECT-MAPPING-OTHER",),
    )
    with pytest.raises(ProductionSessionError, match="principal"):
        session_service.issue(
            verification=verification(),
            binding=other_binding,
            now=NOW,
        )
