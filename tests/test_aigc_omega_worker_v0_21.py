import pytest

from src.core.omega_worker_evidence_ledger import EvidenceLedger
from src.core.omega_worker_connector_boundary import (
    ConnectorBoundaryError,
    ConnectorEvidence,
    ConnectorPolicy,
    ReadOnlyConnectorBoundary,
)


class FakeSource:
    connector_id = "synthetic-read"

    def __init__(self):
        self.references = []

    def read_evidence(self, evidence_reference):
        self.references.append(evidence_reference)
        return ConnectorEvidence(
            "e1", self.connector_id, "payment", evidence_reference, {"amount": 100}
        )


def policy(**kwargs):
    values = dict(policy_id="p1", allowed_connectors=("synthetic-read",))
    values.update(kwargs)
    return ConnectorPolicy(**values)


def test_allowlisted_read_only_connector_ingests_and_ledgeres_provenance():
    ledger = EvidenceLedger()
    source = FakeSource()
    result = ReadOnlyConnectorBoundary(policy(), ledger).ingest(
        source, evidence_reference="payment/123"
    )
    assert result.evidence_id == "e1"
    assert ledger.verify()
    assert len(ledger.entries) == 1


def test_non_allowlisted_connector_fails_closed():
    source = FakeSource()
    with pytest.raises(ConnectorBoundaryError):
        ReadOnlyConnectorBoundary(
            policy(allowed_connectors=("other",))
        ).ingest(source, evidence_reference="payment/123")


def test_empty_reference_fails_closed():
    with pytest.raises(ConnectorBoundaryError):
        ReadOnlyConnectorBoundary(policy()).ingest(FakeSource(), evidence_reference="")


def test_provenance_mismatch_fails_closed():
    class WrongSource(FakeSource):
        def read_evidence(self, evidence_reference):
            return ConnectorEvidence("e1", "different", "payment", evidence_reference, {})

    with pytest.raises(ConnectorBoundaryError):
        ReadOnlyConnectorBoundary(policy()).ingest(
            WrongSource(), evidence_reference="payment/123"
        )


def test_external_write_and_authority_expansion_are_rejected():
    with pytest.raises(ConnectorBoundaryError):
        policy(allow_external_writes=True)
    with pytest.raises(ConnectorBoundaryError):
        policy(allow_financial_authority=True)


def test_boundary_has_no_write_or_authority_methods():
    boundary = ReadOnlyConnectorBoundary(policy())
    forbidden = ("write", "send", "authorize", "discover_credentials", "discover_target")
    assert all(not hasattr(boundary, name) for name in forbidden)
