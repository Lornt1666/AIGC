from src.core.omega_worker_execution import ExecutionResult
from src.core.omega_worker_execution_evidence import record_execution


def test_execution_evidence_defaults_to_unverified():
    result = ExecutionResult(
        permit_id="permit-001",
        action="deliver",
        executed=True,
        evidence="permit:permit-001;policy:policy-001",
    )

    record = record_execution(result, subject="contract-001")

    assert record.record_version == "AIGC-OMEGA-EVIDENCE-0.1"
    assert record.verification_status == "UNVERIFIED"
    assert record.external_action_performed is False
    assert "external acceptance or payment" in record.claims[1]


def test_execution_evidence_preserves_explicit_external_action_flag():
    result = ExecutionResult(
        permit_id="permit-002",
        action="prepare",
        executed=True,
        evidence="permit:permit-002;policy:policy-002",
    )

    record = record_execution(
        result,
        subject="contract-002",
        artifacts=("artifact://output-1",),
        external_action_performed=True,
    )

    payload = record.to_record()
    assert payload["external_action_performed"] is True
    assert payload["verification"]["status"] == "UNVERIFIED"
    assert payload["artifacts"] == ["artifact://output-1"]
