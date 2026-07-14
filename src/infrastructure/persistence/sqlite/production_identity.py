from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

from src.domain.identity import AuthenticationAssuranceLevel
from src.domain.identity.production_sessions import (
    ProductionSessionRecord,
    ProductionSessionState,
    ProviderSubjectBinding,
    ProviderSubjectState,
)

from .connection import SQLiteConnectionFactory


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return _utc(value).isoformat() if value is not None else None


def _parse(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return _utc(parsed)


def _binding(row: sqlite3.Row) -> ProviderSubjectBinding:
    return ProviderSubjectBinding(
        provider_binding_id=str(row["provider_binding_id"]),
        provider_subject=str(row["provider_subject"]),
        principal_id=str(row["principal_id"]),
        membership_id=str(row["membership_id"]),
        tenant_id=str(row["tenant_id"]),
        project_id=str(row["project_id"]),
        state=ProviderSubjectState(str(row["state"])),
        evidence_ids=tuple(json.loads(row["evidence_ids_json"])),
    )


def _session(row: sqlite3.Row) -> ProductionSessionRecord:
    return ProductionSessionRecord(
        session_id=str(row["session_id"]),
        credential_digest=str(row["credential_digest"]),
        principal_id=str(row["principal_id"]),
        membership_id=str(row["membership_id"]),
        tenant_id=str(row["tenant_id"]),
        project_id=str(row["project_id"]),
        state=ProductionSessionState(str(row["state"])),
        authentication_assurance=AuthenticationAssuranceLevel(
            str(row["authentication_assurance"])
        ),
        issued_at=_parse(row["issued_at"]),
        last_seen_at=_parse(row["last_seen_at"]),
        idle_expires_at=_parse(row["idle_expires_at"]),
        absolute_expires_at=_parse(row["absolute_expires_at"]),
        revision=int(row["revision"]),
        evidence_ids=tuple(json.loads(row["evidence_ids_json"])),
        rotated_from_session_id=(
            str(row["rotated_from_session_id"])
            if row["rotated_from_session_id"] is not None
            else None
        ),
        revoked_at=(
            _parse(row["revoked_at"]) if row["revoked_at"] is not None else None
        ),
        revocation_reason=(
            str(row["revocation_reason"])
            if row["revocation_reason"] is not None
            else None
        ),
    )


class SQLiteProviderSubjectBindingRepository:
    """Trusted provider-subject mappings without email or provider claim storage."""

    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self.factory = factory

    def resolve_subject(
        self,
        *,
        provider_binding_id: str,
        provider_subject: str,
    ) -> ProviderSubjectBinding | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM provider_subject_bindings
                WHERE provider_binding_id = ? AND provider_subject = ?
                """,
                (provider_binding_id, provider_subject),
            ).fetchone()
        return _binding(row) if row else None

    def put(
        self,
        binding: ProviderSubjectBinding,
        *,
        expected_revision: int | None = None,
        now: datetime | None = None,
    ) -> ProviderSubjectBinding:
        current = _utc(now or datetime.now(timezone.utc))
        evidence_json = json.dumps(list(binding.evidence_ids), sort_keys=True)
        with self.factory.transaction() as connection:
            row = connection.execute(
                """
                SELECT revision FROM provider_subject_bindings
                WHERE provider_binding_id = ? AND provider_subject = ?
                """,
                (binding.provider_binding_id, binding.provider_subject),
            ).fetchone()
            if row is None:
                if expected_revision not in (None, 0):
                    raise RuntimeError("Provider subject mapping revision conflict")
                connection.execute(
                    """
                    INSERT INTO provider_subject_bindings(
                        provider_binding_id,
                        provider_subject,
                        principal_id,
                        membership_id,
                        tenant_id,
                        project_id,
                        state,
                        evidence_ids_json,
                        created_at,
                        updated_at,
                        revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        binding.provider_binding_id,
                        binding.provider_subject,
                        binding.principal_id,
                        binding.membership_id,
                        binding.tenant_id,
                        binding.project_id,
                        binding.state.value,
                        evidence_json,
                        _iso(current),
                        _iso(current),
                    ),
                )
            else:
                revision = int(row["revision"])
                if expected_revision is None or revision != expected_revision:
                    raise RuntimeError("Provider subject mapping revision conflict")
                cursor = connection.execute(
                    """
                    UPDATE provider_subject_bindings
                    SET principal_id = ?, membership_id = ?, tenant_id = ?,
                        project_id = ?, state = ?, evidence_ids_json = ?,
                        updated_at = ?, revision = ?
                    WHERE provider_binding_id = ? AND provider_subject = ?
                      AND revision = ?
                    """,
                    (
                        binding.principal_id,
                        binding.membership_id,
                        binding.tenant_id,
                        binding.project_id,
                        binding.state.value,
                        evidence_json,
                        _iso(current),
                        revision + 1,
                        binding.provider_binding_id,
                        binding.provider_subject,
                        revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Provider subject mapping changed concurrently")
        stored = self.resolve_subject(
            provider_binding_id=binding.provider_binding_id,
            provider_subject=binding.provider_subject,
        )
        if stored is None:
            raise RuntimeError("Provider subject mapping was not persisted")
        return stored


class SQLiteProductionSessionRepository:
    """Durable session storage containing only credential digests."""

    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self.factory = factory

    def create(self, record: ProductionSessionRecord) -> ProductionSessionRecord:
        with self.factory.transaction() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO production_identity_sessions(
                        session_id,
                        credential_digest,
                        principal_id,
                        membership_id,
                        tenant_id,
                        project_id,
                        state,
                        authentication_assurance,
                        issued_at,
                        last_seen_at,
                        idle_expires_at,
                        absolute_expires_at,
                        revision,
                        evidence_ids_json,
                        rotated_from_session_id,
                        revoked_at,
                        revocation_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.session_id,
                        record.credential_digest,
                        record.principal_id,
                        record.membership_id,
                        record.tenant_id,
                        record.project_id,
                        record.state.value,
                        record.authentication_assurance.value,
                        _iso(record.issued_at),
                        _iso(record.last_seen_at),
                        _iso(record.idle_expires_at),
                        _iso(record.absolute_expires_at),
                        record.revision,
                        json.dumps(list(record.evidence_ids), sort_keys=True),
                        record.rotated_from_session_id,
                        _iso(record.revoked_at),
                        record.revocation_reason,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise RuntimeError("Production session already exists") from exc
        stored = self.get_by_credential_digest(record.credential_digest)
        if stored is None:
            raise RuntimeError("Production session was not persisted")
        return stored

    def get_by_credential_digest(
        self,
        credential_digest: str,
    ) -> ProductionSessionRecord | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM production_identity_sessions
                WHERE credential_digest = ?
                """,
                (credential_digest,),
            ).fetchone()
        return _session(row) if row else None

    def get(self, session_id: str) -> ProductionSessionRecord | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM production_identity_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return _session(row) if row else None

    def rotate(
        self,
        *,
        current_session_id: str,
        current_revision: int,
        new_record: ProductionSessionRecord,
        rotated_at: datetime,
    ) -> tuple[ProductionSessionRecord, ProductionSessionRecord]:
        current_time = _utc(rotated_at)
        with self.factory.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM production_identity_sessions
                WHERE session_id = ?
                """,
                (current_session_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Production session not found")
            existing = _session(row)
            if existing.revision != current_revision:
                raise RuntimeError("Production session revision conflict")
            if existing.state is not ProductionSessionState.ACTIVE:
                raise RuntimeError("Only an active production session may rotate")
            cursor = connection.execute(
                """
                UPDATE production_identity_sessions
                SET state = 'ROTATED', revoked_at = ?,
                    revocation_reason = 'ROTATED', revision = ?
                WHERE session_id = ? AND revision = ? AND state = 'ACTIVE'
                """,
                (
                    _iso(current_time),
                    current_revision + 1,
                    current_session_id,
                    current_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Production session changed concurrently")
            connection.execute(
                """
                INSERT INTO production_identity_sessions(
                    session_id,
                    credential_digest,
                    principal_id,
                    membership_id,
                    tenant_id,
                    project_id,
                    state,
                    authentication_assurance,
                    issued_at,
                    last_seen_at,
                    idle_expires_at,
                    absolute_expires_at,
                    revision,
                    evidence_ids_json,
                    rotated_from_session_id,
                    revoked_at,
                    revocation_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_record.session_id,
                    new_record.credential_digest,
                    new_record.principal_id,
                    new_record.membership_id,
                    new_record.tenant_id,
                    new_record.project_id,
                    new_record.state.value,
                    new_record.authentication_assurance.value,
                    _iso(new_record.issued_at),
                    _iso(new_record.last_seen_at),
                    _iso(new_record.idle_expires_at),
                    _iso(new_record.absolute_expires_at),
                    new_record.revision,
                    json.dumps(list(new_record.evidence_ids), sort_keys=True),
                    new_record.rotated_from_session_id,
                    _iso(new_record.revoked_at),
                    new_record.revocation_reason,
                ),
            )
        rotated = self.get(current_session_id)
        replacement = self.get(new_record.session_id)
        if rotated is None or replacement is None:
            raise RuntimeError("Production session rotation did not persist")
        return rotated, replacement

    def revoke(
        self,
        *,
        session_id: str,
        expected_revision: int,
        revoked_at: datetime,
        reason: str,
    ) -> ProductionSessionRecord:
        normalized_reason = str(reason).strip()
        if not normalized_reason:
            raise ValueError("Production session revocation requires a reason")
        with self.factory.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE production_identity_sessions
                SET state = 'REVOKED', revoked_at = ?, revocation_reason = ?,
                    revision = ?
                WHERE session_id = ? AND revision = ? AND state = 'ACTIVE'
                """,
                (
                    _iso(revoked_at),
                    normalized_reason,
                    expected_revision + 1,
                    session_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Production session could not be revoked at the expected revision"
                )
        stored = self.get(session_id)
        if stored is None:
            raise RuntimeError("Revoked production session is missing")
        return stored
