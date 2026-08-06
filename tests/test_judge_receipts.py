from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect

import pytest
from pydantic import ValidationError

from src.gemini_workflow.judge_receipts import (
    JudgeReceiptClaim,
    JudgeReceiptConfirmationError,
    JudgeReceiptIntegrityError,
    JudgeReceiptNotFoundError,
    JudgeReceiptPublicationService,
    JudgeReceiptReadService,
    JudgeReceiptStorageError,
    PublishedJudgeReceipt,
    required_publication_phrase,
)


RECEIPT_ID = (
    "AIGC-JUDGE-RECEIPT-12345678-1234-4234-9234-123456789abc"
)
PREPARED_AT = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


class MemoryReceiptStore:
    def __init__(self) -> None:
        self.records: dict[str, PublishedJudgeReceipt] = {}
        self.write_count = 0

    def create_if_absent(self, receipt: PublishedJudgeReceipt) -> None:
        self.write_count += 1
        if receipt.receipt_id in self.records:
            raise RuntimeError("duplicate")
        self.records[receipt.receipt_id] = receipt

    def get(self, receipt_id: str) -> PublishedJudgeReceipt | None:
        return self.records.get(receipt_id)


def offline_claim(**overrides: object) -> JudgeReceiptClaim:
    payload: dict[str, object] = {
        "project_slug": "AIGC",
        "business_identity": "RegenExcalibur",
        "capability": "gemini_opportunity_assessment",
        "evidence_basis": "offline_repository_validation",
        "workflow_run_id": (
            "AIGC-GEMINI-RUN-12345678-1234-4234-9234-123456789abc"
        ),
        "source_revision": "a" * 40,
        "runtime_revision": None,
        "evidence_record_sha256": "b" * 64,
        "evidence_generation": None,
        "model_api_call_status": "not_attempted",
        "model_api_call_performed": False,
        "human_review_state": "required",
        "ai_use_disclosed": True,
        "external_action_performed": False,
    }
    payload.update(overrides)
    return JudgeReceiptClaim.model_validate(payload)


def publication_service(
    store: MemoryReceiptStore,
) -> JudgeReceiptPublicationService:
    times = iter(
        [
            PREPARED_AT,
            PREPARED_AT + timedelta(seconds=1),
        ]
    )
    return JudgeReceiptPublicationService(
        writer=store,
        clock=lambda: next(times),
        receipt_id_factory=lambda: RECEIPT_ID,
    )


@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    [
        ("intake", {"description": "private opportunity"}),
        ("model_output", {"rationale": ["generated"]}),
        ("operator_identity", {"subject_sha256": "c" * 64}),
        ("reason", "private review reason"),
        ("revision_instructions", "private instructions"),
    ],
)
def test_claim_rejects_non_public_fields(
    forbidden_key: str,
    forbidden_value: object,
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        offline_claim(**{forbidden_key: forbidden_value})


def test_public_receipt_contains_only_sanitized_categorical_evidence() -> None:
    store = MemoryReceiptStore()
    service = publication_service(store)
    draft = service.prepare(offline_claim())
    receipt = service.publish(
        draft,
        confirmation_phrase=required_publication_phrase(draft),
    )

    payload = receipt.model_dump(mode="json")
    assert set(payload) == {
        "schema_version",
        "receipt_id",
        "prepared_at",
        "published_at",
        "publication_state",
        "claim",
        "draft_sha256",
        "receipt_sha256",
    }
    assert set(payload["claim"]) == {
        "project_slug",
        "business_identity",
        "capability",
        "evidence_basis",
        "workflow_run_id",
        "source_revision",
        "runtime_revision",
        "evidence_record_sha256",
        "evidence_generation",
        "model_api_call_status",
        "model_api_call_performed",
        "human_review_state",
        "ai_use_disclosed",
        "external_action_performed",
    }
    public_keys = set(payload) | set(payload["claim"])
    for forbidden in {
        "description",
        "source_url",
        "constraints",
        "assessment",
        "rationale",
        "operator_subject",
        "reason",
        "revision_instructions",
    }:
        assert forbidden not in public_keys


@pytest.mark.parametrize(
    "confirmation_transform",
    [
        lambda value: value.lower(),
        lambda value: f"{value} ",
        lambda value: value.replace("SHA256", "sha256"),
        lambda value: value.replace("12345678", "12345679", 1),
    ],
)
def test_publication_requires_byte_exact_content_bound_confirmation(
    confirmation_transform,
) -> None:
    store = MemoryReceiptStore()
    service = publication_service(store)
    draft = service.prepare(offline_claim())

    with pytest.raises(JudgeReceiptConfirmationError, match="exact"):
        service.publish(
            draft,
            confirmation_phrase=confirmation_transform(
                required_publication_phrase(draft)
            ),
        )

    assert store.write_count == 0
    assert store.records == {}


def test_publication_rejects_tampered_draft_before_storage() -> None:
    store = MemoryReceiptStore()
    service = publication_service(store)
    draft = service.prepare(offline_claim())
    tampered = draft.model_copy(update={"draft_sha256": "0" * 64})

    with pytest.raises(JudgeReceiptIntegrityError, match="integrity"):
        service.publish(
            tampered,
            confirmation_phrase=(
                f"PUBLISH JUDGE RECEIPT {RECEIPT_ID} SHA256 {'0' * 64}"
            ),
        )

    assert store.write_count == 0


def test_live_claim_requires_complete_runtime_evidence() -> None:
    with pytest.raises(ValidationError, match="Live runtime claims"):
        offline_claim(
            evidence_basis="live_runtime_receipt",
            model_api_call_status="confirmed",
            model_api_call_performed=True,
        )

    claim = offline_claim(
        evidence_basis="live_runtime_receipt",
        model_api_call_status="confirmed",
        model_api_call_performed=True,
        runtime_revision="aigc-gemini-00042-xyz",
        evidence_generation=9,
    )
    assert claim.evidence_basis == "live_runtime_receipt"


def test_offline_claim_cannot_imply_a_live_model_call() -> None:
    with pytest.raises(ValidationError, match="Offline validation"):
        offline_claim(
            model_api_call_status="confirmed",
            model_api_call_performed=True,
        )


def test_read_service_is_read_only_and_revalidates_integrity() -> None:
    store = MemoryReceiptStore()
    publisher = publication_service(store)
    draft = publisher.prepare(offline_claim())
    receipt = publisher.publish(
        draft,
        confirmation_phrase=required_publication_phrase(draft),
    )
    reader = JudgeReceiptReadService(reader=store)

    assert reader.get(receipt.receipt_id) == receipt
    assert not hasattr(reader, "publish")
    assert not hasattr(reader, "prepare")

    store.records[receipt.receipt_id] = receipt.model_copy(
        update={"receipt_sha256": "0" * 64}
    )
    with pytest.raises(JudgeReceiptIntegrityError, match="integrity"):
        reader.get(receipt.receipt_id)


def test_read_service_handles_missing_and_invalid_storage_records() -> None:
    store = MemoryReceiptStore()
    reader = JudgeReceiptReadService(reader=store)
    with pytest.raises(JudgeReceiptNotFoundError):
        reader.get(RECEIPT_ID)

    store.records[RECEIPT_ID] = {"unsafe": "record"}  # type: ignore[assignment]
    with pytest.raises(JudgeReceiptStorageError, match="invalid"):
        reader.get(RECEIPT_ID)


def test_publication_service_has_no_provider_dependency() -> None:
    parameters = inspect.signature(
        JudgeReceiptPublicationService.__init__
    ).parameters
    assert set(parameters) == {
        "self",
        "writer",
        "clock",
        "receipt_id_factory",
    }
    assert "provider" not in JudgeReceiptPublicationService.__dict__
