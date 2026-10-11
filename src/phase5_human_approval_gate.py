from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ActionClass(str, Enum):
    AUTONOMOUS_ALLOWED = "autonomous_allowed"
    APPROVAL_REQUIRED = "approval_required"
    ENHANCED_APPROVAL_REQUIRED = "enhanced_approval_required"
    BLOCKED_BY_SAFETY = "blocked_by_safety"


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED_FOR_PHASE_6 = "approved_for_phase_6"
    DENIED = "denied"
    REVISION_REQUIRED = "revision_required"
    BLOCKED_BY_SAFETY = "blocked_by_safety"
    EXPIRED = "expired"


@dataclass
class ArtifactRecord:
    artifact_type: str
    artifact_summary: str
    artifact_hash: str
    artifact_preview: str


@dataclass
class ClassificationRecord:
    action_class: str
    risk_class: str
    safety_status: str


@dataclass
class CheckRecord:
    safety_check_score: int
    coherence_check_score: int
    proposal_readiness_score: int
    ai_disclosure_status: str


@dataclass
class ApprovalRecord:
    required: bool
    required_phrase: str
    denial_phrase: str
    revision_phrase_template: str
    received_phrase: str = ""
    approved: bool = False
    denied: bool = False
    revision_required: bool = False
    approved_at: str = ""
    decision_notes: str = ""


@dataclass
class Phase6Status:
    authorized_for_phase6: bool = False
    execution_scope: str = ""
    external_action_performed: bool = False


@dataclass
class AuthorizationPacket:
    authorization_id: str
    action_id: str
    proposal_id: str
    opportunity_id: str
    operator: str
    created_at: str
    expires_at: str
    proposed_external_action: str
    recipient: str
    platform: str
    source_url: str
    artifact: ArtifactRecord
    classification: ClassificationRecord
    checks: CheckRecord
    approval: ApprovalRecord
    phase6_status: Phase6Status
    approval_request: str
    decision: str = ApprovalDecision.PENDING.value
    audit_event_ids: List[str] = field(default_factory=list)


class Phase5AuditLedger:
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


class Phase5Hasher:
    @staticmethod
    def hash_text(value: str) -> str:
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()

    @staticmethod
    def short_hash(value: str, length: int = 16) -> str:
        return Phase5Hasher.hash_text(value)[:length]


class ActionClassifier:
    APPROVAL_REQUIRED_TERMS = [
        "send proposal",
        "send message",
        "message employer",
        "message to",
        "apply",
        "submit proposal",
        "submit application",
        "bid",
        "accept contract",
        "submit deliverable",
        "use credentials",
        "publish",
        "share audit packet",
        "use operator identity",
    ]
    SENSITIVE_TERMS = [
        "api credentials",
        "personal data",
        "payment details",
        "legal terms",
        "security testing",
        "private repository",
        "regulated domain",
        "sign agreement",
    ]
    FORBIDDEN_TERMS = [
        "spam",
        "impersonate",
        "fake qualification",
        "credential misuse",
        "scrape forbidden",
        "fraud",
        "malware",
        "unauthorized access",
        "privacy invasion",
        "harassment",
        "illegal",
    ]

    def classify(self, action_text: str, package: Dict[str, Any]) -> ClassificationRecord:
        # Deliberately inspect outward-facing material and proposed action only.
        # Internal forbidden-action labels include words like "bypass" and should not self-trigger a block.
        outward_blob = " ".join(
            [
                action_text or "",
                str(package.get("employer_facing_message", "")),
                json.dumps(package.get("risk_notes", {}), ensure_ascii=False),
                json.dumps(package.get("human_approval_preview", {}), ensure_ascii=False),
            ]
        ).lower()
        if any(term in outward_blob for term in self.FORBIDDEN_TERMS):
            return ClassificationRecord(
                action_class=ActionClass.BLOCKED_BY_SAFETY.value,
                risk_class="blocked",
                safety_status="blocked",
            )
        if any(term in outward_blob for term in self.SENSITIVE_TERMS):
            return ClassificationRecord(
                action_class=ActionClass.ENHANCED_APPROVAL_REQUIRED.value,
                risk_class="high",
                safety_status="enhanced_review_required",
            )
        if any(term in outward_blob for term in self.APPROVAL_REQUIRED_TERMS):
            return ClassificationRecord(
                action_class=ActionClass.APPROVAL_REQUIRED.value,
                risk_class="medium",
                safety_status="caution",
            )
        return ClassificationRecord(
            action_class=ActionClass.AUTONOMOUS_ALLOWED.value,
            risk_class="low",
            safety_status="cleared",
        )


class SafetyChecklist:
    NEGATIVE_TERMS = [
        "fake qualification",
        "impersonate",
        "spam",
        "scrape forbidden",
        "credential misuse",
        "malware",
        "unauthorized access",
        "fraud",
    ]

    def evaluate(self, package: Dict[str, Any], classification: ClassificationRecord) -> int:
        score = 15
        outward_blob = " ".join(
            [
                str(package.get("employer_facing_message", "")),
                json.dumps(package.get("risk_notes", {}), ensure_ascii=False),
                json.dumps(package.get("human_approval_preview", {}), ensure_ascii=False),
            ]
        ).lower()
        for term in self.NEGATIVE_TERMS:
            if term in outward_blob:
                score -= 5
        disclosure = package.get("ai_use_disclosure", {})
        if isinstance(disclosure, dict):
            recommended = disclosure.get("recommended", False)
            required = disclosure.get("required", False)
            draft = disclosure.get("draft_language", "")
            if (recommended or required) and not draft:
                score -= 3
        readiness_total = readiness_total_from_package(package)
        if readiness_total < 80:
            score -= 3
        if classification.action_class == ActionClass.ENHANCED_APPROVAL_REQUIRED.value:
            score -= 2
        if classification.action_class == ActionClass.BLOCKED_BY_SAFETY.value:
            score = 0
        return max(0, min(15, score))


class CoherenceChecklist:
    REQUIRED_FIELDS = [
        "employer_facing_message",
        "scope_of_work",
        "deliverables",
        "timeline",
        "human_approval_preview",
    ]

    def evaluate(self, package: Dict[str, Any]) -> int:
        score = 10
        for field_name in self.REQUIRED_FIELDS:
            if not package.get(field_name):
                score -= 2
        message = str(package.get("employer_facing_message", ""))
        if len(message.strip()) < 100:
            score -= 2
        if not package.get("deliverables", []):
            score -= 2
        preview = package.get("human_approval_preview", {})
        if isinstance(preview, dict) and not preview.get("proposed_external_action"):
            score -= 2
        return max(0, min(10, score))


class Phase5ApprovalGate:
    def __init__(self, project_root: Path, operator: str = "Justice Gray Maciocha", expiration_hours: int = 24):
        self.project_root = project_root
        self.operator = operator
        self.expiration_hours = expiration_hours
        self.audit_dir = project_root / "data" / "audit"
        self.output_dir = project_root / "data" / "phase5_authorizations"
        self.report_dir = project_root / "data" / "reports"
        for path in [self.audit_dir, self.output_dir, self.report_dir]:
            path.mkdir(parents=True, exist_ok=True)
        self.ledger = Phase5AuditLedger(self.audit_dir / "aigc_phase5_audit.jsonl")
        self.classifier = ActionClassifier()
        self.safety = SafetyChecklist()
        self.coherence = CoherenceChecklist()

    def run_from_config(self, config_path: Path) -> List[AuthorizationPacket]:
        config = load_json_dict(config_path)
        input_path = resolve_project_path(
            self.project_root,
            config.get("input_file", "data/phase4_proposals/aigc_phase4_proposal_packages.json"),
        )
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase5_authorizations/aigc_phase5_authorization_packets.json"),
        )
        eligible = set(config.get("eligible_phase4_readiness_decisions", ["ready_for_phase_5", "strong_minor_review"]))
        self.expiration_hours = int(config.get("approval_expiration_hours", self.expiration_hours))
        packages = load_json_list(input_path)
        return self.run(packages, output_path, eligible_readiness=eligible)

    def run(
        self,
        packages: List[Dict[str, Any]],
        output_path: Optional[Path] = None,
        eligible_readiness: Optional[set[str]] = None,
    ) -> List[AuthorizationPacket]:
        environment = os.environ.get("AIGC_ENV", os.environ.get("ENVIRONMENT", "development")).strip().lower()
        if environment in {"production", "prod"}:
            raise RuntimeError(
                "Phase 5 packet generation is disabled in production until authorization packets "
                "are read and written through the shared durable artifact repository."
            )
        eligible = eligible_readiness or {"ready_for_phase_5", "strong_minor_review"}
        self.ledger.record(
            "phase5_run_start",
            {
                "input_packages": len(packages),
                "eligible_readiness_decisions": sorted(eligible),
                "external_actions_allowed_in_phase5": False,
            },
        )
        selected = [package for package in packages if package.get("readiness_decision") in eligible]
        packets = []
        for index, package in enumerate(selected, start=1):
            packet = self.create_authorization_packet(package, index)
            packets.append(packet)
        target = output_path or self.output_dir / "aigc_phase5_authorization_packets.json"
        self.export_packets(packets, target)
        self.export_signature_update(packets)
        self.ledger.record(
            "phase5_run_complete",
            {"eligible_packages": len(selected), "packets_created": len(packets), "output_path": str(target)},
        )
        return packets

    def create_authorization_packet(self, package: Dict[str, Any], sequence_number: int) -> AuthorizationPacket:
        proposal_id = package.get("proposal_id", package.get("package_id", ""))
        opportunity_id = package.get("opportunity_id", "")
        recipient = package.get("employer", "unknown_recipient")
        platform = package.get("source_platform", "")
        source_url = package.get("source_url", "")
        approval_preview = package.get("human_approval_preview", {}) or {}
        proposed_action = approval_preview.get(
            "proposed_external_action",
            f"Send proposal/message to {recipient} for: {package.get('title', '')}",
        )
        action_id = self._make_action_id(sequence_number)
        authorization_id = "AIGC-AUTH-" + Phase5Hasher.short_hash(action_id + proposal_id, 18)
        artifact_text = package.get("employer_facing_message", "")
        artifact = ArtifactRecord(
            artifact_type="proposal",
            artifact_summary=f"Employer-facing proposal for {package.get('title', '')}",
            artifact_hash=Phase5Hasher.hash_text(artifact_text),
            artifact_preview=artifact_text[:1200],
        )
        classification = self.classifier.classify(proposed_action, package)
        safety_score = self.safety.evaluate(package, classification)
        coherence_score = self.coherence.evaluate(package)
        readiness_total = readiness_total_from_package(package)
        disclosure_status = disclosure_status_from_package(package)
        checks = CheckRecord(
            safety_check_score=safety_score,
            coherence_check_score=coherence_score,
            proposal_readiness_score=readiness_total,
            ai_disclosure_status=disclosure_status,
        )
        classification = self._tighten_classification(classification, checks)
        required_phrase = f"I, {self.operator}, accept action {action_id}."
        approval = ApprovalRecord(
            required=classification.action_class
            in {ActionClass.APPROVAL_REQUIRED.value, ActionClass.ENHANCED_APPROVAL_REQUIRED.value},
            required_phrase=required_phrase,
            denial_phrase=f"I, {self.operator}, deny action {action_id}.",
            revision_phrase_template=f"Revise action {action_id}: [revision instructions]",
        )
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(hours=self.expiration_hours)
        packet = AuthorizationPacket(
            authorization_id=authorization_id,
            action_id=action_id,
            proposal_id=proposal_id,
            opportunity_id=opportunity_id,
            operator=self.operator,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            proposed_external_action=proposed_action,
            recipient=recipient,
            platform=platform,
            source_url=source_url,
            artifact=artifact,
            classification=classification,
            checks=checks,
            approval=approval,
            phase6_status=Phase6Status(
                authorized_for_phase6=False,
                execution_scope=proposed_action,
                external_action_performed=False,
            ),
            approval_request="",
        )
        if classification.action_class == ActionClass.BLOCKED_BY_SAFETY.value:
            packet.decision = ApprovalDecision.BLOCKED_BY_SAFETY.value
        packet.approval_request = self.approval_request_text(packet)
        event_id = self.ledger.record("authorization_packet_created", asdict(packet))
        packet.audit_event_ids.append(event_id)
        return packet

    def validate_operator_response(
        self,
        packet: AuthorizationPacket,
        operator_response: str,
        current_artifact_text: Optional[str] = None,
    ) -> AuthorizationPacket:
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromisoformat(packet.expires_at)
        if now > expires_at:
            packet.decision = ApprovalDecision.EXPIRED.value
            packet.approval.decision_notes = "Authorization request expired."
            packet.audit_event_ids.append(self.ledger.record("authorization_expired", asdict(packet)))
            return packet
        if packet.decision == ApprovalDecision.BLOCKED_BY_SAFETY.value:
            packet.approval.denied = True
            packet.approval.decision_notes = "Blocked action cannot be approved by normal approval phrase."
            packet.audit_event_ids.append(self.ledger.record("blocked_action_approval_attempt", asdict(packet)))
            return packet
        if current_artifact_text is not None:
            current_hash = Phase5Hasher.hash_text(current_artifact_text)
            if current_hash != packet.artifact.artifact_hash:
                packet.decision = ApprovalDecision.REVISION_REQUIRED.value
                packet.approval.revision_required = True
                packet.approval.decision_notes = "Artifact changed after packet creation. Re-approval required."
                packet.audit_event_ids.append(self.ledger.record("artifact_changed_reapproval_required", asdict(packet)))
                return packet
        response = operator_response.strip()
        packet.approval.received_phrase = response
        if response == packet.approval.required_phrase:
            packet.approval.approved = True
            packet.approval.approved_at = now.isoformat()
            packet.decision = ApprovalDecision.APPROVED_FOR_PHASE_6.value
            packet.phase6_status.authorized_for_phase6 = True
            packet.approval.decision_notes = "Correct scoped acceptance phrase received."
            packet.audit_event_ids.append(self.ledger.record("authorization_approved_for_phase6", asdict(packet)))
            return packet
        if response == packet.approval.denial_phrase:
            packet.approval.denied = True
            packet.decision = ApprovalDecision.DENIED.value
            packet.approval.decision_notes = "Operator denied action."
            packet.audit_event_ids.append(self.ledger.record("authorization_denied", asdict(packet)))
            return packet
        revise_prefix = f"Revise action {packet.action_id}:"
        if response.startswith(revise_prefix):
            packet.approval.revision_required = True
            packet.decision = ApprovalDecision.REVISION_REQUIRED.value
            packet.approval.decision_notes = response[len(revise_prefix) :].strip()
            packet.audit_event_ids.append(self.ledger.record("authorization_revision_required", asdict(packet)))
            return packet
        packet.approval.denied = True
        packet.decision = ApprovalDecision.DENIED.value
        packet.approval.decision_notes = "Response did not match required accept, deny, or revise phrase."
        packet.audit_event_ids.append(self.ledger.record("authorization_invalid_response", asdict(packet)))
        return packet

    def export_packets(self, packets: List[AuthorizationPacket], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([asdict(packet) for packet in packets], ensure_ascii=False, indent=2), encoding="utf-8")
        self.ledger.record("authorization_packets_exported", {"path": str(path), "records": len(packets)})
        return path

    def export_signature_update(self, packets: List[AuthorizationPacket]) -> Path:
        path = self.report_dir / "phase5_signature_update.md"
        path.write_text(self.signature_update(packets), encoding="utf-8")
        self.ledger.record("signature_update_exported", {"path": str(path)})
        return path

    def approval_request_text(self, packet: AuthorizationPacket) -> str:
        return f"""
AIGC PHASE 5 APPROVAL REQUEST
Operator:
{packet.operator}
Authorization ID:
{packet.authorization_id}
Action ID:
{packet.action_id}
Proposal ID:
{packet.proposal_id}
Opportunity ID:
{packet.opportunity_id}
Employer / Recipient:
{packet.recipient}
Platform:
{packet.platform}
Proposed External Action:
{packet.proposed_external_action}
Artifact Type:
{packet.artifact.artifact_type}
Artifact Hash:
{packet.artifact.artifact_hash}
Artifact Preview:
{packet.artifact.artifact_preview}
Risk Class:
{packet.classification.risk_class}
Safety Status:
{packet.classification.safety_status}
Action Class:
{packet.classification.action_class}
Safety Checklist Score:
{packet.checks.safety_check_score}/15
Coherence Checklist Score:
{packet.checks.coherence_check_score}/10
Proposal Readiness Score:
{packet.checks.proposal_readiness_score}/100
AI Disclosure:
{packet.checks.ai_disclosure_status}
What Will Happen If Approved:
AIGC will be authorized to move this specific action into Phase 6 execution.
What Will Not Happen:
AIGC will not perform any other external action beyond this scoped action.
Accept:
{packet.approval.required_phrase}
Deny:
{packet.approval.denial_phrase}
Revise:
{packet.approval.revision_phrase_template}
Current Decision:
{packet.decision}
""".strip()

    def signature_update(self, packets: List[AuthorizationPacket]) -> str:
        approved = [packet for packet in packets if packet.decision == ApprovalDecision.APPROVED_FOR_PHASE_6.value]
        pending = [packet for packet in packets if packet.decision == ApprovalDecision.PENDING.value]
        denied = [packet for packet in packets if packet.decision == ApprovalDecision.DENIED.value]
        revisions = [packet for packet in packets if packet.decision == ApprovalDecision.REVISION_REQUIRED.value]
        blocked = [packet for packet in packets if packet.decision == ApprovalDecision.BLOCKED_BY_SAFETY.value]
        top = [
            {
                "authorization_id": packet.authorization_id,
                "action_id": packet.action_id,
                "proposal_id": packet.proposal_id,
                "recipient": packet.recipient,
                "action_class": packet.classification.action_class,
                "decision": packet.decision,
                "required_phrase": packet.approval.required_phrase,
            }
            for packet in packets[:5]
        ]
        return "\n".join(
            [
                "AIGC SIGNATURE UPDATE",
                "Operator:",
                self.operator,
                "Phase:",
                "Phase 5 - Human Approval Gate",
                "Operational Identity:",
                "Permission Gate / Sovereign Authorization Layer",
                "Action Performed:",
                "Created scoped authorization packets for eligible Phase 4 proposal packages.",
                "Safety Review:",
                "No proposal sent.",
                "No application submitted.",
                "No employer contacted.",
                "No bid placed.",
                "No contract accepted.",
                "No credentials used.",
                "No external action performed.",
                f"Authorization Packets Created: {len(packets)}",
                f"Approved for Phase 6: {len(approved)}",
                f"Pending Approval: {len(pending)}",
                f"Denied: {len(denied)}",
                f"Revision Required: {len(revisions)}",
                f"Blocked by Safety: {len(blocked)}",
                "Top Authorization Requests:",
                json.dumps(top, indent=2),
                "Approval Required:",
                "Yes, for every external action.",
                "Next Recommended Action:",
                "Review, approve, deny, revise, or hold a specific action ID. No Phase 6 execution is authorized until exact scoped approval is received.",
            ]
        ).strip() + "\n"

    def _make_action_id(self, sequence_number: int) -> str:
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"AIGC-ACT-{date_part}-{sequence_number:04d}"

    def _tighten_classification(self, classification: ClassificationRecord, checks: CheckRecord) -> ClassificationRecord:
        if classification.action_class == ActionClass.BLOCKED_BY_SAFETY.value or checks.safety_check_score <= 7:
            return ClassificationRecord(
                action_class=ActionClass.BLOCKED_BY_SAFETY.value,
                risk_class="blocked",
                safety_status="blocked",
            )
        if checks.safety_check_score <= 11:
            return ClassificationRecord(
                action_class=ActionClass.ENHANCED_APPROVAL_REQUIRED.value,
                risk_class="high",
                safety_status="enhanced_review_required",
            )
        return classification


def readiness_total_from_package(package: Dict[str, Any]) -> int:
    score = package.get("readiness_score", {})
    if isinstance(score, dict):
        return sum(value for value in score.values() if isinstance(value, int))
    if isinstance(score, int):
        return score
    return 0


def disclosure_status_from_package(package: Dict[str, Any]) -> str:
    disclosure = package.get("ai_use_disclosure", {})
    if not isinstance(disclosure, dict):
        return "not_applicable"
    if disclosure.get("required") and disclosure.get("draft_language"):
        return "required"
    if disclosure.get("recommended") and disclosure.get("draft_language"):
        return "included"
    if disclosure.get("recommended"):
        return "recommended"
    return "not_applicable"


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 5 human approval gate.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase5_human_approval_gate.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json_dict(args.config)
    gate = Phase5ApprovalGate(
        project_root=args.project_root,
        operator="Justice Gray Maciocha",
        expiration_hours=int(config.get("approval_expiration_hours", 24)),
    )
    packets = gate.run_from_config(args.config)
    print(gate.signature_update(packets))
    print(f"\nPackets exported: {args.project_root / 'data' / 'phase5_authorizations' / 'aigc_phase5_authorization_packets.json'}")
    print(f"Report exported: {args.project_root / 'data' / 'reports' / 'phase5_signature_update.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
