from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import validate_artifact, validate_file


SCHEMA_NAME = "chatlog_scoped_observer_access"


class ChatlogScopedObserverError(ValueError):
    """Raised when a chat-log observer packet would over-share or weaken security."""


def load_policy(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ChatlogScopedObserverError(f"Expected JSON object at {path}")
    validate_policy(payload)
    return payload


def validate_policy(policy: Dict[str, Any]) -> None:
    rules = dict(policy.get("default_scope_rules", {}))
    required_true = [
        "specific_chatlog_required",
        "exported_packet_required",
        "redaction_required",
        "operator_approval_required_before_invite",
        "observer_read_only",
        "observer_time_limited",
        "operator_can_revoke",
    ]
    for key in required_true:
        if rules.get(key) is not True:
            raise ChatlogScopedObserverError(f"default_scope_rules.{key} must be true")
    required_false = [
        "whole_account_access_allowed",
        "backend_access_allowed",
        "raw_chatgpt_link_sharing_allowed_by_default",
    ]
    for key in required_false:
        if rules.get(key) is not False:
            raise ChatlogScopedObserverError(f"default_scope_rules.{key} must be false")
    posture = dict(policy.get("security_posture", {}))
    if posture.get("deny_by_default") is not True:
        raise ChatlogScopedObserverError("security_posture.deny_by_default must be true")
    if posture.get("share_packet_not_backend") is not True:
        raise ChatlogScopedObserverError("security_posture.share_packet_not_backend must be true")
    if posture.get("crawler_indexing_allowed") is not False:
        raise ChatlogScopedObserverError("security_posture.crawler_indexing_allowed must be false")
    if posture.get("search_engine_discoverability_allowed") is not False:
        raise ChatlogScopedObserverError("security_posture.search_engine_discoverability_allowed must be false")


def build_chatlog_observer_packet(
    policy: Dict[str, Any],
    *,
    chatlog_artifact_id: str,
    chatlog_title: str,
    observer: Dict[str, Any],
    allowed_sections: Iterable[str],
    redaction_status: str = "pending_operator_review",
) -> Dict[str, Any]:
    validate_policy(policy)
    sections = [str(section) for section in allowed_sections if str(section).strip()]
    if not chatlog_artifact_id:
        raise ChatlogScopedObserverError("chatlog_artifact_id is required")
    if not sections:
        raise ChatlogScopedObserverError("At least one allowed chat-log section is required")
    if not observer.get("name"):
        raise ChatlogScopedObserverError("observer.name is required")
    if redaction_status not in {"pending_operator_review", "redacted_and_approved"}:
        raise ChatlogScopedObserverError("redaction_status must be pending_operator_review or redacted_and_approved")

    proceed_enabled = redaction_status == "redacted_and_approved"
    packet = {
        "packet_id": make_id("AIGC-CHATLOG-OBS", chatlog_artifact_id, observer.get("name", ""), utc_now()),
        "created_at": utc_now(),
        "mode": "specific_chatlog_observer_packet_only",
        "specific_chatlog_scope": {
            "chatlog_artifact_id": chatlog_artifact_id,
            "chatlog_title": chatlog_title,
            "allowed_sections": sections,
            "whole_conversation_access": False,
            "whole_account_access": False,
            "backend_access": False,
            "raw_chatgpt_link_shared": False,
            "exported_redacted_packet_only": True,
        },
        "observer": {
            "name": observer.get("name", ""),
            "organization": observer.get("organization", ""),
            "email": observer.get("email", ""),
            "role": observer.get("role", "employer_or_counterparty_observer"),
        },
        "visibility_controls": {
            "read_only": True,
            "time_limited": True,
            "revocable": True,
            "operator_approval_required_before_invite": True,
            "redaction_status": redaction_status,
            "proceed_enabled": proceed_enabled,
            "blocked_content": list(policy.get("hidden_or_private_content_blocks", [])),
        },
        "security_controls": {
            "least_privilege": True,
            "deny_by_default": True,
            "packet_hash": make_packet_hash(chatlog_artifact_id, chatlog_title, sections),
            "crawler_indexing_allowed": False,
            "search_engine_discoverability_allowed": False,
            "share_packet_not_backend": True,
            "audit_receipt_required": True,
            "watermark_or_identifier_required": True,
        },
        "sharing_state": {
            "invite_prepared": True,
            "invite_sent": False,
            "external_access_enabled": False,
            "operator_must_click_proceed": True,
            "backend_hardening_claimed": False,
            "note": "AIGC cannot harden ChatGPT backend infrastructure; it can only prepare scoped, redacted, least-privilege observer packets.",
        },
    }
    validate_artifact(SCHEMA_NAME, packet)
    return packet


def run_chatlog_observer_packet(
    project_root: Path,
    policy_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    policy_path = policy_path or root / "config" / "chatlog_scoped_observer_access.json"
    artifact_root = artifact_root or root / "reports" / "artifacts" / "chatlog_observer_access"
    policy = load_policy(policy_path)
    validate_file(SCHEMA_NAME.replace("chatlog_scoped_observer_access", "chatlog_scoped_observer_access"), root / "schemas" / "chatlog_scoped_observer_access.schema.json")

    packet = build_chatlog_observer_packet(
        policy,
        chatlog_artifact_id="AIGC-CHATLOG-EXAMPLE-001",
        chatlog_title="Example scoped AIGC work log",
        observer={"name": "Example Employer", "organization": "Example Org", "email": "employer@example.com"},
        allowed_sections=["counterparty_request_summary", "approved_deliverables", "approved_status_updates", "approved_audit_receipts"],
        redaction_status="pending_operator_review",
    )
    output_root = artifact_root / safe_path_name(packet["packet_id"])
    output_root.mkdir(parents=True, exist_ok=True)
    packet_path = output_root / "chatlog_scoped_observer_access.json"
    report_path = output_root / "chatlog_scoped_observer_access.md"
    write_json(packet_path, packet)
    validate_file(SCHEMA_NAME, packet_path)
    report_path.write_text(render_report(packet), encoding="utf-8")
    return {
        "packet": packet,
        "packet_path": relative_to_root(root, packet_path),
        "report_path": relative_to_root(root, report_path),
        "invite_sent": False,
        "external_access_enabled": False,
    }


def render_report(packet: Dict[str, Any]) -> str:
    return "\n".join([
        "# AIGC Chat-Log Scoped Observer Access Packet",
        "",
        f"Packet ID: {packet['packet_id']}",
        f"Created At: {packet['created_at']}",
        f"Chat-log Artifact: {packet['specific_chatlog_scope']['chatlog_artifact_id']}",
        f"Observer: {packet['observer']['name']}",
        "Invite Sent: No",
        "External Access Enabled: No",
        "Backend Access: No",
        "Raw ChatGPT Link Shared: No",
        "",
        "## Allowed Sections",
        *[f"- {item}" for item in packet["specific_chatlog_scope"].get("allowed_sections", [])],
        "",
        "## Security Boundary",
        "- Share an exported, redacted packet only.",
        "- Do not share backend access or whole-account access.",
        "- Do not expose hidden/system/developer/private content.",
        "- Operator approval is required before invite or sharing.",
    ]) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative_to_root(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def safe_path_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in str(value))[:96]


def make_packet_hash(chatlog_artifact_id: str, title: str, sections: Iterable[str]) -> str:
    return hashlib.sha256((chatlog_artifact_id + "|" + title + "|" + "|".join(sections)).encode("utf-8")).hexdigest()


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
