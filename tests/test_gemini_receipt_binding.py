from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.gemini_workflow.control_store import (
    InMemoryRuntimeControlStore,
    RuntimeControlUnavailableError,
)
from src.gemini_workflow.evidence import (
    EvidenceStoreError,
    GcsEvidenceStore,
    JsonlEvidenceStore,
)
from src.gemini_workflow.models import (
    GeminiAssessment,
    HumanDecisionRequest,
    OperatorIdentity,
    OpportunityIntake,
)
from src.gemini_workflow.provider import StubGeminiProvider
from src.gemini_workflow.service import (
    GeminiWorkflowInProgressError,
    GeminiWorkflowService,
    GeminiWorkflowStateError,
)
from src.gemini_workflow.settings import (
    GeminiWorkflowConfigurationError,
    GeminiWorkflowSettings,
)


def _assessment() -> GeminiAssessment:
    return GeminiAssessment.model_validate(
        {
            "fit_score": 85,
            "recommendation": "pursue",
            "rationale": ["Strong fit.", "Scope is reviewable."],
            "evidence_basis": [
                {
                    "input_pointer": "/description",
                    "observation": (
                        "The supplied description states the opportunity."
                    ),
                    "impact": "positive",
                }
            ],
            "assumptions": [],
            "risks": [],
            "clarifying_questions": [],
            "proposed_scope": ["Prepare an internal scope."],
            "ai_use_disclosure": (
                "AI assisted with assessment and drafting; a human reviews "
                "the result."
            ),
            "human_review_required": True,
        }
    )


def _intake() -> OpportunityIntake:
    return OpportunityIntake.model_validate(
        {
            "title": "Receipt race opportunity",
            "description": (
                "A sufficiently detailed permitted opportunity description."
            ),
            "source_url": "https://example.com/opportunity",
            "constraints": ["No external action"],
            "ai_assistance_permitted": True,
            "ai_disclosure_required": True,
        }
    )


def _actor() -> OperatorIdentity:
    return OperatorIdentity(
        principal_id="1" * 64,
        subject_sha256="2" * 64,
        role="operator",
        auth_method="offline_test",
        identity_assurance="offline_test",
    )


class _FailingRunCompletionStore(InMemoryRuntimeControlStore):
    def __init__(self) -> None:
        super().__init__()
        self.failed_run_id: str | None = None

    def complete_run(self, **kwargs: Any):
        self.failed_run_id = kwargs["run_id"]
        raise RuntimeControlUnavailableError(
            "Synthetic failure after execution evidence persistence"
        )


class _FailingDecisionCompletionStore(InMemoryRuntimeControlStore):
    def complete_decision(self, **_kwargs: Any):
        raise RuntimeControlUnavailableError(
            "Synthetic failure after decision evidence persistence"
        )


def test_orphan_execution_evidence_is_quarantined_from_all_service_paths(
    tmp_path: Path,
) -> None:
    evidence_store = JsonlEvidenceStore(tmp_path / "execution-race.jsonl")
    control_store = _FailingRunCompletionStore()
    workflow = GeminiWorkflowService(
        provider=StubGeminiProvider(_assessment()),
        evidence_store=evidence_store,
        control_store=control_store,
    )
    idempotency_key = "receipt-race-execution-0001"

    with pytest.raises(
        RuntimeControlUnavailableError,
        match="after execution evidence",
    ):
        workflow.create_workflow(
            _intake(),
            actor=_actor(),
            idempotency_key=idempotency_key,
        )

    run_id = control_store.failed_run_id
    assert run_id is not None
    assert [
        event.event_type for event in evidence_store.events_for_run(run_id)
    ] == ["workflow_started", "gemini_execution"]
    reservation = control_store.get_run(run_id)
    assert reservation.state == "executing"
    assert reservation.execution_event_id is None
    assert reservation.evidence_object_uri is None
    assert reservation.evidence_generation is None

    assert [
        event.event_type for event in workflow.get_workflow(run_id)
    ] == ["workflow_started"]
    with pytest.raises(GeminiWorkflowInProgressError) as replay:
        workflow.create_workflow(
            _intake(),
            actor=_actor(),
            idempotency_key=idempotency_key,
        )
    assert replay.value.run_id == run_id
    with pytest.raises(
        GeminiWorkflowStateError,
        match="receipt-bound execution",
    ):
        workflow.decide(
            run_id,
            HumanDecisionRequest(
                decision="deny",
                reason="Quarantined execution evidence cannot be reviewed.",
            ),
            actor=_actor(),
        )


def test_orphan_decision_evidence_is_hidden_without_completion_marker(
    tmp_path: Path,
) -> None:
    evidence_store = JsonlEvidenceStore(tmp_path / "decision-race.jsonl")
    control_store = _FailingDecisionCompletionStore()
    workflow = GeminiWorkflowService(
        provider=StubGeminiProvider(_assessment()),
        evidence_store=evidence_store,
        control_store=control_store,
    )
    execution = workflow.create_workflow(
        _intake(),
        actor=_actor(),
        idempotency_key="receipt-race-decision-0001",
    )

    with pytest.raises(
        RuntimeControlUnavailableError,
        match="after decision evidence",
    ):
        workflow.decide(
            execution.run_id,
            HumanDecisionRequest(
                decision="deny",
                reason="The operator denies this internal assessment.",
            ),
            actor=_actor(),
        )

    assert [
        event.event_type
        for event in evidence_store.events_for_run(execution.run_id)
    ] == [
        "workflow_started",
        "gemini_execution",
        "operator_decision",
    ]
    reservation = control_store.get_run(execution.run_id)
    assert reservation.state == "completed"
    assert reservation.decision_event_id is None
    assert reservation.decision_object_uri is None
    assert reservation.decision_generation is None
    assert [
        event.event_type for event in workflow.get_workflow(execution.run_id)
    ] == ["workflow_started", "gemini_execution"]


class _VersionedBlob:
    def __init__(
        self,
        name: str,
        objects: dict[str, tuple[int, str]],
        requested_generation: int | None = None,
    ) -> None:
        self.name = name
        self.objects = objects
        self.requested_generation = requested_generation
        self.metageneration = 1
        self.etag = "synthetic-etag"
        self.crc32c = "synthetic-crc32c"

    @property
    def generation(self) -> int:
        return self.objects.get(self.name, (17, ""))[0]

    def upload_from_string(self, value: str, **kwargs: Any) -> None:
        assert kwargs["if_generation_match"] == 0
        if self.name in self.objects:
            raise RuntimeError("create-only object already exists")
        self.objects[self.name] = (17, value)

    def reload(self, *, if_generation_match: int) -> None:
        if self.name not in self.objects:
            raise RuntimeError("object does not exist")
        actual_generation = self.objects[self.name][0]
        if (
            self.requested_generation != actual_generation
            or if_generation_match != actual_generation
        ):
            raise RuntimeError("generation does not exist")

    def download_as_text(self, **kwargs: Any) -> str:
        actual_generation, value = self.objects[self.name]
        if kwargs.get("if_generation_match") != actual_generation:
            raise RuntimeError("generation precondition failed")
        assert kwargs["checksum"] == "crc32c"
        return value


class _VersionedBucket:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[int, str]] = {}

    def blob(
        self,
        name: str,
        generation: int | None = None,
    ) -> _VersionedBlob:
        return _VersionedBlob(name, self.objects, generation)


class _VersionedClient:
    def __init__(self) -> None:
        self.bucket_value = _VersionedBucket()

    def bucket(self, name: str) -> _VersionedBucket:
        assert name == "evidence-bucket"
        return self.bucket_value


def test_gcs_receipt_read_requires_exact_uri_generation_and_identity() -> None:
    store = GcsEvidenceStore(
        project_id="example-project",
        bucket_name="evidence-bucket",
        prefix="sanitized/gemini",
        client=_VersionedClient(),
    )
    stored = store.append_with_receipt(
        {
            "event_type": "workflow_started",
            "run_id": "AIGC-GEMINI-RUN-receipt-binding",
            "correlation_id": "AIGC-CORR-receipt-binding",
            "status": "executing",
            "payload": {},
        }
    )
    receipt = stored.receipt
    assert receipt.object_uri is not None
    assert receipt.generation == 17

    resolved = store.event_by_receipt(
        run_id=stored.record.run_id,
        event_id=stored.record.event_id,
        object_uri=receipt.object_uri,
        generation=receipt.generation,
    )
    assert resolved == stored.record

    with pytest.raises(EvidenceStoreError, match="Generation-pinned"):
        store.event_by_receipt(
            run_id=stored.record.run_id,
            event_id=stored.record.event_id,
            object_uri=receipt.object_uri,
            generation=18,
        )
    with pytest.raises(EvidenceStoreError, match="Generation-pinned"):
        store.event_by_receipt(
            run_id=stored.record.run_id,
            event_id=stored.record.event_id,
            object_uri=(
                receipt.object_uri.rsplit("/", 1)[0] + "/other-object.json"
            ),
            generation=receipt.generation,
        )
    with pytest.raises(EvidenceStoreError, match="requested run"):
        store.event_by_receipt(
            run_id="AIGC-GEMINI-RUN-other",
            event_id=stored.record.event_id,
            object_uri=receipt.object_uri,
            generation=receipt.generation,
        )
    with pytest.raises(EvidenceStoreError, match="identity"):
        store.event_by_receipt(
            run_id=stored.record.run_id,
            event_id="AIGC-GEMINI-EVENT-other",
            object_uri=receipt.object_uri,
            generation=receipt.generation,
        )


def _set_production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "AIGC_GEMINI_ENABLED": "true",
        "GOOGLE_CLOUD_PROJECT": "regenexcalibur-staging",
        "GOOGLE_CLOUD_LOCATION": "northamerica-northeast1",
        "AIGC_GEMINI_MODEL": "gemini-2.5-pro",
        "AIGC_GEMINI_EVIDENCE_BACKEND": "gcs",
        "AIGC_GEMINI_EVIDENCE_BUCKET": "regenexcalibur-evidence",
        "AIGC_ENV": "production",
        "AIGC_RELEASE_REVISION": "a" * 40,
        "K_REVISION": "aigc-gemini-operator-00001-abc",
        "AIGC_IMAGE_DIGEST": "sha256:" + ("b" * 64),
        "AIGC_SURFACE": "judge",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_production_accepts_exactly_one_provider_transport_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_environment(monkeypatch)
    monkeypatch.setenv("AIGC_GEMINI_MAX_ATTEMPTS", "1")

    settings = GeminiWorkflowSettings.from_env()

    assert settings.max_attempts == 1


def test_production_rejects_multiple_provider_transport_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_environment(monkeypatch)
    monkeypatch.setenv("AIGC_GEMINI_MAX_ATTEMPTS", "2")

    with pytest.raises(
        GeminiWorkflowConfigurationError,
        match="exactly one provider transport attempt",
    ):
        GeminiWorkflowSettings.from_env()


def test_production_rejects_unsupported_toronto_gemini_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_environment(monkeypatch)
    monkeypatch.setenv(
        "GOOGLE_CLOUD_LOCATION",
        "northamerica-northeast2",
    )

    with pytest.raises(
        GeminiWorkflowConfigurationError,
        match="northamerica-northeast1",
    ):
        GeminiWorkflowSettings.from_env()
