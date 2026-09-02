from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.phase6_controlled_execution import (
    load_manual_handoff_confirmations,
    manual_confirmation_matches_handoff,
)


class PacketStatus(str, Enum):
    INTERNAL_DRAFT_ONLY = "internal_draft_only"
    READY_FOR_OPERATOR_REVIEW = "ready_for_operator_review"
    READY_WITH_CAUTION = "ready_with_caution"
    REVISE_BEFORE_DELIVERY = "revise_before_delivery"
    BLOCKED_NEEDS_REVISION = "blocked_needs_revision"


@dataclass
class ProjectIdentity:
    task_title: str
    employer_or_client: str
    platform: str
    source_url: str
    opportunity_id: str


@dataclass
class LinkedRecords:
    phase3_dossier_id: str = ""
    phase4_proposal_id: str = ""
    phase5_authorization_id: str = ""
    phase6_execution_id: str = ""
    action_id: str = ""


@dataclass
class ScopeOfWorkRecord:
    summary: str
    included_work: List[str]
    excluded_work: List[str]
    assumptions: List[str]
    dependencies: List[str]


@dataclass
class DeliverableRecord:
    name: str
    description: str
    format: str
    acceptance_criteria: List[str]
    deliverable_hash: str = ""
    file_reference: str = ""


@dataclass
class MethodologySummary:
    work_phases: List[str]
    tools_or_methods: List[str]
    quality_checks: List[str]


@dataclass
class AIAssistanceDisclosure:
    included: bool
    language: str
    employer_specific_requirement: str = ""


@dataclass
class HumanApprovalSummary:
    operator_reviewed: bool
    approval_required_before_external_action: bool
    approved_action_id: str
    approval_timestamp: str


@dataclass
class ExecutionSummary:
    execution_mode: str
    execution_status: str
    confirmation_id: str
    executed_at: str
    artifact_hash: str


@dataclass
class PrivacySecurityRecord:
    secrets_redacted: bool
    private_data_redacted: bool
    credentials_included: bool
    notes: List[str]


@dataclass
class RevisionAvailability:
    available: bool
    revision_types: List[str]


@dataclass
class AcceptanceRequest:
    requested_response: List[str]


@dataclass
class EmployerAuditPacket:
    packet_id: str
    status: str
    created_at: str
    operator: str
    project: ProjectIdentity
    linked_records: LinkedRecords
    scope_of_work: ScopeOfWorkRecord
    deliverables: List[DeliverableRecord]
    methodology_summary: MethodologySummary
    ai_assistance_disclosure: AIAssistanceDisclosure
    human_approval_summary: HumanApprovalSummary
    execution_summary: ExecutionSummary
    sources_or_inputs: List[str]
    assumptions: List[str]
    limitations: List[str]
    privacy_security: PrivacySecurityRecord
    revision_availability: RevisionAvailability
    acceptance_request: AcceptanceRequest
    quality_score: int
    quality_notes: List[str]
    employer_facing_text: str


class Phase7AuditLedger:
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


class Redactor:
    SECRET_PATTERNS = [
        r"sk-[A-Za-z0-9_\-]{10,}",
        r"AKIA[0-9A-Z]{16}",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"glpat-[A-Za-z0-9_\-]{20,}",
        r"xox[baprs]-[A-Za-z0-9\-]+",
        r"-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----",
        r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+",
        r"(?i)(token\s*[:=]\s*)[^\s,;]+",
        r"(?i)(secret\s*[:=]\s*)[^\s,;]+",
        r"(?i)(password\s*[:=]\s*)[^\s,;]+",
        r"(?i)(authorization\s*:\s*)[^\n]+",
        r"(?i)(cookie\s*:\s*)[^\n]+",
    ]
    PRIVATE_DATA_PATTERNS = [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b\d{16}\b",
    ]

    def redact_text(self, text: str) -> str:
        redacted = text or ""
        for pattern in self.SECRET_PATTERNS:
            redacted = re.sub(pattern, "[REDACTED_SECRET]", redacted, flags=re.DOTALL)
        for pattern in self.PRIVATE_DATA_PATTERNS:
            redacted = re.sub(pattern, "[REDACTED_PRIVATE_DATA]", redacted)
        return redacted


class QualityChecker:
    def score_packet(self, packet: EmployerAuditPacket) -> tuple[int, List[str]]:
        score = 15
        notes: List[str] = []
        if not packet.project.task_title:
            score -= 1
            notes.append("Missing task title.")
        if not packet.project.employer_or_client:
            score -= 1
            notes.append("Missing employer/client.")
        if not packet.scope_of_work.summary:
            score -= 1
            notes.append("Missing scope summary.")
        if not packet.deliverables:
            score -= 2
            notes.append("Missing deliverables.")
        if not packet.methodology_summary.work_phases:
            score -= 1
            notes.append("Missing methodology phases.")
        if packet.ai_assistance_disclosure.included and not packet.ai_assistance_disclosure.language:
            score -= 1
            notes.append("AI disclosure marked included but language missing.")
        if not packet.human_approval_summary.approved_action_id:
            score -= 1
            notes.append("Missing approved action ID.")
        if not packet.execution_summary.execution_status:
            score -= 1
            notes.append("Missing execution status.")
        if packet.privacy_security.credentials_included:
            score -= 5
            notes.append("Credentials must not be included.")
        if not packet.privacy_security.secrets_redacted:
            score -= 2
            notes.append("Secrets redaction not confirmed.")
        return max(0, min(15, score)), notes

    def status_from_score(self, score: int) -> str:
        if score >= 15:
            return PacketStatus.READY_FOR_OPERATOR_REVIEW.value
        if score >= 12:
            return PacketStatus.READY_WITH_CAUTION.value
        if score >= 8:
            return PacketStatus.REVISE_BEFORE_DELIVERY.value
        return PacketStatus.BLOCKED_NEEDS_REVISION.value


class EmployerAuditPacketBuilder:
    def __init__(self, project_root: Path, operator: str = "Justice Gray Maciocha"):
        self.project_root = project_root
        self.operator = operator
        self.redactor = Redactor()
        self.quality = QualityChecker()
        self.ledger = Phase7AuditLedger(project_root / "data" / "audit" / "aigc_phase7_audit.jsonl")

    def build_packet(
        self,
        phase6_receipt: Dict[str, Any],
        phase5_authorization: Dict[str, Any],
        phase4_proposal: Dict[str, Any],
        final_deliverable_content: str = "",
        final_deliverable_file_reference: str = "",
        sources_or_inputs: Optional[List[str]] = None,
    ) -> EmployerAuditPacket:
        sources_or_inputs = sources_or_inputs or []
        redacted_content = self.redactor.redact_text(final_deliverable_content)
        deliverable_hash = HashTools.hash_text(redacted_content)
        proposal_scope = phase4_proposal.get("scope_of_work", {}) or {}
        proposal_methodology = phase4_proposal.get("methodology", {}) or {}
        proposal_disclosure = phase4_proposal.get("ai_use_disclosure", {}) or {}
        proposal_risk = phase4_proposal.get("risk_notes", {}) or {}
        project = ProjectIdentity(
            task_title=phase4_proposal.get("title", ""),
            employer_or_client=phase4_proposal.get("employer", ""),
            platform=phase4_proposal.get("source_platform", ""),
            source_url=phase4_proposal.get("source_url", ""),
            opportunity_id=phase4_proposal.get("opportunity_id", ""),
        )
        linked = LinkedRecords(
            phase3_dossier_id=phase4_proposal.get("dossier_id", ""),
            phase4_proposal_id=phase4_proposal.get("proposal_id", ""),
            phase5_authorization_id=phase5_authorization.get("authorization_id", ""),
            phase6_execution_id=phase6_receipt.get("execution_id", ""),
            action_id=phase6_receipt.get("action_id", ""),
        )
        scope = ScopeOfWorkRecord(
            summary=proposal_scope.get("summary", ""),
            included_work=proposal_scope.get("included_work", []) or [],
            excluded_work=proposal_scope.get("excluded_work", []) or [],
            assumptions=proposal_scope.get("assumptions", []) or [],
            dependencies=proposal_scope.get("dependencies", []) or [],
        )
        methodology = MethodologySummary(
            work_phases=proposal_methodology.get("work_phases", []) or [
                "Requirement review",
                "Work preparation",
                "Quality review",
                "Final delivery preparation",
            ],
            tools_or_methods=proposal_methodology.get("tools_or_methods", []) or [
                "Structured workflow",
                "Human-reviewed AI-assisted support where allowed",
                "Quality-control checklist",
            ],
            quality_checks=proposal_methodology.get("quality_checks", []) or [
                "Scope alignment",
                "Completeness check",
                "Clarity check",
                "Privacy/security review",
                "Human review",
            ],
        )
        disclosure_language = proposal_disclosure.get("draft_language", "") or (
            "This work may have used AI-assisted tools for organization, drafting, analysis, "
            "coding support, summarization, or quality review. Final delivery was reviewed "
            "under human oversight before submission."
        )
        packet = EmployerAuditPacket(
            packet_id=self._make_packet_id(phase6_receipt, phase5_authorization, phase4_proposal),
            status=PacketStatus.INTERNAL_DRAFT_ONLY.value,
            created_at=utc_now(),
            operator=self.operator,
            project=project,
            linked_records=linked,
            scope_of_work=scope,
            deliverables=self._build_deliverables(phase4_proposal, deliverable_hash, final_deliverable_file_reference),
            methodology_summary=methodology,
            ai_assistance_disclosure=AIAssistanceDisclosure(
                included=True,
                language=self.redactor.redact_text(disclosure_language),
            ),
            human_approval_summary=HumanApprovalSummary(
                operator_reviewed=True,
                approval_required_before_external_action=True,
                approved_action_id=phase6_receipt.get("action_id", "") or phase5_authorization.get("action_id", ""),
                approval_timestamp=(phase5_authorization.get("approval", {}) or {}).get("approved_at", ""),
            ),
            execution_summary=ExecutionSummary(
                execution_mode=phase6_receipt.get("execution_mode", ""),
                execution_status=phase6_receipt.get("status", ""),
                confirmation_id=phase6_receipt.get("confirmation_id", ""),
                executed_at=phase6_receipt.get("executed_at", ""),
                artifact_hash=phase6_receipt.get("artifact_hash", ""),
            ),
            sources_or_inputs=[self.redactor.redact_text(item) for item in sources_or_inputs],
            assumptions=scope.assumptions,
            limitations=self._build_limitations(phase6_receipt, proposal_risk),
            privacy_security=PrivacySecurityRecord(
                secrets_redacted=True,
                private_data_redacted=True,
                credentials_included=False,
                notes=[
                    "No passwords, API keys, private tokens, or credentials are included.",
                    "Sensitive or unrelated private data is omitted or redacted where appropriate.",
                    "Raw internal logs are not included in this employer-facing packet.",
                ],
            ),
            revision_availability=RevisionAvailability(
                available=True,
                revision_types=["clarification", "formatting", "correction", "scope-aligned improvement"],
            ),
            acceptance_request=AcceptanceRequest(
                requested_response=[
                    "accepted",
                    "accepted_with_minor_revisions",
                    "revision_requested",
                    "clarification_requested",
                    "rejected_with_reason",
                ],
            ),
            quality_score=0,
            quality_notes=[],
            employer_facing_text="",
        )
        packet.employer_facing_text = self.redactor.redact_text(self._render_employer_facing_text(packet))
        score, notes = self.quality.score_packet(packet)
        packet.quality_score = score
        packet.quality_notes = notes
        packet.status = self.quality.status_from_score(score)
        self.ledger.record("phase7_employer_audit_packet_created", {
            "packet_id": packet.packet_id,
            "status": packet.status,
            "quality_score": packet.quality_score,
            "linked_records": asdict(packet.linked_records),
            "external_sharing_performed": False,
        })
        return packet

    def run_from_config(self, config_path: Path) -> List[EmployerAuditPacket]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        receipts = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase6_receipts", "")))
        authorizations = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase5_authorizations", "")))
        proposals = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase4_proposals", "")))
        confirmations = load_manual_handoff_confirmations(
            resolve_project_path(
                self.project_root,
                inputs.get(
                    "manual_handoff_confirmations",
                    "data/phase6_execution/aigc_phase6_manual_handoff_confirmations.jsonl",
                ),
            )
        )
        auth_by_id = {item.get("authorization_id", ""): item for item in authorizations}
        proposals_by_id = {item.get("proposal_id", ""): item for item in proposals}
        confirmations_by_execution_id: Dict[str, List[Dict[str, Any]]] = {}
        for confirmation in confirmations:
            execution_id = str(confirmation.get("execution_id", ""))
            if execution_id:
                confirmations_by_execution_id.setdefault(execution_id, []).append(
                    confirmation
                )
        packets: List[EmployerAuditPacket] = []
        for receipt in receipts:
            authorization = auth_by_id.get(receipt.get("authorization_id", ""), {})
            matching_confirmations = confirmations_by_execution_id.get(
                str(receipt.get("execution_id", "")),
                [],
            )
            confirmation = (
                matching_confirmations[0]
                if len(matching_confirmations) == 1
                else {}
            )
            if not manual_confirmation_matches_handoff(confirmation, receipt, authorization):
                self.ledger.record(
                    "phase7_audit_packet_blocked_pending_manual_confirmation",
                    {
                        "execution_id": receipt.get("execution_id", ""),
                        "authorization_id": receipt.get("authorization_id", ""),
                        "action_id": receipt.get("action_id", ""),
                        "external_sharing_performed": False,
                    },
                )
                continue
            proposal = proposals_by_id.get(receipt.get("proposal_id", ""), {})
            final_content = proposal.get("employer_facing_message", "")
            confirmed_receipt = {
                **receipt,
                "confirmation_id": confirmation.get("confirmation_id", ""),
                "executed_at": confirmation.get("confirmed_at", ""),
                "phase7_handoff_ready": True,
                "external_action_performed": True,
                "external_action_actor": "human_operator",
            }
            packet = self.build_packet(
                phase6_receipt=confirmed_receipt,
                phase5_authorization=authorization,
                phase4_proposal=proposal,
                final_deliverable_content=final_content,
                final_deliverable_file_reference="",
                sources_or_inputs=[proposal.get("source_url", "")] if proposal.get("source_url") else [],
            )
            packets.append(packet)
        output_path = resolve_project_path(self.project_root, config.get("output_file", "data/phase7_audit_packets/aigc_phase7_employer_audit_packets.json"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps([asdict(packet) for packet in packets], ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_dir = resolve_project_path(self.project_root, config.get("markdown_output_dir", "data/phase7_audit_packets"))
        markdown_dir.mkdir(parents=True, exist_ok=True)
        for packet in packets:
            (markdown_dir / f"{safe_filename(packet.packet_id)}.md").write_text(packet.employer_facing_text, encoding="utf-8")
        self.ledger.record("phase7_packets_exported", {"path": str(output_path), "records": len(packets)})
        report_path = self.project_root / "data" / "reports" / "phase7_signature_update.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            self.signature_update(packets, receipts, confirmations),
            encoding="utf-8",
        )
        return packets

    def _build_deliverables(
        self,
        phase4_proposal: Dict[str, Any],
        deliverable_hash: str,
        final_deliverable_file_reference: str,
    ) -> List[DeliverableRecord]:
        raw_deliverables = phase4_proposal.get("deliverables", []) or []
        deliverables: List[DeliverableRecord] = []
        for item in raw_deliverables:
            deliverables.append(DeliverableRecord(
                name=item.get("name", "Deliverable"),
                description=item.get("description", ""),
                format=item.get("format", "Employer-requested format"),
                acceptance_criteria=item.get("acceptance_criteria", []) or [],
                deliverable_hash=deliverable_hash,
                file_reference=final_deliverable_file_reference,
            ))
        if not deliverables:
            deliverables.append(DeliverableRecord(
                name=phase4_proposal.get("title", "Final Deliverable"),
                description="Final deliverable prepared according to the approved scope.",
                format="Employer-requested format",
                acceptance_criteria=["Matches approved scope", "Reviewed before delivery", "Provided in usable format"],
                deliverable_hash=deliverable_hash,
                file_reference=final_deliverable_file_reference,
            ))
        return deliverables

    def _build_limitations(self, phase6_receipt: Dict[str, Any], proposal_risk: Dict[str, Any]) -> List[str]:
        limitations: List[str] = []
        primary_risk = proposal_risk.get("primary_risk", "")
        if primary_risk:
            limitations.append(primary_risk)
        status = phase6_receipt.get("status", "")
        if status == "requires_manual_completion":
            limitations.append("External submission may require manual operator completion or confirmation.")
        if status == "dry_run_complete":
            limitations.append("This packet is based on a dry run; no external action was performed.")
        if not limitations:
            limitations.append("No major limitations identified beyond the approved scope and available inputs.")
        return [self.redactor.redact_text(item) for item in limitations]

    def _render_employer_facing_text(self, packet: EmployerAuditPacket) -> str:
        return f"""
AIGC EMPLOYER AUDIT PACKET
Project / Task:
{packet.project.task_title}
Prepared For:
{packet.project.employer_or_client}
Prepared By:
{packet.operator}
Date:
{packet.created_at}
Status:
{packet.status}
---
1. Scope of Work
{packet.scope_of_work.summary}
Included work:
{bullets(packet.scope_of_work.included_work)}
Excluded work:
{bullets(packet.scope_of_work.excluded_work)}
---
2. Deliverables
{deliverables_text(packet.deliverables)}
---
3. Methodology Summary
The work was prepared using the following general process:
{bullets(packet.methodology_summary.work_phases)}
---
4. AI-Assistance Disclosure
{packet.ai_assistance_disclosure.language}
---
5. Human Approval Summary
External action required human approval before execution.
Approved Action ID:
{packet.human_approval_summary.approved_action_id}
Approval Timestamp:
{packet.human_approval_summary.approval_timestamp}
---
6. Execution Summary
Execution Mode:
{packet.execution_summary.execution_mode}
Execution Status:
{packet.execution_summary.execution_status}
Confirmation ID:
{packet.execution_summary.confirmation_id}
Executed At:
{packet.execution_summary.executed_at}
Artifact Hash:
{packet.execution_summary.artifact_hash}
---
7. Quality Assurance Checks
{bullets(packet.methodology_summary.quality_checks)}
---
8. Sources / Inputs Used
{bullets(packet.sources_or_inputs) if packet.sources_or_inputs else "- No external sources listed or source list not applicable."}
---
9. Assumptions
{bullets(packet.assumptions)}
---
10. Limitations
{bullets(packet.limitations)}
---
11. Privacy and Security Handling
No passwords, API keys, private tokens, or credentials are included in this packet.
Sensitive or unrelated private information has been omitted or redacted where appropriate.
Raw internal logs are not included in this employer-facing packet.
---
12. Revision Availability
Revisions are available for clarification, formatting, correction, or scope-aligned improvement.
---
13. Acceptance Request
Please review the deliverable and confirm one of the following:
{bullets(packet.acceptance_request.requested_response)}
Prepared by:
{packet.operator}
""".strip()

    def _make_packet_id(
        self,
        phase6_receipt: Dict[str, Any],
        phase5_authorization: Dict[str, Any],
        phase4_proposal: Dict[str, Any],
    ) -> str:
        raw = "|".join([
            phase6_receipt.get("execution_id", ""),
            phase5_authorization.get("authorization_id", ""),
            phase4_proposal.get("proposal_id", ""),
            utc_now(),
        ])
        return "AIGC-PACKET-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:18].upper()

    def signature_update(
        self,
        packets: List[EmployerAuditPacket],
        receipts: Optional[List[Dict[str, Any]]] = None,
        confirmations: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        receipts = receipts or []
        confirmations = confirmations or []
        ready = [packet for packet in packets if packet.status == PacketStatus.READY_FOR_OPERATOR_REVIEW.value]
        caution = [packet for packet in packets if packet.status == PacketStatus.READY_WITH_CAUTION.value]
        revise = [packet for packet in packets if packet.status == PacketStatus.REVISE_BEFORE_DELIVERY.value]
        blocked = [packet for packet in packets if packet.status == PacketStatus.BLOCKED_NEEDS_REVISION.value]
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            self.operator,
            "Phase:",
            "Phase 7 - Employer Audit Packet",
            "Operational Identity:",
            "Transparent Delivery / Employer Review Layer",
            "Action Performed:",
            "Generated employer-safe internal audit packet drafts from Phase 6 receipts.",
            "Safety Review:",
            "No external sharing performed.",
            "No credentials exposed.",
            "No raw internal logs exposed.",
            "Secret-like patterns redacted.",
            f"Phase 6 Receipts Read: {len(receipts)}",
            f"Valid Manual Confirmations Read: {len(confirmations)}",
            f"Packets Created: {len(packets)}",
            f"Ready for Operator Review: {len(ready)}",
            f"Ready with Caution: {len(caution)}",
            f"Revise Before Delivery: {len(revise)}",
            f"Blocked Needs Revision: {len(blocked)}",
            "Approval Required:",
            "Yes, before externally sharing any employer audit packet unless already covered by the original approval scope.",
        ]).strip() + "\n"


def deliverables_text(deliverables: List[DeliverableRecord]) -> str:
    if not deliverables:
        return "- No deliverables listed."
    return "\n".join(
        "\n".join([
            f"- {item.name}",
            f"  Description: {item.description}",
            f"  Format: {item.format}",
            f"  Acceptance Criteria: {', '.join(item.acceptance_criteria) if item.acceptance_criteria else 'As agreed'}",
        ])
        for item in deliverables
    )


def bullets(items: List[str]) -> str:
    if not items:
        return "- Not specified."
    return "\n".join(f"- {item}" for item in items if item)


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "packet")


def load_json_dict(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_list_if_exists(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 7 employer audit packet generation.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase7_employer_audit_packet.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    builder = EmployerAuditPacketBuilder(project_root=args.project_root)
    packets = builder.run_from_config(args.config)
    receipts_path = args.project_root / "data" / "phase6_execution" / "aigc_phase6_execution_receipts.json"
    receipts = load_json_list_if_exists(receipts_path)
    confirmations_path = (
        args.project_root
        / "data"
        / "phase6_execution"
        / "aigc_phase6_manual_handoff_confirmations.jsonl"
    )
    print(
        builder.signature_update(
            packets,
            receipts,
            load_manual_handoff_confirmations(confirmations_path),
        )
    )
    print(f"\nPackets exported: {args.project_root / 'data' / 'phase7_audit_packets' / 'aigc_phase7_employer_audit_packets.json'}")
    print(f"Report exported: {args.project_root / 'data' / 'reports' / 'phase7_signature_update.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
