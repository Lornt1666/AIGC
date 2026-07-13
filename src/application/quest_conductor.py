from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from src.domain.quests import QuestLifecycleState, QuestNotFound, QuestRepository, QuestStateError
from src.domain.repositories import AuditEventRepository, RecordRepository, StoredRecord

from .quest_conductor_review import (
    AgentHandoffConflict,
    AgentRegistryError,
    ReviewEvidenceResult,
    digest,
    now,
    record_review_evidence as _record_review,
)


_ALLOWED_STATES = {
    QuestLifecycleState.WORK_ACCEPTED.value,
    QuestLifecycleState.RESEARCHING.value,
    QuestLifecycleState.PLANNING.value,
    QuestLifecycleState.EXECUTING_LOCALLY.value,
    QuestLifecycleState.REVIEW_REQUIRED.value,
    QuestLifecycleState.REWORK_REQUIRED.value,
}


def _validator(path: str | Path) -> Draft202012Validator:
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


class QuestConductor:
    """Omega-X records internal Quest handoffs; it never executes agents."""

    def __init__(
        self,
        quest_repository: QuestRepository,
        handoff_repository: RecordRepository,
        review_repository: RecordRepository,
        audit_repository: AuditEventRepository,
        *,
        registry_path: str | Path,
        registry_schema_path: str | Path,
        handoff_schema_path: str | Path,
        review_schema_path: str | Path,
        exact_revision: str = "LOCAL_UNVERIFIED",
    ) -> None:
        self.quest_repository = quest_repository
        self.handoff_repository = handoff_repository
        self.review_repository = review_repository
        self.audit_repository = audit_repository
        self.exact_revision = str(exact_revision).strip() or "LOCAL_UNVERIFIED"
        self.registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
        _validator(registry_schema_path).validate(self.registry)
        self.handoff_validator = _validator(handoff_schema_path)
        self.review_validator = _validator(review_schema_path)
        self.agents = self._index_registry()
        self.conductor_id = self.registry["conductor_agent_id"]
        self.conductor_agent_id = self.conductor_id
        self.default_sequence = tuple(self.registry["default_handoff_sequence"])

    @staticmethod
    def _operator(role: str) -> None:
        if role != "ACCOUNTABLE_OPERATOR":
            raise PermissionError("ACCOUNTABLE_OPERATOR authority is required")

    def _index_registry(self) -> dict[str, dict[str, Any]]:
        entries = [dict(item) for item in self.registry["agents"]]
        agents = {item["agent_id"]: item for item in entries}
        if len(agents) != len(entries):
            raise AgentRegistryError("duplicate agent_id")
        conductor = agents.get(self.registry["conductor_agent_id"])
        sequence = self.registry["default_handoff_sequence"]
        if not conductor or not conductor["active"] or conductor["agent_id"] in sequence:
            raise AgentRegistryError("invalid conductor")
        if len(set(sequence)) != len(sequence):
            raise AgentRegistryError("duplicate default agent")
        for agent in entries:
            if agent["external_action_allowed"] is not False:
                raise AgentRegistryError("external-action authority is prohibited")
            if any(target not in agents for target in agent["handoff_targets"]):
                raise AgentRegistryError("unknown handoff target")
        if any(not agents.get(item, {}).get("active") for item in sequence):
            raise AgentRegistryError("inactive default agent")
        return agents

    def _sequence(self, values: Sequence[str] | None) -> tuple[str, ...]:
        sequence = tuple(values or self.default_sequence)
        if not sequence or len(set(sequence)) != len(sequence) or self.conductor_id in sequence:
            raise AgentRegistryError("invalid agent sequence")
        chain = (self.conductor_id, *sequence)
        for source_id, target_id in zip(chain, chain[1:]):
            source, target = self.agents.get(source_id), self.agents.get(target_id)
            if not source or not target or not target["active"] or target_id not in source["handoff_targets"]:
                raise AgentRegistryError(f"invalid handoff edge {source_id} -> {target_id}")
        return sequence

    def _audit(self, event_type: str, material: Mapping[str, Any]) -> None:
        event_digest = digest(material)
        self.audit_repository.append(
            f"qcevt_{event_digest[:24]}",
            event_type,
            {
                **dict(material),
                "operator_review_required": True,
                "external_action_performed": False,
            },
            exact_revision=self.exact_revision,
            request_digest=event_digest,
            idempotency_key=f"quest-conductor:{event_type}:{event_digest}",
        )

    def plan_handoffs(
        self,
        quest_id: str,
        *,
        expected_quest_revision: int,
        operator_role: str,
        agent_sequence: Sequence[str] | None = None,
    ) -> tuple[StoredRecord, ...]:
        self._operator(operator_role)
        quest = self.quest_repository.get(quest_id)
        if quest is None:
            raise QuestNotFound(quest_id)
        if quest.revision != expected_quest_revision:
            raise AgentHandoffConflict("Quest revision changed")
        if quest.payload.get("lifecycle_state") not in _ALLOWED_STATES:
            raise QuestStateError("Quest must contain accepted bounded internal work")
        if quest.payload.get("external_action_performed") is not False:
            raise QuestStateError("external-action evidence cannot seed handoffs")

        sequence = self._sequence(agent_sequence)
        previous: str | None = None
        records: list[StoredRecord] = []
        for index, target_id in enumerate(sequence, start=1):
            source_id = self.conductor_id if previous is None else sequence[index - 2]
            agent = self.agents[target_id]
            logical = {
                "schema_version": "1.0.0",
                "evidence_subject": "INTERNAL_QUEST_HANDOFF",
                "quest_id": quest_id,
                "quest_revision": quest.revision,
                "sequence": index,
                "from_agent_id": source_id,
                "to_agent_id": target_id,
                "source_handoff_id": previous,
                "status": "PLANNED",
                "purpose": agent["purpose"],
                "input_artifact_ids": (
                    [f"quest:{quest_id}:revision:{quest.revision}"]
                    if previous is None
                    else [f"handoff:{previous}:expected-output"]
                ),
                "input_artifact_types": list(agent["input_artifact_types"]),
                "expected_output_artifact_type": agent["output_artifact_types"][0],
                "acceptance_criteria": list(self.registry["default_quality_criteria"]),
                "required_approval_gates": list(self.registry["required_approval_gates"]),
                "exact_revision": self.exact_revision,
                "authority_class": "ACCOUNTABLE_OPERATOR",
                "operator_review_required": True,
                "external_action_performed": False,
            }
            handoff_digest = digest(logical)
            handoff_id = f"handoff_{handoff_digest[:24]}"
            existing = self.handoff_repository.get(handoff_id)
            if existing:
                if existing.payload.get("handoff_digest") != handoff_digest:
                    raise AgentHandoffConflict("handoff identity collision")
                records.append(existing)
            else:
                payload = {
                    "handoff_id": handoff_id,
                    **logical,
                    "handoff_digest": handoff_digest,
                    "created_at": now(),
                    "completed_at": None,
                    "review_packet_ids": [],
                    "last_review_verdict": None,
                }
                self.handoff_validator.validate(payload)
                records.append(self.handoff_repository.put(
                    handoff_id,
                    payload,
                    expected_revision=0,
                    idempotency_key=handoff_id,
                ))
            previous = handoff_id

        self._audit("quest_conductor.handoff_plan_created", {
            "quest_id": quest_id,
            "quest_revision": quest.revision,
            "handoff_ids": [record.record_id for record in records],
            "exact_revision": self.exact_revision,
        })
        return tuple(records)

    def record_review_evidence(
        self,
        handoff_id: str,
        *,
        expected_handoff_revision: int,
        reviewer_agent_id: str,
        verdict: str,
        findings: Sequence[Mapping[str, Any]],
        acceptance_criteria_results: Sequence[Mapping[str, Any]],
        evidence_ids: Sequence[str],
        operator_role: str,
    ) -> ReviewEvidenceResult:
        return _record_review(
            self,
            handoff_id,
            expected_handoff_revision=expected_handoff_revision,
            reviewer_agent_id=reviewer_agent_id,
            verdict=verdict,
            findings=findings,
            acceptance_criteria_results=acceptance_criteria_results,
            evidence_ids=evidence_ids,
            operator_role=operator_role,
        )

    def get_handoff(self, handoff_id: str) -> StoredRecord | None:
        return self.handoff_repository.get(handoff_id)

    def list_handoffs(self, quest_id: str) -> tuple[StoredRecord, ...]:
        return tuple(
            record for record in self.handoff_repository.list()
            if record.payload.get("quest_id") == quest_id
        )

    def get_review_packet(self, packet_id: str) -> StoredRecord | None:
        return self.review_repository.get(packet_id)
