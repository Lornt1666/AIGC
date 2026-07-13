from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from src.application import QuestCandidateApplicationService
from src.core.identity.principal_authority_binding import PrincipalAuthorityBindingKernel
from src.domain.quests import (
    QuestCandidateConflict,
    QuestCandidateNotFound,
    QuestCandidateStateError,
    QuestCandidateStatus,
    WorkSourcePolicyError,
)
from src.infrastructure.persistence.sqlite import (
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteQuestCandidateRepository,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "governance" / "identity" / "local_identity_simulation.json"
MIGRATIONS = ROOT / "migrations" / "sqlite"
WORK_SOURCE_CATALOG = ROOT / "config" / "aigc_work_source_gate_catalog.json"
QUEST_CANDIDATE_SCHEMA = ROOT / "schemas" / "quest_candidate.schema.json"


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
    deadline_at: str | None = None
    location: str | None = Field(default=None, max_length=500)
    remote_status: Literal["remote", "hybrid", "onsite", "unspecified"] = "unspecified"
    issuer: str | None = Field(default=None, max_length=500)
    risk_class: Literal["unassessed", "low", "medium", "high", "restricted"] = "unassessed"
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
    observed_at: str | None = None


class QuestCandidateQualifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    decision: Literal["QUALIFY"]
    operator_role: Literal["ACCOUNTABLE_OPERATOR"]
    reason: str | None = Field(default=None, max_length=4000)


def _record_response(record: Any) -> dict[str, Any]:
    return {
        **dict(record.payload),
        "revision": record.revision,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def create_app(database_path: str | Path | None = None) -> FastAPI:
    api = FastAPI(
        title="AIGC Local Operator API",
        version="1.1.0-local",
        description=(
            "Localhost-only, non-production AIGC control surface. "
            "IAL0/AAL0/FAL0. Quest-candidate intake is internal only."
        ),
    )

    resolved_database = Path(
        database_path
        or os.getenv("AIGC_DATABASE_PATH")
        or ROOT / "memory" / "aigc_state.sqlite"
    )
    factory = SQLiteConnectionFactory(resolved_database)
    SQLiteMigrator(factory, MIGRATIONS).apply_all()
    candidate_service = QuestCandidateApplicationService(
        SQLiteQuestCandidateRepository(factory),
        catalog_path=WORK_SOURCE_CATALOG,
        schema_path=QUEST_CANDIDATE_SCHEMA,
        exact_revision=os.getenv("AIGC_EXACT_REVISION", "LOCAL_UNVERIFIED"),
    )
    receipts: dict[str, dict[str, Any]] = {}

    api.state.database_path = str(resolved_database)
    api.state.quest_candidate_service = candidate_service

    @api.get("/", response_class=HTMLResponse)
    def operator_console() -> str:
        return """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>AIGC Local Operator</title><style>body{font-family:system-ui;max-width:760px;margin:2rem auto;padding:0 1rem}a,button{font-size:1rem}code{background:#eee;padding:.15rem .3rem}section{margin:1.5rem 0}*:focus{outline:3px solid currentColor;outline-offset:3px}</style></head><body><main><h1>AIGC Local Operator API</h1><p><strong>Local simulation only.</strong> Production identity and external actions remain blocked.</p><section><h2>Status</h2><ul><li><a href='/health'>Health</a></li><li><a href='/api/v1/system/status'>System status</a></li><li><a href='/api/v1/readiness'>Readiness</a></li><li><a href='/api/v1/quests/sources'>Work-source catalog</a></li><li><a href='/api/v1/quests/candidates'>Quest candidates</a></li><li><a href='/docs'>OpenAPI</a></li></ul></section><section><h2>Boundary</h2><p><code>127.0.0.1</code> only. Candidate ingestion records supplied data; it does not scrape, apply, bid, message, use credentials, or create external side effects.</p></section></main></body></html>"""

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "mode": "local_simulation",
            "persistence": "sqlite",
            "external_action_performed": False,
        }

    @api.get("/api/v1/system/status")
    def system_status() -> dict[str, Any]:
        return {
            "system": "AIGC",
            "mode": "local_simulation",
            "identity_assurance": {"ial": "IAL0", "aal": "AAL0", "fal": "FAL0"},
            "production_identity_access": "blocking",
            "deployment_authorized": False,
            "quest_candidate_intake": "internal_persistent",
            "external_action_performed": False,
        }

    @api.get("/api/v1/readiness")
    def readiness() -> dict[str, Any]:
        return {
            "production_ready": False,
            "production_identity_access": {"state": "partial", "blocking": True},
            "evidence_scope": "local_behavioral_simulation",
            "exact_main_ci_observed": False,
            "quest_creation_from_candidate": {
                "state": "qualification_only",
                "blocking_reason": "canonical_quest_lifecycle_requires_separate_ratification_and_implementation",
            },
            "external_action_performed": False,
        }

    @api.get("/api/v1/identity/contracts")
    def identity_contracts() -> dict[str, Any]:
        contract_root = ROOT / "governance" / "schemas" / "identity"
        return {
            "contracts": sorted(path.name for path in contract_root.glob("*.schema.json")),
            "external_action_performed": False,
        }

    @api.post("/api/v1/identity/authorize")
    def authorize(bundle: AuthorizationBundle) -> dict[str, Any]:
        kernel = PrincipalAuthorityBindingKernel()
        try:
            decision = kernel.evaluate(
                request=bundle.request,
                principals=bundle.principals,
                memberships=bundle.memberships,
                sessions=bundle.sessions,
                policies=bundle.policies,
                approvals=bundle.approvals,
                revocations=bundle.revocations,
                now=datetime.now(timezone.utc),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "AUTHORIZATION_EVALUATION_FAILED", "message": str(exc)},
            ) from exc
        receipt = dict(decision.receipt)
        receipt_id = str(
            receipt.get("receipt_id")
            or receipt.get("decision_id")
            or bundle.request.get("request_id")
        )
        receipts[receipt_id] = receipt
        return {
            "result": decision.result,
            "passed": decision.passed,
            "reason_codes": list(decision.reason_codes),
            "receipt_id": receipt_id,
            "receipt": receipt,
        }

    @api.get("/api/v1/audit/receipts/{receipt_id}")
    def audit_receipt(receipt_id: str) -> dict[str, Any]:
        receipt = receipts.get(receipt_id)
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
        items = candidate_service.list_sources(category=category)
        return {
            "catalog_version": candidate_service.catalog.catalog_version,
            "count": len(items),
            "items": items,
            "catalog_inclusion_grants_external_action": False,
            "external_action_performed": False,
        }

    @api.post("/api/v1/quests/candidates/ingest", status_code=201)
    def ingest_quest_candidate(
        request: QuestCandidateIngestRequest,
    ) -> dict[str, Any]:
        try:
            record = candidate_service.ingest(
                request.model_dump(mode="json")
            )
        except WorkSourcePolicyError as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "WORK_SOURCE_POLICY_DENIED", "message": str(exc)},
            ) from exc
        except QuestCandidateConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "QUEST_CANDIDATE_CONFLICT", "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "QUEST_CANDIDATE_INVALID", "message": str(exc)},
            ) from exc
        return _record_response(record)

    @api.get("/api/v1/quests/candidates")
    def list_quest_candidates(
        status: QuestCandidateStatus | None = None,
    ) -> dict[str, Any]:
        records = candidate_service.list_candidates(status=status)
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
            record = candidate_service.qualify(
                candidate_id,
                expected_revision=request.expected_revision,
                operator_role=request.operator_role,
                decision=request.decision,
                reason=request.reason,
            )
        except QuestCandidateNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "QUEST_CANDIDATE_NOT_FOUND", "message": str(exc)},
            ) from exc
        except (QuestCandidateConflict, QuestCandidateStateError) as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "QUEST_CANDIDATE_STATE_CONFLICT", "message": str(exc)},
            ) from exc
        except WorkSourcePolicyError as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "QUEST_CANDIDATE_QUALIFICATION_DENIED", "message": str(exc)},
            ) from exc
        return _record_response(record)

    return api


app = create_app()
