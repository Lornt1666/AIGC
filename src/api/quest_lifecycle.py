from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src.api.review_evidence import register_review_evidence_routes
from src.domain.quests import (
    QuestConflict,
    QuestLifecycleState,
    QuestNotFound,
    QuestStateError,
    WorkSourcePolicyError,
)


class WorkApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    reason: str | None = Field(default=None, max_length=4000)


class LocalIdentityPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]


class IdentityBoundWorkAcceptanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    identity_receipt_id: str = Field(
        pattern=r"^IDR-[A-F0-9]{24}$",
        max_length=28,
    )
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    reason: str | None = Field(default=None, max_length=4000)


class WorkAcceptanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    authorization_receipt_id: str = Field(min_length=1, max_length=300)
    authorization_request: dict[str, Any]
    reason: str | None = Field(default=None, max_length=4000)


class QuestTerminalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    reason: str = Field(min_length=1, max_length=4000)


def _record_response(record: Any) -> dict[str, Any]:
    return {
        **dict(record.payload),
        "revision": record.revision,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _raise_quest_error(exc: Exception, *, operation: str) -> None:
    if isinstance(exc, QuestNotFound):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUEST_NOT_FOUND",
                "operation": operation,
                "message": str(exc),
                "external_action_performed": False,
            },
        ) from exc
    if isinstance(exc, (QuestConflict, QuestStateError)):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "QUEST_LIFECYCLE_CONFLICT",
                "operation": operation,
                "message": str(exc),
                "external_action_performed": False,
            },
        ) from exc
    if isinstance(exc, WorkSourcePolicyError):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "QUEST_LIFECYCLE_AUTHORIZATION_DENIED",
                "operation": operation,
                "message": str(exc),
                "external_action_performed": False,
            },
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "QUEST_LIFECYCLE_INVALID_REQUEST",
                "operation": operation,
                "message": str(exc),
                "external_action_performed": False,
            },
        ) from exc
    raise exc


def _terminal_replay_or_none(
    container: Any,
    quest_id: str,
    request: QuestTerminalRequest,
    *,
    target_state: QuestLifecycleState,
) -> Any | None:
    """Recover an identical terminal command after a completed first write."""

    record = container.quest_service.get(quest_id)
    if record.payload.get("lifecycle_state") != target_state.value:
        return None
    terminal = dict(record.payload.get("terminal_decision") or {})
    identical = (
        record.revision == request.expected_revision + 1
        and terminal.get("decision") == target_state.value
        and terminal.get("operator_role") == request.operator_role
        and terminal.get("reason") == request.reason.strip()
    )
    if identical:
        return record
    raise QuestConflict(
        f"Quest already contains a different {target_state.value} decision"
    )


def build_quest_lifecycle_router(
    container: Any,
    *,
    identity_fixture_path: str | Path,
) -> APIRouter:
    router = APIRouter()
    fixture_path = Path(identity_fixture_path)

    @router.get("/api/v1/quest-board")
    def quest_board_projection(
        candidate_status: str | None = Query(default=None, max_length=40),
        quest_state: QuestLifecycleState | None = None,
    ) -> dict[str, Any]:
        candidates = container.quest_candidate_service.list_candidates()
        if candidate_status is not None:
            normalized = candidate_status.strip().upper()
            candidates = tuple(
                item
                for item in candidates
                if item.payload.get("status") == normalized
            )
        quests = container.quest_service.list_quests(state=quest_state)
        candidate_items = [_record_response(item) for item in candidates]
        quest_items = [_record_response(item) for item in quests]

        all_candidates = container.quest_candidate_service.list_candidates()
        all_quests = container.quest_service.list_quests()
        candidate_counts: dict[str, int] = {}
        quest_counts: dict[str, int] = {}
        for item in all_candidates:
            status = str(item.payload.get("status") or "UNKNOWN")
            candidate_counts[status] = candidate_counts.get(status, 0) + 1
        for item in all_quests:
            state = str(item.payload.get("lifecycle_state") or "UNKNOWN")
            quest_counts[state] = quest_counts.get(state, 0) + 1

        return {
            "candidates": candidate_items,
            "active_quests": quest_items,
            "stats": {
                "total_candidates": len(all_candidates),
                "awaiting_review": candidate_counts.get("DISCOVERED", 0),
                "qualified_candidates": candidate_counts.get("QUALIFIED", 0),
                "rejected_candidates": candidate_counts.get("REJECTED", 0),
                "total_quests": len(all_quests),
                "proposed_quests": quest_counts.get("PROPOSED", 0),
                "approval_required": quest_counts.get("APPROVAL_REQUIRED", 0),
                "work_accepted": quest_counts.get("WORK_ACCEPTED", 0),
                "rejected_quests": quest_counts.get("REJECTED", 0),
                "cancelled_quests": quest_counts.get("CANCELLED", 0),
            },
            "canonical_acceptance_semantics": {
                "work_acceptance": "WORK_ACCEPTED",
                "delivery_acceptance": "ACCEPTED_FOR_DELIVERY",
                "generic_accepted_prohibited": True,
            },
            "identity_assurance": {
                "ial": "IAL0",
                "aal": "AAL0",
                "fal": "FAL0",
            },
            "identity_bound_acceptance_available": True,
            "production_identity_authorized": False,
            "external_action_performed": False,
        }

    @router.post("/api/v1/quests/{quest_id}/request-work-approval")
    def request_work_approval(
        quest_id: str,
        request: WorkApprovalRequest,
    ) -> dict[str, Any]:
        try:
            record = container.quest_service.request_work_approval(
                quest_id,
                expected_revision=request.expected_revision,
                operator_role=request.operator_role,
                reason=request.reason,
            )
        except Exception as exc:
            _raise_quest_error(exc, operation="REQUEST_WORK_APPROVAL")
            raise
        return {
            "quest": _record_response(record),
            "next_step": "OBTAIN_PIBC_IDENTITY_RECEIPT",
            "work_accepted": False,
            "external_action_performed": False,
        }

    @router.post("/api/v1/quests/{quest_id}/local-identity-preflight")
    def local_identity_preflight(
        quest_id: str,
        request: LocalIdentityPreflightRequest,
    ) -> dict[str, Any]:
        try:
            evaluation = (
                container.local_identity_preflight_service.issue_for_quest(
                    quest_id=quest_id,
                    expected_revision=request.expected_revision,
                    operator_role=request.operator_role,
                )
            )
        except Exception as exc:
            _raise_quest_error(exc, operation="LOCAL_IDENTITY_PREFLIGHT")
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

    @router.post(
        "/api/v1/quests/{quest_id}/identity-bound-accept-work"
    )
    def identity_bound_accept_work(
        quest_id: str,
        request: IdentityBoundWorkAcceptanceRequest,
    ) -> dict[str, Any]:
        try:
            result = (
                container.identity_bound_work_acceptance_handler.execute(
                    quest_id=quest_id,
                    expected_revision=request.expected_revision,
                    identity_receipt_id=request.identity_receipt_id,
                    operator_role=request.operator_role,
                    reason=request.reason,
                )
            )
        except Exception as exc:
            _raise_quest_error(
                exc,
                operation="IDENTITY_BOUND_ACCEPT_WORK",
            )
            raise
        return {
            "quest": _record_response(result.quest),
            "identity_receipt_id": result.identity_receipt_id,
            "authorization_receipt_id": result.authorization_receipt_id,
            "authorization_request_digest": (
                result.authorization_request_digest
            ),
            "work_accepted": True,
            "external_contract_accepted": False,
            "production_identity_authorized": False,
            "external_action_performed": False,
        }

    @router.get(
        "/api/v1/quests/{quest_id}/work-acceptance-authorization-bundle"
    )
    def work_acceptance_authorization_bundle(
        quest_id: str,
    ) -> dict[str, Any]:
        try:
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            record = container.quest_service.get(quest_id)
            bundle = (
                container.quest_service.build_work_acceptance_authorization_bundle(
                    quest_id,
                    fixture,
                )
            )
        except Exception as exc:
            _raise_quest_error(exc, operation="BUILD_WORK_AUTHORIZATION_BUNDLE")
            raise
        return {
            "quest_id": quest_id,
            "quest_revision": record.revision,
            "approval_request": record.payload.get("approval_request"),
            "bundle": bundle,
            "assurance_scope": "synthetic_local_simulation_only",
            "production_identity_authorized": False,
            "external_action_performed": False,
        }

    @router.post("/api/v1/quests/{quest_id}/accept-work")
    def accept_work(
        quest_id: str,
        request: WorkAcceptanceRequest,
    ) -> dict[str, Any]:
        try:
            record = container.quest_service.accept_work(
                quest_id,
                expected_revision=request.expected_revision,
                operator_role=request.operator_role,
                authorization_receipt_id=request.authorization_receipt_id,
                authorization_request=request.authorization_request,
                reason=request.reason,
            )
        except Exception as exc:
            _raise_quest_error(exc, operation="ACCEPT_WORK")
            raise
        return {
            "quest": _record_response(record),
            "work_accepted": True,
            "external_contract_accepted": False,
            "external_action_performed": False,
        }

    @router.post("/api/v1/quests/{quest_id}/reject")
    def reject_quest(
        quest_id: str,
        request: QuestTerminalRequest,
    ) -> dict[str, Any]:
        try:
            record = _terminal_replay_or_none(
                container,
                quest_id,
                request,
                target_state=QuestLifecycleState.REJECTED,
            )
            if record is None:
                record = container.quest_service.reject(
                    quest_id,
                    expected_revision=request.expected_revision,
                    operator_role=request.operator_role,
                    reason=request.reason,
                )
        except Exception as exc:
            _raise_quest_error(exc, operation="REJECT_QUEST")
            raise
        return {
            "quest": _record_response(record),
            "work_accepted": False,
            "external_action_performed": False,
        }

    @router.post("/api/v1/quests/{quest_id}/cancel")
    def cancel_quest(
        quest_id: str,
        request: QuestTerminalRequest,
    ) -> dict[str, Any]:
        try:
            record = _terminal_replay_or_none(
                container,
                quest_id,
                request,
                target_state=QuestLifecycleState.CANCELLED,
            )
            if record is None:
                record = container.quest_service.cancel(
                    quest_id,
                    expected_revision=request.expected_revision,
                    operator_role=request.operator_role,
                    reason=request.reason,
                )
        except Exception as exc:
            _raise_quest_error(exc, operation="CANCEL_QUEST")
            raise
        return {
            "quest": _record_response(record),
            "external_action_performed": False,
        }

    register_review_evidence_routes(router, container)
    return router
