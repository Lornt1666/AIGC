from __future__ import annotations

from datetime import date, timedelta
import sqlite3

import pytest
from pydantic import ValidationError

from automated_canadian_grant_system.core.constitutional_guardrails import (
    ACGSGuardrailError,
)
from automated_canadian_grant_system.core.models import (
    GrantApplicationRequest,
    OperatorReviewRequest,
)
from automated_canadian_grant_system.core.orchestrator import GrantOrchestrator
from automated_canadian_grant_system.database.storage import (
    GrantApplicationStateError,
)
from automated_canadian_grant_system.tests.test_grant_pipeline import (
    application_payload,
    operator_review_payload,
)


def build_service(tmp_path) -> GrantOrchestrator:
    return GrantOrchestrator(database_path=tmp_path / "acgs-local.sqlite3")


def create_application(service: GrantOrchestrator) -> dict:
    return service.generate(
        GrantApplicationRequest.model_validate(application_payload())
    )


def test_generated_draft_is_persisted_with_source_and_ai_audit_metadata(
    tmp_path,
) -> None:
    service = build_service(tmp_path)
    generated = create_application(service)

    record = service.get_application(generated["application_id"])
    assert record["lifecycle_state"] == "AUDITED_REVIEW_REQUIRED"
    assert record["revision"] == 1
    assert record["external_submission_performed"] is False
    assert record["package"]["source_attribution"]["portal_id"] == (
        "alberta_innovates"
    )
    assert record["package"]["ai_use_disclosure"]
    assert len(record["audit_events"]) == 1
    audit = record["audit_events"][0]
    assert audit["event_type"] == "grant_application.draft_generated"
    assert audit["metadata"]["source_attribution"]["portal_id"] == (
        "alberta_innovates"
    )
    assert audit["metadata"]["ai_use_disclosure_present"] is True
    assert audit["event_hash"]


def test_operator_review_approves_only_a_local_export(tmp_path) -> None:
    service = build_service(tmp_path)
    generated = create_application(service)

    reviewed = service.review_application(
        generated["application_id"],
        OperatorReviewRequest.model_validate(operator_review_payload()),
    )

    assert reviewed["lifecycle_state"] == "LOCAL_EXPORT_APPROVED"
    assert reviewed["revision"] == 2
    assert reviewed["operator_reviews"][0]["local_export_approved"] is True
    assert reviewed["operator_reviews"][0]["phase5_submission_approved"] is False
    assert reviewed["audit_events"][1]["previous_event_hash"] == (
        reviewed["audit_events"][0]["event_hash"]
    )
    exported = service.local_export(generated["application_id"])
    assert exported["source_attribution"]["operator_reviewed_source"][
        "source_version"
    ] == "operator-record-2026-09"
    assert exported["draft"]["ai_use_disclosure"]
    assert exported["submission"]["external_submission_performed"] is False
    assert exported["external_action_performed"] is False
    assert exported["artifact_digest"] == exported["operator_review"][
        "approved_artifact_digest"
    ]


def test_return_for_revision_blocks_export_and_additional_review(tmp_path) -> None:
    service = build_service(tmp_path)
    generated = create_application(service)
    review_payload = operator_review_payload(decision="return_for_revision")

    reviewed = service.review_application(
        generated["application_id"],
        OperatorReviewRequest.model_validate(review_payload),
    )

    assert reviewed["lifecycle_state"] == "REVISION_REQUIRED"
    assert reviewed["revision"] == 2
    with pytest.raises(GrantApplicationStateError):
        service.local_export(generated["application_id"])
    with pytest.raises(GrantApplicationStateError):
        service.review_application(
            generated["application_id"],
            OperatorReviewRequest.model_validate(
                operator_review_payload(expected_revision=2)
            ),
        )


def test_stale_source_and_unsupported_claims_block_local_export(tmp_path) -> None:
    service = build_service(tmp_path)
    generated = create_application(service)
    stale_payload = operator_review_payload(
        source_reviewed_at=(date.today() - timedelta(days=31)).isoformat()
    )

    with pytest.raises(ACGSGuardrailError, match="stale"):
        service.review_application(
            generated["application_id"],
            OperatorReviewRequest.model_validate(stale_payload),
        )

    unsupported_payload = application_payload()
    project = dict(unsupported_payload["project"])
    project["project_summary"] = (
        "This project will be awarded a grant and guarantee success."
    )
    unsupported_payload["project"] = project
    unsupported = service.generate(
        GrantApplicationRequest.model_validate(unsupported_payload)
    )
    with pytest.raises(ACGSGuardrailError, match="UNSUPPORTED_"):
        service.review_application(
            unsupported["application_id"],
            OperatorReviewRequest.model_validate(operator_review_payload()),
        )


def test_reviewed_criteria_mismatch_blocks_local_export(tmp_path) -> None:
    service = build_service(tmp_path)
    generated = create_application(service)
    review_payload = operator_review_payload()
    criteria = dict(review_payload["operator_attested_criteria"])
    criteria["min_trl"] = 7
    review_payload["operator_attested_criteria"] = criteria

    with pytest.raises(
        ACGSGuardrailError,
        match="does not match operator-attested eligibility criteria: minimum_trl",
    ):
        service.review_application(
            generated["application_id"],
            OperatorReviewRequest.model_validate(review_payload),
        )


def test_missing_review_attestation_or_budget_evidence_is_rejected() -> None:
    unverified = operator_review_payload(operator_attests_current_source=False)
    with pytest.raises(ValidationError):
        OperatorReviewRequest.model_validate(unverified)

    incomplete_budget = operator_review_payload(
        budget_evidence_references=[],
    )
    with pytest.raises(ValidationError):
        OperatorReviewRequest.model_validate(incomplete_budget)

    blank_region = operator_review_payload()
    reviewed_criteria = dict(blank_region["operator_attested_criteria"])
    reviewed_criteria["eligible_regions"] = [""]
    blank_region["operator_attested_criteria"] = reviewed_criteria
    with pytest.raises(ValidationError, match="eligible regions cannot be blank"):
        OperatorReviewRequest.model_validate(blank_region)


def test_unregistered_source_host_and_secret_like_input_are_blocked(
    tmp_path,
) -> None:
    service = build_service(tmp_path)
    hostile_payload = application_payload()
    grant = dict(hostile_payload["grant"])
    grant["guideline_url"] = "https://untrusted.example/grant"
    hostile_payload["grant"] = grant
    with pytest.raises(ACGSGuardrailError, match="registered official portal"):
        service.generate(GrantApplicationRequest.model_validate(hostile_payload))

    secret_url_payload = application_payload()
    secret_url_grant = dict(secret_url_payload["grant"])
    secret_url_grant["guideline_url"] = (
        "https://albertainnovates.ca/sk-abcdefghijk"
    )
    secret_url_payload["grant"] = secret_url_grant
    with pytest.raises(ACGSGuardrailError, match="secret-like"):
        service.generate(
            GrantApplicationRequest.model_validate(secret_url_payload)
        )

    generated = create_application(service)
    review_url_payload = operator_review_payload()
    review_url = "https://albertainnovates.ca/sk-abcdefghijk"
    review_url_payload["source_guideline_url"] = review_url
    review_url_payload["source_evidence_references"] = [
        review_url,
        "operator-record://alberta-source-review-2026-09",
    ]
    with pytest.raises(ACGSGuardrailError, match="secret-like"):
        service.review_application(
            generated["application_id"],
            OperatorReviewRequest.model_validate(review_url_payload),
        )

    secret_like_payload = application_payload()
    project = dict(secret_like_payload["project"])
    project["project_summary"] = (
        "Do not store this " + "to" + "ken: test-only-value."
    )
    secret_like_payload["project"] = project
    with pytest.raises(ACGSGuardrailError, match="secret-like"):
        service.generate(
            GrantApplicationRequest.model_validate(secret_like_payload)
        )


def test_operator_review_records_are_append_only(tmp_path) -> None:
    database_path = tmp_path / "acgs-local.sqlite3"
    service = GrantOrchestrator(database_path=database_path)
    generated = create_application(service)
    reviewed = service.review_application(
        generated["application_id"],
        OperatorReviewRequest.model_validate(operator_review_payload()),
    )
    review = reviewed["operator_reviews"][0]
    connection = sqlite3.connect(database_path)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                """
                UPDATE grant_operator_reviews
                SET decision = 'RETURN_FOR_REVISION'
                WHERE review_id = ?
                """,
                (review["review_id"],),
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                """
                INSERT OR REPLACE INTO grant_operator_reviews(
                    review_id,
                    application_id,
                    application_revision,
                    created_at,
                    decision,
                    review_digest,
                    review_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review["review_id"],
                    generated["application_id"],
                    2,
                    review["reviewed_at"],
                    "RETURN_FOR_REVISION",
                    "0" * 64,
                    "{}",
                ),
            )
    finally:
        connection.close()


def test_approved_export_uses_an_immutable_snapshot(tmp_path) -> None:
    database_path = tmp_path / "acgs-local.sqlite3"
    service = GrantOrchestrator(database_path=database_path)
    generated = create_application(service)
    service.review_application(
        generated["application_id"],
        OperatorReviewRequest.model_validate(operator_review_payload()),
    )
    exported = service.local_export(generated["application_id"])

    connection = sqlite3.connect(database_path)
    try:
        with pytest.raises(
            sqlite3.DatabaseError,
            match="approved grant applications are immutable",
        ):
            connection.execute(
                """
                UPDATE grant_applications
                SET payload_json = '{"draft":{"executive_summary":"tampered"}}'
                WHERE application_id = ?
                """,
                (generated["application_id"],),
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                """
                UPDATE grant_local_export_artifacts
                SET artifact_json = '{}'
                WHERE application_id = ?
                """,
                (generated["application_id"],),
            )
    finally:
        connection.close()

    assert service.local_export(generated["application_id"]) == exported
