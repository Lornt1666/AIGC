"""GET-only FastAPI surface for Ω Mission OS read-only projections."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from src.mission_os.projection import compose_projection


ROOT = Path(__file__).resolve().parents[2]


def create_mission_app(
    repository_root: Path | str = ROOT,
    mission_path: Path | str = Path("config/mission.example.json"),
    database_path: Path | str | None = None,
) -> FastAPI:
    root = Path(repository_root).resolve()
    api = FastAPI(
        title="Ω Mission OS Read-Only Projection API",
        version="1.0.0-read-only",
        description="GET-only mission, Quest, and phase projection surface. No canonical mutation or external action routes are registered.",
    )

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "mode": "READ_ONLY",
            "methods": ["GET"],
            "canonical_state_mutated": False,
            "external_action_performed": False,
        }

    @api.get("/api/v1/mission/snapshot")
    def mission_snapshot() -> dict[str, Any]:
        try:
            return compose_projection(root, mission_path, database_path)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "MISSION_PROJECTION_FAILED",
                    "message": str(exc),
                    "canonical_state_mutated": False,
                    "external_action_performed": False,
                },
            ) from exc

    return api


app = create_mission_app()
