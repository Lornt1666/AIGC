from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.production_readiness_ledger import (
    ProductionReadinessLedgerError,
    build_report,
    load_ledger,
    run_production_readiness_ledger,
    validate_ledger,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_production_readiness_report_is_evidence_backed(tmp_path: Path) -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    report = build_report(PROJECT_ROOT, ledger)

    assert report["external_action_performed"] is False
    assert report["operator_review_required"] is True
    assert report["production_ready"] is False
    assert report["overall_score"] < report["production_readiness_threshold"]
    assert "production_identity_access" in report["blocking_gaps"]
    assert report["highest_impact_next_step"]["capability_id"] == "production_identity_access"

    result = run_production_readiness_ledger(PROJECT_ROOT, artifact_root=tmp_path)
    assert Path(result["report_path"]).exists()
    assert Path(result["markdown_report_path"]).exists()


def test_missing_evidence_downgrades_completion_claim(tmp_path: Path) -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    ledger = json.loads(json.dumps(ledger))
    ledger["capabilities"] = [
        {
            "capability_id": "unsupported_complete",
            "name": "Unsupported completion claim",
            "dimension": "quality",
            "weight": 1,
            "declared_status": "complete",
            "required_evidence": ["does/not/exist.py"],
            "blocking_for_production": True,
        }
    ]

    report = build_report(tmp_path, ledger)
    result = report["capability_results"][0]
    assert result["effective_status"] == "partial"
    assert result["evidence_complete"] is False
    assert result["missing_evidence"] == ["does/not/exist.py"]


def test_ledger_rejects_weakened_truth_controls() -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    ledger = json.loads(json.dumps(ledger))
    ledger["truth_controls"]["completion_claim_requires_all_evidence"] = False

    with pytest.raises(ProductionReadinessLedgerError):
        validate_ledger(ledger)
