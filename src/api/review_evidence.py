from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.domain.quests import (
    QuestConflict,
    QuestNotFound,
    QuestStateError,
    WorkSourcePolicyError,
)
from src.domain.review_evidence import (
    ReviewEvidenceConflict,
    ReviewEvidenceNotFound,
    ReviewJudgmentDenied,
)


class ReviewIdentityPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]


class CriterionEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_index: int = Field(ge=0)
    status: Literal["SATISFIED", "PARTIAL", "UNSATISFIED"]
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)


class ArtifactEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(pattern=r"^artifact_[A-Za-z0-9_-]{6,120}$")
    path: str = Field(min_length=1, max_length=2000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0)
    evidence_state: Literal[
        "DECLARED",
        "HASH_VERIFIED",
        "TESTED",
        "CI_OBSERVED",
    ]
    source: Literal[
        "OPERATOR_DECLARED",
        "REPOSITORY_ARTIFACT",
        "CI_ARTIFACT",
    ]
    description: str | None = Field(default=None, max_length=4000)


class TestReceiptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: str = Field(pattern=r"^test_[A-Za-z0-9_-]{4,120}$")
    command: str = Field(min_length=1, max_length=4000)
    result: Literal["PASS", "FAIL", "NOT_APPLICABLE"]
    observed_at: datetime
    evidence_ref: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)


class SourceReferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^source_[A-Za-z0-9_-]{4,120}$")
    title: str = Field(min_length=1, max_length=1000)
    reference: str = Field(min_length=1, max_length=4000)
    rights_status: Literal[
        "PUBLIC",
        "CONSENTED",
        "OFFICIAL_API",
        "OPERATOR_PROVIDED",
        "INTERNAL",
    ]


class GenerateReviewPacketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    identity_receipt_id: str = Field(pattern=r"^IDR-[A-F0-9]{24}$")
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    executive_summary: str = Field(min_length=1, max_length=12000)
    acceptance_criteria: list[CriterionEvidenceInput] = Field(
        min_length=1,
        max_length=100,
    )
    artifacts: list[ArtifactEvidenceInput] = Field(
        default_factory=list,
        max_length=500,
    )
    test_receipts: list[TestReceiptInput] = Field(
        default_factory=list,
        max_length=200,
    )
    source_references: list[SourceReferenceInput] = Field(
        default_factory=list,
        max_length=200,
    )
    security_findings: list[str] = Field(default_factory=list, max_length=200)
    privacy_findings: list[str] = Field(default_factory=list, max_length=200)
    policy_findings: list[str] = Field(default_factory=list, max_length=200)
    unresolved_blockers: list[str] = Field(default_factory=list, max_length=200)
    rework_recommendations: list[str] = Field(default_factory=list, max_length=200)


class OpenReviewGateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    packet_id: str = Field(pattern=r"^REP-[A-F0-9]{24}$")
    identity_receipt_id: str = Field(pattern=r"^IDR-[A-F0-9]{24}$")
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]


class ReviewJudgmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    packet_id: str = Field(pattern=r"^REP-[A-F0-9]{24}$")
    identity_receipt_id: str = Field(pattern=r"^IDR-[A-F0-9]{24}$")
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    decision: Literal["ACCEPTED_FOR_DELIVERY", "REWORK_REQUIRED"]
    reason: str = Field(min_length=1, max_length=8000)


def _record_response(record: Any) -> dict[str, Any]:
    return {
        **dict(record.payload),
        "revision": record.revision,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _raise_review_error(exc: Exception, *, operation: str) -> None:
    if isinstance(exc, (QuestNotFound, ReviewEvidenceNotFound)):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "REVIEW_EVIDENCE_NOT_FOUND",
                "operation": operation,
                "message": str(exc),
                "external_action_performed": False,
            },
        ) from exc
    if isinstance(
        exc,
        (
            QuestConflict,
            QuestStateError,
            ReviewEvidenceConflict,
        ),
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REVIEW_EVIDENCE_CONFLICT",
                "operation": operation,
                "message": str(exc),
                "external_action_performed": False,
            },
        ) from exc
    if isinstance(exc, (WorkSourcePolicyError, ReviewJudgmentDenied)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "REVIEW_GATE_AUTHORIZATION_DENIED",
                "operation": operation,
                "message": str(exc),
                "external_action_performed": False,
            },
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "REVIEW_EVIDENCE_INVALID_REQUEST",
                "operation": operation,
                "message": str(exc),
                "external_action_performed": False,
            },
        ) from exc
    raise exc


def register_review_evidence_routes(
    router: APIRouter,
    container: Any,
) -> None:
    @router.post(
        "/api/v1/quests/{quest_id}/local-review-identity-preflight"
    )
    def local_review_identity_preflight(
        quest_id: str,
        request: ReviewIdentityPreflightRequest,
    ) -> dict[str, Any]:
        try:
            evaluation = (
                container.local_review_identity_preflight_service.issue_for_review(
                    quest_id=quest_id,
                    expected_revision=request.expected_revision,
                    operator_role=request.operator_role,
                )
            )
        except Exception as exc:
            _raise_review_error(exc, operation="LOCAL_REVIEW_IDENTITY_PREFLIGHT")
            raise
        receipt = evaluation.receipt.to_dict()
        return {
            "quest_id": quest_id,
            "quest_revision": request.expected_revision,
            "identity_receipt_id": receipt["receipt_id"],
            "result": receipt["result"],
            "principal_id": receipt["principal_id"],
            "tenant_id": receipt["tenant_id"],
            "project_id": receipt["project_id"],
            "runtime_authority": receipt["runtime_authority"],
            "expires_at": receipt["expires_at"],
            "production_identity_authorized": False,
            "external_action_performed": False,
        }

    @router.post("/api/v1/quests/{quest_id}/review-packets", status_code=201)
    def generate_review_packet(
        quest_id: str,
        request: GenerateReviewPacketRequest,
    ) -> dict[str, Any]:
        try:
            packet = container.review_evidence_service.generate_packet(
                quest_id=quest_id,
                expected_revision=request.expected_revision,
                identity_receipt_id=request.identity_receipt_id,
                operator_role=request.operator_role,
                executive_summary=request.executive_summary,
                criteria_evidence=[
                    item.model_dump(mode="json")
                    for item in request.acceptance_criteria
                ],
                artifacts=[
                    item.model_dump(mode="json") for item in request.artifacts
                ],
                test_receipts=[
                    item.model_dump(mode="json")
                    for item in request.test_receipts
                ],
                source_references=[
                    item.model_dump(mode="json")
                    for item in request.source_references
                ],
                security_findings=request.security_findings,
                privacy_findings=request.privacy_findings,
                policy_findings=request.policy_findings,
                unresolved_blockers=request.unresolved_blockers,
                rework_recommendations=request.rework_recommendations,
            )
        except Exception as exc:
            _raise_review_error(exc, operation="GENERATE_REVIEW_PACKET")
            raise
        return {
            "packet": packet.to_dict(),
            "quest_state_changed": False,
            "human_judgment_required": True,
            "external_action_performed": False,
        }

    @router.get("/api/v1/quests/{quest_id}/review-packets")
    def list_review_packets(quest_id: str) -> dict[str, Any]:
        packets = container.review_evidence_service.list_packets(quest_id)
        return {
            "quest_id": quest_id,
            "count": len(packets),
            "items": [packet.to_dict() for packet in packets],
            "external_action_performed": False,
        }

    @router.get("/api/v1/review-packets/{packet_id}")
    def get_review_packet(packet_id: str) -> dict[str, Any]:
        try:
            packet = container.review_evidence_service.get_packet(packet_id)
        except Exception as exc:
            _raise_review_error(exc, operation="GET_REVIEW_PACKET")
            raise
        judgment = container.review_evidence_service.get_judgment_for_packet(
            packet_id
        )
        return {
            "packet": packet.to_dict(),
            "judgment": judgment.to_dict() if judgment else None,
            "external_action_performed": False,
        }

    @router.post("/api/v1/quests/{quest_id}/review-gate/open")
    def open_review_gate(
        quest_id: str,
        request: OpenReviewGateRequest,
    ) -> dict[str, Any]:
        try:
            result = container.review_evidence_service.open_review_gate(
                quest_id=quest_id,
                expected_revision=request.expected_revision,
                packet_id=request.packet_id,
                identity_receipt_id=request.identity_receipt_id,
                operator_role=request.operator_role,
            )
        except Exception as exc:
            _raise_review_error(exc, operation="OPEN_REVIEW_GATE")
            raise
        return {
            "quest": _record_response(result.quest),
            "packet_id": result.packet.packet_id,
            "packet_digest": result.packet.packet_digest,
            "identity_receipt_id": result.identity_receipt_id,
            "authorization_receipt_id": result.authorization_receipt_id,
            "authorization_request_digest": (
                result.authorization_request_digest
            ),
            "human_judgment_required": True,
            "external_action_performed": False,
        }

    @router.post("/api/v1/quests/{quest_id}/review-gate/judge")
    def judge_review_gate(
        quest_id: str,
        request: ReviewJudgmentRequest,
    ) -> dict[str, Any]:
        try:
            result = container.review_evidence_service.judge_review(
                quest_id=quest_id,
                expected_revision=request.expected_revision,
                packet_id=request.packet_id,
                identity_receipt_id=request.identity_receipt_id,
                operator_role=request.operator_role,
                decision=request.decision,
                reason=request.reason,
            )
        except Exception as exc:
            _raise_review_error(exc, operation="JUDGE_REVIEW_GATE")
            raise
        return {
            "quest": _record_response(result.quest),
            "packet": result.packet.to_dict(),
            "judgment": result.judgment.to_dict(),
            "delivery_performed": False,
            "external_action_performed": False,
        }
