from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import secrets
from typing import Callable
from uuid import uuid4

from src.domain.identity import (
    AuthenticationAssuranceLevel,
    ProviderVerification,
    RuntimeAuthority,
    SessionBinding,
    SessionState,
)
from src.domain.identity.production_sessions import (
    IssuedProductionSession,
    ProductionSessionRecord,
    ProductionSessionRepository,
    ProductionSessionState,
    ProviderSubjectBinding,
    ProviderSubjectState,
    SessionCredentialDigester,
)


class ProductionSessionError(ValueError):
    """Raised when a server-owned session cannot be issued or accepted."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class HmacSessionCredentialDigester:
    """Digest session credentials with an in-memory pepper resolved elsewhere."""

    def __init__(self, pepper_material: bytes) -> None:
        if len(pepper_material) < 32:
            raise ProductionSessionError(
                "Session credential pepper material must be at least 32 bytes"
            )
        self._pepper_material = bytes(pepper_material)

    def digest(self, session_credential: str) -> str:
        if not isinstance(session_credential, str) or len(session_credential) < 32:
            raise ProductionSessionError("Session credential is malformed")
        return hmac.new(
            self._pepper_material,
            session_credential.encode("utf-8"),
            sha256,
        ).hexdigest()


class ProductionSessionService:
    def __init__(
        self,
        *,
        repository: ProductionSessionRepository,
        digester: SessionCredentialDigester,
        idle_timeout_seconds: int = 1800,
        absolute_timeout_seconds: int = 43200,
        credential_factory: Callable[[], str] | None = None,
    ) -> None:
        if idle_timeout_seconds <= 0 or absolute_timeout_seconds <= 0:
            raise ProductionSessionError("Session timeouts must be positive")
        if idle_timeout_seconds > absolute_timeout_seconds:
            raise ProductionSessionError(
                "Session idle timeout cannot exceed absolute timeout"
            )
        self.repository = repository
        self.digester = digester
        self.idle_timeout_seconds = idle_timeout_seconds
        self.absolute_timeout_seconds = absolute_timeout_seconds
        self.credential_factory = credential_factory or (
            lambda: secrets.token_urlsafe(48)
        )

    def issue(
        self,
        *,
        verification: ProviderVerification,
        binding: ProviderSubjectBinding,
        now: datetime | None = None,
        rotated_from_session_id: str | None = None,
    ) -> IssuedProductionSession:
        current = _utc(now or datetime.now(timezone.utc))
        self._require_verified_binding(verification, binding)
        session_credential = self.credential_factory()
        credential_digest = self.digester.digest(session_credential)
        session_id = "sess_" + uuid4().hex
        evidence_ids = tuple(
            dict.fromkeys(
                (
                    *verification.evidence_ids,
                    *binding.evidence_ids,
                    "EVID-SESSION-ISSUED-" + sha256(
                        (session_id + "|" + verification.assertion_id).encode("utf-8")
                    ).hexdigest()[:20].upper(),
                )
            )
        )
        record = ProductionSessionRecord(
            session_id=session_id,
            credential_digest=credential_digest,
            principal_id=binding.principal_id,
            membership_id=binding.membership_id,
            tenant_id=binding.tenant_id,
            project_id=binding.project_id,
            state=ProductionSessionState.ACTIVE,
            authentication_assurance=verification.authentication_assurance,
            issued_at=current,
            last_seen_at=current,
            idle_expires_at=current + timedelta(seconds=self.idle_timeout_seconds),
            absolute_expires_at=current
            + timedelta(seconds=self.absolute_timeout_seconds),
            revision=1,
            evidence_ids=evidence_ids,
            rotated_from_session_id=rotated_from_session_id,
        )
        stored = self.repository.create(record)
        return IssuedProductionSession(
            record=stored,
            session_credential=session_credential,
        )

    def authenticate(
        self,
        session_credential: str,
        *,
        now: datetime | None = None,
        expected_tenant_id: str | None = None,
        expected_project_id: str | None = None,
    ) -> ProductionSessionRecord:
        current = _utc(now or datetime.now(timezone.utc))
        credential_digest = self.digester.digest(session_credential)
        record = self.repository.get_by_credential_digest(credential_digest)
        if record is None:
            raise ProductionSessionError("Production session was not found")
        if record.state is not ProductionSessionState.ACTIVE:
            raise ProductionSessionError("Production session is not active")
        if current >= record.idle_expires_at or current >= record.absolute_expires_at:
            raise ProductionSessionError("Production session has expired")
        if expected_tenant_id is not None and record.tenant_id != expected_tenant_id:
            raise ProductionSessionError("Production session tenant mismatch")
        if expected_project_id is not None and record.project_id != expected_project_id:
            raise ProductionSessionError("Production session project mismatch")
        return record

    def rotate(
        self,
        session_credential: str,
        *,
        verification: ProviderVerification,
        binding: ProviderSubjectBinding,
        now: datetime | None = None,
    ) -> IssuedProductionSession:
        current = _utc(now or datetime.now(timezone.utc))
        existing = self.authenticate(
            session_credential,
            now=current,
            expected_tenant_id=binding.tenant_id,
            expected_project_id=binding.project_id,
        )
        self._require_verified_binding(verification, binding)
        if existing.principal_id != binding.principal_id:
            raise ProductionSessionError("Production session principal mismatch")
        replacement_credential = self.credential_factory()
        replacement = ProductionSessionRecord(
            session_id="sess_" + uuid4().hex,
            credential_digest=self.digester.digest(replacement_credential),
            principal_id=existing.principal_id,
            membership_id=existing.membership_id,
            tenant_id=existing.tenant_id,
            project_id=existing.project_id,
            state=ProductionSessionState.ACTIVE,
            authentication_assurance=verification.authentication_assurance,
            issued_at=current,
            last_seen_at=current,
            idle_expires_at=current + timedelta(seconds=self.idle_timeout_seconds),
            absolute_expires_at=current
            + timedelta(seconds=self.absolute_timeout_seconds),
            revision=1,
            evidence_ids=tuple(
                dict.fromkeys(
                    (
                        *verification.evidence_ids,
                        *binding.evidence_ids,
                        "EVID-SESSION-ROTATED-" + sha256(
                            (existing.session_id + "|" + verification.assertion_id).encode(
                                "utf-8"
                            )
                        ).hexdigest()[:20].upper(),
                    )
                )
            ),
            rotated_from_session_id=existing.session_id,
        )
        _, stored = self.repository.rotate(
            current_session_id=existing.session_id,
            current_revision=existing.revision,
            new_record=replacement,
            rotated_at=current,
        )
        return IssuedProductionSession(
            record=stored,
            session_credential=replacement_credential,
        )

    def revoke(
        self,
        session_credential: str,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> ProductionSessionRecord:
        current = _utc(now or datetime.now(timezone.utc))
        credential_digest = self.digester.digest(session_credential)
        record = self.repository.get_by_credential_digest(credential_digest)
        if record is None:
            raise ProductionSessionError("Production session was not found")
        if record.state is not ProductionSessionState.ACTIVE:
            raise ProductionSessionError("Only an active production session may revoke")
        return self.repository.revoke(
            session_id=record.session_id,
            expected_revision=record.revision,
            revoked_at=current,
            reason=reason,
        )

    @staticmethod
    def to_session_binding(record: ProductionSessionRecord) -> SessionBinding:
        state = (
            SessionState.ACTIVE
            if record.state is ProductionSessionState.ACTIVE
            else SessionState.REVOKED
            if record.state in {
                ProductionSessionState.REVOKED,
                ProductionSessionState.ROTATED,
            }
            else SessionState.EXPIRED
        )
        return SessionBinding(
            session_id=record.session_id,
            principal_id=record.principal_id,
            membership_id=record.membership_id,
            tenant_id=record.tenant_id,
            project_id=record.project_id,
            state=state,
            issued_at=record.issued_at,
            idle_expires_at=record.idle_expires_at,
            absolute_expires_at=record.absolute_expires_at,
            authentication_assurance=record.authentication_assurance,
            evidence_ids=record.evidence_ids,
        )

    @staticmethod
    def _require_verified_binding(
        verification: ProviderVerification,
        binding: ProviderSubjectBinding,
    ) -> None:
        if not verification.verified:
            raise ProductionSessionError(
                "Verified provider evidence is required to issue a session"
            )
        if verification.runtime_authority is not RuntimeAuthority.PRODUCTION_VERIFIED:
            raise ProductionSessionError(
                "Production-verified provider authority is required"
            )
        if verification.principal_id != binding.principal_id:
            raise ProductionSessionError("Provider principal does not match binding")
        if binding.state is not ProviderSubjectState.ACTIVE:
            raise ProductionSessionError("Provider subject binding is not active")
        if verification.authentication_assurance is AuthenticationAssuranceLevel.AAL0:
            raise ProductionSessionError(
                "Authentication assurance is insufficient for a session"
            )
