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
from src.phase27_stale_artifact_renewal import StaleArtifactRenewalController


def test_phase27_renews_expired_generated_candidate_without_deletion(tmp_path: Path) -> None:
    create_phase27_fixture(tmp_path, classification="real_source_with_expired_generated_action_candidate")
    records = StaleArtifactRenewalController(tmp_path).run_from_config(
        tmp_path / "config" / "phase27_stale_artifact_renewal.json"
    )
    payload = asdict(records[0])

    validate_artifact("stale_artifact_renewal_record", payload)
    assert payload["renewal_strategy"] == "preserve_historical_derivative_and_regenerate_from_fresh_source_context"
    assert payload["approval_gate"]["old_action_id_approval_allowed"] is False
    assert payload["deep_research_brief"]["external_research_performed"] is False
    assert payload["deletion_performed"] is False
    assert payload["external_data_fetch_performed"] is False
    assert payload["external_action_performed"] is False


def test_phase27_ignores_active_pending_candidate(tmp_path: Path) -> None:
    create_phase27_fixture(tmp_path, classification="real_source_with_pending_generated_action_candidate")
    records = StaleArtifactRenewalController(tmp_path).run_from_config(
        tmp_path / "config" / "phase27_stale_artifact_renewal.json"
    )

    assert records == []


def test_cli_run_phase27_exports_renewal_records(tmp_path: Path) -> None:
    create_phase27_fixture(tmp_path, classification="real_source_with_expired_generated_action_candidate")
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase27",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase27_renewal" / "aigc_phase27_stale_artifact_renewal_records.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("stale_artifact_renewal_record", payload[0])
    assert payload[0]["regeneration_blueprint"]["regeneration_allowed_now"] is False
    assert payload[0]["external_action_performed"] is False


def test_phase_registry_includes_phase27_stale_artifact_renewal() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase27"].schema_name == "stale_artifact_renewal_record"
    assert registry["phase27"].external_action_risk == "none_internal_renewal_blueprints_only"


def create_phase27_fixture(root: Path, classification: str) -> None:
    for path in [
        root / "config",
        root / "data" / "phase24_procurement",
        root / "data" / "phase25_intelligence",
        root / "data" / "phase26_capability_procurement",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    write_json(
        root / "data" / "phase24_procurement" / "aigc_phase24_procurement_records.json",
        [{
            "record_id": "proc_renewal_1",
            "created_at": "2026-07-02T00:00:00+00:00",
            "phase": "phase24_truth_first_procurement_governance",
            "status": "procurement_truth_recorded",
            "opportunity_id": "opp_renewal",
            "proposal_id": "proposal_renewal",
            "authorization_id": "auth_renewal",
            "action_id": "AIGC-ACT-RENEWAL",
            "title": "Renewal test candidate",
            "employer": "Example",
            "source_platform": "GitHub",
            "source_url": "https://example.invalid/renewal",
            "source_truth_status": "real_read_only_source_snapshot_present",
            "artifact_chain": [
                {
                    "phase": "phase2_opportunity_radar",
                    "artifact_id": "opp_renewal",
                    "path": "data/phase2_processed/aigc_phase2_opportunity_queue.json",
                    "truth_role": "source_evidence",
                    "status": "queue_for_phase_3",
                },
                {
                    "phase": "phase5_human_approval_gate",
                    "artifact_id": "auth_renewal",
                    "path": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
                    "truth_role": "generated_internal_derivative",
                    "status": "expired_pending_generated_derivative",
                },
            ],
            "procurement_classification": classification,
            "procurement_decision": "archive_or_regenerate_before_action",
            "current_action_state": {
                "expired": classification == "real_source_with_expired_generated_action_candidate",
                "external_action_performed": False,
            },
            "truth_controls": {},
            "recommended_cleanup_actions": [],
            "blocked_actions": [],
            "approval_required_before_external_action": True,
            "deletion_performed": False,
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "data" / "phase25_intelligence" / "aigc_phase25_intelligence_ingestion_records.json",
        [{
            "record_id": "ciil_renewal",
            "context_domain": "phase5_approval_candidates",
            "staleness_status": "stale_expired_generated_candidates",
            "drift_risk_level": "high",
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "data" / "phase26_capability_procurement" / "aigc_phase26_capability_procurement_records.json",
        [{
            "record_id": "cap_renewal",
            "gap_analysis": [
                "test: average quality score 70 is below threshold 85.",
                "test: expired generated action candidates exceed threshold 0.",
            ],
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "config" / "phase27_stale_artifact_renewal.json",
        {
            "output_file": "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json",
            "report_file": "data/reports/phase27_signature_update.md",
            "audit_log": "data/audit/aigc_phase27_audit.jsonl",
            "input_files": {
                "truth_first_procurement_records": "data/phase24_procurement/aigc_phase24_procurement_records.json",
                "intelligence_ingestion_records": "data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json",
                "capability_procurement_records": "data/phase26_capability_procurement/aigc_phase26_capability_procurement_records.json",
            },
            "renewal_targets": [
                "real_source_with_expired_generated_action_candidate",
                "generated_internal_chain_missing_source_snapshot",
            ],
            "quality_targets": {
                "minimum_quality_score": 85,
                "maximum_uncertainty_score": 35,
                "maximum_high_drift_records": 0,
                "maximum_expired_generated_action_candidates": 0,
            },
            "deep_research_axes": ["source_currentness", "technical_scope", "legal_ethics"],
            "renewal_commands": ["python .\\src\\aigc.py run phase24", "python .\\src\\aigc.py run phase27"],
            "blocked_actions": [
                "delete_stale_artifacts_without_operator_command",
                "approve_external_action",
                "bypass_phase5_approval",
            ],
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
