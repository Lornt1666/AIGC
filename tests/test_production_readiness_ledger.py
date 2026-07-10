from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.production_readiness_ledger import (
    ProductionReadinessLedgerError,
    build_report,
    evidence_exists,
    load_ledger,
    repository_revision,
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
    assert report["evidence_model"] == "structural_repository_evidence_v2"
    assert report["evidence_strength"] == "structural_not_operational_proof"
    assert report["source_revision"]
    assert report["governance_summary"]["operational_proof_claimed"] is False
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


def test_empty_files_and_directories_do_not_count_as_evidence(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("", encoding="utf-8")
    assert evidence_exists(tmp_path, "empty.py") is False

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    (empty_dir / "placeholder.txt").write_text("", encoding="utf-8")
    assert evidence_exists(tmp_path, "empty_dir") is False

    (empty_dir / "evidence.txt").write_text("verified structural evidence\n", encoding="utf-8")
    assert evidence_exists(tmp_path, "empty_dir") is True


def test_report_revision_is_bound_or_explicitly_unbound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    revision = repository_revision(tmp_path)
    assert revision == "unbound"

    monkeypatch.setenv("GITHUB_SHA", "abc123")
    assert repository_revision(tmp_path) == "abc123"


def test_strict_report_schema_rejects_untracked_fields() -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    report = build_report(PROJECT_ROOT, ledger)
    report["fabricated_metric"] = 100
    from src.core.contract_validator import ContractValidationError, validate_artifact

    with pytest.raises(ContractValidationError):
        validate_artifact("production_readiness_report", report)


def test_unified_cli_exposes_readiness_command() -> None:
    from src.aigc import parse_args

    args = parse_args(["readiness", "--require-production-ready"])
    assert args.command == "readiness"
    assert args.require_production_ready is True
