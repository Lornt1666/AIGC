from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.contract_validator import validate_artifact  # noqa: E402
from src.core.workbench_isolation import create_parallel_workbench, export_workbench_manifest  # noqa: E402
from src.orchestration.dry_run_executor import run_workflow_dry_run, write_dry_run_report  # noqa: E402
from src.orchestration.event_contracts import create_orchestration_event  # noqa: E402
from src.orchestration.gateway import assert_n8n_templates_safe, validate_n8n_templates  # noqa: E402
from src.orchestration.workflow_registry import list_workflows, workflow_registry_payload  # noqa: E402


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    if args.command == "list-workflows":
        print(json.dumps(workflow_registry_payload(), indent=2))
        return 0
    if args.command == "emit-fixture-event":
        event = create_orchestration_event(
            args.event_type,
            workflow_execution_id="AIGC-WORKFLOW-FIXTURE",
            work_order_id=args.work_order_id,
            payload={"fixture": True, "no_external_action": True},
        )
        print(json.dumps(event, indent=2))
        return 0
    if args.command == "dry-run":
        result = run_workflow_dry_run(args.workflow, work_order_id=args.work_order_id)
        report_path = write_dry_run_report(result, root)
        print(json.dumps({"report_path": str(report_path), **asdict(result)}, indent=2))
        return 0
    if args.command == "validate-n8n-templates":
        results = validate_n8n_templates(root)
        print(json.dumps([asdict(result) for result in results], indent=2))
        return 1 if any(not result.valid for result in results) else 0
    if args.command == "workbench-smoke":
        workspaces = create_parallel_workbench(
            tenant_id=args.tenant_id,
            work_order_ids=[f"WORK-ORDER-{index:02d}" for index in range(1, args.count + 1)],
        )
        manifest = export_workbench_manifest(workspaces)
        print(json.dumps(manifest, indent=2))
        return 0
    if args.command == "orchestration-smoke":
        result = orchestration_smoke(root)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "PASS" else 1
    raise ValueError(f"Unhandled command: {args.command}")


def orchestration_smoke(root: Path) -> Dict[str, Any]:
    workflows = list_workflows()
    for workflow in workflows:
        validate_artifact("workflow_candidate", workflow.to_dict())
    template_results = assert_n8n_templates_safe(root)
    intake = run_workflow_dry_run("intake_to_work_order")
    regression = run_workflow_dry_run("regression_guard_check")
    delivery = run_workflow_dry_run("delivery_draft")
    workspaces = create_parallel_workbench(
        tenant_id="OWNER-LOCAL",
        work_order_ids=[f"WORK-ORDER-{index:02d}" for index in range(1, 11)],
    )
    manifest = export_workbench_manifest(workspaces)
    checks = {
        "workflow_registry_load": len(workflows) == 6,
        "template_validation": all(result.valid for result in template_results),
        "intake_emits_work_order": any(event["event_type"] == "work_order.created" for event in intake.events),
        "regression_emits_status": any(event["event_type"] == "regression_guard.passed" for event in regression.events),
        "delivery_stops_before_external_action": delivery.workflow_execution["external_action_performed"] is False
        and any(event["external_action_performed"] == "blocked" for event in delivery.events),
        "approval_boundary": all(workflow.external_action_allowed is False for workflow in workflows),
        "workbench_ten_jobs_isolated": manifest["workspace_count"] == 10
        and manifest["cross_workspace_mutable_state_allowed"] is False,
        "no_external_action": all(
            result.external_action_performed is False for result in [intake, regression, delivery]
        )
        and manifest["external_action_performed"] is False,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "workflow_count": len(workflows),
        "template_count": len(template_results),
        "workspace_count": manifest["workspace_count"],
        "external_action_performed": False,
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC local dry-run orchestration CLI.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-workflows")

    event_parser = subparsers.add_parser("emit-fixture-event")
    event_parser.add_argument("--event-type", default="work_order.created")
    event_parser.add_argument("--work-order-id", default="WORK-ORDER-FIXTURE")

    dry_run_parser = subparsers.add_parser("dry-run")
    dry_run_parser.add_argument("--workflow", required=True)
    dry_run_parser.add_argument("--work-order-id", default="WORK-ORDER-FIXTURE")

    subparsers.add_parser("validate-n8n-templates")

    workbench_parser = subparsers.add_parser("workbench-smoke")
    workbench_parser.add_argument("--tenant-id", default="OWNER-LOCAL")
    workbench_parser.add_argument("--count", type=int, default=10)

    subparsers.add_parser("orchestration-smoke")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
