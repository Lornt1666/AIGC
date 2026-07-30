from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from src.core.financial_evidence import (
    FinancialEvidenceError,
    canonical_digest,
    load_financial_evidence_config,
    prepare_financial_evidence_packet,
    run_financial_evidence_workflow,
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


def financial_config() -> dict:
    return {
        "schema_version": "1.0.0",
        "tenant_id": "TENANT-SYNTHETIC",
        "engagement_id": "ENGAGEMENT-SYNTHETIC",
        "work_order_id": "WORK-SYNTHETIC",
        "as_of_date": "2026-07-30",
        "currency": "CAD",
        "projection_version": "synthetic-v1",
        "evidence_scope": {
            "period_start": "2026-01-01",
            "period_end": "2026-07-30",
            "scope_status": "partial",
            "source_classes": [
                "app_store_receipt",
                "payment_processor_receipt",
                "subscription_notice",
            ],
        },
        "records": [
            {
                "record_id": "FIN-OUTFLOW-001",
                "source_ref_id": "SRC-AAAAAAAAAAAAAAAA",
                "source_provider": "apple_app_store",
                "record_type": "settlement_evidence",
                "evidence_state": "itemized_receipt_verified",
                "settlement_state": "settled",
                "allocation_state": "unallocated",
                "direction": "outflow",
                "effective_date": "2026-01-15",
                "amount_minor_units": 12345,
                "counted_in_settled_cash": True,
            },
            {
                "record_id": "FIN-REFUND-001",
                "source_ref_id": "SRC-BBBBBBBBBBBBBBBB",
                "source_provider": "payment_processor",
                "record_type": "settlement_evidence",
                "evidence_state": "payment_processor_verified",
                "settlement_state": "settled",
                "allocation_state": "unallocated",
                "direction": "refund",
                "effective_date": "2026-01-20",
                "amount_minor_units": 2345,
                "counted_in_settled_cash": True,
            },
            {
                "record_id": "FIN-SIGNAL-001",
                "source_ref_id": "SRC-CCCCCCCCCCCCCCCC",
                "source_provider": "other_subscription",
                "record_type": "commercial_obligation_signal",
                "evidence_state": "subscription_signal_unverified",
                "settlement_state": "unverified",
                "allocation_state": "candidate",
                "direction": "outflow",
                "effective_date": "2026-02-01",
                "amount_minor_units": 9999,
                "counted_in_settled_cash": False,
            },
        ],
        "unpaid_work": {
            "rate_scenarios": [
                {
                    "rate_id": "RATE-LOW",
                    "rate_label": "Synthetic lower reference",
                    "hourly_rate_minor_units": 3606,
                    "basis_code": "job_bank_alberta_low",
                },
                {
                    "rate_id": "RATE-REFERENCE",
                    "rate_label": "Synthetic programmer reference",
                    "hourly_rate_minor_units": 4455,
                    "basis_code": "alis_programmer_average",
                },
                {
                    "rate_id": "RATE-HIGH",
                    "rate_label": "Synthetic engineer reference",
                    "hourly_rate_minor_units": 5311,
                    "basis_code": "alis_software_engineer_average",
                },
            ],
            "scenario_hours": [100, 250, 500],
            "projects": [
                {
                    "project_id": "PROJECT-AIGC",
                    "project_label": "Synthetic governed workforce project",
                    "evidence_state": "repository_verified",
                    "documented_minutes": None,
                    "selected_rate_id": None,
                },
                {
                    "project_id": "PROJECT-MARKET",
                    "project_label": "Synthetic market-analysis project",
                    "evidence_state": "owner_stated",
                    "documented_minutes": None,
                    "selected_rate_id": None,
                },
            ],
        },
        "coverage_gaps": [
            "GITHUB_BILLING_RECEIPTS_NOT_OBSERVED",
            "MOBILE_CARRIER_BILLS_NOT_OBSERVED",
        ],
    }


def _write_private_config(tmp_path: Path, payload: dict) -> Path:
    private_parent = tmp_path / "private-config"
    private_parent.mkdir(mode=0o700)
    private_parent.chmod(0o700)
    config_path = private_parent / "financial.json"
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    config_path.chmod(0o600)
    return config_path


def _private_artifact_root(tmp_path: Path, name: str = "financial-output") -> Path:
    private_parent = tmp_path / "private-artifacts"
    private_parent.mkdir(mode=0o700)
    private_parent.chmod(0o700)
    return private_parent / name


def test_financial_config_and_packet_satisfy_strict_schemas() -> None:
    config = financial_config()
    _validator("financial_evidence_config").validate(config)

    packet = prepare_financial_evidence_packet(config)

    _validator("financial_evidence_packet").validate(packet)


def test_repository_example_is_synthetic_schema_valid_and_internal_only() -> None:
    config = json.loads(
        (ROOT / "config" / "financial_evidence.example.json").read_text(
            encoding="utf-8"
        )
    )

    _validator("financial_evidence_config").validate(config)
    packet = prepare_financial_evidence_packet(config)
    _validator("financial_evidence_packet").validate(packet)

    assert packet["external_action_performed"] is False
    assert (
        "SYNTHETIC_FIXTURE_NOT_REAL_FINANCIAL_DATA"
        in packet["coverage_gaps"]
    )


def test_packet_digest_is_deterministic_and_order_stable_for_records_and_estimates() -> None:
    first_config = financial_config()
    reordered = deepcopy(first_config)
    reordered["records"].reverse()
    reordered["unpaid_work"]["rate_scenarios"].reverse()
    reordered["unpaid_work"]["scenario_hours"].reverse()
    reordered["unpaid_work"]["projects"].reverse()

    first = prepare_financial_evidence_packet(first_config)
    second = prepare_financial_evidence_packet(reordered)

    assert first == second
    assert first["packet_digest"] == canonical_digest(
        {
            key: value
            for key, value in first.items()
            if key not in {"packet_id", "packet_digest"}
        }
    )
    assert first["packet_id"].endswith(first["packet_digest"][:18].upper())


def test_integer_minor_unit_totals_keep_cash_refunds_and_signals_separate() -> None:
    packet = prepare_financial_evidence_packet(financial_config())

    assert packet["typed_totals"] == {
        "record_count": 3,
        "counted_settlement_count": 2,
        "settled_cash_outflow_minor_units": 12345,
        "settled_refund_minor_units": 2345,
        "net_settled_cash_outflow_minor_units": 10000,
        "commercial_obligation_signal_minor_units": 9999,
    }
    assert all(
        isinstance(value, int)
        for value in packet["typed_totals"].values()
    )


@pytest.mark.parametrize(
    ("record_index", "counted"),
    [
        (0, False),
        (2, True),
    ],
)
def test_counted_cash_flag_must_follow_evidence_and_settlement_state(
    record_index: int,
    counted: bool,
) -> None:
    config = financial_config()
    config["records"][record_index]["counted_in_settled_cash"] = counted

    assert list(_validator("financial_evidence_config").iter_errors(config))
    with pytest.raises(FinancialEvidenceError):
        prepare_financial_evidence_packet(config)


def test_fractional_minor_units_fail_closed() -> None:
    config = financial_config()
    config["records"][0]["amount_minor_units"] = 123.45

    assert list(_validator("financial_evidence_config").iter_errors(config))
    with pytest.raises(FinancialEvidenceError):
        prepare_financial_evidence_packet(config)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount_minor_units", 9007199254740992),
        ("counted_in_settled_cash", 1),
        ("record_id", 123),
    ],
)
def test_strict_runtime_validation_enforces_nested_types_and_limits(
    field: str,
    value: object,
) -> None:
    config = financial_config()
    config["records"][0][field] = value

    assert list(_validator("financial_evidence_config").iter_errors(config))
    with pytest.raises(ValueError):
        prepare_financial_evidence_packet(config)


@pytest.mark.parametrize("duplicate_field", ["record_id", "source_ref_id"])
def test_duplicate_records_and_sources_are_rejected(
    duplicate_field: str,
) -> None:
    config = financial_config()
    config["records"][1][duplicate_field] = config["records"][0][
        duplicate_field
    ]

    with pytest.raises(FinancialEvidenceError, match="Duplicate"):
        prepare_financial_evidence_packet(config)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "operator@example.invalid"),
        ("card_number", "4000000000000002"),
        ("password", "synthetic-placeholder"),
        ("message_id", "mail-record-001"),
    ],
)
def test_pii_secret_and_raw_source_fields_are_rejected(
    field: str,
    value: str,
) -> None:
    config = financial_config()
    config["records"][0][field] = value

    with pytest.raises(FinancialEvidenceError):
        prepare_financial_evidence_packet(config)


def test_strict_schema_rejects_unknown_top_level_and_nested_fields() -> None:
    config = financial_config()
    config["unreviewed_success_claim"] = True
    config["records"][0]["raw_receipt_text"] = "synthetic"

    paths = {
        tuple(error.absolute_path)
        for error in _validator("financial_evidence_config").iter_errors(config)
    }

    assert () in paths
    assert ("records", 0) in paths


def test_founder_estimate_remains_unselected_without_time_and_rate() -> None:
    packet = prepare_financial_evidence_packet(financial_config())

    for project in packet["unpaid_work"]["projects"]:
        assert project["status"] == "blocked_pending_documented_time"
        assert project["selected_estimate_minor_units"] is None
    assert (
        packet["unpaid_work"]["valuation_status"]
        == "planning_only_not_cash_accounting_or_tax"
    )


@pytest.mark.parametrize(
    ("minutes", "rate_id"),
    [
        (None, "RATE-REFERENCE"),
        (90, "RATE-NOT-REGISTERED"),
    ],
)
def test_selected_founder_value_requires_documented_time_and_registered_rate(
    minutes: int | None,
    rate_id: str | None,
) -> None:
    config = financial_config()
    project = config["unpaid_work"]["projects"][0]
    project["documented_minutes"] = minutes
    project["selected_rate_id"] = rate_id

    with pytest.raises(FinancialEvidenceError):
        prepare_financial_evidence_packet(config)


def test_verified_time_without_reviewed_rate_remains_unselected() -> None:
    config = financial_config()
    project = config["unpaid_work"]["projects"][0]
    project["evidence_state"] = "documented_time_verified"
    project["documented_minutes"] = 90
    project["selected_rate_id"] = None

    packet = prepare_financial_evidence_packet(config)
    prepared = packet["unpaid_work"]["projects"][0]

    assert prepared["status"] == "blocked_pending_reviewed_rate"
    assert prepared["selected_estimate_minor_units"] is None


@pytest.mark.parametrize(
    "evidence_state",
    ["unknown", "owner_stated", "repository_verified"],
)
def test_unverified_time_states_cannot_select_founder_value(
    evidence_state: str,
) -> None:
    config = financial_config()
    project = config["unpaid_work"]["projects"][0]
    project["evidence_state"] = evidence_state
    project["documented_minutes"] = 90
    project["selected_rate_id"] = "RATE-REFERENCE"

    with pytest.raises(FinancialEvidenceError):
        prepare_financial_evidence_packet(config)


def test_fractional_documented_minutes_fail_closed() -> None:
    config = financial_config()
    project = config["unpaid_work"]["projects"][0]
    project["documented_minutes"] = 90.5
    project["selected_rate_id"] = "RATE-REFERENCE"

    assert list(_validator("financial_evidence_config").iter_errors(config))
    with pytest.raises(FinancialEvidenceError):
        prepare_financial_evidence_packet(config)


def test_founder_estimate_is_non_cash_and_uses_integer_half_up_rounding() -> None:
    config = financial_config()
    project = config["unpaid_work"]["projects"][0]
    project["evidence_state"] = "documented_time_verified"
    project["documented_minutes"] = 90
    project["selected_rate_id"] = "RATE-REFERENCE"

    packet = prepare_financial_evidence_packet(config)
    prepared = next(
        item
        for item in packet["unpaid_work"]["projects"]
        if item["project_id"] == "PROJECT-AIGC"
    )

    assert prepared["selected_estimate_minor_units"] == 6683
    assert (
        prepared["status"]
        == "owner_management_estimate_requires_professional_review"
    )
    assert packet["typed_totals"]["net_settled_cash_outflow_minor_units"] == 10000
    assert "selected_estimate_minor_units" not in packet["typed_totals"]


def test_financial_projection_cannot_claim_or_perform_external_action() -> None:
    packet = prepare_financial_evidence_packet(financial_config())

    assert packet["external_action_performed"] is False
    assert "submit_or_amend_a_tax_return" in packet["blocked_actions"]
    assert "make_a_payment_or_remittance" in packet["blocked_actions"]
    assert "create_an_accounting_posting" in packet["blocked_actions"]
    assert all(record.get("external_action_performed") is None for record in packet["records"])


@pytest.mark.parametrize("artifact_mode", ["missing", "relative", "inside"])
def test_workflow_refuses_repository_local_artifact_output(
    tmp_path: Path,
    artifact_mode: str,
) -> None:
    config_path = _write_private_config(tmp_path, financial_config())
    artifact_root = {
        "missing": None,
        "relative": Path("relative-output"),
        "inside": ROOT / "reports" / "financial",
    }[artifact_mode]

    with pytest.raises(FinancialEvidenceError):
        run_financial_evidence_workflow(
            ROOT,
            config_path,
            artifact_root,
        )


def test_workflow_writes_only_to_explicit_external_artifact_root(
    tmp_path: Path,
) -> None:
    private_root = _private_artifact_root(tmp_path)
    config_path = _write_private_config(tmp_path, financial_config())

    result = run_financial_evidence_workflow(
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
    _validator("financial_evidence_run_receipt").validate(result["receipt"])

    with pytest.raises(FinancialEvidenceError, match="create-only"):
        run_financial_evidence_workflow(
            ROOT,
            config_path,
            private_root,
        )


def test_workflow_rejects_caller_supplied_false_repository_root(
    tmp_path: Path,
) -> None:
    false_root = tmp_path / "false-repository"
    false_root.mkdir()
    config_path = _write_private_config(tmp_path, financial_config())

    with pytest.raises(FinancialEvidenceError, match="canonical"):
        run_financial_evidence_workflow(
            false_root,
            config_path,
            _private_artifact_root(tmp_path),
        )


def test_core_loader_rejects_repository_file_and_permissive_mode(
    tmp_path: Path,
) -> None:
    repository_config = ROOT / "config" / "financial_evidence.example.json"
    with pytest.raises(FinancialEvidenceError):
        load_financial_evidence_config(repository_config)

    private_config = _write_private_config(tmp_path, financial_config())
    private_config.chmod(0o644)
    with pytest.raises(FinancialEvidenceError):
        load_financial_evidence_config(private_config)
