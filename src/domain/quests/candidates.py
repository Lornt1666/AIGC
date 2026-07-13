from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence

from src.domain.repositories import StoredRecord


class QuestCandidateStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"


class QuestCandidateError(RuntimeError):
    """Base error for the governed quest-candidate boundary."""


class QuestCandidateNotFound(QuestCandidateError):
    pass


class QuestCandidateConflict(QuestCandidateError):
    pass


class QuestCandidateStateError(QuestCandidateError):
    pass


class WorkSourcePolicyError(QuestCandidateError):
    pass


class QuestCandidateRepository(Protocol):
    def ingest(
        self,
        candidate: Mapping[str, Any],
        *,
        idempotency_key: str,
        exact_revision: str,
    ) -> StoredRecord: ...

    def get(self, candidate_id: str) -> StoredRecord | None: ...

    def list(self) -> Sequence[StoredRecord]: ...

    def qualify(
        self,
        candidate_id: str,
        candidate: Mapping[str, Any],
        *,
        expected_revision: int,
        exact_revision: str,
    ) -> StoredRecord: ...
