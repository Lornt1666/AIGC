from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agent_registry import build_agent_registry, build_workflow_plan, get_agent
from src.core.state_store import AIGCStateStore


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()

    if args.command == "list":
        registry = build_agent_registry()
        print(json.dumps({
            "agent_count": len(registry),
            "agents": [agent.to_dict() for _, agent in sorted(registry.items())],
            "external_actions_default": False,
        }, indent=2))
        return 0

    try:
        agent = get_agent(args.agent_id)
    except KeyError as exc:
        print(str(exc))
        return 2

    if args.command == "inspect":
        print(json.dumps(agent.to_dict(), indent=2))
        return 0

    # Read-only list/inspect commands must not create or initialize the runtime database.
    store = AIGCStateStore(args.state_db or root / "memory" / "aigc_state.sqlite")

    if agent.kind == "workflow_planner":
        try:
            plan = build_workflow_plan(agent, args.task or "")
        except ValueError as exc:
            print(str(exc))
            return 2
        if args.output:
            output_path = (root / args.output).resolve()
            if root not in output_path.parents:
                print("Agent output path must remain inside the configured project root.")
                return 2
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            plan["output_path"] = str(output_path)
        task_digest = hashlib.sha256((args.task or "").encode("utf-8")).hexdigest()
        store.insert_event(
            event_type="workflow_agent_plan_created",
            phase="agent_registry",
            status="plan_created",
            summary=f"Created a deterministic workflow plan with {agent.agent_id}.",
            data={"agent_id": agent.agent_id, "workflow": agent.workflow_path, "task_sha256": task_digest, "output_written": bool(args.output)},
            external_action_performed=False,
        )
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if store.emergency_stop_active() and agent.phase != "phase14":
        store.insert_event(
            event_type="agent_run_blocked_by_emergency_stop",
            phase="agent_registry",
            status="blocked",
            summary=f"Blocked agent {agent.agent_id} because emergency stop is active.",
            data={"agent_id": agent.agent_id, "phase": agent.phase},
            external_action_performed=False,
        )
        print("Emergency stop is active. Agent execution is blocked until clear-emergency-stop is run.")
        return 2

    store.insert_event(
        event_type="agent_run_started",
        phase="agent_registry",
        status="started",
        summary=f"Started governed phase adapter {agent.agent_id}.",
        data={"agent_id": agent.agent_id, "phase": agent.phase, "autonomy": agent.autonomy},
        external_action_performed=False,
    )
    phase_mode = args.mode
    if agent.phase == "phase13" and phase_mode == "real_data_read_only":
        phase_mode = "real"
    command = [
        sys.executable, str(root / "src" / "aigc.py"), "--root", str(root),
        "run", agent.phase, "--mode", phase_mode, "--source", args.source, "--limit", str(args.limit),
    ]
    if args.input:
        command.extend(["--input", str(args.input)])
    if args.artifact_root:
        command.extend(["--artifact-root", str(args.artifact_root)])
    if args.registry:
        command.extend(["--registry", str(args.registry)])
    if args.profile:
        command.extend(["--profile", str(args.profile)])
    completed = subprocess.run(command, cwd=root, check=False)
    store.insert_event(
        event_type="agent_run_completed" if completed.returncode == 0 else "agent_run_failed",
        phase="agent_registry",
        status="completed" if completed.returncode == 0 else "failed",
        summary=f"Governed phase adapter {agent.agent_id} exited with status {completed.returncode}.",
        data={"agent_id": agent.agent_id, "phase": agent.phase, "exit_code": completed.returncode},
        external_action_performed=False,
    )
    return completed.returncode


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC governed agent registry and dispatcher.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--state-db", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List all registered agents and their permission boundaries.")
    inspect_parser = subparsers.add_parser("inspect", help="Inspect one registered agent.")
    inspect_parser.add_argument("agent_id")
    run_parser = subparsers.add_parser("run", help="Run a governed phase adapter or create an engineering workflow plan.")
    run_parser.add_argument("agent_id")
    run_parser.add_argument("--task", default="", help="Required task text for engineering workflow planners.")
    run_parser.add_argument("--output", default="", help="Optional project-relative JSON path for a workflow plan.")
    run_parser.add_argument("--mode", choices=["synthetic", "real", "real_data_read_only"], default="synthetic")
    run_parser.add_argument("--source", choices=["remoteok", "remotive", "weworkremotely", "github_issues"], default="remoteok")
    run_parser.add_argument("--limit", type=int, default=10)
    run_parser.add_argument("--input", type=Path, default=None)
    run_parser.add_argument("--artifact-root", type=Path, default=None)
    run_parser.add_argument("--registry", type=Path, default=None)
    run_parser.add_argument("--profile", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
