from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.coordination import CoordinationEngineeringRequest, engineer_coordination_plan
from src.coordination.models import CoordinationEngineeringReceipt
from src.core.epistemic.canonicalization import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_generated_coordination_schemas_match_runtime_contracts():
    request_schema = load("schemas/aigc_coordination_engineering_request.schema.json")
    receipt_schema = load("schemas/aigc_coordination_engineering_receipt.schema.json")

    assert request_schema == CoordinationEngineeringRequest.model_json_schema()
    assert receipt_schema == CoordinationEngineeringReceipt.model_json_schema()

    request = load("config/aigc_coordination_example.v1.json")
    receipt = engineer_coordination_plan(
        CoordinationEngineeringRequest.model_validate(request)
    )
    Draft202012Validator(request_schema).validate(request)
    Draft202012Validator(receipt_schema).validate(receipt)


def test_committed_local_acceptance_receipt_is_hash_valid_and_truthful():
    evidence = load("reports/artifacts/aigc_coordination_endpoint_local_validation.json")
    evidence_hash = evidence.pop("evidence_sha256")

    assert evidence_hash == canonical_sha256(evidence)
    assert evidence["terminal_status"] == "PASS"
    assert evidence["verified_checks"] == evidence["applicable_checks"] == 11
    assert all(evidence["checks"].values())
    assert evidence["production_ready"] is False
    assert evidence["authority_granted"] is False
    assert evidence["external_actions_performed"] == 0


def test_endpoint_architecture_document_names_all_four_required_dimensions():
    document = (
        ROOT / "docs" / "architecture" / "AIGC_COORDINATION_ENGINEERING_ENDPOINT_V1.md"
    ).read_text(encoding="utf-8")
    for dimension in ("State", "Iteration", "Tooling", "Multi-agent coordination"):
        assert dimension in document
    assert "POST /v1/coordination/engineer" in document
    assert "PROPOSED_NOT_APPLIED" in document
