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


def test_evolution_architect_generates_one_review_only_snapshot(tmp_path: Path) -> None:
    policy = load_policy(PROJECT_ROOT / "config" / "recursive_production_architect.json")
    assert policy["mode"] == "single_snapshot_review_only"
    assert policy["maximum_cycles_per_run"] == 1

    cycle = build_cycle(PROJECT_ROOT, policy, 1)
    assert cycle["cycle_number"] == 1
    assert cycle["execution_mode"] == "single_snapshot_review_only"
    assert cycle["operator_review_required"] is True
    assert cycle["external_action_performed"] is False
    assert cycle["architecture_assessment"]["production_readiness_score"] >= 0
    assert cycle["ontology"]["risk"]["external_execution"] == "blocked_by_default"

    result = run_recursive_production_architect(PROJECT_ROOT, artifact_root=tmp_path)
    assert result["cycles_executed"] == 1
    assert result["cycle"]["execution_mode"] == "single_snapshot_review_only"
    assert result["repository_mutated"] is False
    assert result["external_action_performed"] is False
    assert any(tmp_path.rglob("recursive_production_cycle.json"))
    assert any(tmp_path.rglob("recursive_production_cycle.md"))


def test_evolution_architect_rejects_multiple_cycles() -> None:
    policy = json.loads((PROJECT_ROOT / "config" / "recursive_production_architect.json").read_text(encoding="utf-8"))
    policy["maximum_cycles_per_run"] = 2
    with pytest.raises(RecursiveProductionArchitectError, match="must equal 1"):
        validate_policy(policy)


def test_evolution_architect_rejects_uncontracted_recursive_mode() -> None:
    policy = json.loads((PROJECT_ROOT / "config" / "recursive_production_architect.json").read_text(encoding="utf-8"))
    policy["mode"] = "bounded_review_only_transformation_cycles"
    with pytest.raises(RecursiveProductionArchitectError, match="single_snapshot_review_only"):
        validate_policy(policy)


def test_evolution_architect_rejects_non_primary_cycle_number() -> None:
    policy = load_policy(PROJECT_ROOT / "config" / "recursive_production_architect.json")
    with pytest.raises(RecursiveProductionArchitectError, match="cycle_number=1"):
        build_cycle(PROJECT_ROOT, policy, 2)


def test_evolution_architect_rejects_self_approval_gap() -> None:
    policy = json.loads((PROJECT_ROOT / "config" / "recursive_production_architect.json").read_text(encoding="utf-8"))
    policy["hard_blocks"].remove("self_approval")
    with pytest.raises(RecursiveProductionArchitectError):
        validate_policy(policy)
