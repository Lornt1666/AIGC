from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.application.identity_boundary import IdentityBoundaryService
from src.domain.identity import (
    IdentityDecision,
    IdentityDenialReason,
    IdentityEvidenceReceipt,
)
from src.infrastructure.identity import LocalDevelopmentIdentityAdapter


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)


class MemoryReceiptRepository:
    def __init__(self) -> None:
        self.by_id: dict[str, IdentityEvidenceReceipt] = {}
        self.by_replay: dict[str, IdentityEvidenceReceipt] = {}

    def append(
        self,
        receipt: IdentityEvidenceReceipt,
    ) -> IdentityEvidenceReceipt:
        self.by_id[receipt.receipt_id] = receipt
        self.by_replay[receipt.replay_key_digest] = receipt
        return receipt

    def get(self, receipt_id: str) -> IdentityEvidenceReceipt | None:
        return self.by_id.get(receipt_id)

    def get_by_replay_key(
        self,
        replay_key_digest: str,
    ) -> IdentityEvidenceReceipt | None:
        return self.by_replay.get(replay_key_digest)


def service() -> IdentityBoundaryService:
    adapter = LocalDevelopmentIdentityAdapter(
        ROOT / "governance" / "identity" / "local_identity_simulation.json"
    )
    return IdentityBoundaryService(
        provider=adapter,
        membership_resolver=adapter,
        session_verifier=adapter,
        receipt_repository=MemoryReceiptRepository(),
        config_path=ROOT / "config" / "identity_boundary.json",
        context_schema_path=ROOT / "schemas" / "identity_boundary.schema.json",
        receipt_schema_path=(
            ROOT / "schemas" / "identity_evidence_receipt.schema.json"
        ),
    )


def request(
    assertion_id: str = "assertion-a",
    **overrides: object,
) -> dict[str, object]:
    value: dict[str, object] = {
        "provider_type": "LOCAL_DEVELOPMENT",
        "raw_assertion": {
            "assertion_id": assertion_id,
            "principal_id": "principal-a",
            "issuer": "local-simulation",
            "audience": "aigc-local-operator",
        },
        "membership_id": "membership-a",
        "session_id": "session-a",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "exact_revision": "LOCAL_UNVERIFIED",
        "production_mode": False,
        "now": NOW,
    }
    value.update(overrides)
    return value


def test_local_context_is_permitted_and_roles_come_from_membership() -> None:
    result = service().evaluate(**request())

    assert result.permitted is True
    assert result.result is IdentityDecision.PERMIT
    assert result.context is not None
    assert result.context.roles == ("operator",)
    assert result.context.runtime_authority.value == "LOCAL_SIMULATION"
    assert result.receipt.to_dict()["external_action_performed"] is False


def test_local_adapter_is_denied_in_production_mode() -> None:
    result = service().evaluate(
        **request(
            assertion_id="assertion-production",
            exact_revision="a" * 40,
            production_mode=True,
        )
    )

    assert result.permitted is False
    assert IdentityDenialReason.LOCAL_PROVIDER_PROHIBITED in result.reason_codes
    assert result.context is None


def test_production_requires_exact_revision() -> None:
    result = service().evaluate(
        **request(
            assertion_id="assertion-unbound",
            production_mode=True,
            exact_revision="LOCAL_UNVERIFIED",
        )
    )

    assert IdentityDenialReason.REVISION_UNBOUND in result.reason_codes


def test_role_injection_is_denied_and_never_enters_receipt() -> None:
    raw = dict(request()["raw_assertion"])
    raw["roles"] = ["administrator"]
    result = service().evaluate(
        **request(assertion_id="assertion-role", raw_assertion=raw)
    )

    assert result.permitted is False
    assert IdentityDenialReason.ROLE_SOURCE_UNTRUSTED in result.reason_codes
    serialized = str(result.receipt.to_dict())
    assert "administrator" not in serialized


def test_missing_project_membership_is_denied() -> None:
    result = service().evaluate(
        **request(
            assertion_id="assertion-project",
            project_id="project-other",
        )
    )

    assert result.permitted is False
    assert (
        IdentityDenialReason.PROJECT_MEMBERSHIP_MISSING
        in result.reason_codes
    )


def test_exact_replay_returns_same_receipt() -> None:
    boundary = service()
    first = boundary.evaluate(**request(assertion_id="assertion-replay"))
    replay = boundary.evaluate(**request(assertion_id="assertion-replay"))

    assert replay.receipt.receipt_id == first.receipt.receipt_id
    assert replay.receipt.request_digest == first.receipt.request_digest


def test_changed_intent_with_same_assertion_is_replay_conflict() -> None:
    boundary = service()
    boundary.evaluate(**request(assertion_id="assertion-conflict"))
    conflict = boundary.evaluate(
        **request(
            assertion_id="assertion-conflict",
            project_id="project-other",
        )
    )

    assert conflict.permitted is False
    assert IdentityDenialReason.REPLAY_CONFLICT in conflict.reason_codes
