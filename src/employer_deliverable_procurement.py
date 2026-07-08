from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_employer_deliverable_procurement.json"
PHASE_NAME = "employer_deliverable_procurement"


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


def collect_inputs(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    collected: Dict[str, Any] = {}
    for key, value in config.get("inputs", {}).items():
        if not isinstance(value, str):
            continue
        path = resolve_path(root, value)
        collected[key] = {
            "path": value,
            "found": path.exists(),
            "payload": load_json_if_exists(path, {}) if path.suffix == ".json" else {},
        }
    return collected


def collect_text_signal(inputs: Dict[str, Any]) -> str:
    parts: List[str] = []
    for entry in inputs.values():
        payload = entry.get("payload", {})
        if isinstance(payload, dict):
            parts.append(json.dumps(payload, ensure_ascii=False)[:8000])
        elif isinstance(payload, list):
            parts.append(json.dumps(payload[:20], ensure_ascii=False))
    return " ".join(parts).lower()


def recognize_discipline(config: Dict[str, Any], text_signal: str) -> Dict[str, Any]:
    scores: Dict[str, int] = {}
    agents_by_discipline: Dict[str, List[str]] = {}
    for item in config.get("occupational_taxonomy", []):
        discipline = item.get("discipline", "generalist_delivery")
        keywords = [str(keyword).lower() for keyword in item.get("keywords", [])]
        score = sum(1 for keyword in keywords if keyword in text_signal)
        scores[discipline] = score
        agents_by_discipline[discipline] = item.get("agents", [])
    if not scores or max(scores.values()) == 0:
        return {
            "primary_discipline": "generalist_delivery",
            "discipline_scores": scores,
            "recognition_confidence": "low_default_generalist",
            "selected_agents": [
                "requirements_analyst",
                "domain_researcher",
                "methodology_engineer",
                "data_quality_reviewer",
                "submission_writer",
                "fidelity_reviewer",
            ],
        }
    primary = max(scores, key=scores.get)
    confidence = "high" if scores[primary] >= 4 else "medium" if scores[primary] >= 2 else "low"
    return {
        "primary_discipline": primary,
        "discipline_scores": dict(sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))),
        "recognition_confidence": confidence,
        "selected_agents": agents_by_discipline.get(primary, []),
    }


def build_agent_constellation(agents: List[str], ology_stack: List[str]) -> List[Dict[str, Any]]:
    if not agents:
        agents = ["requirements_analyst", "domain_researcher", "submission_writer", "fidelity_reviewer"]
    constellation = []
    for index, agent in enumerate(agents, start=1):
        lenses = ology_stack[:7] if index <= 3 else ology_stack[7:]
        constellation.append(
            {
                "agent_id": agent,
                "rank": index,
                "mission": agent.replace("_", " ").title(),
                "required_lenses": lenses,
                "output": "reviewable contribution to employer deliverable packet",
            }
        )
    return constellation


def build_ology_plan(ology_stack: List[str], discipline: str) -> List[Dict[str, str]]:
    return [
        {
            "ology": ology,
            "application": f"Apply {ology.replace('_', ' ')} to the {discipline.replace('_', ' ')} project so the final submission has structured reasoning, evidence, value, constraints, quality controls, and employer relevance.",
        }
        for ology in ology_stack
    ]


def build_data_analytics_plan(discipline: str) -> Dict[str, Any]:
    return {
        "discipline": discipline,
        "analytics_modes": [
            "requirements scoring",
            "acceptance criteria traceability",
            "evidence completeness scoring",
            "risk and uncertainty register",
            "quality rubric scoring",
            "comparative best-practice benchmarking",
            "submission readiness scoring",
        ],
        "metrics": [
            "requirements_fit",
            "evidence_depth",
            "domain_quality",
            "clarity",
            "risk_control",
            "differentiated_value",
            "submission_readiness",
        ],
        "rule": "Use analytics to improve the deliverable and state uncertainty; never fabricate certainty or guarantee employer payment.",
    }


def build_practices_plan(discipline: str) -> Dict[str, Any]:
    return {
        "discipline": discipline,
        "best_practices": [
            "clarify employer requirements and acceptance criteria",
            "use verifiable evidence and cite sources when available",
            "separate assumptions from confirmed facts",
            "show method, constraints, risks, and quality checks",
            "deliver in an employer-readable format",
        ],
        "emerging_practices": [
            "agent-role decomposition",
            "traceable artifact generation",
            "metacognitive self-review",
            "interleaved verification and governance loops",
            "submission-readiness scoring",
        ],
    }


def build_deliverable_sections(sections: List[str]) -> List[Dict[str, str]]:
    return [
        {
            "section_id": section,
            "status": "planned_reviewable_content",
            "instruction": f"Prepare {section.replace('_', ' ')} for the employer-facing deliverable. Do not publish internal phase maps unless explicitly approved.",
        }
        for section in sections
    ]


def score_readiness(input_status: Dict[str, Any], discipline: Dict[str, Any], rubric: Dict[str, int]) -> Dict[str, Any]:
    found_count = sum(1 for value in input_status.values() if value.get("found"))
    total_count = max(len(input_status), 1)
    evidence_completeness = round(found_count / total_count, 3)
    confidence = discipline.get("recognition_confidence", "low")
    confidence_bonus = {"high": 30, "medium": 20, "low": 10, "low_default_generalist": 5}.get(str(confidence), 5)
    score = min(100, int(evidence_completeness * 50) + confidence_bonus + min(20, len(rubric)))
    return {
        "readiness_score": score,
        "evidence_completeness": evidence_completeness,
        "recognition_confidence": confidence,
        "recommended_decision": "ready_for_human_final_review" if score >= 85 else "human_review_before_submission",
        "employer_submission_allowed_now": False,
        "reason": "This packet prepares a high-quality employer submission package, but external submission requires explicit human approval through the submission cockpit.",
    }


def build_packet(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    inputs = collect_inputs(root, config)
    text_signal = collect_text_signal(inputs)
    discipline = recognize_discipline(config, text_signal)
    ology_stack = config.get("ology_stack", [])
    rubric = config.get("quality_rubric", {})
    input_status = {key: {"path": value.get("path"), "found": value.get("found", False)} for key, value in inputs.items()}
    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_reviewable_employer_procurement_packet",
        "input_status": input_status,
        "missing_inputs": [key for key, value in input_status.items() if not value.get("found")],
        "publication_policy": config.get("publication_policy", {}),
        "occupational_discipline_recognition": discipline,
        "agent_constellation": build_agent_constellation(discipline.get("selected_agents", []), ology_stack),
        "ology_research_plan": build_ology_plan(ology_stack, discipline.get("primary_discipline", "generalist_delivery")),
        "data_analytics_coordination": build_data_analytics_plan(discipline.get("primary_discipline", "generalist_delivery")),
        "best_and_emerging_practices": build_practices_plan(discipline.get("primary_discipline", "generalist_delivery")),
        "deliverable_sections": build_deliverable_sections(config.get("deliverable_sections", [])),
        "quality_rubric": rubric,
        "submission_readiness": score_readiness(input_status, discipline, rubric),
        "safety_result": {
            "auto_submitted_to_employer": False,
            "external_action_performed": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
            "pay_outcome_guaranteed": False,
            "human_review_required_before_submission": True,
            "phase_map_published_to_employer": bool(config.get("publication_policy", {}).get("publish_phase_map_artifact_to_employer", False)),
        },
    }


def render_report(packet: Dict[str, Any]) -> str:
    discipline = packet["occupational_discipline_recognition"]
    readiness = packet["submission_readiness"]
    inputs = "\n".join(f"- `{k}`: {'found' if v.get('found') else 'missing'} at `{v.get('path')}`" for k, v in sorted(packet.get("input_status", {}).items())) or "- None"
    agents = "\n".join(f"- `{agent['agent_id']}`: {agent['mission']}" for agent in packet.get("agent_constellation", [])) or "- None"
    sections = "\n".join(f"- `{section['section_id']}`" for section in packet.get("deliverable_sections", [])) or "- None"
    return f"""# AIGC Employer Deliverable Procurement Report

Generated At: {packet['generated_at']}

Status: {packet['status']}

## Employer-Facing Purpose

This stage synthesizes internal AIGC phase outputs into a reviewable employer deliverable procurement packet. It recognizes the occupational discipline, assigns the agent constellation, applies ology research, coordinates data analytics, and prepares the best possible submission package without submitting externally.

## Input Audit

{inputs}

## Occupational Discipline Recognition

- Primary discipline: `{discipline.get('primary_discipline')}`
- Confidence: `{discipline.get('recognition_confidence')}`

## Agent Constellation

{agents}

## Deliverable Sections

{sections}

## Submission Readiness

- Readiness score: `{readiness.get('readiness_score')}`
- Recommended decision: `{readiness.get('recommended_decision')}`
- Employer submission allowed now: `false`

## Safety Boundary

No external action, credential use, secret logging, payment guarantee, or employer submission occurred. The packet must pass through the Submission Approval Cockpit before any submit/handoff action.
"""


def write_outputs(root: Path, config: Dict[str, Any], packet: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    packet_path = resolve_path(root, outputs.get("packet", "data/employer_deliverables/aigc_employer_deliverable_procurement_packet.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/employer_deliverable_procurement_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_employer_deliverable_procurement_audit.jsonl"))
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(packet), encoding="utf-8")
    audit_record = {
        "event_id": f"AIGC-EMPLOYER-DELIVERABLE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": packet["generated_at"],
        "phase": PHASE_NAME,
        "status": packet["status"],
        "primary_discipline": packet["occupational_discipline_recognition"].get("primary_discipline"),
        "readiness_score": packet["submission_readiness"].get("readiness_score"),
        "external_action_performed": False,
        "auto_submitted_to_employer": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")
    return packet_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC employer deliverable procurement stage.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_config(root, args.config)
    packet = build_packet(root, config)
    packet_path, report_path, audit_path = write_outputs(root, config, packet)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": packet["status"],
        "primary_discipline": packet["occupational_discipline_recognition"].get("primary_discipline"),
        "readiness_score": packet["submission_readiness"].get("readiness_score"),
        "packet_path": str(packet_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "external_action_performed": False,
        "auto_submitted_to_employer": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
