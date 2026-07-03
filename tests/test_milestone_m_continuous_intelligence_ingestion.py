from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.contract_validator import validate_artifact
from src.core.phase_registry import build_phase_registry
from src.phase25_continuous_intelligence_ingestion import ContinuousIntelligenceIngestionLayer


def test_phase25_marks_current_artifact_fresh(tmp_path: Path) -> None:
    create_phase25_fixture(tmp_path, expires_at="2099-01-01T00:00:00+00:00", horizon_hours=1000000)
    records = ContinuousIntelligenceIngestionLayer(tmp_path).run_from_config(
        tmp_path / "config" / "phase25_continuous_intelligence_ingestion.json"
    )
    payload = asdict(records[0])

    validate_artifact("intelligence_ingestion_record", payload)
    assert payload["staleness_status"] == "fresh"
    assert payload["drift_risk_level"] in {"minimal", "low"}
    assert payload["external_data_fetch_performed"] is False
    assert payload["external_action_performed"] is False


def test_phase25_detects_expired_generated_candidates(tmp_path: Path) -> None:
    create_phase25_fixture(tmp_path, expires_at="2026-01-01T00:00:00+00:00", horizon_hours=1000000)
    records = ContinuousIntelligenceIngestionLayer(tmp_path).run_from_config(
        tmp_path / "config" / "phase25_continuous_intelligence_ingestion.json"
    )
    payload = asdict(records[0])

    validate_artifact("intelligence_ingestion_record", payload)
    assert payload["staleness_status"] == "stale_expired_generated_candidates"
    assert payload["drift_risk_level"] == "high"
    assert "expired_generated_action_candidates_present" in payload["stale_indicators"]
    assert payload["temporal_freshness_validation"]["expired_generated_action_candidates"] == 1
    assert any("Regeneration target" in action for action in payload["recommended_refresh_actions"])
    assert payload["external_data_fetch_performed"] is False


def test_cli_run_phase25_exports_intelligence_ingestion_records(tmp_path: Path) -> None:
    create_phase25_fixture(tmp_path, expires_at="2026-01-01T00:00:00+00:00", horizon_hours=1000000)
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase25",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase25_intelligence" / "aigc_phase25_intelligence_ingestion_records.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("intelligence_ingestion_record", payload[0])
    assert payload[0]["staleness_status"] == "stale_expired_generated_candidates"
    assert payload[0]["external_data_fetch_performed"] is False


def test_phase_registry_includes_phase25_continuous_intelligence() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase25"].schema_name == "intelligence_ingestion_record"
    assert registry["phase25"].external_action_risk == "none_internal_freshness_and_drift_review_only"


def create_phase25_fixture(root: Path, expires_at: str, horizon_hours: int) -> None:
    for path in [
        root / "config",
        root / "data" / "phase24_procurement",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    procurement_record = {
        "record_id": "AIGC-PROC-CIIL",
        "created_at": "2026-07-02T00:00:00+00:00",
        "phase": "phase24_truth_first_procurement_governance",
        "status": "procurement_truth_recorded",
        "opportunity_id": "opp_ciil",
        "proposal_id": "proposal_ciil",
        "authorization_id": "auth_ciil",
        "action_id": "AIGC-ACT-CIIL",
        "title": "Continuous intelligence fixture",
        "employer": "Example",
        "source_platform": "GitHub",
        "source_url": "https://example.invalid/ciil",
        "source_truth_status": "real_read_only_source_snapshot_present",
        "artifact_chain": [],
        "procurement_classification": "real_source_with_pending_generated_action_candidate"
        if expires_at.startswith("2099")
        else "real_source_with_expired_generated_action_candidate",
        "procurement_decision": "operator_review_required_before_action"
        if expires_at.startswith("2099")
        else "archive_or_regenerate_before_action",
        "current_action_state": {
            "phase5_decision": "pending",
            "created_at": "2026-07-02T00:00:00+00:00",
            "expires_at": expires_at,
            "expired": not expires_at.startswith("2099"),
            "phase6_authorized": False,
            "approval_granted": False,
            "external_action_performed": False,
            "generated_action_candidate": True,
        },
        "truth_controls": {
            "source_snapshot_preserved": True,
            "generated_artifacts_marked_derived": True,
            "stale_generated_artifacts_active": not expires_at.startswith("2099"),
            "requires_regeneration_before_approval": not expires_at.startswith("2099"),
            "approval_granted": False,
            "deletion_allowed_in_phase24": False,
        },
        "recommended_cleanup_actions": [],
        "blocked_actions": [],
        "approval_required_before_external_action": True,
        "deletion_performed": False,
        "external_action_performed": False,
    }
    write_json(root / "data" / "phase24_procurement" / "aigc_phase24_procurement_records.json", [procurement_record])
    write_json(
        root / "config" / "phase25_continuous_intelligence_ingestion.json",
        {
            "output_file": "data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json",
            "report_file": "data/reports/phase25_signature_update.md",
            "audit_log": "data/audit/aigc_phase25_audit.jsonl",
            "artifact_sources": [
                {
                    "context_domain": "truth_first_procurement_ledger",
                    "source_kind": "generated_internal_procurement_ledger",
                    "path": "data/phase24_procurement/aigc_phase24_procurement_records.json",
                    "freshness_horizon_hours": horizon_hours,
                    "regeneration_command": "python .\\src\\aigc.py run phase24",
                }
            ],
            "freshness_agents": [
                "Temporal-Reasoning Agent",
                "Freshness-Validation Agent",
                "Drift-Detection Agent",
                "Ontological-Mapping Agent",
                "Praxeological-Optimization Agent",
            ],
            "ontology_axes": ["ontology", "epistemology", "methodology", "praxeology"],
            "blocked_actions": [
                "fetch_external_data_without_operator_command",
                "run_background_daemon",
                "delete_stale_artifacts_without_operator_command",
                "approve_external_action",
            ],
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
