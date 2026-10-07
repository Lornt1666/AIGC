import pytest

from src.core.omega_worker_connector_sdk import (
    ConnectorCapabilities, ConnectorConformance, ConnectorContractError
)


class SyntheticConnector:
    capabilities = ConnectorCapabilities("synthetic", "0.22")

    def read(self, evidence_reference):
        return type("Result", (), {
            "connector_id": "synthetic",
            "evidence_id": "e1",
            "evidence_kind": "payment",
            "source_reference": evidence_reference,
            "payload": {"amount": 100, "currency": "CAD"},
            "observed_at": "2099-01-01T00:00:00Z",
        })()


def test_synthetic_connector_conforms():
    result = ConnectorConformance.validate(
        SyntheticConnector(), evidence_reference="payment/1"
    )
    assert result.evidence_id == "e1"


def test_explicit_reference_is_required():
    with pytest.raises(ConnectorContractError):
        ConnectorConformance.validate(SyntheticConnector(), evidence_reference="")


@pytest.mark.parametrize("field", [
    "write_external", "credential_discovery", "target_discovery",
    "recipient_inference", "permission_inference", "financial_authority",
])
def test_authority_expansion_is_rejected(field):
    with pytest.raises(ConnectorContractError):
        ConnectorCapabilities("bad", "0.22", **{field: True})


def test_identity_mismatch_is_rejected():
    class Bad:
        capabilities = ConnectorCapabilities("synthetic", "0.22")
        def read(self, ref):
            return type("Result", (), {
                "connector_id": "other",
                "evidence_id": "e1",
                "evidence_kind": "payment",
                "source_reference": ref,
                "payload": {},
                "observed_at": "2099-01-01T00:00:00Z",
            })()
    with pytest.raises(ConnectorContractError):
        ConnectorConformance.validate(Bad(), evidence_reference="x")
