"""GET-only FastAPI surface for Ω Mission OS read-only projections."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from src.mission_os.dashboard import build_dashboard_payload, render_dashboard_html
from src.mission_os.projection import compose_projection
from src.mission_os.revenue import project_revenue_pipeline


ROOT = Path(__file__).resolve().parents[2]


def create_mission_app(
    repository_root: Path | str = ROOT,
    mission_path: Path | str = Path("config/mission.example.json"),
    database_path: Path | str | None = None,
) -> FastAPI:
    root = Path(repository_root).resolve()
    api = FastAPI(
        title="Ω Mission OS Read-Only Projection API",
        version="1.1.0-read-only",
        description="GET-only mission, Quest, phase, dashboard, and revenue projection surface. No canonical mutation or external action routes are registered.",
    )

    def compose_all() -> tuple[dict[str, Any], dict[str, Any]]:
        snapshot = compose_projection(root, mission_path, database_path)
        revenue = project_revenue_pipeline(root)
        return snapshot, revenue

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "mode": "READ_ONLY",
            "methods": ["GET"],
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

    @api.get("/api/v1/dashboard")
    def dashboard_payload() -> dict[str, Any]:
        try:
            snapshot, revenue = compose_all()
            return build_dashboard_payload(snapshot, revenue)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail={"code": "DASHBOARD_PROJECTION_FAILED", "message": str(exc), "canonical_state_mutated": False, "external_action_performed": False}) from exc

    return api


app = create_mission_app()
