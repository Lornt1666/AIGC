from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.recursive_production_architect import (
    RecursiveProductionArchitectError,
    build_cycle,
    load_policy,
    run_recursive_production_architect,
    validate_policy,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_recursive_architect_generates_review_only_cycle(tmp_path: Path) -> None:
    policy = load_policy(PROJECT_ROOT / "config" / "recursive_production_architect.json")
    cycle = build_cycle(PROJECT_ROOT, policy, 1)
    assert cycle["operator_review_required"] is True
    assert cycle["external_action_performed"] is False
    assert cycle["architecture_assessment"]["production_readiness_score"] >= 0
    assert cycle["ontology"]["risk"]["external_execution"] == "blocked_by_default"

    result = run_recursive_production_architect(PROJECT_ROOT, artifact_root=tmp_path)
    assert result["cycles_executed"] == 1
    assert result["repository_mutated"] is False
    assert result["external_action_performed"] is False
    assert any(tmp_path.rglob("recursive_production_cycle.json"))
    assert any(tmp_path.rglob("recursive_production_cycle.md"))


def test_recursive_architect_rejects_unbounded_cycle_count() -> None:
    policy = json.loads((PROJECT_ROOT / "config" / "recursive_production_architect.json").read_text(encoding="utf-8"))
    policy["maximum_cycles_per_run"] = 1000
    with pytest.raises(RecursiveProductionArchitectError):
        validate_policy(policy)


def test_recursive_architect_rejects_self_approval_gap() -> None:
    policy = json.loads((PROJECT_ROOT / "config" / "recursive_production_architect.json").read_text(encoding="utf-8"))
    policy["hard_blocks"].remove("self_approval")
    with pytest.raises(RecursiveProductionArchitectError):
        validate_policy(policy)
