from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract


RepositoryOperation = Literal[
    "REPOSITORY_METADATA",
    "GET_TREE",
    "READ_FILE",
    "READ_COMMIT",
    "SEARCH_CODE",
    "COMPARE_REVISIONS",
    "READ_PULL_REQUEST",
]


class ParentMessageContext(NexusContract):
    message_id: str = Field(pattern=r"^ARTMSG-[A-F0-9]{24}$")
    source_canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_id: str = Field(min_length=1, max_length=100)
    model_label: str = Field(min_length=1, max_length=200)
    response_type: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=100000)
    evidence_refs: tuple[str, ...] = ()
    uncertainty: float = Field(ge=0.0, le=1.0)
    redaction_applied: bool = False
    projected_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_classification: Literal["UNTRUSTED_PARENT_ARTICULATION_CONTEXT"] = (
        "UNTRUSTED_PARENT_ARTICULATION_CONTEXT"
    )
    authority_granted: Literal[False] = False
    external_action_performed: Literal[False] = False


class RepositoryReadRequest(NexusContract):
    repository: str = Field(min_length=1, max_length=300)
    exact_revision: str = Field(min_length=1, max_length=200)
    operation: RepositoryOperation
    path_or_query: str = Field(min_length=1, max_length=2000)
    sensitivity: str = Field(default="INTERNAL", min_length=1, max_length=64)


class RepositoryReadObservation(NexusContract):
    repository: str = Field(min_length=1, max_length=300)
    observed_revision: str = Field(min_length=1, max_length=200)
    operation: RepositoryOperation
    path_or_query: str = Field(min_length=1, max_length=2000)
    retrieved_at: datetime
    raw_content: str = Field(max_length=200000)
    raw_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_type: str = Field(min_length=1, max_length=100)
    sensitivity: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_observation_time(self) -> "RepositoryReadObservation":
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("RepositoryReadObservation retrieved_at must be timezone-aware")
        return self


class RepositoryContextRecord(NexusContract):
    repository: str = Field(min_length=1, max_length=300)
    exact_revision: str = Field(min_length=1, max_length=200)
    operation: RepositoryOperation
    path_or_query: str = Field(min_length=1, max_length=2000)
    retrieved_at: datetime
    content: str = Field(max_length=200000)
    raw_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    projected_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_type: str = Field(min_length=1, max_length=100)
    sensitivity: str = Field(min_length=1, max_length=64)
    redaction_applied: bool = False
    content_classification: Literal["UNTRUSTED_REPOSITORY_CONTENT"] = "UNTRUSTED_REPOSITORY_CONTENT"
    authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def validate_retrieval_time(self) -> "RepositoryContextRecord":
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("RepositoryContextRecord retrieved_at must be timezone-aware")
        return self


class RepositoryContext(NexusContract):
    context_id: str = Field(pattern=r"^RCTX-[A-F0-9]{24}$")
    repository: str = Field(min_length=1, max_length=300)
    exact_revision: str = Field(min_length=1, max_length=200)
    records: tuple[RepositoryContextRecord, ...]
    policy_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority_granted: Literal[False] = False
    write_capability_present: Literal[False] = False

    @model_validator(mode="after")
    def validate_records(self) -> "RepositoryContext":
        if not self.records:
            raise ValueError("RepositoryContext requires at least one record")
        for record in self.records:
            if record.repository != self.repository:
                raise ValueError("RepositoryContext contains a different repository")
            if record.exact_revision != self.exact_revision:
                raise ValueError("RepositoryContext contains a different exact revision")
        return self


class ContributionContextProjection(NexusContract):
    projection_id: str = Field(pattern=r"^CPRJ-[A-F0-9]{24}$")
    parent_messages: tuple[ParentMessageContext, ...] = ()
    repository_records: tuple[RepositoryContextRecord, ...] = ()
    repository_context_id: str | None = None
    canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority_granted: Literal[False] = False
