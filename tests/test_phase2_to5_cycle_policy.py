from __future__ import annotations

from pathlib import Path

import pytest

from src.core.aigc_master_curriculum import (
    load_aigc_master_curriculum,
    summarize_aigc_master_curriculum,
)
from src.core.phase2_to5_cycle_policy import (
    AUTHORIZATION_ENV,
    REVIEW_ONLY_ENV,
    Phase2To5CyclePolicyError,
    active_hold_directive,
    authorized_native_cycle_provenance,
    load_phase2_to5_cycle_policy,
    packet_was_generated_by_authorized_native_cycle,
    require_phase2_to5_generation_authorized,
)


ROOT = Path(__file__).resolve().parents[1]


def test_active_cycle_policy_blocks_direct_phase2_to5_generation() -> None:
    policy = load_phase2_to5_cycle_policy(ROOT)

    assert policy["active_hold"]["enabled"] is True
    assert policy["active_hold"]["automatic_regeneration_allowed"] is False
    assert policy["active_hold"]["maximum_scoped_internal_improvement_proposals"] == 1
    assert policy["phase6"]["execution_mode"] == "manual_handoff"
    assert policy["connector_and_production_boundary"]["connectors_enabled"] is False
    assert policy["connector_and_production_boundary"]["production_deployment_authorized"] is False

    with pytest.raises(Phase2To5CyclePolicyError, match="read-only Phase 4/5 hold"):
        require_phase2_to5_generation_authorized(ROOT, "Phase 4", environ={})


def test_missing_cycle_policy_fails_closed_for_generation(tmp_path: Path) -> None:
    with pytest.raises(Phase2To5CyclePolicyError, match="cycle policy is missing"):
        require_phase2_to5_generation_authorized(tmp_path, "Phase 2", environ={})


def test_native_review_context_is_the_only_generation_exception() -> None:
    policy = load_phase2_to5_cycle_policy(ROOT)
    environment = {
        AUTHORIZATION_ENV: policy["authorized_native_cycle"]["operator_authorization_phrase"],
        REVIEW_ONLY_ENV: "true",
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ID": "12345",
        "GITHUB_WORKFLOW_REF": (
            "Lornt1666/AIGC/.github/workflows/aigc_phase2_to5_review.yml"
            "@refs/heads/main"
        ),
    }

    require_phase2_to5_generation_authorized(ROOT, "Phase 5", environ=environment)
    provenance = authorized_native_cycle_provenance(policy, environment)
    assert packet_was_generated_by_authorized_native_cycle(
        policy,
        {"generation_provenance": provenance},
    )
    assert active_hold_directive(policy)["packet_regeneration_allowed"] is False
    assert policy["scoped_internal_improvement_proposal"]["apply_authorized"] is False


def test_master_curriculum_is_complete_and_governance_bound() -> None:
    curriculum = load_aigc_master_curriculum(ROOT)
    summary = summarize_aigc_master_curriculum(curriculum)

    assert summary["operating_mode"] == "internal_reference_only"
    assert summary["class_count"] == 15
    assert {item["class_id"] for item in curriculum["classes"]} == set(range(1, 16))
    assert curriculum["governance_boundary"]["external_actions_authorized"] is False
    assert curriculum["governance_boundary"]["production_activation_authorized"] is False
    assert curriculum["governance_boundary"]["phase5_approval_required"] is True
    assert curriculum["governance_boundary"]["phase6_manual_handoff_only"] is True


def test_authorized_phase2_to5_workflow_is_manual_read_only_and_receipted() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "aigc_phase2_to5_review.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "\n  push:" not in workflow
    assert "\n  pull_request:" not in workflow
    assert "AUTHORIZE AIGC PHASE 2 TO 5 REVIEW CYCLE" in workflow
    assert "inputs.review_only == true" in workflow
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "AIGC_PHASE2_TO5_OPERATOR_AUTHORIZATION" in workflow
    assert "python src/phase2_radar.py" in workflow
    assert "python src/phase3_ology_assessment.py" in workflow
    assert "python src/phase4_proposal_drafting.py" in workflow
    assert "python src/phase5_human_approval_gate.py" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    assert "external_action_performed" in workflow
    assert "secrets." not in workflow
