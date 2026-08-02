"""Read-only adapters from canonical AIGC state into Ω Mission OS projections."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.core.phase_registry import build_phase_registry


def project_phase_registry(repository_root: Path | str) -> list[dict[str, Any]]:
    """Project phase definitions and artifact availability without running phases."""
    root = Path(repository_root).resolve()
    projections: list[dict[str, Any]] = []
    for name, definition in sorted(build_phase_registry(root).items()):
        item = asdict(definition)
        input_path = (root / definition.input_path).resolve()
        output_path = (root / definition.output_path).resolve()
        item.update(
            {
                "phase": name,
                "input_available": input_path.is_file(),
                "output_available": output_path.is_file(),
                "command_executed": False,
                "external_action_performed": False,
            }
        )
        projections.append(item)
    return projections


def project_quest_records(records: Iterable[Any]) -> list[dict[str, Any]]:
    """Convert canonical persisted Quest records into immutable dictionaries."""
    projected: list[dict[str, Any]] = []
    for record in records:
        payload = getattr(record, "payload", None)
        if not isinstance(payload, Mapping):
            continue
        item = dict(payload)
        item.update(
            {
                "revision": getattr(record, "revision", None),
                "created_at": getattr(record, "created_at", None),
                "updated_at": getattr(record, "updated_at", None),
                "projection_only": True,
                "external_action_performed": False,
            }
        )
        projected.append(item)
    return projected


def project_quests_from_service(quest_service: Any) -> list[dict[str, Any]]:
    """Read all Quests through the canonical service's list operation only."""
    return project_quest_records(quest_service.list_quests(state=None))
