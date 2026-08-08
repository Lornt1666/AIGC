from __future__ import annotations

from dataclasses import dataclass

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.articulation import ArticulationMessage
from src.domain.nexus.contextualization import (
    ContributionContextProjection,
    ParentMessageContext,
    RepositoryContext,
)
from src.security.redactor import Redactor


@dataclass(frozen=True)
class ContributionContextProjectionPolicy:
    maximum_parent_messages: int = 8
    maximum_repository_records: int = 24
    maximum_parent_content_chars: int = 50000
    maximum_repository_content_chars: int = 100000
    maximum_total_context_chars: int = 150000

    def __post_init__(self) -> None:
        values = (
            self.maximum_parent_messages,
            self.maximum_repository_records,
            self.maximum_parent_content_chars,
            self.maximum_repository_content_chars,
            self.maximum_total_context_chars,
        )
        if any(value < 0 for value in values):
            raise ValueError("context projection limits cannot be negative")


def _verify_message_hash(message: ArticulationMessage) -> None:
    observed = canonical_sha256(message.model_dump(mode="json", exclude={"canonical_hash"}))
    if observed != message.canonical_hash:
        raise ValueError(f"parent message canonical hash mismatch: {message.message_id}")


def build_contribution_context_projection(
    *,
    parent_messages: tuple[ArticulationMessage, ...] = (),
    repository_context: RepositoryContext | None = None,
    expected_session_id: str | None = None,
    policy: ContributionContextProjectionPolicy = ContributionContextProjectionPolicy(),
    redactor: Redactor | None = None,
) -> ContributionContextProjection:
    if len(parent_messages) > policy.maximum_parent_messages:
        raise ValueError("parent-message projection limit exceeded")
    if repository_context is not None and len(repository_context.records) > policy.maximum_repository_records:
        raise ValueError("repository-record projection limit exceeded")

    message_ids = [message.message_id for message in parent_messages]
    if len(message_ids) != len(set(message_ids)):
        raise ValueError("duplicate parent messages are not permitted")

    redactor = redactor or Redactor()
    projected_parents: list[ParentMessageContext] = []
    parent_chars = 0
    for message in parent_messages:
        _verify_message_hash(message)
        if expected_session_id is not None and message.session_id != expected_session_id:
            raise ValueError("parent message belongs to another articulation session")
        projected_content = redactor.redact_text(message.content)
        parent_chars += len(projected_content)
        if parent_chars > policy.maximum_parent_content_chars:
            raise ValueError("parent-message content projection limit exceeded")
        projected_parents.append(
            ParentMessageContext(
                message_id=message.message_id,
                source_canonical_hash=message.canonical_hash,
                provider_id=message.provider_id,
                model_label=message.model_label,
                response_type=message.response_type,
                content=projected_content,
                evidence_refs=message.evidence_refs,
                uncertainty=message.uncertainty,
                redaction_applied=projected_content != message.content,
                projected_content_sha256=canonical_sha256(projected_content),
            )
        )

    repository_records = repository_context.records if repository_context is not None else ()
    repository_chars = sum(len(record.content) for record in repository_records)
    if repository_chars > policy.maximum_repository_content_chars:
        raise ValueError("repository content projection limit exceeded")
    if parent_chars + repository_chars > policy.maximum_total_context_chars:
        raise ValueError("total contribution context projection limit exceeded")

    payload = {
        "parent_messages": [item.model_dump(mode="json") for item in projected_parents],
        "repository_records": [item.model_dump(mode="json") for item in repository_records],
        "repository_context_id": repository_context.context_id if repository_context else None,
    }
    digest = canonical_sha256(payload)
    return ContributionContextProjection(
        projection_id="CPRJ-" + digest[:24].upper(),
        parent_messages=tuple(projected_parents),
        repository_records=repository_records,
        repository_context_id=repository_context.context_id if repository_context else None,
        canonical_hash=digest,
    )
