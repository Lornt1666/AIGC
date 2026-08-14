from __future__ import annotations

from datetime import datetime, timedelta, timezone

import google.auth
import pytest

import scripts.bind_nexus_canary_executor as binder


NOW = datetime(2026, 8, 10, 14, 0, tzinfo=timezone.utc)
PROJECT = "aigc-stage"
PREFIX = "aigc"
PROVISIONER = f"{PREFIX}-can-prov@{PROJECT}.iam.gserviceaccount.com"
BINDER = f"{PREFIX}-can-bind@{PROJECT}.iam.gserviceaccount.com"


def _provisioning(expiry: datetime) -> dict:
    return {
        "provisioner_principal": PROVISIONER,
        "identity_evidence": {
            "attached_service_account": PROVISIONER,
            "attached_service_account_verified": True,
            "credential_source": "gce_metadata_server",
            "client_impersonation_used": False,
            "project_wide_permanent_mutation_authority": False,
            "service_account_key_used": False,
            "broker_authority_expires_at": expiry.isoformat(),
        },
    }


def test_binding_waits_until_provisioner_mutation_authority_is_expired() -> None:
    provisioning = _provisioning(NOW)
    with pytest.raises(
        binder.CanaryExecutorBindingError, match="not provably quiescent"
    ):
        binder._require_quiescent_provisioner(
            provisioning, authoritative_now=NOW - timedelta(microseconds=1)
        )
    assert binder._require_quiescent_provisioner(
        provisioning, authoritative_now=NOW
    ) == {"provisioner_broker_authority_expired_at": NOW.isoformat()}


def test_binder_role_is_exact_job_only_and_expires_before_executor_binding() -> None:
    permit = {
        "permit_id": "CJB-CANARY001",
        "project_id": PROJECT,
        "binder_principal": BINDER,
        "expires_at": NOW.isoformat(),
    }
    binding = binder._binder_binding(permit=permit, prefix=PREFIX)
    assert binding["role"] == f"projects/{PROJECT}/roles/aigc_canary_job_iam_binder"
    assert binding["members"] == [f"serviceAccount:{BINDER}"]
    assert binding["condition"]["expression"] == (
        'request.time < timestamp("2026-08-10T14:00:00Z")'
    )


def test_client_impersonated_binder_is_rejected(monkeypatch) -> None:
    credentials = type("Credentials", (), {})()
    credentials.target_principal = BINDER
    credentials._target_principal = BINDER
    credentials._source_credentials = object()
    monkeypatch.setattr(
        google.auth, "default", lambda **_kwargs: (credentials, PROJECT)
    )
    with pytest.raises(
        binder.CanaryExecutorBindingError,
        match="non-impersonable attached metadata",
    ):
        binder._adc_session(BINDER)


def test_binding_condition_uses_separate_executor_expiry() -> None:
    title, expression = binder.expected_condition(
        permit_id="CJB-CANARY001",
        expires_at=(NOW + timedelta(minutes=4)).isoformat(),
    )
    assert title == "aigc_canary_cjb_canary001"
    assert expression.endswith('2026-08-10T14:04:00Z")')
