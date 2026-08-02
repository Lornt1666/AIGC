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
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, Mapping)]
        return [value]
    return []


def _number(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _taxonomy(item: Mapping[str, Any]) -> set[str]:
    raw = item.get("discovered_taxonomy") or item.get("taxonomy_tags") or []
    return {str(value).lower() for value in raw} if isinstance(raw, list) else set()


def _score(item: Mapping[str, Any], offer: Mapping[str, Any]) -> dict[str, Any]:
    taxonomy = _taxonomy(item)
    fit = {str(value).lower() for value in offer.get("fit_taxonomy", [])}
    fit_score = min(100.0, 35.0 + 15.0 * len(taxonomy & fit))
    assessment = _number(item.get("radar_score"), _number(item.get("overall_score"), 50.0))
    urgency = _number(item.get("urgency_score"), 50.0)
    payment_probability = _number(item.get("payment_probability"), 35.0)
    effort_minutes = max(30.0, _number(item.get("estimated_minutes"), 120.0))
    risk_flags = item.get("risk_flags") if isinstance(item.get("risk_flags"), list) else []
    risk_score = min(100.0, 10.0 * len(risk_flags))
    expected_price = _number(item.get("budget_cad"), 0.0)
    if expected_price <= 0:
        tiers = offer.get("tiers") if isinstance(offer.get("tiers"), list) else []
        expected_price = min((_number(t.get("price")) for t in tiers if isinstance(t, Mapping)), default=0.0)
    weighted = (
        fit_score * 0.30
        + assessment * 0.25
        + urgency * 0.15
        + payment_probability * 0.15
        + max(0.0, 100.0 - effort_minutes / 3.0) * 0.10
        + max(0.0, 100.0 - risk_score) * 0.05
    )
    expected_value_per_hour = (expected_price * payment_probability / 100.0) / (effort_minutes / 60.0)
    return {
        "fit_score": round(fit_score, 2),
        "assessment_score": round(assessment, 2),
        "urgency_score": round(urgency, 2),
        "payment_probability": round(payment_probability, 2),
        "risk_score": round(risk_score, 2),
        "estimated_operator_minutes": round(effort_minutes, 2),
        "estimated_price_cad": round(expected_price, 2),
        "rank_score": round(weighted, 2),
        "expected_value_per_operator_hour_cad": round(expected_value_per_hour, 2),
        "classification": "ESTIMATED",
    }


def _approval_packet(opportunity_id: str, proposal_id: str, revision: str) -> dict[str, Any]:
    return {
        "approval_id": f"approval_{proposal_id}",
        "action_type": "EXTERNAL_PROPOSAL_SUBMISSION",
        "opportunity_id": opportunity_id,
        "proposal_id": proposal_id,
        "exact_revision": revision,
        "status": "NOT_REQUESTED",
        "scope": "Submit this exact proposal to the identified counterparty through the identified channel.",
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
    candidates = _records(phase2) if _records(phase2) else _records(phase3)
    source_used = "PHASE_2" if _records(phase2) else "PHASE_3_FALLBACK"

    ranked: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    evidence_chains: list[dict[str, Any]] = []
    for item in candidates:
        opportunity_id = str(item.get("opportunity_id") or item.get("id") or item.get("dossier_id") or "unknown")
        score = _score(item, offer)
        ranked.append({
            "opportunity_id": opportunity_id,
            "title": str(item.get("title") or "Untitled opportunity"),
            "counterparty": str(item.get("employer") or item.get("client") or "Unknown"),
            "source_platform": item.get("source_platform"),
            "source_url": item.get("source_url"),
            "offer_id": offer.get("offer_id"),
            "score": score,
        })
    ranked.sort(key=lambda row: (row["score"]["rank_score"], row["score"]["expected_value_per_operator_hour_cad"]), reverse=True)
    ranked = ranked[: max(1, min(int(top_n), 25))]

    for index, row in enumerate(ranked, start=1):
        revision_seed = json.dumps(row, sort_keys=True, separators=(",", ":"))
        revision = sha256(revision_seed.encode("utf-8")).hexdigest()
        proposal_id = f"proposal_internal_{index:02d}_{row['opportunity_id']}"
        proposal = {
            "proposal_id": proposal_id,
            "status": "INTERNAL_DRAFT_ONLY",
            "opportunity_id": row["opportunity_id"],
            "offer_id": offer.get("offer_id"),
            "counterparty": row["counterparty"],
            "title": f"{offer.get('name')} for {row['title']}",
            "scope": offer.get("deliverables", []),
            "exclusions": offer.get("exclusions", []),
            "acceptance_criteria": offer.get("acceptance_criteria", []),
            "price_cad": row["score"]["estimated_price_cad"],
            "delivery_business_days": (offer.get("tiers") or [{}])[0].get("delivery_business_days"),
            "exact_revision": revision,
            "external_action_authorized": False,
            "external_action_performed": False,
        }
        proposals.append(proposal)
        approvals.append(_approval_packet(row["opportunity_id"], proposal_id, revision))
        evidence_chains.append({
            "chain_id": f"revenue_chain_{row['opportunity_id']}",
            "opportunity_id": row["opportunity_id"],
            "links": [
                {"stage": "OPPORTUNITY", "reference": row["opportunity_id"], "state": "AVAILABLE"},
                {"stage": "ASSESSMENT", "reference": row["opportunity_id"], "state": "AVAILABLE" if source_used == "PHASE_3_FALLBACK" else "UNKNOWN"},
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
            "external_outreach",
            "proposal_submission",
            "contract_acceptance",
            "invoice_issuance",
            "payment_request",
            "payment_collection",
            "connector_write_actions",
        ],
        "external_action_authorized": False,
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }
