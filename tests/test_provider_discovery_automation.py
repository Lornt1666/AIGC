from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.provider_discovery_automation import (
    ProviderDiscoveryAutomationError,
    ProviderExecutionDisabled,
    build_target_specification_submission,
    canonical_digest,
    execute_live,
    load_catalog,
    load_fixture,
    load_template,
    render_command_plan,
    run_mock_discovery,
    scan_for_sensitive_material,
    strict_validate,
    validate_gcloud_argv,
    write_mock_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40
CREATED_AT = datetime(2026, 7, 15, 0, 30, tzinfo=timezone.utc)


def _load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _report(fixture=None):
    return run_mock_discovery(
        catalog=load_catalog(ROOT / "config/provider_discovery_command_catalog.json"),
        fixture=fixture
        or load_fixture(ROOT / "config/provider_discovery_mock_fixture.json"),
        template=load_template(
            ROOT / "config/staging_identity_procurement_readiness_pack.json"
        ),
        repository_revision=REVISION,
        created_at=CREATED_AT,
        rollback_reference="branch:codex/provider-discovery-automation-kit-v1",
    )


def test_catalog_and_fixture_are_strictly_valid():
    strict_validate(
        "provider_discovery_command_catalog",
        _load("config/provider_discovery_command_catalog.json"),
    )
    strict_validate(
        "provider_discovery_mock_fixture",
        _load("config/provider_discovery_mock_fixture.json"),
    )


def test_catalog_is_mock_only_and_every_command_is_read_only():
    catalog = load_catalog(ROOT / "config/provider_discovery_command_catalog.json")
    assert catalog["execution_mode"] == "MOCK_ONLY"
    assert catalog["live_execution_enabled"] is False
    assert catalog["shell_execution_allowed"] is False
    assert len(catalog["commands"]) == 13
    for command in catalog["commands"]:
        assert command["classification"] == "READ_ONLY"
        assert command["mutation_performed"] is False
        assert command["secret_value_access"] is False
        validate_gcloud_argv(command["argv_template"], template=True)


@pytest.mark.parametrize(
    "argv",
    [
        ["gcloud", "services", "enable", "iam.googleapis.com", "--format=json"],
        ["gcloud", "secrets", "versions", "access", "1", "--format=json"],
        ["gcloud", "projects", "delete", "aigc-staging-001", "--format=json"],
        ["gcloud", "projects", "describe", "aigc-staging-001;rm", "--format=json"],
    ],
)
def test_mutating_secret_access_and_shell_commands_are_rejected(argv):
    with pytest.raises(ProviderDiscoveryAutomationError):
        validate_gcloud_argv(argv)


def test_rendered_plan_has_no_placeholders_and_stable_digests():
    catalog = load_catalog(ROOT / "config/provider_discovery_command_catalog.json")
    fixture = load_fixture(ROOT / "config/provider_discovery_mock_fixture.json")
    first = render_command_plan(catalog, fixture["parameters"])
    second = render_command_plan(catalog, fixture["parameters"])
    assert first == second
    assert canonical_digest(first) == canonical_digest(second)
    assert all("{" not in token for item in first for token in item["argv"])
    assert all(item["argv_digest"] == canonical_digest(item["argv"]) for item in first)


def test_target_specification_submission_is_offline_and_non_authorizing():
    fixture = load_fixture(ROOT / "config/provider_discovery_mock_fixture.json")
    pack = build_target_specification_submission(
        load_template(ROOT / "config/staging_identity_procurement_readiness_pack.json"),
        parameters=fixture["parameters"],
        repository_revision=REVISION,
        created_at=CREATED_AT,
    )
    assert pack["artifact_kind"] == "SUBMISSION"
    assert pack["status"] == "TARGET_SPECIFICATION"
    assert pack["pack_id"].startswith("SIP-")
    assert pack["authorization_receipt_issued"] is False
    assert pack["provider_action_performed"] is False
    assert pack["terraform_plan_performed"] is False
    assert pack["terraform_apply_performed"] is False
    assert pack["external_action_performed"] is False
    assert all(
        phase["status"] == "UNUSED" for phase in pack["phase_consumption"].values()
    )


def test_mock_run_is_no_network_and_not_provider_evidence():
    report = _report()
    assert report["execution_mode"] == "MOCK_ONLY"
    assert report["no_network"] is True
    assert report["live_execution_attempted"] is False
    assert report["provider_action_performed"] is False
    assert report["external_action_performed"] is False
    assert report["authorization_receipt_issued"] is False
    assert report["evidence_candidate"]["artifact_kind"] == "SIMULATION_ONLY"
    assert report["evidence_candidate"]["admissible_as_provider_evidence"] is False
    assert report["evidence_candidate"]["provider_read_performed"] is False
    assert report["evidence_candidate"]["external_action_performed"] is False
    assert report["result"] == "PARTIAL"


def test_mock_run_is_deterministic_for_exact_inputs():
    first = _report()
    second = _report()
    assert first == second
    assert first["run_id"] == second["run_id"]
    assert first["command_plan_digest"] == second["command_plan_digest"]
    assert first["provenance_envelope"] == second["provenance_envelope"]


def test_simulation_report_and_provenance_validate():
    report = _report()
    strict_validate("provider_discovery_simulation_report", report)
    strict_validate("evidence_provenance_envelope", report["provenance_envelope"])
    assert report["provenance_envelope"]["authorization_receipt_id"] is None
    assert report["provenance_envelope"]["evidence_receipt_id"] is None
    assert report["provenance_envelope"]["operator_approval_reference"] is None


def test_timeout_retries_and_then_succeeds():
    fixture = load_fixture(ROOT / "config/provider_discovery_mock_fixture.json")
    fixture = copy.deepcopy(fixture)
    fixture["responses"]["project_describe"]["attempts"] = [
        {
            "outcome": "TIMEOUT",
            "exit_code": 124,
            "stdout_json": None,
            "stderr": "synthetic timeout",
            "duration_ms": 30000,
        },
        {
            "outcome": "SUCCESS",
            "exit_code": 0,
            "stdout_json": {
                "projectId": "aigc-staging-001",
                "projectNumber": "123456789012",
                "lifecycleState": "ACTIVE",
            },
            "stderr": "",
            "duration_ms": 20,
        },
    ]
    report = _report(fixture)
    project = next(
        item for item in report["command_results"] if item["command_id"] == "PROJECT_DESCRIBE"
    )
    assert project["status"] == "SUCCESS"
    assert project["attempt_count"] == 2


def test_permission_denial_fails_closed_without_receipt():
    fixture = load_fixture(ROOT / "config/provider_discovery_mock_fixture.json")
    fixture = copy.deepcopy(fixture)
    fixture["responses"]["enabled_services"]["attempts"] = [
        {
            "outcome": "PERMISSION_DENIED",
            "exit_code": 1,
            "stdout_json": None,
            "stderr": "synthetic permission denied",
            "duration_ms": 15,
        }
    ]
    report = _report(fixture)
    services = next(
        item
        for item in report["command_results"]
        if item["command_id"] == "ENABLED_SERVICES_LIST"
    )
    assert services["status"] == "PERMISSION_DENIED"
    assert report["authorization_receipt_issued"] is False
    assert report["evidence_candidate"]["admissible_as_provider_evidence"] is False


def test_missing_fixture_response_fails_closed():
    fixture = load_fixture(ROOT / "config/provider_discovery_mock_fixture.json")
    fixture = copy.deepcopy(fixture)
    fixture["responses"].pop("project_describe")
    report = _report(fixture)
    project = next(
        item for item in report["command_results"] if item["command_id"] == "PROJECT_DESCRIBE"
    )
    assert project["status"] == "MISSING_FIXTURE"
    assert report["result"] == "PARTIAL"


@pytest.mark.parametrize(
    "payload",
    [
        {"access_token": "synthetic"},
        {"nested": {"private_key": "synthetic"}},
        {"value": "-----BEGIN " + "PRIVATE KEY-----"},
        {"value": "ya" + "29.synthetic"},
    ],
)
def test_sensitive_material_is_rejected(payload):
    with pytest.raises(ProviderDiscoveryAutomationError):
        scan_for_sensitive_material(payload)


def test_live_provider_execution_is_impossible():
    with pytest.raises(ProviderExecutionDisabled):
        execute_live()


def test_outputs_contain_only_simulation_and_target_artifacts(tmp_path):
    report = _report()
    paths = write_mock_outputs(tmp_path, report)
    assert {path.name for path in paths} == {
        "target_specification_submission.json",
        "command_plan.json",
        "discovery_simulation_report.json",
        "provenance_envelope.json",
    }
    saved = json.loads(
        (tmp_path / "discovery_simulation_report.json").read_text(encoding="utf-8")
    )
    assert saved["external_action_performed"] is False
    assert saved["evidence_candidate"]["admissible_as_provider_evidence"] is False
