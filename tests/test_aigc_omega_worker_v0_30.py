import pytest
from src.core.omega_worker_connector_admission_ledger import AdmissionLedgerError, ConnectorAdmissionAuditLedger

def make_receipt(ledger, receipt_id="receipt-001"):
    return ledger.record(receipt_id=receipt_id, policy_id="policy-001", connector_id="connector-a",
        evidence_reference="sandbox://fixture/001", evidence_id="evidence-001", admitted=True,
        policy={"connector_id":"connector-a","sandbox_only":True},
        evidence={"evidence_id":"evidence-001","status":"ok"})

def test_admission_receipt_binds_policy_and_evidence():
    ledger=ConnectorAdmissionAuditLedger(); receipt=make_receipt(ledger)
    assert ledger.verify_receipt(receipt); assert ledger.verify_chain()

def test_tampered_receipt_fails_verification():
    ledger=ConnectorAdmissionAuditLedger(); receipt=make_receipt(ledger)
    tampered=receipt.__class__(**{**receipt.__dict__,"evidence_id":"evidence-attacker"})
    assert not ledger.verify_receipt(tampered)

def test_tampered_ledger_fails_chain_verification():
    ledger=ConnectorAdmissionAuditLedger(); make_receipt(ledger)
    ledger.ledger.entries[0].record["connector_id"]="attacker"
    assert not ledger.verify_chain()

def test_incomplete_receipt_fails_closed():
    ledger=ConnectorAdmissionAuditLedger()
    with pytest.raises(AdmissionLedgerError):
        ledger.record(receipt_id="", policy_id="p", connector_id="c", evidence_reference="r",
            evidence_id="e", admitted=True, policy={"x":1}, evidence={"y":1})

def test_audit_ledger_has_no_execution_surface():
    ledger=ConnectorAdmissionAuditLedger()
    assert not hasattr(ledger,"execute"); assert not hasattr(ledger,"write_external")
