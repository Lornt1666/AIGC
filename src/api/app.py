from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from src.api.composition import build_container
from src.api.quest_board import QUEST_BOARD_HTML
from src.application import (
    OpportunityScoutPolicyError,
    OpportunityScoutUnavailable,
)
from src.domain.quests import (
    QuestCandidateConflict,
    QuestCandidateNotFound,
    QuestCandidateStateError,
    QuestCandidateStatus,
    QuestConflict,
    QuestLifecycleState,
    QuestNotFound,
    QuestStateError,
    WorkSourcePolicyError,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "governance" / "identity" / "local_identity_simulation.json"


class AuthorizationBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: dict[str, Any]
    principals: list[dict[str, Any]]
    memberships: list[dict[str, Any]]
    sessions: list[dict[str, Any]]
    policies: list[dict[str, Any]]
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    revocations: list[dict[str, Any]] = Field(default_factory=list)


class BudgetRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class QuestCandidateIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str | None = Field(
        default=None,
        pattern=r"^cand_[A-Za-z0-9_-]{6,80}$",
    )
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{1,79}$")
    source_url: str = Field(pattern=r"^https?://", max_length=4000)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=50000)
    proposed_quest_title: str | None = Field(default=None, max_length=500)
    domain: str = Field(pattern=r"^[a-z0-9][a-z0-9_\-]{1,119}$")
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    budget_range: BudgetRange | None = None
    compensation_text: str | None = Field(default=None, max_length=1000)
    deadline_days: int | None = Field(default=None, ge=1, le=3650)
    deadline_at: datetime | None = None
    location: str | None = Field(default=None, max_length=500)
    remote_status: Literal[
        "remote",
        "hybrid",
        "onsite",
        "unspecified",
    ] = "unspecified"
    issuer: str | None = Field(default=None, max_length=500)
    risk_class: Literal[
        "unassessed",
        "low",
        "medium",
        "high",
        "restricted",
    ] = "unassessed"
    rights_status: Literal[
        "public_posting",
        "account_visible_posting",
        "consented_feed",
        "official_api_record",
        "manual_operator_entry",
        "unknown",
    ] = "public_posting"
    ingestion_channel: Literal[
        "manual",
        "existing_read_only_adapter",
        "approved_read_only_adapter",
    ] = "manual"
    observed_at: datetime | None = None


class QuestCandidateQualifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    decision: Literal["QUALIFY"]
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    reason: str | None = Field(default=None, max_length=4000)


class QuestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_candidate_revision: int = Field(ge=1)
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    purpose: str | None = Field(default=None, min_length=1, max_length=50000)
    scope: str | None = Field(default=None, min_length=1, max_length=20000)
    non_scope: str | None = Field(default=None, min_length=1, max_length=20000)
    acceptance_criteria: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    budget: BudgetRange | None = None
    deadline_at: datetime | None = None


def _record_response(record: Any) -> dict[str, Any]:
    return {
        **dict(record.payload),
        "revision": record.revision,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def create_app(database_path: str | Path | None = None) -> FastAPI:
    container = build_container(database_path)
    api = FastAPI(
        title="AIGC Local Operator API",
        version="1.3.0-local",
        description=(
            "Localhost-only, non-production AIGC control surface. "
            "IAL0/AAL0/FAL0. Opportunity discovery is fixed-source and "
            "read-only; candidate intake and Quest creation are internal only; "
            "external actions remain blocked."
        ),
    )
    api.state.container = container
    api.state.database_path = str(container.database_path)

    @api.get("/", response_class=HTMLResponse)
    @api.get("/quest-board", response_class=HTMLResponse)
    def quest_board() -> str:
        return QUEST_BOARD_HTML

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "mode": "local_simulation",
            "persistence": "sqlite",
            "quest_board": "available",
            "opportunity_scout": "available_read_only",
            "external_action_performed": False,
        }

    @api.get("/api/v1/system/status")
    def system_status() -> dict[str, Any]:
        return {
            "system": "AIGC",
            "mode": "local_simulation",
            "identity_assurance": {
                "ial": "IAL0",
                "aal": "AAL0",
                "fal": "FAL0",
            },
            "authorization_receipt_persistence": "sqlite_local",
            "opportunity_scout": "fixed_source_read_only",
            "quest_candidate_intake": "internal_persistent",
            "quest_creation": "qualified_candidate_to_proposed_quest",
            "canonical_acceptance_semantics": {
                "work_acceptance": "WORK_ACCEPTED",
                "delivery_acceptance": "ACCEPTED_FOR_DELIVERY",
                "generic_accepted_prohibited": True,
            },
            "production_identity_access": "blocking",
            "deployment_authorized": False,
            "external_action_performed": False,
        }

    @api.get("/api/v1/readiness")
    def readiness() -> dict[str, Any]:
        return {
            "production_ready": False,
            "production_identity_access": {
                "state": "partial",
                "blocking": True,
            },
            "authorization_receipt_persistence": {
                "state": "implemented_internal",
                "blocking": False,
            },
            "opportunity_scout": {
                "state": "implemented_internal_read_only",
                "arbitrary_urls_allowed": False,
                "credentials_used": False,
                "blocking": False,
            },
            "quest_candidate_intake": {
                "state": "implemented_internal",
                "blocking": False,
            },
            "quest_creation_from_candidate": {
                "state": "implemented_internal",
                "initial_state": "PROPOSED",
                "work_accepted": False,
                "blocking": False,
            },
            "work_acceptance_transition": {
                "state": "not_implemented",
                "blocking": True,
            },
            "evidence_scope": "local_behavioral_simulation",
            "exact_main_ci_observed": False,
            "external_action_performed": False,
        }

    @api.get("/api/v1/identity/contracts")
    def identity_contracts() -> dict[str, Any]:
        contract_root = ROOT / "governance" / "schemas" / "identity"
        return {
            "contracts": sorted(
                path.name
                for path in contract_root.glob("*.schema.json")
            ),
            "external_action_performed": False,
        }

    @api.post("/api/v1/identity/authorize")
    def authorize(bundle: AuthorizationBundle) -> dict[str, Any]:
        try:
            return container.authorization_service.authorize(
                request=bundle.request,
                principals=bundle.principals,
                memberships=bundle.memberships,
                sessions=bundle.sessions,
                policies=bundle.policies,
                approvals=bundle.approvals,
                revocations=bundle.revocations,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "AUTHORIZATION_EVALUATION_FAILED",
                    "message": str(exc),
                },
            ) from exc

    @api.get("/api/v1/audit/receipts/{receipt_id}")
    def audit_receipt(receipt_id: str) -> dict[str, Any]:
        receipt = container.authorization_service.get_receipt(receipt_id)
        if receipt is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "RECEIPT_NOT_FOUND"},
            )
        return receipt

    @api.get("/api/v1/identity/example")
    def identity_example() -> dict[str, Any]:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    @api.get("/api/v1/quests/sources")
    def quest_sources(
        category: str | None = Query(default=None, max_length=120),
    ) -> dict[str, Any]:
        items = container.quest_candidate_service.list_sources(
            category=category
        )
        return {
            "catalog_version": (
                container.quest_candidate_service.catalog.catalog_version
            ),
            "count": len(items),
            "items": items,
            "catalog_inclusion_grants_external_action": False,
            "external_action_performed": False,
        }

    @api.post("/api/v1/opportunities/discover")
    def discover_opportunities(
        limit: int = Query(default=5, ge=1, le=25),
        source_id: list[str] | None = Query(default=None),
    ) -> dict[str, Any]:
        try:
            return container.opportunity_scout_service.discover(
                limit=limit,
                source_ids=source_id,
            )
        except OpportunityScoutPolicyError as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "OPPORTUNITY_SCOUT_POLICY_DENIED",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc
        except OpportunityScoutUnavailable as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "OPPORTUNITY_SOURCES_UNAVAILABLE",
                    "message": str(exc),
                    "report": exc.report,
                    "external_action_performed": False,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "OPPORTUNITY_SCOUT_INVALID_REQUEST",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc

    @api.post("/api/v1/quests/candidates/ingest", status_code=201)
    def ingest_quest_candidate(
        request: QuestCandidateIngestRequest,
    ) -> dict[str, Any]:
        try:
            record = container.quest_candidate_service.ingest(
                request.model_dump(mode="json")
            )
        except WorkSourcePolicyError as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "WORK_SOURCE_POLICY_DENIED",
                    "message": str(exc),
                },
            ) from exc
        except QuestCandidateConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "QUEST_CANDIDATE_CONFLICT",
                    "message": str(exc),
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "QUEST_CANDIDATE_INVALID",
                    "message": str(exc),
                },
            ) from exc
        return _record_response(record)

    @api.get("/api/v1/quests/candidates")
    def list_quest_candidates(
        status: QuestCandidateStatus | None = None,
    ) -> dict[str, Any]:
        records = container.quest_candidate_service.list_candidates(
            status=status
        )
        items = [_record_response(record) for record in records]
        return {
            "count": len(items),
            "items": items,
            "external_action_performed": False,
        }

    @api.post("/api/v1/quests/candidates/{candidate_id}/qualify")
    def qualify_quest_candidate(
        candidate_id: str,
        request: QuestCandidateQualifyRequest,
    ) -> dict[str, Any]:
        try:
            record = container.quest_candidate_service.qualify(
                candidate_id,
                expected_revision=request.expected_revision,
                operator_role=request.operator_role,
                decision=request.decision,
                reason=request.reason,
            )
        except QuestCandidateNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "QUEST_CANDIDATE_NOT_FOUND",
                    "message": str(exc),
                },
            ) from exc
        except (
            QuestCandidateConflict,
            QuestCandidateStateError,
        ) as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "QUEST_CANDIDATE_STATE_CONFLICT",
                    "message": str(exc),
                },
            ) from exc
        except WorkSourcePolicyError as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "QUEST_CANDIDATE_QUALIFICATION_DENIED",
                    "message": str(exc),
                },
            ) from exc
        return _record_response(record)

    @api.post(
        "/api/v1/quests/candidates/{candidate_id}/create-quest",
        status_code=201,
    )
    def create_quest_from_candidate(
        candidate_id: str,
        request: QuestCreateRequest,
    ) -> dict[str, Any]:
        try:
            result = container.quest_service.create_from_candidate(
                candidate_id,
                expected_candidate_revision=(
                    request.expected_candidate_revision
                ),
                operator_role=request.operator_role,
                purpose=request.purpose,
                scope=request.scope,
                non_scope=request.non_scope,
                acceptance_criteria=request.acceptance_criteria,
                budget=(
                    request.budget.model_dump(mode="json")
                    if request.budget
                    else None
                ),
                deadline_at=request.deadline_at,
            )
        except QuestNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "QUEST_CANDIDATE_NOT_FOUND",
                    "message": str(exc),
                },
            ) from exc
        except (QuestConflict, QuestStateError) as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "QUEST_CREATION_CONFLICT",
                    "message": str(exc),
                },
            ) from exc
        except WorkSourcePolicyError as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "QUEST_CREATION_DENIED",
                    "message": str(exc),
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "QUEST_INVALID",
                    "message": str(exc),
                },
            ) from exc
        return {
            "candidate": _record_response(result.candidate),
            "quest": _record_response(result.quest),
            "work_accepted": False,
            "external_action_performed": False,
        }

    @api.get("/api/v1/quests")
    def list_quests(
        state: QuestLifecycleState | None = None,
    ) -> dict[str, Any]:
        records = container.quest_service.list_quests(state=state)
        items = [_record_response(record) for record in records]
        return {
            "count": len(items),
            "items": items,
            "external_action_performed": False,
        }

    @api.get("/api/v1/quests/{quest_id}")
    def get_quest(quest_id: str) -> dict[str, Any]:
        try:
            return _record_response(container.quest_service.get(quest_id))
        except QuestNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "QUEST_NOT_FOUND",
                    "message": str(exc),
                },
            ) from exc

    return api


app = create_app()
