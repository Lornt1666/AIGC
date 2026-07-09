from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.core.contract_validator import validate_artifact, validate_file


REQUEST_SCHEMA = "counterparty_request_packet"
REVIEW_SCHEMA = "counterparty_acceptance_review"

REQUIRED_SUMMARY_FIELDS = [
    "counterparty.name",
    "requested_action",
    "work_description.summary",
    "work_description.success_outcome",
    "deliverables",
    "acceptance_criteria",
    "terms.compensation",
    "terms.contract_obligations",
    "timeline.requested_deadline",
]

HIGH_RISK_ACCEPTANCE_ACTIONS = {"accept", "bid", "submit", "deliver_work", "pay", "purchase", "deploy"}

HARD_BLOCK_PHRASES = [
    "bypass platform rules",
    "fake credential",
    "fabricate credential",
    "misrepresent",
    "use credentials without approval",
    "self approve",
]


class CounterpartyRequestError(ValueError):
    """Raised when counterparty intake data is unsafe or malformed."""


def run_counterparty_request_intake(
    project_root: Path,
    request_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    project_root = project_root.resolve()
    request_path = resolve_project_path(project_root, request_path or project_root / "config" / "counterparty_request_example.json")
    artifact_root = resolve_project_path(project_root, artifact_root or project_root / "reports" / "artifacts" / "counterparty_request_intake")

    request = load_json_dict(request_path)
    validate_artifact(REQUEST_SCHEMA, request)
    validate_request_safety(request)
    review = build_acceptance_review(request)

    run_root = artifact_root / safe_path_name(review["review_id"])
    run_root.mkdir(parents=True, exist_ok=True)
    request_out = run_root / "counterparty_request_packet.json"
    review_out = run_root / "counterparty_acceptance_review.json"
    report_out = run_root / "counterparty_acceptance_review.md"

    write_json(request_out, request)
    write_json(review_out, review)
    report_out.write_text(render_review_report(request, review), encoding="utf-8")

    validate_file(REQUEST_SCHEMA, request_out)
    validate_file(REVIEW_SCHEMA, review_out)

    return {
        "request": request,
        "review": review,
        "request_path": relative_to_root(project_root, request_out),
        "review_path": relative_to_root(project_root, review_out),
        "report_path": relative_to_root(project_root, report_out),
        "external_action_performed": False,
    }


def build_acceptance_review(request: Dict[str, Any]) -> Dict[str, Any]:
    missing = find_missing_information(request)
    risks = find_risk_flags(request)
    action = str(request.get("requested_action", ""))
    high_risk = action in HIGH_RISK_ACCEPTANCE_ACTIONS

    if risks:
        decision_state = "blocked_pending_risk_review"
        proceed_enabled = False
    elif missing:
        decision_state = "insufficient_information"
        proceed_enabled = False
    elif high_risk:
        decision_state = "ready_for_operator_popup_high_risk"
        proceed_enabled = True
    else:
        decision_state = "ready_for_operator_popup"
        proceed_enabled = True

    review = {
        "review_id": make_id("AIGC-COUNTERPARTY-REVIEW", request.get("request_id", ""), utc_now()),
        "created_at": utc_now(),
        "request_id": request.get("request_id", ""),
        "decision_state": decision_state,
        "proceed_enabled": proceed_enabled,
        "operator_popup_required": True,
        "required_clarifications": missing,
        "risk_flags": risks,
        "visible_acceptance_summary": build_visible_summary(request),
        "external_action_performed": False,
    }
    validate_artifact(REVIEW_SCHEMA, review)
    return review


def find_missing_information(request: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for field in REQUIRED_SUMMARY_FIELDS:
        value = nested_get(request, field)
        if value in (None, "", [], {}):
            missing.append(field)
        elif isinstance(value, str) and value.strip().lower() in {"unknown", "not agreed", "not agreed yet", "tbd", "to be determined"}:
            missing.append(field)
    return missing


def find_risk_flags(request: Dict[str, Any]) -> List[str]:
    blob = json.dumps(request, ensure_ascii=False).lower()
    flags: List[str] = []
    for phrase in HARD_BLOCK_PHRASES:
        if phrase in blob:
            flags.append(f"hard-block phrase detected: {phrase}")
    if request.get("external_action_performed") is not False:
        flags.append("external_action_performed must be false at intake")
    if request.get("operator_review_required") is not True:
        flags.append("operator_review_required must be true")
    return flags


def build_visible_summary(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "counterparty": request.get("counterparty", {}),
        "requested_action": request.get("requested_action", ""),
        "work_summary": request.get("work_description", {}).get("summary", ""),
        "success_outcome": request.get("work_description", {}).get("success_outcome", ""),
        "deliverables": request.get("deliverables", []),
        "acceptance_criteria": request.get("acceptance_criteria", []),
        "terms": request.get("terms", {}),
        "timeline": request.get("timeline", {}),
        "constraints": request.get("constraints", []),
        "attachments": request.get("attachments", []),
        "communication_history": request.get("communication_history", []),
    }


def validate_request_safety(request: Dict[str, Any]) -> None:
    if request.get("external_action_performed") is not False:
        raise CounterpartyRequestError("Counterparty intake cannot start from external_action_performed=true.")
    if request.get("operator_review_required") is not True:
        raise CounterpartyRequestError("Counterparty intake requires operator_review_required=true.")


def render_review_report(request: Dict[str, Any], review: Dict[str, Any]) -> str:
    summary = review.get("visible_acceptance_summary", {})
    lines = [
        "# AIGC Counterparty Acceptance Review",
        "",
        f"Request ID: {request.get('request_id', '')}",
        f"Review ID: {review.get('review_id', '')}",
        f"Decision State: {review.get('decision_state', '')}",
        f"Proceed Enabled: {review.get('proceed_enabled')}",
        "External Action Performed: No",
        "",
        "## Counterparty",
        json.dumps(summary.get("counterparty", {}), indent=2),
        "",
        "## Requested Action",
        str(summary.get("requested_action", "")),
        "",
        "## Work Description",
        str(summary.get("work_summary", "")),
        "",
        "## Success Outcome",
        str(summary.get("success_outcome", "")),
        "",
        "## Deliverables",
    ]
    for deliverable in summary.get("deliverables", []):
        lines.append(f"- {deliverable.get('title', deliverable)}")
    lines.extend(["", "## Acceptance Criteria"])
    lines.extend(f"- {item}" for item in summary.get("acceptance_criteria", []))
    lines.extend(["", "## Terms", json.dumps(summary.get("terms", {}), indent=2)])
    lines.extend(["", "## Timeline", json.dumps(summary.get("timeline", {}), indent=2)])
    lines.extend(["", "## Required Clarifications"])
    lines.extend(f"- {item}" for item in review.get("required_clarifications", []) or ["None"])
    lines.extend(["", "## Risk Flags"])
    lines.extend(f"- {item}" for item in review.get("risk_flags", []) or ["None"])
    lines.extend([
        "",
        "## Operator Rule",
        "Do not accept, bid, submit, pay, purchase, deploy, message, or deliver externally until this review is complete and the operator has seen the exact acceptance summary.",
    ])
    return "\n".join(lines) + "\n"


def nested_get(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


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
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in str(value))[:96]


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
