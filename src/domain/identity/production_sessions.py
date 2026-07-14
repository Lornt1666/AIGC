from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from .contracts import AuthenticationAssuranceLevel


class ProviderSubjectState(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class ProductionSessionState(StrEnum):
    ACTIVE = "ACTIVE"
    ROTATED = "ROTATED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class ProviderSubjectBinding:
    provider_binding_id: str
    provider_subject: str
    principal_id: str
    membership_id: str
    tenant_id: str
    project_id: str
    state: ProviderSubjectState
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ProviderRevocationEvidence:
    provider_binding_id: str
    provider_subject: str
    active: bool
    checked_at: datetime
    evidence_id: str


@dataclass(frozen=True)
class ProductionSessionRecord:
    session_id: str
    credential_digest: str
    principal_id: str
    membership_id: str
    tenant_id: str
    project_id: str
    state: ProductionSessionState
    authentication_assurance: AuthenticationAssuranceLevel
    issued_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revision: int
    evidence_ids: tuple[str, ...]
    rotated_from_session_id: str | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None


@dataclass(frozen=True)
class IssuedProductionSession:
    record: ProductionSessionRecord
    session_credential: str


class ProviderSubjectBindingResolver(Protocol):
    def resolve_subject(
        self,
        *,
        provider_binding_id: str,
        provider_subject: str,
    ) -> ProviderSubjectBinding | None: ...


class ProviderRevocationResolver(Protocol):
    def check_subject(
        self,
        *,
        provider_binding_id: str,
        provider_subject: str,
        authentication_time: datetime,
        now: datetime,
    ) -> ProviderRevocationEvidence: ...


class ProductionSessionRepository(Protocol):
    def create(self, record: ProductionSessionRecord) -> ProductionSessionRecord: ...

    def get_by_credential_digest(
        self,
        credential_digest: str,
    ) -> ProductionSessionRecord | None: ...

    def touch(
        self,
        *,
        session_id: str,
        expected_revision: int,
        seen_at: datetime,
        idle_expires_at: datetime,
    ) -> ProductionSessionRecord: ...

    def rotate(
        self,
        *,
        current_session_id: str,
        current_revision: int,
        new_record: ProductionSessionRecord,
        rotated_at: datetime,
    ) -> tuple[ProductionSessionRecord, ProductionSessionRecord]: ...

    def revoke(
        self,
        *,
        session_id: str,
        expected_revision: int,
        revoked_at: datetime,
        reason: str,
    ) -> ProductionSessionRecord: ...


class SessionCredentialDigester(Protocol):
    def digest(self, session_credential: str) -> str: ...
