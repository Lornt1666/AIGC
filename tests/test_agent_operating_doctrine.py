from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.agent_operating_doctrine import (
    AgentOperatingDoctrineError,
    build_agent_doctrine_report,
    load_doctrine,
    run_agent_operating_doctrine,
    validate_doctrine,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_agent_doctrine_generates_report(tmp_path: Path) -> None:
    doctrine = load_doctrine(PROJECT_ROOT / "config" / "agent_operating_doctrine.json")
    report = build_agent_doctrine_report(doctrine)

    assert report["decision_state"] == "agent_doctrine_ready_for_operator_review"
    assert report["external_action_performed"] is False
    assert report["mandatory_gate"]["receipt_required"] is True
    assert "security_privacy_wiring_cli.py" in report["mandatory_gate"]["cli"]
    assert {card["role_id"] for card in report["agent_job_cards"]} >= {
        "researcher",
        "communicator",
        "reasoner",
        "sentinel",
        "operator_cockpit",
        "phase4_phase5_readonly_reviewer",
        "scoped_internal_improvement_proposer",
    }

    result = run_agent_operating_doctrine(PROJECT_ROOT, artifact_root=tmp_path)
    assert result["external_action_performed"] is False
    assert Path(result["report_path"]).exists()
    assert Path(result["markdown_report_path"]).exists()
    assert any(tmp_path.rglob("agent_operating_doctrine_report.json"))
    assert any(tmp_path.rglob("agent_operating_doctrine_report.md"))


def test_agent_doctrine_rejects_runtime_dependency_download() -> None:
    payload = json.loads((PROJECT_ROOT / "config" / "agent_operating_doctrine.json").read_text(encoding="utf-8"))
    payload["dependency_policy"]["no_runtime_dependency_download_inside_agents"] = False

    with pytest.raises(AgentOperatingDoctrineError):
        validate_doctrine(payload)


def test_agent_doctrine_rejects_missing_hard_block() -> None:
    payload = json.loads((PROJECT_ROOT / "config" / "agent_operating_doctrine.json").read_text(encoding="utf-8"))
    payload["hard_blocks"].remove("self_approval")

    with pytest.raises(AgentOperatingDoctrineError):
        validate_doctrine(payload)


def test_agent_doctrine_preserves_manual_handoff_review_boundaries() -> None:
    doctrine = load_doctrine(PROJECT_ROOT / "config" / "agent_operating_doctrine.json")
    roles = {item["role_id"]: item for item in doctrine["agent_roles"]}

    assert "regenerate Phase 4 or Phase 5 artifacts" in roles[
        "phase4_phase5_readonly_reviewer"
    ]["must_not_do"]
    assert "apply a behavior-changing patch" in roles[
        "scoped_internal_improvement_proposer"
    ]["must_not_do"]
    assert {
        "unapproved_native_workflow_or_packet_regeneration",
        "expired_packet_acceptance_or_handoff",
        "unapproved_external_contact",
    }.issubset(doctrine["hard_blocks"])
