from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
from typing import Any, Literal, Protocol
import uuid

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


_DRAFT_SCHEMA = "aigc.judge-receipt-draft.v1"
_PUBLIC_SCHEMA = "aigc.judge-receipt.v1"
_RECEIPT_ID = re.compile(
    r"^AIGC-JUDGE-RECEIPT-[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class JudgeReceiptError(RuntimeError):
    """Base class for judge-receipt boundary failures."""


class JudgeReceiptConfirmationError(JudgeReceiptError):
    """Raised when publication was not explicitly confirmed."""


class JudgeReceiptIntegrityError(JudgeReceiptError):
    """Raised when a receipt fails its content binding."""


class JudgeReceiptStorageError(JudgeReceiptError):
    """Raised when the sanitized receipt store is unavailable or invalid."""


class JudgeReceiptConflictError(JudgeReceiptStorageError):
    """Raised when a create-only receipt identifier already exists."""


class JudgeReceiptNotFoundError(JudgeReceiptError):
    """Raised when a published judge receipt does not exist."""


class _JudgeSafeModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=False,
        revalidate_instances="always",
    )


class JudgeReceiptClaim(_JudgeSafeModel):
    """A deliberately narrow, non-narrative public capability claim.

    This schema has no place for opportunity intake, generated assessment
    content, operator identity, decisions, or review reasons. It also omits
    internal storage locations. Callers must supply only evidence-bound,
    categorical facts.
    """

    project_slug: str = Field(
        min_length=2,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$",
    )
    business_identity: str = Field(
        min_length=2,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$",
    )
    capability: Literal["gemini_opportunity_assessment"]
    evidence_basis: Literal[
        "offline_repository_validation",
        "live_runtime_receipt",
    ]
    workflow_run_id: str = Field(
        min_length=16,
        max_length=96,
        pattern=r"^AIGC-GEMINI-RUN-[A-Za-z0-9-]+$",
    )
    source_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    runtime_revision: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    evidence_record_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_generation: int | None = Field(default=None, gt=0)
    model_api_call_status: Literal["not_attempted", "confirmed"]
    model_api_call_performed: bool
    human_review_state: Literal["required", "attestation_recorded"]
    ai_use_disclosed: Literal[True] = True
    external_action_performed: Literal[False] = False

    @model_validator(mode="after")
    def enforce_evidence_basis(self) -> "JudgeReceiptClaim":
        if self.evidence_basis == "live_runtime_receipt":
            if (
                self.model_api_call_status != "confirmed"
                or self.model_api_call_performed is not True
                or self.runtime_revision is None
                or self.evidence_generation is None
            ):
                raise ValueError(
                    "Live runtime claims require a confirmed model call, "
                    "runtime revision, and evidence generation"
                )
        elif (
            self.model_api_call_status != "not_attempted"
            or self.model_api_call_performed is not False
            or self.runtime_revision is not None
            or self.evidence_generation is not None
        ):
            raise ValueError(
                "Offline validation cannot claim a model call, runtime "
                "revision, or durable object generation"
            )
        return self


class JudgeReceiptDraft(_JudgeSafeModel):
    schema_version: Literal["aigc.judge-receipt-draft.v1"] = _DRAFT_SCHEMA
    receipt_id: str = Field(min_length=55, max_length=55)
    prepared_at: datetime
    claim: JudgeReceiptClaim
    draft_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_draft(self) -> "JudgeReceiptDraft":
        _validate_receipt_id(self.receipt_id)
        _validate_utc(self.prepared_at, field_name="prepared_at")
        expected = _draft_hash(
            receipt_id=self.receipt_id,
            prepared_at=self.prepared_at,
            claim=self.claim,
        )
        if not hmac.compare_digest(self.draft_sha256, expected):
            raise ValueError("draft_sha256 does not match the receipt content")
        return self


class PublishedJudgeReceipt(_JudgeSafeModel):
    schema_version: Literal["aigc.judge-receipt.v1"] = _PUBLIC_SCHEMA
    receipt_id: str = Field(min_length=55, max_length=55)
    prepared_at: datetime
    published_at: datetime
    publication_state: Literal["published"] = "published"
    claim: JudgeReceiptClaim
    draft_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_publication(self) -> "PublishedJudgeReceipt":
        _validate_receipt_id(self.receipt_id)
        _validate_utc(self.prepared_at, field_name="prepared_at")
        _validate_utc(self.published_at, field_name="published_at")
        if self.published_at < self.prepared_at:
            raise ValueError("published_at cannot precede prepared_at")
        expected_draft = _draft_hash(
            receipt_id=self.receipt_id,
            prepared_at=self.prepared_at,
            claim=self.claim,
        )
        if not hmac.compare_digest(self.draft_sha256, expected_draft):
            raise ValueError("draft_sha256 does not match the receipt content")
        expected_receipt = _receipt_hash(
            receipt_id=self.receipt_id,
            prepared_at=self.prepared_at,
            published_at=self.published_at,
            claim=self.claim,
            draft_sha256=self.draft_sha256,
        )
        if not hmac.compare_digest(self.receipt_sha256, expected_receipt):
            raise ValueError(
                "receipt_sha256 does not match the published receipt"
            )
        return self


class JudgeReceiptWriteStore(Protocol):
    """Operator-side create-only storage.

    Implementations must atomically fail with ``JudgeReceiptConflictError``
    when ``receipt.receipt_id`` already exists.
    """

    def create_if_absent(self, receipt: PublishedJudgeReceipt) -> None: ...


class JudgeReceiptReadStore(Protocol):
    """Read-only storage contract for a separately deployed judge surface."""

    def get(self, receipt_id: str) -> PublishedJudgeReceipt | None: ...


class JudgeReceiptPublicationService:
    """Prepares and explicitly publishes sanitized receipts.

    The service intentionally accepts only a judge-safe claim and a write
    store. It has no model-provider dependency and performs no generation.
    """

    def __init__(
        self,
        *,
        writer: JudgeReceiptWriteStore,
        clock: Callable[[], datetime] | None = None,
        receipt_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._writer = writer
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._receipt_id_factory = receipt_id_factory or (
            lambda: f"AIGC-JUDGE-RECEIPT-{uuid.uuid4()}"
        )

    def prepare(self, claim: JudgeReceiptClaim) -> JudgeReceiptDraft:
        validated_claim = JudgeReceiptClaim.model_validate(
            claim.model_dump(mode="python")
        )
        receipt_id = self._receipt_id_factory()
        _validate_receipt_id(receipt_id)
        prepared_at = _clock_value(self._clock)
        digest = _draft_hash(
            receipt_id=receipt_id,
            prepared_at=prepared_at,
            claim=validated_claim,
        )
        return JudgeReceiptDraft(
            receipt_id=receipt_id,
            prepared_at=prepared_at,
            claim=validated_claim,
            draft_sha256=digest,
        )

    def publish(
        self,
        draft: JudgeReceiptDraft,
        *,
        confirmation_phrase: str,
    ) -> PublishedJudgeReceipt:
        validated_draft = _revalidate_draft(draft)
        required = required_publication_phrase(validated_draft)
        if not isinstance(confirmation_phrase, str) or not hmac.compare_digest(
            confirmation_phrase,
            required,
        ):
            raise JudgeReceiptConfirmationError(
                "Judge receipt publication requires the exact "
                "content-bound confirmation phrase"
            )

        published_at = _clock_value(self._clock)
        receipt_hash = _receipt_hash(
            receipt_id=validated_draft.receipt_id,
            prepared_at=validated_draft.prepared_at,
            published_at=published_at,
            claim=validated_draft.claim,
            draft_sha256=validated_draft.draft_sha256,
        )
        receipt = PublishedJudgeReceipt(
            receipt_id=validated_draft.receipt_id,
            prepared_at=validated_draft.prepared_at,
            published_at=published_at,
            claim=validated_draft.claim,
            draft_sha256=validated_draft.draft_sha256,
            receipt_sha256=receipt_hash,
        )
        try:
            self._writer.create_if_absent(receipt)
        except JudgeReceiptConflictError:
            raise
        except Exception as exc:
            raise JudgeReceiptStorageError(
                "The sanitized judge receipt could not be published"
            ) from exc
        return receipt


class JudgeReceiptReadService:
    """The complete application service for a read-only judge surface."""

    def __init__(self, *, reader: JudgeReceiptReadStore) -> None:
        self._reader = reader

    def get(self, receipt_id: str) -> PublishedJudgeReceipt:
        _validate_receipt_id(receipt_id)
        try:
            stored = self._reader.get(receipt_id)
        except Exception as exc:
            raise JudgeReceiptStorageError(
                "The sanitized judge receipt could not be read"
            ) from exc
        if stored is None:
            raise JudgeReceiptNotFoundError("Judge receipt not found")
        if not isinstance(stored, PublishedJudgeReceipt):
            raise JudgeReceiptStorageError(
                "The judge receipt store returned an invalid record"
            )
        try:
            validated = PublishedJudgeReceipt.model_validate(
                stored.model_dump(mode="python")
            )
        except ValidationError as exc:
            raise JudgeReceiptIntegrityError(
                "Published judge receipt integrity validation failed"
            ) from exc
        if validated.receipt_id != receipt_id:
            raise JudgeReceiptIntegrityError(
                "Published judge receipt identifier mismatch"
            )
        return validated


def required_publication_phrase(draft: JudgeReceiptDraft) -> str:
    """Return the exact, content-bound phrase required for publication."""

    validated = _revalidate_draft(draft)
    return (
        f"PUBLISH JUDGE RECEIPT {validated.receipt_id} "
        f"SHA256 {validated.draft_sha256}"
    )


def _revalidate_draft(draft: JudgeReceiptDraft) -> JudgeReceiptDraft:
    if not isinstance(draft, JudgeReceiptDraft):
        raise JudgeReceiptIntegrityError("A validated judge receipt is required")
    try:
        return JudgeReceiptDraft.model_validate(
            draft.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise JudgeReceiptIntegrityError(
            "Judge receipt draft integrity validation failed"
        ) from exc


def _clock_value(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise JudgeReceiptIntegrityError(
            "The judge receipt clock must return a datetime"
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise JudgeReceiptIntegrityError(
            "The judge receipt clock must return a timezone-aware datetime"
        )
    return value.astimezone(timezone.utc)


def _validate_utc(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be represented in UTC")


def _validate_receipt_id(value: str) -> None:
    if not isinstance(value, str) or not _RECEIPT_ID.fullmatch(value):
        raise ValueError("receipt_id must be a canonical judge receipt UUID")


def _draft_hash(
    *,
    receipt_id: str,
    prepared_at: datetime,
    claim: JudgeReceiptClaim,
) -> str:
    return _canonical_hash(
        {
            "schema_version": _DRAFT_SCHEMA,
            "receipt_id": receipt_id,
            "prepared_at": _utc_isoformat(prepared_at),
            "claim": claim.model_dump(mode="json"),
        }
    )


def _receipt_hash(
    *,
    receipt_id: str,
    prepared_at: datetime,
    published_at: datetime,
    claim: JudgeReceiptClaim,
    draft_sha256: str,
) -> str:
    return _canonical_hash(
        {
            "schema_version": _PUBLIC_SCHEMA,
            "receipt_id": receipt_id,
            "prepared_at": _utc_isoformat(prepared_at),
            "published_at": _utc_isoformat(published_at),
            "publication_state": "published",
            "claim": claim.model_dump(mode="json"),
            "draft_sha256": draft_sha256,
        }
    )


def _utc_isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
