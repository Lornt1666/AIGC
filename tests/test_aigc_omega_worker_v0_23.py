import pytest

from src.core.omega_worker_connector_registry import (
    ConnectorAdmissionError, ConnectorRegistry, EvidenceRouter
)
from src.core.omega_worker_connector_sdk import ConnectorCapabilities


class SyntheticConnector:
    capabilities = ConnectorCapabilities("synthetic-a", "0.23")

    def read(self, ref):
        return type("Result", (), {
            "connector_id": "synthetic-a",
            "evidence_id": "e1",
            "evidence_kind": "delivery",
            "source_reference": ref,
            "payload": {"accepted": True},
            "observed_at": "2099-01-01T00:00:00Z",
        })()


def test_registration_and_deterministic_routing():
    registry = ConnectorRegistry()
    record = registry.register(SyntheticConnector())
    assert record.admitted is True
    assert registry.list_admitted() == ("synthetic-a",)
    result = EvidenceRouter(registry).route("synthetic-a", "delivery/1")
    assert result.evidence_id == "e1"
    assert registry.ledger.verify()
    assert len(registry.ledger.entries) == 2


def test_duplicate_registration_fails_closed():
    registry = ConnectorRegistry()
    registry.register(SyntheticConnector())
    with pytest.raises(ConnectorAdmissionError):
        registry.register(SyntheticConnector())


def test_unknown_connector_cannot_route():
    with pytest.raises(ConnectorAdmissionError):
        EvidenceRouter(ConnectorRegistry()).route("missing", "x")


def test_empty_reference_cannot_route():
    registry = ConnectorRegistry()
    registry.register(SyntheticConnector())
    with pytest.raises(ConnectorAdmissionError):
        EvidenceRouter(registry).route("synthetic-a", "")


@pytest.mark.parametrize("field", [
    "write_external", "credential_discovery", "target_discovery",
    "recipient_inference", "permission_inference", "financial_authority",
])
def test_unsafe_capability_manifest_cannot_exist(field):
    with pytest.raises(Exception):
        ConnectorCapabilities("unsafe", "0.23", **{field: True})


def test_router_does_not_expose_write_or_authorize_operations():
    router = EvidenceRouter(ConnectorRegistry())
    forbidden = ("write", "send", "authorize", "discover_credentials", "discover_target")
    assert all(not hasattr(router, name) for name in forbidden)
