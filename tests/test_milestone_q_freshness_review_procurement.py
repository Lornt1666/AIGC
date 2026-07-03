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
from src.phase28_regeneration_controller import FreshCandidateRegenerationController
from src.phase29_freshness_review_procurement import OperatorFreshnessReviewProcurement


def test_phase29_procures_pending_freshness_review_records(tmp_path: Path) -> None:
    create_phase29_fixture(tmp_path)
    records = OperatorFreshnessReviewProcurement(tmp_path).run_from_config(
        tmp_path / "config" / "phase29_freshness_review_procurement.json"
    )
    payload = asdict(records[0])

    validate_artifact("freshness_review_record", payload)
    assert payload["decision"] == "pending"
    assert payload["operator_review"]["approved"] is False
    assert payload["operator_review"]["required_phrase"].startswith(
        "I, Justice Gray Maciocha, approve freshness review AIGC-FRESH-"
    )
    assert payload["phase28_gate_projection"]["phase28_regeneration_allowed"] is False
    assert payload["external_action_performed"] is False


def test_cli_approve_freshness_review_updates_record(tmp_path: Path) -> None:
    create_phase29_fixture(tmp_path)
    OperatorFreshnessReviewProcurement(tmp_path).run_from_config(
        tmp_path / "config" / "phase29_freshness_review_procurement.json"
    )
    review_path = tmp_path / "data" / "phase29_freshness_reviews" / "aigc_phase29_freshness_review_records.json"
    records = json.loads(review_path.read_text(encoding="utf-8"))
    review_id = records[0]["record_id"]
    phrase = records[0]["operator_review"]["required_phrase"]

    result = subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "approve-freshness-review",
            "--review-id",
            review_id,
            "--phrase",
            phrase,
            "--reviews-path",
            str(review_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output = json.loads(result.stdout)
    updated = json.loads(review_path.read_text(encoding="utf-8"))[0]
    assert output["decision"] == "approved_for_phase28_regeneration"
    assert output["phase28_regeneration_allowed"] is True
    assert updated["operator_review"]["approved"] is True
    assert all(updated["required_review_controls"].values())
    assert updated["external_action_performed"] is False


def test_phase28_consumes_approved_phase29_review_record(tmp_path: Path) -> None:
    create_phase29_fixture(tmp_path)
    OperatorFreshnessReviewProcurement(tmp_path).run_from_config(
        tmp_path / "config" / "phase29_freshness_review_procurement.json"
    )
    review_path = tmp_path / "data" / "phase29_freshness_reviews" / "aigc_phase29_freshness_review_records.json"
    records = json.loads(review_path.read_text(encoding="utf-8"))
    review_id = records[0]["record_id"]
    phrase = records[0]["operator_review"]["required_phrase"]
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "approve-freshness-review",
            "--review-id",
            review_id,
            "--phrase",
            phrase,
            "--reviews-path",
            str(review_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    regeneration_records = FreshCandidateRegenerationController(tmp_path).run_from_config(
        tmp_path / "config" / "phase28_regeneration_controller.json"
    )
    payload = asdict(regeneration_records[0])
    validate_artifact("regeneration_candidate_record", payload)
    validate_artifact("proposal_package", payload["fresh_phase4_candidate"])
    validate_artifact("authorization_packet", payload["fresh_phase5_candidate"])
    assert payload["regeneration_allowed"] is True
    assert payload["freshness_review_gate"]["review_source"] == "phase29_freshness_review_record"
    assert payload["fresh_phase5_candidate"]["decision"] == "pending"
    assert payload["fresh_phase5_candidate"]["phase6_status"]["authorized_for_phase6"] is False
    assert payload["external_action_performed"] is False


def test_phase_registry_includes_phase29_freshness_review_procurement() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase29"].schema_name == "freshness_review_record"
    assert registry["phase29"].external_action_risk == "none_internal_freshness_review_only"


def create_phase29_fixture(root: Path) -> None:
    for path in [
        root / "config",
        root / "data" / "phase25_intelligence",
        root / "data" / "phase26_capability_procurement",
        root / "data" / "phase27_renewal",
        root / "data" / "phase28_regeneration",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    write_json(
        root / "data" / "phase27_renewal" / "aigc_phase27_stale_artifact_renewal_records.json",
        [{
            "record_id": "AIGC-REN-QTEST",
            "created_at": "2026-07-02T00:00:00+00:00",
            "phase": "phase27_stale_artifact_renewal_controller",
            "status": "renewal_blueprint_recorded",
            "source_procurement_record_id": "AIGC-PROC-QTEST",
            "opportunity_id": "opp_qtest",
            "proposal_id": "phase4_old_qtest",
            "authorization_id": "AIGC-AUTH-QOLD",
            "action_id": "AIGC-ACT-QOLD",
            "title": "Freshness review test candidate",
            "employer": "Example",
            "source_platform": "GitHub",
            "source_url": "https://example.invalid/qtest",
            "source_truth_status": "real_read_only_source_snapshot_present",
            "stale_artifact_classification": "real_source_with_expired_generated_action_candidate",
            "renewal_strategy": "preserve_historical_derivative_and_regenerate_from_fresh_source_context",
            "preserved_artifact_chain": [],
            "deep_research_brief": {
                "research_questions": [
                    "Is the source opportunity still current?",
                    "What technical acceptance criteria are explicit or missing?",
                ]
            },
            "architecture_evolution_plan": {},
            "regeneration_blueprint": {
                "regeneration_allowed_now": False,
                "would_create_new_authorization_candidate": True,
            },
            "quality_upgrade_targets": {
                "minimum_quality_score": 85,
                "maximum_uncertainty_score": 35,
            },
            "freshness_requirements": {
                "fresh_source_required": True,
            },
            "approval_gate": {
                "old_action_id_approval_allowed": False,
                "external_action_authorized": False,
            },
            "blocked_actions": [],
            "deletion_performed": False,
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "data" / "phase25_intelligence" / "aigc_phase25_intelligence_ingestion_records.json",
        [{
            "record_id": "ciil_qtest",
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
            "record_id": "cap_qtest",
            "gap_analysis": ["test: expired generated action candidates exceed threshold 0."],
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "data" / "phase28_regeneration" / "aigc_phase28_regeneration_candidates.json",
        [{
            "record_id": "regen_qtest",
            "source_phase27_record_id": "AIGC-REN-QTEST",
            "regeneration_allowed": False,
            "external_action_performed": False,
        }],
    )
    write_json(
        root / "config" / "phase29_freshness_review_procurement.json",
        {
            "output_file": "data/phase29_freshness_reviews/aigc_phase29_freshness_review_records.json",
            "report_file": "data/reports/phase29_signature_update.md",
            "audit_log": "data/audit/aigc_phase29_audit.jsonl",
            "max_records": 25,
            "review_expiration_hours": 24,
            "operator": "Justice Gray Maciocha",
            "input_files": {
                "phase27_renewal_records": "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json",
                "phase25_intelligence_ingestion": "data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json",
                "phase26_capability_procurement": "data/phase26_capability_procurement/aigc_phase26_capability_procurement_records.json",
                "phase28_regeneration_candidates": "data/phase28_regeneration/aigc_phase28_regeneration_candidates.json",
            },
            "required_review_controls": [
                "source_currentness_reviewed",
                "scope_reviewed",
                "compliance_reviewed",
                "quality_plan_reviewed",
                "payment_contract_reviewed",
                "old_action_id_confirmed_inactive",
                "phase28_internal_candidate_only_confirmed",
            ],
            "blocked_actions": ["authorize_phase6", "contact_external_party", "submit_proposal"],
        },
    )
    write_json(
        root / "config" / "phase28_regeneration_controller.json",
        {
            "output_file": "data/phase28_regeneration/aigc_phase28_regeneration_candidates.json",
            "report_file": "data/reports/phase28_signature_update.md",
            "audit_log": "data/audit/aigc_phase28_audit.jsonl",
            "max_records": 25,
            "approval_expiration_hours": 24,
            "input_files": {
                "phase27_renewal_records": "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json",
                "freshness_review_records": "data/phase29_freshness_reviews/aigc_phase29_freshness_review_records.json",
            },
            "operator_freshness_review": {
                "approved": False,
                "freshness_review_status": "not_reviewed",
                "allowed_output_mode": "internal_candidate_only",
                "required_phrase": "I, Justice Gray Maciocha, approve Phase 28 freshness-reviewed internal regeneration.",
                "received_phrase": "",
            },
            "candidate_defaults": {
                "operator": "Justice Gray Maciocha",
                "proposal_status": "internal_regenerated_candidate_only",
                "proposal_readiness_decision": "ready_for_phase_5",
                "phase5_decision": "pending",
                "minimum_quality_score": 88,
                "uncertainty_score": 22,
            },
            "blocked_actions": ["authorize_phase6", "contact_external_party", "submit_proposal"],
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
