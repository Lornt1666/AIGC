from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import ContractValidationError, validate_artifact, validate_file


WORK_ORDER_SCHEMA = "work_order_packet"
GOVERNANCE_SCHEMA = "governance_decision"
APPROVAL_SCHEMA = "approval_packet"
ARTIFACT_MANIFEST_SCHEMA = "artifact_manifest"
RUN_RECEIPT_SCHEMA = "aigc_run_receipt"
EXTERNAL_PERMIT_SCHEMA = "external_action_permit"
SECRET_REFERENCE_SCHEMA = "secret_reference"
VALIDATION_RECEIPT_SCHEMA = "validation_receipt"

WORK_ORDER_CATEGORIES = {
    "internal-only",
    "documentation-only",
    "code-generation",
    "research-packet",
    "customer-facing-draft",
    "external-action-proposed",
    "blocked/high-risk",
    "requires-permit",
}

HIGH_RISK_TERMS = {
    "submit",
    "send",
    "purchase",
    "payment",
    "invoice",
    "contract",
    "apply",
    "bid",
    "post",
    "credential",
    "secret",
    "production deploy",
    "live connector",
}

BLOCKED_EXTERNAL_ACTIONS = [
    "job_application_submission",
    "bid_submission",
    "outreach_message",
    "invoice_dispatch",
    "contract_acceptance",
    "purchase_or_payment",
    "account_change",
    "social_posting",
    "website_action",
    "credential_use",
    "external_api_side_effect",
    "file_movement_outside_workspace",
    "production_deployment",
    "secret_access_or_logging",
]

SAFE_INTERNAL_OPERATIONS = [
    "schema_validation",
    "risk_classification",
    "governance_routing",
    "artifact_generation",
    "manifest_generation",
    "approval_packet_generation",
    "redaction_review_instruction",
    "operator_review_preparation",
    "audit_record_preparation",
]

AGENT_ROLES = [
    "researcher",
    "planner",
    "coder",
    "auditor",
    "compliance_checker",
    "redaction_checker",
    "acceptance_reviewer",
]


@dataclass(frozen=True)
class SecretReference:
    reference_id: str
    provider: str
    reference: str
    purpose: str
    raw_secret_present: bool = False


@dataclass(frozen=True)
class RiskFinding:
    finding_id: str
    severity: str
    category: str
    summary: str
    mitigation: str


@dataclass(frozen=True)
class WorkOrder:
    work_order_id: str
    created_at: str
    title: str
    objective: str
    domain: str
    urgency: str
    risk_class: str
    desired_output: str
    external_action_intent: str
    acceptance_criteria: List[str]
    operator_visible_summary: str
    symbolic_layers: List[str]
    requested_agents: List[str]
    secret_references: List[SecretReference]
    source: str


@dataclass(frozen=True)
class GovernanceDecision:
    decision_id: str
    work_order_id: str
    correlation_id: str
    created_at: str
    classification: str
    risk_class: str
    allowed_operations: List[str]
    blocked_operations: List[str]
    required_approvals: List[str]
    assigned_agents: List[str]
    risk_findings: List[RiskFinding]
    external_action_allowed: bool
    approval_required_before_external_action: bool
    self_approval_allowed: bool
    symbolic_layers_grant_authority: bool
    status: str


@dataclass(frozen=True)
class ExternalActionPermit:
    permit_id: str
    work_order_id: str
    correlation_id: str
    requested: bool
    status: str
    reason: str
    required_future_controls: List[str]
    live_execution_allowed: bool = False
    external_action_performed: bool = False


@dataclass(frozen=True)
class ApprovalPacket:
    approval_id: str
    work_order_id: str
    correlation_id: str
    created_at: str
    status: str
    required_phrase: str
    denial_phrase: str
    revision_phrase_template: str
    expires_at: str
    approved: bool
    denied: bool
    revision_required: bool
    self_approval_allowed: bool
    external_action_performed: bool
    visible_review_summary: str
    blocked_actions: List[str]


@dataclass(frozen=True)
class ArtifactManifest:
    manifest_id: str
    work_order_id: str
    correlation_id: str
    created_at: str
    artifact_root: str
    generated_artifacts: List[Dict[str, str]]
    schema_validated: bool
    external_action_performed: bool


@dataclass(frozen=True)
class ValidationReceipt:
    receipt_id: str
    work_order_id: str
    correlation_id: str
    created_at: str
    valid: bool
    validated_artifacts: List[Dict[str, Any]]
    failures: List[str]


@dataclass(frozen=True)
class AIGCRunReceipt:
    run_id: str
    work_order_id: str
    correlation_id: str
    created_at: str
    status: str
    artifact_root: str
    work_order_packet_path: str
    governance_decision_path: str
    approval_packet_path: str
    external_action_permit_path: str
    artifact_manifest_path: str
    validation_receipt_path: str
    external_action_performed: bool
    operator_next_action: str
    source_revision: str
    source_tree_sha: str
    work_order_sha256: str
    artifact_manifest_sha256: str
    validation_receipt_sha256: str


@dataclass(frozen=True)
class WorkOrderRunResult:
    work_order: WorkOrder
    governance_decision: GovernanceDecision
    external_action_permit: ExternalActionPermit
    approval_packet: ApprovalPacket
    artifact_manifest: ArtifactManifest
    validation_receipt: ValidationReceipt
    run_receipt: AIGCRunReceipt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_order": serialize(self.work_order),
            "governance_decision": serialize(self.governance_decision),
            "external_action_permit": serialize(self.external_action_permit),
            "approval_packet": serialize(self.approval_packet),
            "artifact_manifest": serialize(self.artifact_manifest),
            "validation_receipt": serialize(self.validation_receipt),
            "run_receipt": serialize(self.run_receipt),
        }


def run_work_order(
    project_root: Path,
    input_path: Path,
    artifact_root: Path | None = None,
) -> WorkOrderRunResult:
    project_root = project_root.resolve()
    input_path = resolve_project_path(project_root, input_path)
    if artifact_root is None:
        artifact_root = project_root / "reports" / "artifacts" / "work_orders"
    else:
        artifact_root = resolve_project_path(project_root, artifact_root)

    input_payload = load_json_dict(input_path)
    work_order_sha256 = hashlib.sha256(
        json.dumps(input_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    source_revision, source_tree_sha = git_provenance(project_root)
    validate_artifact(WORK_ORDER_SCHEMA, input_payload)
    work_order = work_order_from_payload(input_payload)
    validate_secret_references(work_order.secret_references)

    correlation_id = make_id("AIGC-CORR", work_order.work_order_id, utc_now(), str(uuid.uuid4()))
    decision = build_governance_decision(work_order, correlation_id)
    permit = build_external_action_permit(work_order, decision, correlation_id)
    approval = build_approval_packet(work_order, decision, correlation_id)

    run_root = artifact_root / safe_path_name(work_order.work_order_id) / safe_path_name(correlation_id)
    run_root.mkdir(parents=True, exist_ok=True)

    artifact_paths = {
        WORK_ORDER_SCHEMA: run_root / "work_order_packet.json",
        GOVERNANCE_SCHEMA: run_root / "governance_decision.json",
        EXTERNAL_PERMIT_SCHEMA: run_root / "external_action_permit.json",
        APPROVAL_SCHEMA: run_root / "approval_packet.json",
    }
    write_json(artifact_paths[WORK_ORDER_SCHEMA], serialize(work_order))
    write_json(artifact_paths[GOVERNANCE_SCHEMA], serialize(decision))
    write_json(artifact_paths[EXTERNAL_PERMIT_SCHEMA], serialize(permit))
    write_json(artifact_paths[APPROVAL_SCHEMA], serialize(approval))

    generated_artifacts = []
    for schema_name, path in artifact_paths.items():
        validate_file(schema_name, path)
        generated_artifacts.append({
            "schema": schema_name,
            "path": relative_to_root(project_root, path),
            "sha256": sha256_file(path),
        })

    report_path = run_root / "operator_review_report.md"
    report_path.write_text(render_operator_report(work_order, decision, permit, approval), encoding="utf-8")
    generated_artifacts.append({
        "schema": "markdown_operator_review_report",
        "path": relative_to_root(project_root, report_path),
        "sha256": sha256_file(report_path),
    })

    manifest = ArtifactManifest(
        manifest_id=make_id("AIGC-MANIFEST", work_order.work_order_id, correlation_id),
        work_order_id=work_order.work_order_id,
        correlation_id=correlation_id,
        created_at=utc_now(),
        artifact_root=relative_to_root(project_root, run_root),
        generated_artifacts=generated_artifacts,
        schema_validated=True,
        external_action_performed=False,
    )
    manifest_path = run_root / "artifact_manifest.json"
    write_json(manifest_path, serialize(manifest))
    validate_file(ARTIFACT_MANIFEST_SCHEMA, manifest_path)

    validation_receipt = validate_generated_artifacts(
        work_order.work_order_id,
        correlation_id,
        {
            WORK_ORDER_SCHEMA: artifact_paths[WORK_ORDER_SCHEMA],
            GOVERNANCE_SCHEMA: artifact_paths[GOVERNANCE_SCHEMA],
            EXTERNAL_PERMIT_SCHEMA: artifact_paths[EXTERNAL_PERMIT_SCHEMA],
            APPROVAL_SCHEMA: artifact_paths[APPROVAL_SCHEMA],
            ARTIFACT_MANIFEST_SCHEMA: manifest_path,
        },
    )
    validation_path = run_root / "validation_receipt.json"
    write_json(validation_path, serialize(validation_receipt))
    validate_file(VALIDATION_RECEIPT_SCHEMA, validation_path)

    run_receipt = AIGCRunReceipt(
        run_id=make_id("AIGC-RUN", work_order.work_order_id, correlation_id),
        work_order_id=work_order.work_order_id,
        correlation_id=correlation_id,
        created_at=utc_now(),
        status="operator_review_required" if validation_receipt.valid else "validation_failed",
        artifact_root=relative_to_root(project_root, run_root),
        work_order_packet_path=relative_to_root(project_root, artifact_paths[WORK_ORDER_SCHEMA]),
        governance_decision_path=relative_to_root(project_root, artifact_paths[GOVERNANCE_SCHEMA]),
        approval_packet_path=relative_to_root(project_root, artifact_paths[APPROVAL_SCHEMA]),
        external_action_permit_path=relative_to_root(project_root, artifact_paths[EXTERNAL_PERMIT_SCHEMA]),
        artifact_manifest_path=relative_to_root(project_root, manifest_path),
        validation_receipt_path=relative_to_root(project_root, validation_path),
        external_action_performed=False,
        operator_next_action="Review the approval packet, then Accept, Revise, Deny, or Emergency Stop. No external action is performed by this run.",
        source_revision=source_revision,
        source_tree_sha=source_tree_sha,
        work_order_sha256=work_order_sha256,
        artifact_manifest_sha256=sha256_file(manifest_path),
        validation_receipt_sha256=sha256_file(validation_path),
    )
    run_receipt_path = run_root / "aigc_run_receipt.json"
    write_json(run_receipt_path, serialize(run_receipt))
    validate_file(RUN_RECEIPT_SCHEMA, run_receipt_path)

    return WorkOrderRunResult(
        work_order=work_order,
        governance_decision=decision,
        external_action_permit=permit,
        approval_packet=approval,
        artifact_manifest=manifest,
        validation_receipt=validation_receipt,
        run_receipt=run_receipt,
    )


def run_governance_smoke(project_root: Path) -> WorkOrderRunResult:
    return run_work_order(
        project_root=project_root,
        input_path=project_root / "config" / "example_work_order.json",
        artifact_root=project_root / "reports" / "artifacts" / "governance_smoke",
    )


def run_cockpit_smoke(project_root: Path) -> Dict[str, Any]:
    result = run_governance_smoke(project_root)
    cockpit_path = project_root / "src" / "dashboard" / "operator_cockpit_app.py"
    return {
        "status": "completed",
        "cockpit_path_exists": cockpit_path.exists(),
        "external_action_performed": False,
        "run_receipt": serialize(result.run_receipt),
    }


def work_order_from_payload(payload: Dict[str, Any]) -> WorkOrder:
    secret_references = [
        SecretReference(
            reference_id=str(item.get("reference_id", "")),
            provider=str(item.get("provider", "")),
            reference=str(item.get("reference", "")),
            purpose=str(item.get("purpose", "")),
            raw_secret_present=bool(item.get("raw_secret_present", False)),
        )
        for item in payload.get("secret_references", [])
        if isinstance(item, dict)
    ]
    created_at = str(payload.get("created_at", "") or utc_now())
    return WorkOrder(
        work_order_id=str(payload.get("work_order_id") or make_id("AIGC-WO", payload.get("title", "work-order"))),
        created_at=created_at,
        title=str(payload.get("title", "Untitled AIGC work order")),
        objective=str(payload.get("objective", "")),
        domain=str(payload.get("domain", "general")),
        urgency=str(payload.get("urgency", "normal")),
        risk_class=str(payload.get("risk_class", "medium")),
        desired_output=str(payload.get("desired_output", "operator-reviewable artifact packet")),
        external_action_intent=str(payload.get("external_action_intent", "none")),
        acceptance_criteria=[str(item) for item in payload.get("acceptance_criteria", [])],
        operator_visible_summary=str(payload.get("operator_visible_summary", "")),
        symbolic_layers=[str(item) for item in payload.get("symbolic_layers", [])],
        requested_agents=[str(item) for item in payload.get("requested_agents", [])],
        secret_references=secret_references,
        source=str(payload.get("source", "operator_cli")),
    )


def build_governance_decision(work_order: WorkOrder, correlation_id: str) -> GovernanceDecision:
    classification = classify_work_order(work_order)
    findings = build_risk_findings(work_order, classification)
    required_approvals = ["operator_review_required"]
    if work_order.external_action_intent != "none" or classification in {"requires-permit", "external-action-proposed"}:
        required_approvals.extend([
            "external_action_permit_required",
            "platform_terms_review_required",
            "scope_specific_human_authority_required",
        ])
    if work_order.secret_references:
        required_approvals.append("secret_reference_review_required")

    assigned_agents = unique((work_order.requested_agents or []) + AGENT_ROLES)
    return GovernanceDecision(
        decision_id=make_id("AIGC-GOV", work_order.work_order_id, correlation_id),
        work_order_id=work_order.work_order_id,
        correlation_id=correlation_id,
        created_at=utc_now(),
        classification=classification,
        risk_class=work_order.risk_class,
        allowed_operations=SAFE_INTERNAL_OPERATIONS,
        blocked_operations=BLOCKED_EXTERNAL_ACTIONS,
        required_approvals=unique(required_approvals),
        assigned_agents=assigned_agents,
        risk_findings=findings,
        external_action_allowed=False,
        approval_required_before_external_action=True,
        self_approval_allowed=False,
        symbolic_layers_grant_authority=False,
        status="operator_review_required",
    )


def classify_work_order(work_order: WorkOrder) -> str:
    text = " ".join([
        work_order.title,
        work_order.objective,
        work_order.domain,
        work_order.desired_output,
        work_order.external_action_intent,
    ]).lower()
    if work_order.risk_class.lower() in {"high", "critical"} and any(term in text for term in HIGH_RISK_TERMS):
        return "blocked/high-risk"
    if work_order.external_action_intent != "none":
        return "requires-permit"
    if "customer" in text or "proposal" in text or "client" in text:
        return "customer-facing-draft"
    if "code" in text or "python" in text or "implementation" in text:
        return "code-generation"
    if "research" in text or "brief" in text or "source" in text:
        return "research-packet"
    if "doc" in text or "runbook" in text or "spec" in text:
        return "documentation-only"
    return "internal-only"


def build_risk_findings(work_order: WorkOrder, classification: str) -> List[RiskFinding]:
    findings = [
        RiskFinding(
            finding_id=make_id("AIGC-RISK", work_order.work_order_id, "approval"),
            severity="medium",
            category="human_authority",
            summary="Human review remains required before acceptance or downstream execution.",
            mitigation="Use exact visible approval, revise, deny, or emergency-stop controls.",
        )
    ]
    if classification in {"requires-permit", "external-action-proposed", "blocked/high-risk"}:
        findings.append(RiskFinding(
            finding_id=make_id("AIGC-RISK", work_order.work_order_id, "external"),
            severity="high",
            category="external_action",
            summary="The work order contains external-action intent or high-risk outward movement.",
            mitigation="Keep the gateway blocked until a separate permit, scope, terms review, and operator approval exist.",
        ))
    if work_order.secret_references:
        findings.append(RiskFinding(
            finding_id=make_id("AIGC-RISK", work_order.work_order_id, "secrets"),
            severity="high",
            category="secret_reference",
            summary="The work order references secret-managed material.",
            mitigation="Store references only. Do not store, print, or log raw secret values.",
        ))
    if work_order.symbolic_layers:
        findings.append(RiskFinding(
            finding_id=make_id("AIGC-RISK", work_order.work_order_id, "symbolic"),
            severity="low",
            category="execution_authority",
            summary="Symbolic layers may improve articulation but grant no authority.",
            mitigation="Bind authority only to explicit contracts, tests, and human approval gates.",
        ))
    return findings


def build_external_action_permit(
    work_order: WorkOrder,
    decision: GovernanceDecision,
    correlation_id: str,
) -> ExternalActionPermit:
    requested = work_order.external_action_intent != "none"
    status = "blocked_pending_future_review" if requested else "not_requested_blocked_by_default"
    reason = (
        "External action was requested, but this sprint implements a blocked-by-default gateway scaffold only."
        if requested
        else "No external action requested. The gateway still remains disabled by default."
    )
    return ExternalActionPermit(
        permit_id=make_id("AIGC-PERMIT", work_order.work_order_id, correlation_id),
        work_order_id=work_order.work_order_id,
        correlation_id=correlation_id,
        requested=requested,
        status=status,
        reason=reason,
        required_future_controls=[
            "external_action_schema",
            "permit_schema",
            "authority_scope",
            "revocation_path",
            "dry_run_mode",
            "audit_logging",
            "operator_confirmation",
            "platform_terms_review",
            "rate_limits",
            "rollback_or_stop_control",
            "blocked_by_default_tests",
        ],
        live_execution_allowed=False,
        external_action_performed=False,
    )


def build_approval_packet(
    work_order: WorkOrder,
    decision: GovernanceDecision,
    correlation_id: str,
) -> ApprovalPacket:
    required_phrase = f"I reviewed and accept AIGC work order {work_order.work_order_id} for internal governed preparation only."
    denial_phrase = f"I deny AIGC work order {work_order.work_order_id}."
    revision_phrase_template = f"Revise AIGC work order {work_order.work_order_id}: [operator revision instructions]"
    return ApprovalPacket(
        approval_id=make_id("AIGC-APPROVAL", work_order.work_order_id, correlation_id),
        work_order_id=work_order.work_order_id,
        correlation_id=correlation_id,
        created_at=utc_now(),
        status="pending_operator_review",
        required_phrase=required_phrase,
        denial_phrase=denial_phrase,
        revision_phrase_template=revision_phrase_template,
        expires_at="2999-12-31T23:59:59+00:00",
        approved=False,
        denied=False,
        revision_required=False,
        self_approval_allowed=False,
        external_action_performed=False,
        visible_review_summary=(
            f"{work_order.title}: {decision.classification}. "
            "Accept records internal preparation approval only and does not perform external action."
        ),
        blocked_actions=decision.blocked_operations,
    )


def validate_secret_references(secret_references: Iterable[SecretReference]) -> None:
    for reference in secret_references:
        validate_artifact(SECRET_REFERENCE_SCHEMA, serialize(reference))
        if reference.raw_secret_present:
            raise ContractValidationError(f"Secret reference {reference.reference_id} reports a raw secret value.")
        if is_raw_secret_value(reference.reference):
            raise ContractValidationError(f"Secret reference {reference.reference_id} appears to contain a raw secret value.")
        if reference.reference.strip().lower().startswith(("password=", "token=", "secret=", "api_key=")):
            raise ContractValidationError(f"Secret reference {reference.reference_id} contains a secret-like assignment.")


def is_raw_secret_value(value: str) -> bool:
    normalized = str(value or "").strip()
    lowered = normalized.lower()
    safe_markers = (
        "gcp_secret://",
        "secret://",
        "vault://",
        "credential://",
        "n8n_credential://",
        "env:",
        "github_actions_secret:",
    )
    if any(lowered.startswith(marker) for marker in safe_markers):
        return False
    raw_prefixes = ("sk-", "ghp_", "github_pat_", "glpat-", "xoxb-", "xoxp-", "xoxa-", "ya29.", "AIza")
    if normalized.startswith(raw_prefixes):
        return True
    if "BEGIN PRIVATE KEY" in normalized:
        return True
    if normalized.count(".") == 2 and normalized.startswith("eyJ"):
        return True
    return False


def validate_generated_artifacts(
    work_order_id: str,
    correlation_id: str,
    targets: Dict[str, Path],
) -> ValidationReceipt:
    validated: List[Dict[str, Any]] = []
    failures: List[str] = []
    for schema_name, path in targets.items():
        try:
            result = validate_file(schema_name, path)
            validated.append(asdict(result))
        except Exception as exc:  # pragma: no cover - defensive receipt path
            failures.append(f"{schema_name}:{path}: {exc}")
    return ValidationReceipt(
        receipt_id=make_id("AIGC-VALIDATION", work_order_id, correlation_id),
        work_order_id=work_order_id,
        correlation_id=correlation_id,
        created_at=utc_now(),
        valid=not failures,
        validated_artifacts=validated,
        failures=failures,
    )


def render_operator_report(
    work_order: WorkOrder,
    decision: GovernanceDecision,
    permit: ExternalActionPermit,
    approval: ApprovalPacket,
) -> str:
    criteria = "\n".join(f"- {item}" for item in work_order.acceptance_criteria) or "- None supplied."
    blocked = "\n".join(f"- {item}" for item in decision.blocked_operations)
    approvals = "\n".join(f"- {item}" for item in decision.required_approvals)
    risks = "\n".join(f"- {finding.severity}: {finding.summary}" for finding in decision.risk_findings)
    return f"""# AIGC Work Order Review Packet

Generated At: {utc_now()}

Work Order: {work_order.work_order_id}

Correlation ID: {decision.correlation_id}

## Operator Intent

**Title:** {work_order.title}

**Objective:** {work_order.objective}

**Desired Output:** {work_order.desired_output}

## Classification

- Classification: `{decision.classification}`
- Risk Class: `{decision.risk_class}`
- Status: `{decision.status}`
- External Action Allowed: `false`
- Self Approval Allowed: `false`
- Symbolic Layers Grant Authority: `false`

## Acceptance Criteria

{criteria}

## Required Approvals

{approvals}

## Blocked Operations

{blocked}

## Risk Findings

{risks}

## External Action Permit

- Requested: `{str(permit.requested).lower()}`
- Status: `{permit.status}`
- Live Execution Allowed: `false`
- External Action Performed: `false`

## Approval Packet

Type this exact phrase only after review if you accept internal governed preparation:

```text
{approval.required_phrase}
```

Deny phrase:

```text
{approval.denial_phrase}
```

Revision template:

```text
{approval.revision_phrase_template}
```

## Boundary

Accept does not submit, message, bid, apply, purchase, deploy, use credentials, log secrets, or perform external API side effects.
"""


def serialize(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        payload: Dict[str, Any] = {}
        for key, item in asdict(value).items():
            payload[key] = serialize(item)
        return payload
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize(item) for key, item in value.items()}
    return value


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def relative_to_root(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def safe_path_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)[:96]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_provenance(project_root: Path) -> tuple[str, str]:
    """Return the checked-out source revision/tree without network access.

    Non-git source distributions report `unavailable` instead of inventing provenance.
    """
    values: List[str] = []
    for revision in ("HEAD", "HEAD^{tree}"):
        try:
            result = subprocess.run(
                ["git", "-C", str(project_root), "rev-parse", revision],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            values.append("unavailable")
            continue
        value = result.stdout.strip()
        if result.returncode != 0 or len(value) not in {40, 64} or any(c not in "0123456789abcdef" for c in value.lower()):
            values.append("unavailable")
        else:
            values.append(value.lower())
    return values[0], values[1]


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def unique(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
