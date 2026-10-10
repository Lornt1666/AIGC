from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json

import pytest

from src.gemini_workflow.judge_receipts import (
    JudgeReceiptClaim,
    JudgeReceiptConflictError,
    JudgeReceiptIntegrityError,
    JudgeReceiptPublicationService,
    PublishedJudgeReceipt,
    required_publication_phrase,
)
from src.gemini_workflow.judge_store import (
    GcsJudgeReceiptLocator,
    GcsJudgeReceiptReader,
    GcsJudgeReceiptWriter,
)
import src.gemini_workflow.judge_store as judge_store_module


RECEIPT_ID = (
    "AIGC-JUDGE-RECEIPT-12345678-1234-4234-9234-123456789abc"
)
PROJECT_ID = "regenexcalibur-prod"
BUCKET_NAME = "regenexcalibur-judge-receipts"
PREFIX = "public/judge/v1"
PREPARED_AT = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


class PreconditionFailed(Exception):
    pass


class NotFound(Exception):
    pass


class FakeObject:
    def __init__(
        self,
        *,
        payload: bytes,
        generation: int,
        crc32c: str,
    ) -> None:
        self.payload = payload
        self.generation = generation
        self.crc32c = crc32c


class FakeBlob:
    def __init__(
        self,
        client: "FakeStorageClient",
        bucket_name: str,
        name: str,
        generation: int | None,
    ) -> None:
        self._client = client
        self.bucket_name = bucket_name
        self.name = name
        self.generation = generation
        self.crc32c: str | None = None

    def upload_from_string(
        self,
        payload: bytes,
        *,
        content_type: str,
        if_generation_match: int,
        checksum: str,
    ) -> None:
        self._client.upload_calls.append(
            {
                "bucket": self.bucket_name,
                "name": self.name,
                "content_type": content_type,
                "if_generation_match": if_generation_match,
                "checksum": checksum,
            }
        )
        key = (self.bucket_name, self.name)
        if key in self._client.objects:
            raise PreconditionFailed("exists")
        generation = self._client.next_generation
        self._client.next_generation += 1
        crc32c = fake_crc32c(payload)
        self._client.objects[key] = FakeObject(
            payload=payload,
            generation=generation,
            crc32c=crc32c,
        )
        self.generation = generation
        self.crc32c = crc32c

    def reload(self, *, if_generation_match: int) -> None:
        self._client.reload_calls.append(
            {
                "bucket": self.bucket_name,
                "name": self.name,
                "generation": self.generation,
                "if_generation_match": if_generation_match,
            }
        )
        stored = self._stored()
        if stored.generation != if_generation_match:
            raise PreconditionFailed("generation mismatch")
        self.generation = stored.generation
        self.crc32c = stored.crc32c

    def download_as_bytes(
        self,
        *,
        checksum: str,
        if_generation_match: int | None = None,
    ) -> bytes:
        self._client.download_calls.append(
            {
                "bucket": self.bucket_name,
                "name": self.name,
                "generation": self.generation,
                "if_generation_match": if_generation_match,
                "checksum": checksum,
            }
        )
        stored = self._stored()
        if (
            if_generation_match is not None
            and stored.generation != if_generation_match
        ):
            raise PreconditionFailed("generation mismatch")
        self.generation = stored.generation
        self.crc32c = stored.crc32c
        return stored.payload

    def _stored(self) -> FakeObject:
        key = (self.bucket_name, self.name)
        try:
            stored = self._client.objects[key]
        except KeyError as exc:
            raise NotFound(self.name) from exc
        if (
            self.generation is not None
            and stored.generation != self.generation
        ):
            raise NotFound(f"{self.name}#{self.generation}")
        return stored


class FakeBucket:
    def __init__(
        self,
        client: "FakeStorageClient",
        bucket_name: str,
    ) -> None:
        self._client = client
        self.bucket_name = bucket_name

    def blob(
        self,
        name: str,
        generation: int | None = None,
    ) -> FakeBlob:
        self._client.blob_calls.append(
            {
                "bucket": self.bucket_name,
                "name": name,
                "generation": generation,
            }
        )
        return FakeBlob(
            self._client,
            self.bucket_name,
            name,
            generation,
        )


class FakeStorageClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], FakeObject] = {}
        self.next_generation = 1
        self.bucket_calls: list[str] = []
        self.blob_calls: list[dict[str, object]] = []
        self.upload_calls: list[dict[str, object]] = []
        self.reload_calls: list[dict[str, object]] = []
        self.download_calls: list[dict[str, object]] = []

    def bucket(self, bucket_name: str) -> FakeBucket:
        self.bucket_calls.append(bucket_name)
        return FakeBucket(self, bucket_name)


def fake_crc32c(payload: bytes) -> str:
    return base64.b64encode(hashlib.sha256(payload).digest()[:4]).decode()


def published_receipt(client: FakeStorageClient) -> PublishedJudgeReceipt:
    claim = JudgeReceiptClaim(
        project_slug="AIGC",
        business_identity="RegenExcalibur",
        capability="gemini_opportunity_assessment",
        evidence_basis="offline_repository_validation",
        workflow_run_id=(
            "AIGC-GEMINI-RUN-12345678-1234-4234-9234-123456789abc"
        ),
        source_revision="a" * 40,
        evidence_record_sha256="b" * 64,
        model_api_call_status="not_attempted",
        model_api_call_performed=False,
        human_review_state="required",
    )

    class CaptureWriter:
        def __init__(self) -> None:
            self.receipt: PublishedJudgeReceipt | None = None

        def create_if_absent(self, value: PublishedJudgeReceipt) -> None:
            self.receipt = value

    capture = CaptureWriter()
    times = iter([PREPARED_AT, PREPARED_AT + timedelta(seconds=1)])
    service = JudgeReceiptPublicationService(
        writer=capture,
        clock=lambda: next(times),
        receipt_id_factory=lambda: RECEIPT_ID,
    )
    draft = service.prepare(claim)
    service.publish(
        draft,
        confirmation_phrase=required_publication_phrase(draft),
    )
    assert capture.receipt is not None
    return capture.receipt


def writer(client: FakeStorageClient) -> GcsJudgeReceiptWriter:
    return GcsJudgeReceiptWriter(
        project_id=PROJECT_ID,
        bucket_name=BUCKET_NAME,
        prefix=PREFIX,
        client=client,
    )


def reader(client: FakeStorageClient) -> GcsJudgeReceiptReader:
    return GcsJudgeReceiptReader(
        project_id=PROJECT_ID,
        bucket_name=BUCKET_NAME,
        prefix=PREFIX,
        client=client,
    )


def test_writer_create_only_persists_generation_pinned_index() -> None:
    client = FakeStorageClient()
    receipt = published_receipt(client)
    result = writer(client).create_if_absent(receipt)

    receipt_name = f"{PREFIX}/receipts/{RECEIPT_ID}.json"
    index_name = f"{PREFIX}/index/{RECEIPT_ID}.json"
    assert [call["name"] for call in client.upload_calls] == [
        receipt_name,
        index_name,
    ]
    assert all(
        call["if_generation_match"] == 0
        and call["checksum"] == "crc32c"
        and call["content_type"] == "application/json"
        for call in client.upload_calls
    )
    assert result.receipt.object_uri == (
        f"gs://{BUCKET_NAME}/{receipt_name}"
    )
    assert result.receipt.generation == 1
    assert result.index_uri == f"gs://{BUCKET_NAME}/{index_name}"
    assert result.index_generation == 2
    assert result.receipt.crc32c
    assert result.index_crc32c

    index_payload = client.objects[
        (BUCKET_NAME, index_name)
    ].payload
    indexed = GcsJudgeReceiptLocator.model_validate_json(index_payload)
    assert indexed == result.receipt
    assert b"https://" not in index_payload
    assert b"signature" not in index_payload.lower()
    assert b"token" not in index_payload.lower()
    assert b"?" not in index_payload


def test_writer_conflict_does_not_overwrite_existing_receipt() -> None:
    client = FakeStorageClient()
    receipt = published_receipt(client)
    store = writer(client)
    store.create_if_absent(receipt)
    receipt_name = f"{PREFIX}/receipts/{RECEIPT_ID}.json"
    before = client.objects[(BUCKET_NAME, receipt_name)].payload

    with pytest.raises(JudgeReceiptConflictError, match="already exists"):
        store.create_if_absent(receipt)

    assert client.objects[(BUCKET_NAME, receipt_name)].payload == before
    assert all(
        call["if_generation_match"] == 0 for call in client.upload_calls
    )


def test_reader_uses_exact_prefix_and_pins_indexed_generation() -> None:
    client = FakeStorageClient()
    receipt = published_receipt(client)
    result = writer(client).create_if_absent(receipt)
    client.blob_calls.clear()
    client.download_calls.clear()
    client.reload_calls.clear()

    loaded = reader(client).get(RECEIPT_ID)

    receipt_name = f"{PREFIX}/receipts/{RECEIPT_ID}.json"
    index_name = f"{PREFIX}/index/{RECEIPT_ID}.json"
    assert loaded == receipt
    assert client.bucket_calls[-1] == BUCKET_NAME
    assert client.blob_calls == [
        {
            "bucket": BUCKET_NAME,
            "name": index_name,
            "generation": None,
        },
        {
            "bucket": BUCKET_NAME,
            "name": receipt_name,
            "generation": result.receipt.generation,
        },
    ]
    assert client.reload_calls[0]["if_generation_match"] == (
        result.receipt.generation
    )
    receipt_download = client.download_calls[-1]
    assert receipt_download["if_generation_match"] == (
        result.receipt.generation
    )
    assert receipt_download["checksum"] == "crc32c"


def test_reader_rejects_index_that_escapes_configured_bucket_or_prefix() -> None:
    client = FakeStorageClient()
    receipt = published_receipt(client)
    writer(client).create_if_absent(receipt)
    index_name = f"{PREFIX}/index/{RECEIPT_ID}.json"
    index_object = client.objects[(BUCKET_NAME, index_name)]
    locator = GcsJudgeReceiptLocator.model_validate_json(index_object.payload)
    escaped = locator.model_copy(
        update={
            "object_uri": (
                f"gs://other-bucket/{PREFIX}/receipts/{RECEIPT_ID}.json"
            )
        }
    )
    index_object.payload = escaped.model_dump_json().encode() + b"\n"
    client.blob_calls.clear()

    with pytest.raises(JudgeReceiptIntegrityError, match="bucket or prefix"):
        reader(client).get(RECEIPT_ID)

    assert [call["name"] for call in client.blob_calls] == [index_name]


@pytest.mark.parametrize("tamper", ["generation", "crc32c"])
def test_reader_verifies_indexed_generation_and_checksum(tamper: str) -> None:
    client = FakeStorageClient()
    receipt = published_receipt(client)
    writer(client).create_if_absent(receipt)
    index_name = f"{PREFIX}/index/{RECEIPT_ID}.json"
    index_object = client.objects[(BUCKET_NAME, index_name)]
    locator = GcsJudgeReceiptLocator.model_validate_json(index_object.payload)
    update: dict[str, object]
    if tamper == "generation":
        update = {"generation": locator.generation + 100}
    else:
        update = {"crc32c": "AAAAAA=="}
    index_object.payload = (
        locator.model_copy(update=update).model_dump_json().encode() + b"\n"
    )

    with pytest.raises(JudgeReceiptIntegrityError):
        reader(client).get(RECEIPT_ID)


def test_reader_rejects_receipt_content_mismatch() -> None:
    client = FakeStorageClient()
    receipt = published_receipt(client)
    writer(client).create_if_absent(receipt)
    receipt_name = f"{PREFIX}/receipts/{RECEIPT_ID}.json"
    stored = client.objects[(BUCKET_NAME, receipt_name)]
    stored.payload += b" "
    stored.crc32c = fake_crc32c(stored.payload)

    with pytest.raises(JudgeReceiptIntegrityError, match="checksum"):
        reader(client).get(RECEIPT_ID)


def test_reader_returns_none_only_when_index_is_missing() -> None:
    client = FakeStorageClient()
    assert reader(client).get(RECEIPT_ID) is None


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "/public/judge",
        "public/judge/",
        "public//judge",
        "public/../judge",
        "public judge",
    ],
)
def test_reader_rejects_non_exact_prefixes(prefix: str) -> None:
    with pytest.raises(ValueError, match="prefix"):
        GcsJudgeReceiptReader(
            project_id=PROJECT_ID,
            bucket_name=BUCKET_NAME,
            prefix=prefix,
            client=FakeStorageClient(),
        )


def test_reader_surface_and_module_are_strictly_read_only() -> None:
    public_methods = {
        name
        for name, member in inspect.getmembers(
            GcsJudgeReceiptReader,
            predicate=inspect.isfunction,
        )
        if not name.startswith("_")
    }
    assert public_methods == {"get"}

    source = inspect.getsource(judge_store_module)
    assert "generate_" + "signed_url" not in source
    assert "gemini_workflow.provider" not in source
    assert "gemini_workflow.control_store" not in source
    assert "list_blobs" not in source
