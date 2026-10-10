from __future__ import annotations

from src.gemini_workflow.evidence import GcsEvidenceStore


class FakeBlob:
    generation = 17
    metageneration = 3
    etag = "etag-value"
    crc32c = "crc-value"

    def __init__(self, name: str) -> None:
        self.name = name
        self.value = ""

    def upload_from_string(self, value: str, **kwargs) -> None:
        assert kwargs["if_generation_match"] == 0
        self.value = value


class FakeBucket:
    def __init__(self) -> None:
        self.created: list[FakeBlob] = []

    def blob(self, name: str) -> FakeBlob:
        blob = FakeBlob(name)
        self.created.append(blob)
        return blob


class FakeClient:
    def __init__(self) -> None:
        self.value = FakeBucket()

    def bucket(self, name: str) -> FakeBucket:
        assert name == "evidence-bucket"
        return self.value


def test_gcs_append_returns_generation_bound_receipt() -> None:
    client = FakeClient()
    store = GcsEvidenceStore(
        project_id="example-project",
        bucket_name="evidence-bucket",
        prefix="sanitized/gemini",
        client=client,
    )
    stored = store.append_with_receipt(
        {
            "event_type": "workflow_started",
            "run_id": "AIGC-GEMINI-RUN-synthetic",
            "correlation_id": "AIGC-CORR-synthetic",
            "status": "executing",
            "payload": {},
        }
    )

    assert stored.receipt.backend == "gcs"
    assert stored.receipt.object_uri.startswith(
        "gs://evidence-bucket/sanitized/gemini/"
    )
    assert stored.receipt.generation == 17
    assert stored.receipt.metageneration == 3
    assert stored.receipt.etag == "etag-value"
    assert stored.receipt.crc32c == "crc-value"
    assert stored.receipt.record_sha256 == stored.record.record_sha256
