"""Governed, read-only revenue mission activation for Ω Mission OS Increment 5."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

ASSESSMENTS_PATH = "data/phase3_processed/aigc_phase3_assessment_dossiers.json"
OPPORTUNITIES_PATH = "data/phase2_processed/aigc_phase2_opportunity_queue.json"
OFFER_PATH = "config/mission_os_offer_catalog.json"


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes repository root: {relative}")
    return path


def _read_json(root: Path, relative: str) -> tuple[str, Any]:
    path = _inside(root, relative)
    if not path.is_file():
        return "MISSING", None
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return "EMPTY", None
        return "AVAILABLE", json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "INVALID", None


def _records(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        for key in ("records", "items", "opportunities", "dossiers"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, Mapping)]
        return [value]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _taxonomy(item: Mapping[str, Any]) -> set[str]:
    raw = item.get("discovered_taxonomy") or item.get("taxonomy_tags") or []
    return {str(value).lower() for value in raw} if isinstance(raw, list) else set()


def _score(item: Mapping[str, Any], offer: Mapping[str, Any]) -> dict[str, Any]:
    taxonomy = _taxonomy(item)
    fit = {str(value).lower() for value in offer.get("fit_taxonomy", [])}
    fit_score = min(100.0, 35.0 + 15.0 * len(taxonomy & fit))
    assessment = _number(item.get("radar_score"))
    if assessment is None:
        assessment = _number(item.get("overall_score"))
    assessment = 50.0 if assessment is None else max(0.0, min(100.0, assessment))
    urgency_raw = _number(item.get("urgency_score"))
    urgency = 50.0 if urgency_raw is None else max(0.0, min(100.0, urgency_raw))
    effort_raw = _number(item.get("estimated_minutes"))
    effort_minutes = max(30.0, effort_raw if effort_raw is not None else 120.0)
    risk_flags = item.get("risk_flags") if isinstance(item.get("risk_flags"), list) else []
    risk_score = min(100.0, 10.0 * len(risk_flags))

    budget = _number(item.get("budget_cad"))
    payment_probability = _number(item.get("payment_probability"))
    payment_probability = (
        max(0.0, min(100.0, payment_probability))
        if payment_probability is not None
        else None
    )
    expected_value_per_hour = None
    if budget is not None and budget >= 0 and payment_probability is not None:
        expected_value_per_hour = (budget * payment_probability / 100.0) / (effort_minutes / 60.0)

    weighted = (
        fit_score * 0.35
        + assessment * 0.30
        + urgency * 0.15
        + max(0.0, 100.0 - effort_minutes / 3.0) * 0.15
        + max(0.0, 100.0 - risk_score) * 0.05
    )
    return {
        "fit_score": round(fit_score, 2),
        "assessment_score": round(assessment, 2),
        "urgency_score": round(urgency, 2),
        "urgency_classification": "SOURCE_VALUE" if urgency_raw is not None else "NEUTRAL_DEFAULT",
        "payment_probability": round(payment_probability, 2) if payment_probability is not None else None,
        "payment_probability_classification": "SOURCE_VALUE" if payment_probability is not None else "UNKNOWN",
        "risk_score": round(risk_score, 2),
        "estimated_operator_minutes": round(effort_minutes, 2),
        "operator_minutes_classification": "SOURCE_VALUE" if effort_raw is not None else "PLANNING_DEFAULT",
        "opportunity_budget_cad": round(budget, 2) if budget is not None else None,
        "budget_classification": "SOURCE_VALUE" if budget is not None else "UNKNOWN",
        "rank_score": round(weighted, 2),
        "expected_value_per_operator_hour_cad": (
            round(expected_value_per_hour, 2) if expected_value_per_hour is not None else None
        ),
        "classification": "DECISION_SUPPORT_ONLY",
    }


def _digest(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _approval_packet(proposal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "approval_id": f"approval_{proposal['proposal_id']}",
        "action_type": "EXTERNAL_PROPOSAL_SUBMISSION",
        "opportunity_id": proposal["opportunity_id"],
        "proposal_id": proposal["proposal_id"],
        "counterparty": proposal["counterparty"],
        "submission_channel": proposal["submission_channel"],
        "exact_revision": proposal["exact_revision"],
        "status": "NOT_REQUESTED",
        "scope": "Submit only this exact proposal revision to this exact counterparty through this exact channel.",
        "expires_at": None,
        "external_action_authorized": False,
        "external_action_performed": False,
    }


def build_activation_projection(repository_root: Path | str, *, top_n: int = 10) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    offer_status, catalog = _read_json(root, OFFER_PATH)
    phase2_status, phase2 = _read_json(root, OPPORTUNITIES_PATH)
    phase3_status, phase3 = _read_json(root, ASSESSMENTS_PATH)
    offers = _records((catalog or {}).get("offers") if isinstance(catalog, Mapping) else catalog)
    if not offers:
        raise ValueError("no governed offer is available")
    offer = offers[0]
    phase2_records = _records(phase2)
    phase3_records = _records(phase3)
    candidates = phase2_records if phase2_records else phase3_records
    source_used = "PHASE_2" if phase2_records else "PHASE_3_FALLBACK"

    ranked: list[dict[str, Any]] = []
    for item in candidates:
        opportunity_id = str(item.get("opportunity_id") or item.get("id") or item.get("dossier_id") or "unknown")
        ranked.append({
            "opportunity_id": opportunity_id,
            "assessment_reference": item.get("dossier_id"),
            "title": str(item.get("title") or "Untitled opportunity"),
            "counterparty": str(item.get("employer") or item.get("client") or "Unknown"),
            "source_platform": item.get("source_platform"),
            "source_url": item.get("source_url"),
            "offer_id": offer.get("offer_id"),
            "score": _score(item, offer),
        })
    ranked.sort(key=lambda row: row["score"]["rank_score"], reverse=True)
    ranked = ranked[: max(1, min(int(top_n), 25))]

    proposals: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    evidence_chains: list[dict[str, Any]] = []
    tiers = offer.get("tiers") if isinstance(offer.get("tiers"), list) else []
    default_tier = tiers[0] if tiers and isinstance(tiers[0], Mapping) else {}
    for index, row in enumerate(ranked, start=1):
        proposal_id = f"proposal_internal_{index:02d}_{row['opportunity_id']}"
        proposal_body = {
            "proposal_id": proposal_id,
            "status": "INTERNAL_DRAFT_ONLY",
            "opportunity_id": row["opportunity_id"],
            "assessment_reference": row.get("assessment_reference"),
            "offer_id": offer.get("offer_id"),
            "tier_id": default_tier.get("tier_id"),
            "counterparty": row["counterparty"],
            "submission_channel": row.get("source_url"),
            "title": f"{offer.get('name')} for {row['title']}",
            "scope": offer.get("deliverables", []),
            "exclusions": offer.get("exclusions", []),
            "acceptance_criteria": offer.get("acceptance_criteria", []),
            "proposed_list_price_cad": _number(default_tier.get("price")),
            "price_classification": "INTERNAL_OFFER_LIST_PRICE_NOT_COUNTERPARTY_BUDGET",
            "delivery_business_days": default_tier.get("delivery_business_days"),
            "external_action_authorized": False,
            "external_action_performed": False,
        }
        proposal = dict(proposal_body)
        proposal["exact_revision"] = _digest(proposal_body)
        proposals.append(proposal)
        approvals.append(_approval_packet(proposal))
        evidence_chains.append({
            "chain_id": f"revenue_chain_{row['opportunity_id']}",
            "opportunity_id": row["opportunity_id"],
            "links": [
                {"stage": "OPPORTUNITY", "reference": row["opportunity_id"], "state": "AVAILABLE"},
                {"stage": "ASSESSMENT", "reference": row.get("assessment_reference"), "state": "AVAILABLE" if row.get("assessment_reference") else "UNKNOWN"},
                {"stage": "PROPOSAL", "reference": proposal_id, "state": "INTERNAL_DRAFT"},
                {"stage": "AUTHORIZATION", "reference": f"approval_{proposal_id}", "state": "NOT_REQUESTED"},
                {"stage": "EXECUTION_RECEIPT", "reference": None, "state": "BLOCKED"},
                {"stage": "CONTRACT_EVIDENCE", "reference": None, "state": "BLOCKED"},
                {"stage": "INVOICE", "reference": None, "state": "BLOCKED"},
                {"stage": "COLLECTION_RECEIPT", "reference": None, "state": "BLOCKED"},
            ],
            "verified_collected_cad": 0,
        })

    remaining_minutes = 120
    brief_tasks: list[dict[str, Any]] = []
    for row in ranked:
        minutes = min(30, remaining_minutes)
        if minutes <= 0:
            break
        brief_tasks.append({
            "task": f"Review opportunity and internal proposal: {row['title']}",
            "opportunity_id": row["opportunity_id"],
            "minutes": minutes,
            "external_action": False,
            "operator_decision_required": True,
        })
        remaining_minutes -= minutes

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "READ_ONLY_INTERNAL_PREPARATION",
        "source_status": {"offer_catalog": offer_status, "phase2": phase2_status, "phase3": phase3_status, "ranking_source": source_used},
        "offer": offer,
        "ranked_opportunities": ranked,
        "internal_proposal_packets": proposals,
        "exact_action_approval_queue": approvals,
        "daily_operator_brief": {
            "operator_minutes_ceiling": 120,
            "scheduled_minutes": 120 - remaining_minutes,
            "tasks": brief_tasks,
            "external_actions_included": False,
        },
        "revenue_evidence_chains": evidence_chains,
        "disabled_capabilities": [
            "external_outreach", "proposal_submission", "contract_acceptance",
            "invoice_issuance", "payment_request", "payment_collection",
            "connector_write_actions", "quest_transitions", "canonical_state_mutation",
        ],
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
