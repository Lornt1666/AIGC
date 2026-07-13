from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.api.composition import build_container
from src.domain.identity import IdentityBoundaryError


class IdentityContextVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_type: Literal[
        "LOCAL_DEVELOPMENT",
        "OIDC",
        "WORKLOAD_IDENTITY",
    ]
    assertion: dict[str, Any]
    membership_id: str = Field(min_length=1, max_length=160)
    session_id: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    exact_revision: str = Field(min_length=1, max_length=80)
    production_mode: bool = False


def create_identity_boundary_app(
    database_path: str | Path | None = None,
    *,
    evaluation_time: datetime | None = None,
) -> FastAPI:
    container = build_container(database_path)
    api = FastAPI(
        title="AIGC PIBC-v1 Internal Preflight API",
        version="1.0.0-local",
        description=(
            "Local-only, provider-neutral identity preflight. "
            "The configured adapter is fixture-backed and cannot establish "
            "production identity. No external action is performed."
        ),
    )
    api.state.container = container
    api.state.database_path = str(container.database_path)

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "component": "production_identity_boundary_v1",
            "runtime_authority": "LOCAL_SIMULATION",
            "production_identity_configured": False,
            "external_action_performed": False,
        }

    @api.post("/api/v1/identity/context/verify")
    def verify_identity_context(
        request: IdentityContextVerifyRequest,
    ) -> dict[str, Any]:
        try:
            return container.identity_boundary_service.evaluate(
                provider_type=request.provider_type,
                raw_assertion=request.assertion,
                membership_id=request.membership_id,
                session_id=request.session_id,
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                exact_revision=request.exact_revision,
                production_mode=request.production_mode,
                now=evaluation_time,
            ).to_dict()
        except IdentityBoundaryError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "IDENTITY_BOUNDARY_CONTRACT_FAILURE",
                    "message": str(exc),
                    "external_action_performed": False,
                },
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "IDENTITY_BOUNDARY_INTERNAL_FAILURE",
                    "message": "Identity preflight failed closed.",
                    "external_action_performed": False,
                },
            ) from exc

    @api.get("/api/v1/identity/receipts/{receipt_id}")
    def get_identity_receipt(receipt_id: str) -> dict[str, Any]:
        receipt = container.identity_boundary_service.get_receipt(receipt_id)
        if receipt is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "IDENTITY_RECEIPT_NOT_FOUND",
                    "external_action_performed": False,
                },
            )
        return receipt.to_dict()

    return api


app = create_identity_boundary_app()
