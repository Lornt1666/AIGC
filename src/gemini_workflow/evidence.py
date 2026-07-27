from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Protocol
import uuid

from .models import WorkflowRecord


class EvidenceStoreError(RuntimeError):
    """Raised when a workflow evidence event cannot be stored or verified."""


class EvidenceConflictError(EvidenceStoreError):
    """Raised when a single-use evidence transition already exists."""


class EvidenceStore(Protocol):
    def append(self, event: dict[str, Any]) -> WorkflowRecord: ...
    def append_human_decision(self, event: dict[str, Any]) -> WorkflowRecord: ...
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
        record = finalize_event(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = record.model_dump_json() + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
        return record

    def append_human_decision(self, event: dict[str, Any]) -> WorkflowRecord:
        record = finalize_event(event)
        if record.event_type != "human_decision":
            raise EvidenceStoreError(
                "append_human_decision accepts only human-decision events"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            records = self._read_records_unlocked()
            if any(
                item.run_id == record.run_id
                and item.event_type == "human_decision"
                for item in records
            ):
                raise EvidenceConflictError(
                    "A human decision has already been recorded"
                )
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(record.model_dump_json() + "\n")
                handle.flush()
        return record

    def events_for_run(self, run_id: str) -> list[WorkflowRecord]:
        with self._lock:
            records = self._read_records_unlocked()
        return sorted(
            [item for item in records if item.run_id == run_id],
            key=lambda item: item.created_at,
        )

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
        record = finalize_event(event)
        safe_time = record.created_at.replace(":", "-")
        object_name = (
            f"{self.prefix}/{record.run_id}/"
            f"{safe_time}-{record.event_id}.json"
        )
        self._upload_record(record, object_name)
        return record

    def append_human_decision(self, event: dict[str, Any]) -> WorkflowRecord:
        record = finalize_event(event)
        if record.event_type != "human_decision":
            raise EvidenceStoreError(
                "append_human_decision accepts only human-decision events"
            )
        object_name = f"{self.prefix}/{record.run_id}/human-decision.json"
        self._upload_record(record, object_name, single_use=True)
        return record

    def _upload_record(
        self,
        record: WorkflowRecord,
        object_name: str,
        *,
        single_use: bool = False,
    ) -> None:
        try:
            blob = self._get_client().bucket(self.bucket_name).blob(object_name)
            blob.upload_from_string(
                record.model_dump_json(indent=2) + "\n",
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:
            if single_use and type(exc).__name__ in {
                "Conflict",
                "PreconditionFailed",
            }:
                raise EvidenceConflictError(
                    "A human decision has already been recorded"
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
