from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Literal, Protocol
import uuid

from pydantic import BaseModel, ConfigDict, Field

from .models import WorkflowRecord


class EvidenceStoreError(RuntimeError):
    """Raised when a workflow evidence event cannot be stored or verified."""


class EvidenceConflictError(EvidenceStoreError):
    """Raised when a single-use evidence transition already exists."""


class EvidenceWriteReceipt(BaseModel):
    """Storage-location receipt; never contains a signed or public URL."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["gcs", "jsonl_test"]
    object_uri: str | None = None
    generation: int | None = Field(default=None, gt=0)
    metageneration: int | None = Field(default=None, gt=0)
    etag: str | None = None
    crc32c: str | None = None
    record_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class StoredWorkflowEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: WorkflowRecord
    receipt: EvidenceWriteReceipt


class EvidenceStore(Protocol):
    def append(self, event: dict[str, Any]) -> WorkflowRecord: ...
    def append_operator_decision(self, event: dict[str, Any]) -> WorkflowRecord: ...
    def append_with_receipt(
        self,
        event: dict[str, Any],
    ) -> StoredWorkflowEvent: ...
    def append_operator_decision_with_receipt(
        self,
        event: dict[str, Any],
    ) -> StoredWorkflowEvent: ...
    def event_by_receipt(
        self,
        *,
        run_id: str,
        event_id: str,
        object_uri: str | None,
        generation: int | None,
    ) -> WorkflowRecord: ...
    def events_for_run(self, run_id: str) -> list[WorkflowRecord]: ...


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def finalize_event(event: dict[str, Any]) -> WorkflowRecord:
    payload = dict(event)
    if payload.get("external_action_performed") or payload.get(
        "external_business_action_performed"
    ):
        raise EvidenceStoreError(
            "The Gemini workflow cannot record an external business action"
        )
    payload.setdefault("event_id", f"AIGC-GEMINI-EVENT-{uuid.uuid4()}")
    payload.setdefault("created_at", utc_now())
    payload.setdefault("model_api_call_status", "not_attempted")
    payload.setdefault("model_api_call_performed", False)
    payload["external_business_action_performed"] = False
    payload["external_action_performed"] = False
    payload.pop("record_sha256", None)
    payload["record_sha256"] = canonical_hash(payload)
    return WorkflowRecord.model_validate(payload)


class JsonlEvidenceStore:
    """Append-only local evidence store for development and controlled export."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def append(self, event: dict[str, Any]) -> WorkflowRecord:
        return self.append_with_receipt(event).record

    def append_with_receipt(
        self,
        event: dict[str, Any],
    ) -> StoredWorkflowEvent:
        record = finalize_event(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = record.model_dump_json() + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
        return StoredWorkflowEvent(
            record=record,
            receipt=EvidenceWriteReceipt(
                backend="jsonl_test",
                record_sha256=record.record_sha256,
            ),
        )

    def append_operator_decision(self, event: dict[str, Any]) -> WorkflowRecord:
        return self.append_operator_decision_with_receipt(event).record

    def append_operator_decision_with_receipt(
        self,
        event: dict[str, Any],
    ) -> StoredWorkflowEvent:
        record = finalize_event(event)
        if record.event_type != "operator_decision":
            raise EvidenceStoreError(
                "append_operator_decision accepts only operator-decision events"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            records = self._read_records_unlocked()
            if any(
                item.run_id == record.run_id
                and item.event_type == "operator_decision"
                for item in records
            ):
                raise EvidenceConflictError(
                    "An operator decision has already been recorded"
                )
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(record.model_dump_json() + "\n")
                handle.flush()
        return StoredWorkflowEvent(
            record=record,
            receipt=EvidenceWriteReceipt(
                backend="jsonl_test",
                record_sha256=record.record_sha256,
            ),
        )

    def events_for_run(self, run_id: str) -> list[WorkflowRecord]:
        with self._lock:
            records = self._read_records_unlocked()
        return sorted(
            [item for item in records if item.run_id == run_id],
            key=lambda item: item.created_at,
        )

    def event_by_receipt(
        self,
        *,
        run_id: str,
        event_id: str,
        object_uri: str | None,
        generation: int | None,
    ) -> WorkflowRecord:
        if object_uri is not None or generation is not None:
            raise EvidenceStoreError(
                "JSONL test evidence must not claim a GCS receipt"
            )
        records = self.events_for_run(run_id)
        matches = [item for item in records if item.event_id == event_id]
        if len(matches) != 1:
            raise EvidenceStoreError(
                "Exact JSONL evidence event could not be resolved"
            )
        return matches[0]

    def _read_records_unlocked(self) -> list[WorkflowRecord]:
        if not self.path.exists():
            return []
        records: list[WorkflowRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = WorkflowRecord.model_validate_json(line)
            raw = record.model_dump(mode="json")
            expected = raw.pop("record_sha256")
            if canonical_hash(raw) != expected:
                raise EvidenceStoreError("Evidence record integrity check failed")
            records.append(record)
        return records


class GcsEvidenceStore:
    """One create-only Cloud Storage object per evidence event."""

    def __init__(
        self,
        *,
        project_id: str,
        bucket_name: str,
        prefix: str,
        client: Any | None = None,
    ) -> None:
        self.project_id = project_id
        self.bucket_name = bucket_name
        self.prefix = prefix.strip("/")
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import storage
            except ImportError as exc:
                raise EvidenceStoreError(
                    "google-cloud-storage is required for GCS evidence"
                ) from exc
            self._client = storage.Client(project=self.project_id)
        return self._client

    def append(self, event: dict[str, Any]) -> WorkflowRecord:
        return self.append_with_receipt(event).record

    def append_with_receipt(
        self,
        event: dict[str, Any],
    ) -> StoredWorkflowEvent:
        record = finalize_event(event)
        safe_time = record.created_at.replace(":", "-")
        object_name = (
            f"{self.prefix}/{record.run_id}/"
            f"{safe_time}-{record.event_id}.json"
        )
        receipt = self._upload_record(record, object_name)
        return StoredWorkflowEvent(record=record, receipt=receipt)

    def append_operator_decision(self, event: dict[str, Any]) -> WorkflowRecord:
        return self.append_operator_decision_with_receipt(event).record

    def append_operator_decision_with_receipt(
        self,
        event: dict[str, Any],
    ) -> StoredWorkflowEvent:
        record = finalize_event(event)
        if record.event_type != "operator_decision":
            raise EvidenceStoreError(
                "append_operator_decision accepts only operator-decision events"
            )
        object_name = f"{self.prefix}/{record.run_id}/operator-decision.json"
        receipt = self._upload_record(record, object_name, single_use=True)
        return StoredWorkflowEvent(record=record, receipt=receipt)

    def _upload_record(
        self,
        record: WorkflowRecord,
        object_name: str,
        *,
        single_use: bool = False,
    ) -> EvidenceWriteReceipt:
        try:
            blob = self._get_client().bucket(self.bucket_name).blob(object_name)
            blob.upload_from_string(
                record.model_dump_json(indent=2) + "\n",
                content_type="application/json",
                if_generation_match=0,
            )
            generation = _positive_int(getattr(blob, "generation", None))
            metageneration = _positive_int(
                getattr(blob, "metageneration", None)
            )
            if generation is None:
                raise EvidenceStoreError(
                    "Cloud Storage did not return an object generation receipt"
                )
            object_uri = f"gs://{self.bucket_name}/{object_name}"
            expected_prefix = (
                f"gs://{self.bucket_name}/{self.prefix}/"
                if self.prefix
                else f"gs://{self.bucket_name}/"
            )
            if not object_uri.startswith(expected_prefix):
                raise EvidenceStoreError(
                    "Cloud Storage evidence receipt escaped its configured prefix"
                )
            return EvidenceWriteReceipt(
                backend="gcs",
                object_uri=object_uri,
                generation=generation,
                metageneration=metageneration,
                etag=_optional_text(getattr(blob, "etag", None)),
                crc32c=_optional_text(getattr(blob, "crc32c", None)),
                record_sha256=record.record_sha256,
            )
        except Exception as exc:
            if isinstance(exc, EvidenceStoreError):
                raise
            if single_use and type(exc).__name__ in {
                "Conflict",
                "PreconditionFailed",
            }:
                raise EvidenceConflictError(
                    "An operator decision has already been recorded"
                ) from exc
            raise EvidenceStoreError(
                f"Cloud Storage evidence write failed: {type(exc).__name__}"
            ) from exc

    def events_for_run(self, run_id: str) -> list[WorkflowRecord]:
        object_prefix = f"{self.prefix}/{run_id}/"
        try:
            blobs = self._get_client().list_blobs(
                self.bucket_name,
                prefix=object_prefix,
            )
            records = [
                WorkflowRecord.model_validate_json(blob.download_as_text())
                for blob in blobs
            ]
        except Exception as exc:
            raise EvidenceStoreError(
                f"Cloud Storage evidence read failed: {type(exc).__name__}"
            ) from exc
        for record in records:
            raw = record.model_dump(mode="json")
            expected = raw.pop("record_sha256")
            if canonical_hash(raw) != expected:
                raise EvidenceStoreError("Evidence record integrity check failed")
        return sorted(records, key=lambda item: item.created_at)

    def event_by_receipt(
        self,
        *,
        run_id: str,
        event_id: str,
        object_uri: str | None,
        generation: int | None,
    ) -> WorkflowRecord:
        if not object_uri or generation is None or generation <= 0:
            raise EvidenceStoreError(
                "GCS evidence requires an exact object URI and generation"
            )
        expected_prefix = (
            f"gs://{self.bucket_name}/{self.prefix}/"
            if self.prefix
            else f"gs://{self.bucket_name}/"
        )
        if (
            not object_uri.startswith(expected_prefix)
            or "?" in object_uri
            or "#" in object_uri
        ):
            raise EvidenceStoreError(
                "GCS evidence receipt escaped its configured bucket or prefix"
            )
        object_name = object_uri.removeprefix(
            f"gs://{self.bucket_name}/"
        )
        expected_run_prefix = f"{self.prefix}/{run_id}/"
        if not object_name.startswith(expected_run_prefix):
            raise EvidenceStoreError(
                "GCS evidence receipt does not match the requested run"
            )
        try:
            blob = self._get_client().bucket(self.bucket_name).blob(
                object_name,
                generation=generation,
            )
            blob.reload(if_generation_match=generation)
            if int(getattr(blob, "generation", 0)) != generation:
                raise EvidenceStoreError(
                    "GCS evidence generation does not match its receipt"
                )
            record = WorkflowRecord.model_validate_json(
                blob.download_as_text(
                    if_generation_match=generation,
                    checksum="crc32c",
                )
            )
        except EvidenceStoreError:
            raise
        except Exception as exc:
            raise EvidenceStoreError(
                f"Generation-pinned evidence read failed: {type(exc).__name__}"
            ) from exc
        raw = record.model_dump(mode="json")
        expected_hash = raw.pop("record_sha256")
        if canonical_hash(raw) != expected_hash:
            raise EvidenceStoreError("Evidence record integrity check failed")
        if record.run_id != run_id or record.event_id != event_id:
            raise EvidenceStoreError(
                "Generation-pinned evidence identity does not match"
            )
        return record


def _positive_int(value: Any) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
