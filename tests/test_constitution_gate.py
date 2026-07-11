from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "core" / "governance" / "constitution_gate.py"
SPEC = importlib.util.spec_from_file_location("constitution_gate", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ConstitutionGate = MODULE.ConstitutionGate
load_json = MODULE.load_json


def registry() -> dict:
    return load_json(ROOT / "governance" / "constitution" / "aec_001.registry.json")


def valid_manifest() -> dict:
    return {
        "manifest_id": "AIGC-TRACE-TEST-001",
        "revision": "abcdef1234567890",
        "affected_articles": [
            {
                "article_id": "AEC-II",
                "compliance_state": "conformant",
                "rationale": "Claims are bound to repository evidence."
            },
            {
                "article_id": "AEC-XV",
                "compliance_state": "conformant",
                "rationale": "Scope, tests, evidence, and rollback are declared."
            }
        ],
        "contracts_changed": [],
        "risks": ["Incorrect article mapping"],
        "expected_measurable_delta": {"constitutional_traceability": "absent_to_enforced"},
        "test_plan": ["positive manifest", "blocking manifest"],
        "evidence_plan": ["CI bound to exact head"],
        "rollback_boundary": "Revert the bounded AEC-001 PR.",
        "data_classification": "internal",
        "jurisdiction_classification": ["Canada", "Alberta"],
        "human_approval_requirements": ["operator_ratification"],
        "exceptions_or_waivers": [],
        "external_action_performed": False
    }


def test_registry_is_complete_and_fail_closed() -> None:
    result = ConstitutionGate(registry()).validate_registry()
    assert result.passed, result


def test_valid_manifest_passes() -> None:
    result = ConstitutionGate(registry()).evaluate_manifest(valid_manifest())
    assert result.passed, result


def test_unknown_article_fails() -> None:
    manifest = valid_manifest()
    manifest["affected_articles"][0]["article_id"] = "AEC-UNKNOWN"
    result = ConstitutionGate(registry()).evaluate_manifest(manifest)
    assert not result.passed
    assert "UNKNOWN_ARTICLE" in result.reason_codes


def test_blocking_nonconformance_fails() -> None:
    manifest = valid_manifest()
    manifest["affected_articles"][0]["compliance_state"] = "nonconformant_blocking"
    result = ConstitutionGate(registry()).evaluate_manifest(manifest)
    assert not result.passed
    assert "NONCONFORMANT_BLOCKING" in result.reason_codes


def test_exception_requires_waiver() -> None:
    manifest = valid_manifest()
    manifest["affected_articles"][0]["compliance_state"] = "exception_requested"
    result = ConstitutionGate(registry()).evaluate_manifest(manifest)
    assert not result.passed
    assert "EXCEPTION_WITHOUT_WAIVER" in result.reason_codes


def test_missing_rollback_fails() -> None:
    manifest = valid_manifest()
    manifest["rollback_boundary"] = ""
    result = ConstitutionGate(registry()).evaluate_manifest(manifest)
    assert not result.passed
    assert "MISSING_REQUIRED_TRACEABILITY_FIELD" in result.reason_codes


def test_external_action_flag_fails() -> None:
    manifest = valid_manifest()
    manifest["external_action_performed"] = True
    result = ConstitutionGate(registry()).evaluate_manifest(manifest)
    assert not result.passed
    assert "EXTERNAL_ACTION_NOT_ALLOWED" in result.reason_codes
