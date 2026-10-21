"""Deterministic, offline ARCHON-GENESIS architecture compiler.

This is a bounded design-time compiler, not an unrestricted agent executor. It
validates a project brief and emits reproducible plans/prompts to a caller-chosen
output directory. It never calls models, networks, shells, repository APIs, or
deployment systems. Generated content is an untrusted proposal until reviewed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
POLICY_ID = "aigc-archon-genesis-v1"
STATUSES = {"PASS", "FAIL", "UNKNOWN", "BLOCK"}
EPISTEMIC_LABELS = {"FACT", "MEASUREMENT", "CALCULATION", "INFERENCE", "HYPOTHESIS", "ASSUMPTION", "SYNTHESIS"}
TOPOLOGIES = {"DAG", "HIERARCHICAL", "BLACKBOARD", "BOUNDED_MESH"}
RISK_CLASSES = {"low", "moderate", "high", "critical"}
MODES = {"observe", "simulate", "validate", "propose"}
REQUIRED_FIELDS = {
    "schema_version", "project_id", "objective", "constraints", "interfaces",
    "scale_reliability_target", "risk_class", "approval_policy", "requested_mode", "source_refs",
}
KNOWN_FIELDS = REQUIRED_FIELDS
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CompileError(ValueError):
    """Input contract or compilation failure."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompileError(f"{field} must be a non-empty string")
    return value.strip()


def validate_input(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise CompileError("input must be a JSON object")
    missing = sorted(REQUIRED_FIELDS - data.keys())
    unknown = sorted(data.keys() - KNOWN_FIELDS)
    if missing:
        raise CompileError("missing required fields: " + ", ".join(missing))
    if unknown:
        raise CompileError("unknown fields (schema is strict): " + ", ".join(unknown))
    if data["schema_version"] != SCHEMA_VERSION:
        raise CompileError(f"schema_version must equal {SCHEMA_VERSION}")
    _nonempty_string(data["project_id"], "project_id")
    _nonempty_string(data["objective"], "objective")
    if data["risk_class"] not in RISK_CLASSES:
        raise CompileError("risk_class must be one of: " + ", ".join(sorted(RISK_CLASSES)))
    if data["requested_mode"] not in MODES:
        raise CompileError("requested_mode must be one of: " + ", ".join(sorted(MODES)))
    for key in ("constraints", "scale_reliability_target", "approval_policy"):
        if not isinstance(data[key], dict):
            raise CompileError(f"{key} must be a JSON object; use explicit 'unknown' values")
    if not isinstance(data["interfaces"], list) or not all(isinstance(x, dict) for x in data["interfaces"]):
        raise CompileError("interfaces must be a list of objects")
    if not isinstance(data["source_refs"], list) or not all(isinstance(x, dict) for x in data["source_refs"]):
        raise CompileError("source_refs must be a list of objects")
    for i, interface in enumerate(data["interfaces"]):
        if not isinstance(interface.get("name"), str) or not interface["name"].strip():
            raise CompileError(f"interfaces[{i}].name is required")
        if interface.get("access", "unknown") not in {"read", "write", "execute", "unknown"}:
            raise CompileError(f"interfaces[{i}].access must be read, write, execute, or unknown")
    # Canonical JSON rejects NaN/Infinity and non-JSON values.
    try:
        json.loads(canonical_json(data))
    except (TypeError, ValueError) as exc:
        raise CompileError(f"input is not canonical JSON-compatible: {exc}") from exc
    return json.loads(canonical_json(data))


def compile_architecture(raw: Any) -> dict[str, Any]:
    brief = validate_input(raw)
    objective = brief["objective"].strip()
    risk = brief["risk_class"]
    mode = brief["requested_mode"]
    interfaces = brief["interfaces"]
    has_write_or_execute = any(x.get("access") in {"write", "execute"} for x in interfaces)

    # Deterministic minimum viable topology. This is a rule-based baseline, not
    # a claim that semantic planning or an LLM inference has occurred.
    topology = "HIERARCHICAL" if risk in {"high", "critical"} else "DAG"
    workstreams = [
        {"id": "WS-01", "name": "Objective and requirements", "purpose": "Normalize objective, constraints, acceptance criteria, and unknowns.", "depends_on": [], "acceptance": ["Required fields validated", "Unknowns and assumptions explicitly recorded"]},
        {"id": "WS-02", "name": "Architecture and interfaces", "purpose": "Define components, data contracts, trust boundaries, and dependency order.", "depends_on": ["WS-01"], "acceptance": ["Interfaces and ownership documented", "No implicit permissions granted"]},
        {"id": "WS-03", "name": "Implementation proposal", "purpose": "Produce a bounded, reviewable implementation plan and tests.", "depends_on": ["WS-02"], "acceptance": ["Changes are scoped and reproducible", "Automated tests are specified"]},
        {"id": "WS-04", "name": "Independent assurance", "purpose": "Evaluate contract conformance, failure modes, security, and evidence quality.", "depends_on": ["WS-02", "WS-03"], "acceptance": ["Author is not sole reviewer", "Findings are evidence-linked"]},
        {"id": "WS-05", "name": "Human acceptance and lifecycle", "purpose": "Present the proposal, unresolved risks, rollback plan, and next authorized step.", "depends_on": ["WS-04"], "acceptance": ["Explicit approval gate retained", "Release authority remains external and canonical"]},
    ]
    agents = [
        {"id": "ARCHON-01", "name": "ARCHON Compiler", "role": "Validate brief and compile deterministic architecture proposal", "owns": ["input validation", "workstream decomposition", "prompt and runbook generation"], "may": ["read supplied brief", "emit proposal artifacts"], "must_not": ["execute generated prompts", "grant permissions", "self-approve", "make release decisions"], "reviewer": "VERIFIER-01"},
        {"id": "DOMAIN-01", "name": "Implementation Planner", "role": "Propose scoped implementation tasks and acceptance tests", "owns": ["implementation plan", "test plan"], "may": ["produce proposed diffs and tests as text"], "must_not": ["write to external systems", "deploy", "merge"], "reviewer": "AER-01"},
        {"id": "AER-01", "name": "AER Assurance", "role": "Assess architecture, engineering, reliability, operations, and rollback", "owns": ["architecture review", "failure mode analysis", "operational readiness"], "may": ["review supplied artifacts", "report findings"], "must_not": ["be sole approver of its own authored change", "release"], "reviewer": "VERIFIER-01"},
        {"id": "RED-01", "name": "Red Team (synthetic)", "role": "Identify abuse cases and threat scenarios offline", "owns": ["threat model", "negative test proposals"], "may": ["analyze supplied text", "propose synthetic tests"], "must_not": ["perform live attacks", "access external targets", "exfiltrate data"], "reviewer": "BLUE-01"},
        {"id": "BLUE-01", "name": "Blue Team", "role": "Review prevention, detection, containment, and recovery controls", "owns": ["defensive control review", "monitoring and recovery checks"], "may": ["propose defensive checks"], "must_not": ["change production controls"], "reviewer": "AER-01"},
        {"id": "GREEN-01", "name": "Green Team", "role": "Propose minimal remediation for verified findings", "owns": ["remediation proposals"], "may": ["draft patches or remediation plans"], "must_not": ["apply changes", "merge", "self-approve remediation"], "reviewer": "AER-01"},
        {"id": "VERIFIER-01", "name": "Independent Contract Verifier", "role": "Check schema, deterministic outputs, separation of duties, and evidence completeness", "owns": ["contract validation", "independent findings"], "may": ["validate supplied artifacts"], "must_not": ["authenticate itself", "override canonical Release Assurance"], "reviewer": "Human approver"},
    ]
    # Any external write/execute interface raises a risk finding; it never
    # increases this compiler's permissions or changes its mode.
    findings = [
        {"id": "FMEA-01", "severity": "high", "failure": "Generated plan is mistaken for an authorized execution instruction", "effect": "Unreviewed changes or unsafe external actions", "mitigation": "Treat all output as proposal; enforce separate tool permits and human gates", "residual": "medium"},
        {"id": "FMEA-02", "severity": "high", "failure": "Evidence is stale, fabricated, or bound to another revision", "effect": "Incorrect assurance or release decision", "mitigation": "Bind evidence to exact commit/tree/policy and verify via an independent trusted verifier", "residual": "medium"},
        {"id": "FMEA-03", "severity": "medium", "failure": "Objective or constraints are incomplete", "effect": "Wrong decomposition or unrecognized requirements", "mitigation": "Record unknowns; require clarification before consequential action", "residual": "low"},
        {"id": "FMEA-04", "severity": "high" if has_write_or_execute else "medium", "failure": "Connected interface permits writes or execution", "effect": "Side effects exceed proposal scope", "mitigation": "This compiler never invokes interfaces; downstream execution requires scoped authorization", "residual": "medium"},
    ]
    epistemic_ledger = [
        {"label": "FACT", "statement": "The supplied brief contains the fields accepted by schema version 1.0.", "basis": "Input contract validation", "confidence": "high"},
        {"label": "SYNTHESIS", "statement": f"Proposed architecture for {brief['project_id']}: {objective}", "basis": "Deterministic rules and templates in this compiler", "confidence": "medium"},
        {"label": "ASSUMPTION", "statement": "Human review and the existing canonical Release Assurance remain required for consequential actions.", "basis": "AIGC governance policy", "confidence": "high"},
        {"label": "UNKNOWN", "statement": "Actual runtime behavior, external service state, and production readiness have not been measured by this offline compiler.", "basis": "No external calls or execution are performed", "confidence": "high"},
    ]
    if has_write_or_execute:
        epistemic_ledger.append({"label": "INFERENCE", "statement": "One or more declared interfaces may cause side effects and require a separately authorized execution boundary.", "basis": "Interface access declarations", "confidence": "medium"})
    prompts = {}
    for agent in agents:
        prompts[agent["id"]] = (
            f"You are {agent['name']} in AIGC. Role: {agent['role']}.\n"
            f"Owned outputs: {', '.join(agent['owns'])}.\n"
            f"Allowed: {', '.join(agent['may'])}.\n"
            f"Prohibited: {', '.join(agent['must_not'])}.\n"
            f"Required output: JSON with schema_version, agent_id, status (PASS/FAIL/UNKNOWN/BLOCK), "
            "inputs_reviewed, findings, evidence_refs, assumptions, and next_safe_step.\n"
            "Label claims FACT, MEASUREMENT, CALCULATION, INFERENCE, HYPOTHESIS, ASSUMPTION, or SYNTHESIS. "
            "Never invent evidence. If information is missing, return UNKNOWN or BLOCK. "
            "Do not grant permissions or make release decisions."
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "compiler": {"name": "ARCHON-GENESIS", "version": "0.1.0", "mode": "deterministic_offline"},
        "input_digest_sha256": digest(brief),
        "project": {"project_id": brief["project_id"], "objective": objective, "risk_class": risk, "requested_mode": mode},
        "status": "PASS" if mode in MODES else "BLOCK",
        "topology": {"type": topology, "rationale": "Rule-based baseline: high/critical risk gets explicit hierarchy; otherwise use a dependency DAG.", "alternatives_not_selected": ["BLACKBOARD", "BOUNDED_MESH"]},
        "workstreams": workstreams,
        "agents": agents,
        "system_prompts": prompts,
        "interfaces": interfaces,
        "fmea": findings,
        "epistemic_ledger": epistemic_ledger,
        "runbook": [
            "Review input digest and generated artifacts.",
            "Resolve UNKNOWNs and validate the objective with the project owner.",
            "Run unit, schema, security, and negative tests on the exact source revision.",
            "Have a reviewer independent of the author verify the change and evidence.",
            "Request explicit authorization before any external write, execution, merge, or deployment.",
            "Pass authenticated, exact-revision evidence to the existing canonical Release Assurance; this compiler does not decide releases.",
        ],
        "authority": {"release_decision_authority": "existing canonical Release Assurance only", "compiler_may_execute": False, "external_writes_performed": False, "self_approval_permitted": False},
        "disclaimer": "Deterministic proposal only; not a semantic AI planner, authenticated evidence producer, execution engine, or production-readiness certification.",
    }
    result["output_digest_sha256"] = digest(result)
    return result


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# ARCHON-GENESIS output: {result['project']['project_id']}", "",
        f"- Status: **{result['status']}**",
        f"- Compiler: {result['compiler']['name']} {result['compiler']['version']} (deterministic/offline)",
        f"- Input SHA-256: `{result['input_digest_sha256']}`",
        f"- Output SHA-256: `{result['output_digest_sha256']}`",
        f"- Topology: **{result['topology']['type']}**", "",
        "## Objective", "", result["project"]["objective"], "",
        "## Workstreams", "",
    ]
    for item in result["workstreams"]:
        lines += [f"### {item['id']} — {item['name']}", item["purpose"], f"Dependencies: {', '.join(item['depends_on']) or 'none'}", "Acceptance:"]
        lines += [f"- {x}" for x in item["acceptance"]]
        lines.append("")
    lines += ["## Agent roster", "", "| ID | Agent | Mandate | Reviewer |", "|---|---|---|---|"]
    for agent in result["agents"]:
        lines.append(f"| {agent['id']} | {agent['name']} | {agent['role']} | {agent['reviewer']} |")
    lines += ["", "## FMEA", ""]
    for item in result["fmea"]:
        lines.append(f"- **{item['id']} ({item['severity']}) — {item['failure']}** Effect: {item['effect']}. Mitigation: {item['mitigation']}.")
    lines += ["", "## Epistemic ledger", ""]
    for item in result["epistemic_ledger"]:
        lines.append(f"- **{item['label']}** — {item['statement']} (basis: {item['basis']}; confidence: {item['confidence']})")
    lines += ["", "## Runbook", ""]
    lines += [f"{i}. {step}" for i, step in enumerate(result["runbook"], 1)]
    lines += ["", "## Authority boundary", "", "The compiler did not execute agents, invoke external interfaces, write to external systems, or make a release decision.", "", result["disclaimer"], ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a deterministic ARCHON-GENESIS proposal from a strict JSON brief.")
    parser.add_argument("--input", required=True, help="Path to a project brief JSON file")
    parser.add_argument("--output-dir", required=True, help="Directory for generated proposal artifacts")
    args = parser.parse_args(argv)
    try:
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = compile_architecture(raw)
    except (OSError, json.JSONDecodeError, CompileError) as exc:
        parser.error(str(exc))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "archon_genesis_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "archon_genesis_report.md").write_text(render_markdown(result), encoding="utf-8")
    prompt_dir = output_dir / "prompts"
    prompt_dir.mkdir(exist_ok=True)
    for agent_id, prompt in result["system_prompts"].items():
        (prompt_dir / f"{agent_id.lower()}.txt").write_text(prompt + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "project_id": result["project"]["project_id"], "output_dir": str(output_dir), "input_digest_sha256": result["input_digest_sha256"], "output_digest_sha256": result["output_digest_sha256"], "agents": len(result["agents"]), "workstreams": len(result["workstreams"]), "external_writes_performed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
