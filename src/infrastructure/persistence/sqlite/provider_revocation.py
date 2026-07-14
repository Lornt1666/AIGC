from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

from src.domain.identity.production_sessions import ProviderRevocationEvidence

from .connection import SQLiteConnectionFactory


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat()


def _parse(value: object) -> datetime:
    return _utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def _evidence_id(
    provider_binding_id: str,
    provider_subject: str,
    disabled: bool,
    valid_after: datetime,
    checked_at: datetime,
) -> str:
    material = "|".join(
        (
            provider_binding_id,
            provider_subject,
            str(disabled),
            _iso(valid_after),
            _iso(checked_at),
        )
    )
    return "EVID-PROVIDER-REVOCATION-" + sha256(
        material.encode("utf-8")
    ).hexdigest()[:20].upper()


class SQLiteProviderRevocationRepository:
    """Minimum-necessary provider revocation cache for offline/staging tests."""

    def __init__(
        self,
        factory: SQLiteConnectionFactory,
        *,
        max_cache_age_seconds: int = 300,
    ) -> None:
        if max_cache_age_seconds <= 0:
            raise ValueError("Provider revocation cache age must be positive")
        self.factory = factory
        self.max_cache_age_seconds = max_cache_age_seconds

    def put(
        self,
        *,
        provider_binding_id: str,
        provider_subject: str,
        disabled: bool,
        valid_after: datetime,
        checked_at: datetime,
        expected_revision: int | None = None,
    ) -> ProviderRevocationEvidence:
        valid = _utc(valid_after)
        checked = _utc(checked_at)
        evidence_id = _evidence_id(
            provider_binding_id,
            provider_subject,
            disabled,
            valid,
            checked,
        )
        with self.factory.transaction() as connection:
            row = connection.execute(
                """
                SELECT revision FROM provider_subject_revocation_state
                WHERE provider_binding_id = ? AND provider_subject = ?
                """,
                (provider_binding_id, provider_subject),
            ).fetchone()
            if row is None:
                if expected_revision not in (None, 0):
                    raise RuntimeError("Provider revocation revision conflict")
                connection.execute(
                    """
                    INSERT INTO provider_subject_revocation_state(
                        provider_binding_id,
                        provider_subject,
                        disabled,
                        valid_after,
                        checked_at,
                        evidence_id,
                        revision
                    ) VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        provider_binding_id,
                        provider_subject,
                        1 if disabled else 0,
                        _iso(valid),
                        _iso(checked),
                        evidence_id,
                    ),
                )
            else:
                revision = int(row["revision"])
                if expected_revision is None or revision != expected_revision:
                    raise RuntimeError("Provider revocation revision conflict")
                cursor = connection.execute(
                    """
                    UPDATE provider_subject_revocation_state
                    SET disabled = ?, valid_after = ?, checked_at = ?,
                        evidence_id = ?, revision = ?
                    WHERE provider_binding_id = ? AND provider_subject = ?
                      AND revision = ?
                    """,
                    (
                        1 if disabled else 0,
                        _iso(valid),
                        _iso(checked),
                        evidence_id,
                        revision + 1,
                        provider_binding_id,
                        provider_subject,
                        revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Provider revocation state changed concurrently")
        return ProviderRevocationEvidence(
            provider_binding_id=provider_binding_id,
            provider_subject=provider_subject,
            active=not disabled,
            checked_at=checked,
            evidence_id=evidence_id,
        )

    def check_subject(
        self,
        *,
        provider_binding_id: str,
        provider_subject: str,
        authentication_time: datetime,
        now: datetime,
    ) -> ProviderRevocationEvidence:
        current = _utc(now)
        authenticated = _utc(authentication_time)
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM provider_subject_revocation_state
                WHERE provider_binding_id = ? AND provider_subject = ?
                """,
                (provider_binding_id, provider_subject),
            ).fetchone()
        if row is None:
            missing_evidence_id = "EVID-PROVIDER-REVOCATION-MISSING-" + sha256(
                (provider_binding_id + "|" + provider_subject).encode("utf-8")
            ).hexdigest()[:20].upper()
            return ProviderRevocationEvidence(
                provider_binding_id=provider_binding_id,
                provider_subject=provider_subject,
                active=False,
                checked_at=current,
                evidence_id=missing_evidence_id,
            )

        checked_at = _parse(row["checked_at"])
        valid_after = _parse(row["valid_after"])
        disabled = bool(row["disabled"])
        fresh = current <= checked_at + timedelta(
            seconds=self.max_cache_age_seconds
        )
        active = not disabled and fresh and authenticated >= valid_after
        return ProviderRevocationEvidence(
            provider_binding_id=provider_binding_id,
            provider_subject=provider_subject,
            active=active,
            checked_at=checked_at,
            evidence_id=str(row["evidence_id"]),
        )
