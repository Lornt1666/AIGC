from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "core" / "assurance" / "shared_contracts.py"
SPEC = importlib.util.spec_from_file_location("eiap_shared_contracts", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SharedContractValidator = MODULE.SharedContractValidator


def envelope(contract_type: str, payload: dict) -> dict:
    return {
        "contract_version": "1.0.0",
        "contract_type": contract_type,
        "payload": payload,
    }


def test_actor_reference_passes() -> None:
    result = SharedContractValidator().validate(envelope("actor_reference", {
        "actor_id": "actor-001",
        "actor_type": "human",
        "display_name": "Operator",
        "authority_source": "repository_operator",
    }))
    assert result.passed, result


def test_unknown_contract_type_fails() -> None:
    result = SharedContractValidator().validate(envelope("unknown", {}))
    assert not result.passed
    assert "UNKNOWN_CONTRACT_TYPE" in result.reason_codes


def test_missing_required_fields_fail() -> None:
    result = SharedContractValidator().validate(envelope("artifact_reference", {
        "artifact_id": "artifact-001"
    }))
    assert not result.passed
    assert "MISSING_REQUIRED_FIELDS" in result.reason_codes


def test_invalid_revision_fails() -> None:
    result = SharedContractValidator().validate(envelope("decision", {
        "decision_id": "decision-001",
        "decision_type": "review",
        "result": "pass",
        "reason_codes": [],
        "revision": "abc",
    }))
    assert not result.passed
    assert "INVALID_REVISION" in result.reason_codes


def test_finding_confidence_is_bounded() -> None:
    result = SharedContractValidator().validate(envelope("finding", {
        "finding_id": "finding-001",
        "domain": "security",
        "revision": "abcdef123456",
        "severity": "high",
        "confidence": 1.5,
        "blocking": True,
        "state": "open",
    }))
    assert not result.passed
    assert "INVALID_CONFIDENCE" in result.reason_codes


def test_traceability_requires_articles_and_rollback() -> None:
    result = SharedContractValidator().validate(envelope("traceability_manifest", {
        "manifest_id": "manifest-001",
        "revision": "abcdef123456",
        "constitutional_articles": [],
        "artifact_ids": [],
        "evidence_ids": [],
        "rollback_boundary": "",
    }))
    assert not result.passed
    assert "MISSING_CONSTITUTIONAL_TRACEABILITY" in result.reason_codes
    assert "MISSING_ROLLBACK_BOUNDARY" in result.reason_codes
