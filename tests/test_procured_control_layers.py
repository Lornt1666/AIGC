from __future__ import annotations

from src.core.contract_validator import validate_artifact
from src.core.procured_control_layers import (
    REQUESTED_LAYER_IDS,
    build_procured_control_layers_catalog,
    validate_procured_control_layers_catalog,
)


def test_all_requested_layers_are_procured_as_contracts() -> None:
    catalog = build_procured_control_layers_catalog()

    assert validate_artifact("procured_control_layers_catalog", catalog) == catalog
    assert validate_procured_control_layers_catalog(catalog) == catalog
    assert catalog["status"] == "procured_as_local_contracts"
    layer_ids = {layer["layer_id"] for layer in catalog["procured_layers"]}
    assert set(REQUESTED_LAYER_IDS).issubset(layer_ids)


def test_procured_layers_have_controls_tests_sources_and_boundaries() -> None:
    catalog = build_procured_control_layers_catalog()

    for layer in catalog["procured_layers"]:
        assert not layer["status"].startswith("planned")
        assert layer["source_ids"]
        assert layer["formations_procured"]
        assert layer["schemas_to_create"]
        assert layer["modules_to_create"]
        assert layer["tests_to_create"]
        assert layer["controls"]
        assert layer["acceptance_tests"]
        assert layer["human_review_required"] is True
        assert layer["external_action_performed"] is False
        assert "unchecked_outward_action" in layer["blocked_failure_modes"]


def test_procurement_boundary_keeps_external_systems_off() -> None:
    catalog = build_procured_control_layers_catalog()
    boundary = catalog["procurement_boundary"]

    assert boundary["external_services_installed"] is False
    assert boundary["accounts_configured"] is False
    assert boundary["credentials_read"] is False
    assert boundary["live_actions_executed"] is False
    assert boundary["push_command_executed_by_catalog"] is False
    assert boundary["merge_or_deploy_authorized"] is False
    assert catalog["external_action_performed"] is False


def test_safe_push_command_is_procured_but_not_executed_by_catalog() -> None:
    catalog = build_procured_control_layers_catalog()
    commands = {command["command_id"]: command for command in catalog["procured_safe_commands"]}
    push = commands["next_safe_push_pr12"]

    assert push["command"] == "git push -u origin codex/operator-cockpit-run-accept"
    assert push["human_review_required"] is True
    assert push["external_action_performed"] is False
    assert "merge_pull_request" in push["forbidden_side_effects"]
    assert "deploy_service" in push["forbidden_side_effects"]
    assert "read_secrets" in push["forbidden_side_effects"]
    assert any("pytest" in item for item in push["prerequisites"])
    assert any("gh pr view 12" in item for item in push["verification_after_command"])
