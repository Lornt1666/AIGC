from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from src.api.composition import build_container
from src.application import AgentRegistryError, QuestConductor
from src.domain.quests import QuestStateError
from src.infrastructure.persistence.sqlite import (
    SQLiteAgentHandoffRepository,
    SQLiteAuditEventRepository,
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteQuestRepository,
    SQLiteRecordRepository,
    SQLiteReviewEvidencePacketRepository,
)


ROOT = Path(__file__).resolve().parents[2]
QUEST_ID = "quest_conductor_example_001"


def validator(name: str) -> Draft202012Validator:
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def service(tmp_path: Path, state: str = "WORK_ACCEPTED") -> QuestConductor:
    factory = SQLiteConnectionFactory(tmp_path / "operator.sqlite3")
    SQLiteMigrator(factory, ROOT / "migrations" / "sqlite").apply_all()
    SQLiteRecordRepository(factory, "quests").put(
        QUEST_ID,
        {"quest_id": QUEST_ID, "lifecycle_state": state, "external_action_performed": False},
        expected_revision=0,
    )
    return QuestConductor(
        SQLiteQuestRepository(factory),
        SQLiteAgentHandoffRepository(factory),
        SQLiteReviewEvidencePacketRepository(factory),
        SQLiteAuditEventRepository(factory),
        registry_path=ROOT / "config" / "agent_registry_v1.json",
        registry_schema_path=ROOT / "schemas" / "agent_registry.schema.json",
        handoff_schema_path=ROOT / "schemas" / "agent_handoff.schema.json",
        review_schema_path=ROOT / "schemas" / "review_evidence_packet.schema.json",
        exact_revision="TEST-REVISION",
    )


def handoff_example() -> dict:
    return {
        "handoff_id": "handoff_" + "a" * 24,
        "schema_version": "1.0.0",
        "evidence_subject": "INTERNAL_QUEST_HANDOFF",
        "quest_id": "quest_example_001",
        "quest_revision": 3,
        "sequence": 1,
        "from_agent_id": "AIGC-AGENT-OMEGA-X",
        "to_agent_id": "AIGC-AGENT-TASK-ARCHITECT",
        "source_handoff_id": None,
        "status": "PLANNED",
        "purpose": "Create a bounded task architecture.",
        "input_artifact_ids": ["quest:quest_example_001:revision:3"],
        "input_artifact_types": ["quest"],
        "expected_output_artifact_type": "task_architecture_brief",
        "acceptance_criteria": ["scope_is_bounded"],
        "required_approval_gates": ["accountable_operator_work_acceptance"],
        "handoff_digest": "b" * 64,
        "created_at": "2026-07-13T22:15:00+00:00",
        "completed_at": None,
        "review_packet_ids": [],
        "last_review_verdict": None,
        "exact_revision": "TEST-REVISION",
        "authority_class": "ACCOUNTABLE_OPERATOR",
        "operator_review_required": True,
        "external_action_performed": False,
    }


def review_example() -> dict:
    return {
        "packet_id": "review_" + "c" * 24,
        "schema_version": "1.0.0",
        "evidence_subject": "INTERNAL_HANDOFF_REVIEW",
        "quest_id": "quest_example_001",
        "quest_revision": 3,
        "handoff_id": "handoff_" + "a" * 24,
        "handoff_revision": 1,
        "reviewer_agent_id": "AIGC-AGENT-QUALITY-SENTINEL",
        "subject_agent_id": "AIGC-AGENT-TASK-ARCHITECT",
        "verdict": "PASS",
        "findings": [],
        "acceptance_criteria_results": [
            {"criterion": "scope_is_bounded", "status": "PASS", "evidence_ids": ["artifact:1"]}
        ],
        "evidence_ids": ["artifact:1"],
        "packet_digest": "e" * 64,
        "created_at": "2026-07-13T22:20:00+00:00",
        "exact_revision": "TEST-REVISION",
        "authority_class": "ACCOUNTABLE_OPERATOR",
        "operator_review_required": True,
        "external_action_performed": False,
    }


def test_contracts_and_registry_are_strict_internal_only() -> None:
    registry = json.loads((ROOT / "config" / "agent_registry_v1.json").read_text(encoding="utf-8"))
    validator("agent_registry.schema.json").validate(registry)
    ids = {item["agent_id"] for item in registry["agents"]}
    assert registry["conductor_agent_id"] in ids
    assert set(registry["default_handoff_sequence"]) < ids
    assert all(set(item["handoff_targets"]) <= ids for item in registry["agents"])
    assert all(item["external_action_allowed"] is False for item in registry["agents"])

    handoff = handoff_example()
    handoff_validator = validator("agent_handoff.schema.json")
    handoff_validator.validate(handoff)
    handoff["external_action_performed"] = True
    assert list(handoff_validator.iter_errors(handoff))

    review = review_example()
    review_validator = validator("review_evidence_packet.schema.json")
    review_validator.validate(review)
    review["acceptance_criteria_results"] = []
    assert list(review_validator.iter_errors(review))


def test_conductor_persists_idempotent_handoffs_and_review(tmp_path: Path) -> None:
    conductor = service(tmp_path)
    planned = conductor.plan_handoffs(
        QUEST_ID, expected_quest_revision=1, operator_role="ACCOUNTABLE_OPERATOR"
    )
    assert len(planned) == 8
    assert planned[0].payload["from_agent_id"] == "AIGC-AGENT-OMEGA-X"
    assert all(item.revision == 1 and item.payload["external_action_performed"] is False for item in planned)
    replay = conductor.plan_handoffs(
        QUEST_ID, expected_quest_revision=1, operator_role="ACCOUNTABLE_OPERATOR"
    )
    assert [item.record_id for item in replay] == [item.record_id for item in planned]

    criteria = [
        {"criterion": value, "status": "PASS", "evidence_ids": ["artifact:task"]}
        for value in planned[0].payload["acceptance_criteria"]
    ]
    reviewed = conductor.record_review_evidence(
        planned[0].record_id,
        expected_handoff_revision=1,
        reviewer_agent_id="AIGC-AGENT-QUALITY-SENTINEL",
        verdict="PASS",
        findings=[],
        acceptance_criteria_results=criteria,
        evidence_ids=["artifact:task"],
        operator_role="ACCOUNTABLE_OPERATOR",
    )
    assert reviewed.handoff.revision == 2
    assert reviewed.handoff.payload["status"] == "COMPLETED"
    assert reviewed.packet.payload["external_action_performed"] is False
    replayed = conductor.record_review_evidence(
        planned[0].record_id,
        expected_handoff_revision=1,
        reviewer_agent_id="AIGC-AGENT-QUALITY-SENTINEL",
        verdict="PASS",
        findings=[],
        acceptance_criteria_results=criteria,
        evidence_ids=["artifact:task"],
        operator_role="ACCOUNTABLE_OPERATOR",
    )
    assert replayed.handoff.revision == 2
    assert replayed.packet.record_id == reviewed.packet.record_id


def test_conductor_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(QuestStateError):
        service(tmp_path / "proposed", "PROPOSED").plan_handoffs(
            QUEST_ID, expected_quest_revision=1, operator_role="ACCOUNTABLE_OPERATOR"
        )
    conductor = service(tmp_path / "accepted")
    handoff = conductor.plan_handoffs(
        QUEST_ID, expected_quest_revision=1, operator_role="ACCOUNTABLE_OPERATOR"
    )[0]
    with pytest.raises(AgentRegistryError):
        conductor.record_review_evidence(
            handoff.record_id,
            expected_handoff_revision=1,
            reviewer_agent_id="AIGC-AGENT-TASK-ARCHITECT",
            verdict="PASS",
            findings=[],
            acceptance_criteria_results=[
                {"criterion": "scope_is_bounded", "status": "PASS", "evidence_ids": []}
            ],
            evidence_ids=[],
            operator_role="ACCOUNTABLE_OPERATOR",
        )


def test_application_container_wires_omega_x(tmp_path: Path) -> None:
    container = build_container(tmp_path / "container.sqlite3")
    assert container.quest_conductor is not None
    assert container.quest_conductor.conductor_agent_id == "AIGC-AGENT-OMEGA-X"
