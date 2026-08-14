from __future__ import annotations

from pathlib import Path

from src.core.nexus.connector_registry import ConnectorRegistry
from src.domain.nexus.connectors import ConnectorCapability, ConnectorPassport
from src.webapp.nexus_dashboard import build_nexus_dashboard_snapshot


ROOT = Path(__file__).resolve().parents[1]


def registry() -> ConnectorRegistry:
    return ConnectorRegistry.from_constitution(
        ROOT / "config/aigc_employment_connector_registry.v1.json"
    )


def test_current_registry_exposes_truthful_default_deny_states():
    snapshot = registry().status_snapshot()
    assert {item["connector_id"] for item in snapshot} == {
        "PASSPORT_GENERIC_WEB",
        "PASSPORT_GMAIL",
        "PASSPORT_INDEED",
        "PASSPORT_PORTABLE_AI",
    }
    assert sum(item["live_mutation_capability_count"] for item in snapshot) == 0
    assert all(item["authority_granted"] is False for item in snapshot)


def test_gmail_send_indeed_submit_and_generic_site_submit_remain_blocked():
    cases = (
        ("PASSPORT_GMAIL", "send_message"),
        ("PASSPORT_INDEED", "submit_application"),
        ("PASSPORT_GENERIC_WEB", "submit_or_message"),
    )
    for connector_id, action in cases:
        decision = registry().assess(connector_id, action, "EXECUTE")
        assert decision.disposition == "BLOCKED"
        assert decision.capability_admitted is False
        assert decision.live_mutation_possible is False
        assert decision.authority_granted is False
        assert decision.external_action_performed is False


def test_human_handoff_is_not_misreported_as_executable_capability():
    decision = registry().assess(
        "PASSPORT_INDEED", "prepare_application", "DRAFT"
    )
    assert decision.disposition == "HUMAN_HANDOFF_REQUIRED"
    assert decision.capability_admitted is False
    assert decision.live_mutation_possible is False


def test_unknown_connector_and_unknown_action_fail_closed():
    unknown_connector = registry().assess("PASSPORT_UNKNOWN", "send", "EXECUTE")
    unknown_action = registry().assess("PASSPORT_GMAIL", "delete_mailbox", "EXECUTE")
    assert unknown_connector.disposition == unknown_action.disposition == "BLOCKED"
    assert unknown_connector.capability_status == unknown_action.capability_status == "NOT_IMPLEMENTED"


def test_certified_capability_reaches_authority_gate_but_does_not_grant_authority():
    passport = ConnectorPassport(
        connector_id="PASSPORT_FIXTURE",
        name="fixture",
        owner="test",
        certification_status="CERTIFIED",
        identity_binding="fixture identity",
        terms_binding="fixture terms",
        capabilities=(
            ConnectorCapability(
                action="submit_fixture",
                stage="EXECUTE",
                status="CERTIFIED",
                reason="test-only certified fixture",
                live_mutation_allowed=True,
            ),
        ),
    )
    decision = ConnectorRegistry((passport,)).assess(
        "PASSPORT_FIXTURE", "submit_fixture", "EXECUTE"
    )
    assert decision.disposition == "PROCEED_TO_AUTHORITY_GATE"
    assert decision.capability_admitted is True
    assert decision.live_mutation_possible is True
    assert decision.separate_execution_permit_required is True
    assert decision.authority_granted is False


def test_dashboard_projects_connector_truth_without_write_through():
    snapshot = build_nexus_dashboard_snapshot()
    assert snapshot["system"]["employment_connectors"] == "VISIBLE_DEFAULT_DENY"
    assert snapshot["connectors"]["enabled_live_mutation_capabilities"] == 0
    assert snapshot["connectors"]["grants_authority"] is False
