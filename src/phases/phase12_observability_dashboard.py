from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.security.redaction_scanner import RedactionScanner


@dataclass
class PhaseHealth:
    phase: str
    status: str
    signal_count: int
    notes: List[str]


@dataclass
class SystemSnapshot:
    generated_at: str
    operator: str
    phase: str
    system_health: str
    health_reasons: List[str]
    phase_health: List[PhaseHealth]
    pipeline_metrics: Dict[str, int]
    approval_metrics: Dict[str, int]
    patch_metrics: Dict[str, int]
    secrets_privacy: Dict[str, Any]
    audit_integrity: Dict[str, Any]
    next_recommended_action: str
    external_action_performed: bool = False


class Phase12ObservabilityDashboard:
    PHASES = [
        "phase0_genesis_constitution",
        "phase1_domain_discovery",
        "phase2_opportunity_radar",
        "phase3_ology_assessment",
        "phase4_proposal_drafting",
        "phase5_human_approval_gate",
        "phase6_controlled_execution",
        "phase7_employer_audit_packet",
        "phase8_evolution_loop",
        "phase9_omega_x_memory_core",
        "phase10_connector_api_layer",
        "phase11_security_vault",
        "phase12_observability_dashboard",
        "phase13_simulation_arena",
        "phase14_deployment_runtime",
        "phase15_finance_contracts_asset_ledger",
        "phase16_compliance_legal_review",
        "phase17_incident_response",
        "phase18_scaling_productization",
        "phase19_subagent_generation_forge",
        "phase20_fidelity_forge",
        "phase21_customer_satisfaction_continuum",
        "phase22_quantum_aware_quality_kernel",
        "phase23_ascended_work_order_governor",
        "phase24_truth_first_procurement_governance",
        "phase25_continuous_intelligence_ingestion_layer",
        "phase26_ascended_capability_procurement_program",
        "phase27_stale_artifact_renewal_controller",
        "phase28_fresh_candidate_regeneration_controller",
        "phase29_operator_freshness_review_procurement",
        "phase30_omni_agent_cloud_intelligence_architecture_procurement",
    ]

    def __init__(self, root: Path, config_path: Path):
        self.root = root.resolve()
        self.config_path = config_path
        self.config = load_json_dict(config_path)
        self.scanner = RedactionScanner()

    def build_snapshot(self) -> SystemSnapshot:
        inputs = self.config.get("inputs", {})
        audit_dir = self.resolve(inputs.get("audit_dir", "data/audit"))
        audit_events = count_jsonl_dir(audit_dir)
        memory_events = count_jsonl_file(self.resolve(inputs.get("omega_memory_events", "")))
        phase2_count = count_json_list(self.resolve(inputs.get("phase2_queue", "")))
        phase3_count = count_json_list(self.resolve(inputs.get("phase3_dossiers", "")))
        phase4_count = count_json_list(self.resolve(inputs.get("phase4_proposals", "")))
        phase5_packets = load_json_list_if_exists(self.resolve(inputs.get("phase5_authorizations", "")))
        phase6_count = count_json_list(self.resolve(inputs.get("phase6_receipts", "")))
        phase7_count = count_json_list(self.resolve(inputs.get("phase7_packets", "")))
        phase8_patch_records = read_jsonl_records(self.resolve(inputs.get("phase8_patches", "")))
        phase13_synthetic_count = count_json_list(self.resolve(inputs.get("phase13_synthetic", "")))
        phase13_real_replay_count = count_replay_records(self.resolve(inputs.get("phase13_real_replay", "")))
        phase20_count = count_json_list(self.resolve(inputs.get("phase20_fidelity_reviews", "")))
        phase21_count = count_json_list(self.resolve(inputs.get("phase21_customer_satisfaction", "")))
        phase22_count = count_json_list(self.resolve(inputs.get("phase22_quality_records", "")))
        phase23_count = count_json_list(self.resolve(inputs.get("phase23_work_order_governance", "")))
        phase24_count = count_json_list(self.resolve(inputs.get("phase24_procurement_records", "")))
        phase25_count = count_json_list(self.resolve(inputs.get("phase25_intelligence_ingestion", "")))
        phase26_count = count_json_list(self.resolve(inputs.get("phase26_capability_procurement", "")))
        phase27_count = count_json_list(self.resolve(inputs.get("phase27_stale_artifact_renewal", "")))
        phase28_records = load_json_list_if_exists(self.resolve(inputs.get("phase28_regeneration_candidates", "")))
        phase29_records = load_json_list_if_exists(self.resolve(inputs.get("phase29_freshness_reviews", "")))
        phase30_count = count_json_list(self.resolve(inputs.get("phase30_omni_agent_architecture", "")))
        secret_manifest_exists = self.resolve(inputs.get("secret_manifest", "")).exists()
        external_secret_manifest_exists = self.resolve(inputs.get("external_secret_manifest", "")).exists()
        secret_findings = self.scan_secret_paths()
        approval_metrics = self.approval_metrics(phase5_packets)
        patch_metrics = self.patch_metrics(phase8_patch_records)
        pipeline_metrics = {
            "audit_events": audit_events,
            "memory_events": memory_events,
            "phase2_opportunities": phase2_count,
            "phase3_dossiers": phase3_count,
            "phase4_proposals": phase4_count,
            "phase5_authorizations": len(phase5_packets),
            "phase6_receipts": phase6_count,
            "phase7_packets": phase7_count,
            "phase8_patch_records": len(phase8_patch_records),
            "phase13_synthetic_records": phase13_synthetic_count,
            "phase13_real_replay_records": phase13_real_replay_count,
            "phase20_fidelity_reviews": phase20_count,
            "phase21_customer_satisfaction_records": phase21_count,
            "phase22_quality_kernel_records": phase22_count,
            "phase23_work_order_governance_records": phase23_count,
            "phase24_procurement_records": phase24_count,
            "phase25_intelligence_ingestion_records": phase25_count,
            "phase26_capability_procurement_records": phase26_count,
            "phase27_stale_artifact_renewal_records": phase27_count,
            "phase28_regeneration_candidate_records": len(phase28_records),
            "phase28_allowed_regeneration_candidates": sum(1 for item in phase28_records if item.get("regeneration_allowed") is True),
            "phase28_blocked_regeneration_candidates": sum(1 for item in phase28_records if item.get("regeneration_allowed") is False),
            "phase29_freshness_review_records": len(phase29_records),
            "phase29_approved_freshness_reviews": sum(1 for item in phase29_records if item.get("decision") == "approved_for_phase28_regeneration"),
            "phase29_pending_freshness_reviews": sum(1 for item in phase29_records if item.get("decision") == "pending"),
            "phase30_omni_agent_architecture_records": phase30_count,
        }
        audit_integrity = {
            "audit_dir_exists": audit_dir.exists(),
            "audit_events": audit_events,
            "memory_events": memory_events,
            "missing_audit_baseline": audit_events == 0,
            "missing_memory_baseline": memory_events == 0,
        }
        secrets_privacy = {
            "repo_secret_manifest_present": secret_manifest_exists,
            "external_secret_manifest_present": external_secret_manifest_exists,
            "secret_like_findings": len(secret_findings),
            "findings": [asdict(item) for item in secret_findings[:25]],
        }
        phase_health = self.phase_health(pipeline_metrics, secret_manifest_exists, external_secret_manifest_exists)
        system_health, reasons = self.system_health(
            pipeline_metrics=pipeline_metrics,
            approval_metrics=approval_metrics,
            patch_metrics=patch_metrics,
            secrets_privacy=secrets_privacy,
            audit_integrity=audit_integrity,
        )
        return SystemSnapshot(
            generated_at=utc_now(),
            operator="Justice Gray Maciocha",
            phase="Phase 12 - Observability Dashboard",
            system_health=system_health,
            health_reasons=reasons,
            phase_health=phase_health,
            pipeline_metrics=pipeline_metrics,
            approval_metrics=approval_metrics,
            patch_metrics=patch_metrics,
            secrets_privacy=secrets_privacy,
            audit_integrity=audit_integrity,
            next_recommended_action=self.next_action(system_health, approval_metrics, secrets_privacy, pipeline_metrics),
        )

    def export(self, snapshot: SystemSnapshot) -> None:
        outputs = self.config.get("outputs", {})
        snapshot_path = self.resolve(outputs.get("snapshot", "data/phase12_observability/system_snapshot.json"))
        report_path = self.resolve(outputs.get("report", "reports/phase12_system_health.md"))
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(render_markdown_report(snapshot), encoding="utf-8")

    def resolve(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.root / path).resolve()

    def scan_secret_paths(self):
        paths = [self.resolve(value) for value in self.config.get("secret_scan_paths", [])]
        return self.scanner.scan_paths(paths)

    def approval_metrics(self, packets: List[Dict[str, Any]]) -> Dict[str, int]:
        return {
            "pending": sum(1 for item in packets if item.get("decision") == "pending"),
            "expired_pending": sum(1 for item in packets if item.get("decision") == "pending" and authorization_expired(item)),
            "approved_for_phase6": sum(1 for item in packets if item.get("decision") == "approved_for_phase_6"),
            "denied": sum(1 for item in packets if item.get("decision") == "denied"),
            "revision_required": sum(1 for item in packets if item.get("decision") == "revision_required"),
            "blocked": sum(1 for item in packets if item.get("decision") == "blocked_by_safety"),
        }

    def patch_metrics(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        return {
            "pending": sum(1 for item in records if item.get("decision") == "pending"),
            "accepted": sum(1 for item in records if item.get("decision") == "accepted"),
            "denied": sum(1 for item in records if item.get("decision") == "denied"),
            "revision_required": sum(1 for item in records if item.get("decision") == "revision_required"),
            "blocked": sum(1 for item in records if item.get("decision") == "blocked"),
        }

    def phase_health(
        self,
        pipeline_metrics: Dict[str, int],
        secret_manifest_exists: bool,
        external_secret_manifest_exists: bool,
    ) -> List[PhaseHealth]:
        metric_by_phase = {
            "phase2_opportunity_radar": pipeline_metrics["phase2_opportunities"],
            "phase3_ology_assessment": pipeline_metrics["phase3_dossiers"],
            "phase4_proposal_drafting": pipeline_metrics["phase4_proposals"],
            "phase5_human_approval_gate": pipeline_metrics["phase5_authorizations"],
            "phase6_controlled_execution": pipeline_metrics["phase6_receipts"],
            "phase7_employer_audit_packet": pipeline_metrics["phase7_packets"],
            "phase8_evolution_loop": pipeline_metrics["phase8_patch_records"],
            "phase9_omega_x_memory_core": pipeline_metrics["memory_events"],
            "phase11_security_vault": int(secret_manifest_exists and external_secret_manifest_exists),
            "phase12_observability_dashboard": 1,
            "phase13_simulation_arena": pipeline_metrics["phase13_synthetic_records"] + pipeline_metrics["phase13_real_replay_records"],
            "phase20_fidelity_forge": pipeline_metrics["phase20_fidelity_reviews"],
            "phase21_customer_satisfaction_continuum": pipeline_metrics["phase21_customer_satisfaction_records"],
            "phase22_quantum_aware_quality_kernel": pipeline_metrics["phase22_quality_kernel_records"],
            "phase23_ascended_work_order_governor": pipeline_metrics["phase23_work_order_governance_records"],
            "phase24_truth_first_procurement_governance": pipeline_metrics["phase24_procurement_records"],
            "phase25_continuous_intelligence_ingestion_layer": pipeline_metrics["phase25_intelligence_ingestion_records"],
            "phase26_ascended_capability_procurement_program": pipeline_metrics["phase26_capability_procurement_records"],
            "phase27_stale_artifact_renewal_controller": pipeline_metrics["phase27_stale_artifact_renewal_records"],
            "phase28_fresh_candidate_regeneration_controller": pipeline_metrics["phase28_regeneration_candidate_records"],
            "phase29_operator_freshness_review_procurement": pipeline_metrics["phase29_freshness_review_records"],
            "phase30_omni_agent_cloud_intelligence_architecture_procurement": pipeline_metrics["phase30_omni_agent_architecture_records"],
        }
        results: List[PhaseHealth] = []
        for phase in self.PHASES:
            count = metric_by_phase.get(phase, 0)
            if phase == "phase12_observability_dashboard":
                status = "green"
                notes = ["Observability snapshot generated."]
            elif count > 0:
                status = "green"
                notes = ["Telemetry present."]
            elif phase in {"phase0_genesis_constitution", "phase1_domain_discovery", "phase10_connector_api_layer", "phase13_simulation_arena", "phase14_deployment_runtime", "phase15_finance_contracts_asset_ledger", "phase16_compliance_legal_review", "phase17_incident_response", "phase18_scaling_productization", "phase19_subagent_generation_forge", "phase20_fidelity_forge", "phase21_customer_satisfaction_continuum", "phase22_quantum_aware_quality_kernel", "phase23_ascended_work_order_governor", "phase24_truth_first_procurement_governance", "phase25_continuous_intelligence_ingestion_layer", "phase26_ascended_capability_procurement_program", "phase27_stale_artifact_renewal_controller", "phase28_fresh_candidate_regeneration_controller", "phase29_operator_freshness_review_procurement", "phase30_omni_agent_cloud_intelligence_architecture_procurement"}:
                status = "yellow"
                notes = ["No baseline telemetry found yet."]
            else:
                status = "yellow"
                notes = ["Phase exists in architecture; no current output signal found."]
            results.append(PhaseHealth(phase=phase, status=status, signal_count=count, notes=notes))
        return results

    def system_health(
        self,
        pipeline_metrics: Dict[str, int],
        approval_metrics: Dict[str, int],
        patch_metrics: Dict[str, int],
        secrets_privacy: Dict[str, Any],
        audit_integrity: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        reasons: List[str] = []
        if secrets_privacy["secret_like_findings"] > 0:
            reasons.append("Secret-like findings detected.")
            return "red", reasons
        if not secrets_privacy["repo_secret_manifest_present"] or not secrets_privacy["external_secret_manifest_present"]:
            reasons.append("Required secret manifest missing.")
            return "red", reasons
        if audit_integrity["missing_audit_baseline"]:
            reasons.append("No baseline audit events found.")
        if audit_integrity["missing_memory_baseline"]:
            reasons.append("No Omega-X memory events found.")
        if approval_metrics.get("expired_pending", 0) > 0:
            reasons.append(f"{approval_metrics['expired_pending']} pending approval packets are expired generated action candidates.")
        elif approval_metrics["pending"] > 0:
            reasons.append(f"{approval_metrics['pending']} approval packets pending.")
        if patch_metrics["pending"] > 0:
            reasons.append(f"{patch_metrics['pending']} evolution patches pending.")
        if not reasons:
            reasons.append("All monitored internal signals are healthy.")
            return "green", reasons
        return "yellow", reasons

    def next_action(
        self,
        system_health: str,
        approval_metrics: Dict[str, int],
        secrets_privacy: Dict[str, Any],
        pipeline_metrics: Dict[str, int],
    ) -> str:
        if system_health == "red":
            return "Resolve red health findings before running additional phases."
        if secrets_privacy["secret_like_findings"] > 0:
            return "Redact secret-like findings and rerun Phase 12."
        if approval_metrics.get("expired_pending", 0) > 0:
            if pipeline_metrics.get("phase29_pending_freshness_reviews", 0) > 0:
                return "Review Phase 29 freshness packets before allowing Phase 28 regeneration; do not approve or use expired Phase 5 packets."
            if pipeline_metrics.get("phase28_blocked_regeneration_candidates", 0) > 0:
                return "Run Phase 29 freshness review procurement before allowing Phase 28 regeneration; do not approve or use expired Phase 5 packets."
            if pipeline_metrics.get("phase28_allowed_regeneration_candidates", 0) > 0:
                return "Review the fresh Phase 28 internal candidates; any Phase 5 candidate still needs separate exact-phrase approval before Phase 6."
            return "Run Phase 27 renewal, then Phase 28 regeneration gating before replacing expired Phase 5 candidates."
        if approval_metrics["pending"] > 0:
            return "Review pending Phase 5 approval packets before Phase 6 handoff."
        return "Run Phase 13 simulation or continue the next internal AIGC cycle."


def render_markdown_report(snapshot: SystemSnapshot) -> str:
    phase_rows = "\n".join(
        f"- {item.phase}: {item.status} ({item.signal_count}) - {'; '.join(item.notes)}"
        for item in snapshot.phase_health
    )
    return f"""
# AIGC Phase 12 System Health

Generated At:
{snapshot.generated_at}

Operator:
{snapshot.operator}

System Health:
{snapshot.system_health}

Health Reasons:
{bullets(snapshot.health_reasons)}

Pipeline Metrics:
```json
{json.dumps(snapshot.pipeline_metrics, indent=2)}
```

Approval Metrics:
```json
{json.dumps(snapshot.approval_metrics, indent=2)}
```

Patch Metrics:
```json
{json.dumps(snapshot.patch_metrics, indent=2)}
```

Secrets / Privacy:
```json
{json.dumps(snapshot.secrets_privacy, indent=2)}
```

Audit Integrity:
```json
{json.dumps(snapshot.audit_integrity, indent=2)}
```

Phase Health:
{phase_rows}

AIGC Signature Update

Phase:
Phase 12 - Observability Dashboard

Approval Required:
No approval required for internal monitoring.

External Action Performed:
No.

Next Recommended Action:
{snapshot.next_recommended_action}
""".strip() + "\n"


def bullets(items: List[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def count_jsonl_dir(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(count_jsonl_file(item) for item in path.glob("*.jsonl"))


def count_jsonl_file(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def read_jsonl_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
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


def count_json_list(path: Path) -> int:
    return len(load_json_list_if_exists(path))


def count_replay_records(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return len(payload["records"])
    return 0


def load_json_list_if_exists(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def load_json_dict(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Run AIGC Phase 12 observability dashboard.")
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase12_observability_dashboard.json")
    parser.add_argument("--export", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dashboard = Phase12ObservabilityDashboard(root=args.root, config_path=args.config)
    snapshot = dashboard.build_snapshot()
    if args.export:
        dashboard.export(snapshot)
    print(render_markdown_report(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
