from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import (
    ContractValidationError,
    validate_artifact_strict,
)
from src.core.private_artifact_io import (
    PrivateArtifactIOError,
    read_private_json,
    write_private_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTLEMENT_EVIDENCE = {
    "itemized_receipt_verified",
    "payment_processor_verified",
}
ALLOWED_EVIDENCE_STATES = SETTLEMENT_EVIDENCE | {
    "subscription_signal_unverified",
    "owner_stated",
}
ALLOWED_SETTLEMENT_STATES = {"settled", "unverified", "reversed", "indeterminate"}
ALLOWED_ALLOCATION_STATES = {"unallocated", "candidate", "mixed", "personal"}
ALLOWED_RECORD_TYPES = {"settlement_evidence", "commercial_obligation_signal"}
ALLOWED_DIRECTIONS = {"outflow", "refund"}
ALLOWED_SOURCE_PROVIDERS = {
    "apple_app_store",
    "google_play",
    "github",
    "openai",
    "other_subscription",
    "payment_processor",
    "telecom",
    "other",
}
ALLOWED_SOURCE_CLASSES = {
    "app_store_receipt",
    "google_play_receipt",
    "github_billing_receipt",
    "ai_provider_receipt",
    "payment_processor_receipt",
    "telecom_receipt",
    "subscription_notice",
    "owner_statement",
}
ALLOWED_PROJECT_EVIDENCE_STATES = {
    "documented_time_verified",
    "repository_verified",
    "owner_stated",
    "unknown",
}
ALLOWED_RATE_BASIS_CODES = {
    "job_bank_alberta_low",
    "alis_programmer_average",
    "alis_software_engineer_average",
}
CONFIG_KEYS = {
    "schema_version",
    "tenant_id",
    "engagement_id",
    "work_order_id",
    "as_of_date",
    "currency",
    "projection_version",
    "evidence_scope",
    "records",
    "unpaid_work",
    "coverage_gaps",
}
EVIDENCE_SCOPE_KEYS = {
    "period_start",
    "period_end",
    "scope_status",
    "source_classes",
}
RECORD_KEYS = {
    "record_id",
    "source_ref_id",
    "source_provider",
    "record_type",
    "evidence_state",
    "settlement_state",
    "allocation_state",
    "direction",
    "effective_date",
    "amount_minor_units",
    "counted_in_settled_cash",
}
UNPAID_WORK_KEYS = {"rate_scenarios", "scenario_hours", "projects"}
RATE_SCENARIO_KEYS = {
    "rate_id",
    "rate_label",
    "hourly_rate_minor_units",
    "basis_code",
}
PROJECT_KEYS = {
    "project_id",
    "project_label",
    "evidence_state",
    "documented_minutes",
    "selected_rate_id",
}
SENSITIVE_KEY_TOKENS = {
    "account_number",
    "apple_account",
    "bank_account",
    "billing_address",
    "card",
    "card_number",
    "cra_user_id",
    "credit_card",
    "description",
    "email",
    "full_name",
    "invoice_id",
    "line_items",
    "memo",
    "message_id",
    "mfa",
    "name",
    "order_id",
    "password",
    "payment_method",
    "phone",
    "postal_address",
    "raw_mime",
    "sin",
    "source_url",
    "secret",
    "token",
    "transaction_id",
}
BLOCKED_ACTIONS = [
    "submit_or_amend_a_tax_return",
    "register_or_modify_a_cra_program_account",
    "make_a_payment_or_remittance",
    "classify_an_expense_as_tax_deductible",
    "create_an_accounting_posting",
    "select_a_tax_position",
    "represent_the_operator_before_a_regulator",
    "log_in_to_cra_or_handle_credentials",
    "send_financial_records_to_an_external_party",
]


class FinancialEvidenceError(ValueError):
    """Raised when a financial-evidence projection is unsafe or inconsistent."""


def load_financial_evidence_config(path: Path) -> Dict[str, Any]:
    try:
        payload = read_private_json(path, PROJECT_ROOT)
    except PrivateArtifactIOError as exc:
        raise FinancialEvidenceError(
            "Financial evidence config failed its private-file boundary."
        ) from exc
    if not isinstance(payload, dict):
        raise FinancialEvidenceError("Financial evidence config must be a JSON object.")
    return payload


def prepare_financial_evidence_packet(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a deterministic, read-only financial-evidence projection.

    This is intentionally not an accounting ledger. It does not create
    accounting postings, tax assertions, payroll, invoices, or external effects.
    """

    _assert_no_sensitive_material(config)
    _validate_contract("financial_evidence_config", config)
    _validate_config_semantics(config)

    records = sorted(
        [dict(record) for record in config["records"]],
        key=lambda record: (record["effective_date"], record["record_id"]),
    )
    totals = _summarize_records(records)
    unpaid_work = _build_unpaid_work_estimates(config["unpaid_work"])

    packet_core: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "tenant_id": config["tenant_id"],
        "engagement_id": config["engagement_id"],
        "work_order_id": config["work_order_id"],
        "as_of_date": config["as_of_date"],
        "currency": "CAD",
        "projection_version": config["projection_version"],
        "evidence_scope": {
            **config["evidence_scope"],
            "source_classes": sorted(config["evidence_scope"]["source_classes"]),
        },
        "typed_totals": totals,
        "records": records,
        "unpaid_work": unpaid_work,
        "coverage_gaps": sorted(config["coverage_gaps"]),
        "accounting_boundaries": [
            "Settlement evidence is a cash-event projection, not proof of business purpose, accounting expense, or deductibility.",
            "Commercial obligations, renewal notices, expirations, and failed-payment notices never enter settled-cash totals.",
            "Personal, mixed, candidate, and unallocated states are review queues, not tax conclusions.",
            "Recognized accounting expense, GST/HST input-tax-credit candidates, and tax deductions are outside version 1.",
            "Non-cash founder effort never enters cash, expense, liability, tax, GST/HST, payroll, filing, or revenue totals.",
            "No founder-work amount is selected until documented time and a reviewed rate basis exist.",
        ],
        "blocked_actions": BLOCKED_ACTIONS,
        "external_action_performed": False,
    }
    packet_digest = canonical_digest(packet_core)
    packet = {
        **packet_core,
        "packet_id": f"AIGC-FIN-EVIDENCE-{packet_digest[:18].upper()}",
        "packet_digest": packet_digest,
    }
    _validate_contract("financial_evidence_packet", packet)
    return packet


def run_financial_evidence_workflow(
    project_root: Path,
    config_path: Path,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    _assert_canonical_project_root(project_root)
    if artifact_root is None:
        raise FinancialEvidenceError(
            "An absolute private artifact_root outside the repository is required."
        )
    config = load_financial_evidence_config(config_path)
    packet = prepare_financial_evidence_packet(config)
    packet_text = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
    report_text = render_financial_evidence_report(packet)

    receipt_core = {
        "schema_version": "1.0.0",
        "tenant_id": packet["tenant_id"],
        "engagement_id": packet["engagement_id"],
        "packet_id": packet["packet_id"],
        "packet_digest": packet["packet_digest"],
        "work_order_id": packet["work_order_id"],
        "as_of_date": packet["as_of_date"],
        "artifact_digests": {
            "packet": _content_digest(packet_text),
            "report": _content_digest(report_text),
        },
        "status": "internal_evidence_projection_prepared",
        "external_action_performed": False,
    }
    receipt = {**receipt_core, "receipt_digest": canonical_digest(receipt_core)}
    _validate_contract("financial_evidence_run_receipt", receipt)
    receipt_text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    try:
        paths = write_private_bundle(
            artifact_root,
            PROJECT_ROOT,
            {
                "financial_evidence_packet.json": packet_text,
                "financial_evidence_report.md": report_text,
                "financial_evidence_run_receipt.json": receipt_text,
            },
        )
    except PrivateArtifactIOError as exc:
        raise FinancialEvidenceError(
            "Financial evidence artifact bundle failed its private I/O boundary: "
            f"{exc}"
        ) from exc
    return {
        "packet": packet,
        "receipt": receipt,
        "paths": {
            "packet": paths["financial_evidence_packet.json"],
            "report": paths["financial_evidence_report.md"],
            "receipt": paths["financial_evidence_run_receipt.json"],
        },
    }


def render_financial_evidence_report(packet: Dict[str, Any]) -> str:
    totals = packet["typed_totals"]
    lines = [
        "# AIGC Financial Evidence Register",
        "",
        f"- Packet: `{packet['packet_id']}`",
        f"- As of: `{packet['as_of_date']}`",
        f"- Currency: `{packet['currency']}`",
        f"- Counted settlement records: `{totals['counted_settlement_count']}`",
        f"- Settled cash outflow: `{format_minor_units(totals['settled_cash_outflow_minor_units'])}`",
        f"- Settled refunds: `{format_minor_units(totals['settled_refund_minor_units'])}`",
        f"- Net settled cash outflow: `{format_minor_units(totals['net_settled_cash_outflow_minor_units'])}`",
        f"- Unverified obligation signals: `{format_minor_units(totals['commercial_obligation_signal_minor_units'])}`",
        "",
        "## Evidence boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in packet["accounting_boundaries"])
    lines.extend(["", "## Coverage gaps", ""])
    lines.extend(f"- {item}" for item in packet["coverage_gaps"])
    lines.extend(["", "## Non-cash founder effort", ""])
    for project in packet["unpaid_work"]["projects"]:
        selected = project["selected_estimate_minor_units"]
        selected_text = (
            "not selected" if selected is None else format_minor_units(selected)
        )
        lines.append(
            f"- **{project['project_label']}** — `{project['status']}`; "
            f"documented minutes: `{project['documented_minutes']}`; "
            f"selected planning value: `{selected_text}`"
        )
    lines.extend(
        [
            "",
            "Founder-effort scenarios are management estimates only. They are not cash",
            "spending, payroll, an invoice, revenue, a tax deduction, or proof of market value.",
            "",
            "## Prohibited automation",
            "",
        ]
    )
    lines.extend(f"- `{action}`" for action in packet["blocked_actions"])
    lines.extend(
        [
            "",
            f"`external_action_performed={str(packet['external_action_performed']).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def canonical_digest(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def format_minor_units(value: int) -> str:
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    return f"{sign}${absolute // 100:,}.{absolute % 100:02d} CAD"


def _validate_config_semantics(config: Dict[str, Any]) -> None:
    _assert_exact_keys(config, CONFIG_KEYS, "$")
    if config.get("schema_version") != "1.0.0":
        raise FinancialEvidenceError("Unsupported financial evidence schema_version.")
    if config.get("currency") != "CAD":
        raise FinancialEvidenceError("Version 1 accepts CAD projections only.")
    if not config["tenant_id"] or not config["engagement_id"]:
        raise FinancialEvidenceError("Tenant and engagement scope are mandatory.")
    as_of_date = _parse_iso_date(config["as_of_date"], "$.as_of_date")

    scope = config["evidence_scope"]
    _assert_exact_keys(scope, EVIDENCE_SCOPE_KEYS, "$.evidence_scope")
    period_start = _parse_iso_date(scope["period_start"], "$.evidence_scope.period_start")
    period_end = _parse_iso_date(scope["period_end"], "$.evidence_scope.period_end")
    if period_start > period_end:
        raise FinancialEvidenceError("Evidence period_start cannot follow period_end.")
    if period_end > as_of_date:
        raise FinancialEvidenceError("Evidence period cannot end after as_of_date.")
    if scope["scope_status"] not in {"partial", "complete"}:
        raise FinancialEvidenceError("Evidence scope_status must be partial or complete.")
    source_classes = scope["source_classes"]
    if not source_classes:
        raise FinancialEvidenceError("At least one evidence source class is required.")
    if len(set(source_classes)) != len(source_classes):
        raise FinancialEvidenceError("Evidence source_classes must be unique.")
    unsupported_sources = set(source_classes) - ALLOWED_SOURCE_CLASSES
    if unsupported_sources:
        raise FinancialEvidenceError(
            f"Unsupported evidence source classes: {sorted(unsupported_sources)}"
        )

    record_ids: set[str] = set()
    source_refs: set[str] = set()
    for index, record in enumerate(config["records"]):
        _assert_exact_keys(record, RECORD_KEYS, f"$.records[{index}]")
        record_id = str(record["record_id"])
        source_ref = str(record["source_ref_id"])
        if record_id in record_ids:
            raise FinancialEvidenceError(f"Duplicate record_id: {record_id}")
        if source_ref in source_refs:
            raise FinancialEvidenceError(f"Duplicate source_ref_id: {source_ref}")
        if not re.fullmatch(r"SRC-[A-Z0-9]{16,64}", source_ref):
            raise FinancialEvidenceError(
                f"{record_id} source_ref_id must be opaque and non-predictable."
            )
        record_ids.add(record_id)
        source_refs.add(source_ref)

        if record["source_provider"] not in ALLOWED_SOURCE_PROVIDERS:
            raise FinancialEvidenceError(f"{record_id} has unsupported source_provider.")
        if record["record_type"] not in ALLOWED_RECORD_TYPES:
            raise FinancialEvidenceError(f"{record_id} has unsupported record_type.")
        if record["evidence_state"] not in ALLOWED_EVIDENCE_STATES:
            raise FinancialEvidenceError(f"{record_id} has unsupported evidence_state.")
        if record["settlement_state"] not in ALLOWED_SETTLEMENT_STATES:
            raise FinancialEvidenceError(f"{record_id} has unsupported settlement_state.")
        if record["allocation_state"] not in ALLOWED_ALLOCATION_STATES:
            raise FinancialEvidenceError(f"{record_id} has unsupported allocation_state.")
        if record["direction"] not in ALLOWED_DIRECTIONS:
            raise FinancialEvidenceError(f"{record_id} has unsupported direction.")
        if (
            isinstance(record["amount_minor_units"], bool)
            or not isinstance(record["amount_minor_units"], int)
            or record["amount_minor_units"] < 0
        ):
            raise FinancialEvidenceError(
                f"{record_id} amount_minor_units must be a non-negative integer."
            )
        effective_date = _parse_iso_date(
            record["effective_date"],
            f"$.records[{index}].effective_date",
        )
        if effective_date < period_start or effective_date > period_end:
            raise FinancialEvidenceError(
                f"{record_id} effective_date is outside the evidence scope."
            )

        should_count = (
            record["record_type"] == "settlement_evidence"
            and record["evidence_state"] in SETTLEMENT_EVIDENCE
            and record["settlement_state"] == "settled"
        )
        if bool(record["counted_in_settled_cash"]) is not should_count:
            raise FinancialEvidenceError(
                f"{record_id} counted_in_settled_cash contradicts its typed states."
            )

    unpaid = config["unpaid_work"]
    _assert_exact_keys(unpaid, UNPAID_WORK_KEYS, "$.unpaid_work")
    rate_ids = {item["rate_id"] for item in unpaid["rate_scenarios"]}
    if len(rate_ids) != len(unpaid["rate_scenarios"]):
        raise FinancialEvidenceError("Unpaid-work rate IDs must be unique.")
    if not unpaid["scenario_hours"]:
        raise FinancialEvidenceError("At least one scenario-hour value is required.")
    if len(set(unpaid["scenario_hours"])) != len(unpaid["scenario_hours"]):
        raise FinancialEvidenceError("Unpaid-work scenario hours must be unique.")
    for hours in unpaid["scenario_hours"]:
        if isinstance(hours, bool) or not isinstance(hours, int) or hours <= 0:
            raise FinancialEvidenceError("Scenario hours must be positive integers.")
    for index, rate in enumerate(unpaid["rate_scenarios"]):
        _assert_exact_keys(
            rate,
            RATE_SCENARIO_KEYS,
            f"$.unpaid_work.rate_scenarios[{index}]",
        )
        if (
            isinstance(rate["hourly_rate_minor_units"], bool)
            or not isinstance(rate["hourly_rate_minor_units"], int)
            or rate["hourly_rate_minor_units"] <= 0
        ):
            raise FinancialEvidenceError("Hourly rate scenarios must be positive.")
        if rate["basis_code"] not in ALLOWED_RATE_BASIS_CODES:
            raise FinancialEvidenceError("Unsupported founder-work rate basis.")
    project_ids: set[str] = set()
    for index, project in enumerate(unpaid["projects"]):
        _assert_exact_keys(
            project,
            PROJECT_KEYS,
            f"$.unpaid_work.projects[{index}]",
        )
        if project["project_id"] in project_ids:
            raise FinancialEvidenceError("Unpaid-work project IDs must be unique.")
        project_ids.add(project["project_id"])
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,63}", project["project_id"]):
            raise FinancialEvidenceError(
                f"{project['project_id']} is not a bounded opaque project ID."
            )
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .&()+/_-]{0,79}", project["project_label"]):
            raise FinancialEvidenceError(
                f"{project['project_id']} has an unsafe project label."
            )
        if project["evidence_state"] not in ALLOWED_PROJECT_EVIDENCE_STATES:
            raise FinancialEvidenceError(
                f"{project['project_id']} has unsupported evidence_state."
            )
        minutes = project["documented_minutes"]
        selected_rate = project["selected_rate_id"]
        if minutes is None and selected_rate is not None:
            raise FinancialEvidenceError(
                f"{project['project_id']} cannot select a rate without documented time."
            )
        if minutes is not None:
            if (
                isinstance(minutes, bool)
                or not isinstance(minutes, int)
                or minutes < 0
            ):
                raise FinancialEvidenceError(
                    f"{project['project_id']} documented_minutes must be non-negative."
                )
            if project["evidence_state"] != "documented_time_verified":
                raise FinancialEvidenceError(
                    f"{project['project_id']} cannot use documented_minutes until "
                    "time evidence is independently verified."
                )
            if selected_rate is not None and selected_rate not in rate_ids:
                raise FinancialEvidenceError(
                    f"{project['project_id']} requires a valid selected rate."
                )

    for index, gap in enumerate(config["coverage_gaps"]):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", gap):
            raise FinancialEvidenceError(
                f"Coverage gap at index {index} must be a bounded uppercase code."
            )


def _summarize_records(records: List[Dict[str, Any]]) -> Dict[str, int]:
    counted = [record for record in records if record["counted_in_settled_cash"]]
    outflows = [
        record for record in counted if record["direction"] == "outflow"
    ]
    refunds = [record for record in counted if record["direction"] == "refund"]
    obligations = [
        record
        for record in records
        if record["record_type"] == "commercial_obligation_signal"
    ]
    outflow_total = _sum_minor_units(outflows)
    refund_total = _sum_minor_units(refunds)
    return {
        "record_count": len(records),
        "counted_settlement_count": len(counted),
        "settled_cash_outflow_minor_units": outflow_total,
        "settled_refund_minor_units": refund_total,
        "net_settled_cash_outflow_minor_units": outflow_total - refund_total,
        "commercial_obligation_signal_minor_units": _sum_minor_units(obligations),
    }


def _build_unpaid_work_estimates(unpaid: Dict[str, Any]) -> Dict[str, Any]:
    rates = sorted(
        [dict(rate) for rate in unpaid["rate_scenarios"]],
        key=lambda rate: rate["hourly_rate_minor_units"],
    )
    scenario_hours = sorted(int(hours) for hours in unpaid["scenario_hours"])
    projects: List[Dict[str, Any]] = []
    for project in sorted(unpaid["projects"], key=lambda item: item["project_id"]):
        documented_minutes = project["documented_minutes"]
        selected_rate_id = project["selected_rate_id"]
        selected_estimate = None
        status = "blocked_pending_documented_time"
        if documented_minutes is not None and selected_rate_id is None:
            status = "blocked_pending_reviewed_rate"
        elif documented_minutes is not None and selected_rate_id is not None:
            rate = next(item for item in rates if item["rate_id"] == selected_rate_id)
            selected_estimate = _round_minutes_value(
                documented_minutes,
                rate["hourly_rate_minor_units"],
            )
            status = "owner_management_estimate_requires_professional_review"

        scenarios = []
        for hours in scenario_hours:
            values = [hours * rate["hourly_rate_minor_units"] for rate in rates]
            scenarios.append(
                {
                    "hours": hours,
                    "low_minor_units": min(values),
                    "reference_minor_units": values[len(values) // 2],
                    "high_minor_units": max(values),
                }
            )
        projects.append(
            {
                **project,
                "status": status,
                "selected_estimate_minor_units": selected_estimate,
                "planning_scenarios": scenarios,
            }
        )
    return {
        "valuation_status": "planning_only_not_cash_accounting_or_tax",
        "rate_scenarios": rates,
        "projects": projects,
    }


def _round_minutes_value(minutes: int, hourly_rate_minor_units: int) -> int:
    # Half-up to the nearest cent without binary floating point.
    numerator = minutes * hourly_rate_minor_units
    quotient, remainder = divmod(numerator, 60)
    return quotient + (1 if remainder >= 30 else 0)


def _assert_no_sensitive_material(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in SENSITIVE_KEY_TOKENS:
                raise FinancialEvidenceError(
                    f"Sensitive/free-text field {path}.{key} is prohibited; use an opaque source reference."
                )
            _assert_no_sensitive_material(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_sensitive_material(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value, re.I):
            raise FinancialEvidenceError(f"Email-like value is prohibited at {path}.")
        if re.search(r"\b(?:\d[ -]*?){12,19}\b", value):
            raise FinancialEvidenceError(
                f"Payment-card or long account-like value is prohibited at {path}."
            )
        if re.search(r"(?i)\b(?:password|api[_ -]?key|one[- ]time code|mfa code)\b", value):
            raise FinancialEvidenceError(f"Secret-like text is prohibited at {path}.")


def _assert_exact_keys(value: Dict[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if unknown:
            details.append(f"unknown={unknown}")
        raise FinancialEvidenceError(f"{path} has invalid fields: {', '.join(details)}")


def _parse_iso_date(value: Any, path: str) -> date:
    if not isinstance(value, str):
        raise FinancialEvidenceError(f"{path} must be an ISO date string.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise FinancialEvidenceError(f"{path} must be a valid ISO date.") from exc


def _assert_canonical_project_root(project_root: Path) -> None:
    try:
        supplied = project_root.resolve(strict=True)
    except OSError as exc:
        raise FinancialEvidenceError(
            "The repository root cannot be verified."
        ) from exc
    if supplied != PROJECT_ROOT:
        raise FinancialEvidenceError(
            "The workflow must use its canonical repository root."
        )


def _validate_contract(schema_name: str, payload: Any) -> None:
    try:
        validate_artifact_strict(schema_name, payload)
    except ContractValidationError as exc:
        raise FinancialEvidenceError(
            f"{schema_name} does not satisfy its strict contract."
        ) from exc


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _sum_minor_units(records: Iterable[Dict[str, Any]]) -> int:
    return sum(int(record["amount_minor_units"]) for record in records)
