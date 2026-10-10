from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from scripts.publish_gemini_judge_receipt import (
    JudgeReceiptCommandError,
    prepare_judge_receipt,
    publish_judge_receipt,
    validate_evidence_bundle,
)
from src.gemini_workflow.judge_receipts import (
    JudgeReceiptDraft,
    JudgeReceiptPublicationService,
    PublishedJudgeReceipt,
    required_publication_phrase,
)
from src.gemini_workflow.judge_store import (
    GcsJudgeReceiptLocator,
    GcsJudgeReceiptWriteResult,
)


NOW = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
RECEIPT_ID = (
    "AIGC-JUDGE-RECEIPT-12345678-1234-4234-9234-123456789abc"
)


class FailIfCalledWriter:
    def __init__(self) -> None:
        self.calls = 0

    def create_if_absent(self, receipt: PublishedJudgeReceipt) -> None:
        del receipt
        self.calls += 1
        raise AssertionError("prepare mode attempted publication")


class GenerationReceiptWriter:
    def __init__(self) -> None:
        self.calls = 0
        self.receipt: PublishedJudgeReceipt | None = None

    def create_if_absent(
        self,
        receipt: PublishedJudgeReceipt,
    ) -> GcsJudgeReceiptWriteResult:
        self.calls += 1
        self.receipt = receipt
        locator = GcsJudgeReceiptLocator(
            receipt_id=receipt.receipt_id,
            object_uri=(
                "gs://aigc-stage-judge/judge-receipts/v1/receipts/"
                f"{receipt.receipt_id}.json"
            ),
            generation=101,
            crc32c="YWJjZA==",
            content_sha256="d" * 64,
            receipt_sha256=receipt.receipt_sha256,
        )
        return GcsJudgeReceiptWriteResult(
            receipt=locator,
            index_uri=(
                "gs://aigc-stage-judge/judge-receipts/v1/index/"
                f"{receipt.receipt_id}.json"
            ),
            index_generation=102,
            index_crc32c="YWJjZA==",
            index_content_sha256="e" * 64,
        )


def bundle() -> tuple[dict, dict, dict, dict]:
    project = "aigc-stage-12345"
    release = "a" * 40
    digest = f"sha256:{'b' * 64}"
    authorization = json.loads(
        Path("config/gemini_staging_authorization.example.json").read_text(
            encoding="utf-8"
        )
    )
    authorization["release_revision"] = release
    authorization["gemini_model"] = "gemini-example-model"
    authorization["cloud"].update(
        {
            "project_id": project,
            "vertex_model_availability_reviewed": True,
            "artifact_registry_repository": "aigc-runtime",
            "cloud_sql_instance_connection_name": (
                f"{project}:northamerica-northeast1:aigc-control"
            ),
            "database_name": "aigc_control",
            "evidence_bucket": "aigc-stage-evidence",
            "judge_receipt_bucket": "aigc-stage-judge",
        }
    )
    authorization["service_accounts"] = {
        name: f"{name.replace('_', '-')}@{project}.iam.gserviceaccount.com"
        for name in (
            "deployer",
            "cloud_build",
            "operator_runtime",
            "judge_runtime",
        )
    }
    authorization["secret_manager_exact_version_refs"] = {
        name: f"projects/{project}/secrets/{name}/versions/1"
        for name in (
            "runtime_control_dsn",
            "operator_token",
            "operator_binding_key",
            "runtime_admin_token",
            "runtime_admin_binding_key",
            "judge_token",
            "judge_binding_key",
        )
    }
    authorization["iam_review"] = {
        "operator_runtime_roles": ["roles/aiplatform.user"],
        "judge_runtime_roles": ["roles/storage.objectViewer"],
        "deployer_roles": ["roles/run.developer"],
        "cloud_build_roles": ["roles/artifactregistry.writer"],
        "least_privilege_reviewed": True,
        "no_primitive_or_admin_roles": True,
        "secret_access_is_exact_secret_scoped": True,
        "storage_access_is_bucket_or_prefix_scoped": True,
        "cloud_run_invoker_bindings_reviewed": True,
        "judge_has_no_vertex_permission": True,
        "judge_has_no_control_store_write_permission": True,
        "judge_has_sanitized_prefix_read_only": True,
    }
    for name in authorization["evidence_controls"]:
        authorization["evidence_controls"][name] = True
    authorization["spending_control"].update(
        {
            "authorized_monthly_ceiling": 50,
            "billing_budget_configured": True,
            "vertex_quota_reviewed": True,
            "application_limits_reviewed": True,
            "acknowledges_budget_is_not_a_hard_cap": True,
        }
    )
    authorization["authorization"].update(
        {
            "configuration_reviewed": True,
            "resource_creation_authorized": True,
            "staging_deployment_authorized": True,
            "one_live_gemini_call_authorized": True,
            "judge_receipt_publication_authorized": True,
            "authorized_by": "Accountable owner",
            "authorized_at": "2026-07-27T00:00:00Z",
            "expires_at": "2026-07-29T00:00:00Z",
            "approval_phrase": (
                "AUTHORIZE AIGC GEMINI STAGING "
                f"{project} northamerica-northeast1 {release} "
                "CEILING CAD 50"
            ),
        }
    )
    deployment = {
        "schema_version": (
            "aigc.gemini-staging-deployment-receipt.v1"
        ),
        "project_id": project,
        "region": "northamerica-northeast1",
        "release_revision": release,
        "build_id": "build-123",
        "image_digest": digest,
        "immutable_image_uri": (
            "northamerica-northeast1-docker.pkg.dev/"
            f"{project}/aigc-runtime/aigc-gemini@{digest}"
        ),
        "operator_service": "aigc-gemini-operator-staging",
        "operator_revision": "aigc-gemini-operator-staging-00001-abc",
        "operator_candidate_url": "https://operator-candidate.example",
        "operator_service_url": "https://operator.example",
        "judge_service": "aigc-gemini-judge-staging",
        "judge_revision": "aigc-gemini-judge-staging-00001-def",
        "judge_candidate_url": "https://judge-candidate.example",
        "judge_service_url": "https://judge.example",
        "traffic_migration_performed": False,
        "live_model_call_performed": False,
        "external_business_action_performed": False,
        "captured_at": "2026-07-27T11:30:00Z",
    }
    ci_receipt = {
        "schema_version": "aigc.github-actions-ci-receipt.v1",
        "repository": "Lornt1666/AIGC",
        "workflow_name": "AIGC CI",
        "run_id": "123456",
        "run_url": (
            "https://github.com/Lornt1666/AIGC/actions/runs/123456"
        ),
        "head_sha": release,
        "conclusion": "success",
        "steps_executed": 37,
        "required_artifacts": [
            "gemini-workflow-offline-smoke-a",
            "test-results-a",
            "terraform-validation-a",
        ],
        "captured_at": "2026-07-27T11:00:00Z",
    }
    runtime_receipt = {
        "schema_version": "aigc.gemini-runtime-receipt.v1",
        "environment": "staging",
        "business_identity": "RegenExcalibur",
        "repository": "Lornt1666/AIGC",
        "release_revision": release,
        "image_digest": digest,
        "cloud_run_revision": deployment["operator_revision"],
        "provider": "google_vertex_ai",
        "model": "gemini-example-model",
        "location": "northamerica-northeast1",
        "response_id_present": True,
        "latency_ms": 420,
        "usage": {
            "prompt_tokens": 100,
            "candidate_tokens": 200,
            "total_tokens": 300,
        },
        "workflow_run_id": (
            "AIGC-GEMINI-RUN-12345678-1234-4234-9234-123456789abc"
        ),
        "input_sha256": "1" * 64,
        "assessment_sha256": "2" * 64,
        "policy_outcome": "allow",
        "model_api_call_status": "confirmed",
        "model_api_call_performed": True,
        "external_business_action_performed": False,
        "idempotency_key_sha256": "3" * 64,
        "evidence": {
            "object_uri": (
                "gs://aigc-stage-evidence/product-evidence/gemini/"
                "2026/07/27/execution.json"
            ),
            "generation": 91,
            "record_sha256": "c" * 64,
        },
        "ci": deepcopy(ci_receipt),
        "captured_at": "2026-07-27T11:45:00Z",
    }
    return authorization, deployment, ci_receipt, runtime_receipt


def prepare(
    tmp_path: Path,
) -> tuple[dict, dict, dict, dict, JudgeReceiptDraft]:
    authorization, deployment, ci_receipt, runtime_receipt = bundle()
    fail_writer = FailIfCalledWriter()
    service = JudgeReceiptPublicationService(
        writer=fail_writer,
        clock=lambda: NOW,
        receipt_id_factory=lambda: RECEIPT_ID,
    )
    draft = prepare_judge_receipt(
        authorization=authorization,
        deployment=deployment,
        ci_receipt=ci_receipt,
        runtime_receipt=runtime_receipt,
        output=tmp_path / "judge-draft.json",
        now=NOW,
        service=service,
    )
    assert fail_writer.calls == 0
    return (
        authorization,
        deployment,
        ci_receipt,
        runtime_receipt,
        draft,
    )


def test_default_preparation_is_local_only_and_content_bound(
    tmp_path: Path,
) -> None:
    *_, draft = prepare(tmp_path)

    stored = json.loads(
        (tmp_path / "judge-draft.json").read_text(encoding="utf-8")
    )
    assert stored["receipt_id"] == RECEIPT_ID
    assert stored["claim"]["evidence_basis"] == "live_runtime_receipt"
    assert stored["claim"]["source_revision"] == "a" * 40
    assert stored["claim"]["runtime_revision"].endswith("-00001-abc")
    assert stored["claim"]["evidence_generation"] == 91
    assert required_publication_phrase(draft) == (
        f"PUBLISH JUDGE RECEIPT {RECEIPT_ID} "
        f"SHA256 {draft.draft_sha256}"
    )


def test_publication_requires_judge_gate_before_any_storage_call(
    tmp_path: Path,
) -> None:
    (
        authorization,
        deployment,
        ci_receipt,
        runtime_receipt,
        draft,
    ) = prepare(tmp_path)
    authorization["authorization"][
        "judge_receipt_publication_authorized"
    ] = False
    writer = GenerationReceiptWriter()

    with pytest.raises(JudgeReceiptCommandError, match="judge gate"):
        publish_judge_receipt(
            authorization=authorization,
            deployment=deployment,
            ci_receipt=ci_receipt,
            runtime_receipt=runtime_receipt,
            draft=draft,
            confirmation_phrase=required_publication_phrase(draft),
            output=tmp_path / "publication.json",
            now=NOW,
            writer=writer,
        )

    assert writer.calls == 0
    assert not (tmp_path / "publication.json").exists()


def test_publication_requires_exact_content_bound_phrase(
    tmp_path: Path,
) -> None:
    (
        authorization,
        deployment,
        ci_receipt,
        runtime_receipt,
        draft,
    ) = prepare(tmp_path)
    writer = GenerationReceiptWriter()

    with pytest.raises(JudgeReceiptCommandError, match="exact content-bound"):
        publish_judge_receipt(
            authorization=authorization,
            deployment=deployment,
            ci_receipt=ci_receipt,
            runtime_receipt=runtime_receipt,
            draft=draft,
            confirmation_phrase=required_publication_phrase(draft) + " ",
            output=tmp_path / "publication.json",
            now=NOW,
            writer=writer,
        )

    assert writer.calls == 0


@pytest.mark.parametrize(
    ("target", "field", "value", "match"),
    [
        ("runtime", "release_revision", "f" * 40, "release_revision"),
        (
            "runtime",
            "image_digest",
            f"sha256:{'f' * 64}",
            "image_digest",
        ),
        (
            "runtime",
            "cloud_run_revision",
            "another-revision-00001-xyz",
            "cloud_run_revision",
        ),
        ("evidence", "generation", 0, "positive GCS generation"),
    ],
)
def test_exact_runtime_bindings_fail_closed(
    target: str,
    field: str,
    value: object,
    match: str,
) -> None:
    authorization, deployment, ci_receipt, runtime_receipt = bundle()
    if target == "runtime":
        runtime_receipt[field] = value
    else:
        runtime_receipt["evidence"][field] = value

    with pytest.raises(JudgeReceiptCommandError, match=match):
        validate_evidence_bundle(
            authorization=authorization,
            deployment=deployment,
            ci_receipt=ci_receipt,
            runtime_receipt=runtime_receipt,
            gate="judge",
            now=NOW,
        )


def test_runtime_must_embed_the_exact_successful_ci_receipt() -> None:
    authorization, deployment, ci_receipt, runtime_receipt = bundle()
    runtime_receipt["ci"]["run_id"] = "substituted"

    with pytest.raises(JudgeReceiptCommandError, match="exact supplied CI"):
        validate_evidence_bundle(
            authorization=authorization,
            deployment=deployment,
            ci_receipt=ci_receipt,
            runtime_receipt=runtime_receipt,
            gate="judge",
            now=NOW,
        )


def test_authorized_publication_records_create_only_gcs_generations(
    tmp_path: Path,
) -> None:
    (
        authorization,
        deployment,
        ci_receipt,
        runtime_receipt,
        draft,
    ) = prepare(tmp_path)
    writer = GenerationReceiptWriter()

    result = publish_judge_receipt(
        authorization=authorization,
        deployment=deployment,
        ci_receipt=ci_receipt,
        runtime_receipt=runtime_receipt,
        draft=draft,
        confirmation_phrase=required_publication_phrase(draft),
        output=tmp_path / "publication.json",
        now=NOW,
        writer=writer,
        clock=lambda: NOW + timedelta(seconds=1),
    )

    assert writer.calls == 1
    assert writer.receipt is not None
    assert result["publication_state"] == "published"
    assert result["gcs_create_only_objects_created"] == 2
    assert result["gcs_write_receipt"]["receipt"]["generation"] == 101
    assert result["gcs_write_receipt"]["index_generation"] == 102
    assert result["release_revision"] == "a" * 40
    assert result["image_digest"] == f"sha256:{'b' * 64}"
    assert result["operator_revision"].endswith("-00001-abc")
    assert result["runtime_evidence"]["generation"] == 91
    assert result["model_api_call_performed_during_publication"] is False
    assert json.loads(
        (tmp_path / "publication.json").read_text(encoding="utf-8")
    ) == result


def test_local_receipt_files_are_create_only(tmp_path: Path) -> None:
    authorization, deployment, ci_receipt, runtime_receipt = bundle()
    output = tmp_path / "judge-draft.json"
    output.write_text("existing\n", encoding="utf-8")

    with pytest.raises(JudgeReceiptCommandError, match="Refusing to overwrite"):
        prepare_judge_receipt(
            authorization=authorization,
            deployment=deployment,
            ci_receipt=ci_receipt,
            runtime_receipt=runtime_receipt,
            output=output,
            now=NOW,
        )

    assert output.read_text(encoding="utf-8") == "existing\n"


def test_existing_publication_receipt_blocks_before_gcs_write(
    tmp_path: Path,
) -> None:
    (
        authorization,
        deployment,
        ci_receipt,
        runtime_receipt,
        draft,
    ) = prepare(tmp_path)
    output = tmp_path / "publication.json"
    output.write_text("existing\n", encoding="utf-8")
    writer = GenerationReceiptWriter()

    with pytest.raises(JudgeReceiptCommandError, match="Refusing to overwrite"):
        publish_judge_receipt(
            authorization=authorization,
            deployment=deployment,
            ci_receipt=ci_receipt,
            runtime_receipt=runtime_receipt,
            draft=draft,
            confirmation_phrase=required_publication_phrase(draft),
            output=output,
            now=NOW,
            writer=writer,
        )

    assert writer.calls == 0
    assert output.read_text(encoding="utf-8") == "existing\n"
