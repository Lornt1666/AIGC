from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "core" / "governance" / "constitutional_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("constitutional_lifecycle", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

validate_amendment = MODULE.validate_amendment
validate_waiver = MODULE.validate_waiver
validate_governance_registry = MODULE.validate_governance_registry


def valid_amendment() -> dict:
    return {
        "amendment_id": "AEC-AMEND-0001",
        "constitution_id": "AEC-001",
        "from_version": "1.0.0",
        "to_version": "1.1.0",
        "affected_articles": ["AEC-II"],
        "rationale": "Clarify the evidence threshold for consequential claims.",
        "risk_analysis": ["Existing manifests may require migration."],
        "compatibility_assessment": "Backward compatible with a migration notice.",
        "migration_plan": "Update affected manifests before enforcement.",
        "rollback_plan": "Revert the amendment PR and registry version.",
        "review_path": "independent_human_review",
        "operator_ratification": True,
        "exact_revision": "abcdef1234567890",
        "status": "approved"
    }


def valid_waiver() -> dict:
    return {
        "waiver_id": "AEC-WAIVER-0001",
        "article_ids": ["AEC-XV"],
        "scope": "One bounded non-production documentation migration.",
        "owner": "repository_operator",
        "risk_statement": "The temporary exception may delay full traceability.",
        "mitigations": ["No runtime effect", "Expiry enforced"],
        "issued_at": "2026-07-11T00:00:00Z",
        "expires_at": "2026-07-20T00:00:00Z",
        "revocable": True,
        "status": "active",
        "approval_reference": "AIGC-GOV-RECEIPT-TEST",
        "exact_revision": "abcdef1234567890"
    }


def test_governance_registry_passes() -> None:
    registry = json.loads((ROOT / "governance" / "governance_registry.json").read_text(encoding="utf-8"))
    assert validate_governance_registry(registry).passed


def test_approved_amendment_requires_version_increment() -> None:
    record = valid_amendment()
    record["to_version"] = record["from_version"]
    result = validate_amendment(record)
    assert not result.passed
    assert "VERSION_NOT_INCREMENTED" in result.reason_codes


def test_approved_amendment_requires_ratification() -> None:
    record = valid_amendment()
    record["operator_ratification"] = False
    result = validate_amendment(record)
    assert not result.passed
    assert "MISSING_OPERATOR_RATIFICATION" in result.reason_codes


def test_active_waiver_must_not_be_expired() -> None:
    result = validate_waiver(valid_waiver(), now=datetime(2026, 7, 15, tzinfo=timezone.utc))
    assert result.passed

    result = validate_waiver(valid_waiver(), now=datetime(2026, 7, 21, tzinfo=timezone.utc))
    assert not result.passed
    assert "ACTIVE_WAIVER_EXPIRED" in result.reason_codes


def test_waiver_must_be_revocable() -> None:
    record = valid_waiver()
    record["revocable"] = False
    result = validate_waiver(record, now=datetime(2026, 7, 15, tzinfo=timezone.utc))
    assert not result.passed
    assert "WAIVER_NOT_REVOCABLE" in result.reason_codes
