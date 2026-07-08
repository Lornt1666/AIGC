from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_phase_interleave_scheduler.json"
PHASE_NAME = "phase_interleave_scheduler"


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


def normalize_phase_id(value: str) -> str:
    text = str(value).strip().lower()
    if text.startswith("phase"):
        return text
    if text.isdigit():
        return f"phase{text}"
    return text


def load_phase1_plan(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    plan_path = resolve_path(root, config.get("inputs", {}).get("phase1_plan", ""))
    return load_json_if_exists(plan_path, {})


def extract_base_sequence(phase1_plan: Dict[str, Any]) -> List[str]:
    candidates = [
        phase1_plan.get("selected_sequence"),
        phase1_plan.get("execution_sequence"),
        phase1_plan.get("planned_sequence"),
        phase1_plan.get("phase_sequence"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return [normalize_phase_id(item) for item in candidate]
    plan_items = phase1_plan.get("plan")
    if isinstance(plan_items, list) and plan_items:
        sequence = []
        for item in plan_items:
            if isinstance(item, dict):
                value = item.get("phase") or item.get("phase_id") or item.get("id")
                if value:
                    sequence.append(normalize_phase_id(value))
            elif isinstance(item, str):
                sequence.append(normalize_phase_id(item))
        if sequence:
            return sequence
    return [
        "phase1",
        "phase2",
        "phase3",
        "phase4",
        "phase5",
        "phase6",
        "phase7",
        "phase8",
        "phase9",
        "phase10",
        "phase11",
        "phase12",
        "phase13",
        "phase14",
        "phase15",
        "phase16",
        "phase17",
        "phase18",
        "phase19",
        "phase20",
        "phase21",
        "phase22",
        "phase23",
        "phase24",
        "mvp_plus_plus_plus",
        "phase25",
        "phase26",
    ]


def extract_intents(phase1_plan: Dict[str, Any]) -> List[str]:
    values = []
    for key in ["detected_intents", "intents", "selected_intents"]:
        candidate = phase1_plan.get(key)
        if isinstance(candidate, list):
            values.extend(str(item) for item in candidate)
        elif isinstance(candidate, str):
            values.append(candidate)
    selected = phase1_plan.get("selected_profile") or phase1_plan.get("project_profile")
    if selected:
        values.append(str(selected))
    return sorted(set(value.strip().lower() for value in values if value))


def phase_slot(phase_id: str) -> int:
    if phase_id == "mvp_plus_plus_plus":
        return 24
    if phase_id.startswith("phase"):
        suffix = phase_id.removeprefix("phase")
        if suffix.isdigit():
            return int(suffix)
    return 0


def make_occurrence(
    *,
    phase_id: str,
    role: str,
    anchor: str,
    reason: str,
    index: int,
    auto_executable: bool = False,
) -> Dict[str, Any]:
    return {
        "occurrence_id": f"{phase_id}@{role}:{anchor}:{index}",
        "phase_id": phase_id,
        "phase_slot": phase_slot(phase_id),
        "role": role,
        "anchor_phase": anchor,
        "reason": reason,
        "auto_executable_in_workflow": auto_executable,
        "external_action_allowed": False,
        "physical_file_moves_allowed": False,
        "source_rewrite_allowed": False,
        "workflow_rewrite_allowed": False,
        "credential_use_allowed": False,
        "secret_value_logging_allowed": False,
    }


def build_schedule(config: Dict[str, Any], phase1_plan: Dict[str, Any]) -> Dict[str, Any]:
    base_sequence = extract_base_sequence(phase1_plan)
    intents = extract_intents(phase1_plan)
    before = config.get("always_insert_before", {})
    after = config.get("always_insert_after", {})
    guard_meanings = config.get("guard_phase_meanings", {})

    schedule: List[Dict[str, Any]] = []
    index = 1

    for phase_id in base_sequence:
        for guard in before.get(phase_id, []):
            reason = f"Guard before {phase_id}: {guard_meanings.get(guard, 'configured guard phase')}"
            schedule.append(make_occurrence(phase_id=guard, role="before", anchor=phase_id, reason=reason, index=index))
            index += 1

        schedule.append(
            make_occurrence(
                phase_id=phase_id,
                role="primary",
                anchor=phase_id,
                reason="Primary phase occurrence from selected base sequence.",
                index=index,
                auto_executable=phase_id in {"phase1", "phase25", "phase26", "mvp_plus_plus_plus"},
            )
        )
        index += 1

        for guard in after.get(phase_id, []):
            reason = f"Loop after {phase_id}: {guard_meanings.get(guard, 'configured follow-up phase')}"
            schedule.append(make_occurrence(phase_id=guard, role="after", anchor=phase_id, reason=reason, index=index))
            index += 1

    schedule, index = add_triggered_interleaves(config, schedule, intents, index)
    counts = Counter(item["phase_id"] for item in schedule)
    repeated = {phase: count for phase, count in sorted(counts.items()) if count > 1}
    role_counts = Counter(item["role"] for item in schedule)

    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_interleaved_plan",
        "intents": intents,
        "base_sequence": base_sequence,
        "safety_doctrine": config.get("safety_doctrine", {}),
        "summary": {
            "base_sequence_length": len(base_sequence),
            "interleaved_occurrences": len(schedule),
            "unique_phases": len(counts),
            "repeated_phases": repeated,
            "role_counts": dict(sorted(role_counts.items())),
            "external_action_performed": False,
            "physical_file_moves_performed": False,
            "source_rewrites_performed": False,
            "workflow_rewrites_performed": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
        },
        "schedule": schedule,
    }


def add_triggered_interleaves(
    config: Dict[str, Any],
    schedule: List[Dict[str, Any]],
    intents: List[str],
    index: int,
) -> Tuple[List[Dict[str, Any]], int]:
    if not intents:
        return schedule, index
    triggered = config.get("triggered_interleaves", [])
    intent_text = " ".join(intents)
    additions: List[Dict[str, Any]] = []
    for rule in triggered:
        needle = str(rule.get("when_intent_contains", "")).lower()
        if not needle or needle not in intent_text:
            continue
        for anchor in rule.get("insert_before_each", []):
            for guard in rule.get("insert_phases", []):
                additions.append(
                    make_occurrence(
                        phase_id=guard,
                        role="intent_before",
                        anchor=anchor,
                        reason=f"Intent-triggered guard before {anchor} for intent {needle}.",
                        index=index,
                    )
                )
                index += 1
        for anchor in rule.get("insert_after_each", []):
            for guard in rule.get("insert_phases", []):
                additions.append(
                    make_occurrence(
                        phase_id=guard,
                        role="intent_after",
                        anchor=anchor,
                        reason=f"Intent-triggered loop after {anchor} for intent {needle}.",
                        index=index,
                    )
                )
                index += 1
    return schedule + additions, index


def render_report(plan: Dict[str, Any]) -> str:
    summary = plan["summary"]
    repeated_lines = render_counter(summary.get("repeated_phases", {}))
    role_lines = render_counter(summary.get("role_counts", {}))
    preview_lines = "\n".join(
        f"- `{item['occurrence_id']}` -> `{item['phase_id']}` ({item['reason']})"
        for item in plan.get("schedule", [])[:40]
    ) or "- None"
    return f"""# AIGC Phase Interleave Scheduler Report

Generated At: {plan['generated_at']}

Status: {plan['status']}

## Purpose

This report turns the 1-through-26 phase continuum into an interleaved schedule. Phases can recur as guards, reviews, audits, quality checks, approval gates, security checks, observability loops, and evolution loops between numbered phases.

## Summary

- Base sequence length: {summary['base_sequence_length']}
- Interleaved occurrences: {summary['interleaved_occurrences']}
- Unique phases: {summary['unique_phases']}

## Repeated Phases

{repeated_lines}

## Role Counts

{role_lines}

## Schedule Preview

{preview_lines}

## Safety Boundary

The scheduler emits a plan only. It performs no external action, file movement, source rewrite, workflow rewrite, credential use, or secret logging.
"""


def render_counter(counter: Dict[str, int]) -> str:
    if not counter:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items()))


def write_outputs(root: Path, config: Dict[str, Any], schedule: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    schedule_path = resolve_path(root, outputs.get("schedule", "data/phase_interleaves/aigc_phase_interleave_schedule.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/phase_interleave_scheduler_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_phase_interleave_scheduler_audit.jsonl"))

    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    schedule_path.write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(schedule), encoding="utf-8")

    audit_record = {
        "event_id": f"AIGC-INTERLEAVE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": schedule["generated_at"],
        "phase": PHASE_NAME,
        "status": schedule["status"],
        "base_sequence_length": schedule["summary"]["base_sequence_length"],
        "interleaved_occurrences": schedule["summary"]["interleaved_occurrences"],
        "external_action_performed": False,
        "credential_use_performed": False,
        "secret_values_logged": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")

    return schedule_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC phase interleave scheduler.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_config(root, args.config)
    phase1_plan = load_phase1_plan(root, config)
    schedule = build_schedule(config, phase1_plan)
    schedule_path, report_path, audit_path = write_outputs(root, config, schedule)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": schedule["status"],
        "base_sequence_length": schedule["summary"]["base_sequence_length"],
        "interleaved_occurrences": schedule["summary"]["interleaved_occurrences"],
        "schedule_path": str(schedule_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "external_action_performed": False,
        "credential_use_performed": False,
        "secret_values_logged": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
