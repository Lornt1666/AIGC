from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class FreshnessReviewRecord:
    record_id: str
    created_at: str
    updated_at: str
    expires_at: str
    phase: str
    status: str
    source_phase27_record_id: str
    source_procurement_record_id: str
    opportunity_id: str
    proposal_id: str
    authorization_id: str
    action_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    review_scope: Dict[str, Any]
    evidence_summary: Dict[str, Any]
    freshness_findings: Dict[str, Any]
    required_review_controls: Dict[str, bool]
    operator_review: Dict[str, Any]
    phase28_gate_projection: Dict[str, Any]
    decision: str
    blocked_actions: List[str]
    external_data_fetch_performed: bool = False
    external_action_performed: bool = False


class Phase29AuditLedger:
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


class OperatorFreshnessReviewProcurement:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[FreshnessReviewRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        phase27_records = load_records(resolve_project_path(
            self.project_root,
            str(inputs.get("phase27_renewal_records", "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json")),
        ))
        intelligence_records = load_records(resolve_project_path(
            self.project_root,
            str(inputs.get("phase25_intelligence_ingestion", "data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json")),
        ))
        capability_records = load_records(resolve_project_path(
            self.project_root,
            str(inputs.get("phase26_capability_procurement", "data/phase26_capability_procurement/aigc_phase26_capability_procurement_records.json")),
        ))
        phase28_records = load_records(resolve_project_path(
            self.project_root,
            str(inputs.get("phase28_regeneration_candidates", "data/phase28_regeneration/aigc_phase28_regeneration_candidates.json")),
        ))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase29_freshness_reviews/aigc_phase29_freshness_review_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase29_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase29_audit.jsonl"),
        )
        existing = existing_records_by_source(load_records(output_path))
        records = self.build_records(config, phase27_records, intelligence_records, capability_records, phase28_records, existing)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        Phase29AuditLedger(audit_path).record("phase29_freshness_review_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "approved": sum(1 for record in records if record.decision == "approved_for_phase28_regeneration"),
            "pending": sum(1 for record in records if record.decision == "pending"),
            "external_data_fetch_performed": False,
            "external_action_performed": False,
        })
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        phase27_records: List[Dict[str, Any]],
        intelligence_records: List[Dict[str, Any]],
        capability_records: List[Dict[str, Any]],
        phase28_records: List[Dict[str, Any]],
        existing: Dict[str, Dict[str, Any]],
    ) -> List[FreshnessReviewRecord]:
        max_records = int(config.get("max_records", 25))
        return [
            self._build_record(config, renewal, intelligence_records, capability_records, phase28_records, existing)
            for renewal in phase27_records[:max_records]
        ]

    def _build_record(
        self,
        config: Dict[str, Any],
        renewal: Dict[str, Any],
        intelligence_records: List[Dict[str, Any]],
        capability_records: List[Dict[str, Any]],
        phase28_records: List[Dict[str, Any]],
        existing: Dict[str, Dict[str, Any]],
    ) -> FreshnessReviewRecord:
        source_phase27_id = str(renewal.get("record_id", ""))
        record_id = make_record_id(source_phase27_id)
        prior = existing.get(source_phase27_id, {})
        created_at = str(prior.get("created_at", "")) or utc_now()
        expires_at = str(prior.get("expires_at", "")) or (
            datetime.now(timezone.utc) + timedelta(hours=int(config.get("review_expiration_hours", 24)))
        ).isoformat()
        operator = str(config.get("operator", "Justice Gray Maciocha"))
        controls = required_controls(config, prior)
        operator_review = build_operator_review(record_id, operator, prior)
        decision = str(prior.get("decision", "pending"))
        status = status_for_decision(decision)
        return FreshnessReviewRecord(
            record_id=record_id,
            created_at=created_at,
            updated_at=utc_now(),
            expires_at=expires_at,
            phase="phase29_operator_freshness_review_procurement",
            status=status,
            source_phase27_record_id=source_phase27_id,
            source_procurement_record_id=str(renewal.get("source_procurement_record_id", "")),
            opportunity_id=str(renewal.get("opportunity_id", "")),
            proposal_id=str(renewal.get("proposal_id", "")),
            authorization_id=str(renewal.get("authorization_id", "")),
            action_id=str(renewal.get("action_id", "")),
            title=str(renewal.get("title", "")),
            employer=str(renewal.get("employer", "")),
            source_platform=str(renewal.get("source_platform", "")),
            source_url=str(renewal.get("source_url", "")),
            review_scope=build_review_scope(renewal),
            evidence_summary=build_evidence_summary(renewal, phase28_records),
            freshness_findings=build_freshness_findings(renewal, intelligence_records, capability_records),
            required_review_controls=controls,
            operator_review=operator_review,
            phase28_gate_projection=build_phase28_projection(decision, controls, operator_review),
            decision=decision,
            blocked_actions=[str(item) for item in config.get("blocked_actions", [])],
            external_data_fetch_performed=False,
            external_action_performed=False,
        )

    def signature_update(self, records: List[FreshnessReviewRecord]) -> str:
        approved = sum(1 for record in records if record.decision == "approved_for_phase28_regeneration")
        pending = sum(1 for record in records if record.decision == "pending")
        denied = sum(1 for record in records if record.decision == "denied")
        revisions = sum(1 for record in records if record.decision == "revision_required")
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 29 - Operator Freshness Review Procurement",
            "Operational Identity:",
            "Freshness Review Packet Procurement Layer",
            "Action Performed:",
            "Generated or preserved operator freshness-review records for Phase 27 renewal candidates.",
            "Safety Review:",
            "No external data fetch performed.",
            "No proposal sent.",
            "No application submitted.",
            "No employer contacted.",
            "No credentials used.",
            "No Phase 6 authorization granted.",
            "No external action performed.",
            f"Freshness Review Records: {len(records)}",
            f"Approved for Phase 28 Regeneration: {approved}",
            f"Pending Review: {pending}",
            f"Denied: {denied}",
            f"Revision Required: {revisions}",
            "Approval Required:",
            "Yes. Each review record requires its exact operator phrase before Phase 28 may generate candidates from it.",
        ]).strip() + "\n"


def approve_review_record(record: Dict[str, Any], phrase: str, decision: str) -> Dict[str, Any]:
    review = record.setdefault("operator_review", {})
    if review_expired(record):
        record["status"] = "expired_operator_review"
        record["decision"] = "expired"
        review["decision_notes"] = "Freshness review expired. Rerun Phase 29 to procure a fresh review packet."
        return record
    if decision == "approve":
        expected = str(review.get("required_phrase", ""))
        if phrase.strip() != expected:
            raise ValueError(f"Freshness approval phrase mismatch. Required phrase: {expected}")
        now = utc_now()
        review["received_phrase"] = phrase.strip()
        review["approved"] = True
        review["denied"] = False
        review["revision_required"] = False
        review["approved_at"] = now
        review["decision_notes"] = "Operator approved freshness review for internal Phase 28 regeneration only."
        record["required_review_controls"] = {
            key: True for key in record.get("required_review_controls", {})
        }
        record["decision"] = "approved_for_phase28_regeneration"
        record["status"] = "approved_for_internal_regeneration"
        record["updated_at"] = now
        record["phase28_gate_projection"] = build_phase28_projection(
            record["decision"],
            record["required_review_controls"],
            review,
        )
        return record
    if decision == "deny":
        expected = str(review.get("denial_phrase", ""))
        if phrase.strip() != expected:
            raise ValueError(f"Freshness denial phrase mismatch. Required phrase: {expected}")
        review["received_phrase"] = phrase.strip()
        review["approved"] = False
        review["denied"] = True
        review["revision_required"] = False
        review["decision_notes"] = "Operator denied freshness review."
        record["decision"] = "denied"
        record["status"] = "denied"
        record["updated_at"] = utc_now()
        record["phase28_gate_projection"] = build_phase28_projection(
            record["decision"],
            record.get("required_review_controls", {}),
            review,
        )
        return record
    expected_prefix = f"Revise freshness review {record.get('record_id', '')}:"
    if not phrase.strip().startswith(expected_prefix) or not phrase.strip()[len(expected_prefix):].strip():
        raise ValueError(f"Freshness revision phrase mismatch. Required prefix: {expected_prefix}")
    review["received_phrase"] = phrase.strip()
    review["approved"] = False
    review["denied"] = False
    review["revision_required"] = True
    review["decision_notes"] = phrase.strip().split(":", 1)[1].strip()
    record["decision"] = "revision_required"
    record["status"] = "revision_required"
    record["updated_at"] = utc_now()
    record["phase28_gate_projection"] = build_phase28_projection(
        record["decision"],
        record.get("required_review_controls", {}),
        review,
    )
    return record


def required_controls(config: Dict[str, Any], prior: Dict[str, Any]) -> Dict[str, bool]:
    existing = prior.get("required_review_controls", {})
    if isinstance(existing, dict) and existing:
        return {str(key): bool(value) for key, value in existing.items()}
    return {str(key): False for key in config.get("required_review_controls", [])}


def build_operator_review(record_id: str, operator: str, prior: Dict[str, Any]) -> Dict[str, Any]:
    existing = prior.get("operator_review", {})
    if isinstance(existing, dict) and existing:
        return existing
    return {
        "required": True,
        "required_phrase": f"I, {operator}, approve freshness review {record_id}.",
        "denial_phrase": f"I, {operator}, deny freshness review {record_id}.",
        "revision_phrase_template": f"Revise freshness review {record_id}: [revision instructions]",
        "received_phrase": "",
        "approved": False,
        "denied": False,
        "revision_required": False,
        "approved_at": "",
        "decision_notes": "",
        "external_action_authorized": False,
    }


def build_review_scope(renewal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "review_target": "phase27_renewal_record",
        "phase28_output_mode": "internal_candidate_only",
        "source_currentness_required": True,
        "old_action_id_approval_allowed": False,
        "old_action_id": renewal.get("action_id", ""),
        "required_review_questions": renewal.get("deep_research_brief", {}).get("research_questions", []),
    }


def build_evidence_summary(renewal: Dict[str, Any], phase28_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    source_id = str(renewal.get("record_id", ""))
    matching_phase28 = [
        record for record in phase28_records
        if str(record.get("source_phase27_record_id", "")) == source_id
    ]
    return {
        "source_truth_status": renewal.get("source_truth_status", ""),
        "renewal_strategy": renewal.get("renewal_strategy", ""),
        "preserved_artifact_chain": renewal.get("preserved_artifact_chain", []),
        "phase28_records_found": len(matching_phase28),
        "phase28_currently_blocked": any(record.get("regeneration_allowed") is False for record in matching_phase28),
        "external_data_fetch_performed": False,
        "external_action_performed": False,
    }


def build_freshness_findings(
    renewal: Dict[str, Any],
    intelligence_records: List[Dict[str, Any]],
    capability_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    drift_summary = renewal.get("freshness_requirements", {})
    capability_gaps = []
    for record in capability_records:
        for gap in record.get("gap_analysis", []):
            capability_gaps.append(str(gap))
    high_drift = sum(1 for record in intelligence_records if str(record.get("drift_risk_level", "")) in {"high", "critical"})
    stale_records = sum(1 for record in intelligence_records if str(record.get("staleness_status", "")) not in {"", "fresh"})
    return {
        "phase27_freshness_requirements": drift_summary,
        "intelligence_high_or_critical_drift_records": high_drift,
        "intelligence_stale_records": stale_records,
        "capability_gap_count": len(capability_gaps),
        "capability_gaps": unique(capability_gaps),
        "freshness_review_required": True,
    }


def build_phase28_projection(
    decision: str,
    controls: Dict[str, bool],
    operator_review: Dict[str, Any],
) -> Dict[str, Any]:
    controls_pass = all(bool(value) for value in controls.values()) if controls else False
    approved = (
        decision == "approved_for_phase28_regeneration"
        and bool(operator_review.get("approved", False))
        and controls_pass
    )
    return {
        "phase28_regeneration_allowed": approved,
        "allowed_output_mode": "internal_candidate_only",
        "controls_pass": controls_pass,
        "approved_review_required": True,
        "external_action_authorized": False,
        "phase6_authorized": False,
    }


def status_for_decision(decision: str) -> str:
    if decision == "approved_for_phase28_regeneration":
        return "approved_for_internal_regeneration"
    if decision == "denied":
        return "denied"
    if decision == "revision_required":
        return "revision_required"
    if decision == "expired":
        return "expired_operator_review"
    return "pending_operator_freshness_review"


def existing_records_by_source(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for record in records:
        source_id = str(record.get("source_phase27_record_id", ""))
        if source_id:
            result[source_id] = record
    return result


def review_expired(record: Dict[str, Any]) -> bool:
    value = str(record.get("expires_at", ""))
    if not value:
        return True
    try:
        expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at.astimezone(timezone.utc)


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


def make_record_id(source_phase27_record_id: str) -> str:
    seed = f"{source_phase27_record_id}|phase29"
    return "AIGC-FRESH-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 29 operator freshness review procurement.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase29_freshness_review_procurement.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = OperatorFreshnessReviewProcurement(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nFreshness review records exported: {args.project_root / 'data' / 'phase29_freshness_reviews' / 'aigc_phase29_freshness_review_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
