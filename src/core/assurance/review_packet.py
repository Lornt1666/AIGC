from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED_SECTIONS = (
    "executive_summary",
    "scope_and_intent",
    "constitutional_traceability",
    "architecture_diff",
    "contract_diff",
    "schema_diff",
    "testing_and_regression",
    "security_diff",
    "privacy_diff",
    "accessibility_diff",
    "readiness_impact",
    "rollback_plan",
    "reviewer_questions",
    "reviewer_decision_sheet",
    "evidence_appendix",
)


@dataclass(frozen=True)
class ReviewPacketResult:
    passed: bool
    packet: dict[str, Any]
    reason_codes: tuple[str, ...]


class ReviewPacketGenerator:
    """Builds deterministic, exact-head review packets from declared evidence.

    The generator prepares review material only. It cannot submit approvals,
    merge, deploy, publish externally, or infer reviewer identity.
    """

    def generate(
        self,
        *,
        packet_id: str,
        revision: str,
        sections: dict[str, Any],
        evidence_references: list[dict[str, Any]],
        gate_receipts: list[dict[str, Any]],
        suggested_review_minutes: int,
    ) -> ReviewPacketResult:
        reasons: list[str] = []
        if len(revision) < 7:
            reasons.append("INVALID_REVISION")
        missing = [name for name in REQUIRED_SECTIONS if name not in sections]
        if missing:
            reasons.append("MISSING_REQUIRED_SECTIONS")
        if not evidence_references:
            reasons.append("MISSING_EVIDENCE_REFERENCES")
        if not gate_receipts:
            reasons.append("MISSING_GATE_RECEIPTS")
        if suggested_review_minutes <= 0:
            reasons.append("INVALID_REVIEW_TIME")

        for evidence in evidence_references:
            payload = evidence.get("payload", {})
            if evidence.get("contract_type") != "evidence_reference":
                reasons.append("INVALID_EVIDENCE_CONTRACT")
            if payload.get("revision") != revision:
                reasons.append("STALE_EVIDENCE_REFERENCE")

        for receipt in gate_receipts:
            payload = receipt.get("payload", {})
            if receipt.get("contract_type") != "gate_receipt":
                reasons.append("INVALID_GATE_RECEIPT")
            if payload.get("revision") != revision:
                reasons.append("STALE_GATE_RECEIPT")

        packet = {
            "packet_id": packet_id,
            "revision": revision,
            "status": "invalid" if reasons else "review_ready",
            "suggested_review_minutes": suggested_review_minutes,
            "sections": sections,
            "evidence_references": evidence_references,
            "gate_receipts": gate_receipts,
            "authority_boundary": {
                "advisory_only": True,
                "independent_human_review_claimed": False,
                "external_action_performed": False,
            },
        }
        return ReviewPacketResult(not reasons, packet, tuple(sorted(set(reasons))))

    @staticmethod
    def render_markdown(packet: dict[str, Any]) -> str:
        lines = [
            f"# Review Packet {packet['packet_id']}",
            "",
            f"Revision: `{packet['revision']}`",
            f"Status: `{packet['status']}`",
            f"Suggested review time: {packet['suggested_review_minutes']} minutes",
            "",
        ]
        for name in REQUIRED_SECTIONS:
            title = name.replace("_", " ").title()
            lines.extend([f"## {title}", "", str(packet["sections"].get(name, "")), ""])
        return "\n".join(lines)
