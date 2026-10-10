from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from scripts.run_controlled_gemini_canary import (
    ControlledCanaryError,
    _write_unknown_outcome,
    canonical_sha256,
    validate_ci_receipt,
    validate_live_permit,
)


def test_ci_receipt_rejects_zero_step_job() -> None:
    with pytest.raises(ControlledCanaryError, match="zero-step"):
        validate_ci_receipt(
            {
                "schema_version": "aigc.github-actions-ci-receipt.v1",
                "repository": "Lornt1666/AIGC",
                "conclusion": "success",
                "head_sha": "a" * 40,
                "steps_executed": 0,
                "run_url": (
                    "https://github.com/Lornt1666/AIGC/actions/runs/123"
                ),
                "required_artifacts": [],
            },
            release_revision="a" * 40,
        )


def test_live_permit_binds_input_release_digest_and_revision() -> None:
    authorization = {
        "release_revision": "a" * 40,
        "gemini_model": "gemini-example-model",
        "cloud": {
            "project_id": "aigc-stage-12345",
            "primary_region": "northamerica-northeast2",
            "operator_service_name": "aigc-gemini-operator-staging",
        },
    }
    deployment = {
        "image_digest": f"sha256:{'b' * 64}",
        "operator_revision": "aigc-gemini-operator-staging-00001-abc",
    }
    fixture_hash = canonical_sha256({"synthetic": True})
    permit = json.loads(
        Path("config/gemini_live_assessment_permit.example.json").read_text(
            encoding="utf-8"
        )
    )
    permit.update(
        {
            "project_id": authorization["cloud"]["project_id"],
            "region": authorization["cloud"]["primary_region"],
            "operator_service_name": authorization["cloud"][
                "operator_service_name"
            ],
            "release_revision": authorization["release_revision"],
            "image_digest": deployment["image_digest"],
            "cloud_run_revision": deployment["operator_revision"],
            "input_fixture_sha256": fixture_hash,
            "model": authorization["gemini_model"],
            "authorized": True,
            "authorized_by": "Accountable owner",
            "authorized_at": "2026-07-27T00:00:00Z",
            "expires_at": "2026-07-28T00:00:00Z",
            "approval_phrase": (
                "AUTHORIZE ONE STAGING GEMINI ASSESSMENT "
                f"{authorization['release_revision']} "
                f"{deployment['image_digest']} {fixture_hash}"
            ),
        }
    )

    validate_live_permit(
        permit,
        authorization=authorization,
        deployment=deployment,
        input_sha256=fixture_hash,
        now=datetime(2026, 7, 27, 1, tzinfo=timezone.utc),
    )

    permit["input_fixture_sha256"] = "c" * 64
    with pytest.raises(ControlledCanaryError, match="input_fixture_sha256"):
        validate_live_permit(
            permit,
            authorization=authorization,
            deployment=deployment,
            input_sha256=fixture_hash,
            now=datetime(2026, 7, 27, 1, tzinfo=timezone.utc),
        )


def test_canary_script_has_no_automatic_retry() -> None:
    source = Path("scripts/run_controlled_gemini_canary.py").read_text(
        encoding="utf-8"
    )
    assert "retry_authorized\": False" in source
    assert "HTTPTransport(retries=" not in source
    assert "for attempt" not in source


def test_unknown_live_outcome_is_durable_and_non_retriable(
    tmp_path: Path,
) -> None:
    output = tmp_path / "runtime-attempt.json"
    _write_unknown_outcome(
        output,
        release_revision="a" * 40,
        input_sha256="b" * 64,
        idempotency_key="one-controlled-attempt",
        failure_class="HTTP_502",
    )

    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["model_api_call_status"] == "attempted_outcome_unknown"
    assert receipt["model_api_call_performed"] is None
    assert receipt["retry_authorized"] is False
    assert receipt["external_business_action_performed"] is False
    assert receipt["failure_class"] == "HTTP_502"
    assert "one-controlled-attempt" not in output.read_text(encoding="utf-8")
