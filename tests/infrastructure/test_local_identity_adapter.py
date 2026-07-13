from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.domain.identity import (
    IdentityDenialReason,
    RuntimeAuthority,
)
from src.infrastructure.identity import LocalDevelopmentIdentityAdapter


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)


def adapter() -> LocalDevelopmentIdentityAdapter:
    return LocalDevelopmentIdentityAdapter(
        ROOT / "governance" / "identity" / "local_identity_simulation.json"
    )


def assertion(**extra: object) -> dict[str, object]:
    value: dict[str, object] = {
        "assertion_id": "assertion-a",
        "principal_id": "principal-a",
        "issuer": "local-simulation",
        "audience": "aigc-local-operator",
    }
    value.update(extra)
    return value


def test_local_adapter_can_only_advertise_local_simulation() -> None:
    evidence = adapter().verify(assertion(), now=NOW)

    assert evidence.verified is True
    assert evidence.runtime_authority is RuntimeAuthority.LOCAL_SIMULATION
    assert evidence.identity_assurance.value == "IAL0"
    assert evidence.authentication_assurance.value == "AAL0"
    assert evidence.federation_assurance.value == "FAL0"


def test_roles_and_scopes_are_resolved_from_membership_not_assertion() -> None:
    identity = adapter()
    membership = identity.resolve_membership(
        principal_id="principal-a",
        membership_id="membership-a",
        tenant_id="tenant-a",
        project_id="project-a",
        now=NOW,
    )

    assert membership is not None
    assert membership.roles == ("operator",)
    assert membership.granted_scopes == ("project:read",)


def test_raw_token_or_role_fields_fail_closed() -> None:
    evidence = adapter().verify(
        assertion(access_token="secret", roles=["administrator"]),
        now=NOW,
    )

    assert evidence.verified is False
    assert IdentityDenialReason.ROLE_SOURCE_UNTRUSTED in evidence.denial_reasons
    assert "secret" not in str(evidence)
    assert "administrator" not in str(evidence)
