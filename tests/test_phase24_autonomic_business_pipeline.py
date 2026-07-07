from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.phase24_autonomic_business_pipeline import (
    AutonomicBusinessPipeline,
    blocked_reasons,
    business_agents,
    business_pipeline,
    neural_microcycle,
    status_from,
)


def packet(decision: str = "pending", approved: bool = False, authorized: bool = False) -> dict:
    return {
        "authorization_id": "AUTH-1",
        "action_id": "AIGC-ACT-1",
        "proposal_id": "PROPOSAL-1",
        "opportunity_id": "OPPORTUNITY-1",
        "recipient": "Example",
        "platform": "Example Platform",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "proposed_external_action": "Prepare governed business handoff.",
        "approval": {"approved": approved},
        "phase6_status": {"authorized_for_phase6": authorized, "external_action_performed": False},
        "artifact": {"artifact_hash": "abc"},
        "decision": decision,
    }


def test_business_pipeline_contains_full_user_lifecycle() -> None:
    stages = [item["stage"] for item in business_pipeline("Example Work")]

    assert stages == [
        "find_work",
        "ingest_job",
        "research_job",
        "find_best_practices",
        "deep_dive_into_work",
        "instantiate_learning_measures",
        "design_appropriate_agents",
        "use_agents",
        "governed_handoff",
        "evolve_structure",
    ]


def test_neural_microcycle_has_functional_gates() -> None:
    cycle = neural_microcycle("AIGC-ACT-1", "Example Work", ["review required"])

    assert "sensory_intake" in cycle
    assert "attention" in cycle
    assert "working_memory" in cycle
    assert "motor_gate" in cycle
    assert cycle["working_memory"]["blocked_reason_count"] == 1


def test_business_agents_are_internal_and_governed() -> None:
    agents = business_agents("Example Work", "ready")

    assert len(agents) >= 8
    assert all(agent["governance_required"] for agent in agents)
    assert all(agent["external_action_allowed"] is False for agent in agents)


def test_pending_packet_waits_for_review() -> None:
    item = packet()
    reasons = blocked_reasons(item, expired=False, quality_state="ready")

    assert "Phase 5 decision is not approved_for_phase_6." in reasons
    assert status_from(item["decision"], expired=False, blocked=reasons) == "waiting_for_human_review"


def test_approved_packet_can_reach_handoff_readiness_without_outward_action(tmp_path) -> None:
    pipeline = AutonomicBusinessPipeline(project_root=tmp_path)
    config = {"business_ologies": ["strategy"], "blocked_behaviors": []}
    item = packet(decision="approved_for_phase_6", approved=True, authorized=True)
    record = pipeline.build_record(config, item, {"title": "Example Work", "ascended_output_v2": {"quality_state": "ready"}})

    assert record.status == "approved_for_handoff_readiness"
    assert record.external_action_performed is False
    assert record.governed_next_action.startswith("Create Phase 6 manual handoff")
