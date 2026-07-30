from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from src.core.canadian_compliance_workflow import (
    CanadianComplianceError,
    load_canadian_compliance_config,
    prepare_canadian_compliance_work_packet,
)
from src.core.contract_validator import ContractValidationError
from src.core.financial_evidence import (
    FinancialEvidenceError,
    PROJECT_ROOT as REPOSITORY_ROOT,
    format_minor_units,
    load_financial_evidence_config,
    prepare_financial_evidence_packet,
)


FEATURE_FLAG = "AIGC_ENABLE_LOCAL_FINANCIAL_EVIDENCE_TAB"
FINANCIAL_CONFIG_ENV = "AIGC_FINANCIAL_EVIDENCE_CONFIG"
COMPLIANCE_CONFIG_ENV = "AIGC_CANADIAN_COMPLIANCE_CONFIG"
TRUTHY_VALUES = {"1", "true", "yes", "on"}


class FinancialEvidencePanelError(ValueError):
    """Raised when the local-only financial panel boundary is violated."""


def is_financial_evidence_tab_enabled(
    environ: Mapping[str, str] | None = None,
) -> bool:
    env = os.environ if environ is None else environ
    return env.get(FEATURE_FLAG, "").strip().lower() in TRUTHY_VALUES


def _assert_canonical_project_root(project_root: Path) -> None:
    try:
        supplied = project_root.resolve(strict=True)
    except OSError as exc:
        raise FinancialEvidencePanelError(
            "The repository root cannot be verified."
        ) from exc
    if supplied != REPOSITORY_ROOT:
        raise FinancialEvidencePanelError(
            "The financial panel must use its canonical repository root."
        )


def load_local_financial_projection(
    project_root: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    if not is_financial_evidence_tab_enabled(env):
        return {
            "status": "disabled",
            "financial_packet": None,
            "compliance_packet": None,
        }

    _assert_canonical_project_root(project_root)
    raw_financial_path = env.get(FINANCIAL_CONFIG_ENV, "").strip()
    if not raw_financial_path:
        return {
            "status": "configuration_required",
            "financial_packet": None,
            "compliance_packet": None,
        }

    financial_packet = prepare_financial_evidence_packet(
        load_financial_evidence_config(Path(raw_financial_path))
    )

    compliance_packet = None
    raw_compliance_path = env.get(COMPLIANCE_CONFIG_ENV, "").strip()
    if raw_compliance_path:
        compliance_packet = prepare_canadian_compliance_work_packet(
            load_canadian_compliance_config(Path(raw_compliance_path))
        )
        _assert_linked_packet_scope(financial_packet, compliance_packet)

    return {
        "status": "ready",
        "financial_packet": financial_packet,
        "compliance_packet": compliance_packet,
    }


def _assert_linked_packet_scope(
    financial_packet: dict[str, Any],
    compliance_packet: dict[str, Any],
) -> None:
    required_matches = {
        "tenant_id": (
            financial_packet["tenant_id"],
            compliance_packet["tenant_id"],
        ),
        "engagement_id": (
            financial_packet["engagement_id"],
            compliance_packet["engagement_id"],
        ),
        "as_of_date": (
            financial_packet["as_of_date"],
            compliance_packet["as_of_date"],
        ),
        "financial_evidence_packet_id": (
            financial_packet["packet_id"],
            compliance_packet["financial_evidence_packet_id"],
        ),
    }
    mismatches = [
        field
        for field, (expected, observed) in required_matches.items()
        if expected != observed
    ]
    if mismatches:
        raise FinancialEvidencePanelError(
            "Financial and compliance packets are not bound to the same "
            f"scope: {', '.join(sorted(mismatches))}."
        )


def render_financial_evidence_tab(
    st: Any,
    project_root: Path,
    environ: Mapping[str, str] | None = None,
) -> None:
    st.header("Financial Evidence")
    st.caption(
        "Local, read-only evidence projection. It is not an accounting ledger, "
        "tax return, tax opinion, payroll record, or filing interface."
    )

    try:
        state = load_local_financial_projection(project_root, environ)
    except (
        CanadianComplianceError,
        ContractValidationError,
        FinancialEvidenceError,
        FinancialEvidencePanelError,
        OSError,
        ValueError,
    ):
        st.error(
            "The private projection failed closed. Review its schema, scope, "
            "location, and evidence classifications outside this interface."
        )
        return

    if state["status"] == "disabled":
        st.warning(
            "Disabled by default. This local cockpit is not a production "
            "multi-tenant financial-data boundary."
        )
        st.info(
            "Enable only for an isolated local review session with a schema-valid "
            "config stored outside the repository."
        )
        return
    if state["status"] == "configuration_required":
        st.info(
            "The local feature flag is enabled, but no external financial "
            "projection config has been supplied."
        )
        return

    packet = state["financial_packet"]
    totals = packet["typed_totals"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Settled cash outflow",
        format_minor_units(totals["settled_cash_outflow_minor_units"]),
    )
    col2.metric(
        "Settled refunds",
        format_minor_units(totals["settled_refund_minor_units"]),
    )
    col3.metric(
        "Net settled cash",
        format_minor_units(totals["net_settled_cash_outflow_minor_units"]),
    )
    col4.metric("Counted receipts", totals["counted_settlement_count"])

    st.subheader("Evidence coverage")
    st.write(
        {
            "period": (
                f"{packet['evidence_scope']['period_start']} to "
                f"{packet['evidence_scope']['period_end']}"
            ),
            "scope_status": packet["evidence_scope"]["scope_status"],
            "record_count": totals["record_count"],
            "obligation_signal_total": format_minor_units(
                totals["commercial_obligation_signal_minor_units"]
            ),
        }
    )
    if packet["coverage_gaps"]:
        st.warning("Coverage is incomplete.")
        for gap in packet["coverage_gaps"]:
            st.markdown(f"- `{gap}`")

    provider_rows = _safe_provider_summary(packet)
    if provider_rows:
        st.subheader("Verified settlement evidence by source class")
        st.dataframe(provider_rows, use_container_width=True)

    st.subheader("Non-cash founder-work scenarios")
    st.warning(
        "These are planning scenarios only. They do not enter cash, expense, "
        "tax, GST/HST, payroll, liability, invoice, or revenue totals."
    )
    project_rows = _safe_project_summary(packet)
    if project_rows:
        st.dataframe(project_rows, use_container_width=True)

    compliance = state["compliance_packet"]
    st.subheader("Canadian compliance preparation")
    if compliance is None:
        st.info("No separate Canadian compliance preparation packet is loaded.")
    else:
        st.write(
            {
                "status": compliance["status"],
                "evidence_level": compliance["evidence_level"],
                "jurisdiction": (
                    f"{compliance['jurisdiction']['country']}-"
                    f"{compliance['jurisdiction']['province']}"
                ),
                "unknown_count": len(compliance["unknowns"]),
                "blocker_count": len(compliance["blockers"]),
                "external_action_performed": False,
            }
        )
        st.dataframe(
            [
                {
                    "obligation": item["obligation_id"],
                    "status": item["status"],
                }
                for item in compliance["obligations"]
            ],
            use_container_width=True,
        )

    st.error(
        "CRA login, filing, registration, representative changes, payments, "
        "final tax classification, and external transmission are blocked."
    )


def _safe_provider_summary(packet: dict[str, Any]) -> list[dict[str, Any]]:
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for record in packet["records"]:
        if not record["counted_in_settled_cash"]:
            continue
        provider = record["source_provider"]
        signed_amount = (
            -record["amount_minor_units"]
            if record["direction"] == "refund"
            else record["amount_minor_units"]
        )
        totals[provider] = totals.get(provider, 0) + signed_amount
        counts[provider] = counts.get(provider, 0) + 1
    return [
        {
            "source_class": provider,
            "count": counts[provider],
            "net_settled_cash": format_minor_units(totals[provider]),
        }
        for provider in sorted(totals)
    ]


def _safe_project_summary(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for project in packet["unpaid_work"]["projects"]:
        selected = project["selected_estimate_minor_units"]
        rows.append(
            {
                "project": project["project_label"],
                "evidence_state": project["evidence_state"],
                "documented_hours": (
                    None
                    if project["documented_minutes"] is None
                    else project["documented_minutes"] / 60
                ),
                "selected_planning_value": (
                    None if selected is None else format_minor_units(selected)
                ),
                "status": project["status"],
            }
        )
    return rows
