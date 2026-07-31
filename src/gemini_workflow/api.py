from __future__ import annotations

from functools import lru_cache
import os
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from .control_store import (
    EmergencyStopActiveError,
    IdempotencyConflictError,
    PostgresRuntimeControlStore,
    RuntimeControlError,
    RuntimeQuotaExceededError,
)
from .evidence import EvidenceStoreError, GcsEvidenceStore, JsonlEvidenceStore
from .models import HumanDecisionRequest, OperatorIdentity, OpportunityIntake
from .provider import GeminiProviderError, VertexGeminiProvider
from .runtime_limits import RuntimeLimits
from .secret_broker import OmegaXSecretAccess, SecretBrokerError
from .service import (
    GeminiWorkflowInProgressError,
    GeminiWorkflowService,
    GeminiWorkflowStateError,
)
from .settings import (
    GeminiWorkflowConfigurationError,
    GeminiWorkflowSettings,
)


_SERVICE_OVERRIDE: GeminiWorkflowService | None = None


class EmergencyStopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=2_000)


class EmergencyClearRequest(EmergencyStopRequest):
    expected_epoch: int = Field(ge=0)
    exact_phrase: str = Field(min_length=1, max_length=200)


def workflow_controls(
    status: str,
    *,
    decision_recorded: bool = False,
) -> dict[str, Any]:
    """Project canonical workflow state into additive UI capabilities."""

    allowed_decisions: list[str] = []
    if not decision_recorded:
        if status == "pending_human_review":
            allowed_decisions = ["approve", "deny", "revise"]
        elif status in {"clarification_required", "blocked"}:
            allowed_decisions = ["deny", "revise"]
    return {
        "allowed_decisions": allowed_decisions,
        "human_review_required": True,
        "approval_scope": "internal_use_only",
        "external_action_allowed": False,
        "operator_record_kind": "accountable_attestation",
    }


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
    control_dsn = settings.control_dsn
    if settings.environment == "production":
        try:
            control_dsn, _receipt = OmegaXSecretAccess.from_environment(
                project_id=settings.project_id
            ).resolve("gemini-runtime-control-dsn")
        except SecretBrokerError as exc:
            raise GeminiWorkflowConfigurationError(
                "The durable runtime-control secret could not be resolved"
            ) from exc
    return GeminiWorkflowService(
        provider=VertexGeminiProvider(settings),
        evidence_store=store,
        control_store=PostgresRuntimeControlStore.from_dsn(
            control_dsn
        ),
        runtime_limits=RuntimeLimits.from_env(),
        source_revision=settings.source_revision,
        runtime_revision=settings.runtime_revision,
        model_name=settings.model,
        max_output_tokens=settings.max_output_tokens,
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


def create_router(
    auth_dependency: Callable[..., Any],
    runtime_admin_dependency: Callable[..., Any] | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/gemini",
        tags=["governed-gemini"],
    )

    @router.get("/status")
    def status(
        _actor: OperatorIdentity = Depends(auth_dependency),
    ) -> dict[str, Any]:
        return safe_status()

    @router.post("/workflows")
    def create_workflow(
        intake: OpportunityIntake,
        response: Response,
        actor: OperatorIdentity = Depends(auth_dependency),
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
        ),
    ) -> dict[str, Any]:
        if idempotency_key is None and (
            os.environ.get("AIGC_ENV", "development").strip().lower()
            == "production"
        ):
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key is required",
            )
        try:
            service = get_service()
            record = service.create_workflow(
                intake,
                actor=actor,
                idempotency_key=idempotency_key,
            )
            result = record.model_dump(mode="json")
            result["runtime_receipt"] = _runtime_receipt_payload(
                service.runtime_receipt(record.run_id),
                record=record,
            )
            result["api_contract_version"] = "1.1"
            result["status_url"] = (
                f"/api/gemini/workflows/{record.run_id}"
            )
            result["controls"] = workflow_controls(record.status)
            return result
        except GeminiWorkflowInProgressError as exc:
            response.status_code = 202
            return {
                "api_contract_version": "1.1",
                "run_id": exc.run_id,
                "status": "executing",
                "status_url": f"/api/gemini/workflows/{exc.run_id}",
                "model_api_call_repeated": False,
                "controls": workflow_controls("executing"),
            }
        except GeminiWorkflowConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeQuotaExceededError as exc:
            raise HTTPException(
                status_code=429,
                detail=str(exc),
                headers={"Retry-After": str(exc.retry_after_seconds)},
            ) from exc
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except EmergencyStopActiveError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeControlError as exc:
            raise HTTPException(
                status_code=503,
                detail="Gemini runtime controls are unavailable",
            ) from exc
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
    def get_workflow(
        run_id: str,
        _actor: OperatorIdentity = Depends(auth_dependency),
    ) -> dict[str, Any]:
        try:
            service = get_service()
            records = service.get_workflow(run_id)
            decision_recorded = any(
                item.event_type == "operator_decision" for item in records
            )
            current_status = records[-1].status
            return {
                "api_contract_version": "1.1",
                "run_id": run_id,
                "current_status": current_status,
                "controls": workflow_controls(
                    current_status,
                    decision_recorded=decision_recorded,
                ),
                "runtime_receipt": _runtime_receipt_payload(
                    service.runtime_receipt(run_id),
                    record=records[-1],
                ),
                "events": [
                    item.model_dump(mode="json") for item in records
                ],
            }
        except GeminiWorkflowStateError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeControlError as exc:
            raise HTTPException(
                status_code=503,
                detail="Gemini runtime controls are unavailable",
            ) from exc
        except EvidenceStoreError as exc:
            raise HTTPException(
                status_code=503,
                detail="Workflow evidence could not be read",
            ) from exc

    @router.post("/workflows/{run_id}/decision")
    def decide(
        run_id: str,
        request: HumanDecisionRequest,
        actor: OperatorIdentity = Depends(auth_dependency),
    ) -> dict[str, Any]:
        try:
            service = get_service()
            record = service.decide(
                run_id,
                request,
                actor=actor,
            )
            result = record.model_dump(mode="json")
            result["decision_receipt"] = _runtime_receipt_payload(
                service.runtime_receipt(run_id),
                record=record,
            )
            result["api_contract_version"] = "1.1"
            result["status_url"] = f"/api/gemini/workflows/{run_id}"
            result["controls"] = workflow_controls(
                record.status,
                decision_recorded=True,
            )
            return result
        except (GeminiWorkflowStateError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except EmergencyStopActiveError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeControlError as exc:
            raise HTTPException(
                status_code=503,
                detail="Gemini runtime controls are unavailable",
            ) from exc
        except EvidenceStoreError as exc:
            raise HTTPException(
                status_code=503,
                detail="Workflow evidence could not be persisted",
            ) from exc

    @router.get("/runtime/emergency-stop")
    def emergency_state(
        _actor: OperatorIdentity = Depends(auth_dependency),
    ) -> dict[str, Any]:
        state = get_service().emergency_state()
        return {
            "active": state.active,
            "stop_epoch": state.stop_epoch,
            "reason_present": bool(state.reason),
            "updated_at": state.updated_at,
        }

    @router.post("/runtime/emergency-stop")
    def activate_emergency_stop(
        request: EmergencyStopRequest,
        actor: OperatorIdentity = Depends(auth_dependency),
    ) -> dict[str, Any]:
        try:
            state = get_service().activate_emergency_stop(
                actor=actor,
                reason=request.reason,
            )
            return {
                "active": state.active,
                "stop_epoch": state.stop_epoch,
                "updated_at": state.updated_at,
            }
        except (GeminiWorkflowStateError, ValueError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeControlError as exc:
            raise HTTPException(
                status_code=503,
                detail="Gemini runtime controls are unavailable",
            ) from exc

    if runtime_admin_dependency is not None:

        @router.post("/runtime/emergency-stop/clear")
        def clear_emergency_stop(
            request: EmergencyClearRequest,
            actor: OperatorIdentity = Depends(runtime_admin_dependency),
        ) -> dict[str, Any]:
            try:
                state = get_service().clear_emergency_stop(
                    actor=actor,
                    reason=request.reason,
                    expected_epoch=request.expected_epoch,
                    exact_phrase=request.exact_phrase,
                )
                return {
                    "active": state.active,
                    "stop_epoch": state.stop_epoch,
                    "updated_at": state.updated_at,
                }
            except (GeminiWorkflowStateError, ValueError) as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except EmergencyStopActiveError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except RuntimeControlError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Gemini runtime controls are unavailable",
                ) from exc

    return router


def _runtime_receipt_payload(
    reservation: Any,
    *,
    record: Any | None = None,
) -> dict[str, Any]:
    return {
        "run_id": reservation.run_id,
        "state": reservation.state,
        "stop_epoch": reservation.stop_epoch,
        "reserved_tokens": reservation.reserved_tokens,
        "actual_tokens": reservation.actual_tokens,
        "source_revision": reservation.source_revision or None,
        "runtime_revision": (
            (
                record.payload.get("runtime_revision")
                or record.payload.get("binds_to_runtime_revision")
            )
            if record is not None
            else None
        ),
        "model": reservation.model or None,
        "image_digest": os.environ.get("AIGC_IMAGE_DIGEST", "").strip()
        or None,
        "execution_event_id": reservation.execution_event_id,
        "evidence_object_uri": reservation.evidence_object_uri,
        "evidence_generation": reservation.evidence_generation,
        "decision_event_id": getattr(
            reservation,
            "decision_event_id",
            None,
        ),
        "decision_object_uri": getattr(
            reservation,
            "decision_object_uri",
            None,
        ),
        "decision_generation": getattr(
            reservation,
            "decision_generation",
            None,
        ),
    }
