from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from src.domain.identity import (
    AuthenticationAssuranceLevel,
    EvidenceMaturity,
    FederationAssuranceLevel,
    IdentityAssuranceLevel,
    IdentityDecision,
    IdentityEvidenceReceipt,
    IdentityProviderClass,
    RuntimeAuthority,
)
from src.infrastructure.persistence.sqlite import (
    SQLiteConnectionFactory,
    SQLiteIdentityEvidenceReceiptRepository,
    SQLiteMigrator,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "sqlite"
NOW = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)


def prepared(tmp_path: Path) -> SQLiteConnectionFactory:
    factory = SQLiteConnectionFactory(tmp_path / "identity.sqlite3")
    SQLiteMigrator(factory, MIGRATIONS).apply_all()
    return factory


def receipt(
    *,
    receipt_id: str = "IDR-" + "A" * 24,
    request_digest: str = "b" * 64,
    replay_key_digest: str = "c" * 64,
) -> IdentityEvidenceReceipt:
    return IdentityEvidenceReceipt(
        receipt_id=receipt_id,
        request_digest=request_digest,
        replay_key_digest=replay_key_digest,
        result=IdentityDecision.PERMIT,
        reason_codes=(),
        provider_class=IdentityProviderClass.LOCAL_DEVELOPMENT,
        provider_binding_id="aigc-local-development-fixture-v1",
        assertion_id="assertion-a",
        principal_id="principal-a",
        membership_id="membership-a",
        session_id="session-a",
        tenant_id="tenant-a",
        project_id="project-a",
        identity_assurance=IdentityAssuranceLevel.IAL0,
        authentication_assurance=AuthenticationAssuranceLevel.AAL0,
        federation_assurance=FederationAssuranceLevel.FAL0,
        evidence_maturity=EvidenceMaturity.EA1_SCHEMA_VALID,
        runtime_authority=RuntimeAuthority.LOCAL_SIMULATION,
        exact_revision="LOCAL_UNVERIFIED",
        evidence_ids=("EVID-PRINCIPAL-A",),
        production_mode=False,
        created_at=NOW,
        expires_at=datetime(2027, 7, 11, tzinfo=timezone.utc),
        retention_class="IDENTITY_EVIDENCE_90D",
    )


def test_identity_receipt_survives_repository_restart(tmp_path: Path) -> None:
    factory = prepared(tmp_path)
    first = SQLiteIdentityEvidenceReceiptRepository(factory)
    stored = first.append(receipt())

    restarted = SQLiteIdentityEvidenceReceiptRepository(
        SQLiteConnectionFactory(factory.database_path)
    )
    assert restarted.get(stored.receipt_id) == stored
    assert restarted.get_by_replay_key(stored.replay_key_digest) == stored


def test_identity_receipt_is_immutable_and_append_only(tmp_path: Path) -> None:
    factory = prepared(tmp_path)
    repository = SQLiteIdentityEvidenceReceiptRepository(factory)
    stored = repository.append(receipt())

    with pytest.raises(ValueError, match="immutable"):
        repository.append(
            receipt(
                receipt_id=stored.receipt_id,
                request_digest="d" * 64,
                replay_key_digest="e" * 64,
            )
        )
    with factory.connect() as connection:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                """
                UPDATE identity_evidence_receipts
                SET result = 'DENY'
                WHERE receipt_id = ?
                """,
                (stored.receipt_id,),
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                """
                DELETE FROM identity_evidence_receipts
                WHERE receipt_id = ?
                """,
                (stored.receipt_id,),
            )


def test_identity_receipt_storage_contains_no_raw_secret_material(
    tmp_path: Path,
) -> None:
    factory = prepared(tmp_path)
    repository = SQLiteIdentityEvidenceReceiptRepository(factory)
    repository.append(receipt())

    with factory.connect() as connection:
        payload = connection.execute(
            """
            SELECT receipt_json FROM identity_evidence_receipts
            LIMIT 1
            """
        ).fetchone()["receipt_json"]

    assert "access_token" not in payload
    assert "refresh_token" not in payload
    assert "client_secret" not in payload
    assert "provider_claims" not in payload
    assert '"nonce"' not in payload
