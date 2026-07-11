from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "core" / "assurance" / "review_packet.py"
SPEC = importlib.util.spec_from_file_location("review_packet", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

ReviewPacketGenerator = MODULE.ReviewPacketGenerator
REQUIRED_SECTIONS = MODULE.REQUIRED_SECTIONS


def sections() -> dict[str, str]:
    return {name: f"content for {name}" for name in REQUIRED_SECTIONS}


def evidence(revision: str) -> dict:
    return {
        "contract_version": "1.0.0",
        "contract_type": "evidence_reference",
        "payload": {
            "evidence_id": "EVID-001",
            "evidence_class": "behavioural_test",
            "revision": revision,
            "location": "ci/run/1",
            "maturity": "tested",
        },
    }


def receipt(revision: str) -> dict:
    return {
        "contract_version": "1.0.0",
        "contract_type": "gate_receipt",
        "payload": {
            "receipt_id": "GATE-001",
            "gate_id": "testing",
            "revision": revision,
            "result": "pass",
            "reason_codes": [],
            "evidence_ids": ["EVID-001"],
        },
    }


def test_valid_packet_is_review_ready() -> None:
    revision = "abcdef123456"
    result = ReviewPacketGenerator().generate(
        packet_id="PACKET-001",
        revision=revision,
        sections=sections(),
        evidence_references=[evidence(revision)],
        gate_receipts=[receipt(revision)],
        suggested_review_minutes=30,
    )
    assert result.passed
    assert result.packet["status"] == "review_ready"
    assert "Review Packet PACKET-001" in ReviewPacketGenerator.render_markdown(result.packet)


def test_missing_section_fails() -> None:
    revision = "abcdef123456"
    values = sections()
    values.pop("rollback_plan")
    result = ReviewPacketGenerator().generate(
        packet_id="PACKET-002",
        revision=revision,
        sections=values,
        evidence_references=[evidence(revision)],
        gate_receipts=[receipt(revision)],
        suggested_review_minutes=20,
    )
    assert not result.passed
    assert "MISSING_REQUIRED_SECTIONS" in result.reason_codes


def test_stale_evidence_fails() -> None:
    result = ReviewPacketGenerator().generate(
        packet_id="PACKET-003",
        revision="abcdef123456",
        sections=sections(),
        evidence_references=[evidence("oldrev123")],
        gate_receipts=[receipt("abcdef123456")],
        suggested_review_minutes=20,
    )
    assert not result.passed
    assert "STALE_EVIDENCE_REFERENCE" in result.reason_codes
