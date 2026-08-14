from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.core.nexus.connector_registry import build_connector_status_snapshot
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
    connector_status: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    """Read-only dashboard projection for admitted Nexus V1 capabilities.

    The projection exposes implementation availability without claiming runtime wiring,
    authority, provider execution, credential access, deployment, or production state.
    """
    specialists = select_specialists(work_order) if work_order is not None else ()
    connectors = (
        list(connector_status)
        if connector_status is not None
        else build_connector_status_snapshot()
    )
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
            "toolbroker": "GOVERNED_DEFAULT_DENY",
            "verifier": "ACTIVE_READ_ONLY",
            "external_execution": "GOVERNED_AVAILABLE_DEFAULT_DENY",
            "production_activation": "DISABLED",
            "repository_gateway": "READ_ONLY_AVAILABLE_NOT_AUTO_CONNECTED",
            "provider_runtime": "LIVE_FOUNDATION_AVAILABLE_NOT_AUTO_CONNECTED",
            "durable_runtime_controls": "POSTGRES_AVAILABLE_NOT_AUTO_CONNECTED",
            "memory_adapter": "SQLITE_AVAILABLE_NOT_AUTO_CONNECTED",
            "evidence_adapter": "SQLITE_AVAILABLE_NOT_AUTO_CONNECTED",
            "odse": "ACTIVE_PROVIDER_FREE",
            "employment_connectors": "VISIBLE_DEFAULT_DENY",
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
        "available_runtime_surfaces": [
            "REPOSITORY_GATEWAY_READ_ONLY",
            "PROVIDER_CONTRIBUTION_RESOLVER",
            "NEXUS_PROVIDER_RUNTIME_DEFAULT_DENY",
            "GOVERNED_LIVE_PROVIDER_RUNTIME",
            "POSTGRES_RUNTIME_CONTROLS",
            "SQLITE_MEMORY",
            "SQLITE_EVIDENCE",
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
        "connectors": {
            "records": connectors,
            "enabled_live_mutation_capabilities": sum(
                item["live_mutation_capability_count"] for item in connectors
            ),
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
