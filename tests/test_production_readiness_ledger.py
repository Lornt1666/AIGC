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
    validate_report,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BLOCKING_GAPS = {
    "security_privacy_wiring",
    "transactional_persistence",
    "production_identity_access",
    "approved_external_connectors",
    "production_deployment",
}
EXPECTED_IDENTITY_EVIDENCE = {
    "config/production_identity_platform_baseline.json",
    "src/infrastructure/identity/google_identity_platform_adapter.py",
    "src/application/production_sessions.py",
    "migrations/sqlite/0004_production_identity_sessions.sql",
    "migrations/postgresql/0004_production_identity_sessions.sql",
    "tests/integration/test_identity_platform_session_pipeline.py",
}
EXPECTED_CONNECTOR_EVIDENCE = {
    "config/production_connector_secret_broker.json",
    "schemas/production_connector_secret_broker.schema.json",
    "src/application/production_connectors.py",
    "src/infrastructure/secrets/google_secret_manager.py",
    "tests/application/test_production_connector_broker.py",
    "tests/application/test_connector_broker_execution_unification.py",
    "tests/infrastructure/test_google_secret_manager_resolver.py",
    "docs/PRODUCTION_CONNECTOR_SECRET_BROKER_V1.md",
}
EXPECTED_DEPLOYMENT_EVIDENCE = {
    "config/production_deployment_baseline.json",
    "schemas/production_deployment_baseline.schema.json",
    "src/core/production_deployment_plan.py",
    "src/core/production_release_gate.py",
    "schemas/production_release_gate_receipt.schema.json",
    "infra/terraform/gcp/guardrails.tf",
    "infra/terraform/gcp/main.tf",
    "tests/test_production_deployment_plan.py",
    "tests/test_production_release_gate.py",
    "docs/PRODUCTION_DEPLOYMENT_BASELINE_V1.md",
}


def capability_map(report: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(item["capability_id"]): item
        for item in report["capability_results"]  # type: ignore[index]
    }


def ledger_capability(ledger: dict[str, object], capability_id: str) -> dict[str, object]:
    return next(
        item
        for item in ledger["capabilities"]  # type: ignore[index]
        if item["capability_id"] == capability_id
    )


def test_production_readiness_report_is_evidence_backed(tmp_path: Path) -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    report = build_report(PROJECT_ROOT, ledger)

    assert report["external_action_performed"] is False
    assert report["operator_review_required"] is True
    assert report["production_ready"] is False
    assert report["overall_score"] == pytest.approx(74.5)
    assert report["overall_score"] < report["production_readiness_threshold"]
    assert report["evidence_model"] == "structural_repository_evidence_v2"
    assert report["evidence_strength"] == "structural_not_operational_proof"
    assert report["source_revision"]
    assert report["governance_summary"]["operational_proof_claimed"] is False
    assert set(report["blocking_gaps"]) == EXPECTED_BLOCKING_GAPS
    assert report["highest_impact_next_step"]["capability_id"] == "production_identity_access"

    result = run_production_readiness_ledger(PROJECT_ROOT, artifact_root=tmp_path)
    assert Path(result["report_path"]).exists()
    assert Path(result["markdown_report_path"]).exists()


def test_merged_capabilities_receive_only_supported_structural_credit() -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    report = build_report(PROJECT_ROOT, ledger)
    capabilities = capability_map(report)

    expected_statuses = {
        "work_acquisition": "implemented_internal",
        "security_privacy_wiring": "implemented_internal",
        "transactional_persistence": "implemented_internal",
        "production_identity_access": "partial",
        "approved_external_connectors": "implemented_internal",
        "production_deployment": "implemented_internal",
    }
    for capability_id, expected_status in expected_statuses.items():
        result = capabilities[capability_id]
        assert result["effective_status"] == expected_status
        assert result["evidence_complete"] is True
        assert result["missing_evidence"] == []

    assert report["dimension_scores"]["work_acquisition"] == pytest.approx(75.0)
    assert report["dimension_scores"]["data"] == pytest.approx(75.0)
    assert report["dimension_scores"]["identity_access"] == pytest.approx(50.0)
    assert report["dimension_scores"]["integrations"] == pytest.approx(75.0)
    assert report["dimension_scores"]["deployment_operations"] == pytest.approx(75.0)


def test_identity_partial_credit_is_bound_to_merged_identity_platform_baseline() -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    identity = ledger_capability(ledger, "production_identity_access")
    assert identity["declared_status"] == "partial"
    assert set(identity["required_evidence"]) == EXPECTED_IDENTITY_EVIDENCE

    report = build_report(PROJECT_ROOT, ledger)
    result = capability_map(report)["production_identity_access"]
    assert result["effective_status"] == "partial"
    assert result["evidence_complete"] is True
    assert result["blocking_for_production"] is True
    assert result["readiness_percent"] == pytest.approx(50.0)


def test_connector_internal_credit_is_bound_to_disabled_default_deny_baseline() -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    connector = ledger_capability(ledger, "approved_external_connectors")
    assert connector["declared_status"] == "implemented_internal"
    assert set(connector["required_evidence"]) == EXPECTED_CONNECTOR_EVIDENCE

    report = build_report(PROJECT_ROOT, ledger)
    result = capability_map(report)["approved_external_connectors"]
    assert result["effective_status"] == "implemented_internal"
    assert result["evidence_complete"] is True
    assert result["blocking_for_production"] is True
    assert result["readiness_percent"] == pytest.approx(75.0)


def test_deployment_internal_credit_is_bound_to_no_resource_baseline() -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    deployment = ledger_capability(ledger, "production_deployment")
    assert deployment["declared_status"] == "implemented_internal"
    assert set(deployment["required_evidence"]) == EXPECTED_DEPLOYMENT_EVIDENCE

    report = build_report(PROJECT_ROOT, ledger)
    result = capability_map(report)["production_deployment"]
    assert result["effective_status"] == "implemented_internal"
    assert result["evidence_complete"] is True
    assert result["blocking_for_production"] is True
    assert result["readiness_percent"] == pytest.approx(75.0)


def test_status_distribution_reflects_merged_internal_foundations() -> None:
    ledger = load_ledger(PROJECT_ROOT / "config" / "production_readiness_ledger.json")
    report = build_report(PROJECT_ROOT, ledger)
    assert report["status_counts"] == {
        "complete": 1,
        "implemented_internal": 8,
        "partial": 2,
    }


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
    with pytest.raises(ProductionReadinessLedgerError):
        validate_report(report)


def test_unified_cli_exposes_readiness_command() -> None:
    from src.aigc import parse_args

    args = parse_args(["readiness", "--require-production-ready"])
    assert args.command == "readiness"
    assert args.require_production_ready is True
