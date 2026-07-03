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
class StaleArtifactRenewalRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    source_procurement_record_id: str
    opportunity_id: str
    proposal_id: str
    authorization_id: str
    action_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    source_truth_status: str
    stale_artifact_classification: str
    renewal_strategy: str
    preserved_artifact_chain: List[Dict[str, Any]]
    deep_research_brief: Dict[str, Any]
    architecture_evolution_plan: Dict[str, Any]
    regeneration_blueprint: Dict[str, Any]
    quality_upgrade_targets: Dict[str, Any]
    freshness_requirements: Dict[str, Any]
    approval_gate: Dict[str, Any]
    blocked_actions: List[str]
    deletion_performed: bool = False
    external_data_fetch_performed: bool = False
    external_action_performed: bool = False


class Phase27AuditLedger:
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


class StaleArtifactRenewalController:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[StaleArtifactRenewalRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        procurement_records = load_records(resolve_project_path(self.project_root, str(inputs.get("truth_first_procurement_records", ""))))
        intelligence_records = load_records(resolve_project_path(self.project_root, str(inputs.get("intelligence_ingestion_records", ""))))
        capability_records = load_records(resolve_project_path(self.project_root, str(inputs.get("capability_procurement_records", ""))))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase27_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase27_audit.jsonl"),
        )
        records = self.build_records(config, procurement_records, intelligence_records, capability_records)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        Phase27AuditLedger(audit_path).record("phase27_stale_artifact_renewal_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "deletion_performed": False,
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        })
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        procurement_records: List[Dict[str, Any]],
        intelligence_records: List[Dict[str, Any]],
        capability_records: List[Dict[str, Any]],
    ) -> List[StaleArtifactRenewalRecord]:
        renewal_targets = set(str(item) for item in config.get("renewal_targets", []))
        max_records = int(config.get("max_records", 50))
        eligible = [
            record for record in procurement_records
            if str(record.get("procurement_classification", "")) in renewal_targets
        ]
        return [
            self._build_record(config, procurement, intelligence_records, capability_records)
            for procurement in eligible[:max_records]
        ]

    def _build_record(
        self,
        config: Dict[str, Any],
        procurement: Dict[str, Any],
        intelligence_records: List[Dict[str, Any]],
        capability_records: List[Dict[str, Any]],
    ) -> StaleArtifactRenewalRecord:
        classification = str(procurement.get("procurement_classification", "unknown_stale_artifact"))
        title = str(procurement.get("title", "Untitled renewal candidate"))
        employer = str(procurement.get("employer", ""))
        source_platform = str(procurement.get("source_platform", ""))
        source_url = str(procurement.get("source_url", ""))
        gaps = capability_gaps(capability_records)
        drift = drift_summary(intelligence_records)
        return StaleArtifactRenewalRecord(
            record_id=make_record_id(str(procurement.get("record_id", ""))),
            created_at=utc_now(),
            phase="phase27_stale_artifact_renewal_controller",
            status="renewal_blueprint_recorded",
            source_procurement_record_id=str(procurement.get("record_id", "")),
            opportunity_id=str(procurement.get("opportunity_id", "")),
            proposal_id=str(procurement.get("proposal_id", "")),
            authorization_id=str(procurement.get("authorization_id", "")),
            action_id=str(procurement.get("action_id", "")),
            title=title,
            employer=employer,
            source_platform=source_platform,
            source_url=source_url,
            source_truth_status=str(procurement.get("source_truth_status", "")),
            stale_artifact_classification=classification,
            renewal_strategy=renewal_strategy_for(classification),
            preserved_artifact_chain=list(procurement.get("artifact_chain", [])),
            deep_research_brief=build_deep_research_brief(config, procurement, gaps, drift),
            architecture_evolution_plan=build_architecture_evolution_plan(procurement, gaps),
            regeneration_blueprint=build_regeneration_blueprint(config, procurement),
            quality_upgrade_targets=build_quality_upgrade_targets(config, gaps),
            freshness_requirements=build_freshness_requirements(drift),
            approval_gate=build_approval_gate(procurement),
            blocked_actions=[str(item) for item in config.get("blocked_actions", [])],
            deletion_performed=False,
            external_data_fetch_performed=False,
            external_action_performed=False,
        )

    def signature_update(self, records: List[StaleArtifactRenewalRecord]) -> str:
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 27 - Stale Artifact Renewal and Deep Research Controller",
            "Operational Identity:",
            "Internal Renewal Queue for Stale Generated Artifacts",
            "Action Performed:",
            "Generated renewal records that preserve stale generated artifacts as historical derivatives and convert them into deep-research and regeneration blueprints.",
            "Safety Review:",
            "No deletion performed.",
            "No external data fetch performed.",
            "No external action performed.",
            "No approvals granted.",
            "No credentials used.",
            f"Renewal Records Created: {len(records)}",
            "Approval Required:",
            "Yes, before any regenerated approval candidate can proceed to Phase 6 or any external action.",
        ]).strip() + "\n"


def build_deep_research_brief(
    config: Dict[str, Any],
    procurement: Dict[str, Any],
    gaps: List[str],
    drift: Dict[str, Any],
) -> Dict[str, Any]:
    title = str(procurement.get("title", "this work candidate"))
    employer = str(procurement.get("employer", "the employer"))
    source_url = str(procurement.get("source_url", ""))
    axes = [str(item) for item in config.get("deep_research_axes", [])]
    questions = [
        f"Is the source opportunity still current and materially unchanged for {title}?",
        f"What technical acceptance criteria are explicit or missing for {title}?",
        f"What value would {employer} recognize as a successful outcome?",
        "What platform terms, disclosure requirements, privacy constraints, or communication norms apply?",
        "What payment, contract, revision, and delivery terms must be clarified before commitment?",
        "What evidence should appear in an employer-safe audit packet if this becomes real work?",
    ]
    if gaps:
        questions.append("Which Phase 26 capability gaps must be resolved before this candidate can claim high-quality readiness?")
    if drift.get("high_or_critical_drift_records", 0):
        questions.append("Which stale or high-drift context must be refreshed before regeneration?")
    return {
        "research_mode": "operator_scheduled_deep_dive_no_external_fetch",
        "external_research_required": True,
        "external_research_performed": False,
        "source_url_to_review_if_operator_approves": source_url,
        "research_axes": axes,
        "research_questions": questions,
        "local_evidence_to_review": artifact_paths(procurement),
        "capability_gaps_to_resolve": gaps,
        "freshness_drift_summary": drift,
    }


def build_architecture_evolution_plan(
    procurement: Dict[str, Any],
    gaps: List[str],
) -> Dict[str, Any]:
    return {
        "evolution_goal": "preserve_stale_derivative_then_regenerate_better_candidate_from_fresh_truth",
        "steps": [
            "Preserve the Phase 2 read-only source snapshot as historical evidence.",
            "Mark Phase 4 and later artifacts as generated derivatives, not source truth.",
            "Keep the expired Phase 5 packet unavailable for approval.",
            "Use the stale packet only as learning material for a refreshed proposal and approval candidate.",
            "Regenerate downstream artifacts after source currentness, compliance, payment, and quality blockers are reviewed.",
        ],
        "phase26_gap_count": len(gaps),
        "source_truth_status": procurement.get("source_truth_status", ""),
        "current_procurement_decision": procurement.get("procurement_decision", ""),
    }


def build_regeneration_blueprint(
    config: Dict[str, Any],
    procurement: Dict[str, Any],
) -> Dict[str, Any]:
    commands = [str(item) for item in config.get("renewal_commands", [])]
    return {
        "regeneration_allowed_now": False,
        "reason_not_allowed_now": "Stale generated candidates require operator review and fresh governed context before regeneration.",
        "operator_preconditions": [
            "Confirm whether the source opportunity should remain in scope.",
            "Authorize any external source refresh or manual source review explicitly.",
            "Resolve compliance, payment, scope, and disclosure questions.",
            "Keep all external action blocked until new Phase 5 and Phase 6 gates resolve.",
        ],
        "recommended_command_sequence": commands,
        "would_create_new_authorization_candidate": True,
        "old_action_id_retained_as_historical_derivative": procurement.get("action_id", ""),
    }


def build_quality_upgrade_targets(config: Dict[str, Any], gaps: List[str]) -> Dict[str, Any]:
    targets = config.get("quality_targets", {})
    return {
        "minimum_quality_score": int(targets.get("minimum_quality_score", 85)),
        "maximum_uncertainty_score": int(targets.get("maximum_uncertainty_score", 35)),
        "maximum_high_drift_records": int(targets.get("maximum_high_drift_records", 0)),
        "maximum_expired_generated_action_candidates": int(targets.get("maximum_expired_generated_action_candidates", 0)),
        "current_gap_count": len(gaps),
        "upgrade_definition": "A renewed candidate must reduce uncertainty, refresh truth context, remove expired approval authority, and preserve auditability.",
    }


def build_freshness_requirements(drift: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "fresh_source_required": True,
        "temporal_metadata_required": True,
        "high_or_critical_drift_records": drift.get("high_or_critical_drift_records", 0),
        "stale_records": drift.get("stale_records", 0),
        "regenerate_after_phase25_refresh": True,
    }


def build_approval_gate(procurement: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "phase5_required": True,
        "phase6_scope_match_required": True,
        "old_action_id_approval_allowed": False,
        "old_action_id": procurement.get("action_id", ""),
        "external_action_authorized": False,
        "operator_review_required": True,
    }


def renewal_strategy_for(classification: str) -> str:
    if classification == "generated_internal_chain_missing_source_snapshot":
        return "quarantine_derivatives_until_source_truth_is_restored_then_regenerate"
    if classification == "real_source_with_expired_generated_action_candidate":
        return "preserve_historical_derivative_and_regenerate_from_fresh_source_context"
    return "manual_operator_review_before_renewal"


def artifact_paths(procurement: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    for item in procurement.get("artifact_chain", []):
        if isinstance(item, dict) and item.get("path"):
            paths.append(str(item.get("path")))
    return unique(paths)


def capability_gaps(records: List[Dict[str, Any]]) -> List[str]:
    gaps: List[str] = []
    for record in records:
        for gap in record.get("gap_analysis", []):
            gaps.append(str(gap))
    return unique(gaps)


def drift_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    high_or_critical = sum(1 for record in records if str(record.get("drift_risk_level", "")) in {"high", "critical"})
    stale = sum(1 for record in records if str(record.get("staleness_status", "")) not in {"", "fresh"})
    domains = [
        str(record.get("context_domain", ""))
        for record in records
        if str(record.get("staleness_status", "")) not in {"", "fresh"}
    ]
    return {
        "high_or_critical_drift_records": high_or_critical,
        "stale_records": stale,
        "stale_context_domains": unique(domains),
    }


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


def make_record_id(source_procurement_record_id: str) -> str:
    seed = f"{source_procurement_record_id}|phase27"
    return "AIGC-REN-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 27 stale artifact renewal controller.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase27_stale_artifact_renewal.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = StaleArtifactRenewalController(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nStale artifact renewal records exported: {args.project_root / 'data' / 'phase27_renewal' / 'aigc_phase27_stale_artifact_renewal_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
