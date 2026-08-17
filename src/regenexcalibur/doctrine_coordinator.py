from __future__ import annotations

from src.core.epistemic.canonicalization import canonical_sha256
from src.regenexcalibur.agent_hub import modality_plan
from src.regenexcalibur.doctrine_models import CoordinatorRequest


WORKFLOW_ARTICULATIONS = {
    "APPLY_JOBS": "compose and validate a truthful application packet for an exact opportunity",
    "ARTICULATE_PRACTICES": "generate an employer-facing best-practice task articulation and deliverable specification",
    "SUBMIT_WORK": "assemble a provenance-bound work delivery packet for operator review",
    "INVOICE_HOURS": "prepare an evidence-backed invoice and hour ledger packet without signing or sending",
}

CONSEQUENTIAL_WORKFLOWS = {"APPLY_JOBS", "SUBMIT_WORK", "INVOICE_HOURS"}


def plan_regenexcalibur_workflow(request: CoordinatorRequest) -> dict[str, object]:
    """Compose one deterministic affix-tagged plan; never execute an external action."""

    consequential = request.workflow in CONSEQUENTIAL_WORKFLOWS
    stages = [
        {
            "stage": "PRE_CONSENT",
            "affix": "pre:consent",
            "status": "SIMULATED",
            "artifact": "reference-only consent and credential precondition assessment",
        },
        {
            "stage": "AGENT_IN_ORCHESTRATE",
            "affix": "agent·in·orchestrate",
            "status": "SIMULATED",
            "artifact": WORKFLOW_ARTICULATIONS[request.workflow],
        },
        {
            "stage": "VERIFY_POST",
            "affix": "verify:post",
            "status": "SIMULATED",
            "artifact": "truthfulness, provenance, format, destination, consent, and duplicate-risk checks",
        },
        {
            "stage": "CIRC_EXECUTE",
            "affix": "circ(execute)",
            "status": "BLOCKED_PERMISSION" if consequential else "NOT_REQUESTED",
            "artifact": (
                "external execution requires certified connector and request-bound one-use permit"
                if consequential
                else "local articulation completes without external execution"
            ),
        },
    ]

    required_bindings = (
        [
            "EXACT_ACCOUNT",
            "EXACT_TARGET",
            "CANONICAL_PAYLOAD_DIGEST",
            "EXPLICIT_CONSENT_ARTIFACT",
            "SECRET_BROKER_CREDENTIAL_REFERENCE",
            "CERTIFIED_CONNECTOR",
            "COST_CEILING",
            "EXPIRY",
            "EXACT_REVISION",
            "ONE_USE_EXECUTION_PERMIT",
            "RECONCILIATION_PLAN",
        ]
        if consequential
        else []
    )
    missing_bindings: list[str] = []
    if consequential and request.target_ref is None:
        missing_bindings.append("EXACT_TARGET")
    if consequential and request.consent_artifact_ref is None:
        missing_bindings.append("EXPLICIT_CONSENT_ARTIFACT")
    if consequential and request.credential_ref is None:
        missing_bindings.append("SECRET_BROKER_CREDENTIAL_REFERENCE")

    body: dict[str, object] = {
        "schema_version": "regenexcalibur.coordinator-plan.v1",
        "project": "RegenExcalibur AIGC Coordinator",
        "handle": "RegenEx::AIGC",
        "request_id": request.request_id,
        "workflow": request.workflow,
        "objective": request.objective,
        "folded_root": {
            "notation": f"<{request.workflow.lower()}>^fold",
            "behaviors": ["compose", "validate", "prepare", "approval_gate"],
        },
        "modality_plan": modality_plan(request.requested_modalities),
        "stages": stages,
        "approval_packet": {
            "required": consequential,
            "required_bindings": required_bindings,
            "missing_bindings": missing_bindings,
            "caller_supplied_authority_accepted": False,
        },
        "first_blocker": "CERTIFIED_CONNECTOR_REQUIRED" if consequential else None,
        "terminal_status": "BLOCKED" if consequential else "PASS",
        "zero_egress": True,
        "provider_calls_performed": 0,
        "external_actions_performed": 0,
        "authority_granted": False,
        "impersonation_performed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body
