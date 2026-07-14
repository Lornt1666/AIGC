from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from src.application.governed_production_connectors import (
    GovernedProductionConnectorBroker,
)
from src.application.production_connectors import (
    ConnectorDefinition,
    ConnectorOperation,
    MemoryConnectorIdempotencyStore,
    ProductionConnectorBroker,
)
from src.infrastructure.secrets import ResolvedSecret, SecretAccessReceipt


NOW = datetime(2026, 7, 14, 7, 0, tzinfo=timezone.utc)
REVISION = "a" * 40
DESTINATION = "approved-test-destination"


class FakeSecretResolver:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.references: list[str] = []

    def access(self, reference: str) -> ResolvedSecret:
        self.references.append(reference)
        if self.fail:
            raise RuntimeError("offline secret access failure")
        return ResolvedSecret(
            b"offline-connector-material",
            SecretAccessReceipt(
                reference=reference,
                resource_name="projects/offline/secrets/test/versions/1",
                version_name="projects/offline/secrets/test/versions/1",
                accessed_at=NOW,
            ),
        )


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
        return {"status": "completed", "remote_reference_digest": "b" * 64}


def definition(*, write: bool = False) -> ConnectorDefinition:
    operation = ConnectorOperation(
        operation_id="create_issue" if write else "read_repository",
        mode="write" if write else "read",
        consequence="external_write" if write else "read_only",
        approval_scope="CONNECTOR_GITHUB_CREATE_ISSUE" if write else None,
    )
    return ConnectorDefinition(
        connector_id="github",
        platform="GitHub",
        enabled=True,
        official_api=True,
        secret_reference="gcp_secret://approved-project/aigc-github-app/latest",
        destination_allowlist=(DESTINATION,),
        operations=(operation,),
        staging_verified=True,
        terms_approved=True,
    )


def broker(
    broker_type: type[ProductionConnectorBroker],
    *,
    current_definition: ConnectorDefinition,
    resolver: FakeSecretResolver,
    adapter: FakeAdapter | None,
    store: MemoryConnectorIdempotencyStore,
) -> ProductionConnectorBroker:
    return broker_type(
        secret_resolver=resolver,
        adapters=(
            {current_definition.connector_id: adapter}
            if adapter is not None
            else {}
        ),
        idempotency_store=store,
        execution_authorized=True,
    )


def prepare(
    current_broker: ProductionConnectorBroker,
    current_definition: ConnectorDefinition,
    *,
    idempotency_key: str,
):
    operation = current_definition.operations[0]
    return current_broker.prepare(
        definition=current_definition,
        operation_id=operation.operation_id,
        destination=DESTINATION,
        payload={"repository": "owner/repository"},
        idempotency_key=idempotency_key,
        exact_revision=REVISION,
        now=NOW,
    )


def approval_for(prepared: Any) -> dict[str, object]:
    request = prepared.request
    return {
        "contract_id": "AIGC-CONNECTOR-ACTION-APPROVAL-001",
        "contract_version": "1.0.0",
        "approval_id": "CAP-" + "A" * 24,
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "exact_revision": request["exact_revision"],
        "connector_id": request["connector_id"],
        "operation_id": request["operation_id"],
        "destination": request["destination"],
        "approval_scope": request["approval_scope"],
        "decision": "APPROVED",
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "reason": "Approved for isolated offline connector verification.",
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        "external_action_performed": False,
    }


def test_compatibility_broker_inherits_the_single_canonical_execute_path() -> None:
    assert "execute" not in GovernedProductionConnectorBroker.__dict__
    assert (
        GovernedProductionConnectorBroker.execute
        is ProductionConnectorBroker.execute
    )


def test_missing_adapter_does_not_consume_the_idempotency_claim() -> None:
    current_definition = definition()
    resolver = FakeSecretResolver()
    store = MemoryConnectorIdempotencyStore()

    missing_adapter_broker = broker(
        ProductionConnectorBroker,
        current_definition=current_definition,
        resolver=resolver,
        adapter=None,
        store=store,
    )
    prepared = prepare(
        missing_adapter_broker,
        current_definition,
        idempotency_key="broker-unification-001",
    )

    denied = missing_adapter_broker.execute(prepared, approval=None, now=NOW)

    adapter = FakeAdapter()
    repaired_broker = broker(
        ProductionConnectorBroker,
        current_definition=current_definition,
        resolver=resolver,
        adapter=adapter,
        store=store,
    )
    completed = repaired_broker.execute(prepared, approval=None, now=NOW)

    assert denied["result"] == "DENY"
    assert denied["reason_codes"] == ["CONNECTOR_ADAPTER_MISSING"]
    assert denied["external_action_performed"] is False
    assert completed["result"] == "COMPLETED"
    assert len(resolver.references) == 1
    assert len(adapter.calls) == 1


def test_direct_broker_distinguishes_pre_adapter_and_post_adapter_write_failure() -> None:
    current_definition = definition(write=True)

    pre_adapter_resolver = FakeSecretResolver(fail=True)
    pre_adapter = broker(
        ProductionConnectorBroker,
        current_definition=current_definition,
        resolver=pre_adapter_resolver,
        adapter=FakeAdapter(),
        store=MemoryConnectorIdempotencyStore(),
    )
    pre_adapter_prepared = prepare(
        pre_adapter,
        current_definition,
        idempotency_key="broker-unification-002",
    )
    pre_adapter_receipt = pre_adapter.execute(
        pre_adapter_prepared,
        approval=approval_for(pre_adapter_prepared),
        now=NOW,
    )

    post_adapter_resolver = FakeSecretResolver()
    failing_adapter = FakeAdapter(fail=True)
    post_adapter = broker(
        ProductionConnectorBroker,
        current_definition=current_definition,
        resolver=post_adapter_resolver,
        adapter=failing_adapter,
        store=MemoryConnectorIdempotencyStore(),
    )
    post_adapter_prepared = prepare(
        post_adapter,
        current_definition,
        idempotency_key="broker-unification-003",
    )
    post_adapter_receipt = post_adapter.execute(
        post_adapter_prepared,
        approval=approval_for(post_adapter_prepared),
        now=NOW,
    )

    assert pre_adapter_receipt["result"] == "FAILED"
    assert pre_adapter_receipt["external_action_performed"] is False
    assert post_adapter_receipt["result"] == "FAILED"
    assert post_adapter_receipt["external_action_performed"] is True
    assert len(failing_adapter.calls) == 1
