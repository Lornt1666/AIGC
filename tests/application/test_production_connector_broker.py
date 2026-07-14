from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.application.governed_production_connectors import (
    GovernedProductionConnectorBroker,
)
from src.application.production_connectors import (
    ConnectorDefinition,
    ConnectorOperation,
    MemoryConnectorIdempotencyStore,
    ProductionConnectorBroker,
    ProductionConnectorPolicyError,
    definitions_from_policy,
    evaluate_connector_policy,
    load_connector_policy,
)
from src.infrastructure.secrets import (
    ResolvedSecret,
    SecretAccessReceipt,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "production_connector_secret_broker.json"
POLICY_SCHEMA = ROOT / "schemas" / "production_connector_secret_broker.schema.json"
NOW = datetime(2026, 7, 14, 6, 0, tzinfo=timezone.utc)
REVISION = "a" * 40
DESTINATION = "approved-test-destination"


class FakeSecretResolver:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.references: list[str] = []
        self.last_secret: ResolvedSecret | None = None

    def access(self, reference: str) -> ResolvedSecret:
        self.references.append(reference)
        if self.fail:
            raise RuntimeError("offline secret access failure")
        receipt = SecretAccessReceipt(
            reference=reference,
            resource_name="projects/offline/secrets/test/versions/1",
            version_name="projects/offline/secrets/test/versions/1",
            accessed_at=NOW,
        )
        self.last_secret = ResolvedSecret(b"offline-connector-material", receipt)
        return self.last_secret


class FakeAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def execute(
        self,
        *,
        operation_id: str,
        destination: str,
        payload: Mapping[str, Any],
        credential_material: bytes,
    ) -> Mapping[str, Any]:
        self.calls.append(
            {
                "operation_id": operation_id,
                "destination": destination,
                "payload": dict(payload),
                "credential_length": len(credential_material),
            }
        )
        if self.fail:
            raise RuntimeError("offline adapter failure")
        return {
            "status": "completed",
            "remote_reference_digest": "b" * 64,
        }


def operation(
    *,
    operation_id: str = "read_repository",
    mode: str = "read",
    consequence: str = "read_only",
    approval_scope: str | None = None,
) -> ConnectorOperation:
    return ConnectorOperation(
        operation_id=operation_id,
        mode=mode,
        consequence=consequence,
        approval_scope=approval_scope,
    )


def definition(
    *,
    enabled: bool,
    staging_verified: bool,
    terms_approved: bool,
    operations: tuple[ConnectorOperation, ...] | None = None,
) -> ConnectorDefinition:
    return ConnectorDefinition(
        connector_id="github",
        platform="GitHub",
        enabled=enabled,
        official_api=True,
        secret_reference="gcp_secret://approved-project/aigc-github-app/latest",
        destination_allowlist=(DESTINATION,),
        operations=operations or (operation(),),
        staging_verified=staging_verified,
        terms_approved=terms_approved,
    )


def broker(
    *,
    current_definition: ConnectorDefinition,
    resolver: FakeSecretResolver,
    adapter: FakeAdapter | None,
    execution_authorized: bool,
    store: MemoryConnectorIdempotencyStore | None = None,
) -> GovernedProductionConnectorBroker:
    return GovernedProductionConnectorBroker(
        secret_resolver=resolver,
        adapters=(
            {current_definition.connector_id: adapter}
            if adapter is not None
            else {}
        ),
        idempotency_store=store or MemoryConnectorIdempotencyStore(),
        execution_authorized=execution_authorized,
    )


def prepare(
    current_broker: ProductionConnectorBroker,
    current_definition: ConnectorDefinition,
    *,
    payload: Mapping[str, Any] | None = None,
    idempotency_key: str = "offline-idempotency-001",
    operation_id: str = "read_repository",
):
    return current_broker.prepare(
        definition=current_definition,
        operation_id=operation_id,
        destination=DESTINATION,
        payload=payload or {"repository": "owner/repository"},
        idempotency_key=idempotency_key,
        exact_revision=REVISION,
        now=NOW,
    )


def approval_for(
    prepared: Any,
    *,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    request_digest: str | None = None,
) -> dict[str, object]:
    request = prepared.request
    return {
        "contract_id": "AIGC-CONNECTOR-ACTION-APPROVAL-001",
        "contract_version": "1.0.0",
        "approval_id": "CAP-" + "A" * 24,
        "request_id": request["request_id"],
        "request_digest": request_digest or request["request_digest"],
        "exact_revision": request["exact_revision"],
        "connector_id": request["connector_id"],
        "operation_id": request["operation_id"],
        "destination": request["destination"],
        "approval_scope": request["approval_scope"],
        "decision": "APPROVED",
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Approved for isolated offline connector verification.",
        "issued_at": (issued_at or (NOW - timedelta(minutes=1))).isoformat(),
        "expires_at": (expires_at or (NOW + timedelta(minutes=5))).isoformat(),
        "external_action_performed": False,
    }


def test_real_connector_policy_is_internal_and_zero_enabled() -> None:
    policy = load_connector_policy(POLICY_PATH, POLICY_SCHEMA)
    evaluation = evaluate_connector_policy(policy)
    definitions = definitions_from_policy(policy)

    assert evaluation.implemented_internal is True
    assert evaluation.production_complete is False
    assert evaluation.enabled_connectors == ()
    assert set(definitions) == {"github", "google_drive", "gmail"}
    assert all(item.enabled is False for item in definitions.values())
    assert all(item.destination_allowlist == () for item in definitions.values())
    assert evaluation.secret_access_authorized is False
    assert evaluation.production_connector_activation_authorized is False
    assert evaluation.production_external_action_authorized is False
    assert evaluation.external_action_performed is False


def test_prepared_request_contains_digests_not_payload() -> None:
    current_definition = definition(
        enabled=True,
        staging_verified=True,
        terms_approved=True,
    )
    resolver = FakeSecretResolver()
    current_broker = broker(
        current_definition=current_definition,
        resolver=resolver,
        adapter=FakeAdapter(),
        execution_authorized=True,
    )
    prepared = prepare(
        current_broker,
        current_definition,
        payload={"title": "Internal test", "body": "Not persisted in receipt"},
    )

    assert prepared.request["dry_run_completed"] is True
    assert len(prepared.request["payload_digest"]) == 64
    assert "payload" not in prepared.request
    assert "Internal test" not in json.dumps(prepared.request)
    assert "Not persisted in receipt" not in json.dumps(prepared.request)
    assert prepared.request["external_action_performed"] is False
    assert resolver.references == []


def test_unallowlisted_destination_is_rejected_during_prepare() -> None:
    current_definition = definition(
        enabled=True,
        staging_verified=True,
        terms_approved=True,
    )
    current_broker = broker(
        current_definition=current_definition,
        resolver=FakeSecretResolver(),
        adapter=FakeAdapter(),
        execution_authorized=True,
    )

    with pytest.raises(ProductionConnectorPolicyError, match="not allowlisted"):
        current_broker.prepare(
            definition=current_definition,
            operation_id="read_repository",
            destination="other-destination",
            payload={"repository": "owner/repository"},
            idempotency_key="offline-idempotency-002",
            exact_revision=REVISION,
            now=NOW,
        )


def test_disabled_unverified_connector_denies_before_secret_or_adapter() -> None:
    current_definition = definition(
        enabled=False,
        staging_verified=False,
        terms_approved=False,
    )
    resolver = FakeSecretResolver()
    adapter = FakeAdapter()
    current_broker = broker(
        current_definition=current_definition,
        resolver=resolver,
        adapter=adapter,
        execution_authorized=False,
    )
    prepared = prepare(current_broker, current_definition)

    receipt = current_broker.execute(prepared, approval=None, now=NOW)

    assert receipt["result"] == "DENY"
    assert set(receipt["reason_codes"]) >= {
        "CONNECTOR_EXECUTION_UNAUTHORIZED",
        "CONNECTOR_DISABLED",
        "TERMS_REVIEW_INCOMPLETE",
        "STAGING_EVIDENCE_INCOMPLETE",
    }
    assert receipt["secret_access_receipt"] is None
    assert receipt["external_action_performed"] is False
    assert resolver.references == []
    assert adapter.calls == []


def test_missing_or_invalid_approval_denies_before_secret_access() -> None:
    write_operation = operation(
        operation_id="create_issue",
        mode="write",
        consequence="external_write",
        approval_scope="CONNECTOR_GITHUB_CREATE_ISSUE",
    )
    current_definition = definition(
        enabled=True,
        staging_verified=True,
        terms_approved=True,
        operations=(write_operation,),
    )
    resolver = FakeSecretResolver()
    adapter = FakeAdapter()
    current_broker = broker(
        current_definition=current_definition,
        resolver=resolver,
        adapter=adapter,
        execution_authorized=True,
    )
    prepared = prepare(
        current_broker,
        current_definition,
        operation_id="create_issue",
    )

    missing = current_broker.execute(prepared, approval=None, now=NOW)
    expired = current_broker.execute(
        prepared,
        approval=approval_for(
            prepared,
            issued_at=NOW - timedelta(minutes=20),
            expires_at=NOW - timedelta(minutes=10),
        ),
        now=NOW,
    )
    mismatched = current_broker.execute(
        prepared,
        approval=approval_for(prepared, request_digest="c" * 64),
        now=NOW,
    )

    assert "ACTION_APPROVAL_MISSING" in missing["reason_codes"]
    assert "ACTION_APPROVAL_INVALID" in expired["reason_codes"]
    assert "ACTION_APPROVAL_INVALID" in mismatched["reason_codes"]
    assert resolver.references == []
    assert adapter.calls == []


def test_valid_read_action_accesses_secret_once_and_emits_digest_only_receipt() -> None:
    current_definition = definition(
        enabled=True,
        staging_verified=True,
        terms_approved=True,
    )
    resolver = FakeSecretResolver()
    adapter = FakeAdapter()
    current_broker = broker(
        current_definition=current_definition,
        resolver=resolver,
        adapter=adapter,
        execution_authorized=True,
    )
    prepared = prepare(current_broker, current_definition)

    receipt = current_broker.execute(prepared, approval=None, now=NOW)

    assert receipt["result"] == "COMPLETED"
    assert receipt["reason_codes"] == []
    assert receipt["external_action_performed"] is False
    assert len(receipt["adapter_result_digest"]) == 64
    assert receipt["secret_access_receipt"]["raw_value_logged"] is False
    assert receipt["secret_access_receipt"]["raw_value_persisted"] is False
    assert resolver.references == [current_definition.secret_reference]
    assert len(adapter.calls) == 1
    serialized = json.dumps(receipt)
    assert "offline-connector-material" not in serialized
    assert prepared.payload["repository"] not in serialized
    assert resolver.last_secret is not None
    with pytest.raises(Exception, match="closed"):
        resolver.last_secret.bytes()


def test_valid_approved_write_records_external_action_only_after_adapter_invocation() -> None:
    write_operation = operation(
        operation_id="create_issue",
        mode="write",
        consequence="external_write",
        approval_scope="CONNECTOR_GITHUB_CREATE_ISSUE",
    )
    current_definition = definition(
        enabled=True,
        staging_verified=True,
        terms_approved=True,
        operations=(write_operation,),
    )
    resolver = FakeSecretResolver()
    adapter = FakeAdapter()
    current_broker = broker(
        current_definition=current_definition,
        resolver=resolver,
        adapter=adapter,
        execution_authorized=True,
    )
    prepared = prepare(
        current_broker,
        current_definition,
        operation_id="create_issue",
    )

    receipt = current_broker.execute(
        prepared,
        approval=approval_for(prepared),
        now=NOW,
    )

    assert receipt["result"] == "COMPLETED"
    assert receipt["approval_id"] is not None
    assert receipt["external_action_performed"] is True
    assert len(adapter.calls) == 1


def test_secret_failure_does_not_claim_external_platform_action() -> None:
    write_operation = operation(
        operation_id="create_issue",
        mode="write",
        consequence="external_write",
        approval_scope="CONNECTOR_GITHUB_CREATE_ISSUE",
    )
    current_definition = definition(
        enabled=True,
        staging_verified=True,
        terms_approved=True,
        operations=(write_operation,),
    )
    resolver = FakeSecretResolver(fail=True)
    adapter = FakeAdapter()
    current_broker = broker(
        current_definition=current_definition,
        resolver=resolver,
        adapter=adapter,
        execution_authorized=True,
    )
    prepared = prepare(
        current_broker,
        current_definition,
        operation_id="create_issue",
    )

    receipt = current_broker.execute(
        prepared,
        approval=approval_for(prepared),
        now=NOW,
    )

    assert receipt["result"] == "FAILED"
    assert receipt["reason_codes"] == ["CONNECTOR_EXECUTION_FAILED"]
    assert receipt["external_action_performed"] is False
    assert adapter.calls == []


def test_duplicate_and_conflicting_idempotency_are_blocked_without_second_secret_access() -> None:
    current_definition = definition(
        enabled=True,
        staging_verified=True,
        terms_approved=True,
    )
    resolver = FakeSecretResolver()
    adapter = FakeAdapter()
    store = MemoryConnectorIdempotencyStore()
    current_broker = broker(
        current_definition=current_definition,
        resolver=resolver,
        adapter=adapter,
        execution_authorized=True,
        store=store,
    )
    first_prepared = prepare(current_broker, current_definition)
    duplicate_prepared = prepare(current_broker, current_definition)
    conflict_prepared = prepare(
        current_broker,
        current_definition,
        payload={"repository": "owner/other-repository"},
    )

    first = current_broker.execute(first_prepared, approval=None, now=NOW)
    duplicate = current_broker.execute(duplicate_prepared, approval=None, now=NOW)
    conflict = current_broker.execute(conflict_prepared, approval=None, now=NOW)

    assert first["result"] == "COMPLETED"
    assert duplicate["reason_codes"] == ["DUPLICATE_ACTION_BLOCKED"]
    assert conflict["reason_codes"] == ["IDEMPOTENCY_CONFLICT"]
    assert len(resolver.references) == 1
    assert len(adapter.calls) == 1
