from __future__ import annotations

import re
import sys
from typing import Any
from urllib.parse import quote

from scripts import provision_nexus_provider_canary_job_impl as _impl
from src.core.epistemic.canonicalization import canonical_sha256


def _verify_expiring_broker_authority(
    *,
    session: Any,
    permit: dict[str, Any],
    runtime_service_account: str,
    prefix: str,
) -> dict[str, Any]:
    """Require the provisioner to hold only the exact expiring IAM bindings.

    The prior validator selected only the expected role before comparison. That
    proved the expected binding existed, but it did not reject an additional
    role held by the same principal. Such drift could make the resulting
    ``project_wide_permanent_mutation_authority`` receipt field false. This
    validator evaluates every binding for the principal and fails closed unless
    the exact conditioned project role and exact conditioned actAs role are the
    principal's complete binding sets on the inspected resources.
    """

    expiry = _impl._aware_datetime(permit["expires_at"], field="expires_at")
    expiry_z = expiry.isoformat().replace("+00:00", "Z")
    suffix = re.sub(
        r"[^a-z0-9]",
        "_",
        permit["permit_id"].lower(),
    ).strip("_")
    expression = f'request.time < timestamp("{expiry_z}")'
    member = f"serviceAccount:{permit['provisioner_principal']}"
    expected_project_binding = {
        "role": (
            f"projects/{permit['project_id']}/roles/"
            f"{prefix.replace('-', '_')}_canary_job_provisioner"
        ),
        "members": [member],
        "condition": {
            "title": f"aigc_provision_{suffix}"[:79],
            "description": "One dormant-job provisioning permit",
            "expression": expression,
        },
    }
    expected_act_as = {
        "role": "roles/iam.serviceAccountUser",
        "members": [member],
        "condition": {
            "title": f"aigc_provision_actas_{suffix}"[:79],
            "description": "Act as one canary runtime for one dormant job",
            "expression": expression,
        },
    }

    project_response = session.post(
        "https://cloudresourcemanager.googleapis.com/v1/projects/"
        f"{permit['project_id']}:getIamPolicy",
        json={"options": {"requestedPolicyVersion": 3}},
        timeout=10,
    )
    runtime_response = session.get(
        "https://iam.googleapis.com/v1/projects/"
        f"{quote(permit['project_id'], safe='')}/serviceAccounts/"
        f"{quote(runtime_service_account, safe='@.')}:getIamPolicy",
        params={"options.requestedPolicyVersion": "3"},
        timeout=10,
    )
    try:
        project_policy = project_response.json()
        runtime_policy = runtime_response.json()
    except (TypeError, ValueError) as exc:
        raise _impl.CanaryJobProvisioningError(
            "trusted provisioner broker IAM evidence is invalid"
        ) from exc
    if (
        project_response.status_code != 200
        or runtime_response.status_code != 200
    ):
        raise _impl.CanaryJobProvisioningError(
            "BLOCKED_PENDING_TRUSTED_BROKER: conditional authority "
            "is not observable"
        )
    if not isinstance(project_policy, dict) or not isinstance(
        runtime_policy,
        dict,
    ):
        raise _impl.CanaryJobProvisioningError(
            "trusted provisioner broker IAM evidence is invalid"
        )

    def _member_bindings(policy: dict[str, Any]) -> list[dict[str, Any]]:
        bindings = policy.get("bindings", [])
        if not isinstance(bindings, list):
            raise _impl.CanaryJobProvisioningError(
                "trusted provisioner broker IAM bindings are invalid"
            )
        return [
            item
            for item in bindings
            if isinstance(item, dict)
            and member in (item.get("members") or [])
        ]

    project_member_bindings = _member_bindings(project_policy)
    runtime_member_bindings = _member_bindings(runtime_policy)
    if (
        project_member_bindings != [expected_project_binding]
        or runtime_member_bindings != [expected_act_as]
    ):
        raise _impl.CanaryJobProvisioningError(
            "BLOCKED_PENDING_TRUSTED_BROKER: exact expiring broker "
            "authority is absent or non-exclusive"
        )

    return {
        "broker_authority_expires_at": expiry.isoformat(),
        "project_binding_sha256": canonical_sha256(
            expected_project_binding
        ),
        "runtime_act_as_binding_sha256": canonical_sha256(expected_act_as),
        "project_wide_permanent_mutation_authority": False,
    }


_impl._verify_expiring_broker_authority = (
    _verify_expiring_broker_authority
)

_ENTRYPOINT_NAME = __name__
if _ENTRYPOINT_NAME != "__main__":
    # Return the original implementation module to importers so existing
    # monkeypatch-based tests and all function-global lookups remain compatible.
    sys.modules[_ENTRYPOINT_NAME] = _impl
else:
    try:
        raise SystemExit(_impl.main())
    except _impl.CanaryJobProvisioningError as exc:
        raise SystemExit(
            f"Nexus canary job provisioning blocked: {exc}"
        ) from exc
