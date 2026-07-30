from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from src.core.canadian_compliance_workflow import (
    CanadianComplianceError,
    canonical_digest,
    load_canadian_compliance_config,
    prepare_canadian_compliance_work_packet,
    run_canadian_compliance_workflow,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads(
        (SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8")
    )


def _schema_registry() -> Registry:
    schemas = (
        _load_schema("financial_evidence_config"),
        _load_schema("financial_evidence_packet"),
        _load_schema("financial_evidence_run_receipt"),
        _load_schema("canadian_compliance_workflow_config"),
        _load_schema("canadian_compliance_work_packet"),
        _load_schema("canadian_compliance_run_receipt"),
    )
    return Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        _load_schema(name),
        registry=_schema_registry(),
        format_checker=FormatChecker(),
    )


def compliance_config(entity_type: str = "unknown") -> dict:
    return {
        "schema_version": "1.0.0",
        "tenant_id": "TENANT-SYNTHETIC",
        "engagement_id": "ENGAGEMENT-SYNTHETIC",
        "work_order_id": "WORK-SYNTHETIC",
        "as_of_date": "2026-07-30",
        "financial_evidence_packet_id": None,
        "business_profile": {
            "country": "CA",
            "province": "AB",
            "entity_type": entity_type,
            "fiscal_period_end": None,
            "accounting_method": "unknown",
            "has_taxable_supplies": "unknown",
            "current_quarter_taxable_supplies_cad": None,
            "previous_four_quarters_taxable_supplies_cad": None,
            "gst_hst_registration_status": "unknown",
            "has_employees": "unknown",
            "payroll_account_status": "unknown",
            "workers_in_alberta": None,
            "collects_personal_information": "unknown",
            "cra_representative_status": "unknown",
        },
    }


def resolved_corporation_config() -> dict:
    config = compliance_config("corporation")
    config["financial_evidence_packet_id"] = (
        "AIGC-FIN-EVIDENCE-ABCDEF0123456789AB"
    )
    profile = config["business_profile"]
    profile.update(
        {
            "fiscal_period_end": "2026-12-31",
            "accounting_method": "accrual",
            "has_taxable_supplies": "yes",
            "current_quarter_taxable_supplies_cad": "12500.00",
            "previous_four_quarters_taxable_supplies_cad": "25000.00",
            "gst_hst_registration_status": "not_registered",
            "has_employees": "no",
            "payroll_account_status": "none",
            "workers_in_alberta": 0,
            "collects_personal_information": "no",
            "cra_representative_status": "none",
        }
    )
    return config


def _write_private_config(tmp_path: Path, payload: dict) -> Path:
    private_parent = tmp_path / "private-config"
    private_parent.mkdir(mode=0o700)
    private_parent.chmod(0o700)
    config_path = private_parent / "compliance.json"
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    config_path.chmod(0o600)
    return config_path


def _private_artifact_root(tmp_path: Path, name: str = "compliance-output") -> Path:
    private_parent = tmp_path / "private-artifacts"
    private_parent.mkdir(mode=0o700)
    private_parent.chmod(0o700)
    return private_parent / name


def test_unknown_entity_fails_closed_with_explicit_unknowns() -> None:
    config = compliance_config()
    _validator("canadian_compliance_workflow_config").validate(config)

    packet = prepare_canadian_compliance_work_packet(config)

    _validator("canadian_compliance_work_packet").validate(packet)
    assert packet["status"] == "authority_unresolved"
    assert "legal_entity_type_unresolved" in packet["blockers"]
    assert "legal_entity_type" in packet["unknowns"]
    assert "required_business_facts_missing" in packet["blockers"]
    assert packet["evidence_level"] == "preparation_only"


def test_repository_example_is_synthetic_schema_valid_and_fails_closed() -> None:
    config = json.loads(
        (
            ROOT / "config" / "canadian_compliance_workflow.example.json"
        ).read_text(encoding="utf-8")
    )

    _validator("canadian_compliance_workflow_config").validate(config)
    packet = prepare_canadian_compliance_work_packet(config)
    _validator("canadian_compliance_work_packet").validate(packet)

    assert packet["status"] == "authority_unresolved"
    assert packet["external_action_performed"] is False


def test_packet_is_deterministic_and_digest_is_bound_to_packet_core() -> None:
    config = resolved_corporation_config()

    first = prepare_canadian_compliance_work_packet(deepcopy(config))
    second = prepare_canadian_compliance_work_packet(deepcopy(config))

    assert first == second
    assert first["packet_digest"] == canonical_digest(
        {
            key: value
            for key, value in first.items()
            if key not in {"packet_id", "packet_digest"}
        }
    )
    assert first["packet_id"].endswith(first["packet_digest"][:18].upper())


@pytest.mark.parametrize(
    ("current_quarter", "trailing_quarters"),
    [
        ("30000.01", "0.00"),
        ("0.00", "30000.01"),
    ],
)
def test_gst_hst_general_threshold_creates_review_signal_not_registration(
    current_quarter: str,
    trailing_quarters: str,
) -> None:
    config = resolved_corporation_config()
    profile = config["business_profile"]
    profile["current_quarter_taxable_supplies_cad"] = current_quarter
    profile["previous_four_quarters_taxable_supplies_cad"] = trailing_quarters

    packet = prepare_canadian_compliance_work_packet(config)
    gst = next(
        item
        for item in packet["obligations"]
        if item["obligation_id"] == "CA-GST-HST-001"
    )

    assert gst["status"] == "threshold_review_required"
    assert gst["external_action_performed"] is False
    assert "register_or_modify_gst_hst_payroll_or_other_program_accounts" in (
        packet["blocked_external_actions"]
    )


def test_exact_threshold_remains_monitoring_signal() -> None:
    config = resolved_corporation_config()
    profile = config["business_profile"]
    profile["current_quarter_taxable_supplies_cad"] = "30000.00"
    profile["previous_four_quarters_taxable_supplies_cad"] = "30000.00"

    packet = prepare_canadian_compliance_work_packet(config)
    gst = next(
        item
        for item in packet["obligations"]
        if item["obligation_id"] == "CA-GST-HST-001"
    )

    assert gst["status"] == "monitoring_required"


def test_runtime_rejects_three_decimal_taxable_supply_amount() -> None:
    config = resolved_corporation_config()
    config["business_profile"]["current_quarter_taxable_supplies_cad"] = "1.234"

    assert list(
        _validator("canadian_compliance_workflow_config").iter_errors(config)
    )
    with pytest.raises(ValueError):
        prepare_canadian_compliance_work_packet(config)


def test_alberta_corporation_gets_federal_provincial_and_registry_review() -> None:
    packet = prepare_canadian_compliance_work_packet(
        resolved_corporation_config()
    )
    obligations = {
        item["obligation_id"]: item for item in packet["obligations"]
    }

    assert {
        "CA-T2-001",
        "AB-AT1-001",
        "AB-REGISTRY-001",
        "AB-WCB-001",
        "AB-PIPA-001",
        "CA-EXPENSE-001",
    }.issubset(obligations)
    assert obligations["CA-T2-001"]["status"] == (
        "fiscal_period_and_professional_review_required"
    )
    assert packet["status"] == "operator_review_required"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("business_number", "synthetic-redacted-value"),
        ("cra_user_id", "synthetic-user"),
        ("sin", "000000000"),
        ("password", "synthetic-placeholder"),
    ],
)
def test_sensitive_identity_and_credential_fields_are_rejected(
    field: str,
    value: str,
) -> None:
    config = resolved_corporation_config()
    config["business_profile"][field] = value

    with pytest.raises(CanadianComplianceError):
        prepare_canadian_compliance_work_packet(config)


def test_email_like_values_are_rejected_even_in_nominal_id_fields() -> None:
    config = resolved_corporation_config()
    config["tenant_id"] = "operator@example.invalid"

    with pytest.raises(CanadianComplianceError):
        prepare_canadian_compliance_work_packet(config)


def test_strict_schema_rejects_unknown_top_level_and_profile_fields() -> None:
    config = resolved_corporation_config()
    config["is_compliant"] = True
    config["business_profile"]["tax_deduction_selected"] = True

    paths = {
        tuple(error.absolute_path)
        for error in _validator(
            "canadian_compliance_workflow_config"
        ).iter_errors(config)
    }

    assert () in paths
    assert ("business_profile",) in paths


def test_non_canadian_profile_is_rejected() -> None:
    config = resolved_corporation_config()
    config["business_profile"]["country"] = "US"

    with pytest.raises((CanadianComplianceError, ValueError)):
        prepare_canadian_compliance_work_packet(config)


@pytest.mark.parametrize("province", ["ZZ", "BC", "ON"])
def test_version_one_rejects_non_alberta_provinces(province: str) -> None:
    config = resolved_corporation_config()
    config["business_profile"]["province"] = province

    assert list(
        _validator("canadian_compliance_workflow_config").iter_errors(config)
    )
    with pytest.raises(ValueError):
        prepare_canadian_compliance_work_packet(config)


def test_packet_is_preparation_only_and_all_external_actions_remain_blocked() -> None:
    packet = prepare_canadian_compliance_work_packet(
        resolved_corporation_config()
    )

    assert packet["external_action_performed"] is False
    assert packet["evidence_level"] == "preparation_only"
    assert all(
        obligation["external_action_performed"] is False
        for obligation in packet["obligations"]
    )
    assert "file_or_amend_t1_t2_t2125_gst_hst_payroll_or_information_returns" in (
        packet["blocked_external_actions"]
    )
    assert "make_tax_payroll_wcb_or_registry_payments" in (
        packet["blocked_external_actions"]
    )
    assert "sign_attest_or_certify_on_behalf_of_a_human" in (
        packet["blocked_external_actions"]
    )


@pytest.mark.parametrize("artifact_mode", ["missing", "relative", "inside"])
def test_workflow_refuses_repository_local_artifact_output(
    tmp_path: Path,
    artifact_mode: str,
) -> None:
    config_path = _write_private_config(tmp_path, compliance_config())
    artifact_root = {
        "missing": None,
        "relative": Path("relative-output"),
        "inside": ROOT / "reports" / "compliance",
    }[artifact_mode]

    with pytest.raises(CanadianComplianceError):
        run_canadian_compliance_workflow(
            ROOT,
            config_path,
            artifact_root,
        )


def test_workflow_writes_only_to_explicit_external_artifact_root(
    tmp_path: Path,
) -> None:
    private_root = _private_artifact_root(tmp_path)
    config_path = _write_private_config(tmp_path, compliance_config())

    result = run_canadian_compliance_workflow(
        ROOT,
        config_path,
        private_root,
    )

    assert all(path.parent == private_root for path in result["paths"].values())
    assert private_root.stat().st_mode & 0o777 == 0o700
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in result["paths"].values()
    )
    _validator("canadian_compliance_run_receipt").validate(result["receipt"])

    with pytest.raises(CanadianComplianceError, match="create-only"):
        run_canadian_compliance_workflow(
            ROOT,
            config_path,
            private_root,
        )


def test_workflow_rejects_caller_supplied_false_repository_root(
    tmp_path: Path,
) -> None:
    false_root = tmp_path / "false-repository"
    false_root.mkdir()
    config_path = _write_private_config(tmp_path, compliance_config())

    with pytest.raises(CanadianComplianceError, match="canonical"):
        run_canadian_compliance_workflow(
            false_root,
            config_path,
            _private_artifact_root(tmp_path),
        )


def test_core_loader_rejects_repository_file_and_permissive_mode(
    tmp_path: Path,
) -> None:
    repository_config = (
        ROOT / "config" / "canadian_compliance_workflow.example.json"
    )
    with pytest.raises(CanadianComplianceError):
        load_canadian_compliance_config(repository_config)

    private_config = _write_private_config(tmp_path, compliance_config())
    private_config.chmod(0o644)
    with pytest.raises(CanadianComplianceError):
        load_canadian_compliance_config(private_config)
