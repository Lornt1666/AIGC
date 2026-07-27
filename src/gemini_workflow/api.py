from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException

from .evidence import EvidenceStoreError, GcsEvidenceStore, JsonlEvidenceStore
from .models import HumanDecisionRequest, OpportunityIntake
from .provider import GeminiProviderError, VertexGeminiProvider
from .service import GeminiWorkflowService, GeminiWorkflowStateError
from .settings import (
    GeminiWorkflowConfigurationError,
    GeminiWorkflowSettings,
)


_SERVICE_OVERRIDE: GeminiWorkflowService | None = None


def set_service_override(service: GeminiWorkflowService | None) -> None:
    global _SERVICE_OVERRIDE
    _SERVICE_OVERRIDE = service
    build_live_service.cache_clear()


@lru_cache(maxsize=1)
def build_live_service() -> GeminiWorkflowService:
    settings = GeminiWorkflowSettings.from_env()
    if not settings.enabled:
        raise GeminiWorkflowConfigurationError(
            "Set AIGC_GEMINI_ENABLED=true after live configuration is approved"
        )
    if settings.evidence_backend == "gcs":
        store = GcsEvidenceStore(
            project_id=settings.project_id,
            bucket_name=settings.evidence_bucket,
            prefix=settings.evidence_prefix,
        )
    else:
        assert settings.evidence_path is not None
        store = JsonlEvidenceStore(settings.evidence_path)
    return GeminiWorkflowService(
        provider=VertexGeminiProvider(settings),
        evidence_store=store,
    )


def get_service() -> GeminiWorkflowService:
    return _SERVICE_OVERRIDE or build_live_service()


def safe_status() -> dict[str, Any]:
    try:
        settings = GeminiWorkflowSettings.from_env()
        error = None
    except GeminiWorkflowConfigurationError as exc:
        settings = None
        error = str(exc)
    return {
        "enabled": bool(settings and settings.enabled),
        "configured": settings is not None and settings.enabled and error is None,
        "provider": "google_vertex_ai",
        "model": settings.model if settings else "",
        "location": settings.location if settings else "",
        "evidence_backend": settings.evidence_backend if settings else "",
        "human_review_required": True,
        "external_action_allowed": False,
        "configuration_error": error,
    }


def create_router(auth_dependency: Callable[..., Any]) -> APIRouter:
    router = APIRouter(
        prefix="/api/gemini",
        tags=["governed-gemini"],
        dependencies=[Depends(auth_dependency)],
    )

    @router.get("/status")
    def status() -> dict[str, Any]:
        return safe_status()

    @router.post("/workflows")
    def create_workflow(intake: OpportunityIntake) -> dict[str, Any]:
        try:
            record = get_service().create_workflow(intake)
            return record.model_dump(mode="json")
        except GeminiWorkflowConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except GeminiWorkflowStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except GeminiProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except EvidenceStoreError as exc:
            raise HTTPException(
                status_code=503,
                detail="Workflow evidence could not be persisted",
            ) from exc

    @router.get("/workflows/{run_id}")
    def get_workflow(run_id: str) -> dict[str, Any]:
        try:
            records = get_service().get_workflow(run_id)
            return {
                "run_id": run_id,
                "events": [
                    item.model_dump(mode="json") for item in records
                ],
            }
        except GeminiWorkflowStateError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/workflows/{run_id}/decision")
    def decide(
        run_id: str,
        request: HumanDecisionRequest,
    ) -> dict[str, Any]:
        try:
            record = get_service().decide(run_id, request)
            return record.model_dump(mode="json")
        except (GeminiWorkflowStateError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except EvidenceStoreError as exc:
            raise HTTPException(
                status_code=503,
                detail="Workflow evidence could not be persisted",
            ) from exc

    return router
