from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.core.production_readiness_ledger import build_report, load_ledger


PROJECTED_COMPLETION_TARGETS = {
    "security_privacy_wiring",
    "transactional_persistence",
    "production_identity_access",
    "approved_external_connectors",
    "production_deployment",
    "work_acquisition",
}


def projected_completion_score(
    ledger: Mapping[str, Any],
    report: Mapping[str, Any],
) -> float:
    """Project readiness after the named completion targets reach complete.

    The projection is scenario analysis only. It never mutates the ledger,
    closes a blocker, grants authority, or changes canonical readiness.
    """

    current_status = {
        str(result["capability_id"]): str(result["effective_status"])
        for result in report["capability_results"]
    }
    multipliers = {
        str(key): float(value)
        for key, value in ledger["status_multipliers"].items()
    }

    total_weight = 0.0
    earned_weight = 0.0
    for capability in ledger["capabilities"]:
        capability_id = str(capability["capability_id"])
        weight = float(capability["weight"])
        total_weight += weight
        status = (
            "complete"
            if capability_id in PROJECTED_COMPLETION_TARGETS
            else current_status[capability_id]
        )
        earned_weight += weight * multipliers[status]

    return round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0


def build_readiness_payload(project_root: Path) -> dict[str, Any]:
    """Return canonical readiness plus compatibility and scenario views.

    Existing top-level capability objects remain stable for current clients.
    The nested ``current`` object is the canonical ledger-derived view, while
    ``projection`` is explicitly non-authoritative scenario analysis.
    """

    root = project_root.resolve()
    ledger = load_ledger(root / "config" / "production_readiness_ledger.json")
    report = build_report(root, ledger)
    projected_score = projected_completion_score(ledger, report)
    threshold = float(report["production_readiness_threshold"])

    current = {
        "structural_score": report["overall_score"],
        "threshold": threshold,
        "production_ready": report["production_ready"],
        "blocking_gaps": report["blocking_gaps"],
        "source_revision": report["source_revision"],
        "evaluated_at": report["created_at"],
        "evidence_strength": report["evidence_strength"],
    }

    delivery_judgment_gate = {
        "state": "implemented_internal",
        "review_packet_generation": True,
        "accountable_human_judgment": True,
        "accepted_for_delivery_supported": True,
        "delivery_performed": False,
        "blocking": False,
        "external_action_performed": False,
    }

    return {
        # Compatibility aliases retained for existing API consumers.
        "structural_score": current["structural_score"],
        "production_ready": current["production_ready"],
        "blocking_gaps": current["blocking_gaps"],
        "evidence_strength": current["evidence_strength"],
        "production_identity_access": {
            "state": "partial",
            "blocking": True,
        },
        "authorization_receipt_persistence": {
            "state": "implemented_internal",
            "blocking": False,
        },
        "opportunity_scout": {
            "state": "implemented_internal_read_only",
            "arbitrary_urls_allowed": False,
            "credentials_used": False,
            "blocking": False,
        },
        "quest_candidate_intake": {
            "state": "implemented_internal",
            "blocking": False,
        },
        "quest_creation_from_candidate": {
            "state": "implemented_internal",
            "initial_state": "PROPOSED",
            "work_accepted": False,
            "blocking": False,
        },
        "work_acceptance_transition": {
            "state": "implemented_internal_local_simulation",
            "path": [
                "PROPOSED",
                "APPROVAL_REQUIRED",
                "WORK_ACCEPTED",
            ],
            "authorization_receipt_required": True,
            "production_identity_required_for_production_use": True,
            "external_contract_accepted": False,
            "blocking": False,
        },
        "delivery_judgment_gate": delivery_judgment_gate,
        "evidence_scope": "local_behavioral_simulation",
        "exact_main_ci_observed": False,
        "current": current,
        "projection": {
            "structural_score": projected_score,
            "production_ready_if_evidence_is_accepted": (
                projected_score >= threshold
            ),
            "assumptions": [
                "all current production blockers become complete",
                "work_acquisition becomes complete",
                "all required operational evidence is accepted",
                "blocking_gaps become empty",
            ],
            "grants_authority": False,
        },
        "highest_impact_next_step": report["highest_impact_next_step"],
        "operator_review_required": True,
        "external_action_performed": False,
    }
