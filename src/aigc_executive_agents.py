"""Governed C-suite agent contracts for AIGC.

This module provides executable, deterministic role definitions and approval
policy evaluation. It is not a model runtime and does not execute external
actions. Any decision here is advisory unless verified by the execution
controller against authenticated policy and evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "1.0"
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

@dataclass(frozen=True)
class Role:
    agent_id: str
    title: str
    mandate: str
    outputs: tuple[str, ...]
    can_block: bool = False
    human_gate: bool = False

ROLES = (
    Role("CEO", "Chief Executive / Action Approval Agent", "Prioritize proposals and issue only narrowly scoped approvals permitted by policy.", ("decision", "rationale", "scoped_approval"), human_gate=True),
    Role("COS", "Chief of Staff", "Validate task contracts, order dependencies, track handoffs and report blockers.", ("dependency_dag", "work_queue", "handoff_report")),
    Role("CIO-CAP", "Chief Investment and Capital Allocation", "Model capital-allocation scenarios and risk-adjusted returns.", ("scenario_model", "allocation_memo"), human_gate=True),
    Role("CORPDEV", "Corporate Development and M&A Director", "Screen targets and produce valuation and diligence analyses.", ("target_scorecard", "valuation_model", "diligence_gaps"), human_gate=True),
    Role("SYNERGY", "Chief Synergy and Integration Officer", "Map portfolio overlaps and propose integration roadmaps.", ("overlap_map", "integration_roadmap"), human_gate=True),
    Role("CRO", "Chief Risk Officer", "Evaluate enterprise and systemic risk, run stress tests, and block unacceptable risk.", ("risk_register", "stress_test"), can_block=True),
    Role("CPO", "Chief Procurement Officer", "Analyze sourcing, supplier concentration, RFPs, and spend opportunities.", ("supplier_scorecard", "rfp_draft"), human_gate=True),
    Role("CLO", "Chief Legal Officer and Corporate Secretary", "Identify legal and governance issues for qualified counsel review.", ("obligation_matrix", "draft_governance_docs"), can_block=True, human_gate=True),
    Role("OPCO", "Operating Partner and Subsidiary Portfolio Chair", "Compare operating KPIs and propose accountable interventions.", ("operating_review", "variance_report"), human_gate=True),
    Role("CTO", "Group Technology Officer and Digital Architect", "Define reference architecture, integration standards, and technical decisions.", ("architecture", "adr", "platform_controls")),
    Role("CISO", "Chief Information Security Officer / Protector", "Evaluate cyber controls and block unsafe or unauthorized actions.", ("threat_model", "security_findings"), can_block=True),
    Role("TRUST", "Trustworthiness and Evidence Assessor", "Verify provenance, source quality, freshness, subject binding, and contradictions.", ("provenance_report", "evidence_gaps"), can_block=True),
    Role("RED", "Red Team", "Find security, policy, abuse, and failure cases within authorized scope.", ("adversarial_findings", "test_cases"), can_block=True),
    Role("BLUE", "Blue Team", "Assess detection, prevention, and containment coverage.", ("defensive_gap_report", "detection_plan")),
    Role("GREEN", "Green Team / Reliability and Recovery", "Test resilience, repair, rollback, and recovery behavior.", ("recovery_plan", "resilience_results")),
    Role("AER", "Architecture and Engineering Review", "Review architecture, dependencies, and non-functional requirements independently.", ("review_report",), can_block=True),
    Role("DOC", "MVP++ Documentation Architect", "Generate evidence-aware draft documentation packs and content digests.", ("document_pack", "manifest")),
    Role("QA", "Verification and Quality Engineering", "Run real checks and bind results to exact source and tested tree.", ("test_report", "reproducibility_record"), can_block=True),
    Role("DATA", "Data Governance and Analytics", "Assess data lineage, quality, minimization, privacy, and retention.", ("data_lineage", "quality_report"), can_block=True),
    Role("FIN", "Finance and Cost Controller", "Forecast and enforce explicit run budgets and cost stop conditions.", ("cost_forecast", "budget_decision"), can_block=True),
    Role("AUDIT", "Internal Audit and Control Assurance", "Independently sample evidence and assess control design and operation.", ("audit_findings",), can_block=True),
    Role("COMMS", "Communications and Stakeholder Reporting", "Produce audience-specific, fact-bound status reports.", ("status_report",), human_gate=True),
    Role("PEOPLE", "People and Succession Planning", "Map organizational capability and succession risks with privacy safeguards.", ("capability_map", "succession_scenarios"), human_gate=True),
    Role("SECRETARY", "Board Governance and Corporate Secretariat", "Prepare decision packs and validate quorum and approval records.", ("board_pack", "decision_register"), human_gate=True),
    Role("DISPATCH", "Execution Controller", "Revalidate scoped authorization and evidence immediately before external side effects.", ("action_receipt", "reconciliation_record"), can_block=True),
    Role("RELEASE", "Canonical Release Assurance", "Issue the sole canonical software release PASS/BLOCK decision from verified evidence.", ("release_decision", "decision_receipt"), can_block=True, human_gate=True),
)
ROLE_BY_ID = {role.agent_id: role for role in ROLES}

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def roster() -> list[dict[str, Any]]:
    return [{"agent_id": r.agent_id, "title": r.title, "mandate": r.mandate,
             "outputs": list(r.outputs), "can_block": r.can_block,
             "human_gate": r.human_gate, "status": "SPECIFIED_NOT_OPERATIONAL"}
            for r in ROLES]

def evaluate_ceo_approval(proposal: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Fail-closed policy evaluator. Never signs, authenticates identity, or executes actions."""
    reasons: list[str] = []
    required = {
        "schema_version", "decision_id", "task_id", "task_digest_sha256",
        "source_revision", "action_class", "allowed_action_ids", "denied_action_ids",
        "max_usd", "expires_at_utc", "required_check_ids", "evidence_digests",
        "risk_decision", "human_approval_ref", "decision", "rationale",
        "signer_identity", "signature_ref",
    }
    if not isinstance(proposal, dict):
        return {"decision": "BLOCK", "reasons": ["proposal must be an object"]}
    unknown = sorted(set(proposal) - required)
    missing = sorted(required - set(proposal))
    if unknown:
        reasons.append("unknown fields: " + ", ".join(unknown))
    if missing:
        reasons.append("missing fields: " + ", ".join(missing))
    if reasons:
        return {"decision": "BLOCK", "reasons": reasons}
    if proposal["schema_version"] != SCHEMA_VERSION:
        reasons.append("unsupported schema_version")
    if not isinstance(proposal["task_digest_sha256"], str) or not DIGEST_RE.fullmatch(proposal["task_digest_sha256"]):
        reasons.append("invalid task digest")
    if not isinstance(proposal["source_revision"], str) or not FULL_SHA_RE.fullmatch(proposal["source_revision"]):
        reasons.append("source_revision must be a full 40-character commit SHA")
    if proposal["action_class"] not in {"read", "write", "external_communication", "spend", "deploy", "release", "destructive"}:
        reasons.append("invalid action_class")
    allowed = proposal["allowed_action_ids"]
    denied = proposal["denied_action_ids"]
    if not isinstance(allowed, list) or not allowed or any(not isinstance(x, str) or not x.strip() or "*" in x for x in allowed):
        reasons.append("allowed_action_ids must be non-empty, explicit, and contain no wildcards")
    if not isinstance(denied, list) or any(not isinstance(x, str) or not x.strip() or "*" in x for x in denied):
        reasons.append("denied_action_ids must be explicit identifiers")
    if isinstance(allowed, list) and isinstance(denied, list) and set(allowed) & set(denied):
        reasons.append("an action cannot be both allowed and denied")
    if isinstance(proposal["max_usd"], bool) or not isinstance(proposal["max_usd"], (int, float)) or proposal["max_usd"] < 0:
        reasons.append("max_usd must be a non-negative number")
    for field in ("required_check_ids", "evidence_digests"):
        if not isinstance(proposal[field], list) or any(not isinstance(x, str) or not x for x in proposal[field]):
            reasons.append(f"{field} must be a list of non-empty strings")
    if isinstance(proposal["evidence_digests"], list) and any(not DIGEST_RE.fullmatch(x) for x in proposal["evidence_digests"]):
        reasons.append("evidence_digests must contain SHA-256 hex digests")
    if proposal["risk_decision"] != "PASS":
        reasons.append("risk decision is not PASS")
    if proposal["decision"] != "APPROVE_SCOPED":
        reasons.append("proposal is not a scoped approval")
    if not isinstance(proposal["rationale"], str) or not proposal["rationale"].strip():
        reasons.append("rationale is required")
    if not isinstance(proposal["signer_identity"], str) or not proposal["signer_identity"].strip():
        reasons.append("authenticated signer identity is required")
    # Signature and human approval are only references here; actual authentication must be
    # performed independently by the execution controller against trusted identity systems.
    if not isinstance(proposal["signature_ref"], str) or not proposal["signature_ref"].strip():
        reasons.append("signature reference missing")
    action_class = proposal["action_class"]
    if action_class in {"spend", "deploy", "release", "destructive", "external_communication"} and not proposal["human_approval_ref"]:
        reasons.append(f"human approval required for action class {action_class}")
    try:
        expiry = datetime.fromisoformat(proposal["expires_at_utc"].replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            raise ValueError("timezone required")
        current = now or datetime.now(timezone.utc)
        if expiry.astimezone(timezone.utc) <= current.astimezone(timezone.utc):
            reasons.append("approval expired")
    except (ValueError, TypeError, AttributeError):
        reasons.append("expires_at_utc must be a timezone-aware RFC3339 timestamp")
    return {"decision": "BLOCK" if reasons else "APPROVE_SCOPED",
            "reasons": reasons,
            "authority": "advisory_only",
            "requires_execution_controller_revalidation": True,
            "release_authority": "canonical_release_assurance_only"}
