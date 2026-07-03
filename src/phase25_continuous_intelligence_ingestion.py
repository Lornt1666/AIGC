from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


TIMESTAMP_KEYS = {
    "created_at",
    "updated_at",
    "generated_at",
    "discovered_at",
    "posted_at",
    "timestamp",
    "expires_at",
}


@dataclass
class IntelligenceIngestionRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    context_domain: str
    source_path: str
    source_kind: str
    observed_record_count: int
    latest_observed_at: str
    freshness_score: int
    staleness_status: str
    drift_risk_level: str
    stale_indicators: List[str]
    missing_context_requests: List[str]
    knowledge_update_events: List[Dict[str, Any]]
    temporal_freshness_validation: Dict[str, Any]
    ontological_integration: Dict[str, Any]
    agent_coordination: List[Dict[str, Any]]
    recommended_refresh_actions: List[str]
    regeneration_targets: List[str]
    blocked_actions: List[str]
    approval_required_before_external_action: bool = True
    external_data_fetch_performed: bool = False
    external_action_performed: bool = False


class Phase25AuditLedger:
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


class ContinuousIntelligenceIngestionLayer:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[IntelligenceIngestionRecord]:
        config = load_json_dict(config_path)
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase25_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase25_audit.jsonl"),
        )
        records = self.build_records(config)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        Phase25AuditLedger(audit_path).record("phase25_intelligence_ingestion_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "stale_or_drift_records": sum(1 for record in records if record.staleness_status != "fresh"),
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        })
        return records

    def build_records(self, config: Dict[str, Any]) -> List[IntelligenceIngestionRecord]:
        sources = config.get("artifact_sources", [])
        max_sources = int(config.get("max_sources", 25))
        records: List[IntelligenceIngestionRecord] = []
        for source_config in sources[:max_sources]:
            records.append(self._build_record(config, source_config))
        return records

    def _build_record(
        self,
        config: Dict[str, Any],
        source_config: Dict[str, Any],
    ) -> IntelligenceIngestionRecord:
        context_domain = str(source_config.get("context_domain", "unknown_context_domain"))
        source_path = str(source_config.get("path", ""))
        source_kind = str(source_config.get("source_kind", "unknown_source_kind"))
        horizon_hours = int(source_config.get("freshness_horizon_hours", 24))
        regeneration_command = str(source_config.get("regeneration_command", "operator_review_required"))
        absolute_path = resolve_project_path(self.project_root, source_path)
        payload, parse_error = load_artifact_payload(absolute_path)
        observed_count = count_records(payload)
        timestamps = parse_timestamps(payload)
        latest_observed_at = max(timestamps).isoformat() if timestamps else ""
        expired_generated_count = count_expired_generated_candidates(payload)
        indicators = stale_indicators(
            absolute_path=absolute_path,
            parse_error=parse_error,
            observed_count=observed_count,
            timestamps=timestamps,
            horizon_hours=horizon_hours,
            expired_generated_count=expired_generated_count,
        )
        score = freshness_score(indicators, timestamps, horizon_hours, expired_generated_count)
        status = staleness_status(indicators)
        drift = drift_risk_level(score, indicators)
        missing_requests = missing_context_requests(context_domain, status, indicators)
        refresh_actions = recommended_refresh_actions(
            context_domain=context_domain,
            staleness=status,
            indicators=indicators,
            regeneration_command=regeneration_command,
        )
        regeneration_targets = [regeneration_command] if status != "fresh" and regeneration_command else []
        temporal_validation = build_temporal_validation(
            timestamps=timestamps,
            horizon_hours=horizon_hours,
            expired_generated_count=expired_generated_count,
            path_exists=absolute_path.exists(),
            parse_error=parse_error,
        )
        knowledge_events = build_knowledge_update_events(
            context_domain=context_domain,
            source_path=source_path,
            observed_count=observed_count,
            status=status,
            indicators=indicators,
        )
        return IntelligenceIngestionRecord(
            record_id=make_record_id(context_domain, source_path),
            created_at=utc_now(),
            phase="phase25_continuous_intelligence_ingestion_layer",
            status="freshness_recorded" if status == "fresh" else "refresh_required",
            context_domain=context_domain,
            source_path=source_path,
            source_kind=source_kind,
            observed_record_count=observed_count,
            latest_observed_at=latest_observed_at,
            freshness_score=score,
            staleness_status=status,
            drift_risk_level=drift,
            stale_indicators=indicators,
            missing_context_requests=missing_requests,
            knowledge_update_events=knowledge_events,
            temporal_freshness_validation=temporal_validation,
            ontological_integration=build_ontological_integration(config, context_domain, status, indicators),
            agent_coordination=build_agent_coordination(config, status, indicators),
            recommended_refresh_actions=refresh_actions,
            regeneration_targets=regeneration_targets,
            blocked_actions=[str(item) for item in config.get("blocked_actions", [])],
            approval_required_before_external_action=True,
            external_data_fetch_performed=False,
            external_action_performed=False,
        )

    def signature_update(self, records: List[IntelligenceIngestionRecord]) -> str:
        stale_count = sum(1 for record in records if record.staleness_status != "fresh")
        high_drift = sum(1 for record in records if record.drift_risk_level in {"high", "critical"})
        average_score = round(sum(record.freshness_score for record in records) / len(records), 2) if records else 0
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 25 - Continuous Intelligence Ingestion Layer",
            "Operational Identity:",
            "Internal Freshness, Drift, and Knowledge Update Ledger",
            "Action Performed:",
            "Generated intelligence ingestion records that validate artifact freshness, detect drift, and recommend refresh or regeneration targets.",
            "Safety Review:",
            "No external data fetch performed.",
            "No background daemon started.",
            "No deletion performed.",
            "No external action performed.",
            "No approvals granted.",
            "No credentials used.",
            f"Intelligence Records Created: {len(records)}",
            f"Records Requiring Refresh: {stale_count}",
            f"High or Critical Drift Records: {high_drift}",
            f"Average Freshness Score: {average_score}",
            "Approval Required:",
            "Yes, before any external data procurement, connector fetch, publication, or external action.",
        ]).strip() + "\n"


def load_artifact_payload(path: Path) -> tuple[Any, str]:
    if not path.exists():
        return None, "missing_path"
    if path.suffix.lower() == ".jsonl":
        records: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        records.append(payload)
        except json.JSONDecodeError as exc:
            return None, f"jsonl_parse_error:{exc.msg}"
        return records, ""
    if path.suffix.lower() == ".json":
        try:
            return json.loads(path.read_text(encoding="utf-8")), ""
        except json.JSONDecodeError as exc:
            return None, f"json_parse_error:{exc.msg}"
    return {
        "text_path": str(path),
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "content_length": len(path.read_text(encoding="utf-8", errors="replace")),
    }, ""


def count_records(payload: Any) -> int:
    if payload is None:
        return 0
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            return len(payload["records"])
        return 1
    return 1


def parse_timestamps(payload: Any) -> List[datetime]:
    timestamps: List[datetime] = []
    for key, value in walk_items(payload):
        if key not in TIMESTAMP_KEYS or not isinstance(value, str):
            continue
        parsed = parse_datetime(value)
        if parsed is not None:
            timestamps.append(parsed)
    return timestamps


def walk_items(payload: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield str(key), value
            yield from walk_items(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from walk_items(item)


def parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def count_expired_generated_candidates(payload: Any) -> int:
    if isinstance(payload, list):
        return sum(count_expired_generated_candidates(item) for item in payload)
    if not isinstance(payload, dict):
        return 0
    count = 0
    classification = str(payload.get("procurement_classification", ""))
    if classification == "real_source_with_expired_generated_action_candidate":
        count += 1
    decision = str(payload.get("decision", ""))
    expires_at = parse_datetime(str(payload.get("expires_at", "")))
    if decision == "pending" and expires_at is not None and datetime.now(timezone.utc) > expires_at:
        count += 1
    for value in payload.values():
        if isinstance(value, (dict, list)):
            count += count_expired_generated_candidates(value)
    return count


def stale_indicators(
    absolute_path: Path,
    parse_error: str,
    observed_count: int,
    timestamps: List[datetime],
    horizon_hours: int,
    expired_generated_count: int,
) -> List[str]:
    indicators: List[str] = []
    if not absolute_path.exists():
        indicators.append("missing_artifact_path")
    if parse_error:
        indicators.append(parse_error)
    if observed_count == 0:
        indicators.append("no_records_observed")
    if not timestamps:
        indicators.append("no_parseable_temporal_metadata")
    else:
        latest = max(timestamps)
        age_hours = max(0.0, (datetime.now(timezone.utc) - latest).total_seconds() / 3600)
        if age_hours > horizon_hours:
            indicators.append("freshness_horizon_exceeded")
        elif age_hours > horizon_hours * 0.75:
            indicators.append("approaching_freshness_horizon")
    if expired_generated_count > 0:
        indicators.append("expired_generated_action_candidates_present")
    return indicators


def freshness_score(
    indicators: List[str],
    timestamps: List[datetime],
    horizon_hours: int,
    expired_generated_count: int,
) -> int:
    score = 100
    penalties = {
        "missing_artifact_path": 75,
        "no_records_observed": 40,
        "no_parseable_temporal_metadata": 20,
        "freshness_horizon_exceeded": 35,
        "approaching_freshness_horizon": 15,
        "expired_generated_action_candidates_present": 35,
    }
    for indicator in indicators:
        score -= penalties.get(indicator, 10)
    if timestamps and "freshness_horizon_exceeded" not in indicators:
        latest = max(timestamps)
        age_hours = max(0.0, (datetime.now(timezone.utc) - latest).total_seconds() / 3600)
        score -= min(20, int((age_hours / max(horizon_hours, 1)) * 20))
    if expired_generated_count > 1:
        score -= min(20, expired_generated_count // 2)
    return max(0, min(100, score))


def staleness_status(indicators: List[str]) -> str:
    if "missing_artifact_path" in indicators:
        return "missing"
    if "no_records_observed" in indicators:
        return "empty"
    if "expired_generated_action_candidates_present" in indicators:
        return "stale_expired_generated_candidates"
    if "freshness_horizon_exceeded" in indicators:
        return "stale"
    if "approaching_freshness_horizon" in indicators:
        return "aging"
    if "no_parseable_temporal_metadata" in indicators:
        return "needs_temporal_metadata"
    return "fresh"


def drift_risk_level(score: int, indicators: List[str]) -> str:
    if "missing_artifact_path" in indicators or score < 30:
        return "critical"
    if score < 55 or "expired_generated_action_candidates_present" in indicators:
        return "high"
    if score < 75 or "freshness_horizon_exceeded" in indicators:
        return "medium"
    if score < 90:
        return "low"
    return "minimal"


def missing_context_requests(context_domain: str, status: str, indicators: List[str]) -> List[str]:
    requests: List[str] = []
    if status == "missing":
        requests.append(f"Provide or regenerate the missing artifact for {context_domain}.")
    if status == "empty":
        requests.append(f"Provide current records for {context_domain}.")
    if "no_parseable_temporal_metadata" in indicators:
        requests.append(f"Add generated_at, created_at, or updated_at metadata to {context_domain}.")
    if "expired_generated_action_candidates_present" in indicators:
        requests.append("Provide explicit operator instruction to archive or regenerate expired generated approval candidates.")
    if status in {"stale", "aging"}:
        requests.append(f"Refresh {context_domain} from current governed inputs before relying on it.")
    return unique(requests)


def recommended_refresh_actions(
    context_domain: str,
    staleness: str,
    indicators: List[str],
    regeneration_command: str,
) -> List[str]:
    actions: List[str] = []
    if staleness == "fresh":
        actions.append(f"Retain {context_domain}; current freshness posture is acceptable.")
    else:
        actions.append(f"Refresh {context_domain} before using it for downstream reasoning.")
        if regeneration_command:
            actions.append(f"Regeneration target: {regeneration_command}.")
    if "expired_generated_action_candidates_present" in indicators:
        actions.append("Run procurement review and archive or regenerate expired generated approval candidates before Phase 6.")
    if "no_parseable_temporal_metadata" in indicators:
        actions.append("Add temporal metadata so future freshness validation can be deterministic.")
    return unique(actions)


def build_temporal_validation(
    timestamps: List[datetime],
    horizon_hours: int,
    expired_generated_count: int,
    path_exists: bool,
    parse_error: str,
) -> Dict[str, Any]:
    latest = max(timestamps).isoformat() if timestamps else ""
    age_hours = None
    if timestamps:
        age_hours = round(max(0.0, (datetime.now(timezone.utc) - max(timestamps)).total_seconds() / 3600), 2)
    return {
        "path_exists": path_exists,
        "parse_error": parse_error,
        "timestamp_count": len(timestamps),
        "latest_observed_at": latest,
        "age_hours": age_hours,
        "freshness_horizon_hours": horizon_hours,
        "expired_generated_action_candidates": expired_generated_count,
        "validated_at": utc_now(),
    }


def build_knowledge_update_events(
    context_domain: str,
    source_path: str,
    observed_count: int,
    status: str,
    indicators: List[str],
) -> List[Dict[str, Any]]:
    events = [{
        "event_type": "local_artifact_ingested",
        "context_domain": context_domain,
        "source_path": source_path,
        "observed_record_count": observed_count,
        "staleness_status": status,
        "recorded_at": utc_now(),
    }]
    if indicators:
        events.append({
            "event_type": "freshness_drift_detected",
            "context_domain": context_domain,
            "indicators": indicators,
            "recorded_at": utc_now(),
        })
    return events


def build_ontological_integration(
    config: Dict[str, Any],
    context_domain: str,
    status: str,
    indicators: List[str],
) -> Dict[str, Any]:
    integration: Dict[str, Any] = {}
    for axis in config.get("ontology_axes", []):
        name = str(axis)
        integration[name] = {
            "status": "integrated",
            "context_domain": context_domain,
            "freshness_state": status,
            "drift_signal_count": len(indicators),
            "interpretation": interpretation_for_axis(name, status),
        }
    return integration


def interpretation_for_axis(axis: str, status: str) -> str:
    interpretations = {
        "ontology": "Classifies the artifact as a context object with source, derivative, or governance meaning.",
        "epistemology": "Constrains reasoning to freshness-validated evidence.",
        "methodology": "Routes stale artifacts to refresh or regeneration before downstream use.",
        "praxeology": "Optimizes action by preventing wasted work on outdated context.",
        "axiology": "Prioritizes truthfulness, auditability, professionalism, legality, and user trust.",
        "teleology": "Aims toward continuously refreshed internal intelligence without unsafe autonomy.",
        "semiotics": "Interprets stale, missing, and expired signals as meaning-bearing quality warnings.",
        "cybernetics": "Feeds drift findings back into future refresh cycles.",
        "systems_theory": "Connects source, approval, procurement, observability, and productization subsystems.",
    }
    return interpretations.get(axis, f"Integrated freshness state {status}.")


def build_agent_coordination(
    config: Dict[str, Any],
    status: str,
    indicators: List[str],
) -> List[Dict[str, Any]]:
    agents: List[Dict[str, Any]] = []
    for role in config.get("freshness_agents", []):
        role_name = str(role)
        agents.append({
            "role": role_name,
            "status": "internal_freshness_review_only",
            "finding": finding_for_agent(role_name, status, indicators),
            "external_action_allowed": False,
        })
    return agents


def finding_for_agent(role: str, status: str, indicators: List[str]) -> str:
    if "Temporal" in role:
        return f"Freshness state is {status} with {len(indicators)} temporal or drift indicators."
    if "Freshness" in role:
        return "Artifact can be retained only if freshness status is fresh."
    if "Drift" in role:
        return "Drift indicators are visible and must remain auditable."
    if "Ontological" in role:
        return "Artifact integrated into the source/derivative/governance context map."
    if "Praxeological" in role:
        return "Recommended action is refresh before downstream use when stale."
    return "Internal intelligence ingestion review completed."


def make_record_id(context_domain: str, source_path: str) -> str:
    seed = f"{context_domain}|{source_path}|phase25"
    return "AIGC-CIIL-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 25 continuous intelligence ingestion layer.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase25_continuous_intelligence_ingestion.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = ContinuousIntelligenceIngestionLayer(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nIntelligence ingestion records exported: {args.project_root / 'data' / 'phase25_intelligence' / 'aigc_phase25_intelligence_ingestion_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
