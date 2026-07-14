from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "evolution_procurement_cycle.schema.json"
CYCLE_PATH = (
    ROOT
    / "data"
    / "evolution_procurement"
    / "aigc_evolution_procurement_cycle_2026-07-14.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_current_evolution_procurement_cycle_matches_contract() -> None:
    schema = _load(SCHEMA_PATH)
    cycle = _load(CYCLE_PATH)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(cycle),
        key=lambda error: list(error.absolute_path),
    )
    assert not errors, [
        {
            "path": list(error.absolute_path),
            "message": error.message,
        }
        for error in errors
    ]


def test_cycle_preserves_operator_and_external_action_boundaries() -> None:
    cycle = _load(CYCLE_PATH)

    assert cycle["scope"] == "AIGC only"
    assert cycle["operator_review_required"] is True
    assert cycle["external_action_performed"] is False
    assert cycle["boundaries"] == {
        "main_write_performed": False,
        "merge_performed": False,
        "deployment_performed": False,
        "credentials_used": False,
        "connector_enabled": False,
        "secret_accessed": False,
        "self_approval_performed": False,
        "security_privacy_gate_weakened": False,
    }


def test_cycle_selects_exactly_one_bounded_step_without_readiness_promotion() -> None:
    cycle = _load(CYCLE_PATH)
    selected = cycle["selected_step"]
    readiness = cycle["assessments"]["production_readiness"]
    impact = cycle["procurement_success_packet"]["estimated_readiness_score_impact"]

    assert selected["step_id"] == "AIGC-STEP-CCA-CURRENTNESS-001"
    assert selected["implementation_authorized"] is False
    assert selected["readiness_ledger_change_authorized"] is False
    assert selected["external_action_authorized"] is False
    assert readiness["score_change_performed"] is False
    assert readiness["production_ready"] is False
    assert impact["implementation_pr_score_change"] == 0
    assert impact["operational_completion_claimed"] is False


def test_workflow_procurement_procedure_has_required_order() -> None:
    cycle = _load(CYCLE_PATH)
    stages = [
        item["stage"]
        for item in sorted(
            cycle["workflow_procurement_procedure"],
            key=lambda item: item["order"],
        )
    ]
    assert stages == [
        "intake",
        "evidence verification",
        "scope lock",
        "contract-first design",
        "implementation plan",
        "security/privacy wiring",
        "tests",
        "CI",
        "operator review",
        "merge decision",
        "post-merge verification",
        "readiness-ledger update",
    ]
