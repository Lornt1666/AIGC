from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from src.core.contract_validator import (
    ContractValidationError,
    validate_artifact_strict,
)


ROOT = Path(__file__).resolve().parents[1]
BACKLOG_PATH = (
    ROOT
    / "config"
    / "task_backlog"
    / "canadian_financial_procurement_tasks.json"
)
ROADMAP_PATH = (
    ROOT
    / "docs"
    / "governance"
    / "roadmaps"
    / "AIGC_CANADIAN_FINANCIAL_FEATURE_OPTIONS.md"
)
TASK_ID = re.compile(r"CAFIN-P[0-3]-[0-9]{3}")


def _backlog() -> dict:
    return json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))


def test_backlog_satisfies_its_strict_schema() -> None:
    validate_artifact_strict(
        "canadian_financial_procurement_tasks",
        _backlog(),
    )


def test_backlog_task_ids_are_unique_and_match_priority() -> None:
    tasks = _backlog()["tasks"]
    task_ids = [task["task_id"] for task in tasks]

    assert len(task_ids) == len(set(task_ids))
    assert all(TASK_ID.fullmatch(task_id) for task_id in task_ids)
    assert all(
        task["task_id"].split("-")[1] == task["priority"]
        for task in tasks
    )


def test_backlog_dependencies_exist_are_unique_and_are_acyclic() -> None:
    tasks = _backlog()["tasks"]
    dependencies = {
        task["task_id"]: task["dependencies"]
        for task in tasks
    }
    known_ids = set(dependencies)

    for task_id, task_dependencies in dependencies.items():
        assert len(task_dependencies) == len(set(task_dependencies)), task_id
        assert set(task_dependencies) <= known_ids, task_id
        assert task_id not in task_dependencies

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        assert task_id not in visiting, f"dependency cycle at {task_id}"
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in dependencies[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in dependencies:
        visit(task_id)

    assert visited == known_ids


def test_backlog_declares_every_used_state_and_covers_p0_through_p3() -> None:
    backlog = _backlog()
    declared_states = backlog["decision_protocol"]["selection_states"]
    used_states = {task["status"] for task in backlog["tasks"]}
    priorities = {task["priority"] for task in backlog["tasks"]}

    assert len(declared_states) == len(set(declared_states))
    assert used_states <= set(declared_states)
    assert priorities == {"P0", "P1", "P2", "P3"}


def test_roadmap_and_machine_readable_backlog_have_task_id_parity() -> None:
    backlog_ids = {
        task["task_id"]
        for task in _backlog()["tasks"]
    }
    roadmap_ids = set(
        TASK_ID.findall(ROADMAP_PATH.read_text(encoding="utf-8"))
    )

    assert roadmap_ids == backlog_ids


def test_strict_validator_rejects_primary_schema_name_traversal(
    tmp_path: Path,
) -> None:
    schema_root = tmp_path / "schemas"
    schema_root.mkdir()
    outside_schema = tmp_path / "outside.schema.json"
    outside_schema.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ContractValidationError, match="safe local basename"):
        validate_artifact_strict(
            "../outside",
            {},
            schema_dir=schema_root,
        )
