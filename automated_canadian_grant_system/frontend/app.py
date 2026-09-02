from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from automated_canadian_grant_system.core.constitutional_guardrails import (  # noqa: E402
    ACGSGuardrailError,
    LiveIngestionBlocked,
    submission_boundary,
)
from automated_canadian_grant_system.core.models import (  # noqa: E402
    GrantApplicationRequest,
    OperatorReviewRequest,
)
from automated_canadian_grant_system.core.orchestrator import (  # noqa: E402
    GrantOrchestrator,
)
from automated_canadian_grant_system.database.storage import (  # noqa: E402
    GrantApplicationConflict,
    GrantApplicationIntegrityError,
    GrantApplicationNotFound,
    GrantApplicationStateError,
)


class SubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(
        pattern=r"^acgs_[a-f0-9]{32}$",
        max_length=37,
    )


def create_app(
    project_root: Path | None = None,
    database_path: Path | None = None,
) -> FastAPI:
    root = (project_root or PACKAGE_ROOT).resolve()
    service = GrantOrchestrator(root, database_path)
    api = FastAPI(
        title="Automated Canadian Grant System (ACGS)",
        version="1.0.0-local",
        description=(
            "Local, draft-only grant workspace. It does not retrieve remote "
            "portal data, use credentials, establish eligibility, or submit "
            "applications."
        ),
    )
    api.state.grant_orchestrator = service
    api.mount(
        "/static",
        StaticFiles(directory=root / "frontend" / "static"),
        name="static",
    )

    @api.get("/", response_class=FileResponse)
    def read_root() -> Path:
        return root / "frontend" / "templates" / "index.html"

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "system": "ACGS",
            "mode": service.policy.runtime_mode,
            "live_ingestion_enabled": False,
            "external_submission_enabled": False,
            "credential_use_enabled": False,
            "external_action_performed": False,
        }

    @api.get("/api/identity")
    def get_identity() -> dict[str, Any]:
        return service.identity_payload()

    @api.get("/api/portals")
    def get_portals() -> dict[str, Any]:
        return service.portal_payload()

    @api.get("/api/draft-payloads/{portal_id}")
    def get_draft_payload(portal_id: str) -> dict[str, Any]:
        try:
            return service.load_draft_payload(portal_id)
        except ACGSGuardrailError as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ACGS_DRAFT_PAYLOAD_UNAVAILABLE",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc

    @api.post("/api/generate_application")
    def generate_application(
        payload: GrantApplicationRequest,
    ) -> dict[str, Any]:
        try:
            return service.generate(payload)
        except ACGSGuardrailError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ACGS_GUARDRAIL_BLOCKED",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc

    @api.get("/api/applications/{application_id}")
    def get_application(application_id: str) -> dict[str, Any]:
        try:
            return service.get_application(application_id)
        except GrantApplicationNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ACGS_APPLICATION_NOT_FOUND",
                    "message": "Local application was not found.",
                    "external_action_performed": False,
                },
            ) from exc

    @api.post("/api/applications/{application_id}/review")
    def review_application(
        application_id: str,
        payload: OperatorReviewRequest,
    ) -> dict[str, Any]:
        try:
            return service.review_application(application_id, payload)
        except GrantApplicationNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ACGS_APPLICATION_NOT_FOUND",
                    "message": "Local application was not found.",
                    "external_action_performed": False,
                },
            ) from exc
        except (GrantApplicationConflict, GrantApplicationStateError) as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ACGS_REVIEW_STATE_CONFLICT",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc
        except ACGSGuardrailError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ACGS_REVIEW_GUARDRAIL_BLOCKED",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc

    @api.get("/api/applications/{application_id}/export")
    def local_export(application_id: str) -> JSONResponse:
        try:
            artifact = service.local_export(application_id)
        except GrantApplicationNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ACGS_APPLICATION_NOT_FOUND",
                    "message": "Local application was not found.",
                    "external_action_performed": False,
                },
            ) from exc
        except (GrantApplicationIntegrityError, GrantApplicationStateError) as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ACGS_LOCAL_EXPORT_BLOCKED",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc
        return JSONResponse(
            content=artifact,
            headers={
                "Content-Disposition": (
                    f'inline; filename="{application_id}-local-review.json"'
                )
            },
        )

    @api.post("/api/ingestion/{portal_id}")
    def request_ingestion(portal_id: str) -> dict[str, Any]:
        try:
            service.request_live_ingestion(portal_id)
        except LiveIngestionBlocked as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "LIVE_INGESTION_BLOCKED",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc
        except ACGSGuardrailError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ACGS_GUARDRAIL_BLOCKED",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={
                "code": "ACGS_UNREACHABLE_INGESTION_STATE",
                "external_action_performed": False,
            },
        )

    @api.post("/api/submit_application")
    def submit_application(payload: SubmissionRequest) -> dict[str, Any]:
        boundary = submission_boundary(service.policy)
        raise HTTPException(
            status_code=409,
            detail={
                "application_id": payload.application_id,
                **boundary,
            },
        )

    return api


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
