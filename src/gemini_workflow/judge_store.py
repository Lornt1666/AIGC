from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .judge_receipts import (
    JudgeReceiptConflictError,
    JudgeReceiptIntegrityError,
    JudgeReceiptStorageError,
    PublishedJudgeReceipt,
)


_INDEX_SCHEMA = "aigc.judge-receipt-gcs-index.v1"
_WRITE_SCHEMA = "aigc.judge-receipt-gcs-write.v1"
_RECEIPT_ID = re.compile(
    r"^AIGC-JUDGE-RECEIPT-[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_BUCKET_NAME = re.compile(
    r"^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$"
)
_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")
_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,510}[A-Za-z0-9]$")
_CRC32C = re.compile(r"^[A-Za-z0-9+/]{6}==$")
_MAX_INDEX_BYTES = 16_384
_MAX_RECEIPT_BYTES = 131_072


class _StrictStorageModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=False,
        revalidate_instances="always",
    )


class GcsJudgeReceiptLocator(_StrictStorageModel):
    """Immutable public-object locator; never a signed or HTTPS URL."""

    schema_version: Literal[
        "aigc.judge-receipt-gcs-index.v1"
    ] = _INDEX_SCHEMA
    backend: Literal["gcs"] = "gcs"
    receipt_id: str = Field(min_length=55, max_length=55)
    object_uri: str = Field(min_length=10, max_length=1_024)
    generation: int = Field(gt=0)
    crc32c: str = Field(min_length=8, max_length=8)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_public_locator(self) -> "GcsJudgeReceiptLocator":
        _validate_receipt_id(self.receipt_id)
        if not self.object_uri.startswith("gs://"):
            raise ValueError("object_uri must use the gs scheme")
        if "?" in self.object_uri or "#" in self.object_uri:
            raise ValueError("object_uri must not contain URL parameters")
        if not _CRC32C.fullmatch(self.crc32c):
            raise ValueError("crc32c must be a base64-encoded CRC32C value")
        return self


class GcsJudgeReceiptWriteResult(_StrictStorageModel):
    """Create-only storage receipt for the operator-side publisher."""

    schema_version: Literal[
        "aigc.judge-receipt-gcs-write.v1"
    ] = _WRITE_SCHEMA
    receipt: GcsJudgeReceiptLocator
    index_uri: str = Field(min_length=10, max_length=1_024)
    index_generation: int = Field(gt=0)
    index_crc32c: str = Field(min_length=8, max_length=8)
    index_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_index_metadata(self) -> "GcsJudgeReceiptWriteResult":
        if not self.index_uri.startswith("gs://"):
            raise ValueError("index_uri must use the gs scheme")
        if "?" in self.index_uri or "#" in self.index_uri:
            raise ValueError("index_uri must not contain URL parameters")
        if not _CRC32C.fullmatch(self.index_crc32c):
            raise ValueError(
                "index_crc32c must be a base64-encoded CRC32C value"
            )
        return self


class GcsJudgeReceiptWriter:
    """Operator-only, create-only Cloud Storage writer.

    A receipt object and its generation-pinned index are both created with
    ``if_generation_match=0``. The index contains only the public receipt
    locator and integrity metadata. No signed URL is generated or retained.
    """

    def __init__(
        self,
        *,
        project_id: str,
        bucket_name: str,
        prefix: str,
        client: Any | None = None,
    ) -> None:
        self.project_id = _validate_project_id(project_id)
        self.bucket_name = _validate_bucket_name(bucket_name)
        self.prefix = _validate_prefix(prefix)
        self._client = client

    def create_if_absent(
        self,
        receipt: PublishedJudgeReceipt,
    ) -> GcsJudgeReceiptWriteResult:
        validated = _validate_published_receipt(receipt)
        receipt_name = self._receipt_object_name(validated.receipt_id)
        index_name = self._index_object_name(validated.receipt_id)
        receipt_payload = (
            validated.model_dump_json(indent=2).encode("utf-8") + b"\n"
        )

        try:
            bucket = self._get_client().bucket(self.bucket_name)
            receipt_blob = bucket.blob(receipt_name)
            receipt_blob.upload_from_string(
                receipt_payload,
                content_type="application/json",
                if_generation_match=0,
                checksum="crc32c",
            )
            receipt_generation, receipt_crc32c = _blob_identity(receipt_blob)
            locator = GcsJudgeReceiptLocator(
                receipt_id=validated.receipt_id,
                object_uri=self._gs_uri(receipt_name),
                generation=receipt_generation,
                crc32c=receipt_crc32c,
                content_sha256=_sha256(receipt_payload),
                receipt_sha256=validated.receipt_sha256,
            )

            index_payload = (
                locator.model_dump_json(indent=2).encode("utf-8") + b"\n"
            )
            index_blob = bucket.blob(index_name)
            index_blob.upload_from_string(
                index_payload,
                content_type="application/json",
                if_generation_match=0,
                checksum="crc32c",
            )
            index_generation, index_crc32c = _blob_identity(index_blob)
            result = GcsJudgeReceiptWriteResult(
                receipt=locator,
                index_uri=self._gs_uri(index_name),
                index_generation=index_generation,
                index_crc32c=index_crc32c,
                index_content_sha256=_sha256(index_payload),
            )
            self._assert_exact_write_result(result)
            return result
        except JudgeReceiptConflictError:
            raise
        except Exception as exc:
            if _is_precondition_failure(exc):
                raise JudgeReceiptConflictError(
                    "A judge receipt or its index already exists"
                ) from exc
            if isinstance(
                exc,
                (JudgeReceiptIntegrityError, JudgeReceiptStorageError),
            ):
                raise
            raise JudgeReceiptStorageError(
                "Cloud Storage judge receipt publication failed"
            ) from exc

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import storage
            except ImportError as exc:
                raise JudgeReceiptStorageError(
                    "google-cloud-storage is required for judge receipts"
                ) from exc
            self._client = storage.Client(project=self.project_id)
        return self._client

    def _receipt_object_name(self, receipt_id: str) -> str:
        return f"{self.prefix}/receipts/{receipt_id}.json"

    def _index_object_name(self, receipt_id: str) -> str:
        return f"{self.prefix}/index/{receipt_id}.json"

    def _gs_uri(self, object_name: str) -> str:
        return f"gs://{self.bucket_name}/{object_name}"

    def _assert_exact_write_result(
        self,
        result: GcsJudgeReceiptWriteResult,
    ) -> None:
        receipt_id = result.receipt.receipt_id
        if result.receipt.object_uri != self._gs_uri(
            self._receipt_object_name(receipt_id)
        ):
            raise JudgeReceiptIntegrityError(
                "Receipt object escaped its configured storage prefix"
            )
        if result.index_uri != self._gs_uri(
            self._index_object_name(receipt_id)
        ):
            raise JudgeReceiptIntegrityError(
                "Receipt index escaped its configured storage prefix"
            )


class GcsJudgeReceiptReader:
    """Read-only, exact-prefix Cloud Storage adapter for a judge surface.

    Only a canonical receipt identifier is accepted. The reader does not list,
    create, update, delete, sign, or return Cloud Storage objects.
    """

    def __init__(
        self,
        *,
        project_id: str,
        bucket_name: str,
        prefix: str,
        client: Any | None = None,
    ) -> None:
        self.project_id = _validate_project_id(project_id)
        self.bucket_name = _validate_bucket_name(bucket_name)
        self.prefix = _validate_prefix(prefix)
        self._client = client

    def get(self, receipt_id: str) -> PublishedJudgeReceipt | None:
        _validate_receipt_id(receipt_id)
        receipt_name = self._receipt_object_name(receipt_id)
        index_name = self._index_object_name(receipt_id)

        try:
            bucket = self._get_client().bucket(self.bucket_name)
            index_blob = bucket.blob(index_name)
            index_payload = index_blob.download_as_bytes(checksum="crc32c")
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise JudgeReceiptStorageError(
                "Cloud Storage judge receipt index read failed"
            ) from exc

        locator = _parse_locator(index_payload)
        expected_uri = self._gs_uri(receipt_name)
        if (
            locator.receipt_id != receipt_id
            or locator.object_uri != expected_uri
        ):
            raise JudgeReceiptIntegrityError(
                "Judge receipt index escaped its configured bucket or prefix"
            )

        try:
            receipt_blob = bucket.blob(
                receipt_name,
                generation=locator.generation,
            )
            receipt_blob.reload(if_generation_match=locator.generation)
            actual_generation, actual_crc32c = _blob_identity(receipt_blob)
            if actual_generation != locator.generation:
                raise JudgeReceiptIntegrityError(
                    "Indexed judge receipt generation does not match"
                )
            if not hmac.compare_digest(actual_crc32c, locator.crc32c):
                raise JudgeReceiptIntegrityError(
                    "Indexed judge receipt checksum does not match"
                )
            receipt_payload = receipt_blob.download_as_bytes(
                if_generation_match=locator.generation,
                checksum="crc32c",
            )
        except JudgeReceiptIntegrityError:
            raise
        except Exception as exc:
            if _is_not_found(exc) or _is_precondition_failure(exc):
                raise JudgeReceiptIntegrityError(
                    "Indexed judge receipt generation is unavailable"
                ) from exc
            raise JudgeReceiptStorageError(
                "Cloud Storage judge receipt read failed"
            ) from exc

        if not isinstance(receipt_payload, bytes):
            raise JudgeReceiptIntegrityError(
                "Cloud Storage returned a non-bytes judge receipt"
            )
        if len(receipt_payload) > _MAX_RECEIPT_BYTES:
            raise JudgeReceiptIntegrityError(
                "Published judge receipt exceeds its maximum size"
            )
        if not hmac.compare_digest(
            _sha256(receipt_payload),
            locator.content_sha256,
        ):
            raise JudgeReceiptIntegrityError(
                "Published judge receipt content checksum does not match"
            )
        try:
            receipt = PublishedJudgeReceipt.model_validate_json(
                receipt_payload
            )
        except ValidationError as exc:
            raise JudgeReceiptIntegrityError(
                "Published judge receipt schema or integrity is invalid"
            ) from exc
        if (
            receipt.receipt_id != receipt_id
            or not hmac.compare_digest(
                receipt.receipt_sha256,
                locator.receipt_sha256,
            )
        ):
            raise JudgeReceiptIntegrityError(
                "Published judge receipt does not match its index"
            )
        return receipt

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import storage
            except ImportError as exc:
                raise JudgeReceiptStorageError(
                    "google-cloud-storage is required for judge receipts"
                ) from exc
            self._client = storage.Client(project=self.project_id)
        return self._client

    def _receipt_object_name(self, receipt_id: str) -> str:
        return f"{self.prefix}/receipts/{receipt_id}.json"

    def _index_object_name(self, receipt_id: str) -> str:
        return f"{self.prefix}/index/{receipt_id}.json"

    def _gs_uri(self, object_name: str) -> str:
        return f"gs://{self.bucket_name}/{object_name}"


def _validate_published_receipt(
    receipt: PublishedJudgeReceipt,
) -> PublishedJudgeReceipt:
    if not isinstance(receipt, PublishedJudgeReceipt):
        raise JudgeReceiptIntegrityError(
            "A validated published judge receipt is required"
        )
    try:
        return PublishedJudgeReceipt.model_validate(
            receipt.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise JudgeReceiptIntegrityError(
            "Published judge receipt integrity validation failed"
        ) from exc


def _parse_locator(payload: Any) -> GcsJudgeReceiptLocator:
    if not isinstance(payload, bytes):
        raise JudgeReceiptIntegrityError(
            "Cloud Storage returned a non-bytes judge receipt index"
        )
    if len(payload) > _MAX_INDEX_BYTES:
        raise JudgeReceiptIntegrityError(
            "Judge receipt index exceeds its maximum size"
        )
    try:
        return GcsJudgeReceiptLocator.model_validate_json(payload)
    except ValidationError as exc:
        raise JudgeReceiptIntegrityError(
            "Judge receipt index schema is invalid"
        ) from exc


def _blob_identity(blob: Any) -> tuple[int, str]:
    raw_generation = getattr(blob, "generation", None)
    if isinstance(raw_generation, bool):
        generation = None
    elif isinstance(raw_generation, int):
        generation = raw_generation
    elif isinstance(raw_generation, str) and raw_generation.isdigit():
        generation = int(raw_generation)
    else:
        generation = None
    crc32c = getattr(blob, "crc32c", None)
    if (
        generation is None
        or generation <= 0
        or not isinstance(crc32c, str)
        or not _CRC32C.fullmatch(crc32c)
    ):
        raise JudgeReceiptStorageError(
            "Cloud Storage omitted required generation or checksum metadata"
        )
    return generation, crc32c


def _validate_receipt_id(value: str) -> None:
    if not isinstance(value, str) or not _RECEIPT_ID.fullmatch(value):
        raise ValueError("receipt_id must be a canonical judge receipt UUID")


def _validate_project_id(value: str) -> str:
    if not isinstance(value, str) or not _PROJECT_ID.fullmatch(value):
        raise ValueError("project_id must be an exact Google Cloud project ID")
    return value


def _validate_bucket_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not _BUCKET_NAME.fullmatch(value)
        or ".." in value
        or ".-" in value
        or "-." in value
    ):
        raise ValueError("bucket_name must be an exact Cloud Storage bucket")
    return value


def _validate_prefix(value: str) -> str:
    if (
        not isinstance(value, str)
        or not _PREFIX.fullmatch(value)
        or "//" in value
        or any(part in {".", ".."} for part in value.split("/"))
    ):
        raise ValueError(
            "prefix must be a non-empty exact object-name prefix"
        )
    return value


def _is_precondition_failure(exc: Exception) -> bool:
    return type(exc).__name__ in {"Conflict", "PreconditionFailed"}


def _is_not_found(exc: Exception) -> bool:
    return type(exc).__name__ == "NotFound"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
