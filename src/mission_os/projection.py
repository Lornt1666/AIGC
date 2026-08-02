"""Composition service for bounded Ω Mission OS read-only projections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.api.composition import DEFAULT_DATABASE_PATH
from src.mission_os.adapters import project_quests_from_sqlite
from src.mission_os.mission_director import MissionDirector


DEFAULT_MISSION_PATH = Path("config/mission.example.json")


def load_mission(repository_root: Path | str, mission_path: Path | str = DEFAULT_MISSION_PATH) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    candidate = Path(mission_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("mission path escapes repository root")
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("mission artifact must be a JSON object")
    return payload


def compose_projection(
    repository_root: Path | str,
    mission_path: Path | str = DEFAULT_MISSION_PATH,
    database_path: Path | str | None = None,
) -> dict[str, Any]:
    """Read canonical Quest persistence and return a validated projection only."""
    root = Path(repository_root).resolve()
    database = Path(database_path).resolve() if database_path else DEFAULT_DATABASE_PATH.resolve()
    quests = project_quests_from_sqlite(database)
    mission = load_mission(root, mission_path)
    return MissionDirector(root).compose(mission, quest_projection=quests)
