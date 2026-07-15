from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.job_interview_cockpit import (
    BLOCKED_ACTIONS,
    load_job_packets,
    load_radar_opportunities,
    prepare_job_packet,
    prepare_job_packet_from_opportunity,
    record_interview_invitation,
    record_job_decision,
)


def test_job_packet_is_truthful_internal_and_manual_only(tmp_path: Path) -> None:
    packet = prepare_job_packet(
        source_url="https://example.com/jobs/architectural-technologist",
        role_title="Architectural Technologist",
        organization="Example Studio",
        posting_summary="Prepare drawings and coordinate design documentation.",
        truthful_qualifications="Carpentry and framing experience; AutoCAD familiarity; architectural technology studies.",
        application_draft="",
        interview_notes="",
        root=tmp_path,
    )

    assert packet["decision"] == "PENDING_REVIEW"
    assert packet["operator_must_submit_on_official_platform"] is True
    assert packet["operator_must_send_messages_manually"] is True
    assert packet["operator_must_schedule_interview_manually"] is True
    assert packet["external_action_performed"] is False
    assert set(BLOCKED_ACTIONS) <= set(packet["blocked_actions"])
    assert "Architectural Technologist" in packet["application_draft"]
    assert "invent" not in packet["application_draft"].lower()


def test_radar_queue_imports_only_reviewable_jobs(tmp_path: Path) -> None:
    queue = tmp_path / "data" / "phase2_processed" / "aigc_phase2_opportunity_queue.json"
    queue.parent.mkdir(parents=True)
    queue.write_text(
        json.dumps(
            [
                {
                    "opportunity_id": "opp-high",
                    "source_platform": "Remotive",
                    "source_type": "api",
                    "source_url": "https://example.com/jobs/high",
                    "source_attribution_required": True,
                    "title": "Documentation Specialist",
                    "employer": "Example Employer",
                    "description_plain": "Prepare technical documentation and review workflows.",
                    "work_type": "job",
                    "radar_score": 88,
                    "radar_decision": "queue_for_phase_3",
                    "risk_flags": ["unclear_pay"],
                    "forbidden_flags": [],
                    "platform_policy_status": "green",
                    "approval_required_before": ["apply", "message_employer"],
                },
                {
                    "opportunity_id": "opp-reject",
                    "source_platform": "Example",
                    "source_type": "api",
                    "source_url": "https://example.com/jobs/reject",
                    "title": "Rejected Role",
                    "employer": "Example",
                    "description_plain": "Rejected.",
                    "work_type": "job",
                    "radar_score": 10,
                    "radar_decision": "reject",
                },
                {
                    "opportunity_id": "opp-open-source",
                    "source_platform": "GitHub",
                    "source_type": "api",
                    "source_url": "https://github.com/example/repo/issues/1",
                    "title": "Open source issue",
                    "employer": "repo",
                    "description_plain": "Issue.",
                    "work_type": "open_source",
                    "radar_score": 90,
                    "radar_decision": "queue_for_phase_3",
                },
            ]
        ),
        encoding="utf-8",
    )

    opportunities = load_radar_opportunities(tmp_path)
    assert [item["opportunity_id"] for item in opportunities] == ["opp-high"]

    packet = prepare_job_packet_from_opportunity(
        "opp-high",
        truthful_qualifications="Verified technical writing and workflow documentation experience.",
        root=tmp_path,
    )
    assert packet["source_metadata"]["radar_score"] == 88
    assert packet["source_metadata"]["risk_flags"] == ["unclear_pay"]
    assert packet["operator_must_submit_on_official_platform"] is True
    assert packet["external_action_performed"] is False


def test_job_acceptance_requires_exact_phrase_and_remains_internal(tmp_path: Path) -> None:
    packet = prepare_job_packet(
        source_url="https://example.com/jobs/aigc-operator",
        role_title="AI Operations Assistant",
        organization="Example Employer",
        posting_summary="Review evidence and prepare operator-visible work packets.",
        truthful_qualifications="Governed workflow design and evidence-backed review experience.",
        application_draft="Truthful draft.",
        interview_notes="Truthful notes.",
        root=tmp_path,
    )

    with pytest.raises(ValueError):
        record_job_decision(
            packet["packet_id"],
            decision="ACCEPT_FOR_MANUAL_SUBMISSION",
            phrase="accept",
            root=tmp_path,
        )

    accepted = record_job_decision(
        packet["packet_id"],
        decision="ACCEPT_FOR_MANUAL_SUBMISSION",
        phrase=packet["required_accept_phrase"],
        root=tmp_path,
    )
    assert accepted["decision"] == "APPROVED_FOR_MANUAL_OPERATOR_SUBMISSION"
    assert accepted["external_action_performed"] is False


def test_interview_invitation_is_recorded_without_reply_or_scheduling(tmp_path: Path) -> None:
    packet = prepare_job_packet(
        source_url="https://example.com/jobs/interview-test",
        role_title="Project Coordinator",
        organization="Example Builder",
        posting_summary="Coordinate project schedules and documentation.",
        truthful_qualifications="Construction workflow and documentation experience.",
        application_draft="Draft.",
        interview_notes="Notes.",
        root=tmp_path,
    )
    updated = record_interview_invitation(
        packet["packet_id"],
        invitation_notes="Invitation received; operator will reply manually.",
        root=tmp_path,
    )

    assert updated["interview_state"] == "INVITATION_RECORDED_INTERNAL_ONLY"
    assert updated["operator_must_schedule_interview_manually"] is True
    assert updated["external_action_performed"] is False
    assert len(load_job_packets(tmp_path)) == 1
