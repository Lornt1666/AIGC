from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence

from src.domain.repositories import StoredRecord


class QuestLifecycleState(StrEnum):
    DISCOVERED = "DISCOVERED"
    QUALIFIED = "QUALIFIED"
    PROPOSED = "PROPOSED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    WORK_ACCEPTED = "WORK_ACCEPTED"
    RESEARCHING = "RESEARCHING"
    PLANNING = "PLANNING"
    EXECUTING_LOCALLY = "EXECUTING_LOCALLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    ACCEPTED_FOR_DELIVERY = "ACCEPTED_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class QuestError(RuntimeError):
    """Base error for canonical Quest operations."""


class QuestNotFound(QuestError):
    pass


class QuestConflict(QuestError):
    pass


class QuestStateError(QuestError):
    pass


@dataclass(frozen=True)
class QuestCreationResult:
    candidate: StoredRecord
    quest: StoredRecord


class QuestRepository(Protocol):
    def create_from_candidate(
        self,
        candidate_id: str,
        quest: Mapping[str, Any],
        *,
        expected_candidate_revision: int,
        idempotency_key: str,
        request_digest: str,
        exact_revision: str,
    ) -> QuestCreationResult: ...

    def transition(
        self,
        quest_id: str,
        quest: Mapping[str, Any],
        *,
        expected_revision: int,
        allowed_from: Sequence[str],
        target_state: str,
        event_type: str,
        idempotency_key: str,
        request_digest: str,
        exact_revision: str,
        audit_payload: Mapping[str, Any],
    ) -> StoredRecord: ...

    def get(self, quest_id: str) -> StoredRecord | None: ...

    def list(self) -> Sequence[StoredRecord]: ...
