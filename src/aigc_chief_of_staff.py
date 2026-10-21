"""AIGC Chief of Staff: deterministic, fail-closed agent orchestration.

Coordinates a dependency graph and invokes only the offline ARCHON compiler in
this initial release. Specialist agents receive explicit work orders; agents
that require real evidence remain BLOCKED until their contracts are satisfied.
No network, model, shell, repository mutation, deployment, or release operation
is performed by this coordinator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from archon_genesis import CompileError, canonical_json, compile_architecture, digest

SCHEMA_VERSION = "1.0"
POLICY_ID = "aigc-chief-of-staff-v1"

# Dependency edges encode the approved order. Independent assurance streams can
# run after architecture compilation, while remediation depends on findings.
STAGES = [
    {"id": "chief-of-staff", "name": "Chief of Staff intake and scope lock", "depends_on": [], "agent": "chief-of-staff", "mode": "local"},
    {"id": "archon-genesis", "name": "Compile architecture and agent contracts", "depends_on": ["chief-of-staff"], "agent": "ARCHON-GENESIS", "mode": "local"},
    {"id": "contract-gate", "name": "Validate schema, topology, authority, and deterministic output", "depends_on": ["archon-genesis"], "agent": "independent-contract-checker", "mode": "local"},
    {"id": "aer-review", "name": "Architecture, Engineering, and Reliability review", "depends_on": ["contract-gate"], "agent": "AER", "mode": "evidence-required"},
    {"id": "red-review", "name": "Synthetic threat and abuse-case review", "depends_on": ["contract-gate"], "agent": "Red Team", "mode": "synthetic-only"},
    {"id": "blue-review", "name": "Defensive controls, telemetry, and recovery review", "depends_on": ["contract-gate"], "agent": "Blue Team", "mode": "evidence-required"},
    {"id": "green-remediation", "name": "Draft minimal remediation proposals for verified findings", "depends_on": ["aer-review", "red-review", "blue-review"], "agent": "Green Team", "mode": "proposal-only"},
    {"id": "independent-verification", "name": "Verify evidence provenance, exact revision, and separation of duties", "depends_on": ["green-remediation"], "agent": "Independent Verifier", "mode": "trusted-verifier-required"},
    {"id": "human-acceptance", "name": "Human review and explicit acceptance of consequential changes", "depends_on": ["independent-verification"], "agent": "Authorized Human Reviewer", "mode": "approval-required"},
    {"id": "release-assurance", "name": "Evaluate release evidence", "depends_on": ["human-acceptance"], "agent": "Canonical Release Assurance", "mode": "canonical-authority-only"},
]

def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def validate_stage_graph(stages: list[dict[str, Any]] = STAGES) -> None:
    ids = [x.get("id") for x in stages]
    if any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("stage IDs must be unique non-empty strings")
    known = set(ids)
    visited: set[str] = set()
    visiting: set[str] = set()
    by_id = {x["id"]: x for x in stages}
    def visit(stage_id: str) -> None:
        if stage_id in visiting:
            raise ValueError("stage graph contains a dependency cycle")
        if stage_id in visited:
            return
        visiting.add(stage_id)
        for dep in by_id[stage_id].get("depends_on", []):
            if dep not in known:
                raise ValueError(f"unknown dependency {dep!r} in {stage_id}")
            visit(dep)
        visiting.remove(stage_id)
        visited.add(stage_id)
    for stage_id in ids:
        visit(stage_id)

def build_runbook(brief: Any) -> dict[str, Any]:
    validate_stage_graph()
    architecture = compile_architecture(brief)
    # Only stages that are actually executed in this first release receive
    # COMPLETE. The rest are explicit work orders with evidence/approval gates.
    work_orders = []
    for stage in STAGES:
        if stage["id"] == "chief-of-staff":
            status = "COMPLETE"
            detail = "Brief validated and orchestration scope locked."
        elif stage["id"] == "archon-genesis":
            status = "COMPLETE"
            detail = "Deterministic offline architecture proposal compiled."
        elif stage["id"] == "contract-gate":
            status = "PASS" if architecture.get("authority", {}).get("release_decision_authority") == "existing canonical Release Assurance only" and not architecture.get("authority", {}).get("compiler_may_execute") else "BLOCK"
            detail = "Static contract invariants checked by Chief of Staff." if status == "PASS" else "Authority boundary invariant failed."
        else:
            status = "BLOCKED_INPUTS"
            detail = "Not executed: requires real, revision-bound evidence, trusted integrations, or explicit human authorization."
        work_orders.append({
            "stage_id": stage["id"], "agent": stage["agent"], "name": stage["name"],
            "depends_on": stage["depends_on"], "mode": stage["mode"], "status": status,
            "detail": detail, "required_output": "Structured report with status, inputs reviewed, findings, evidence references, assumptions, and next safe step.",
        })
    final_status = "BLOCK" if any(x["status"] in {"BLOCK", "BLOCKED_INPUTS"} for x in work_orders) else "READY_FOR_REVIEW"
    result = {
        "schema_version": SCHEMA_VERSION, "policy_id": POLICY_ID,
        "coordinator": "AIGC Chief of Staff", "coordinator_version": "0.1.0",
        "project_id": architecture["project"]["project_id"],
        "input_digest_sha256": architecture["input_digest_sha256"],
        "architecture_output_digest_sha256": architecture["output_digest_sha256"],
        "status": final_status, "work_orders": work_orders,
        "next_safe_steps": [
            "Review the compiled ARCHON architecture and agent prompts.",
            "Collect architecture baseline, interface contracts, failure-mode review, observability baseline, rollback plan, measurable SLOs, and unresolved critical-risk inventory for AER.",
            "Generate only synthetic Red Team cases and attach content-addressed evidence; do not run live attacks.",
            "Provide timestamped telemetry and scenario outcomes to Blue Team; do not infer detection from configuration alone.",
            "Allow Green Team to draft proposals only after findings exist; require a reviewer different from the author.",
            "Configure and independently test a trusted cryptographic verifier before treating reports as authenticated.",
            "Require human acceptance and pass authenticated exact-commit/tree evidence to canonical Release Assurance.",
        ],
        "authority": {
            "chief_of_staff_may_schedule": True,
            "chief_of_staff_may_grant_permissions": False,
            "chief_of_staff_may_execute_external_actions": False,
            "chief_of_staff_may_merge_or_deploy": False,
            "release_decision_authority": "existing canonical Release Assurance only",
            "release_decision": "NOT_MADE",
        },
        "disclaimer": "This run executes intake, ARCHON compilation, and static contract checks only. Specialist work orders are not evidence that those agents ran. Release remains blocked until required real evidence and authorization are independently verified.",
    }
    result["runbook_digest_sha256"] = _sha(result)
    return result

def render_report(result: dict[str, Any]) -> str:
    lines = [
        f"# AIGC Chief of Staff Runbook — {result['project_id']}", "",
        f"- Status: **{result['status']}**",
        f"- Input SHA-256: `{result['input_digest_sha256']}`",
        f"- Architecture output SHA-256: `{result['architecture_output_digest_sha256']}`",
        f"- Runbook SHA-256: `{result['runbook_digest_sha256']}`", "",
        "## Ordered work queue", "",
        "| Order | Stage | Agent | Status | Dependency |",
        "|---:|---|---|---|---|",
    ]
    for i, item in enumerate(result["work_orders"], 1):
        lines.append(f"| {i} | {item['name']} | {item['agent']} | {item['status']} | {', '.join(item['depends_on']) or 'none'} |")
    lines += ["", "## Next safe steps", ""]
    lines += [f"{i}. {step}" for i, step in enumerate(result["next_safe_steps"], 1)]
    lines += ["", "## Authority boundary", "", result["disclaimer"], ""]
    return "\n".join(lines)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the bounded AIGC Chief of Staff orchestration cycle.")
    parser.add_argument("--input", required=True, help="Project brief JSON")
    parser.add_argument("--output-dir", required=True, help="Output directory for runbook artifacts")
    parser.add_argument("--evidence-envelope", help="Optional exact-version evidence envelope JSON; enables local specialist execution")
    parser.add_argument("--evidence-inputs", help="Optional specialist evidence inputs JSON; required with --evidence-envelope")
    args = parser.parse_args(argv)
    if bool(args.evidence_envelope) != bool(args.evidence_inputs):
        parser.error("--evidence-envelope and --evidence-inputs must be supplied together")
    try:
        brief = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = build_runbook(brief)
    except (OSError, json.JSONDecodeError, CompileError, ValueError) as exc:
        parser.error(str(exc))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "chief_of_staff_runbook.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "chief_of_staff_report.md").write_text(render_report(result), encoding="utf-8")
    execution_summary = None
    if args.evidence_envelope:
        try:
            from aigc_evidence_workflow import run_workflow
            envelope = json.loads(Path(args.evidence_envelope).read_text(encoding="utf-8"))
            evidence_inputs = json.loads(Path(args.evidence_inputs).read_text(encoding="utf-8"))
            execution_summary = run_workflow(envelope, evidence_inputs, out / "evidence_workflow")
            (out / "chief_of_staff_execution.json").write_text(
                json.dumps(execution_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            parser.error(str(exc))
    print(json.dumps({"status": result["status"], "project_id": result["project_id"], "work_orders": len(result["work_orders"]), "completed_stages": sum(x["status"] in {"COMPLETE", "PASS"} for x in result["work_orders"]), "blocked_input_stages": sum(x["status"] == "BLOCKED_INPUTS" for x in result["work_orders"]), "release_decision": execution_summary["release_decision"] if execution_summary else "NOT_MADE", "specialist_workflow_status": execution_summary["status"] if execution_summary else "NOT_RUN"}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
