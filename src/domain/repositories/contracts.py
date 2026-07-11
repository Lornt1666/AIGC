from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class StoredRecord:
    record_id: str
    revision: int
    payload: dict[str, Any]
    created_at: str
    updated_at: str
    revoked_at: str | None = None
    retention_state: str = "ACTIVE"


class RecordRepository(Protocol):
    def get(self, record_id: str) -> StoredRecord | None: ...

    def list(self, *, include_revoked: bool = False) -> Sequence[StoredRecord]: ...

    def put(
        self,
        record_id: str,
        payload: Mapping[str, Any],
        *,
        expected_revision: int | None = None,
        idempotency_key: str | None = None,
    ) -> StoredRecord: ...

    def revoke(
        self,
        record_id: str,
        *,
        expected_revision: int,
        reason: str,
    ) -> StoredRecord: ...


class PrincipalRepository(RecordRepository, Protocol): ...
class MembershipRepository(RecordRepository, Protocol): ...
class SessionRepository(RecordRepository, Protocol): ...
class PolicyRepository(RecordRepository, Protocol): ...
class ApprovalRepository(RecordRepository, Protocol): ...
class RevocationRepository(RecordRepository, Protocol): ...
class JobRepository(RecordRepository, Protocol): ...
class ArtifactRepository(RecordRepository, Protocol): ...
class ReadinessEvidenceRepository(RecordRepository, Protocol): ...


class AuthorizationReceiptRepository(Protocol):
    def append(
        self,
        receipt_id: str,
        receipt: Mapping[str, Any],
        *,
        exact_revision: str,
        request_digest: str,
        idempotency_key: str | None = None,
    ) -> StoredRecord: ...

    def get(self, receipt_id: str) -> StoredRecord | None: ...


class AuditEventRepository(Protocol):
    def append(
        self,
        event_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        exact_revision: str,
        request_digest: str | None = None,
        idempotency_key: str | None = None,
    ) -> StoredRecord: ...

    def list(self, *, after_event_id: str | None = None) -> Sequence[StoredRecord]: ...
