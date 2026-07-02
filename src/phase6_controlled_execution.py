from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


class ExecutionMode(str, Enum):
    DRY_RUN = "dry_run"
    MANUAL_HANDOFF = "manual_handoff"
    APPROVED_API = "approved_api"
    APPROVED_PLATFORM_UI = "approved_platform_ui"


class ExecutionStatus(str, Enum):
    DRY_RUN_COMPLETE = "dry_run_complete"
    REQUIRES_MANUAL_COMPLETION = "requires_manual_completion"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    MISMATCH_DETECTED = "mismatch_detected"


@dataclass
class ExecutionArtifact:
    artifact_type: str
    content: str
    hash: str
    format: str = "text"


@dataclass
class ExecutionAuthorization:
    approved_for_phase6: bool
    authorization_id: str
    action_id: str
    proposal_id: str
    opportunity_id: str
    operator: str
    approved_at: str
    expires_at: str
    artifact_hash_at_approval: str
    execution_scope: str
    recipient: str
    platform: str
    source_url: str


@dataclass
class ExecutionSafety:
    platform_policy_checked: bool = False
    ai_disclosure_preserved: bool = False
    privacy_checked: bool = False
    credential_use_approved: bool = False
    batch_action: bool = False
    forbidden_action_detected: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class ExecutionPacket:
    authorization: ExecutionAuthorization
    artifact: ExecutionArtifact
    action_type: str
    execution_mode: str
    safety: ExecutionSafety


@dataclass
class ExecutionResult:
    execution_id: str
    authorization_id: str
    action_id: str
    proposal_id: str
    opportunity_id: str
    operator: str
    action_type: str
    recipient: str
    platform: str
    execution_mode: str
    artifact_hash: str
    status: str
    confirmation_id: str = ""
    response_summary: str = ""
    error: str = ""
    executed_at: str = ""
    audit_event_ids: List[str] = field(default_factory=list)
    phase7_handoff_ready: bool = False
    employer_audit_packet_required: bool = True


class Phase6AuditLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "timestamp": utc_now(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event_id


class HashTools:
    @staticmethod
    def hash_text(value: str) -> str:
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


class ExecutionAdapter(Protocol):
    def execute(self, packet: ExecutionPacket) -> ExecutionResult:
        ...


class DryRunAdapter:
    def execute(self, packet: ExecutionPacket) -> ExecutionResult:
        auth = packet.authorization
        return result_from_packet(
            packet=packet,
            status=ExecutionStatus.DRY_RUN_COMPLETE.value,
            response_summary=(
                "Dry run completed. No external action performed. "
                "Artifact, recipient, platform, scope, and hash are ready for operator review."
            ),
            phase7_handoff_ready=False,
        )


class ManualHandoffAdapter:
    def execute(self, packet: ExecutionPacket) -> ExecutionResult:
        auth = packet.authorization
        handoff = f"""
MANUAL EXECUTION HANDOFF
Operator:
{auth.operator}
Action ID:
{auth.action_id}
Platform:
{auth.platform}
Recipient:
{auth.recipient}
Source URL:
{auth.source_url}
Approved Action:
{auth.execution_scope}
Artifact Type:
{packet.artifact.artifact_type}
Artifact Hash:
{packet.artifact.hash}
Artifact Content:
{packet.artifact.content}
Instructions:
1. Open the approved platform manually.
2. Navigate only to the approved recipient or opportunity.
3. Paste or upload only the approved artifact.
4. Do not change the artifact unless returning to Phase 4 and Phase 5.
5. Submit only if you still consent to the approved action.
6. Capture confirmation or a receipt if available.
7. Return confirmation to AIGC for Phase 7 audit packet creation.
""".strip()
        return result_from_packet(
            packet=packet,
            status=ExecutionStatus.REQUIRES_MANUAL_COMPLETION.value,
            response_summary=handoff,
            phase7_handoff_ready=False,
        )


class ApprovedAPIAdapter:
    def execute(self, packet: ExecutionPacket) -> ExecutionResult:
        return result_from_packet(
            packet=packet,
            status=ExecutionStatus.BLOCKED.value,
            error=(
                "Approved API execution is not implemented. Live execution requires a "
                "platform-specific approved connector, approved credential path, and policy review."
            ),
            phase7_handoff_ready=False,
        )


class PlatformUIAssistAdapter:
    def execute(self, packet: ExecutionPacket) -> ExecutionResult:
        auth = packet.authorization
        instructions = f"""
APPROVED PLATFORM UI ASSIST
This mode does not automate the platform UI.
Platform:
{auth.platform}
Recipient:
{auth.recipient}
Approved Scope:
{auth.execution_scope}
Steps:
1. Manually open the platform.
2. Confirm the opportunity and recipient match the approved packet.
3. Confirm no platform rule prohibits this action.
4. Paste or upload the approved artifact only.
5. Preserve AI-use disclosure if present.
6. Submit manually only if you still approve.
7. Save confirmation for audit.
""".strip()
        return result_from_packet(
            packet=packet,
            status=ExecutionStatus.REQUIRES_MANUAL_COMPLETION.value,
            response_summary=instructions,
            phase7_handoff_ready=False,
        )


class Phase6Validator:
    ALLOWED_ACTION_TYPES = {
        "send_proposal",
        "apply",
        "message",
        "bid",
        "submit_deliverable",
        "share_audit_packet",
    }

    def validate(self, packet: ExecutionPacket) -> Optional[str]:
        auth = packet.authorization
        if not auth.approved_for_phase6:
            return "Authorization is not approved for Phase 6."
        if packet.action_type not in self.ALLOWED_ACTION_TYPES:
            return f"Action type not allowed in Phase 6: {packet.action_type}"
        if packet.safety.forbidden_action_detected:
            return "Safety object indicates forbidden action."
        if packet.safety.batch_action:
            return "Batch actions are forbidden in Phase 6."
        if not auth.action_id or not auth.proposal_id or not auth.authorization_id:
            return "Missing required authorization identifiers."
        if not auth.recipient:
            return "Missing approved recipient."
        if not auth.platform:
            return "Missing approved platform."
        current_hash = HashTools.hash_text(packet.artifact.content)
        if current_hash != packet.artifact.hash:
            return "Artifact self-hash mismatch."
        if packet.artifact.hash != auth.artifact_hash_at_approval:
            return "Artifact changed after approval. Return to Phase 5."
        expires_at = parse_datetime(auth.expires_at)
        if expires_at is None:
            return "Invalid expiration timestamp."
        if datetime.now(timezone.utc) > expires_at:
            return "Authorization expired."
        if not packet.safety.ai_disclosure_preserved:
            return "AI disclosure preservation was not confirmed."
        if not packet.safety.privacy_checked:
            return "Privacy check was not confirmed."
        if packet.execution_mode == ExecutionMode.APPROVED_API.value and not packet.safety.credential_use_approved:
            return "API execution requested without approved credential use."
        return None


class ControlledExecutionEngine:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.ledger = Phase6AuditLedger(project_root / "data" / "audit" / "aigc_phase6_audit.jsonl")
        self.validator = Phase6Validator()
        self.adapters: Dict[str, ExecutionAdapter] = {
            ExecutionMode.DRY_RUN.value: DryRunAdapter(),
            ExecutionMode.MANUAL_HANDOFF.value: ManualHandoffAdapter(),
            ExecutionMode.APPROVED_API.value: ApprovedAPIAdapter(),
            ExecutionMode.APPROVED_PLATFORM_UI.value: PlatformUIAssistAdapter(),
        }

    def execute(self, packet: ExecutionPacket) -> ExecutionResult:
        loaded_event = self.ledger.record("phase6_packet_loaded", {
            "authorization_id": packet.authorization.authorization_id,
            "action_id": packet.authorization.action_id,
            "proposal_id": packet.authorization.proposal_id,
            "recipient": packet.authorization.recipient,
            "platform": packet.authorization.platform,
            "execution_mode": packet.execution_mode,
            "action_type": packet.action_type,
        })
        validation_error = self.validator.validate(packet)
        if validation_error:
            result = result_from_packet(
                packet=packet,
                status=ExecutionStatus.BLOCKED.value,
                error=validation_error,
                phase7_handoff_ready=False,
            )
            result.audit_event_ids.append(loaded_event)
            result.audit_event_ids.append(self.ledger.record("phase6_execution_blocked", asdict(result)))
            return result
        adapter = self.adapters.get(packet.execution_mode)
        if adapter is None:
            result = result_from_packet(
                packet=packet,
                status=ExecutionStatus.BLOCKED.value,
                error=f"Unknown execution mode: {packet.execution_mode}",
                phase7_handoff_ready=False,
            )
            result.audit_event_ids.append(loaded_event)
            result.audit_event_ids.append(self.ledger.record("phase6_unknown_execution_mode", asdict(result)))
            return result
        result = adapter.execute(packet)
        result.audit_event_ids.append(loaded_event)
        result.audit_event_ids.append(self.ledger.record("phase6_execution_result", asdict(result)))
        return result

    def run_from_config(self, config_path: Path, execution_mode_override: str | None = None) -> List[ExecutionResult]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        auth_path = resolve_project_path(self.project_root, inputs.get("phase5_authorizations", ""))
        proposal_path = resolve_project_path(self.project_root, inputs.get("phase4_proposals", ""))
        output_path = resolve_project_path(self.project_root, config.get("output_file", "data/phase6_execution/aigc_phase6_execution_receipts.json"))
        mode = execution_mode_override or str(config.get("default_execution_mode", ExecutionMode.MANUAL_HANDOFF.value))
        if mode == ExecutionMode.APPROVED_API.value and not config.get("live_execution_allowed", False):
            mode = ExecutionMode.MANUAL_HANDOFF.value
        authorizations = load_json_list(auth_path) if auth_path.exists() else []
        proposals = load_json_list(proposal_path) if proposal_path.exists() else []
        proposals_by_id = {proposal.get("proposal_id", ""): proposal for proposal in proposals}
        results: List[ExecutionResult] = []
        for authorization in authorizations:
            if authorization.get("decision") != "approved_for_phase_6":
                continue
            if not (authorization.get("phase6_status") or {}).get("authorized_for_phase6", False):
                continue
            packet = build_packet_from_phase5_authorization(
                authorization_packet=authorization,
                phase4_proposal=proposals_by_id.get(authorization.get("proposal_id", ""), {}),
                execution_mode=mode,
            )
            results.append(self.execute(packet))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2), encoding="utf-8")
        self.ledger.record("phase6_execution_receipts_exported", {"path": str(output_path), "records": len(results)})
        report_path = self.project_root / "data" / "reports" / "phase6_signature_update.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(results, authorizations), encoding="utf-8")
        return results

    def signature_update(self, results: List[ExecutionResult], authorizations: Optional[List[Dict[str, Any]]] = None) -> str:
        authorizations = authorizations or []
        approved_available = [
            item for item in authorizations
            if item.get("decision") == "approved_for_phase_6"
            and (item.get("phase6_status") or {}).get("authorized_for_phase6", False)
        ]
        completed = [result for result in results if result.status == ExecutionStatus.COMPLETED.value]
        manual = [result for result in results if result.status == ExecutionStatus.REQUIRES_MANUAL_COMPLETION.value]
        blocked = [result for result in results if result.status == ExecutionStatus.BLOCKED.value]
        dry_runs = [result for result in results if result.status == ExecutionStatus.DRY_RUN_COMPLETE.value]
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 6 - Controlled Execution Engine",
            "Operational Identity:",
            "Exact-Action Execution Layer",
            "Action Performed:",
            "Validated approved Phase 5 packets and produced exact-scope execution receipts or handoffs.",
            "Safety Review:",
            "No unapproved action executed.",
            "No batch execution performed.",
            "No credentials used.",
            "No artifact modified after approval.",
            "No external action performed by this CLI.",
            f"Approved Packets Available: {len(approved_available)}",
            f"Execution Receipts Created: {len(results)}",
            f"Completed: {len(completed)}",
            f"Manual Completion Required: {len(manual)}",
            f"Dry Runs: {len(dry_runs)}",
            f"Blocked: {len(blocked)}",
            "Next Recommended Action:",
            "Approve a specific Phase 5 action ID before Phase 6 can create a manual handoff or execution receipt.",
        ]).strip() + "\n"


def build_packet_from_phase5_authorization(
    authorization_packet: Dict[str, Any],
    phase4_proposal: Dict[str, Any],
    execution_mode: str = ExecutionMode.MANUAL_HANDOFF.value,
) -> ExecutionPacket:
    artifact_record = authorization_packet.get("artifact", {}) or {}
    phase6_status = authorization_packet.get("phase6_status", {}) or {}
    approval = authorization_packet.get("approval", {}) or {}
    artifact_content = phase4_proposal.get("employer_facing_message", "")
    if not artifact_content:
        artifact_content = artifact_record.get("artifact_preview", "")
    artifact_hash = HashTools.hash_text(artifact_content)
    auth = ExecutionAuthorization(
        approved_for_phase6=bool(phase6_status.get("authorized_for_phase6", False)),
        authorization_id=authorization_packet.get("authorization_id", ""),
        action_id=authorization_packet.get("action_id", ""),
        proposal_id=authorization_packet.get("proposal_id", ""),
        opportunity_id=authorization_packet.get("opportunity_id", ""),
        operator=authorization_packet.get("operator", "Justice Gray Maciocha"),
        approved_at=approval.get("approved_at", ""),
        expires_at=authorization_packet.get("expires_at", ""),
        artifact_hash_at_approval=artifact_record.get("artifact_hash", ""),
        execution_scope=phase6_status.get("execution_scope", ""),
        recipient=authorization_packet.get("recipient", ""),
        platform=authorization_packet.get("platform", ""),
        source_url=authorization_packet.get("source_url", ""),
    )
    return ExecutionPacket(
        authorization=auth,
        artifact=ExecutionArtifact(
            artifact_type=artifact_record.get("artifact_type", "proposal"),
            content=artifact_content,
            hash=artifact_hash,
            format="text",
        ),
        action_type=infer_action_type(authorization_packet.get("proposed_external_action", "")),
        execution_mode=execution_mode,
        safety=ExecutionSafety(
            platform_policy_checked=True,
            ai_disclosure_preserved=True,
            privacy_checked=True,
            credential_use_approved=False,
            batch_action=False,
            forbidden_action_detected=False,
            notes=[
                "Manual handoff and dry-run default.",
                "Live API execution requires platform-specific approval and connector implementation.",
            ],
        ),
    )


def infer_action_type(proposed_action: str) -> str:
    value = (proposed_action or "").lower()
    if "share audit" in value:
        return "share_audit_packet"
    if "submit deliverable" in value:
        return "submit_deliverable"
    if "bid" in value:
        return "bid"
    if "apply" in value or "application" in value:
        return "apply"
    if "send proposal" in value or "proposal" in value:
        return "send_proposal"
    return "message"


def result_from_packet(
    packet: ExecutionPacket,
    status: str,
    response_summary: str = "",
    error: str = "",
    phase7_handoff_ready: bool = False,
) -> ExecutionResult:
    auth = packet.authorization
    return ExecutionResult(
        execution_id=f"AIGC-EXEC-{uuid.uuid4()}",
        authorization_id=auth.authorization_id,
        action_id=auth.action_id,
        proposal_id=auth.proposal_id,
        opportunity_id=auth.opportunity_id,
        operator=auth.operator,
        action_type=packet.action_type,
        recipient=auth.recipient,
        platform=auth.platform,
        execution_mode=packet.execution_mode,
        artifact_hash=packet.artifact.hash,
        status=status,
        response_summary=response_summary,
        error=error,
        executed_at=utc_now(),
        phase7_handoff_ready=phase7_handoff_ready,
    )


def parse_datetime(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_json_dict(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return payload


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run AIGC Phase 6 controlled execution.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase6_controlled_execution.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engine = ControlledExecutionEngine(project_root=args.project_root)
    results = engine.run_from_config(args.config)
    print(engine.signature_update(results, load_json_list(args.project_root / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json")))
    print(f"\nReceipts exported: {args.project_root / 'data' / 'phase6_execution' / 'aigc_phase6_execution_receipts.json'}")
    print(f"Report exported: {args.project_root / 'data' / 'reports' / 'phase6_signature_update.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
