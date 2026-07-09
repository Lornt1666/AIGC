from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import validate_artifact, validate_file


CONFIG_SCHEMA = "paycheque_workflow_config"
PIPELINE_SCHEMA = "paycheque_pipeline"

COMMIT_ACTIONS_BLOCKED = [
    "auto_apply",
    "auto_submit",
    "auto_accept",
    "auto_pay",
    "auto_purchase",
    "auto_deploy",
    "auto_use_credentials",
    "secret_logging",
    "self_approval",
    "platform_rule_bypass",
    "impersonation",
]

DASHBOARD_BUTTONS = [
    "ReviewDraft",
    "CopyText",
    "OpenPlatformLink",
    "MarkCompletedInternalOnly",
]


class PaychequeWorkflowError(ValueError):
    """Raised when the paycheque workflow is asked to cross a governance boundary."""


def prepare_paycheque_workflow(
    user_profile: Dict[str, Any],
    platforms: Iterable[Dict[str, Any]],
    pending_contracts: Iterable[Dict[str, Any]] | None = None,
    pending_payments: Iterable[Dict[str, Any]] | None = None,
    trigger: str = "GenerateDailyPipeline",
) -> Dict[str, Any]:
    """Prepare earning-oriented work without committing externally.

    The system may read approved/exported data, rank opportunities, draft copy,
    and build a dashboard payload. It must never submit, apply, accept, pay,
    purchase, deploy, use credentials, or self-approve.
    """
    actions: List[Dict[str, Any]] = []
    profile_summary = summarize_profile(user_profile)

    for platform in platforms:
        ensure_read_only_platform(platform)
        for opportunity in platform.get("opportunities", []):
            if not isinstance(opportunity, dict):
                continue
            actions.append(build_opportunity_action(user_profile, platform, opportunity))

    for contract in pending_contracts or []:
        if isinstance(contract, dict):
            actions.append(build_contract_action(user_profile, contract))

    for payment in pending_payments or []:
        if isinstance(payment, dict):
            actions.append(build_payment_action(user_profile, payment))

    ranked_actions = sorted(
        actions,
        key=lambda item: int(item.get("expected_payoff_score", 0)),
        reverse=True,
    )

    pipeline = {
        "pipeline_id": make_id("AIGC-PAY", trigger, profile_summary, utc_now()),
        "created_at": utc_now(),
        "mode": "internal_preparation_only",
        "trigger": trigger,
        "user_profile_summary": profile_summary,
        "actions": ranked_actions,
        "dashboard_buttons": DASHBOARD_BUTTONS,
        "audit_policy": {
            "read_only_collection": True,
            "draft_generation_internal_only": True,
            "integration_layer_prefill_only": True,
            "operator_must_click_platform_commit_buttons": True,
            "external_action_performed": False,
            "secret_values_logged": False,
            "self_approval_allowed": False,
        },
        "external_action_performed": False,
        "commit_actions_blocked": COMMIT_ACTIONS_BLOCKED,
    }
    validate_artifact(PIPELINE_SCHEMA, pipeline)
    return pipeline


def run_paycheque_workflow(
    project_root: Path,
    config_path: Path | None = None,
    artifact_root: Path | None = None,
    trigger: str = "GenerateDailyPipeline",
) -> Dict[str, Any]:
    project_root = project_root.resolve()
    config_path = resolve_project_path(project_root, config_path or project_root / "config" / "paycheque_workflow.json")
    artifact_root = resolve_project_path(project_root, artifact_root or project_root / "reports" / "artifacts" / "paycheque_pipeline")

    config = load_json_dict(config_path)
    validate_artifact(CONFIG_SCHEMA, config)
    enforce_constraints(config.get("constraints", {}))

    pipeline = prepare_paycheque_workflow(
        user_profile=dict(config.get("user_profile", {})),
        platforms=list(config.get("platforms", [])),
        pending_contracts=list(config.get("pending_contracts", [])),
        pending_payments=list(config.get("pending_payments", [])),
        trigger=trigger,
    )

    run_root = artifact_root / safe_path_name(pipeline["pipeline_id"])
    run_root.mkdir(parents=True, exist_ok=True)
    pipeline_path = run_root / "paycheque_pipeline.json"
    report_path = run_root / "paycheque_pipeline.md"
    audit_path = run_root / "paycheque_audit_receipt.json"

    write_json(pipeline_path, pipeline)
    validate_file(PIPELINE_SCHEMA, pipeline_path)

    report_path.write_text(render_pipeline_report(pipeline), encoding="utf-8")
    audit_receipt = build_audit_receipt(project_root, pipeline, pipeline_path, report_path)
    write_json(audit_path, audit_receipt)

    return {
        "pipeline": pipeline,
        "pipeline_path": relative_to_root(project_root, pipeline_path),
        "report_path": relative_to_root(project_root, report_path),
        "audit_receipt_path": relative_to_root(project_root, audit_path),
        "external_action_performed": False,
    }


def ensure_read_only_platform(platform: Dict[str, Any]) -> None:
    if not bool(platform.get("read_only", False)):
        raise PaychequeWorkflowError(f"Platform {platform.get('name', '<unknown>')} must be read-only.")
    source_type = str(platform.get("source_type", ""))
    allowed = {"local_export_or_approved_api", "local_export", "approved_api", "manual_entry"}
    if source_type not in allowed:
        raise PaychequeWorkflowError(f"Unsupported paycheque source type: {source_type}")


def enforce_constraints(constraints: Dict[str, Any]) -> None:
    for key in COMMIT_ACTIONS_BLOCKED:
        if bool(constraints.get(key, False)):
            raise PaychequeWorkflowError(f"Unsafe constraint enabled: {key}")
    if bool(constraints.get("external_action_performed", False)):
        raise PaychequeWorkflowError("Paycheque workflow cannot start from external_action_performed=true.")


def build_opportunity_action(
    user_profile: Dict[str, Any],
    platform: Dict[str, Any],
    opportunity: Dict[str, Any],
) -> Dict[str, Any]:
    title = str(opportunity.get("title", "Untitled opportunity"))
    platform_name = str(opportunity.get("platform") or platform.get("name", "Unknown platform"))
    score = int(opportunity.get("fit_score", 0) or 0)
    draft = draft_proposal(user_profile, opportunity)
    return build_action(
        action_id=str(opportunity.get("opportunity_id") or make_id("PAY-OPP", title, platform_name)),
        category="opportunity",
        title=title,
        platform=platform_name,
        platform_link=str(opportunity.get("url", "")),
        expected_payoff_score=score,
        rationale="High-fit opportunity prepared for manual review and manual platform submission.",
        prepared_text=draft,
        human_required_actions=[
            "Review draft",
            "Copy text",
            "Open platform link",
            "Paste manually",
            "Click platform Submit or Apply manually if appropriate",
            "Mark completed internally after the real-world action is done",
        ],
    )


def build_contract_action(user_profile: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    title = str(contract.get("title", "Untitled contract"))
    milestone = str(contract.get("milestone", "Review milestone and prepare next deliverable."))
    prepared = (
        f"Milestone preparation note for {title}:\n\n"
        f"- Milestone: {milestone}\n"
        "- Review deliverable evidence before platform submission.\n"
        "- Submit only manually through the official platform after operator review.\n"
        f"- Operator profile: {summarize_profile(user_profile)}"
    )
    return build_action(
        action_id=str(contract.get("contract_id") or make_id("PAY-CONTRACT", title)),
        category="contract",
        title=title,
        platform=str(contract.get("platform", "Manual Contract Tracker")),
        platform_link=str(contract.get("url", "")),
        expected_payoff_score=int(contract.get("fit_score", 0) or 0),
        rationale="Pending contract or milestone that can move closer to payment after manual review.",
        prepared_text=prepared,
        human_required_actions=[
            "Review work",
            "Open platform link",
            "Submit milestone manually if correct",
            "Mark completed internally after real submission",
        ],
    )


def build_payment_action(user_profile: Dict[str, Any], payment: Dict[str, Any]) -> Dict[str, Any]:
    title = str(payment.get("title", "Untitled payment item"))
    prepared = (
        f"Invoice/payment preparation note for {title}:\n\n"
        f"{payment.get('invoice_note', 'Draft invoice text only. Operator must review and send manually.')}\n\n"
        "Boundary: AIGC prepares text only. The operator must review, open the payment or invoice page, and send manually.\n"
        f"Operator profile: {summarize_profile(user_profile)}"
    )
    return build_action(
        action_id=str(payment.get("payment_id") or make_id("PAY-INVOICE", title)),
        category="payment",
        title=title,
        platform=str(payment.get("platform", "Manual Invoice Tracker")),
        platform_link=str(payment.get("url", "")),
        expected_payoff_score=int(payment.get("fit_score", 0) or 0),
        rationale="Payment-related reminder prepared for manual review and manual sending.",
        prepared_text=prepared,
        human_required_actions=[
            "Review invoice or payment note",
            "Copy text",
            "Open payment page manually",
            "Send or request payment manually if appropriate",
            "Mark completed internally after real action",
        ],
    )


def build_action(
    action_id: str,
    category: str,
    title: str,
    platform: str,
    platform_link: str,
    expected_payoff_score: int,
    rationale: str,
    prepared_text: str,
    human_required_actions: List[str],
) -> Dict[str, Any]:
    return {
        "action_id": action_id,
        "category": category,
        "title": title,
        "platform": platform,
        "platform_link": platform_link,
        "status": "prepared_internal_only",
        "expected_payoff_score": expected_payoff_score,
        "rationale": rationale,
        "buttons": {
            "review_draft": True,
            "copy_text": True,
            "open_platform_link": bool(platform_link),
            "mark_completed_internal_only": True,
            "submit_apply_accept_pay_deploy": False,
        },
        "prepared_text": prepared_text,
        "human_required_actions": human_required_actions,
        "blocked_external_commit_buttons": COMMIT_ACTIONS_BLOCKED,
        "external_action_performed": False,
        "automation_boundary": "AIGC prepares and pre-fills only. The operator must manually commit on the platform.",
    }


def draft_proposal(user_profile: Dict[str, Any], opportunity: Dict[str, Any]) -> str:
    name = str(user_profile.get("name", "the operator"))
    skills = ", ".join(str(item) for item in user_profile.get("skills", [])[:6])
    title = str(opportunity.get("title", "this opportunity"))
    description = str(opportunity.get("description", ""))
    return (
        f"Hello,\n\n"
        f"I can help with {title}. My relevant strengths include {skills}.\n\n"
        f"From the opportunity description, I understand the target as: {description}\n\n"
        "My proposed approach would be:\n"
        "1. Confirm the exact deliverable and acceptance criteria.\n"
        "2. Produce a clear first draft or prototype.\n"
        "3. Validate the result against the agreed requirements.\n"
        "4. Provide a concise handoff package with next steps.\n\n"
        "This message is a draft prepared internally by AIGC. I will review and submit manually if appropriate.\n\n"
        f"Regards,\n{name}"
    )


def summarize_profile(user_profile: Dict[str, Any]) -> str:
    name = str(user_profile.get("name", "Operator"))
    skills = ", ".join(str(item) for item in user_profile.get("skills", [])[:5]) or "general execution"
    return f"{name} | {skills}"


def build_audit_receipt(project_root: Path, pipeline: Dict[str, Any], pipeline_path: Path, report_path: Path) -> Dict[str, Any]:
    return {
        "receipt_id": make_id("AIGC-PAY-AUDIT", pipeline.get("pipeline_id", "")),
        "created_at": utc_now(),
        "pipeline_id": pipeline.get("pipeline_id", ""),
        "pipeline_path": relative_to_root(project_root, pipeline_path),
        "pipeline_sha256": sha256_file(pipeline_path),
        "report_path": relative_to_root(project_root, report_path),
        "report_sha256": sha256_file(report_path),
        "external_action_performed": False,
        "commit_actions_blocked": COMMIT_ACTIONS_BLOCKED,
        "operator_required_for_commit": True,
    }


def render_pipeline_report(pipeline: Dict[str, Any]) -> str:
    lines = [
        "# AIGC Paycheque Pipeline",
        "",
        f"Generated At: {pipeline['created_at']}",
        f"Pipeline ID: {pipeline['pipeline_id']}",
        f"Mode: {pipeline['mode']}",
        "External Action Performed: No",
        "",
        "## Dashboard Buttons",
    ]
    lines.extend(f"- {button}" for button in pipeline.get("dashboard_buttons", []))
    lines.extend([
        "",
        "## Highest-Impact Actions",
    ])
    for index, action in enumerate(pipeline.get("actions", []), start=1):
        lines.extend([
            f"### {index}. {action['title']}",
            f"- Category: {action['category']}",
            f"- Platform: {action['platform']}",
            f"- Expected Payoff Score: {action['expected_payoff_score']}",
            f"- Link: {action['platform_link'] or 'No link supplied'}",
            "- Boundary: Review, copy, open, and mark completed internally only. Commit manually on platform.",
            "",
            "Prepared Text:",
            "```text",
            action.get("prepared_text", ""),
            "```",
            "",
        ])
    lines.extend([
        "## Blocked Commit Actions",
        *[f"- {item}" for item in pipeline.get("commit_actions_blocked", [])],
    ])
    return "\n".join(lines) + "\n"


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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
