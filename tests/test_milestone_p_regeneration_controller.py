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


REQUIRED_PHRASE = "I, Justice Gray Maciocha, approve Phase 28 freshness-reviewed internal regeneration."


def test_phase28_blocks_without_operator_freshness_review(tmp_path: Path) -> None:
    create_phase28_fixture(tmp_path, approved=False)
    records = FreshCandidateRegenerationController(tmp_path).run_from_config(
        tmp_path / "config" / "phase28_regeneration_controller.json"
    )
    payload = asdict(records[0])

    validate_artifact("regeneration_candidate_record", payload)
    assert payload["regeneration_allowed"] is False
    assert payload["fresh_phase4_candidate"] is None
    assert payload["fresh_phase5_candidate"] is None
    assert "approved_flag" in payload["blocker_reasons"]
    assert payload["external_action_performed"] is False
    assert payload["canonical_phase4_overwrite_performed"] is False
    assert payload["canonical_phase5_overwrite_performed"] is False


def test_phase28_creates_internal_candidates_after_exact_freshness_review(tmp_path: Path) -> None:
    create_phase28_fixture(tmp_path, approved=True)
    records = FreshCandidateRegenerationController(tmp_path).run_from_config(
        tmp_path / "config" / "phase28_regeneration_controller.json"
    )
    payload = asdict(records[0])

    validate_artifact("regeneration_candidate_record", payload)
    validate_artifact("proposal_package", payload["fresh_phase4_candidate"])
    validate_artifact("authorization_packet", payload["fresh_phase5_candidate"])
    assert payload["regeneration_allowed"] is True
    assert payload["blocker_reasons"] == []
    assert payload["fresh_phase5_candidate"]["decision"] == "pending"
    assert payload["fresh_phase5_candidate"]["phase6_status"]["authorized_for_phase6"] is False
    assert payload["fresh_phase5_candidate"]["phase6_status"]["external_action_performed"] is False
    assert payload["audit_lineage"]["old_artifacts_are_historical_derivatives"] is True
    assert payload["external_action_performed"] is False


def test_cli_run_phase28_exports_blocked_regeneration_records(tmp_path: Path) -> None:
    create_phase28_fixture(tmp_path, approved=False)
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase28",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase28_regeneration" / "aigc_phase28_regeneration_candidates.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("regeneration_candidate_record", payload[0])
    assert payload[0]["regeneration_allowed"] is False
    assert payload[0]["fresh_phase4_candidate"] is None
    assert payload[0]["fresh_phase5_candidate"] is None


def test_phase_registry_includes_phase28_regeneration_controller() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase28"].schema_name == "regeneration_candidate_record"
    assert registry["phase28"].external_action_risk == "none_internal_candidate_regeneration_only"


def create_phase28_fixture(root: Path, approved: bool) -> None:
    for path in [
        root / "config",
        root / "data" / "phase27_renewal",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    write_json(
        root / "data" / "phase27_renewal" / "aigc_phase27_stale_artifact_renewal_records.json",
        [{
            "record_id": "AIGC-REN-TEST",
            "created_at": "2026-07-02T00:00:00+00:00",
            "phase": "phase27_stale_artifact_renewal_controller",
            "status": "renewal_blueprint_recorded",
            "source_procurement_record_id": "AIGC-PROC-TEST",
            "opportunity_id": "opp_regen",
            "proposal_id": "phase4_old_regen",
            "authorization_id": "AIGC-AUTH-OLD",
            "action_id": "AIGC-ACT-OLD",
            "title": "Regeneration test candidate",
            "employer": "Example",
            "source_platform": "GitHub",
            "source_url": "https://example.invalid/regen",
            "source_truth_status": "real_read_only_source_snapshot_present",
            "stale_artifact_classification": "real_source_with_expired_generated_action_candidate",
            "renewal_strategy": "preserve_historical_derivative_and_regenerate_from_fresh_source_context",
            "preserved_artifact_chain": [
                {
                    "phase": "phase4_proposal_drafting",
                    "artifact_id": "phase4_old_regen",
                    "path": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
                    "truth_role": "generated_internal_derivative",
                    "status": "internal_draft_only",
                },
                {
                    "phase": "phase5_human_approval_gate",
                    "artifact_id": "AIGC-AUTH-OLD",
                    "path": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
                    "truth_role": "generated_internal_derivative",
                    "status": "expired_pending_generated_derivative",
                },
            ],
            "deep_research_brief": {
                "research_questions": [
                    "Is the source opportunity still current?",
                    "What acceptance criteria are explicit or missing?",
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
        root / "config" / "phase28_regeneration_controller.json",
        {
            "output_file": "data/phase28_regeneration/aigc_phase28_regeneration_candidates.json",
            "report_file": "data/reports/phase28_signature_update.md",
            "audit_log": "data/audit/aigc_phase28_audit.jsonl",
            "max_records": 25,
            "approval_expiration_hours": 24,
            "input_files": {
                "phase27_renewal_records": "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json",
            },
            "operator_freshness_review": {
                "approved": approved,
                "review_id": "freshness-review-1" if approved else "",
                "reviewed_at": "2026-07-02T01:00:00+00:00" if approved else "",
                "freshness_review_status": "approved_for_internal_regeneration" if approved else "not_reviewed",
                "reviewed_source_currentness": approved,
                "reviewed_scope": approved,
                "reviewed_compliance": approved,
                "reviewed_quality_plan": approved,
                "reviewed_payment_contract": approved,
                "allowed_output_mode": "internal_candidate_only",
                "required_phrase": REQUIRED_PHRASE,
                "received_phrase": REQUIRED_PHRASE if approved else "",
            },
            "candidate_defaults": {
                "operator": "Justice Gray Maciocha",
                "proposal_status": "internal_regenerated_candidate_only",
                "proposal_readiness_decision": "ready_for_phase_5",
                "phase5_decision": "pending",
                "minimum_quality_score": 88,
                "uncertainty_score": 22,
            },
            "blocked_actions": [
                "regenerate_without_operator_freshness_review",
                "overwrite_canonical_phase4_artifacts",
                "overwrite_canonical_phase5_artifacts",
                "authorize_phase6",
                "contact_external_party",
                "submit_proposal",
            ],
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
