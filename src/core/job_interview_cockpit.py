from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKET_PATH = Path("reports/artifacts/job_interview_cockpit/job_packets.json")

BLOCKED_ACTIONS = [
    "auto_apply",
    "auto_submit",
    "auto_message",
    "auto_schedule_interview",
    "auto_accept_offer",
    "credential_use",
    "platform_login",
    "form_submission",
    "external_contract_acceptance",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def packet_id(*parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    return "JOB-" + sha256(material.encode("utf-8")).hexdigest()[:20].upper()


def resolve_packet_path(root: Path, packet_path: Path = DEFAULT_PACKET_PATH) -> Path:
    return packet_path if packet_path.is_absolute() else root / packet_path


def load_job_packets(
    root: Path = PROJECT_ROOT,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[dict[str, Any]]:
    path = resolve_packet_path(root, packet_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list at {path}")
    return [dict(item) for item in payload if isinstance(item, Mapping)]


def write_job_packets(
    packets: list[dict[str, Any]],
    root: Path = PROJECT_ROOT,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> Path:
    path = resolve_packet_path(root, packet_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packets, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def prepare_job_packet(
    *,
    source_url: str,
    role_title: str,
    organization: str,
    posting_summary: str,
    truthful_qualifications: str,
    application_draft: str,
    interview_notes: str,
    root: Path = PROJECT_ROOT,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> dict[str, Any]:
    source_url = source_url.strip()
    role_title = role_title.strip()
    organization = organization.strip()
    posting_summary = posting_summary.strip()
    truthful_qualifications = truthful_qualifications.strip()
    application_draft = application_draft.strip()
    interview_notes = interview_notes.strip()
    if not source_url.startswith(("https://", "http://")):
        raise ValueError("source_url must be an HTTP or HTTPS URL")
    if not role_title or not organization or not posting_summary:
        raise ValueError("role title, organization, and posting summary are required")
    if not truthful_qualifications:
        raise ValueError("truthful qualifications are required; credentials may not be fabricated")

    created_at = utc_now()
    identifier = packet_id(source_url, role_title, organization, created_at)
    required_phrase = f"Accept job packet {identifier} for manual operator submission only"
    denial_phrase = f"Deny job packet {identifier}"
    packet = {
        "packet_id": identifier,
        "created_at": created_at,
        "source_url": source_url,
        "role_title": role_title,
        "organization": organization,
        "posting_summary": posting_summary,
        "truthful_qualifications": truthful_qualifications,
        "application_draft": application_draft or build_application_draft(
            role_title=role_title,
            organization=organization,
            truthful_qualifications=truthful_qualifications,
        ),
        "interview_notes": interview_notes or build_interview_notes(
            role_title=role_title,
            organization=organization,
            posting_summary=posting_summary,
            truthful_qualifications=truthful_qualifications,
        ),
        "decision": "PENDING_REVIEW",
        "interview_state": "NOT_RECORDED",
        "required_accept_phrase": required_phrase,
        "denial_phrase": denial_phrase,
        "operator_must_submit_on_official_platform": True,
        "operator_must_send_messages_manually": True,
        "operator_must_schedule_interview_manually": True,
        "blocked_actions": list(BLOCKED_ACTIONS),
        "external_action_performed": False,
    }
    packets = load_job_packets(root, packet_path)
    packets.append(packet)
    write_job_packets(packets, root, packet_path)
    return packet


def build_application_draft(
    *, role_title: str, organization: str, truthful_qualifications: str
) -> str:
    return (
        f"Dear Hiring Team at {organization},\n\n"
        f"I am applying for the {role_title} opportunity. My relevant qualifications are:\n"
        f"{truthful_qualifications.strip()}\n\n"
        "I would welcome the opportunity to discuss how these verified skills and experiences "
        "could support the role.\n\nSincerely,\nJustice Gray Maciocha"
    )


def build_interview_notes(
    *,
    role_title: str,
    organization: str,
    posting_summary: str,
    truthful_qualifications: str,
) -> str:
    return (
        f"Role: {role_title}\nOrganization: {organization}\n\n"
        f"Posting summary:\n{posting_summary.strip()}\n\n"
        f"Verified qualifications to discuss:\n{truthful_qualifications.strip()}\n\n"
        "Interview preparation:\n"
        "- Prepare two truthful examples demonstrating relevant work.\n"
        "- Clarify schedule, scope, deliverables, compensation, and reporting structure.\n"
        "- Ask how success is measured in the first 30, 60, and 90 days.\n"
        "- State uncertainties directly; do not invent credentials or completed work."
    )


def record_job_decision(
    packet_id_value: str,
    *,
    decision: str,
    phrase: str,
    root: Path = PROJECT_ROOT,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> dict[str, Any]:
    packets = load_job_packets(root, packet_path)
    target = next((item for item in packets if item.get("packet_id") == packet_id_value), None)
    if target is None:
        raise KeyError(f"Job packet not found: {packet_id_value}")
    if target.get("decision") != "PENDING_REVIEW":
        raise ValueError("Only pending job packets may receive a new decision")

    if decision == "ACCEPT_FOR_MANUAL_SUBMISSION":
        if phrase != target.get("required_accept_phrase"):
            raise ValueError("Acceptance phrase does not match the exact job packet phrase")
        target["decision"] = "APPROVED_FOR_MANUAL_OPERATOR_SUBMISSION"
    elif decision == "DENY":
        if phrase != target.get("denial_phrase"):
            raise ValueError("Denial phrase does not match the exact job packet phrase")
        target["decision"] = "DENIED"
    else:
        raise ValueError("Unsupported job packet decision")

    target["decision_recorded_at"] = utc_now()
    target["external_action_performed"] = False
    write_job_packets(packets, root, packet_path)
    return target


def record_interview_invitation(
    packet_id_value: str,
    *,
    invitation_notes: str,
    root: Path = PROJECT_ROOT,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> dict[str, Any]:
    packets = load_job_packets(root, packet_path)
    target = next((item for item in packets if item.get("packet_id") == packet_id_value), None)
    if target is None:
        raise KeyError(f"Job packet not found: {packet_id_value}")
    target["interview_state"] = "INVITATION_RECORDED_INTERNAL_ONLY"
    target["interview_invitation_notes"] = invitation_notes.strip()
    target["interview_recorded_at"] = utc_now()
    target["operator_must_schedule_interview_manually"] = True
    target["external_action_performed"] = False
    write_job_packets(packets, root, packet_path)
    return target
