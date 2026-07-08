from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_auto_approval_gates.json"
PHASE_NAME = "auto_approval_gate_procurement"


FORBIDDEN_REQUEST_TYPES = {
    "raw_secret_value_logging",
    "credential_exfiltration",
    "unscoped_external_action",
    "unapproved_identity_use",
    "bypass_human_approval",
    "delete_without_review",
    "payment_or_spend_without_approval",
    "live_message_send_without_approval",
}

DANGEROUS_AUTHORITY_FLAGS = {
    "external_action_allowed",
    "physical_file_moves_allowed",
    "source_rewrite_allowed",
    "workflow_rewrite_allowed",
    "credential_use_allowed",
    "secret_value_logging_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_json_if_exists(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(root: Path, config_path: str) -> Dict[str, Any]:
    return load_json_if_exists(resolve_path(root, config_path), {})


def build_gate_packet(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    inputs = config.get("inputs", {})
    input_status = {
        key: {
            "path": value,
            "found": resolve_path(root, value).exists(),
        }
        for key, value in inputs.items()
        if isinstance(value, str)
    }
    policy = config.get("policy", {})
    effective_authority = config.get("effective_runtime_authority", {})
    dangerous_true_flags = sorted(
        flag for flag in DANGEROUS_AUTHORITY_FLAGS if effective_authority.get(flag) is True
    )

    decisions = [decide_stage(stage, policy, dangerous_true_flags) for stage in config.get("stage_requests", [])]
    decision_counts = Counter(decision["decision"] for decision in decisions)
    risk_counts = Counter(decision["risk_level"] for decision in decisions)

    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_gate_procurement",
        "input_status": input_status,
        "effective_runtime_authority": effective_authority,
        "gate_invariants": config.get("gate_invariants", []),
        "summary": {
            "stage_requests_reviewed": len(decisions),
            "decision_counts": dict(sorted(decision_counts.items())),
            "risk_counts": dict(sorted(risk_counts.items())),
            "dangerous_authority_flags_true": dangerous_true_flags,
            "external_action_performed": False,
            "physical_file_moves_performed": False,
            "source_rewrites_performed": False,
            "workflow_rewrites_performed": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
        },
        "decisions": decisions,
    }


def decide_stage(stage: Dict[str, Any], policy: Dict[str, Any], dangerous_true_flags: List[str]) -> Dict[str, Any]:
    stage_id = str(stage.get("stage_id", "unknown_stage"))
    request_type = str(stage.get("request_type", "unknown_request"))
    risk_level = str(stage.get("risk_level", "unknown"))
    auto_pass_allowed = set(policy.get("auto_pass_allowed_for", []))
    human_review_required = set(policy.get("human_review_required_for", []))
    auto_deny = set(policy.get("auto_deny_for", [])) | FORBIDDEN_REQUEST_TYPES

    decision = str(policy.get("default_decision", "human_review_required"))
    reason = "Default gate decision applied."

    if request_type in auto_deny:
        decision = "auto_deny"
        reason = "Request type is categorically forbidden."
    elif request_type in human_review_required:
        decision = "human_review_required"
        reason = "Request type changes authority, secrets, credentials, external action, or repository behavior."
    elif request_type in auto_pass_allowed and not dangerous_true_flags:
        if risk_level in {"low", "medium"}:
            decision = "auto_pass_internal_only"
            reason = "Internal artifact or metadata stage with no dangerous effective authority enabled."
        else:
            decision = "human_review_required"
            reason = "High-risk stage cannot auto-pass even if request type is generally allowed."
    elif dangerous_true_flags:
        decision = "human_review_required"
        reason = "Dangerous effective authority flag is true, so auto-pass is suspended."

    return {
        "stage_id": stage_id,
        "request_type": request_type,
        "risk_level": risk_level,
        "description": stage.get("description", ""),
        "decision": decision,
        "reason": reason,
        "external_action_authorized": False,
        "physical_file_move_authorized": False,
        "source_rewrite_authorized": False,
        "workflow_rewrite_authorized": False,
        "credential_use_authorized": False,
        "secret_value_logging_authorized": False,
    }


def render_report(packet: Dict[str, Any]) -> str:
    summary = packet["summary"]
    decision_lines = render_counter(summary.get("decision_counts", {}))
    risk_lines = render_counter(summary.get("risk_counts", {}))
    input_lines = "\n".join(
        f"- `{key}`: {'found' if value.get('found') else 'missing'} at `{value.get('path')}`"
        for key, value in sorted(packet.get("input_status", {}).items())
    ) or "- None"
    decision_detail_lines = "\n".join(
        f"- `{decision['stage_id']}`: `{decision['decision']}` — {decision['reason']}"
        for decision in packet.get("decisions", [])
    ) or "- None"
    invariant_lines = render_list(packet.get("gate_invariants", []))

    return f"""# AIGC Auto-Approval Gate Procurement Report

Generated At: {packet['generated_at']}

Status: {packet['status']}

## Purpose

This packet procures an auto-approval gate layer for the AIGC pipeline. Auto-approval means automatic policy classification for low-risk internal stages, not automatic permission for dangerous actions.

## Input Status

{input_lines}

## Decision Counts

{decision_lines}

## Risk Counts

{risk_lines}

## Gate Decisions

{decision_detail_lines}

## Gate Invariants

{invariant_lines}

## Safety Result

- External action performed: No
- Physical file moves performed: No
- Source rewrites performed: No
- Workflow rewrites performed: No
- Credential use performed: No
- Secret values logged: No
- Dangerous effective authority flags true: {summary['dangerous_authority_flags_true']}

## Operating Rule

Auto-approval can pass only internal artifact generation and metadata classification stages. It cannot approve secret-value logging, credential use, external actions, identity use, file moves, source rewrites, or workflow rewrites.
"""


def render_counter(counter: Dict[str, int]) -> str:
    if not counter:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items()))


def render_list(items: List[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def write_outputs(root: Path, config: Dict[str, Any], packet: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    packet_path = resolve_path(root, outputs.get("packet", "data/auto_approval_gates/aigc_auto_approval_gate_packet.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/auto_approval_gate_procurement_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_auto_approval_gate_audit.jsonl"))

    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(packet), encoding="utf-8")

    audit_record = {
        "event_id": f"AIGC-AUTO-GATE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": packet["generated_at"],
        "phase": PHASE_NAME,
        "status": packet["status"],
        "stage_requests_reviewed": packet["summary"]["stage_requests_reviewed"],
        "decision_counts": packet["summary"]["decision_counts"],
        "external_action_performed": False,
        "credential_use_performed": False,
        "secret_values_logged": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")

    return packet_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC auto-approval gate procurement stage.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_config(root, args.config)
    packet = build_gate_packet(root, config)
    packet_path, report_path, audit_path = write_outputs(root, config, packet)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": packet["status"],
        "stage_requests_reviewed": packet["summary"]["stage_requests_reviewed"],
        "decision_counts": packet["summary"]["decision_counts"],
        "packet_path": str(packet_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "external_action_performed": False,
        "credential_use_performed": False,
        "secret_values_logged": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
