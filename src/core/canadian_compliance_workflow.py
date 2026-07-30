from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List

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
GST_HST_SMALL_SUPPLIER_THRESHOLD_CAD = Decimal("30000")
ENTITY_TYPES = {
    "unknown",
    "sole_proprietorship",
    "partnership",
    "corporation",
    "nonprofit",
}
TRISTATE = {"unknown", "yes", "no"}
CONFIG_KEYS = {
    "schema_version",
    "tenant_id",
    "engagement_id",
    "work_order_id",
    "as_of_date",
    "financial_evidence_packet_id",
    "business_profile",
}
PROFILE_KEYS = {
    "country",
    "province",
    "entity_type",
    "fiscal_period_end",
    "accounting_method",
    "has_taxable_supplies",
    "current_quarter_taxable_supplies_cad",
    "previous_four_quarters_taxable_supplies_cad",
    "gst_hst_registration_status",
    "has_employees",
    "payroll_account_status",
    "workers_in_alberta",
    "collects_personal_information",
    "cra_representative_status",
}
SENSITIVE_KEYS = {
    "account_number",
    "bank_account",
    "business_number",
    "card_number",
    "cra_user_id",
    "email",
    "mfa",
    "password",
    "phone",
    "representative_identifier",
    "sin",
    "secret",
    "token",
}
ALLOWED_INTERNAL_ACTIONS = [
    "classify_source_documents_without_setting_tax_treatment",
    "prepare_an_obligation_and_evidence_checklist",
    "calculate_review_candidates_from_operator_supplied_numbers",
    "prepare_a_human_review_packet",
    "generate_a_redacted_records_index",
    "identify_missing_entity_period_remitter_and_authority_facts",
]
BLOCKED_EXTERNAL_ACTIONS = [
    "log_in_to_or_control_a_cra_account",
    "handle_cra_credentials_mfa_or_recovery_material",
    "authorize_or_change_a_cra_representative",
    "register_or_modify_gst_hst_payroll_or_other_program_accounts",
    "file_or_amend_t1_t2_t2125_gst_hst_payroll_or_information_returns",
    "submit_alberta_at1_or_corporate_annual_returns",
    "register_or_report_to_wcb_alberta",
    "make_tax_payroll_wcb_or_registry_payments",
    "select_tax_positions_or_final_expense_classifications",
    "communicate_with_a_regulator_as_the_operator",
    "sign_attest_or_certify_on_behalf_of_a_human",
]
SOURCE_REGISTRY = [
    {
        "source_id": "CRA-RECORDS-RETENTION",
        "publisher": "Canada Revenue Agency",
        "title": "Where to keep your records and for how long",
        "url": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/keeping-records/where-keep-your-records-long-request-permission-destroy-them-early.html",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "General six-year retention rule and exceptions; exact application requires entity and record facts.",
    },
    {
        "source_id": "CRA-BUSINESS-EXPENSES",
        "publisher": "Canada Revenue Agency",
        "title": "Business expenses",
        "url": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/small-businesses-self-employed-income/business-income-tax-reporting/business-expenses.html",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "Source-document and business-expense guidance only; no expense is classified or deducted by this workflow.",
    },
    {
        "source_id": "CRA-GST-HST-REGISTRATION",
        "publisher": "Canada Revenue Agency",
        "title": "When to register for and start charging the GST/HST",
        "url": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/when-register-charge.html",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "General non-charity small-supplier threshold signal; effective dates and exceptions require review.",
    },
    {
        "source_id": "CRA-T2125",
        "publisher": "Canada Revenue Agency",
        "title": "Completing Form T2125",
        "url": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/sole-proprietorships-partnerships/report-business-income-expenses/completing-form-t2125.html",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "General form mapping for sole proprietorship and partnership business or professional activity.",
    },
    {
        "source_id": "CRA-T2-DUE",
        "publisher": "Canada Revenue Agency",
        "title": "When to file your corporation income tax return",
        "url": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/corporations/corporation-income-tax-return/when-file-your-corporation-income-tax-return.html",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "General T2 filing period rule; this workflow does not calculate or file a return.",
    },
    {
        "source_id": "CRA-PAYROLL-REMITTANCE",
        "publisher": "Canada Revenue Agency",
        "title": "Payroll remittance due dates",
        "url": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/remitting-source-deductions/how-when-remit-due-dates.html",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "Due dates depend on remitter type; no date is inferred without an authoritative remitter profile.",
    },
    {
        "source_id": "CRA-REPRESENTATIVE-AUTHORITY",
        "publisher": "Canada Revenue Agency",
        "title": "Representative authorization overview",
        "url": "https://www.canada.ca/en/revenue-agency/services/tax/representative-authorization/overview.html",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "Representative authority must be explicit and remains human/accountable; AIGC does not inherit it.",
    },
    {
        "source_id": "ALBERTA-AT1",
        "publisher": "Government of Alberta",
        "title": "Corporate income tax",
        "url": "https://www.alberta.ca/corporate-income-tax",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "Alberta corporate return preparation signal only; no certified filing or payment action.",
    },
    {
        "source_id": "ALBERTA-ANNUAL-RETURN",
        "publisher": "Government of Alberta",
        "title": "Corporations, cooperatives and organizations annual returns",
        "url": "https://www.alberta.ca/corporations-cooperatives-organizations-annual-returns",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "Registry review signal only; exact entity status and due date require authoritative records.",
    },
    {
        "source_id": "WCB-ALBERTA-COVERAGE",
        "publisher": "Workers' Compensation Board - Alberta",
        "title": "Worker coverage",
        "url": "https://www.wcb.ab.ca/insurance-and-premiums/types-of-coverage/worker-coverage.html",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "Industry and worker facts determine coverage; no registration or reporting is performed.",
    },
    {
        "source_id": "ALBERTA-PIPA",
        "publisher": "Government of Alberta",
        "title": "Personal Information Protection Act",
        "url": "https://www.alberta.ca/personal-information-protection-act",
        "retrieved_at": "2026-07-30",
        "claim_boundary": "Privacy-program review signal for provincially regulated private-sector activity.",
    },
]


class CanadianComplianceError(ValueError):
    """Raised when Canadian compliance preparation cannot proceed safely."""


def load_canadian_compliance_config(path: Path) -> Dict[str, Any]:
    try:
        payload = read_private_json(path, PROJECT_ROOT)
    except PrivateArtifactIOError as exc:
        raise CanadianComplianceError(
            "Canadian compliance config failed its private-file boundary."
        ) from exc
    if not isinstance(payload, dict):
        raise CanadianComplianceError("Canadian compliance config must be a JSON object.")
    return payload


def prepare_canadian_compliance_work_packet(config: Dict[str, Any]) -> Dict[str, Any]:
    _assert_no_sensitive_material(config)
    _validate_contract("canadian_compliance_workflow_config", config)
    _validate_semantics(config)

    profile = config["business_profile"]
    obligations: List[Dict[str, Any]] = [_records_obligation()]
    blockers: List[str] = []
    unknowns: List[str] = _profile_unknowns(profile)

    entity_type = profile["entity_type"]
    if entity_type == "unknown":
        blockers.append("legal_entity_type_unresolved")
        unknowns.append("legal_entity_type")
    elif entity_type in {"sole_proprietorship", "partnership"}:
        obligations.append(_t2125_obligation(entity_type))
    elif entity_type == "corporation":
        obligations.extend(_corporate_obligations(profile["province"]))
    else:
        obligations.append(_nonprofit_classification_obligation())

    gst_obligation, gst_unknowns = _gst_hst_obligation(profile)
    obligations.append(gst_obligation)
    unknowns.extend(gst_unknowns)

    payroll_obligation, payroll_unknowns = _payroll_obligation(profile)
    obligations.append(payroll_obligation)
    unknowns.extend(payroll_unknowns)

    if profile["province"] == "AB":
        obligations.append(_wcb_obligation(profile))
        obligations.append(_pipa_obligation(profile))

    representative_obligation, representative_unknowns = _representative_obligation(
        profile
    )
    obligations.append(representative_obligation)
    unknowns.extend(representative_unknowns)
    obligations.append(_expense_classification_obligation(config))

    unknowns = sorted(set(unknowns))
    if unknowns:
        blockers.append("required_business_facts_missing")
    status = "operator_review_required"
    if entity_type == "unknown":
        status = "authority_unresolved"
    elif unknowns:
        status = "evidence_required"

    packet_core: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "tenant_id": config["tenant_id"],
        "engagement_id": config["engagement_id"],
        "work_order_id": config["work_order_id"],
        "as_of_date": config["as_of_date"],
        "evidence_level": "preparation_only",
        "jurisdiction": {
            "country": "CA",
            "province": profile["province"],
        },
        "status": status,
        "business_profile": profile,
        "financial_evidence_packet_id": config["financial_evidence_packet_id"],
        "obligations": obligations,
        "unknowns": unknowns,
        "blockers": sorted(set(blockers)),
        "allowed_internal_actions": ALLOWED_INTERNAL_ACTIONS,
        "blocked_external_actions": BLOCKED_EXTERNAL_ACTIONS,
        "human_review_obligations": [
            "Operator confirms legal entity, tax periods, registrations, worker facts, and business use.",
            "Qualified Canadian tax/accounting professional reviews tax treatment and filing obligations.",
            "Authorized human reviews every government-facing form, statement, representation, payment, and submission.",
            "Privacy or legal professional reviews regulated, contested, or high-consequence questions.",
        ],
        "sources": SOURCE_REGISTRY,
        "external_action_performed": False,
    }
    digest = canonical_digest(packet_core)
    packet = {
        **packet_core,
        "packet_id": f"AIGC-CA-COMPLIANCE-{digest[:18].upper()}",
        "packet_digest": digest,
    }
    _validate_contract("canadian_compliance_work_packet", packet)
    return packet


def run_canadian_compliance_workflow(
    project_root: Path,
    config_path: Path,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    _assert_canonical_project_root(project_root)
    if artifact_root is None:
        raise CanadianComplianceError(
            "An absolute private artifact_root outside the repository is required."
        )
    config = load_canadian_compliance_config(config_path)
    packet = prepare_canadian_compliance_work_packet(config)
    packet_text = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
    report_text = render_compliance_report(packet)
    receipt_core = {
        "schema_version": "1.0.0",
        "tenant_id": packet["tenant_id"],
        "engagement_id": packet["engagement_id"],
        "packet_id": packet["packet_id"],
        "packet_digest": packet["packet_digest"],
        "status": packet["status"],
        "work_order_id": packet["work_order_id"],
        "as_of_date": packet["as_of_date"],
        "artifact_digests": {
            "packet": _content_digest(packet_text),
            "report": _content_digest(report_text),
        },
        "external_action_performed": False,
    }
    receipt = {**receipt_core, "receipt_digest": canonical_digest(receipt_core)}
    _validate_contract("canadian_compliance_run_receipt", receipt)
    receipt_text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    try:
        paths = write_private_bundle(
            artifact_root,
            PROJECT_ROOT,
            {
                "canadian_compliance_work_packet.json": packet_text,
                "canadian_compliance_review.md": report_text,
                "canadian_compliance_run_receipt.json": receipt_text,
            },
        )
    except PrivateArtifactIOError as exc:
        raise CanadianComplianceError(
            "Compliance artifact bundle failed its private I/O boundary: "
            f"{exc}"
        ) from exc
    return {
        "packet": packet,
        "receipt": receipt,
        "paths": {
            "packet": paths["canadian_compliance_work_packet.json"],
            "report": paths["canadian_compliance_review.md"],
            "receipt": paths["canadian_compliance_run_receipt.json"],
        },
    }


def render_compliance_report(packet: Dict[str, Any]) -> str:
    lines = [
        "# Canadian Compliance Preparation Work Packet",
        "",
        f"- Packet: `{packet['packet_id']}`",
        f"- Status: `{packet['status']}`",
        f"- As of: `{packet['as_of_date']}`",
        f"- Jurisdiction: `{packet['jurisdiction']['country']}-{packet['jurisdiction']['province']}`",
        f"- External action: `{str(packet['external_action_performed']).lower()}`",
        "",
        "## Obligations and review signals",
        "",
    ]
    for obligation in packet["obligations"]:
        lines.append(
            f"- **{obligation['title']}** — `{obligation['status']}` "
            f"(`{obligation['obligation_id']}`)"
        )
    lines.extend(["", "## Unknowns", ""])
    if packet["unknowns"]:
        lines.extend(f"- `{item}`" for item in packet["unknowns"])
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Blocked external actions", ""])
    lines.extend(f"- `{item}`" for item in packet["blocked_external_actions"])
    lines.extend(
        [
            "",
            "This artifact prepares evidence and questions. It is not legal or tax advice,",
            "a filing, a payment, a registration, a representation, or proof of compliance.",
            "",
        ]
    )
    return "\n".join(lines)


def _records_obligation() -> Dict[str, Any]:
    return _obligation(
        "CA-RECORDS-001",
        "CRA records, source documents, retention, and location",
        "records_index_and_retention_review_required",
        [
            "Index receipts and source documents without raw credentials.",
            "Record tax year, retention class, location, and legal-hold state.",
        ],
        ["CRA-RECORDS-RETENTION"],
    )


def _t2125_obligation(entity_type: str) -> Dict[str, Any]:
    return _obligation(
        "CA-INCOME-001",
        "T2125 business or professional activity preparation",
        "preparation_review_required",
        [
            f"Confirm each distinct {entity_type} business or professional activity.",
            "Prepare categorized income and expense evidence without selecting final tax treatment.",
        ],
        ["CRA-T2125"],
    )


def _corporate_obligations(province: str) -> List[Dict[str, Any]]:
    obligations = [
        _obligation(
            "CA-T2-001",
            "Federal T2 corporation income tax return preparation",
            "fiscal_period_and_professional_review_required",
            [
                "Confirm fiscal year end and corporation status.",
                "Prepare a source-bound review package; do not file.",
            ],
            ["CRA-T2-DUE"],
        )
    ]
    if province == "AB":
        obligations.extend(
            [
                _obligation(
                    "AB-AT1-001",
                    "Alberta AT1 corporate income tax preparation",
                    "professional_review_required",
                    [
                        "Prepare an Alberta corporate-tax evidence checklist.",
                        "Use certified filing software only through a separately authorized human process.",
                    ],
                    ["ALBERTA-AT1"],
                ),
                _obligation(
                    "AB-REGISTRY-001",
                    "Alberta corporation annual return review",
                    "registry_record_and_due_date_required",
                    [
                        "Obtain an authoritative registry profile and anniversary information.",
                        "Prepare a manual filing handoff; do not submit.",
                    ],
                    ["ALBERTA-ANNUAL-RETURN"],
                ),
            ]
        )
    return obligations


def _nonprofit_classification_obligation() -> Dict[str, Any]:
    return _obligation(
        "CA-ENTITY-001",
        "Nonprofit entity and filing classification",
        "qualified_professional_classification_required",
        ["Confirm incorporation, registration, activities, and applicable return regime."],
        ["CRA-RECORDS-RETENTION"],
    )


def _gst_hst_obligation(profile: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    unknowns: List[str] = []
    status = "not_indicated_by_profile"
    actions = ["Maintain a rolling taxable-supplies evidence schedule."]
    taxable = profile["has_taxable_supplies"]
    current = _decimal_or_none(profile["current_quarter_taxable_supplies_cad"])
    trailing = _decimal_or_none(
        profile["previous_four_quarters_taxable_supplies_cad"]
    )
    if taxable == "unknown":
        status = "evidence_required"
        unknowns.append("whether_supplies_are_taxable_for_gst_hst")
    elif taxable == "yes":
        if current is None:
            unknowns.append("current_quarter_taxable_supplies_cad")
        if trailing is None:
            unknowns.append("previous_four_quarters_taxable_supplies_cad")
        if current is not None and current > GST_HST_SMALL_SUPPLIER_THRESHOLD_CAD:
            status = "threshold_review_required"
        elif trailing is not None and trailing > GST_HST_SMALL_SUPPLIER_THRESHOLD_CAD:
            status = "threshold_review_required"
        elif current is not None and trailing is not None:
            status = "monitoring_required"
        else:
            status = "evidence_required"
        actions.append(
            "If the general threshold signal is exceeded, stop and obtain exact effective-date and registration advice."
        )
    return (
        _obligation(
            "CA-GST-HST-001",
            "GST/HST small-supplier threshold monitoring",
            status,
            actions,
            ["CRA-GST-HST-REGISTRATION"],
        ),
        unknowns,
    )


def _payroll_obligation(profile: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    unknowns: List[str] = []
    employees = profile["has_employees"]
    if employees == "yes":
        status = "remitter_profile_and_payroll_review_required"
        if profile["payroll_account_status"] == "unknown":
            unknowns.append("payroll_account_status")
    elif employees == "no":
        status = "not_indicated_by_profile"
    else:
        status = "evidence_required"
        unknowns.append("whether_workers_are_employees")
    return (
        _obligation(
            "CA-PAYROLL-001",
            "CRA payroll account, deductions, remittance, and information-return review",
            status,
            [
                "Confirm worker classification and authoritative remitter type.",
                "Do not calculate a due date from assumptions.",
            ],
            ["CRA-PAYROLL-REMITTANCE"],
        ),
        unknowns,
    )


def _wcb_obligation(profile: Dict[str, Any]) -> Dict[str, Any]:
    workers = profile["workers_in_alberta"]
    if profile["has_employees"] == "yes" or (workers is not None and workers > 0):
        status = "industry_and_registration_review_required"
    elif profile["has_employees"] == "unknown" or workers is None:
        status = "evidence_required"
    else:
        status = "not_indicated_by_profile"
    return _obligation(
        "AB-WCB-001",
        "WCB-Alberta coverage and employer-account review",
        status,
        [
            "Confirm industry, worker relationships, start dates, and coverage status.",
            "Prepare a manual review packet only.",
        ],
        ["WCB-ALBERTA-COVERAGE"],
    )


def _pipa_obligation(profile: Dict[str, Any]) -> Dict[str, Any]:
    personal_information = profile["collects_personal_information"]
    status = {
        "yes": "privacy_program_review_required",
        "no": "not_indicated_by_profile",
        "unknown": "evidence_required",
    }[personal_information]
    return _obligation(
        "AB-PIPA-001",
        "Alberta private-sector personal-information governance",
        status,
        [
            "Inventory purposes, consent, access, safeguards, retention, correction, and breach handling.",
            "Keep client and financial evidence tenant-scoped and minimized.",
        ],
        ["ALBERTA-PIPA"],
    )


def _representative_obligation(
    profile: Dict[str, Any],
) -> tuple[Dict[str, Any], List[str]]:
    representative = profile["cra_representative_status"]
    unknowns: List[str] = []
    if representative == "authorized_human":
        status = "human_authority_recorded_not_delegated_to_aigc"
    elif representative == "none":
        status = "no_representative_authority"
    else:
        status = "authority_evidence_required"
        unknowns.append("cra_representative_authority")
    return (
        _obligation(
            "CA-AUTHORITY-001",
            "CRA representative authority and human accountability",
            status,
            [
                "Record only a redacted authority reference and access level.",
                "Keep all CRA interaction and representation with an authorized accountable human.",
            ],
            ["CRA-REPRESENTATIVE-AUTHORITY"],
        ),
        unknowns,
    )


def _expense_classification_obligation(config: Dict[str, Any]) -> Dict[str, Any]:
    status = (
        "financial_evidence_linked_professional_review_required"
        if config["financial_evidence_packet_id"]
        else "financial_evidence_required"
    )
    return _obligation(
        "CA-EXPENSE-001",
        "Business-purpose allocation and expense classification",
        status,
        [
            "Separate verified cash outflows from unverified subscription signals.",
            "Allocate personal, mixed, candidate, and unallocated spending with source evidence.",
            "Keep unpaid founder-work valuation outside cash-expense and tax-deduction totals.",
        ],
        ["CRA-RECORDS-RETENTION", "CRA-BUSINESS-EXPENSES"],
    )


def _obligation(
    obligation_id: str,
    title: str,
    status: str,
    allowed_actions: List[str],
    source_ids: List[str],
) -> Dict[str, Any]:
    return {
        "obligation_id": obligation_id,
        "title": title,
        "status": status,
        "allowed_internal_actions": allowed_actions,
        "source_ids": source_ids,
        "external_action_performed": False,
    }


def _validate_semantics(config: Dict[str, Any]) -> None:
    _assert_exact_keys(config, CONFIG_KEYS, "$")
    if config["schema_version"] != "1.0.0":
        raise CanadianComplianceError("Unsupported compliance schema_version.")
    if not config["tenant_id"] or not config["engagement_id"]:
        raise CanadianComplianceError("Tenant and engagement scope are mandatory.")
    _parse_iso_date(config["as_of_date"], "$.as_of_date")
    profile = config["business_profile"]
    _assert_exact_keys(profile, PROFILE_KEYS, "$.business_profile")
    if profile["country"] != "CA":
        raise CanadianComplianceError("This workflow is limited to Canada.")
    if profile["province"] != "AB":
        raise CanadianComplianceError(
            "Version 1 is limited to Alberta; other provinces require a "
            "separately researched and reviewed workflow."
        )
    if profile["entity_type"] not in ENTITY_TYPES:
        raise CanadianComplianceError("Unsupported entity_type.")
    if profile["accounting_method"] not in {"unknown", "cash", "accrual"}:
        raise CanadianComplianceError("Unsupported accounting_method.")
    if profile["gst_hst_registration_status"] not in {
        "unknown",
        "not_registered",
        "registered",
    }:
        raise CanadianComplianceError("Unsupported GST/HST registration status.")
    if profile["payroll_account_status"] not in {
        "unknown",
        "none",
        "active",
        "closed",
    }:
        raise CanadianComplianceError("Unsupported payroll account status.")
    if profile["cra_representative_status"] not in {
        "unknown",
        "none",
        "authorized_human",
    }:
        raise CanadianComplianceError("Unsupported CRA representative status.")
    if profile["fiscal_period_end"] is not None:
        _parse_iso_date(
            profile["fiscal_period_end"],
            "$.business_profile.fiscal_period_end",
        )
    for key in (
        "has_taxable_supplies",
        "has_employees",
        "collects_personal_information",
    ):
        if profile[key] not in TRISTATE:
            raise CanadianComplianceError(f"{key} must be yes, no, or unknown.")
    if profile["workers_in_alberta"] is not None:
        workers = profile["workers_in_alberta"]
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 0:
            raise CanadianComplianceError(
                "workers_in_alberta must be a non-negative integer or null."
            )
    for key in (
        "current_quarter_taxable_supplies_cad",
        "previous_four_quarters_taxable_supplies_cad",
    ):
        if profile[key] is not None and not isinstance(profile[key], str):
            raise CanadianComplianceError(
                f"{key} must be a decimal string or null."
            )
        value = _decimal_or_none(profile[key])
        if value is not None and value < 0:
            raise CanadianComplianceError(f"{key} cannot be negative.")



def _profile_unknowns(profile: Dict[str, Any]) -> List[str]:
    unknowns: List[str] = []
    if profile["entity_type"] == "corporation" and profile["fiscal_period_end"] is None:
        unknowns.append("fiscal_period_end")
    if profile["accounting_method"] == "unknown":
        unknowns.append("accounting_method")
    if (
        profile["has_taxable_supplies"] == "yes"
        and profile["gst_hst_registration_status"] == "unknown"
    ):
        unknowns.append("gst_hst_registration_status")
    return unknowns


def _assert_no_sensitive_material(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS:
                raise CanadianComplianceError(
                    f"Sensitive field {path}.{key} is prohibited; use a redacted reference."
                )
            _assert_no_sensitive_material(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_sensitive_material(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value, re.I):
            raise CanadianComplianceError(f"Email-like value is prohibited at {path}.")
        if (
            not path.endswith(".financial_evidence_packet_id")
            and re.search(r"\b(?:\d[ -]*?){12,19}\b", value)
        ):
            raise CanadianComplianceError(f"Long account-like value is prohibited at {path}.")


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
        raise CanadianComplianceError(f"{path} has invalid fields: {', '.join(details)}")


def _parse_iso_date(value: Any, path: str) -> date:
    if not isinstance(value, str):
        raise CanadianComplianceError(f"{path} must be an ISO date string.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CanadianComplianceError(f"{path} must be a valid ISO date.") from exc


def _assert_canonical_project_root(project_root: Path) -> None:
    try:
        supplied = project_root.resolve(strict=True)
    except OSError as exc:
        raise CanadianComplianceError(
            "The repository root cannot be verified."
        ) from exc
    if supplied != PROJECT_ROOT:
        raise CanadianComplianceError(
            "The workflow must use its canonical repository root."
        )


def _validate_contract(schema_name: str, payload: Any) -> None:
    try:
        validate_artifact_strict(schema_name, payload)
    except ContractValidationError as exc:
        raise CanadianComplianceError(
            f"{schema_name} does not satisfy its strict contract."
        ) from exc


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise CanadianComplianceError("Boolean is not a numeric amount.")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise CanadianComplianceError(f"Invalid numeric amount: {value!r}") from exc
    if not result.is_finite():
        raise CanadianComplianceError("Numeric amounts must be finite.")
    return result


def canonical_digest(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
