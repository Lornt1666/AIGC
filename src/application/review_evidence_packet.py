from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from src.application.authorization_service import AuthorizationApplicationService
from src.application.quests import QuestApplicationService
from src.application.review_authorization_bridge import ReviewAuthorizationBridge
from src.domain.identity import (
    IdentityDecision,
    IdentityEvidenceReceipt,
    IdentityEvidenceReceiptRepository,
)
from src.domain.quests import (
    QuestConflict,
    QuestLifecycleState,
    QuestStateError,
    WorkSourcePolicyError,
)
from src.domain.repositories import StoredRecord
from src.domain.review_evidence import (
    ReviewDecision,
    ReviewEvidenceConflict,
    ReviewEvidenceNotFound,
    ReviewEvidencePacket,
    ReviewEvidenceRepository,
    ReviewJudgmentDenied,
    ReviewJudgmentReceipt,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _unique_texts(values: Sequence[object]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            text
            for text in (str(value).strip() for value in values)
            if text
        )
    )


@dataclass(frozen=True)
class ReviewGateOpenResult:
    quest: StoredRecord
    packet: ReviewEvidencePacket
    identity_receipt_id: str
    authorization_receipt_id: str
    authorization_request_digest: str


@dataclass(frozen=True)
class ReviewJudgmentResult:
    quest: StoredRecord
    packet: ReviewEvidencePacket
    judgment: ReviewJudgmentReceipt


class ReviewEvidencePacketService:
    """Generates immutable review evidence and governs human judgment.

    Packet generation is advisory and never changes Quest state. Review-gate
    transitions require a persisted PIBC receipt, the existing authorization
    kernel, an immutable authorization receipt, optimistic Quest revision, and
    repository-controlled transition evidence.
    """

    _PACKET_SOURCE_STATES = {
        QuestLifecycleState.WORK_ACCEPTED.value,
        QuestLifecycleState.REWORK_REQUIRED.value,
    }

    def __init__(
        self,
        *,
        review_repository: ReviewEvidenceRepository,
        identity_receipt_repository: IdentityEvidenceReceiptRepository,
        authorization_service: AuthorizationApplicationService,
        review_authorization_bridge: ReviewAuthorizationBridge,
        quest_service: QuestApplicationService,
        packet_schema_path: str | Path,
        judgment_schema_path: str | Path,
    ) -> None:
        self.review_repository = review_repository
        self.identity_receipt_repository = identity_receipt_repository
        self.authorization_service = authorization_service
        self.review_authorization_bridge = review_authorization_bridge
        self.quest_service = quest_service
        self.packet_validator = self._validator(packet_schema_path)
        self.judgment_validator = self._validator(judgment_schema_path)

    @staticmethod
    def _validator(path: str | Path) -> Draft202012Validator:
        schema = json.loads(Path(path).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def generate_packet(
        self,
        *,
        quest_id: str,
        expected_revision: int,
        identity_receipt_id: str,
        operator_role: str,
        executive_summary: str,
        criteria_evidence: Sequence[Mapping[str, Any]],
        artifacts: Sequence[Mapping[str, Any]],
        test_receipts: Sequence[Mapping[str, Any]],
        source_references: Sequence[Mapping[str, Any]],
        security_findings: Sequence[str] = (),
        privacy_findings: Sequence[str] = (),
        policy_findings: Sequence[str] = (),
        unresolved_blockers: Sequence[str] = (),
        rework_recommendations: Sequence[str] = (),
        now: datetime | None = None,
    ) -> ReviewEvidencePacket:
        self._require_operator(operator_role)
        current = _utc(now or datetime.now(timezone.utc))
        quest = self.quest_service.get(quest_id)
        if quest.revision != expected_revision:
            raise QuestConflict(
                f"Expected Quest revision {expected_revision}, found {quest.revision}"
            )
        source_state = str(quest.payload.get("lifecycle_state") or "")
        if source_state not in self._PACKET_SOURCE_STATES:
            raise QuestStateError(
                f"Quest {quest_id} must be WORK_ACCEPTED or REWORK_REQUIRED before packet generation"
            )

        identity = self._require_identity_receipt(
            identity_receipt_id,
            current=current,
        )
        exact_revision, _ = self.quest_service._authorization_revision()
        if identity.exact_revision != exact_revision:
            raise WorkSourcePolicyError(
                "Review identity receipt is not bound to the current review revision"
            )

        work_acceptance = dict(quest.payload.get("work_acceptance") or {})
        if work_acceptance.get("decision") != "WORK_ACCEPTED":
            raise QuestStateError(
                "Review packet generation requires durable WORK_ACCEPTED evidence"
            )
        work_authorization_receipt_id = str(
            work_acceptance.get("authorization_receipt_id") or ""
        )
        work_acceptance_request_digest = str(
            work_acceptance.get("request_digest") or ""
        )
        if not work_authorization_receipt_id or not work_acceptance_request_digest:
            raise QuestStateError(
                "WORK_ACCEPTED evidence lacks its authorization binding"
            )
        work_authorization = self.authorization_service.get_receipt(
            work_authorization_receipt_id
        )
        if work_authorization is None or work_authorization.get("result") != "PERMIT":
            raise WorkSourcePolicyError(
                "Review packet requires the persisted work-authorization PERMIT"
            )
        if work_authorization.get("principal_id") != identity.principal_id:
            raise WorkSourcePolicyError(
                "Review identity principal differs from the work-authorized principal"
            )

        normalized_criteria = self._criteria(
            quest.payload.get("acceptance_criteria") or [],
            criteria_evidence,
        )
        normalized_artifacts = tuple(dict(item) for item in artifacts)
        normalized_tests = tuple(
            {
                **dict(item),
                "exact_revision": exact_revision,
            }
            for item in test_receipts
        )
        normalized_sources = tuple(dict(item) for item in source_references)
        findings = {
            "security": _unique_texts(security_findings),
            "privacy": _unique_texts(privacy_findings),
            "policy": _unique_texts(policy_findings),
        }
        blockers = _unique_texts(unresolved_blockers)
        recommendations = _unique_texts(rework_recommendations)
        summary = str(executive_summary).strip()
        if not summary:
            raise ValueError("Review packet executive summary is required")

        criteria_satisfied = all(
            item["status"] == "SATISFIED" for item in normalized_criteria
        )
        tests_acceptable = bool(normalized_tests) and all(
            item.get("result") in {"PASS", "NOT_APPLICABLE"}
            for item in normalized_tests
        )
        no_blockers = not blockers
        delivery_candidate = (
            criteria_satisfied and tests_acceptable and no_blockers
        )
        readiness = {
            "packet_complete": True,
            "criteria_satisfied": criteria_satisfied,
            "tests_acceptable": tests_acceptable,
            "no_unresolved_blockers": no_blockers,
            "delivery_candidate": delivery_candidate,
            "recommended_decision": (
                ReviewDecision.ACCEPTED_FOR_DELIVERY.value
                if delivery_candidate
                else ReviewDecision.REWORK_REQUIRED.value
            ),
        }

        request_material = {
            "contract_id": "AIGC-REVIEW-EVIDENCE-PACKET-001",
            "quest_id": quest_id,
            "quest_revision": expected_revision,
            "source_state": source_state,
            "exact_revision": exact_revision,
            "principal_id": identity.principal_id,
            "tenant_id": identity.tenant_id,
            "project_id": identity.project_id,
            "identity_receipt_id": identity.receipt_id,
            "work_authorization_receipt_id": work_authorization_receipt_id,
            "work_acceptance_request_digest": work_acceptance_request_digest,
            "operator_role": operator_role,
            "executive_summary": summary,
            "acceptance_criteria": list(normalized_criteria),
            "artifacts": list(normalized_artifacts),
            "test_receipts": list(normalized_tests),
            "source_references": list(normalized_sources),
            "findings": {
                key: list(values) for key, values in findings.items()
            },
            "unresolved_blockers": list(blockers),
            "rework_recommendations": list(recommendations),
            "readiness": readiness,
        }
        request_digest = _digest(request_material)
        existing = self.review_repository.get_packet_for_quest_revision(
            quest_id,
            expected_revision,
        )
        if existing is not None:
            if existing.request_digest != request_digest:
                raise ReviewEvidenceConflict(
                    "Quest revision already contains a different review packet"
                )
            return existing

        packet_digest = sha256(
            (
                "AIGC-REVIEW-EVIDENCE-PACKET-001|" + request_digest
            ).encode("utf-8")
        ).hexdigest()
        packet_id = "REP-" + packet_digest[:24].upper()
        evidence_ids = tuple(
            dict.fromkeys(
                [
                    f"AIGC-PIBC-RECEIPT:{identity.receipt_id}",
                    f"AIGC-AUTHORIZATION-RECEIPT:{work_authorization_receipt_id}",
                    f"AIGC-WORK-ACCEPTANCE-DIGEST:{work_acceptance_request_digest}",
                    *(
                        f"AIGC-ARTIFACT:{item.get('artifact_id')}:{item.get('sha256')}"
                        for item in normalized_artifacts
                    ),
                    *(
                        f"AIGC-TEST:{item.get('test_id')}:{item.get('result')}"
                        for item in normalized_tests
                    ),
                ]
            )
        )
        packet = ReviewEvidencePacket(
            packet_id=packet_id,
            packet_digest=packet_digest,
            request_digest=request_digest,
            quest_id=quest_id,
            quest_revision=expected_revision,
            source_state=source_state,
            exact_revision=exact_revision,
            principal_id=str(identity.principal_id),
            tenant_id=str(identity.tenant_id),
            project_id=str(identity.project_id),
            identity_receipt_id=identity.receipt_id,
            work_authorization_receipt_id=work_authorization_receipt_id,
            work_acceptance_request_digest=work_acceptance_request_digest,
            executive_summary=summary,
            acceptance_criteria=normalized_criteria,
            artifacts=normalized_artifacts,
            test_receipts=normalized_tests,
            source_references=normalized_sources,
            findings=findings,
            unresolved_blockers=blockers,
            rework_recommendations=recommendations,
            readiness=readiness,
            evidence_ids=evidence_ids,
            generated_at=current,
        )
        self._validate(self.packet_validator, packet.to_dict(), "review packet")
        return self.review_repository.append_packet(packet)

    def open_review_gate(
        self,
        *,
        quest_id: str,
        expected_revision: int,
        packet_id: str,
        identity_receipt_id: str,
        operator_role: str,
        now: datetime | None = None,
    ) -> ReviewGateOpenResult:
        self._require_operator(operator_role)
        packet = self._packet(packet_id)
        if packet.quest_id != quest_id or packet.quest_revision != expected_revision:
            raise ReviewEvidenceConflict(
                "Review packet is not bound to the requested Quest revision"
            )
        if packet.identity_receipt_id != identity_receipt_id:
            raise WorkSourcePolicyError(
                "Review gate must be opened by the packet-bound PIBC receipt"
            )
        quest = self.quest_service.get(quest_id)
        if quest.revision != expected_revision:
            raise QuestConflict(
                f"Expected Quest revision {expected_revision}, found {quest.revision}"
            )
        if quest.payload.get("lifecycle_state") != packet.source_state:
            raise QuestStateError(
                "Quest state no longer matches the review packet source state"
            )
        if self.review_repository.get_judgment_for_packet(packet_id) is not None:
            raise ReviewEvidenceConflict(
                "A judged packet cannot reopen the review gate"
            )

        required_evidence = [
            f"AIGC-REVIEW-PACKET:{packet.packet_id}",
            f"AIGC-REVIEW-PACKET-DIGEST:{packet.packet_digest}",
            f"AIGC-AUTHORIZATION-RECEIPT:{packet.work_authorization_receipt_id}",
        ]
        authorization = self.review_authorization_bridge.authorize_review_action(
            quest_id=quest_id,
            expected_revision=expected_revision,
            identity_receipt_id=identity_receipt_id,
            exact_revision=packet.exact_revision,
            required_states=[packet.source_state],
            action="submit_review",
            evidence_ids=required_evidence,
            risk_signals=(
                f"review-recommended:{packet.readiness['recommended_decision']}",
            ),
            now=now,
        )
        self.authorization_service.verify_permit_receipt(
            authorization.authorization_receipt_id,
            authorization.authorization_request,
            expected_exact_revision=packet.exact_revision,
            expected_resource_id=quest_id,
            expected_action="submit_review",
            expected_scopes=["quest:review_submit"],
            expected_purpose="review_submission",
            required_evidence_ids=[
                *required_evidence,
                f"AIGC-PIBC-RECEIPT:{identity_receipt_id}",
            ],
        )

        request_material = {
            "quest_id": quest_id,
            "expected_revision": expected_revision,
            "packet_id": packet.packet_id,
            "packet_digest": packet.packet_digest,
            "identity_receipt_id": identity_receipt_id,
            "authorization_receipt_id": authorization.authorization_receipt_id,
            "source_state": packet.source_state,
            "target_state": QuestLifecycleState.REVIEW_REQUIRED.value,
        }
        request_digest = _digest(request_material)
        payload = dict(quest.payload)
        payload["lifecycle_state"] = QuestLifecycleState.REVIEW_REQUIRED.value
        payload["terminal_decision"] = None
        payload["external_action_performed"] = False
        self.quest_service._validate(payload)
        transitioned = self.quest_service.quest_repository.transition(
            quest_id,
            payload,
            expected_revision=expected_revision,
            allowed_from=[packet.source_state],
            target_state=QuestLifecycleState.REVIEW_REQUIRED.value,
            event_type="quest.review_required",
            idempotency_key=f"review-open:{packet.packet_id}",
            request_digest=request_digest,
            exact_revision=self.quest_service.exact_revision,
            audit_payload={
                "packet_id": packet.packet_id,
                "packet_digest": packet.packet_digest,
                "identity_receipt_id": identity_receipt_id,
                "authorization_receipt_id": authorization.authorization_receipt_id,
                "recommended_decision": packet.readiness[
                    "recommended_decision"
                ],
                "state_changed": True,
                "external_action_performed": False,
            },
        )
        return ReviewGateOpenResult(
            quest=transitioned,
            packet=packet,
            identity_receipt_id=identity_receipt_id,
            authorization_receipt_id=authorization.authorization_receipt_id,
            authorization_request_digest=str(
                authorization.authorization_request["request_digest"]
            ),
        )

    def judge_review(
        self,
        *,
        quest_id: str,
        expected_revision: int,
        packet_id: str,
        identity_receipt_id: str,
        operator_role: str,
        decision: str,
        reason: str,
        now: datetime | None = None,
    ) -> ReviewJudgmentResult:
        self._require_operator(operator_role)
        current = _utc(now or datetime.now(timezone.utc))
        packet = self._packet(packet_id)
        if packet.quest_id != quest_id:
            raise ReviewEvidenceConflict(
                "Review judgment Quest does not match the packet"
            )
        resolved_decision = ReviewDecision(str(decision))
        normalized_reason = str(reason).strip()
        if not normalized_reason:
            raise ValueError("Review judgment reason is required")
        if (
            resolved_decision is ReviewDecision.ACCEPTED_FOR_DELIVERY
            and packet.readiness.get("delivery_candidate") is not True
        ):
            raise ReviewJudgmentDenied(
                "Packet evidence does not support ACCEPTED_FOR_DELIVERY"
            )

        quest = self.quest_service.get(quest_id)
        existing_judgment = self.review_repository.get_judgment_for_packet(
            packet_id
        )
        if existing_judgment is not None:
            identical = (
                existing_judgment.decision is resolved_decision
                and existing_judgment.reason == normalized_reason
                and existing_judgment.identity_receipt_id
                == identity_receipt_id
            )
            if not identical:
                raise ReviewEvidenceConflict(
                    "Review packet already contains a different judgment"
                )
            if (
                quest.payload.get("lifecycle_state")
                == resolved_decision.value
                and quest.revision == expected_revision + 1
            ):
                return ReviewJudgmentResult(
                    quest=quest,
                    packet=packet,
                    judgment=existing_judgment,
                )

        if quest.revision != expected_revision:
            raise QuestConflict(
                f"Expected Quest revision {expected_revision}, found {quest.revision}"
            )
        if (
            quest.payload.get("lifecycle_state")
            != QuestLifecycleState.REVIEW_REQUIRED.value
        ):
            raise QuestStateError(
                f"Quest {quest_id} must be REVIEW_REQUIRED before judgment"
            )
        if expected_revision != packet.quest_revision + 1:
            raise ReviewEvidenceConflict(
                "Review judgment revision is not the packet's opened review revision"
            )

        identity = self._require_identity_receipt(
            identity_receipt_id,
            current=current,
        )
        if identity.exact_revision != packet.exact_revision:
            raise WorkSourcePolicyError(
                "Judgment identity receipt is not bound to the packet revision"
            )
        decision_evidence = (
            f"AIGC-REVIEW-DECISION:{resolved_decision.value}"
        )
        required_evidence = [
            f"AIGC-REVIEW-PACKET:{packet.packet_id}",
            f"AIGC-REVIEW-PACKET-DIGEST:{packet.packet_digest}",
            decision_evidence,
        ]
        authorization = self.review_authorization_bridge.authorize_review_action(
            quest_id=quest_id,
            expected_revision=expected_revision,
            identity_receipt_id=identity_receipt_id,
            exact_revision=packet.exact_revision,
            required_states=[QuestLifecycleState.REVIEW_REQUIRED.value],
            action="judge_review",
            evidence_ids=required_evidence,
            risk_signals=(
                f"review-decision:{resolved_decision.value}",
                f"review-delivery-candidate:{str(packet.readiness['delivery_candidate']).lower()}",
            ),
            now=current,
        )
        self.authorization_service.verify_permit_receipt(
            authorization.authorization_receipt_id,
            authorization.authorization_request,
            expected_exact_revision=packet.exact_revision,
            expected_resource_id=quest_id,
            expected_action="judge_review",
            expected_scopes=["quest:review_judge"],
            expected_purpose="review_judgment",
            required_evidence_ids=[
                *required_evidence,
                f"AIGC-PIBC-RECEIPT:{identity_receipt_id}",
            ],
        )

        judgment_material = {
            "packet_id": packet.packet_id,
            "packet_digest": packet.packet_digest,
            "quest_id": quest_id,
            "quest_revision": expected_revision,
            "exact_revision": packet.exact_revision,
            "identity_receipt_id": identity_receipt_id,
            "authorization_receipt_id": authorization.authorization_receipt_id,
            "authorization_request_digest": authorization.authorization_request[
                "request_digest"
            ],
            "reviewer_principal_id": identity.principal_id,
            "operator_role": operator_role,
            "decision": resolved_decision.value,
            "reason": normalized_reason,
        }
        judgment_digest = _digest(judgment_material)
        judgment = ReviewJudgmentReceipt(
            judgment_id="RJR-" + judgment_digest[:24].upper(),
            packet_id=packet.packet_id,
            packet_digest=packet.packet_digest,
            quest_id=quest_id,
            quest_revision=expected_revision,
            exact_revision=packet.exact_revision,
            identity_receipt_id=identity_receipt_id,
            authorization_receipt_id=authorization.authorization_receipt_id,
            authorization_request_digest=str(
                authorization.authorization_request["request_digest"]
            ),
            reviewer_principal_id=str(identity.principal_id),
            decision=resolved_decision,
            reason=normalized_reason,
            evidence_ids=tuple(
                dict.fromkeys(
                    [
                        *required_evidence,
                        f"AIGC-PIBC-RECEIPT:{identity_receipt_id}",
                        f"AIGC-AUTHORIZATION-RECEIPT:{authorization.authorization_receipt_id}",
                    ]
                )
            ),
            decided_at=current,
        )
        self._validate(
            self.judgment_validator,
            judgment.to_dict(),
            "review judgment",
        )
        stored_judgment = self.review_repository.append_judgment(judgment)

        transition_material = {
            **judgment_material,
            "judgment_id": stored_judgment.judgment_id,
            "source_state": QuestLifecycleState.REVIEW_REQUIRED.value,
            "target_state": resolved_decision.value,
        }
        transition_digest = _digest(transition_material)
        payload = dict(quest.payload)
        payload["lifecycle_state"] = resolved_decision.value
        payload["terminal_decision"] = None
        payload["external_action_performed"] = False
        self.quest_service._validate(payload)
        transitioned = self.quest_service.quest_repository.transition(
            quest_id,
            payload,
            expected_revision=expected_revision,
            allowed_from=[QuestLifecycleState.REVIEW_REQUIRED.value],
            target_state=resolved_decision.value,
            event_type=(
                "quest.accepted_for_delivery"
                if resolved_decision
                is ReviewDecision.ACCEPTED_FOR_DELIVERY
                else "quest.rework_required"
            ),
            idempotency_key=f"review-judgment:{packet.packet_id}",
            request_digest=transition_digest,
            exact_revision=self.quest_service.exact_revision,
            audit_payload={
                "packet_id": packet.packet_id,
                "packet_digest": packet.packet_digest,
                "judgment_id": stored_judgment.judgment_id,
                "decision": resolved_decision.value,
                "identity_receipt_id": identity_receipt_id,
                "authorization_receipt_id": authorization.authorization_receipt_id,
                "reviewer_principal_id": identity.principal_id,
                "delivery_performed": False,
                "state_changed": True,
                "external_action_performed": False,
            },
        )
        return ReviewJudgmentResult(
            quest=transitioned,
            packet=packet,
            judgment=stored_judgment,
        )

    def get_packet(self, packet_id: str) -> ReviewEvidencePacket:
        return self._packet(packet_id)

    def list_packets(self, quest_id: str) -> Sequence[ReviewEvidencePacket]:
        return self.review_repository.list_packets(quest_id)

    def get_judgment_for_packet(
        self,
        packet_id: str,
    ) -> ReviewJudgmentReceipt | None:
        return self.review_repository.get_judgment_for_packet(packet_id)

    def _packet(self, packet_id: str) -> ReviewEvidencePacket:
        packet = self.review_repository.get_packet(packet_id)
        if packet is None:
            raise ReviewEvidenceNotFound(
                f"Review evidence packet not found: {packet_id}"
            )
        return packet

    def _require_identity_receipt(
        self,
        receipt_id: str,
        *,
        current: datetime,
    ) -> IdentityEvidenceReceipt:
        receipt = self.identity_receipt_repository.get(receipt_id)
        if receipt is None:
            raise WorkSourcePolicyError(
                "Identity evidence receipt not found"
            )
        if receipt.result is not IdentityDecision.PERMIT:
            raise WorkSourcePolicyError(
                "Identity evidence receipt is not a PERMIT"
            )
        if receipt.expires_at is None or _utc(receipt.expires_at) <= current:
            raise WorkSourcePolicyError(
                "Identity evidence receipt has expired"
            )
        required = (
            receipt.principal_id,
            receipt.membership_id,
            receipt.session_id,
            receipt.tenant_id,
            receipt.project_id,
            receipt.identity_assurance,
            receipt.authentication_assurance,
            receipt.federation_assurance,
            receipt.evidence_maturity,
            receipt.runtime_authority,
        )
        if any(value is None for value in required):
            raise WorkSourcePolicyError(
                "Identity evidence receipt lacks normalized review bindings"
            )
        return receipt

    @staticmethod
    def _criteria(
        quest_criteria: Sequence[object],
        evidence: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        expected = [str(item) for item in quest_criteria]
        supplied: dict[int, dict[str, Any]] = {}
        for raw in evidence:
            item = dict(raw)
            index = int(item.get("criterion_index", -1))
            if index in supplied:
                raise ValueError(
                    f"Duplicate acceptance criterion index: {index}"
                )
            supplied[index] = item
        if set(supplied) != set(range(len(expected))):
            raise ValueError(
                "Review packet must assess every Quest acceptance criterion exactly once"
            )

        normalized: list[dict[str, Any]] = []
        for index, text in enumerate(expected):
            item = supplied[index]
            status = str(item.get("status") or "")
            if status not in {"SATISFIED", "PARTIAL", "UNSATISFIED"}:
                raise ValueError(
                    f"Invalid status for acceptance criterion {index}"
                )
            evidence_refs = list(
                dict.fromkeys(
                    ref
                    for ref in (
                        str(value).strip()
                        for value in item.get("evidence_refs") or []
                    )
                    if ref
                )
            )
            notes = (
                str(item.get("notes")).strip()
                if item.get("notes") is not None
                else None
            )
            if not evidence_refs and not notes:
                raise ValueError(
                    f"Acceptance criterion {index} requires evidence or notes"
                )
            normalized.append(
                {
                    "criterion_index": index,
                    "criterion_text": text,
                    "status": status,
                    "evidence_refs": evidence_refs,
                    "notes": notes,
                }
            )
        return tuple(normalized)

    @staticmethod
    def _require_operator(operator_role: str) -> None:
        if operator_role != "ACCOUNTABLE_OPERATOR":
            raise WorkSourcePolicyError(
                "Only ACCOUNTABLE_OPERATOR may operate the review gate"
            )

    @staticmethod
    def _validate(
        validator: Draft202012Validator,
        value: Mapping[str, Any],
        label: str,
    ) -> None:
        errors = sorted(
            validator.iter_errors(dict(value)),
            key=lambda error: list(error.absolute_path),
        )
        if not errors:
            return
        details = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors[:10]
        )
        raise ValueError(f"{label} contract validation failed: {details}")
