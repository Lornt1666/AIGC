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
from src.phase23_work_order_governor import AscendedWorkOrderGovernor


def test_phase23_governor_generates_v1_audit_v2_record(tmp_path: Path) -> None:
    create_phase23_fixture(tmp_path, uncertainty_score=18, risk_flags=[])
    records = AscendedWorkOrderGovernor(tmp_path).run_from_config(
        tmp_path / "config" / "phase23_work_order_governor.json"
    )
    payload = asdict(records[0])

    validate_artifact("work_order_governance_record", payload)
    assert len(records) == 1
    assert payload["perfect_draft_v1"]
    assert payload["ontological_self_audit"]
    assert payload["ascended_output_v2"]
    assert payload["quantum_quality_state"]["literal_quantum_claim"] is False
    assert payload["approval_required_before_external_action"] is True
    assert payload["external_action_performed"] is False


def test_phase23_governor_applies_uncertainty_next_actions(tmp_path: Path) -> None:
    create_phase23_fixture(
        tmp_path,
        uncertainty_score=82,
        risk_flags=["phase5_approval_pending", "compliance_orange"],
    )
    records = AscendedWorkOrderGovernor(tmp_path).run_from_config(
        tmp_path / "config" / "phase23_work_order_governor.json"
    )
    payload = asdict(records[0])

    validate_artifact("work_order_governance_record", payload)
    assert any("Reduce uncertainty" in action for action in payload["required_next_actions"])
    assert any("Resolve Phase 5" in action for action in payload["required_next_actions"])
    assert payload["legal_ethical_superstructure"]["external_action_blocked"] is True
    assert payload["ascended_output_v2"]["external_action_authorized"] is False


def test_cli_run_phase23_exports_work_order_governance_records(tmp_path: Path) -> None:
    create_phase23_fixture(tmp_path, uncertainty_score=20, risk_flags=[])
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase23",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase23_work_orders" / "aigc_phase23_work_order_governance_records.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("work_order_governance_record", payload[0])
    assert payload[0]["external_action_performed"] is False


def test_phase_registry_includes_phase23_work_order_governor() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase23"].schema_name == "work_order_governance_record"
    assert registry["phase23"].external_action_risk == "none_internal_work_order_governance_only"


def create_phase23_fixture(root: Path, uncertainty_score: int, risk_flags: list[str]) -> None:
    for path in [
        root / "config",
        root / "data" / "phase22_quality",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    quality_record = {
        "record_id": "AIGC-QK-TEST",
        "created_at": "2026-07-02T00:00:00+00:00",
        "phase": "phase22_quantum_aware_quality_kernel",
        "status": "internal_quality_state_recorded",
        "opportunity_id": "opp_test",
        "proposal_id": "proposal_test",
        "title": "Governed technical work order",
        "employer": "Example Client",
        "source_platform": "Example",
        "source_url": "https://example.invalid/work",
        "quality_score": 94 if uncertainty_score < 50 else 75,
        "uncertainty_score": uncertainty_score,
        "quality_state": "ascended_ready_for_human_approval_review" if uncertainty_score < 50 else "improvement_required_before_approval_review",
        "quantum_quality_model": {
            "model_type": "deterministic_uncertainty_aware_quality_state_model",
            "literal_quantum_claim": False,
        },
        "proto_omni_cycle": {
            "perfect_draft_v1": {},
            "ontological_self_audit": {},
            "ascended_output_v2": {},
        },
        "ontology_matrix": {},
        "agent_panel": [],
        "legal_ethical_boundary": {
            "external_action_blocked": True,
            "approval_gate_required": True,
            "phase5_approval_present": False,
            "compliance_status": "orange" if "compliance_orange" in risk_flags else "green",
            "secrets_used": False,
        },
        "disciplinary_best_practices": ["contract_first_artifacts"],
        "risk_flags": risk_flags,
        "improvement_directives": ["Review unresolved risk."] if risk_flags else [],
        "approval_required_before_external_action": True,
        "external_action_performed": False,
    }
    write_json(root / "data" / "phase22_quality" / "aigc_phase22_quality_kernel_records.json", [quality_record])
    write_json(
        root / "config" / "phase23_work_order_governor.json",
        {
            "input_files": {
                "quality_kernel_records": "data/phase22_quality/aigc_phase22_quality_kernel_records.json",
            },
            "output_file": "data/phase23_work_orders/aigc_phase23_work_order_governance_records.json",
            "report_file": "data/reports/phase23_signature_update.md",
            "audit_log": "data/audit/aigc_phase23_audit.jsonl",
            "max_records": 5,
            "ology_matrix": ["ontology", "epistemology", "methodology", "ethics", "risk_theory"],
            "agent_orchestration": ["Meta-Cognition Agent", "Technical-Fidelity Agent", "Ethics-Compliance Agent"],
            "capability_procurements": ["contract_validation", "human_approval_gate"],
            "blocked_actions": ["contact_external_party", "bypass_phase5_approval", "claim_literal_quantum_cognition"],
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
