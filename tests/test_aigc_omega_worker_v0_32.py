import pytest

from src.core.omega_worker_connector_admission import ReadOnlyAdmissionPolicy
from src.core.omega_worker_connector_admission_ledger import ConnectorAdmissionAuditLedger
from src.core.omega_worker_connector_trust import ConnectorTrustObservation
from src.core.omega_worker_sandbox_connector import SandboxConnector, SandboxCredential
from src.core.omega_worker_sandbox_reconciliation import (
    SandboxReconciliationError,
    SandboxReconciliationOrchestrator,
)


def connector(connector_id: str, status: str = "ok") -> SandboxConnector:
    return SandboxConnector(
        connector_id,
        {
            "sandbox://fixture/032": {
                "evidence_id": f"evidence-{connector_id}",
                "observed_at": "2026-10-08T00:00:00Z",
                "payload": {"status": status, "kind": "sandbox"},
            }
        },
    )


def obs(connector_id: str, *, conformance: int = 95, freshness: int = 95, provenance: int = 95, disagreement: int = 0) -> ConnectorTrustObservation:
    return ConnectorTrustObservation(
        connector_id=connector_id,
        conformance_score=conformance,
        freshness_score=freshness,
        provenance_score=provenance,
        disagreement_rate=disagreement,
    )


def setup(status_a: str = "ok", status_b: str = "ok"):
    connectors = {
        "sandbox-a": connector("sandbox-a", status_a),
        "sandbox-b": connector("sandbox-b", status_b),
    }
    policies = {
        cid: ReadOnlyAdmissionPolicy(policy_id=f"policy-{cid}", connector_id=cid)
        for cid in connectors
    }
    credentials = {
        cid: SandboxCredential(f"credential-{cid}")
        for cid in connectors
    }
    return connectors, policies, credentials


def test_consensus_flows_through_admission_trust_and_reconciliation():
    connectors, policies, credentials = setup()
    result = SandboxReconciliationOrchestrator(connectors).run(
        evidence_reference="sandbox://fixture/032",
        policies=policies,
        credentials=credentials,
        trust_observations={cid: obs(cid) for cid in connectors},
        expected_kind="sandbox",
        receipt_prefix="v0-32",
    )
    assert result.reconciliation.status == "ACCEPT"
    assert result.reconciliation.selected_connector == "sandbox-a"
    assert result.reconciliation.candidates == ("sandbox-a", "sandbox-b")
    assert len(result.admission_receipts) == 2
    assert result.audit_valid is True


def test_conflicting_sandbox_evidence_escalates():
    connectors, policies, credentials = setup("ok", "changed")
    result = SandboxReconciliationOrchestrator(connectors).run(
        evidence_reference="sandbox://fixture/032",
        policies=policies,
        credentials=credentials,
        trust_observations={cid: obs(cid) for cid in connectors},
        expected_kind="sandbox",
        receipt_prefix="v0-32-conflict",
    )
    assert result.reconciliation.status == "ESCALATE"
    assert result.reconciliation.selected_connector is None
    assert result.audit_valid is True


def test_low_trust_evidence_escalates_before_reconciliation():
    connectors, policies, credentials = setup()
    result = SandboxReconciliationOrchestrator(connectors).run(
        evidence_reference="sandbox://fixture/032",
        policies=policies,
        credentials=credentials,
        trust_observations={
            "sandbox-a": obs("sandbox-a", conformance=20, disagreement=100),
            "sandbox-b": obs("sandbox-b"),
        },
        expected_kind="sandbox",
        receipt_prefix="v0-32-trust",
    )
    assert result.reconciliation.status == "ESCALATE"
    assert result.reconciliation.selected_connector is None


def test_every_connector_requires_explicit_policy_and_credential():
    connectors, policies, credentials = setup()
    del credentials["sandbox-b"]
    with pytest.raises(SandboxReconciliationError):
        SandboxReconciliationOrchestrator(connectors).run(
            evidence_reference="sandbox://fixture/032",
            policies=policies,
            credentials=credentials,
            trust_observations={cid: obs(cid) for cid in connectors},
            expected_kind="sandbox",
            receipt_prefix="v0-32-missing",
        )


def test_no_execution_or_external_write_surface():
    connectors, _, _ = setup()
    orchestrator = SandboxReconciliationOrchestrator(connectors)
    assert not hasattr(orchestrator, "execute")
    assert not hasattr(orchestrator, "write_external")
    assert not hasattr(orchestrator, "authorize")


def test_audit_receipts_are_bound_to_each_connector():
    connectors, policies, credentials = setup()
    audit = ConnectorAdmissionAuditLedger()
    result = SandboxReconciliationOrchestrator(connectors, audit=audit).run(
        evidence_reference="sandbox://fixture/032",
        policies=policies,
        credentials=credentials,
        trust_observations={cid: obs(cid) for cid in connectors},
        expected_kind="sandbox",
        receipt_prefix="v0-32-audit",
    )
    assert len(result.admission_receipts) == 2
    assert all(audit.verify_receipt(receipt) for receipt in result.admission_receipts)
    assert audit.verify_chain()
