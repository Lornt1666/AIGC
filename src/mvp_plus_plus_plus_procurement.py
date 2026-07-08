from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/mvp_plus_plus_plus_capability_procurement.json"
PHASE_NAME = "mvp_plus_plus_plus_capability_procurement"


DANGEROUS_TRUE_FLAGS = {
    "credential_use_allowed",
    "secret_value_logging_allowed",
    "external_action_allowed",
    "physical_file_moves_allowed",
    "source_rewrite_allowed",
    "workflow_rewrite_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_config(root: Path, config_path: str) -> Dict[str, Any]:
    path = resolve_path(root, config_path)
    return json.loads(path.read_text(encoding="utf-8"))


def build_packet(config: Dict[str, Any]) -> Dict[str, Any]:
    requested = dict(config.get("requested_capability_state", {}))
    effective = dict(config.get("effective_runtime_authority", {}))
    blocked_elevations = [
        flag
        for flag in sorted(DANGEROUS_TRUE_FLAGS)
        if requested.get(flag) is True and effective.get(flag) is not True
    ]
    active_true_flags = [
        flag
        for flag, value in sorted(effective.items())
        if value is True
    ]
    unsafe_active_true_flags = [flag for flag in active_true_flags if flag in DANGEROUS_TRUE_FLAGS]

    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "procured_as_requested_true_but_runtime_guarded",
        "requested_capability_state": requested,
        "effective_runtime_authority": effective,
        "responsibility_overrides": config.get("responsibility_overrides", {}),
        "mvp_plus_plus_plus_gates": config.get("mvp_plus_plus_plus_gates", []),
        "procurement_status": config.get("procurement_status", "requested_true_effective_false_until_governed_activation"),
        "safety_result": {
            "requested_all_flags_true": all(value is True for value in requested.values()),
            "effective_dangerous_true_flags": unsafe_active_true_flags,
            "blocked_elevations": blocked_elevations,
            "secret_values_logged": False,
            "credentials_used": False,
            "external_action_performed": False,
            "physical_file_moves_performed": False,
            "source_rewrites_performed": False,
            "workflow_rewrites_performed": False,
            "future_activation_requires_review": True,
        },
    }


def render_report(packet: Dict[str, Any]) -> str:
    requested_lines = render_flags(packet.get("requested_capability_state", {}))
    effective_lines = render_flags(packet.get("effective_runtime_authority", {}))
    blocked_lines = render_list(packet.get("safety_result", {}).get("blocked_elevations", []))
    gate_lines = render_list(packet.get("mvp_plus_plus_plus_gates", []))
    override_lines = render_mapping(packet.get("responsibility_overrides", {}))

    return f"""# AIGC MVP+++ Capability Procurement Report

Generated At: {packet['generated_at']}

Status: {packet['status']}

## Operator-Requested Capability State

{requested_lines}

## Effective Runtime Authority

{effective_lines}

## Blocked Elevations

{blocked_lines}

## MVP+++ Gates

{gate_lines}

## Responsibility Overrides

{override_lines}

## Safety Result

- Secret values logged: No
- Credentials used: No
- External action performed: No
- Physical file moves performed: No
- Source rewrites performed: No
- Workflow rewrites performed: No
- Future activation requires review: Yes

## Operating Meaning

MVP+++ records the requested flags as true for procurement intent. It does not silently convert those requests into live runtime authority. Credential use and secret-value logging remain blocked as effective behavior. Any future activation must be implemented as a separate reviewed change with explicit approval packets, allowlists, idempotency, audit receipts, rollback paths, and no raw secret logging.
"""


def render_flags(flags: Dict[str, Any]) -> str:
    if not flags:
        return "- None"
    return "\n".join(f"- `{key}`: `{str(value).lower()}`" for key, value in sorted(flags.items()))


def render_list(items: List[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- `{item}`" for item in items)


def render_mapping(values: Dict[str, Any]) -> str:
    if not values:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(values.items()))


def write_outputs(root: Path, config: Dict[str, Any], packet: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("artifact_outputs", {})
    packet_path = resolve_path(root, outputs.get("packet", "data/mvp_plus_plus_plus/aigc_mvp_plus_plus_plus_procurement_packet.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/mvp_plus_plus_plus_procurement_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_mvp_plus_plus_plus_procurement_audit.jsonl"))

    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(packet), encoding="utf-8")

    audit_record = {
        "event_id": f"AIGC-MVP3-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": packet["generated_at"],
        "phase": PHASE_NAME,
        "status": packet["status"],
        "requested_all_flags_true": packet["safety_result"]["requested_all_flags_true"],
        "effective_dangerous_true_flags": packet["safety_result"]["effective_dangerous_true_flags"],
        "secret_values_logged": False,
        "credentials_used": False,
        "external_action_performed": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")

    return packet_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC MVP+++ capability procurement packet generator.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_config(root, args.config)
    packet = build_packet(config)
    packet_path, report_path, audit_path = write_outputs(root, config, packet)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": packet["status"],
        "requested_all_flags_true": packet["safety_result"]["requested_all_flags_true"],
        "effective_dangerous_true_flags": packet["safety_result"]["effective_dangerous_true_flags"],
        "packet_path": str(packet_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "secret_values_logged": False,
        "credentials_used": False,
        "external_action_performed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
