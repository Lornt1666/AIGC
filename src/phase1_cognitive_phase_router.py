from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_cognitive_phase_router.json"
PHASE_NAME = "phase1_cognitive_phase_router"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_config(root: Path, config_path: str) -> Dict[str, Any]:
    return json.loads(resolve_path(root, config_path).read_text(encoding="utf-8"))


def contains_trigger(trigger_text: str, trigger_phrase: str) -> bool:
    return trigger_phrase.lower() in trigger_text.lower()


def detect_intents(trigger_text: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    text = trigger_text.lower()
    detected: List[Dict[str, Any]] = []
    for rule in config.get("intent_rules", []):
        keywords = [str(keyword).lower() for keyword in rule.get("keywords", [])]
        matches = [keyword for keyword in keywords if keyword in text]
        if matches:
            detected.append({
                "intent": rule.get("intent", "unknown"),
                "matches": matches,
                "sequence": rule.get("sequence", []),
            })
    return detected


def choose_sequence(
    *,
    trigger_text: str,
    project_profile: str,
    run_mode: str,
    config: Dict[str, Any],
    detected_intents: List[Dict[str, Any]],
) -> Tuple[str, List[str], List[str]]:
    reasons: List[str] = []

    if project_profile != "auto":
        for rule in config.get("intent_rules", []):
            if rule.get("intent") == project_profile:
                reasons.append(f"project_profile:{project_profile}")
                return project_profile, list(rule.get("sequence", [])), reasons

    if run_mode == "safe_sweep":
        reasons.append("run_mode:safe_sweep")
        return "safe_sweep", list(config.get("safe_sweep_sequence", [])), reasons

    if run_mode == "project_pipeline":
        reasons.append("run_mode:project_pipeline")
        return "project_pipeline", list(config.get("project_pipeline_sequence", [])), reasons

    if detected_intents:
        # Merge detected intent sequences in the order they appear, preserving first occurrence.
        merged: List[str] = []
        for intent in detected_intents:
            reasons.append(f"intent:{intent['intent']} keywords:{','.join(intent['matches'])}")
            for phase_id in intent.get("sequence", []):
                if phase_id not in merged:
                    merged.append(phase_id)
        return "+".join(intent["intent"] for intent in detected_intents), merged, reasons

    reasons.append("default:artifact_generation")
    return "artifact_generation", list(config.get("artifact_generation_sequence", [])), reasons


def build_phase_index(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("id")): item for item in config.get("phase_slots", []) if isinstance(item, dict)}


def build_plan(
    *,
    root: Path,
    config: Dict[str, Any],
    trigger_text: str,
    project_profile: str,
    run_mode: str,
) -> Dict[str, Any]:
    trigger_phrase = str(config.get("trigger_phrase", "AIGC"))
    trigger_found = contains_trigger(trigger_text, trigger_phrase)
    detected_intents = detect_intents(trigger_text, config)
    selected_profile, sequence, reasons = choose_sequence(
        trigger_text=trigger_text,
        project_profile=project_profile,
        run_mode=run_mode,
        config=config,
        detected_intents=detected_intents,
    )
    phase_index = build_phase_index(config)
    script_commands = config.get("script_commands", {})
    safety_doctrine = config.get("safety_doctrine", {})

    steps: List[Dict[str, Any]] = []
    for order, phase_id in enumerate(sequence, start=1):
        phase_meta = phase_index.get(phase_id, {})
        command_template = script_commands.get(phase_id)
        autonomous_allowed = bool(phase_meta.get("autonomous_execution_allowed", phase_id in script_commands))
        if phase_id in script_commands:
            autonomous_allowed = True
        step_status = "planned"
        if not command_template:
            step_status = "planned_not_executable_by_workflow"
        if not autonomous_allowed:
            step_status = "requires_review_or_manual_gate"
        if phase_id == "phase6" and not safety_doctrine.get("external_action_allowed", False):
            step_status = "blocked_external_action_not_allowed"

        steps.append({
            "order": order,
            "phase_id": phase_id,
            "slot": phase_meta.get("slot", None),
            "name": phase_meta.get("name", phase_id),
            "category": phase_meta.get("category", "support"),
            "status": step_status,
            "autonomous_execution_allowed": autonomous_allowed and step_status == "planned",
            "command_available": bool(command_template),
            "command_template": command_template or [],
            "requires_human_review": step_status != "planned",
        })

    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "planned" if trigger_found else "blocked_no_aigc_trigger",
        "trigger": {
            "phrase": trigger_phrase,
            "detected": trigger_found,
            "raw_text_stored": False,
            "trigger_text_sha256": stable_hash(trigger_text),
        },
        "project_profile": project_profile,
        "run_mode": run_mode,
        "selected_profile": selected_profile,
        "detected_intents": detected_intents,
        "selection_reasons": reasons,
        "safety_doctrine": safety_doctrine,
        "summary": {
            "phase_slots_available": len(config.get("phase_slots", [])),
            "planned_steps": len(steps),
            "workflow_executable_steps": sum(1 for step in steps if step["autonomous_execution_allowed"]),
            "review_or_manual_steps": sum(1 for step in steps if step["requires_human_review"]),
            "external_action_allowed": bool(safety_doctrine.get("external_action_allowed", False)),
            "physical_file_moves_allowed": bool(safety_doctrine.get("physical_file_moves_allowed", False)),
            "credential_use_allowed": bool(safety_doctrine.get("credential_use_allowed", False)),
            "secret_value_logging_allowed": bool(safety_doctrine.get("secret_value_logging_allowed", False)),
        },
        "steps": steps,
    }


def render_report(plan: Dict[str, Any]) -> str:
    steps = "\n".join(
        f"| {step['order']} | `{step['phase_id']}` | {step['name']} | {step['status']} | {step['autonomous_execution_allowed']} |"
        for step in plan.get("steps", [])
    ) or "| - | - | - | - | - |"
    reasons = "\n".join(f"- {reason}" for reason in plan.get("selection_reasons", [])) or "- None"
    return f"""# AIGC Phase 1 Cognitive Phase Router Report

Generated At: {plan['generated_at']}

Status: {plan['status']}

Trigger Detected: {plan['trigger']['detected']}

Selected Profile: {plan['selected_profile']}

Run Mode: {plan['run_mode']}

## Selection Reasons

{reasons}

## Planned Steps

| Order | Phase | Name | Status | Workflow Executable |
|---:|---|---|---|---|
{steps}

## Safety Boundary

This router reasons about phases 1-26 and emits a plan. It does not grant credentials, reveal secrets, perform external actions, move files, rewrite source, or rewrite workflows. Executable steps are limited to configured safe artifact-generation commands.
"""


def write_outputs(root: Path, config: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    plan_path = resolve_path(root, outputs.get("plan", "data/phase1_cognitive_router/aigc_phase1_cognitive_plan.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/phase1_cognitive_router_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_phase1_cognitive_router_audit.jsonl"))
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(plan), encoding="utf-8")
    audit_record = {
        "event_id": f"AIGC-P1-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": plan["generated_at"],
        "phase": PHASE_NAME,
        "status": plan["status"],
        "trigger_detected": plan["trigger"]["detected"],
        "selected_profile": plan["selected_profile"],
        "planned_steps": plan["summary"]["planned_steps"],
        "workflow_executable_steps": plan["summary"]["workflow_executable_steps"],
        "external_action_performed": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")
    return plan_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC cognitive phase router.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--trigger-text", default="AIGC")
    parser.add_argument("--project-profile", default="auto")
    parser.add_argument("--run-mode", default="artifact_generation")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_config(root, args.config)
    allowed_modes = set(config.get("allowed_run_modes", []))
    run_mode = args.run_mode if args.run_mode in allowed_modes else config.get("default_run_mode", "artifact_generation")
    plan = build_plan(
        root=root,
        config=config,
        trigger_text=args.trigger_text,
        project_profile=args.project_profile,
        run_mode=run_mode,
    )
    plan_path, report_path, audit_path = write_outputs(root, config, plan)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": plan["status"],
        "trigger_detected": plan["trigger"]["detected"],
        "selected_profile": plan["selected_profile"],
        "planned_steps": plan["summary"]["planned_steps"],
        "workflow_executable_steps": plan["summary"]["workflow_executable_steps"],
        "plan_path": str(plan_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "external_action_performed": False,
    }, indent=2))
    return 0 if plan["trigger"]["detected"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
