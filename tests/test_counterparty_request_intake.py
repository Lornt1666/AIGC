from __future__ import annotations

import json
from pathlib import Path

from src.core.contract_validator import validate_file
from src.core.counterparty_request_intake import run_counterparty_request_intake


def make_request() -> dict:
    return {
        "request_id": "REQ-TEST-001",
        "created_at": "2026-07-09T00:00:00+00:00",
        "source": "manual_test",
        "counterparty": {"name": "Example Client", "platform": "Manual", "verified": False},
        "requested_action": "accept",
        "work_description": {
            "summary": "Client needs a local automation dashboard plan.",
            "problem_to_solve": "Tasks and delivery notes are disorganized.",
            "success_outcome": "A scoped implementation plan and dashboard workflow map."
        },
        "deliverables": [{"deliverable_id": "D1", "title": "Workflow map", "format": "markdown"}],
        "acceptance_criteria": ["Clear scope", "Delivery checklist included"],
        "terms": {
            "compensation": "CAD 250 fixed draft",
            "payment_timing": "manual agreement before start",
            "contract_obligations": "operator reviews before accepting"
        },
        "timeline": {"requested_deadline": "2026-07-20", "milestones": ["scope", "draft", "review"]},
        "constraints": ["no credential use"],
        "attachments": [],
        "communication_history": [],
        "operator_review_required": True,
        "external_action_performed": False,
    }


def test_counterparty_request_ready_when_description_is_complete(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(make_request()), encoding="utf-8")

    result = run_counterparty_request_intake(tmp_path, request_path)

    assert result["external_action_performed"] is False
    assert result["review"]["proceed_enabled"] is True
    assert result["review"]["decision_state"] == "ready_for_operator_popup_high_risk"
    assert result["review"]["visible_acceptance_summary"]["deliverables"]
    validate_file("counterparty_request_packet", tmp_path / result["request_path"])
    validate_file("counterparty_acceptance_review", tmp_path / result["review_path"])


def test_counterparty_request_blocks_when_description_is_missing(tmp_path: Path) -> None:
    payload = make_request()
    payload["work_description"]["summary"] = ""
    payload["terms"]["compensation"] = "not agreed yet"
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_counterparty_request_intake(tmp_path, request_path)

    assert result["review"]["proceed_enabled"] is False
    assert result["review"]["decision_state"] == "insufficient_information"
    assert "work_description.summary" in result["review"]["required_clarifications"]
    assert "terms.compensation" in result["review"]["required_clarifications"]


def test_counterparty_request_blocks_hard_risk_language(tmp_path: Path) -> None:
    payload = make_request()
    payload["work_description"]["summary"] = "Client wants to bypass platform rules."
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_counterparty_request_intake(tmp_path, request_path)

    assert result["review"]["proceed_enabled"] is False
    assert result["review"]["decision_state"] == "blocked_pending_risk_review"
    assert result["review"]["risk_flags"]
