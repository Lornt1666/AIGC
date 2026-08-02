"""Loopback-only API surface for Ω Mission OS projections and operator decisions."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.mission_os.activation import build_activation_projection
from src.mission_os.dashboard import build_dashboard_payload, render_dashboard_html
from src.mission_os.decisions import read_operator_decisions, record_operator_decision
from src.mission_os.projection import compose_projection
from src.mission_os.revenue import project_revenue_pipeline


ROOT = Path(__file__).resolve().parents[2]


def _is_loopback_client(host: str | None) -> bool:
    if host in {"testclient", "localhost"}:
        return True
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def create_mission_app(
    repository_root: Path | str = ROOT,
    mission_path: Path | str = Path("config/mission.example.json"),
    database_path: Path | str | None = None,
    decision_ledger_path: Path | str | None = None,
    operator_token: str | None = None,
) -> FastAPI:
    root = Path(repository_root).resolve()
    api = FastAPI(
        title="Ω Mission OS Local Governed Operator API",
        version="1.3.0-local-decision-surface",
        description=(
            "Loopback-only mission projections plus human operator decision recording. "
            "Decision routes may record reject, revision-request, or exact authorization "
            "receipts, but no route performs an external action or mutates canonical state."
        ),
    )

    @api.middleware("http")
    async def enforce_loopback(request: Request, call_next):
        host = request.client.host if request.client else None
        if not _is_loopback_client(host):
            return JSONResponse(
                status_code=403,
                content={"detail": {"code": "MISSION_OS_LOOPBACK_ONLY", "message": "Mission OS is restricted to loopback clients.", "canonical_state_mutated": False, "external_action_performed": False}},
            )
        return await call_next(request)

    def compose_all() -> tuple[dict[str, Any], dict[str, Any]]:
        return compose_projection(root, mission_path, database_path), project_revenue_pipeline(root)

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "mode": "LOCAL_GOVERNED_OPERATOR",
            "network_boundary": "LOOPBACK_ONLY",
            "projection_methods": ["GET"],
            "decision_methods": ["GET", "POST"],
            "external_execution_routes": 0,
            "canonical_state_mutated": False,
            "external_action_performed": False,
        }

    @api.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> str:
        try:
            snapshot, revenue = compose_all()
            return render_dashboard_html(build_dashboard_payload(snapshot, revenue))
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail={"code": "DASHBOARD_PROJECTION_FAILED", "message": str(exc), "canonical_state_mutated": False, "external_action_performed": False}) from exc

    @api.get("/api/v1/mission/snapshot")
    def mission_snapshot() -> dict[str, Any]:
        try:
            return compose_projection(root, mission_path, database_path)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail={"code": "MISSION_PROJECTION_FAILED", "message": str(exc), "canonical_state_mutated": False, "external_action_performed": False}) from exc

    @api.get("/api/v1/revenue/pipeline")
    def revenue_pipeline() -> dict[str, Any]:
        return project_revenue_pipeline(root)

    @api.get("/api/v1/revenue/activation")
    def revenue_activation() -> dict[str, Any]:
        try:
            return build_activation_projection(root)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail={"code": "MISSION_ACTIVATION_PROJECTION_FAILED", "message": str(exc), "canonical_state_mutated": False, "external_action_performed": False}) from exc

    @api.get("/api/v1/operator/decisions")
    def operator_decisions() -> dict[str, Any]:
        return read_operator_decisions(root, ledger_path=decision_ledger_path)

    @api.post("/api/v1/operator/decisions", status_code=201)
    def create_operator_decision(
        payload: dict[str, Any],
        x_operator_token: str | None = Header(default=None, alias="X-Operator-Token"),
    ) -> dict[str, Any]:
        try:
            return record_operator_decision(
                root,
                payload,
                operator_token=x_operator_token,
                expected_token=operator_token,
                ledger_path=decision_ledger_path,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail={"code": "OPERATOR_AUTHENTICATION_REQUIRED", "message": str(exc), "external_action_performed": False, "canonical_state_mutated": False}) from exc
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail={"code": "OPERATOR_DECISION_REJECTED", "message": str(exc), "external_action_performed": False, "canonical_state_mutated": False}) from exc

    @api.get("/api/v1/dashboard")
    def dashboard_payload() -> dict[str, Any]:
        try:
            snapshot, revenue = compose_all()
            return build_dashboard_payload(snapshot, revenue)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail={"code": "DASHBOARD_PROJECTION_FAILED", "message": str(exc), "canonical_state_mutated": False, "external_action_performed": False}) from exc

    return api


app = create_mission_app()
