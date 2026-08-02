"""Read-only adapters from canonical AIGC state into Ω Mission OS projections."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from typing import Any

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


def project_quests_from_sqlite(database_path: Path | str) -> list[dict[str, Any]]:
    """Read canonical Quest rows through SQLite immutable read-only mode.

    No migrations are applied, no database is created, and no writes are permitted.
    A missing database produces an empty projection.
    """
    path = Path(database_path).resolve()
    if not path.is_file():
        return []
    uri = f"file:{path.as_posix()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT record_id, revision, payload_json, created_at, updated_at,
                   revoked_at, retention_state
            FROM records
            WHERE collection = 'quests' AND revoked_at IS NULL
            ORDER BY updated_at DESC, record_id
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError(f"canonical Quest persistence is unreadable: {exc}") from exc
    finally:
        connection.close()

    projected: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            continue
        payload.update(
            {
                "revision": int(row["revision"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "retention_state": row["retention_state"],
                "projection_only": True,
                "external_action_performed": False,
            }
        )
        projected.append(payload)
    return projected
