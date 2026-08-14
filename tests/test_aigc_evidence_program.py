from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.core.nexus.evidence_program import build_evidence_program
from src.core.nexus.universal_integration import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/aigc_universal_integration_registry.v1.json"
PROGRAM = ROOT / "reports/artifacts/aigc_evidence_program_local_validation.json"
REQUESTS = ROOT / "reports/evidence_requests/aigc_external_evidence_requests.v1.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_evidence_program_is_deterministic_and_schema_valid():
    registry = _load(REGISTRY)
    expected_program, expected_requests = build_evidence_program(registry, ROOT)
    assert _load(PROGRAM) == expected_program
    assert _load(REQUESTS) == expected_requests
    Draft202012Validator(_load(ROOT / "schemas/aigc_evidence_program.schema.json")).validate(expected_program)
    Draft202012Validator(_load(ROOT / "schemas/aigc_evidence_request_bundle.schema.json")).validate(expected_requests)


def test_evidence_program_covers_denominator_optional_gates_and_prerequisites():
    program = _load(PROGRAM)
    assert program["coverage"] == {
        "all_gates": 88,
        "deferred_or_optional_gates": 52,
        "open_request_packets": 76,
        "required_counted_gates": 34,
        "required_open_request_packets": 24,
        "required_prerequisites": 2,
    }
    assert program["receipt_resolved_readiness"] == {
        "applicable_required_checks": 34,
        "verified_required_checks": 12,
        "verified_applicable_ratio": 0.352941,
    }
    assert len({gate["gate_id"] for gate in program["gates"]}) == 88


def test_every_missing_gate_has_an_exact_non_authorizing_request_packet():
    program = _load(PROGRAM)
    requests = _load(REQUESTS)
    request_ids = {item["request_packet_id"] for item in requests["requests"]}
    for gate in program["gates"]:
        assert len(gate["acceptance_criteria"]) >= 2
        if gate["status"] not in {"VERIFIED_LOCAL", "VERIFIED_EXTERNAL"}:
            assert gate["request_packet_id"] in request_ids
    assert requests["authority_granted"] is False
    assert requests["external_action_performed"] is False
    assert all("secret" in item["secret_handling"].lower() for item in requests["requests"])


def test_declared_receipt_that_does_not_resolve_is_demoted():
    registry = copy.deepcopy(_load(REGISTRY))
    chatgpt = next(item for item in registry["surfaces"] if item["id"] == "chatgpt_mcp")
    chatgpt["evidence_receipts"]["MCP initialize"] = "missing-receipt-id"
    program, _ = build_evidence_program(registry, ROOT)
    gate = next(item for item in program["gates"] if item["gate_id"] == "surface.chatgpt_mcp.mcp_initialize")
    assert gate["status"] == "UNRESOLVED_RECEIPT"
    assert gate["receipt_resolved"] is False


def test_program_and_request_hashes_bind_canonical_content():
    program = _load(PROGRAM)
    program_hash = program.pop("program_sha256")
    assert program_hash == canonical_sha256(program)
    requests = _load(REQUESTS)
    bundle_hash = requests.pop("bundle_sha256")
    assert bundle_hash == canonical_sha256(requests)


def test_mcp_v2_receipt_covers_current_tool_contract_and_zero_egress():
    receipt = _load(ROOT / "reports/artifacts/aigc_mcp_loopback_local_validation_v2.json")
    assert receipt["terminal_status"] == "PASS"
    assert receipt["tool_count"] == 12
    assert receipt["sandbox_receipt_id"] == "SBX-4F88AB73D87044790709ABBF"
    assert all(item["annotations"]["readOnlyHint"] is True for item in receipt["tools"])
    assert receipt["provider_calls_performed"] == 0
    assert receipt["external_actions_performed"] == 0
    assert receipt["authority_granted"] is False
