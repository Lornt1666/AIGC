from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.core.nexus.specialist_registry import select_specialists
from src.domain.nexus.contracts import WorkOrder
from src.domain.nexus.odse import OperationalStrategyArtifact


def build_nexus_dashboard_snapshot(
    *,
    work_order: WorkOrder | None = None,
    verifier_findings: tuple[dict[str, Any], ...] = (),
    governance_state: str = "LOCKED",
    strategy: OperationalStrategyArtifact | None = None,
    memory_records: tuple[dict[str, Any], ...] = (),
    memory_candidates: tuple[dict[str, Any], ...] = (),
    evidence_records: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Provider-free dashboard projection for Nexus V1.

    This module intentionally returns presentation data only. It performs no network,
    provider, credential, repository, deployment, or model action.
    """
    specialists = select_specialists(work_order) if work_order is not None else ()
    synapsis = None
    if strategy is not None:
        synapsis = {
            "strategy_id": strategy.strategy_id,
            "strategic_blueprint": strategy.strategic_blueprint,
            "operational_matrix": list(strategy.operational_matrix),
            "synaptic_advantages": list(strategy.synaptic_advantages),
            "academic_frontier": strategy.academic_frontier.model_dump(mode="json"),
            "disciplinary_standards": strategy.disciplinary_standards.model_dump(mode="json"),
            "occupational_praxis": strategy.occupational_praxis.model_dump(mode="json"),
            "next_gen_multipliers": strategy.next_gen_multipliers.model_dump(mode="json"),
            "assumptions": list(strategy.assumptions),
            "uncertainties": list(strategy.uncertainties),
            "evidence_refs": list(strategy.evidence_refs),
        }

    return {
        "product": "AIGC NEXUS V1",
        "system": {
            "governance": "ACTIVE",
            "toolbroker": "LOCKED",
            "verifier": "ACTIVE",
            "external_execution": "DISABLED",
            "production_activation": "DISABLED",
            "memory_adapter": "AVAILABLE_NOT_AUTO_CONNECTED",
            "odse": "ACTIVE_PROVIDER_FREE",
        },
        "work_order": work_order.model_dump(mode="json") if work_order else None,
        "specialists": [asdict(item) for item in specialists],
        "run_graph": [
            "WORK_ORDER",
            "CONTEXT",
            "ODSE",
            "ARCHITECT",
            "SPECIALISTS",
            "CRITIC",
            "SYNTHESIZER",
            "VERIFIER",
            "GOVERNANCE",
            "MEMORY_ADMISSION",
        ],
        "synapsis": synapsis,
        "memory": {
            "records": list(memory_records),
            "candidates": list(memory_candidates),
            "grants_authority": False,
        },
        "evidence": {
            "records": list(evidence_records),
            "grants_authority": False,
        },
        "verifier_findings": list(verifier_findings),
        "governance_state": governance_state,
        "approval_actions": ["INSPECT", "APPROVE", "DENY", "REVISE"],
        "artifact_canvas": {
            "surfaces": ["STATE", "CHANGESET", "DIFF", "SYNAPSIS", "MEMORY", "EVIDENCE", "RECEIPTS"],
            "write_through_enabled": False,
        },
    }
