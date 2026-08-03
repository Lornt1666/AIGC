"""Credential-gated local API routes for Increment 9 Gmail runtime status and revocation."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException

from src.mission_os.decisions import verify_operator_credential
from src.mission_os.gmail_adapter import GovernedGmailDraftProvider, connector_status


def build_gmail_runtime_router(
    *,
    config_path: Path | str,
    expected_operator_credential: str | None,
    provider_factory: Callable[[], GovernedGmailDraftProvider] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/connectors/gmail", tags=["governed-gmail-draft-runtime"])

    def require(supplied: str | None) -> None:
        if not verify_operator_credential(supplied, expected_operator_credential):
            raise HTTPException(status_code=401, detail={"code": "OPERATOR_AUTHENTICATION_REQUIRED", "send_performed": False})

    @router.get("/status")
    def status(supplied: str | None = Header(default=None, alias="X-Operator-Token")) -> dict[str, Any]:
        require(supplied)
        try:
            return connector_status(config_path)
        except (OSError, ValueError, PermissionError) as exc:
            raise HTTPException(status_code=422, detail={"code": "GMAIL_RUNTIME_STATUS_REJECTED", "message": str(exc), "send_performed": False}) from exc

    @router.get("/health")
    def health(supplied: str | None = Header(default=None, alias="X-Operator-Token")) -> dict[str, Any]:
        require(supplied)
        if provider_factory is None:
            raise HTTPException(status_code=503, detail={"code": "GMAIL_PROVIDER_NOT_CONFIGURED", "send_performed": False})
        try:
            return provider_factory().health()
        except (OSError, ValueError, PermissionError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail={"code": "GMAIL_HEALTH_CHECK_FAILED", "message": str(exc), "send_performed": False}) from exc

    @router.post("/revoke")
    def revoke(supplied: str | None = Header(default=None, alias="X-Operator-Token")) -> dict[str, Any]:
        require(supplied)
        if provider_factory is None:
            raise HTTPException(status_code=503, detail={"code": "GMAIL_PROVIDER_NOT_CONFIGURED", "send_performed": False})
        try:
            return provider_factory().revoke()
        except (OSError, ValueError, PermissionError) as exc:
            raise HTTPException(status_code=422, detail={"code": "GMAIL_CREDENTIAL_REVOCATION_FAILED", "message": str(exc), "send_performed": False}) from exc

    return router
