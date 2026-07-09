from __future__ import annotations

import json
from pathlib import Path

from src.core.contract_validator import ContractValidationError, validate_artifact, validate_file
from src.core.work_order import run_work_order, work_order_from_payload


def make_payload() -> dict:
    return {
        "work_order_id": "AIGC-WO-TEST-001",
        "title": "Create governed internal draft",
        "objective": "Prepare a reviewable internal artifact packet.",
        "domain": "documentation",
        "urgency": "normal",
        "risk_class": "medium",
        "desired_output": "documentation runbook",
        "external_action_intent": "none",
        "acceptance_criteria": ["schema-valid output", "no external action"],
        "operator_visible_summary": "Test work order.",
        "symbolic_layers": ["constellation"],
        "requested_agents": ["researcher"],
        "secret_references": [],
        "source": "pytest",
    }


def test_valid_work_order_packet_passes_schema() -> None:
    payload = make_payload()

    validate_artifact("work_order_packet", payload)
    work_order = work_order_from_payload(payload)

    assert work_order.work_order_id == "AIGC-WO-TEST-001"
    assert work_order.external_action_intent == "none"


def test_invalid_work_order_packet_fails_clearly() -> None:
    payload = make_payload()
    payload.pop("objective")

    try:
        validate_artifact("work_order_packet", payload)
    except ContractValidationError as exc:
        assert "objective" in str(exc)
    else:
        raise AssertionError("Invalid work order should fail schema validation.")


def test_run_work_order_writes_schema_valid_artifacts(tmp_path: Path) -> None:
    input_path = tmp_path / "work_order.json"
    input_path.write_text(json.dumps(make_payload()), encoding="utf-8")

    result = run_work_order(tmp_path, input_path)
    receipt = result.run_receipt

    assert receipt.external_action_performed is False
    assert receipt.correlation_id
    assert receipt.status == "operator_review_required"
    assert "work_orders" in receipt.artifact_root

    for relative_path, schema_name in [
        (receipt.work_order_packet_path, "work_order_packet"),
        (receipt.governance_decision_path, "governance_decision"),
        (receipt.approval_packet_path, "approval_packet"),
        (receipt.external_action_permit_path, "external_action_permit"),
        (receipt.artifact_manifest_path, "artifact_manifest"),
        (receipt.validation_receipt_path, "validation_receipt"),
    ]:
        validate_file(schema_name, tmp_path / relative_path)

    assert result.artifact_manifest.correlation_id == receipt.correlation_id
    assert result.artifact_manifest.work_order_id == receipt.work_order_id
