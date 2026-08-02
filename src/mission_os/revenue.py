"""Repository-specific, read-only revenue projections for Ω Mission OS."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping


REVENUE_SOURCES = {
    "opportunities": "data/phase2_processed/aigc_phase2_opportunity_queue.json",
    "assessments": "data/phase3_processed/aigc_phase3_assessment_dossiers.json",
    "proposals": "data/phase4_proposals/aigc_phase4_proposal_packages.json",
    "authorizations": "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
    "executions": "data/phase6_execution/aigc_phase6_execution_receipts.json",
    "finance": "data/phase15_finance/aigc_phase15_finance_ledger.json",
    "compliance": "data/phase16_compliance/aigc_phase16_compliance_reviews.json",
    "fidelity": "data/phase20_fidelity/aigc_phase20_fidelity_reviews.json",
    "customer": "data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json",
    "quality": "data/phase22_quality/aigc_phase22_quality_kernel_records.json",
}


def _records(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        for key in ("records", "items", "opportunities", "proposals", "packets", "reviews"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, Mapping)]
        return [value]
    return []


def _load(root: Path, relative_path: str) -> tuple[str, list[Mapping[str, Any]]]:
    path = (root / relative_path).resolve()
    if root != path and root not in path.parents:
        raise ValueError(f"revenue source escapes repository root: {relative_path}")
    if not path.is_file():
        return "MISSING", []
    try:
        return "AVAILABLE", _records(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "INVALID", []


def _money(record: Mapping[str, Any], keys: Iterable[str]) -> float:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0.0, float(value))
    return 0.0


def project_revenue_pipeline(repository_root: Path | str) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    loaded: dict[str, list[Mapping[str, Any]]] = {}
    source_status: dict[str, str] = {}
    for source_id, path in REVENUE_SOURCES.items():
        status, records = _load(root, path)
        source_status[source_id] = status
        loaded[source_id] = records

    finance = loaded["finance"]
    proposed = sum(_money(item, ("proposed_value", "estimated_revenue", "pipeline_value", "amount")) for item in finance)
    contracted = sum(_money(item, ("contracted_value", "contract_value")) for item in finance)
    invoiced = sum(_money(item, ("invoiced_value", "invoice_amount")) for item in finance)
    collected = sum(
        _money(item, ("collected_revenue", "cash_collected", "collected_value"))
        for item in finance
        if item.get("evidence_ids") or item.get("receipt_id") or item.get("collection_evidence")
    )

    pending_approvals = sum(
        1 for item in loaded["authorizations"]
        if str(item.get("decision") or item.get("status") or "").upper() in {"PENDING", "NOT_REQUESTED", "APPROVAL_REQUIRED"}
    )
    approved = sum(
        1 for item in loaded["authorizations"]
        if str(item.get("decision") or item.get("status") or "").lower() in {"approved_for_phase_6", "approved"}
    )

    return {
        "mode": "READ_ONLY",
        "source_status": source_status,
        "funnel": {
            "opportunities": len(loaded["opportunities"]),
            "assessments": len(loaded["assessments"]),
            "proposals": len(loaded["proposals"]),
            "pending_approvals": pending_approvals,
            "approved_for_controlled_execution": approved,
            "execution_receipts": len(loaded["executions"]),
            "compliance_reviews": len(loaded["compliance"]),
            "fidelity_reviews": len(loaded["fidelity"]),
            "customer_forecasts": len(loaded["customer"]),
            "quality_reviews": len(loaded["quality"]),
        },
        "financials": {
            "currency": "CAD",
            "estimated_pipeline": round(proposed, 2),
            "contracted": round(contracted, 2),
            "invoiced": round(invoiced, 2),
            "verified_collected": round(collected, 2),
            "verification_rule": "Collected revenue requires an evidence or receipt reference; estimates are never promoted to collected cash.",
        },
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
