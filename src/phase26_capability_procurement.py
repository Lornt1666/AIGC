from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class CapabilityProcurementRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    procurement_domain: str
    procurement_purpose: str
    capability_level: str
    source_record_counts: Dict[str, int]
    source_quality_state: Dict[str, Any]
    source_freshness_state: Dict[str, Any]
    required_inputs: List[str]
    required_controls: List[str]
    required_standards: List[str]
    required_agents: List[str]
    evidence_sources: List[Dict[str, Any]]
    gap_analysis: List[str]
    quantum_quality_application: Dict[str, Any]
    ontological_application: Dict[str, Any]
    procurement_decision: str
    recommended_actions: List[str]
    blocked_actions: List[str]
    approval_required_before_external_action: bool = True
    external_data_fetch_performed: bool = False
    external_action_performed: bool = False


class Phase26AuditLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "timestamp": utc_now(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event_id


class AscendedCapabilityProcurementProgram:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[CapabilityProcurementRecord]:
        config = load_json_dict(config_path)
        input_files = config.get("input_files", {})
        records_by_alias = {
            alias: load_records(resolve_project_path(self.project_root, str(path)))
            for alias, path in input_files.items()
        }
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase26_capability_procurement/aigc_phase26_capability_procurement_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase26_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase26_audit.jsonl"),
        )
        records = self.build_records(config, input_files, records_by_alias)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        Phase26AuditLedger(audit_path).record("phase26_capability_procurement_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "records_with_gaps": sum(1 for record in records if record.gap_analysis),
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        })
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        input_files: Dict[str, Any],
        records_by_alias: Dict[str, List[Dict[str, Any]]],
    ) -> List[CapabilityProcurementRecord]:
        thresholds = config.get("quality_thresholds", {})
        procurements = config.get("capability_procurements", [])
        return [
            self._build_record(config, thresholds, input_files, records_by_alias, procurement)
            for procurement in procurements
        ]

    def _build_record(
        self,
        config: Dict[str, Any],
        thresholds: Dict[str, Any],
        input_files: Dict[str, Any],
        records_by_alias: Dict[str, List[Dict[str, Any]]],
        procurement: Dict[str, Any],
    ) -> CapabilityProcurementRecord:
        domain = str(procurement.get("domain", "unknown_capability_domain"))
        aliases = [str(item) for item in procurement.get("source_aliases", [])]
        selected = {alias: records_by_alias.get(alias, []) for alias in aliases}
        counts = {alias: len(records) for alias, records in selected.items()}
        quality_state = build_quality_state(selected)
        freshness_state = build_freshness_state(selected)
        evidence = build_evidence_sources(input_files, selected)
        gaps = build_gap_analysis(domain, counts, quality_state, freshness_state, thresholds)
        capability_score = capability_quality_score(quality_state, freshness_state, gaps)
        uncertainty_score = capability_uncertainty_score(quality_state, freshness_state, gaps)
        capability_level = (
            "ascended_capability_procured_for_internal_use"
            if not gaps
            else "procurement_gaps_require_resolution"
        )
        decision = (
            "ready_for_internal_quality_application"
            if not gaps
            else "resolve_procurement_gaps_before_ascended_quality_claim"
        )
        return CapabilityProcurementRecord(
            record_id=make_record_id(domain),
            created_at=utc_now(),
            phase="phase26_ascended_capability_procurement_program",
            status="capability_procurement_recorded",
            procurement_domain=domain,
            procurement_purpose=str(procurement.get("purpose", "")),
            capability_level=capability_level,
            source_record_counts=counts,
            source_quality_state=quality_state,
            source_freshness_state=freshness_state,
            required_inputs=[str(item) for item in procurement.get("required_inputs", [])],
            required_controls=[str(item) for item in procurement.get("required_controls", [])],
            required_standards=[str(item) for item in procurement.get("required_standards", [])],
            required_agents=[str(item) for item in procurement.get("required_agents", [])],
            evidence_sources=evidence,
            gap_analysis=gaps,
            quantum_quality_application={
                "model_type": "deterministic_uncertainty_aware_capability_procurement_model",
                "literal_quantum_claim": False,
                "capability_quality_score": capability_score,
                "capability_uncertainty_score": uncertainty_score,
                "readiness_state": capability_level,
                "collapse_conditions": collapse_conditions_for(domain),
            },
            ontological_application=build_ontological_application(config, domain, gaps),
            procurement_decision=decision,
            recommended_actions=recommended_actions_for(domain, gaps),
            blocked_actions=[str(item) for item in config.get("blocked_actions", [])],
            approval_required_before_external_action=True,
            external_data_fetch_performed=False,
            external_action_performed=False,
        )

    def signature_update(self, records: List[CapabilityProcurementRecord]) -> str:
        gap_records = sum(1 for record in records if record.gap_analysis)
        average_score = round(
            sum(int(record.quantum_quality_application.get("capability_quality_score", 0)) for record in records) / len(records),
            2,
        ) if records else 0
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 26 - Ascended Capability Procurement Program",
            "Operational Identity:",
            "Internal Capability Procurement Ledger",
            "Action Performed:",
            "Generated capability procurement records that articulate required standards, evidence, internal agents, controls, and freshness gates before ascended quality can be claimed.",
            "Safety Review:",
            "No external data fetch performed.",
            "No external procurement performed.",
            "No deletion performed.",
            "No external action performed.",
            "No approvals granted.",
            "No credentials used.",
            f"Capability Procurement Records Created: {len(records)}",
            f"Records With Procurement Gaps: {gap_records}",
            f"Average Capability Quality Score: {average_score}",
            "Approval Required:",
            "Yes, before any externally visible action, claim, submission, delivery, connector use, or employer/customer contact.",
        ]).strip() + "\n"


def build_quality_state(selected: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    records = flatten(selected.values())
    quality_scores = [int_value(record.get("quality_score")) for record in records if int_value(record.get("quality_score")) is not None]
    uncertainty_scores = [
        int_value(record.get("uncertainty_score"))
        for record in records
        if int_value(record.get("uncertainty_score")) is not None
    ]
    for record in records:
        quantum_state = record.get("quantum_quality_state")
        if isinstance(quantum_state, dict):
            quality = int_value(quantum_state.get("quality_score"))
            uncertainty = int_value(quantum_state.get("uncertainty_score"))
            if quality is not None:
                quality_scores.append(quality)
            if uncertainty is not None:
                uncertainty_scores.append(uncertainty)
    return {
        "average_quality_score": average(quality_scores),
        "average_uncertainty_score": average(uncertainty_scores),
        "quality_score_count": len(quality_scores),
        "uncertainty_score_count": len(uncertainty_scores),
        "quality_states": count_values(records, "quality_state"),
        "external_action_performed_count": count_bool(records, "external_action_performed"),
    }


def build_freshness_state(selected: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    records = flatten(selected.values())
    drift_records = [
        record for record in records
        if str(record.get("drift_risk_level", "")) in {"high", "critical"}
    ]
    stale_records = [
        record for record in records
        if str(record.get("staleness_status", "")) not in {"", "fresh"}
    ]
    expired = [
        record for record in records
        if str(record.get("procurement_classification", "")) == "real_source_with_expired_generated_action_candidate"
        or bool(record.get("current_action_state", {}).get("expired", False))
    ]
    return {
        "high_or_critical_drift_records": len(drift_records),
        "stale_records": len(stale_records),
        "expired_generated_action_candidates": len(expired),
        "freshness_statuses": count_values(records, "staleness_status"),
        "procurement_classifications": count_values(records, "procurement_classification"),
    }


def build_evidence_sources(
    input_files: Dict[str, Any],
    selected: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for alias, records in selected.items():
        path = str(input_files.get(alias, ""))
        sources.append({
            "alias": alias,
            "path": path,
            "record_count": len(records),
            "present": len(records) > 0,
            "truth_role": "source_or_governance_evidence",
        })
    return sources


def build_gap_analysis(
    domain: str,
    counts: Dict[str, int],
    quality_state: Dict[str, Any],
    freshness_state: Dict[str, Any],
    thresholds: Dict[str, Any],
) -> List[str]:
    gaps: List[str] = []
    for alias, count in counts.items():
        if count == 0:
            gaps.append(f"{domain}: required evidence source {alias} has no records.")
    minimum_quality = int(thresholds.get("minimum_average_quality_score", 85))
    maximum_uncertainty = int(thresholds.get("maximum_average_uncertainty_score", 35))
    maximum_drift = int(thresholds.get("maximum_high_drift_records", 0))
    maximum_expired = int(thresholds.get("maximum_expired_generated_action_candidates", 0))
    average_quality_score = quality_state.get("average_quality_score")
    average_uncertainty_score = quality_state.get("average_uncertainty_score")
    if average_quality_score is not None and average_quality_score < minimum_quality:
        gaps.append(f"{domain}: average quality score {average_quality_score} is below threshold {minimum_quality}.")
    if average_uncertainty_score is not None and average_uncertainty_score > maximum_uncertainty:
        gaps.append(f"{domain}: average uncertainty score {average_uncertainty_score} exceeds threshold {maximum_uncertainty}.")
    if int(freshness_state.get("high_or_critical_drift_records", 0)) > maximum_drift:
        gaps.append(f"{domain}: high or critical drift records exceed threshold {maximum_drift}.")
    if int(freshness_state.get("expired_generated_action_candidates", 0)) > maximum_expired:
        gaps.append(f"{domain}: expired generated action candidates exceed threshold {maximum_expired}.")
    if int(quality_state.get("external_action_performed_count", 0)) > 0:
        gaps.append(f"{domain}: evidence indicates external action occurred and requires incident review.")
    return unique(gaps)


def capability_quality_score(
    quality_state: Dict[str, Any],
    freshness_state: Dict[str, Any],
    gaps: List[str],
) -> int:
    base = quality_state.get("average_quality_score")
    score = int(base) if base is not None else 80
    score -= len(gaps) * 10
    score -= int(freshness_state.get("high_or_critical_drift_records", 0)) * 5
    score -= int(freshness_state.get("expired_generated_action_candidates", 0)) * 5
    return max(0, min(100, score))


def capability_uncertainty_score(
    quality_state: Dict[str, Any],
    freshness_state: Dict[str, Any],
    gaps: List[str],
) -> int:
    base = quality_state.get("average_uncertainty_score")
    score = int(base) if base is not None else 20
    score += len(gaps) * 10
    score += int(freshness_state.get("high_or_critical_drift_records", 0)) * 5
    score += int(freshness_state.get("expired_generated_action_candidates", 0)) * 5
    return max(0, min(100, score))


def build_ontological_application(
    config: Dict[str, Any],
    domain: str,
    gaps: List[str],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for axis in config.get("ontology_axes", []):
        axis_name = str(axis)
        result[axis_name] = {
            "status": "gap_review_required" if gaps else "procured",
            "procurement_domain": domain,
            "interpretation": interpretation_for_axis(axis_name, domain),
        }
    return result


def interpretation_for_axis(axis: str, domain: str) -> str:
    interpretations = {
        "ontology": "Defines the capability as an internal requirement object, not a vague aspiration.",
        "epistemology": "Requires evidence before AIGC can claim the capability is active.",
        "methodology": "Maps standards, controls, inputs, and validation steps into a repeatable process.",
        "praxeology": "Turns quality intent into actionable internal next steps.",
        "axiology": "Prioritizes truth, professionalism, legality, user trust, and customer value.",
        "teleology": "Aims the capability toward high-quality work under explicit gates.",
        "semiotics": "Treats gaps, drift, uncertainty, and blocked actions as meaning-bearing signals.",
        "cybernetics": "Feeds procurement gaps back into refresh, regeneration, and quality improvement loops.",
        "systems_theory": "Connects quality, work-order governance, procurement truth, and freshness subsystems.",
        "ethics": "Keeps external action blocked until law, safety, and professional constraints are satisfied.",
        "jurisprudence": "Requires legal and platform-rule review before any externally visible conduct.",
        "risk_theory": "Surfaces unresolved risk instead of hiding it behind confident language.",
    }
    return interpretations.get(axis, f"Applies {axis} to {domain}.")


def collapse_conditions_for(domain: str) -> List[str]:
    return [
        f"{domain} evidence sources are present",
        "contract validation passes",
        "secret scan passes",
        "truth-first procurement has no unresolved expired generated action candidates",
        "continuous intelligence ingestion has no high or critical drift for required evidence",
        "quality uncertainty is below configured threshold or explicitly accepted by the operator",
        "Phase 5 approval and Phase 6 scope are satisfied before external action",
    ]


def recommended_actions_for(domain: str, gaps: List[str]) -> List[str]:
    if not gaps:
        return [f"Retain {domain} capability procurement as ready for internal quality application."]
    actions = [f"Resolve procurement gaps for {domain} before claiming ascended quality."]
    if any("expired generated action candidates" in gap for gap in gaps):
        actions.append("Run Phase 24 and archive or regenerate expired generated approval candidates under operator review.")
    if any("drift" in gap for gap in gaps):
        actions.append("Run Phase 25 and refresh stale local artifacts before downstream use.")
    if any("quality score" in gap or "uncertainty score" in gap for gap in gaps):
        actions.append("Rerun or revise Phase 22 and Phase 23 after resolving quality, compliance, scope, and approval blockers.")
    if any("no records" in gap for gap in gaps):
        actions.append("Regenerate missing source artifacts before using this capability in work-order governance.")
    return unique(actions)


def load_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        records: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    records.append(payload)
        return records
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def flatten(groups: Any) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for group in groups:
        records.extend(item for item in group if isinstance(item, dict))
    return records


def int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def average(values: List[int]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values))


def count_values(records: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        value = str(record.get(key, ""))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def count_bool(records: List[Dict[str, Any]], key: str) -> int:
    return sum(1 for record in records if bool(record.get(key, False)))


def make_record_id(domain: str) -> str:
    seed = f"{domain}|phase26"
    return "AIGC-CAP-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run AIGC Phase 26 ascended capability procurement program.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase26_capability_procurement.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = AscendedCapabilityProcurementProgram(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nCapability procurement records exported: {args.project_root / 'data' / 'phase26_capability_procurement' / 'aigc_phase26_capability_procurement_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
