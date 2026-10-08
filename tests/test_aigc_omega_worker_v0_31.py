import pytest

from src.core.omega_worker_connector_admission import ReadOnlyAdmissionPolicy
from src.core.omega_worker_connector_admission_ledger import ConnectorAdmissionAuditLedger
from src.core.omega_worker_sandbox_connector import SandboxConnector, SandboxConnectorError, SandboxCredential


def make_connector() -> SandboxConnector:
    return SandboxConnector(
        "sandbox-connector-a",
        {
            "sandbox://fixture/001": {
                "evidence_id": "evidence-001",
                "observed_at": "2026-10-08T00:00:00Z",
                "payload": {"status": "ok"},
            }
        },
    )


def make_policy() -> ReadOnlyAdmissionPolicy:
    return ReadOnlyAdmissionPolicy(
        policy_id="policy-v0-31",
        connector_id="sandbox-connector-a",
    )


def test_sandbox_read_requires_explicit_credential_and_fixed_reference() -> None:
    connector = make_connector()
    evidence = connector.read(
        "sandbox://fixture/001",
        SandboxCredential("credential-sandbox-001"),
    )
    assert evidence.payload["status"] == "ok"

    with pytest.raises(SandboxConnectorError):
        connector.read("sandbox://outside/001", SandboxCredential("credential-sandbox-001"))

    with pytest.raises(SandboxConnectorError):
        connector.read("sandbox://fixture/001", object())


def test_admission_creates_audit_receipt() -> None:
    audit = ConnectorAdmissionAuditLedger()
    evidence, admission, receipt = make_connector().admit(
        make_policy(),
        evidence_reference="sandbox://fixture/001",
        credential=SandboxCredential("credential-sandbox-001"),
        audit=audit,
        receipt_id="receipt-v0-31-001",
    )
    assert evidence.evidence_id == "evidence-001"
    assert admission.admitted is True
    assert audit.verify_receipt(receipt)
    assert audit.verify_chain()


def test_production_credential_is_rejected() -> None:
    connector = make_connector()
    with pytest.raises(SandboxConnectorError):
        connector.read("sandbox://fixture/001", SandboxCredential("credential-production-001", sandbox=False))


def test_no_external_write_or_authorization_surface() -> None:
    connector = make_connector()
    assert not hasattr(connector, "write")
    assert not hasattr(connector, "write_external")
    assert not hasattr(connector, "authorize")
    assert not hasattr(connector, "discover_target")


def test_fixture_provenance_is_required() -> None:
    with pytest.raises(SandboxConnectorError):
        SandboxConnector(
            "sandbox-connector-a",
            {"sandbox://fixture/bad": {"payload": {"status": "ok"}}},
        )


def test_audit_cannot_be_bypassed_by_missing_identity() -> None:
    audit = ConnectorAdmissionAuditLedger()
    with pytest.raises(SandboxConnectorError):
        make_connector().admit(
            ReadOnlyAdmissionPolicy(policy_id="policy-v0-31", connector_id="other"),
            evidence_reference="sandbox://fixture/001",
            credential=SandboxCredential("credential-sandbox-001"),
            audit=audit,
            receipt_id="receipt-v0-31-002",
        )
