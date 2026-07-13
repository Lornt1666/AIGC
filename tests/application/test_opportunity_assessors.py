from __future__ import annotations

from src.application import OpportunityAssessmentPipeline
from src.phase2_radar import OpportunityRecord


def record(
    *,
    title: str,
    description: str,
    opportunity_id: str = "assessment-example-001",
    work_type: str = "contract",
) -> OpportunityRecord:
    return OpportunityRecord(
        opportunity_id=opportunity_id,
        source_platform="Assessment Fixture",
        source_type="api",
        source_url=f"https://example.com/{opportunity_id}",
        source_attribution_required=True,
        discovered_at="2026-07-13T18:00:00+00:00",
        title=title,
        employer="Example Company",
        remote_status="remote",
        work_type=work_type,
        description_plain=description,
        platform_policy_status="green",
    )


def assess(title: str, description: str, **kwargs: str) -> dict:
    _, packet = OpportunityAssessmentPipeline().assess(
        record(title=title, description=description, **kwargs)
    )
    return packet


def test_ology_assessor_identifies_frontend_domain_and_skills() -> None:
    packet = assess(
        "React TypeScript frontend developer",
        "Build a responsive Tailwind CSS interface with React and TypeScript.",
    )

    assert packet["ology"]["primary_domain"] == "frontend_development"
    assert {"react", "typescript", "tailwind", "css"}.issubset(
        set(packet["ology"]["required_skills"])
    )


def test_ology_assessor_identifies_backend_domain() -> None:
    packet = assess(
        "FastAPI Python backend engineer",
        "Build a Python FastAPI service backed by PostgreSQL.",
    )

    assert packet["ology"]["primary_domain"] == "backend_development"
    assert {"python", "fastapi", "postgresql"}.issubset(
        set(packet["ology"]["required_skills"])
    )


def test_ology_assessor_identifies_full_stack_domain() -> None:
    packet = assess(
        "Full-stack React and FastAPI developer",
        "Build React TypeScript screens and a Python FastAPI backend.",
    )

    assert packet["ology"]["primary_domain"] == "full_stack_development"


def test_ology_assessor_identifies_machine_learning_domain() -> None:
    packet = assess(
        "Machine learning engineer",
        "Develop a PyTorch LLM evaluation workflow and model tests.",
    )

    assert packet["ology"]["primary_domain"] == "machine_learning"
    assert {"machine learning", "pytorch", "llm"}.issubset(
        set(packet["ology"]["required_skills"])
    )


def test_risk_scout_treats_seniority_as_caution_not_severe_risk() -> None:
    packet = assess(
        "Senior Python automation engineer",
        "Build a Python automation workflow with tests and documentation.",
        work_type="job",
    )

    assert packet["risk"]["risk_class"] == "medium"
    assert "senior_full_time_role" in packet["risk"]["risk_flags"]
    assert packet["risk"]["operator_review_required"] is True


def test_risk_scout_marks_privacy_or_security_sensitive_work_high() -> None:
    packet = assess(
        "Security data engineer",
        "Process patient data and HIPAA records using private credentials.",
    )

    assert packet["risk"]["risk_class"] == "high"
    assert "privacy_or_security_sensitive" in packet["risk"]["risk_flags"]
    assert packet["risk"]["qualification_recommended"] is False


def test_risk_scout_marks_forbidden_work_restricted() -> None:
    packet = assess(
        "Mass DM captcha bypass automation",
        "Spam accounts, mass message users, and bypass captcha limits.",
    )

    assert packet["risk"]["risk_class"] == "restricted"
    assert packet["risk"]["forbidden_flags"]
    assert packet["risk"]["radar_decision"] == "reject"
    assert packet["risk"]["qualification_recommended"] is False


def test_assessment_packet_is_stable_for_identical_evidence() -> None:
    pipeline = OpportunityAssessmentPipeline()
    source = record(
        title="Python API documentation engineer",
        description="Build Python OpenAPI documentation and automated tests.",
    )

    _, first = pipeline.assess(source)
    _, second = pipeline.assess(source)

    assert first == second
    assert len(first["basis_digest"]) == 64
    assert first["external_action_performed"] is False
