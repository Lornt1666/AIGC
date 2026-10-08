from src.core.omega_worker_connector_pilot import (
    ConnectorPilotError,
    ReadOnlyConnectorPilot,
    ReadOnlyPilotPolicy,
)


class Adapter:
    connector_id = "synthetic-readonly"

    def read(self, evidence_reference, credential):
        return type("Evidence", (), {
            "connector_id": self.connector_id,
            "evidence_reference": evidence_reference,
            "evidence_id": "e-1",
            "payload": {"ok": True},
            "observed_at": "2099-01-01T00:00:00Z",
        })()


def policy():
    return ReadOnlyPilotPolicy(
        "pilot-1",
        "synthetic-readonly",
        ("allowed/ref",),
    )


def test_explicit_credential_and_allowlisted_reference():
    result = ReadOnlyConnectorPilot(policy()).read(
        Adapter(), evidence_reference="allowed/ref", credential=object()
    )
    assert result.evidence_reference == "allowed/ref"


def test_missing_credential_fails_closed():
    try:
        ReadOnlyConnectorPilot(policy()).read(
            Adapter(), evidence_reference="allowed/ref", credential=None
        )
    except ConnectorPilotError:
        return
    assert False


def test_unknown_reference_fails_closed():
    try:
        ReadOnlyConnectorPilot(policy()).read(
            Adapter(), evidence_reference="unknown/ref", credential=object()
        )
    except ConnectorPilotError:
        return
    assert False


def test_authority_expansion_is_rejected():
    try:
        ReadOnlyPilotPolicy(
            "pilot-1", "synthetic-readonly", ("allowed/ref",),
            external_writes=True
        )
    except ConnectorPilotError:
        return
    assert False


def test_provenance_is_verified():
    class BadAdapter(Adapter):
        def read(self, evidence_reference, credential):
            return type("Evidence", (), {
                "connector_id": "other",
                "evidence_reference": evidence_reference,
                "evidence_id": "e-1",
                "payload": {},
                "observed_at": "2099-01-01T00:00:00Z",
            })()
    try:
        ReadOnlyConnectorPilot(policy()).read(
            BadAdapter(), evidence_reference="allowed/ref", credential=object()
        )
    except ConnectorPilotError:
        return
    assert False
