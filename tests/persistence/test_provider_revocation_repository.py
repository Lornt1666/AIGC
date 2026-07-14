from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.infrastructure.persistence.sqlite import (
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteProviderRevocationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "sqlite"
NOW = datetime(2026, 7, 14, 5, 0, tzinfo=timezone.utc)


def repository(tmp_path: Path) -> SQLiteProviderRevocationRepository:
    factory = SQLiteConnectionFactory(tmp_path / "revocation.sqlite3")
    SQLiteMigrator(factory, MIGRATIONS).apply_all()
    return SQLiteProviderRevocationRepository(
        factory,
        max_cache_age_seconds=300,
    )


def test_missing_revocation_evidence_fails_closed(tmp_path: Path) -> None:
    evidence = repository(tmp_path).check_subject(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-001",
        authentication_time=NOW - timedelta(minutes=1),
        now=NOW,
    )

    assert evidence.active is False
    assert evidence.evidence_id.startswith("EVID-PROVIDER-REVOCATION-MISSING-")


def test_current_active_revocation_state_allows_post_valid_after_authentication(
    tmp_path: Path,
) -> None:
    current = repository(tmp_path)
    stored = current.put(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-001",
        disabled=False,
        valid_after=NOW - timedelta(hours=1),
        checked_at=NOW,
    )
    checked = current.check_subject(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-001",
        authentication_time=NOW - timedelta(minutes=1),
        now=NOW + timedelta(minutes=1),
    )

    assert stored.active is True
    assert checked.active is True
    assert checked.evidence_id == stored.evidence_id


def test_disabled_stale_or_pre_revocation_authentication_fails_closed(
    tmp_path: Path,
) -> None:
    current = repository(tmp_path)
    current.put(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-disabled",
        disabled=True,
        valid_after=NOW - timedelta(hours=1),
        checked_at=NOW,
    )
    current.put(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-stale",
        disabled=False,
        valid_after=NOW - timedelta(hours=1),
        checked_at=NOW - timedelta(minutes=10),
    )
    current.put(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-revoked-before-auth",
        disabled=False,
        valid_after=NOW,
        checked_at=NOW,
    )

    disabled = current.check_subject(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-disabled",
        authentication_time=NOW - timedelta(minutes=1),
        now=NOW + timedelta(minutes=1),
    )
    stale = current.check_subject(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-stale",
        authentication_time=NOW - timedelta(minutes=1),
        now=NOW,
    )
    revoked_before_auth = current.check_subject(
        provider_binding_id="identity-platform:aigc-test-project",
        provider_subject="provider-subject-revoked-before-auth",
        authentication_time=NOW - timedelta(minutes=1),
        now=NOW + timedelta(minutes=1),
    )

    assert disabled.active is False
    assert stale.active is False
    assert revoked_before_auth.active is False
