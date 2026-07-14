from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.core.production_environment_decision import (
    ProductionEnvironmentDecisionError,
    decision_digest,
    evaluate_decision,
    load_and_validate_decision,
)


ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = ROOT / "config" / "production_environment_decision.json"
SCHEMA_PATH = ROOT / "schemas" / "production_environment_decision.schema.json"


def decision() -> dict[str, object]:
    return json.loads(DECISION_PATH.read_text(encoding="utf-8"))


def write_pair(tmp_path: Path, value: dict[str, object]) -> tuple[Path, Path]:
    decision_path = tmp_path / "decision.json"
    schema_path = tmp_path / "schema.json"
    decision_path.write_text(json.dumps(value), encoding="utf-8")
    schema_path.write_text(SCHEMA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return decision_path, schema_path


def test_accepted_environment_baseline_is_contract_ready_but_not_resource_ready() -> None:
    value = load_and_validate_decision(DECISION_PATH, SCHEMA_PATH)
    evaluation = evaluate_decision(value)

    assert evaluation.accepted_baseline is True
    assert evaluation.contract_implementation_ready is True
    assert evaluation.isolated_staging_preparation_ready is True
    assert evaluation.resource_creation_ready is False
    assert evaluation.production_deployment_ready is False
    assert evaluation.enabled_connectors == ()
    assert evaluation.default_deny_connectors is True
    assert evaluation.monthly_cloud_ceiling_cad == 200
    assert "DEFERRED_IDENTIFIERS_REMAIN" in evaluation.reason_codes


def test_decision_records_accepted_canadian_google_cloud_baseline() -> None:
    value = load_and_validate_decision(DECISION_PATH, SCHEMA_PATH)

    assert value["cloud"]["provider"] == "google_cloud"
    assert value["cloud"]["primary_region"] == "northamerica-northeast2"
    assert value["cloud"]["recovery_region"] == "northamerica-northeast1"
    assert value["database"]["service"] == "cloud_sql"
    assert value["database"]["engine"] == "postgresql"
    assert value["database"]["rpo_minutes"] == 15
    assert value["database"]["rto_minutes"] == 240
    assert value["identity"]["provider"] == "google_cloud_identity_platform"
    assert value["identity"]["sign_in_methods"] == ["google"]
    assert value["identity"]["tenant_model"] == "single_accountable_tenant"
    assert value["secrets"]["provider"] == "google_secret_manager"


def test_connectors_remain_disabled_and_candidates_are_not_authorized() -> None:
    value = load_and_validate_decision(DECISION_PATH, SCHEMA_PATH)

    assert value["connectors"]["enabled"] == []
    assert set(value["connectors"]["candidates"]) == {
        "github",
        "google_drive",
        "gmail",
    }
    assert value["authority"]["connector_activation_authorized"] is False


def test_unknown_or_authority_elevating_fields_fail_schema_validation(tmp_path: Path) -> None:
    value = decision()
    value["claimed_resource_creation_authorized"] = True
    decision_path, schema_path = write_pair(tmp_path, value)

    with pytest.raises(ProductionEnvironmentDecisionError):
        load_and_validate_decision(decision_path, schema_path)


def test_enabled_connector_fails_closed(tmp_path: Path) -> None:
    value = decision()
    value["connectors"]["enabled"] = ["gmail"]
    decision_path, schema_path = write_pair(tmp_path, value)

    with pytest.raises(ProductionEnvironmentDecisionError):
        load_and_validate_decision(decision_path, schema_path)


def test_phone_or_secret_material_cannot_enter_source_controlled_decision(
    tmp_path: Path,
) -> None:
    value = decision()
    value["operations"]["technical_escalation_contact_reference"] = "+1 780 000 0000"
    decision_path, schema_path = write_pair(tmp_path, value)

    with pytest.raises(ProductionEnvironmentDecisionError):
        load_and_validate_decision(decision_path, schema_path)

    secret_value = decision()
    secret_value["operations"]["secret_value"] = "prohibited"
    decision_path, schema_path = write_pair(tmp_path, secret_value)
    with pytest.raises(ProductionEnvironmentDecisionError):
        load_and_validate_decision(decision_path, schema_path)


def test_decision_digest_is_stable_and_changes_with_material_decision() -> None:
    value = decision()
    first = decision_digest(value)
    second = decision_digest(copy.deepcopy(value))
    changed = copy.deepcopy(value)
    changed["budget"]["monthly_ceiling"] = 201

    assert first == second
    assert first != decision_digest(changed)
    assert len(first) == 64
