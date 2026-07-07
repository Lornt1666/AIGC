from __future__ import annotations

from pathlib import Path

from src.orchestration.gateway import REQUIRED_CORRELATION_FIELDS, validate_n8n_templates


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_n8n_templates_validate_as_safe_placeholders() -> None:
    results = validate_n8n_templates(PROJECT_ROOT)

    assert len(results) == 6
    assert all(result.valid for result in results), results


def test_n8n_templates_have_no_enabled_external_action_nodes() -> None:
    results = validate_n8n_templates(PROJECT_ROOT)

    assert all(result.valid for result in results)
    for result in results:
        assert result.findings == []


def test_required_correlation_fields_are_defined() -> None:
    assert {
        "workflow_execution_id",
        "audit_event_id",
        "work_order_id",
        "action_permit_id",
        "requires_human_approval",
        "external_action_performed",
    } == REQUIRED_CORRELATION_FIELDS
