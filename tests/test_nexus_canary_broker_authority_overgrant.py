from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

import scripts.provision_nexus_provider_canary_job as provisioner


PROJECT = "aigc-stage"
PREFIX = "aigc"
PRINCIPAL = "aigc-can-prov@aigc-stage.iam.gserviceaccount.com"
RUNTIME = "aigc-can-gem@aigc-stage.iam.gserviceaccount.com"
MEMBER = f"serviceAccount:{PRINCIPAL}"
EXPIRY = datetime(2026, 8, 12, 4, 0, tzinfo=timezone.utc) + timedelta(
    minutes=5
)
PERMIT = {
    "permit_id": "CJP-CANARY001",
    "project_id": PROJECT,
    "provisioner_principal": PRINCIPAL,
    "expires_at": EXPIRY.isoformat(),
}


class _Response:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload


class _Session:
    def __init__(
        self,
        *,
        project_bindings: list[dict[str, Any]],
        runtime_bindings: list[dict[str, Any]],
    ) -> None:
        self.project_bindings = project_bindings
        self.runtime_bindings = runtime_bindings

    def post(self, *_args: Any, **_kwargs: Any) -> _Response:
        return _Response(
            {
                "version": 3,
                "bindings": self.project_bindings,
            }
        )

    def get(self, *_args: Any, **_kwargs: Any) -> _Response:
        return _Response(
            {
                "version": 3,
                "bindings": self.runtime_bindings,
            }
        )


def _expected_bindings() -> tuple[dict[str, Any], dict[str, Any]]:
    expiry_z = EXPIRY.isoformat().replace("+00:00", "Z")
    expression = f'request.time < timestamp("{expiry_z}")'
    project_binding = {
        "role": (
            f"projects/{PROJECT}/roles/"
            f"{PREFIX}_canary_job_provisioner"
        ),
        "members": [MEMBER],
        "condition": {
            "title": "aigc_provision_cjp_canary001",
            "description": "One dormant-job provisioning permit",
            "expression": expression,
        },
    }
    runtime_binding = {
        "role": "roles/iam.serviceAccountUser",
        "members": [MEMBER],
        "condition": {
            "title": "aigc_provision_actas_cjp_canary001",
            "description": "Act as one canary runtime for one dormant job",
            "expression": expression,
        },
    }
    return project_binding, runtime_binding


def _verify(
    *,
    project_bindings: list[dict[str, Any]],
    runtime_bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    return provisioner._verify_expiring_broker_authority(
        session=_Session(
            project_bindings=project_bindings,
            runtime_bindings=runtime_bindings,
        ),
        permit=PERMIT,
        runtime_service_account=RUNTIME,
        prefix=PREFIX,
    )


def test_exact_exclusive_expiring_bindings_are_accepted() -> None:
    project_binding, runtime_binding = _expected_bindings()

    evidence = _verify(
        project_bindings=[project_binding],
        runtime_bindings=[runtime_binding],
    )

    assert evidence["project_wide_permanent_mutation_authority"] is False
    assert len(evidence["project_binding_sha256"]) == 64
    assert len(evidence["runtime_act_as_binding_sha256"]) == 64


def test_additional_project_role_for_provisioner_is_rejected() -> None:
    project_binding, runtime_binding = _expected_bindings()
    extra_project_role = {
        "role": "roles/editor",
        "members": [MEMBER],
    }

    with pytest.raises(
        provisioner.CanaryJobProvisioningError,
        match="absent or non-exclusive",
    ):
        _verify(
            project_bindings=[project_binding, extra_project_role],
            runtime_bindings=[runtime_binding],
        )


def test_additional_runtime_service_account_role_is_rejected() -> None:
    project_binding, runtime_binding = _expected_bindings()
    extra_runtime_role = {
        "role": "roles/iam.serviceAccountTokenCreator",
        "members": [MEMBER],
    }

    with pytest.raises(
        provisioner.CanaryJobProvisioningError,
        match="absent or non-exclusive",
    ):
        _verify(
            project_bindings=[project_binding],
            runtime_bindings=[runtime_binding, extra_runtime_role],
        )


def test_duplicate_expected_binding_is_rejected() -> None:
    project_binding, runtime_binding = _expected_bindings()

    with pytest.raises(
        provisioner.CanaryJobProvisioningError,
        match="absent or non-exclusive",
    ):
        _verify(
            project_bindings=[project_binding, dict(project_binding)],
            runtime_bindings=[runtime_binding],
        )
