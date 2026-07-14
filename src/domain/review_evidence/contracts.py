from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat()


def _parse(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return _utc(parsed)


class ReviewDecision(StrEnum):
    ACCEPTED_FOR_DELIVERY = "ACCEPTED_FOR_DELIVERY"
    REWORK_REQUIRED = "REWORK_REQUIRED"


@dataclass(frozen=True)
class ReviewEvidencePacket:
    packet_id: str
    packet_digest: str
    request_digest: str
    quest_id: str
    quest_revision: int
    source_state: str
    exact_revision: str
    principal_id: str
    tenant_id: str
    project_id: str
    identity_receipt_id: str
    work_authorization_receipt_id: str
    work_acceptance_request_digest: str
    executive_summary: str
    acceptance_criteria: tuple[dict[str, Any], ...]
    artifacts: tuple[dict[str, Any], ...]
    test_receipts: tuple[dict[str, Any], ...]
    source_references: tuple[dict[str, Any], ...]
    findings: dict[str, tuple[str, ...]]
    unresolved_blockers: tuple[str, ...]
    rework_recommendations: tuple[str, ...]
    readiness: dict[str, Any]
    evidence_ids: tuple[str, ...]
    generated_at: datetime
    operator_role: str = "ACCOUNTABLE_OPERATOR"
    retention_class: str = "REVIEW_EVIDENCE_365D"

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-REVIEW-EVIDENCE-PACKET-001",
            "contract_version": "1.0.0",
            "packet_id": self.packet_id,
            "packet_digest": self.packet_digest,
            "request_digest": self.request_digest,
            "quest_id": self.quest_id,
            "quest_revision": self.quest_revision,
            "source_state": self.source_state,
            "exact_revision": self.exact_revision,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "identity_receipt_id": self.identity_receipt_id,
            "work_authorization_receipt_id": self.work_authorization_receipt_id,
            "work_acceptance_request_digest": self.work_acceptance_request_digest,
            "operator_role": self.operator_role,
            "executive_summary": self.executive_summary,
            "acceptance_criteria": [dict(item) for item in self.acceptance_criteria],
            "artifacts": [dict(item) for item in self.artifacts],
            "test_receipts": [dict(item) for item in self.test_receipts],
            "source_references": [dict(item) for item in self.source_references],
            "findings": {
                key: list(values) for key, values in self.findings.items()
            },
            "unresolved_blockers": list(self.unresolved_blockers),
            "rework_recommendations": list(self.rework_recommendations),
            "readiness": dict(self.readiness),
            "evidence_ids": list(self.evidence_ids),
            "generated_at": _iso(self.generated_at),
            "retention_class": self.retention_class,
            "advisory_only": True,
            "human_judgment_required": True,
            "state_changed": False,
            "external_action_performed": False,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReviewEvidencePacket":
        findings = dict(value.get("findings") or {})
        return cls(
            packet_id=str(value["packet_id"]),
            packet_digest=str(value["packet_digest"]),
            request_digest=str(value["request_digest"]),
            quest_id=str(value["quest_id"]),
            quest_revision=int(value["quest_revision"]),
            source_state=str(value["source_state"]),
            exact_revision=str(value["exact_revision"]),
            principal_id=str(value["principal_id"]),
            tenant_id=str(value["tenant_id"]),
            project_id=str(value["project_id"]),
            identity_receipt_id=str(value["identity_receipt_id"]),
            work_authorization_receipt_id=str(value["work_authorization_receipt_id"]),
            work_acceptance_request_digest=str(value["work_acceptance_request_digest"]),
            executive_summary=str(value["executive_summary"]),
            acceptance_criteria=tuple(dict(item) for item in value.get("acceptance_criteria") or ()),
            artifacts=tuple(dict(item) for item in value.get("artifacts") or ()),
            test_receipts=tuple(dict(item) for item in value.get("test_receipts") or ()),
            source_references=tuple(dict(item) for item in value.get("source_references") or ()),
            findings={
                "security": tuple(str(item) for item in findings.get("security") or ()),
                "privacy": tuple(str(item) for item in findings.get("privacy") or ()),
                "policy": tuple(str(item) for item in findings.get("policy") or ()),
            },
            unresolved_blockers=tuple(str(item) for item in value.get("unresolved_blockers") or ()),
            rework_recommendations=tuple(str(item) for item in value.get("rework_recommendations") or ()),
            readiness=dict(value["readiness"]),
            evidence_ids=tuple(str(item) for item in value.get("evidence_ids") or ()),
            generated_at=_parse(value["generated_at"]),
            operator_role=str(value.get("operator_role") or "ACCOUNTABLE_OPERATOR"),
            retention_class=str(value.get("retention_class") or "REVIEW_EVIDENCE_365D"),
        )


@dataclass(frozen=True)
class ReviewJudgmentReceipt:
    judgment_id: str
    packet_id: str
    packet_digest: str
    quest_id: str
    quest_revision: int
    exact_revision: str
    identity_receipt_id: str
    authorization_receipt_id: str
    authorization_request_digest: str
    reviewer_principal_id: str
    decision: ReviewDecision
    reason: str
    evidence_ids: tuple[str, ...]
    decided_at: datetime
    operator_role: str = "ACCOUNTABLE_OPERATOR"

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-REVIEW-JUDGMENT-RECEIPT-001",
            "contract_version": "1.0.0",
            "judgment_id": self.judgment_id,
            "packet_id": self.packet_id,
            "packet_digest": self.packet_digest,
            "quest_id": self.quest_id,
            "quest_revision": self.quest_revision,
            "source_state": "REVIEW_REQUIRED",
            "target_state": self.decision.value,
            "exact_revision": self.exact_revision,
            "identity_receipt_id": self.identity_receipt_id,
            "authorization_receipt_id": self.authorization_receipt_id,
            "authorization_request_digest": self.authorization_request_digest,
            "reviewer_principal_id": self.reviewer_principal_id,
            "operator_role": self.operator_role,
            "decision": self.decision.value,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "decided_at": _iso(self.decided_at),
            "delivery_performed": False,
            "state_changed": True,
            "external_action_performed": False,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReviewJudgmentReceipt":
        return cls(
            judgment_id=str(value["judgment_id"]),
            packet_id=str(value["packet_id"]),
            packet_digest=str(value["packet_digest"]),
            quest_id=str(value["quest_id"]),
            quest_revision=int(value["quest_revision"]),
            exact_revision=str(value["exact_revision"]),
            identity_receipt_id=str(value["identity_receipt_id"]),
            authorization_receipt_id=str(value["authorization_receipt_id"]),
            authorization_request_digest=str(value["authorization_request_digest"]),
            reviewer_principal_id=str(value["reviewer_principal_id"]),
            decision=ReviewDecision(str(value["decision"])),
            reason=str(value["reason"]),
            evidence_ids=tuple(str(item) for item in value.get("evidence_ids") or ()),
            decided_at=_parse(value["decided_at"]),
            operator_role=str(value.get("operator_role") or "ACCOUNTABLE_OPERATOR"),
        )


class ReviewEvidenceRepository(Protocol):
    def append_packet(self, packet: ReviewEvidencePacket) -> ReviewEvidencePacket: ...

    def get_packet(self, packet_id: str) -> ReviewEvidencePacket | None: ...

    def get_packet_for_quest_revision(
        self,
        quest_id: str,
        quest_revision: int,
    ) -> ReviewEvidencePacket | None: ...

    def list_packets(self, quest_id: str) -> Sequence[ReviewEvidencePacket]: ...

    def append_judgment(
        self,
        receipt: ReviewJudgmentReceipt,
    ) -> ReviewJudgmentReceipt: ...

    def get_judgment(self, judgment_id: str) -> ReviewJudgmentReceipt | None: ...

    def get_judgment_for_packet(
        self,
        packet_id: str,
    ) -> ReviewJudgmentReceipt | None: ...
