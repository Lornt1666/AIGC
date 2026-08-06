from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from scripts.validate_gemini_staging_authorization import (
    StagingAuthorizationError,
    validate_authorization,
)


def _authorized_payload() -> dict:
    payload = json.loads(
        Path("config/gemini_staging_authorization.example.json").read_text(
            encoding="utf-8"
        )
    )
    project = "aigc-stage-12345"
    sha = "a" * 40
    payload["release_revision"] = sha
    payload["gemini_model"] = "gemini-example-model"
    payload["cloud"].update(
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
    payload["service_accounts"] = {
        name: f"{name.replace('_', '-')}@{project}.iam.gserviceaccount.com"
        for name in (
            "deployer",
            "cloud_build",
            "operator_runtime",
            "judge_runtime",
        )
    }
    payload["secret_manager_exact_version_refs"] = {
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
    payload["iam_review"] = {
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
    for name in payload["evidence_controls"]:
        payload["evidence_controls"][name] = True
    payload["spending_control"].update(
        {
            "authorized_monthly_ceiling": 50,
            "billing_budget_configured": True,
            "vertex_quota_reviewed": True,
            "application_limits_reviewed": True,
            "acknowledges_budget_is_not_a_hard_cap": True,
        }
    )
    payload["authorization"].update(
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
                f"{project} northamerica-northeast1 {sha} "
                "CEILING CAD 50"
            ),
        }
    )
    return payload


def test_default_template_is_not_authorized() -> None:
    payload = json.loads(
        Path("config/gemini_staging_authorization.example.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(StagingAuthorizationError):
        validate_authorization(
            payload,
            gate="configuration",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )


def test_exact_authorization_passes_each_gate() -> None:
    payload = _authorized_payload()
    for gate in ("configuration", "deploy", "live", "judge"):
        summary = validate_authorization(
            payload,
            gate=gate,
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )
        assert summary["valid"] is True
        assert summary["external_action_performed"] is False


def test_judge_service_account_and_secret_alias_fail_closed() -> None:
    payload = _authorized_payload()
    payload["service_accounts"]["judge_runtime"] = payload[
        "service_accounts"
    ]["operator_runtime"]
    with pytest.raises(StagingAuthorizationError, match="separate"):
        validate_authorization(
            payload,
            gate="deploy",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )

    payload = _authorized_payload()
    payload["secret_manager_exact_version_refs"]["operator_token"] = (
        "projects/aigc-stage-12345/secrets/operator_token/versions/latest"
    )
    with pytest.raises(StagingAuthorizationError, match="exact numeric"):
        validate_authorization(
            payload,
            gate="deploy",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )


def test_approval_phrase_binds_ceiling_and_release() -> None:
    payload = deepcopy(_authorized_payload())
    payload["spending_control"]["authorized_monthly_ceiling"] = 75
    with pytest.raises(StagingAuthorizationError, match="Approval phrase"):
        validate_authorization(
            payload,
            gate="deploy",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )


def test_toronto_infrastructure_does_not_imply_toronto_gemini() -> None:
    payload = _authorized_payload()
    payload["cloud"]["vertex_location"] = "northamerica-northeast2"

    with pytest.raises(
        StagingAuthorizationError,
        match="supported Canadian regional Gemini endpoint",
    ):
        validate_authorization(
            payload,
            gate="deploy",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )


def test_exact_model_location_review_is_required() -> None:
    payload = _authorized_payload()
    payload["cloud"]["vertex_model_availability_reviewed"] = False

    with pytest.raises(
        StagingAuthorizationError,
        match="exact Gemini model and Vertex location",
    ):
        validate_authorization(
            payload,
            gate="configuration",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )


def test_broad_or_non_judge_roles_fail_closed() -> None:
    payload = _authorized_payload()
    payload["iam_review"]["deployer_roles"] = ["roles/owner"]
    with pytest.raises(
        StagingAuthorizationError,
        match="primitive or administrative",
    ):
        validate_authorization(
            payload,
            gate="configuration",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )

    payload = _authorized_payload()
    payload["iam_review"]["judge_runtime_roles"] = [
        "roles/aiplatform.user"
    ]
    with pytest.raises(
        StagingAuthorizationError,
        match="Judge runtime roles exceed",
    ):
        validate_authorization(
            payload,
            gate="configuration",
            now=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )
