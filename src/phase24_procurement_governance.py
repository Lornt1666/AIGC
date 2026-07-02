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
class ProcurementRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    opportunity_id: str
    proposal_id: str
    authorization_id: str
    action_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    source_truth_status: str
    artifact_chain: List[Dict[str, Any]]
    procurement_classification: str
    procurement_decision: str
    current_action_state: Dict[str, Any]
    truth_controls: Dict[str, Any]
    recommended_cleanup_actions: List[str]
    blocked_actions: List[str]
    approval_required_before_external_action: bool = True
    deletion_performed: bool = False
    external_action_performed: bool = False


class Phase24AuditLedger:
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


class TruthFirstProcurementGovernance:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[ProcurementRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        opportunities = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("opportunities", "")))
        proposals = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("proposals", "")))
        authorizations = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("authorizations", "")))
        quality_records = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("quality_kernel_records", "")))
        work_order_records = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("work_order_governance_records", "")))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase24_procurement/aigc_phase24_procurement_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase24_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase24_audit.jsonl"),
        )
        records = self.build_records(
            config=config,
            paths=inputs,
            opportunities=opportunities,
            proposals=proposals,
            authorizations=authorizations,
            quality_records=quality_records,
            work_order_records=work_order_records,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        Phase24AuditLedger(audit_path).record("phase24_procurement_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "expired_generated_action_candidates": count_expired_generated_candidates(records),
            "deletion_performed": False,
            "external_action_performed": False,
        })
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        paths: Dict[str, Any],
        opportunities: List[Dict[str, Any]],
        proposals: List[Dict[str, Any]],
        authorizations: List[Dict[str, Any]],
        quality_records: List[Dict[str, Any]],
        work_order_records: List[Dict[str, Any]],
    ) -> List[ProcurementRecord]:
        max_records = int(config.get("max_records", 50))
        opportunities_by_id = {str(item.get("opportunity_id", "")): item for item in opportunities}
        authorizations_by_proposal = group_by(authorizations, "proposal_id")
        quality_by_proposal = {str(item.get("proposal_id", "")): item for item in quality_records}
        work_order_by_proposal = {str(item.get("proposal_id", "")): item for item in work_order_records}
        records: List[ProcurementRecord] = []

        for proposal in proposals:
            proposal_id = str(proposal.get("proposal_id") or proposal.get("package_id", ""))
            opportunity_id = str(proposal.get("opportunity_id", ""))
            source = opportunities_by_id.get(opportunity_id, {})
            matched_authorizations = authorizations_by_proposal.get(proposal_id, [])
            if matched_authorizations:
                for authorization in matched_authorizations:
                    records.append(self._build_record(
                        config=config,
                        paths=paths,
                        source=source,
                        proposal=proposal,
                        authorization=authorization,
                        quality_record=quality_by_proposal.get(proposal_id, {}),
                        work_order_record=work_order_by_proposal.get(proposal_id, {}),
                    ))
                    if len(records) >= max_records:
                        return records
            else:
                records.append(self._build_record(
                    config=config,
                    paths=paths,
                    source=source,
                    proposal=proposal,
                    authorization={},
                    quality_record=quality_by_proposal.get(proposal_id, {}),
                    work_order_record=work_order_by_proposal.get(proposal_id, {}),
                ))
                if len(records) >= max_records:
                    return records

        if records:
            return records

        for source in opportunities[:max_records]:
            records.append(self._build_source_only_record(config=config, paths=paths, source=source))
        return records

    def _build_record(
        self,
        config: Dict[str, Any],
        paths: Dict[str, Any],
        source: Dict[str, Any],
        proposal: Dict[str, Any],
        authorization: Dict[str, Any],
        quality_record: Dict[str, Any],
        work_order_record: Dict[str, Any],
    ) -> ProcurementRecord:
        opportunity_id = str(proposal.get("opportunity_id") or authorization.get("opportunity_id") or source.get("opportunity_id", ""))
        proposal_id = str(proposal.get("proposal_id") or proposal.get("package_id") or authorization.get("proposal_id", ""))
        authorization_id = str(authorization.get("authorization_id", ""))
        action_id = str(authorization.get("action_id", ""))
        title = str(proposal.get("title") or source.get("title") or authorization.get("proposed_external_action", "Untitled procurement candidate"))
        employer = str(proposal.get("employer") or source.get("employer") or authorization.get("recipient", ""))
        source_platform = str(proposal.get("source_platform") or source.get("source_platform") or authorization.get("platform", ""))
        source_url = str(proposal.get("source_url") or source.get("source_url") or authorization.get("source_url", ""))
        action_state = build_action_state(authorization)
        source_present = bool(source)
        source_truth_status = (
            "real_read_only_source_snapshot_present"
            if source_present
            else "missing_source_snapshot_generated_internal_only"
        )
        classification = procurement_classification(source_present, action_state, bool(proposal), bool(authorization))
        decision = procurement_decision(classification)
        chain = build_artifact_chain(
            paths=paths,
            source=source,
            proposal=proposal,
            authorization=authorization,
            quality_record=quality_record,
            work_order_record=work_order_record,
            action_state=action_state,
        )
        truth_controls = {
            "source_snapshot_preserved": source_present,
            "generated_artifacts_marked_derived": True,
            "stale_generated_artifacts_active": action_state["phase5_decision"] == "pending" and action_state["expired"],
            "requires_regeneration_before_approval": action_state["expired"] or not source_present,
            "approval_granted": action_state["approval_granted"],
            "deletion_allowed_in_phase24": False,
            "truth_warning": truth_warning(source_present, action_state),
        }
        return ProcurementRecord(
            record_id=make_record_id(opportunity_id, proposal_id, authorization_id, action_id),
            created_at=utc_now(),
            phase="phase24_truth_first_procurement_governance",
            status="procurement_truth_recorded",
            opportunity_id=opportunity_id,
            proposal_id=proposal_id,
            authorization_id=authorization_id,
            action_id=action_id,
            title=title,
            employer=employer,
            source_platform=source_platform,
            source_url=source_url,
            source_truth_status=source_truth_status,
            artifact_chain=chain,
            procurement_classification=classification,
            procurement_decision=decision,
            current_action_state=action_state,
            truth_controls=truth_controls,
            recommended_cleanup_actions=recommended_cleanup_actions(classification, source_present, bool(quality_record), bool(work_order_record)),
            blocked_actions=[str(item) for item in config.get("blocked_actions", [])],
            approval_required_before_external_action=True,
            deletion_performed=False,
            external_action_performed=False,
        )

    def _build_source_only_record(
        self,
        config: Dict[str, Any],
        paths: Dict[str, Any],
        source: Dict[str, Any],
    ) -> ProcurementRecord:
        opportunity_id = str(source.get("opportunity_id", ""))
        return ProcurementRecord(
            record_id=make_record_id(opportunity_id, "", "", ""),
            created_at=utc_now(),
            phase="phase24_truth_first_procurement_governance",
            status="procurement_truth_recorded",
            opportunity_id=opportunity_id,
            proposal_id="",
            authorization_id="",
            action_id="",
            title=str(source.get("title", "Untitled source opportunity")),
            employer=str(source.get("employer", "")),
            source_platform=str(source.get("source_platform", "")),
            source_url=str(source.get("source_url", "")),
            source_truth_status="real_read_only_source_snapshot_present",
            artifact_chain=[
                artifact_item("phase2_opportunity_radar", opportunity_id, str(paths.get("opportunities", "")), "source_evidence", source.get("radar_decision", "source_snapshot_present"))
            ],
            procurement_classification="real_source_no_generated_procurement_chain",
            procurement_decision="retain_source_snapshot_and_run_assessment_before_action",
            current_action_state=empty_action_state(),
            truth_controls={
                "source_snapshot_preserved": True,
                "generated_artifacts_marked_derived": True,
                "stale_generated_artifacts_active": False,
                "requires_regeneration_before_approval": True,
                "approval_granted": False,
                "deletion_allowed_in_phase24": False,
                "truth_warning": "Only a read-only source snapshot exists. No approval or action exists.",
            },
            recommended_cleanup_actions=[
                "Preserve the Phase 2 source snapshot as historical evidence.",
                "Run Phase 3 and Phase 4 before creating any approval packet.",
            ],
            blocked_actions=[str(item) for item in config.get("blocked_actions", [])],
            approval_required_before_external_action=True,
            deletion_performed=False,
            external_action_performed=False,
        )

    def signature_update(self, records: List[ProcurementRecord]) -> str:
        expired = count_expired_generated_candidates(records)
        missing_source = sum(1 for record in records if record.source_truth_status == "missing_source_snapshot_generated_internal_only")
        real_sources = sum(1 for record in records if record.source_truth_status == "real_read_only_source_snapshot_present")
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 24 - Truth-First Procurement Governance",
            "Operational Identity:",
            "Internal Procurement Truth Ledger",
            "Action Performed:",
            "Generated procurement records that classify real source evidence, generated internal derivatives, stale approval candidates, and cleanup recommendations.",
            "Safety Review:",
            "No deletion performed.",
            "No external action performed.",
            "No approvals granted.",
            "No employers or customers contacted.",
            "No credentials used.",
            f"Procurement Records Created: {len(records)}",
            f"Real Source Snapshots Present: {real_sources}",
            f"Generated Chains Missing Source Snapshot: {missing_source}",
            f"Expired Generated Action Candidates: {expired}",
            "Approval Required:",
            "Yes, before any procurement candidate can become an external action.",
        ]).strip() + "\n"


def build_action_state(authorization: Dict[str, Any]) -> Dict[str, Any]:
    if not authorization:
        return empty_action_state()
    phase6_status = authorization.get("phase6_status", {})
    approval = authorization.get("approval", {})
    decision = str(authorization.get("decision", "missing"))
    expired = authorization_expired(authorization)
    return {
        "phase5_decision": decision,
        "created_at": str(authorization.get("created_at", "")),
        "expires_at": str(authorization.get("expires_at", "")),
        "expired": expired,
        "phase6_authorized": bool(phase6_status.get("authorized_for_phase6", False)),
        "approval_granted": bool(approval.get("approved", False)) or decision == "approved_for_phase_6",
        "approval_denied": bool(approval.get("denied", False)) or decision == "denied",
        "revision_required": bool(approval.get("revision_required", False)) or decision == "revision_required",
        "external_action_performed": bool(phase6_status.get("external_action_performed", False)),
        "generated_action_candidate": True,
    }


def empty_action_state() -> Dict[str, Any]:
    return {
        "phase5_decision": "missing",
        "created_at": "",
        "expires_at": "",
        "expired": False,
        "phase6_authorized": False,
        "approval_granted": False,
        "approval_denied": False,
        "revision_required": False,
        "external_action_performed": False,
        "generated_action_candidate": False,
    }


def procurement_classification(
    source_present: bool,
    action_state: Dict[str, Any],
    proposal_present: bool,
    authorization_present: bool,
) -> str:
    if not source_present and (proposal_present or authorization_present):
        return "generated_internal_chain_missing_source_snapshot"
    decision = action_state["phase5_decision"]
    if authorization_present and decision == "pending" and action_state["expired"]:
        return "real_source_with_expired_generated_action_candidate"
    if authorization_present and decision == "pending":
        return "real_source_with_pending_generated_action_candidate"
    if authorization_present and action_state["approval_granted"]:
        return "real_source_with_approved_generated_action_candidate"
    if authorization_present and action_state["approval_denied"]:
        return "real_source_with_denied_generated_action_candidate"
    if authorization_present and action_state["revision_required"]:
        return "real_source_with_revision_required_generated_action_candidate"
    if proposal_present:
        return "real_source_with_generated_internal_draft"
    return "real_source_no_generated_procurement_chain"


def procurement_decision(classification: str) -> str:
    decisions = {
        "generated_internal_chain_missing_source_snapshot": "quarantine_until_source_snapshot_is_verified",
        "real_source_with_expired_generated_action_candidate": "archive_or_regenerate_before_action",
        "real_source_with_pending_generated_action_candidate": "operator_review_required_before_action",
        "real_source_with_approved_generated_action_candidate": "phase6_scope_review_required_before_manual_handoff",
        "real_source_with_denied_generated_action_candidate": "retain_as_denied_historical_record",
        "real_source_with_revision_required_generated_action_candidate": "revise_generated_artifacts_before_action",
        "real_source_with_generated_internal_draft": "retain_source_snapshot_and_optionally_regenerate_approval",
        "real_source_no_generated_procurement_chain": "retain_source_snapshot_and_run_assessment_before_action",
    }
    return decisions.get(classification, "manual_operator_review_required")


def truth_warning(source_present: bool, action_state: Dict[str, Any]) -> str:
    if not source_present:
        return "Generated artifacts exist without a matched Phase 2 source snapshot. Treat as unverified internal derivatives."
    if action_state["phase5_decision"] == "pending" and action_state["expired"]:
        return "Phase 5 packet is pending but expired. It is not active approval authority."
    if action_state["approval_granted"]:
        return "Approval is recorded, but Phase 6 scope must still match exactly before action."
    return "Source and generated artifacts are truth-classified for internal review only."


def build_artifact_chain(
    paths: Dict[str, Any],
    source: Dict[str, Any],
    proposal: Dict[str, Any],
    authorization: Dict[str, Any],
    quality_record: Dict[str, Any],
    work_order_record: Dict[str, Any],
    action_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    chain: List[Dict[str, Any]] = []
    if source:
        chain.append(artifact_item(
            "phase2_opportunity_radar",
            str(source.get("opportunity_id", "")),
            str(paths.get("opportunities", "")),
            "source_evidence",
            str(source.get("radar_decision", "source_snapshot_present")),
        ))
    if proposal:
        chain.append(artifact_item(
            "phase4_proposal_drafting",
            str(proposal.get("proposal_id") or proposal.get("package_id", "")),
            str(paths.get("proposals", "")),
            "generated_internal_derivative",
            str(proposal.get("status", "internal_draft_only")),
        ))
    if authorization:
        auth_status = "expired_pending_generated_derivative" if action_state["expired"] and authorization.get("decision") == "pending" else str(authorization.get("decision", "generated_authorization_packet"))
        chain.append(artifact_item(
            "phase5_human_approval_gate",
            str(authorization.get("authorization_id", "")),
            str(paths.get("authorizations", "")),
            "generated_internal_derivative",
            auth_status,
        ))
    if quality_record:
        chain.append(artifact_item(
            "phase22_quantum_aware_quality_kernel",
            str(quality_record.get("record_id", "")),
            str(paths.get("quality_kernel_records", "")),
            "generated_internal_derivative",
            str(quality_record.get("status", "internal_quality_state_recorded")),
        ))
    if work_order_record:
        chain.append(artifact_item(
            "phase23_ascended_work_order_governor",
            str(work_order_record.get("record_id", "")),
            str(paths.get("work_order_governance_records", "")),
            "generated_internal_derivative",
            str(work_order_record.get("status", "internal_work_order_governance_recorded")),
        ))
    return chain


def artifact_item(phase: str, artifact_id: str, path: str, truth_role: str, status: str) -> Dict[str, str]:
    return {
        "phase": phase,
        "artifact_id": artifact_id,
        "path": path,
        "truth_role": truth_role,
        "status": status,
    }


def recommended_cleanup_actions(
    classification: str,
    source_present: bool,
    quality_present: bool,
    work_order_present: bool,
) -> List[str]:
    actions: List[str] = []
    if source_present:
        actions.append("Preserve the Phase 2 source snapshot as historical evidence.")
    else:
        actions.append("Quarantine generated derivatives until a matching Phase 2 source snapshot is verified.")
    if classification == "real_source_with_expired_generated_action_candidate":
        actions.extend([
            "Archive expired Phase 5 approval packets before any future approval attempt.",
            "Regenerate Phase 4 proposal and Phase 5 authorization from current source data before action.",
            "Refresh downstream generated artifacts after stale generated records are archived.",
        ])
    elif classification == "generated_internal_chain_missing_source_snapshot":
        actions.append("Do not use generated proposal or approval artifacts until source provenance is restored.")
    elif classification == "real_source_with_pending_generated_action_candidate":
        actions.append("Keep as pending only if the approval window is still active and operator review is intended.")
    elif classification == "real_source_with_generated_internal_draft":
        actions.append("Generate a fresh Phase 5 packet only after confirming the source is still current.")
    elif classification == "real_source_no_generated_procurement_chain":
        actions.append("Run assessment and proposal drafting before any approval packet is created.")
    if quality_present or work_order_present:
        actions.append("Treat Phase 22 and Phase 23 records as downstream internal quality derivatives, not source facts.")
    return unique(actions)


def count_expired_generated_candidates(records: List[ProcurementRecord]) -> int:
    return sum(
        1
        for record in records
        if record.procurement_classification == "real_source_with_expired_generated_action_candidate"
    )


def authorization_expired(packet: Dict[str, Any]) -> bool:
    value = packet.get("expires_at", "")
    if not value:
        return False
    try:
        expires_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at.astimezone(timezone.utc)


def make_record_id(opportunity_id: str, proposal_id: str, authorization_id: str, action_id: str) -> str:
    seed = f"{opportunity_id}|{proposal_id}|{authorization_id}|{action_id}|phase24"
    return "AIGC-PROC-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def group_by(records: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get(key, "")), []).append(record)
    return grouped


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def load_json_list_if_exists(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 24 truth-first procurement governance.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase24_procurement_governance.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = TruthFirstProcurementGovernance(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nProcurement records exported: {args.project_root / 'data' / 'phase24_procurement' / 'aigc_phase24_procurement_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
