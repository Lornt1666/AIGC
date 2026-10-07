import pytest

from src.core.omega_worker_connector_registry import ConnectorRegistry
from src.core.omega_worker_connector_sdk import ConnectorCapabilities
from src.core.omega_worker_connector_arena import SyntheticMultiConnectorArena


def connector(cid, payload, observed_at="2099-01-01T00:00:00Z"):
    class C:
        capabilities = ConnectorCapabilities(cid, "0.24")
        def read(self, ref):
            return type("Result", (), {
                "connector_id": cid,
                "evidence_id": cid + "-e1",
                "evidence_kind": "payment",
                "source_reference": ref,
                "payload": payload,
                "observed_at": observed_at,
            })()
    return C()


def arena(*connectors):
    registry = ConnectorRegistry()
    for c in connectors:
        registry.register(c)
    return SyntheticMultiConnectorArena(registry)


def test_consensus_selects_deterministically():
    result = arena(
        connector("a", {"amount": 100}),
        connector("b", {"amount": 100}),
    ).evaluate(("b", "a"), evidence_reference="payment/1", expected_kind="payment")
    assert result.status == "ACCEPT"
    assert result.selected_connector == "a"
    assert result.candidates == ("a", "b")


def test_conflicting_valid_evidence_escalates():
    result = arena(
        connector("a", {"amount": 100}),
        connector("b", {"amount": 125}),
    ).evaluate(("a", "b"), evidence_reference="payment/1", expected_kind="payment")
    assert result.status == "ESCALATE"
    assert result.selected_connector is None


def test_stale_evidence_is_excluded():
    result = arena(
        connector("stale", {"amount": 100}, "2020-01-01T00:00:00Z"),
        connector("fresh", {"amount": 100}),
    ).evaluate(
        ("stale", "fresh"),
        evidence_reference="payment/1",
        expected_kind="payment",
        observed_after="2090-01-01T00:00:00Z",
    )
    assert result.status == "ESCALATE"
    assert result.selected_connector is None


def test_wrong_kind_is_excluded():
    result = arena(
        connector("a", {"amount": 100}),
    ).evaluate(("a",), evidence_reference="payment/1", expected_kind="delivery")
    assert result.status == "ESCALATE"


def test_ledger_remains_valid():
    registry = ConnectorRegistry()
    registry.register(connector("a", {"amount": 100}))
    SyntheticMultiConnectorArena(registry).evaluate(
        ("a",), evidence_reference="payment/1", expected_kind="payment"
    )
    assert registry.ledger.verify()
