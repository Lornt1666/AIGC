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
from src.phase26_capability_procurement import AscendedCapabilityProcurementProgram


def test_phase26_records_ready_capability_procurement(tmp_path: Path) -> None:
    create_phase26_fixture(
        tmp_path,
        quality_score=92,
        uncertainty_score=12,
        expired_generated_candidate=False,
        drift_risk_level="minimal",
    )
    records = AscendedCapabilityProcurementProgram(tmp_path).run_from_config(
        tmp_path / "config" / "phase26_capability_procurement.json"
    )
    payload = asdict(records[0])

    validate_artifact("capability_procurement_record", payload)
    assert payload["procurement_decision"] == "ready_for_internal_quality_application"
    assert payload["gap_analysis"] == []
    assert payload["quantum_quality_application"]["literal_quantum_claim"] is False
    assert payload["external_data_fetch_performed"] is False
    assert payload["external_action_performed"] is False


def test_phase26_surfaces_procurement_gaps(tmp_path: Path) -> None:
    create_phase26_fixture(
        tmp_path,
        quality_score=70,
        uncertainty_score=80,
        expired_generated_candidate=True,
        drift_risk_level="high",
    )
    records = AscendedCapabilityProcurementProgram(tmp_path).run_from_config(
        tmp_path / "config" / "phase26_capability_procurement.json"
    )
    payload = asdict(records[0])

    validate_artifact("capability_procurement_record", payload)
    assert payload["procurement_decision"] == "resolve_procurement_gaps_before_ascended_quality_claim"
    assert payload["gap_analysis"]
    assert any("quality score" in gap for gap in payload["gap_analysis"])
    assert any("uncertainty score" in gap for gap in payload["gap_analysis"])
    assert any("drift records" in gap for gap in payload["gap_analysis"])
    assert any("expired generated action candidates" in gap for gap in payload["gap_analysis"])
    assert payload["approval_required_before_external_action"] is True


def test_cli_run_phase26_exports_capability_procurement_records(tmp_path: Path) -> None:
    create_phase26_fixture(
        tmp_path,
        quality_score=70,
        uncertainty_score=80,
        expired_generated_candidate=True,
        drift_risk_level="high",
    )
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase26",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase26_capability_procurement" / "aigc_phase26_capability_procurement_records.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("capability_procurement_record", payload[0])
    assert payload[0]["external_action_performed"] is False
    assert payload[0]["procurement_decision"] == "resolve_procurement_gaps_before_ascended_quality_claim"


def test_phase_registry_includes_phase26_capability_procurement() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase26"].schema_name == "capability_procurement_record"
    assert registry["phase26"].external_action_risk == "none_internal_capability_procurement_only"


def create_phase26_fixture(
    root: Path,
    quality_score: int,
    uncertainty_score: int,
    expired_generated_candidate: bool,
    drift_risk_level: str,
) -> None:
    for path in [
        root / "config",
        root / "data" / "phase20_fidelity",
        root / "data" / "phase21_customer_satisfaction",
        root / "data" / "phase22_quality",
        root / "data" / "phase23_work_orders",
        root / "data" / "phase24_procurement",
        root / "data" / "phase25_intelligence",
    ]:
        path.mkdir(parents=True, exist_ok=True)

    write_json(root / "data" / "phase20_fidelity" / "aigc_phase20_fidelity_reviews.json", [{"review_id": "fid_1"}])
    write_json(root / "data" / "phase21_customer_satisfaction" / "aigc_phase21_customer_satisfaction_records.json", [{"record_id": "chi_1"}])
    write_json(
        root / "data" / "phase22_quality" / "aigc_phase22_quality_kernel_records.json",
        [{
            "record_id": "qk_1",
            "quality_score": quality_score,
            "uncertainty_score": uncertainty_score,
            "quality_state": "ascended_ready_for_human_approval_review" if uncertainty_score < 35 else "improvement_required_before_approval_review",
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "data" / "phase23_work_orders" / "aigc_phase23_work_order_governance_records.json",
        [{
            "record_id": "wog_1",
            "quantum_quality_state": {
                "quality_score": quality_score,
                "uncertainty_score": uncertainty_score,
            },
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "data" / "phase24_procurement" / "aigc_phase24_procurement_records.json",
        [{
            "record_id": "proc_1",
            "procurement_classification": "real_source_with_expired_generated_action_candidate"
            if expired_generated_candidate
            else "real_source_with_pending_generated_action_candidate",
            "current_action_state": {
                "expired": expired_generated_candidate,
                "external_action_performed": False,
            },
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "data" / "phase25_intelligence" / "aigc_phase25_intelligence_ingestion_records.json",
        [{
            "record_id": "ciil_1",
            "staleness_status": "stale" if drift_risk_level == "high" else "fresh",
            "drift_risk_level": drift_risk_level,
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "config" / "phase26_capability_procurement.json",
        {
            "output_file": "data/phase26_capability_procurement/aigc_phase26_capability_procurement_records.json",
            "report_file": "data/reports/phase26_signature_update.md",
            "audit_log": "data/audit/aigc_phase26_audit.jsonl",
            "input_files": {
                "quality_kernel_records": "data/phase22_quality/aigc_phase22_quality_kernel_records.json",
                "work_order_governance_records": "data/phase23_work_orders/aigc_phase23_work_order_governance_records.json",
                "truth_first_procurement_records": "data/phase24_procurement/aigc_phase24_procurement_records.json",
                "intelligence_ingestion_records": "data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json",
            },
            "quality_thresholds": {
                "minimum_average_quality_score": 85,
                "maximum_average_uncertainty_score": 35,
                "maximum_high_drift_records": 0,
                "maximum_expired_generated_action_candidates": 0,
            },
            "capability_procurements": [
                {
                    "domain": "test_capability_procurement",
                    "purpose": "Unit-test capability procurement.",
                    "source_aliases": [
                        "quality_kernel_records",
                        "work_order_governance_records",
                        "truth_first_procurement_records",
                        "intelligence_ingestion_records",
                    ],
                    "required_inputs": ["quality_kernel_records"],
                    "required_controls": ["perfect_draft_v1", "ontological_self_audit"],
                    "required_standards": ["technical_correctness", "auditability"],
                    "required_agents": ["Technical-Fidelity Agent"],
                }
            ],
            "ontology_axes": ["ontology", "epistemology", "methodology", "risk_theory"],
            "blocked_actions": ["claim_ascended_quality_without_evidence", "bypass_phase5_approval"],
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
