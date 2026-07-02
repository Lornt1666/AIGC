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
from src.phase22_quantum_quality_kernel import QuantumAwareQualityKernel


def test_phase22_quality_kernel_generates_internal_quality_record(tmp_path: Path) -> None:
    create_phase22_fixture(tmp_path, compliance_status="green", finance_blockers=[], fidelity_risks=[], customer_risks=[])
    records = QuantumAwareQualityKernel(tmp_path).run_from_config(
        tmp_path / "config" / "phase22_quantum_quality_kernel.json"
    )
    payload = asdict(records[0])

    validate_artifact("quality_kernel_record", payload)
    assert len(records) == 1
    assert payload["quality_score"] >= 80
    assert payload["quantum_quality_model"]["literal_quantum_claim"] is False
    assert payload["quantum_quality_model"]["model_type"] == "deterministic_uncertainty_aware_quality_state_model"
    assert set(payload["proto_omni_cycle"]) == {"perfect_draft_v1", "ontological_self_audit", "ascended_output_v2"}
    assert payload["agent_panel"]
    assert payload["approval_required_before_external_action"] is True
    assert payload["external_action_performed"] is False


def test_phase22_quality_kernel_surfaces_uncertainty_and_review_gates(tmp_path: Path) -> None:
    create_phase22_fixture(
        tmp_path,
        compliance_status="orange",
        finance_blockers=["pay_or_budget_not_visible"],
        fidelity_risks=["acceptance_criteria_weak"],
        customer_risks=["requirements_unclear"],
    )
    records = QuantumAwareQualityKernel(tmp_path).run_from_config(
        tmp_path / "config" / "phase22_quantum_quality_kernel.json"
    )
    payload = asdict(records[0])

    validate_artifact("quality_kernel_record", payload)
    assert "compliance_orange" in payload["risk_flags"]
    assert "pay_or_budget_not_visible" in payload["risk_flags"]
    assert "phase5_approval_pending" in payload["risk_flags"]
    assert "high_quality_uncertainty" in payload["risk_flags"]
    assert payload["quality_state"] != "ascended_ready_for_human_approval_review"
    assert payload["uncertainty_score"] >= 50
    assert payload["improvement_directives"]
    assert payload["legal_ethical_boundary"]["external_action_blocked"] is True
    assert payload["external_action_performed"] is False


def test_cli_run_phase22_exports_quality_records(tmp_path: Path) -> None:
    create_phase22_fixture(tmp_path, compliance_status="green", finance_blockers=[], fidelity_risks=[], customer_risks=[])
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase22",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase22_quality" / "aigc_phase22_quality_kernel_records.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("quality_kernel_record", payload[0])
    assert payload[0]["external_action_performed"] is False
    assert payload[0]["quantum_quality_model"]["literal_quantum_claim"] is False


def test_phase_registry_includes_phase22_quality_kernel() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase22"].schema_name == "quality_kernel_record"
    assert registry["phase22"].external_action_risk == "none_internal_quality_state_model_only"


def create_phase22_fixture(
    root: Path,
    compliance_status: str,
    finance_blockers: list[str],
    fidelity_risks: list[str],
    customer_risks: list[str],
) -> None:
    for path in [
        root / "config",
        root / "data" / "phase4_proposals",
        root / "data" / "phase5_authorizations",
        root / "data" / "phase15_finance",
        root / "data" / "phase16_compliance",
        root / "data" / "phase20_fidelity",
        root / "data" / "phase21_customer_satisfaction",
    ]:
        path.mkdir(parents=True, exist_ok=True)

    proposal = {
        "proposal_id": "phase4_quality_test",
        "opportunity_id": "opp_quality_test",
        "title": "Governed documentation system",
        "employer": "Example Client",
        "source_platform": "Example",
        "source_url": "https://example.invalid/work",
        "status": "internal_draft_only",
        "employer_facing_message": "Internal draft for a scoped documentation deliverable.",
        "scope_of_work": ["Trace requirements.", "Draft deliverable.", "Review quality."],
        "deliverables": [{"name": "Documentation", "acceptance_criteria": ["Clear", "Traceable"]}],
        "forbidden_actions": ["send_external_message", "submit_application", "use_credentials"],
        "ai_use_disclosure": {"required": True, "draft_language": "AI-assisted workflow with human review."},
        "quality_assurance_plan": ["Validate against scope.", "Review assumptions."],
        "audit_summary": "Internal quality trace prepared.",
    }
    authorization = {
        "authorization_id": "AIGC-AUTH-QUALITY",
        "action_id": "AIGC-ACT-QUALITY",
        "proposal_id": "phase4_quality_test",
        "opportunity_id": "opp_quality_test",
        "decision": "pending",
        "phase6_status": {"authorized_for_phase6": False, "external_action_performed": False},
    }
    finance = {
        "record_id": "AIGC-FIN-QUALITY",
        "opportunity_id": "opp_quality_test",
        "proposal_id": "phase4_quality_test",
        "status": "internal_estimate_only",
        "blockers": finance_blockers,
        "external_action_performed": False,
    }
    compliance = {
        "review_id": "AIGC-COMP-QUALITY",
        "opportunity_id": "opp_quality_test",
        "proposal_id": "phase4_quality_test",
        "status": "cleared_internal" if compliance_status == "green" else "requires_operator_review",
        "compliance_status": compliance_status,
        "risk_flags": [] if compliance_status == "green" else ["unclear_platform_terms"],
        "required_actions": [],
        "external_action_performed": False,
    }
    fidelity = {
        "review_id": "AIGC-FID-QUALITY",
        "opportunity_id": "opp_quality_test",
        "proposal_id": "phase4_quality_test",
        "fidelity_score": 95 if compliance_status == "green" else 82,
        "quality_status": "high_fidelity_ready_for_approval_review",
        "risk_flags": fidelity_risks,
        "revision_recommendations": ["Tighten acceptance criteria."] if fidelity_risks else [],
        "external_action_performed": False,
    }
    customer = {
        "record_id": "AIGC-CHI-QUALITY",
        "opportunity_id": "opp_quality_test",
        "proposal_id": "phase4_quality_test",
        "title": "Governed documentation system",
        "employer": "Example Client",
        "source_platform": "Example",
        "source_url": "https://example.invalid/work",
        "chi_score": 91 if compliance_status == "green" else 76,
        "measurement_stage": "pre_external_action",
        "risk_flags": customer_risks,
        "improvement_actions": ["Ask one more scope question."] if customer_risks else [],
        "external_action_performed": False,
    }

    write_json(root / "data" / "phase4_proposals" / "aigc_phase4_proposal_packages.json", [proposal])
    write_json(root / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json", [authorization])
    write_json(root / "data" / "phase15_finance" / "aigc_phase15_finance_ledger.json", [finance])
    write_json(root / "data" / "phase16_compliance" / "aigc_phase16_compliance_reviews.json", [compliance])
    write_json(root / "data" / "phase20_fidelity" / "aigc_phase20_fidelity_reviews.json", [fidelity])
    write_json(
        root / "data" / "phase21_customer_satisfaction" / "aigc_phase21_customer_satisfaction_records.json",
        [customer],
    )
    write_json(
        root / "config" / "phase22_quantum_quality_kernel.json",
        {
            "input_files": {
                "proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
                "authorizations": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
                "finance_records": "data/phase15_finance/aigc_phase15_finance_ledger.json",
                "compliance_reviews": "data/phase16_compliance/aigc_phase16_compliance_reviews.json",
                "fidelity_reviews": "data/phase20_fidelity/aigc_phase20_fidelity_reviews.json",
                "customer_satisfaction_records": "data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json",
            },
            "output_file": "data/phase22_quality/aigc_phase22_quality_kernel_records.json",
            "report_file": "data/reports/phase22_signature_update.md",
            "audit_log": "data/audit/aigc_phase22_audit.jsonl",
            "max_records": 5,
            "ologys": [
                "ontology",
                "epistemology",
                "methodology",
                "praxeology",
                "axiology",
                "teleology",
                "semiotics",
                "cybernetics",
                "systems_theory",
                "ethics",
                "jurisprudence",
                "risk_theory",
            ],
            "agent_panel": [
                "Meta-Cognition Agent",
                "Technical-Fidelity Agent",
                "Ethics-Compliance Agent",
                "Risk Mitigation Agent",
            ],
            "score_thresholds": {
                "ascended_ready": 90,
                "high_quality_review": 80,
                "improvement_required": 65,
            },
            "best_practice_standards": ["contract_first_artifacts", "auditability"],
            "forbidden_behaviors": ["claim_literal_quantum_cognition", "bypass_phase5_approval"],
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
