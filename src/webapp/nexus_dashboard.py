from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.core.nexus.specialist_registry import select_specialists
from src.domain.nexus.contracts import WorkOrder


def build_nexus_dashboard_snapshot(
    *,
    work_order: WorkOrder | None = None,
    verifier_findings: tuple[dict[str, Any], ...] = (),
    governance_state: str = "LOCKED",
) -> dict[str, Any]:
    """Provider-free dashboard projection for Nexus V1.

    This module intentionally returns presentation data only. It performs no network,
    provider, credential, repository, deployment, or model action.
    """
    specialists = select_specialists(work_order) if work_order is not None else ()
    return {
        "product": "AIGC NEXUS V1",
        "system": {
            "governance": "ACTIVE",
            "toolbroker": "LOCKED",
            "verifier": "ACTIVE",
            "external_execution": "DISABLED",
            "production_activation": "DISABLED",
        },
        "work_order": work_order.model_dump(mode="json") if work_order else None,
        "specialists": [asdict(item) for item in specialists],
        "run_graph": [
            "WORK_ORDER",
            "ARCHITECT",
            "SPECIALISTS",
            "CRITIC",
            "SYNTHESIZER",
            "VERIFIER",
            "GOVERNANCE",
        ],
        "verifier_findings": list(verifier_findings),
        "governance_state": governance_state,
        "approval_actions": ["INSPECT", "APPROVE", "DENY", "REVISE"],
        "artifact_canvas": {
            "surfaces": ["STATE", "CHANGESET", "DIFF", "EVIDENCE", "RECEIPTS"],
            "write_through_enabled": False,
        },
    }
