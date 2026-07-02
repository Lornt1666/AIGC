from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.core.contract_validator import ContractValidationError, validate_file
from src.core.state_store import AIGCStateStore
from src.phase6_controlled_execution import ControlledExecutionEngine, ExecutionMode
from src.phase7_employer_audit_packet import EmployerAuditPacketBuilder


@dataclass
class PipelineClosureResult:
    closure_id: str
    created_at: str
    status: str
    execution_mode: str
    authorization_counts: Dict[str, int]
    phase6_receipts_created: int
    phase7_packets_created: int
    validation_failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    external_action_performed: bool = False
    report_path: str = ""
    summary_path: str = ""


class PipelineClosureRunner:
    """
    Internal-only closure runner for Milestone C.

    It does not approve actions, contact recipients, use credentials, or perform
    external execution. It only processes already-approved Phase 5 packets
    through Phase 6 handoff/dry-run and Phase 7 internal audit drafts.
    """

    def __init__(self, project_root: Path, store: AIGCStateStore | None = None):
        self.project_root = project_root
        self.store = store

    def run(self, execution_mode: str = ExecutionMode.MANUAL_HANDOFF.value) -> PipelineClosureResult:
        if execution_mode not in {ExecutionMode.DRY_RUN.value, ExecutionMode.MANUAL_HANDOFF.value}:
            raise ValueError("Milestone C closure allows only dry_run or manual_handoff.")

        phase6_config = self.project_root / "config" / "phase6_controlled_execution.json"
        phase7_config = self.project_root / "config" / "phase7_employer_audit_packet.json"
        authorization_path = self.project_root / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json"
        receipt_path = self.project_root / "data" / "phase6_execution" / "aigc_phase6_execution_receipts.json"
        audit_packet_path = self.project_root / "data" / "phase7_audit_packets" / "aigc_phase7_employer_audit_packets.json"

        authorizations = _load_json_list(authorization_path)
        counts = count_authorizations(authorizations)
        warnings = build_authorization_warnings(counts)

        phase6_results = ControlledExecutionEngine(self.project_root).run_from_config(
            phase6_config,
            execution_mode_override=execution_mode,
        )
        phase7_packets = EmployerAuditPacketBuilder(self.project_root).run_from_config(phase7_config)

        failures: List[str] = []
        for schema_name, path in [
            ("authorization_packet", authorization_path),
            ("execution_receipt", receipt_path),
            ("employer_audit_packet", audit_packet_path),
        ]:
            try:
                validate_file(schema_name, path)
            except (ContractValidationError, FileNotFoundError) as exc:
                failures.append(str(exc))

        status = closure_status(counts, phase6_results, phase7_packets, failures)
        result = PipelineClosureResult(
            closure_id=f"AIGC-CLOSURE-{uuid.uuid4()}",
            created_at=utc_now(),
            status=status,
            execution_mode=execution_mode,
            authorization_counts=counts,
            phase6_receipts_created=len(phase6_results),
            phase7_packets_created=len(phase7_packets),
            validation_failures=failures,
            warnings=warnings,
            external_action_performed=False,
        )
        write_outputs(self.project_root, result)

        if self.store is not None:
            self.store.insert_event(
                event_type="milestone_c_pipeline_closure_run",
                phase="phase14_runtime_engine",
                status=status,
                summary="Ran internal Phase 5 to Phase 7 closure check.",
                data=asdict(result),
                external_action_performed=False,
            )
            self.store.insert_artifact_record(
                table="executions",
                record_id=result.closure_id,
                phase="phase14_runtime_engine",
                status=status,
                source_file=result.summary_path,
                data=asdict(result),
                risk_level="none_internal_only",
                approval_status="no_new_approval_granted",
            )
        return result


def count_authorizations(authorizations: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "total": len(authorizations),
        "pending": 0,
        "approved_for_phase_6": 0,
        "denied": 0,
        "revision_required": 0,
        "blocked_by_safety": 0,
        "expired": 0,
        "approved_but_expired": 0,
        "authorized_for_phase6": 0,
    }
    now = datetime.now(timezone.utc)
    for packet in authorizations:
        decision = str(packet.get("decision", "pending"))
        if decision in counts:
            counts[decision] += 1
        expires_at = parse_datetime(packet.get("expires_at", ""))
        is_expired = bool(expires_at and now > expires_at)
        if is_expired:
            counts["expired"] += 1
            if decision == "approved_for_phase_6":
                counts["approved_but_expired"] += 1
        if (packet.get("phase6_status") or {}).get("authorized_for_phase6", False):
            counts["authorized_for_phase6"] += 1
    return counts


def build_authorization_warnings(counts: Dict[str, int]) -> List[str]:
    warnings: List[str] = []
    if counts["pending"]:
        warnings.append(f"{counts['pending']} authorization packet(s) are still pending.")
    if counts["approved_but_expired"]:
        warnings.append(f"{counts['approved_but_expired']} approved packet(s) are expired and will block in Phase 6.")
    if counts["authorized_for_phase6"] == 0:
        warnings.append("No packets are currently authorized for Phase 6.")
    return warnings


def closure_status(
    counts: Dict[str, int],
    phase6_results: List[Any],
    phase7_packets: List[Any],
    failures: List[str],
) -> str:
    if failures:
        return "validation_failed"
    if counts["approved_but_expired"]:
        return "blocked_expired_authorization"
    if not phase6_results:
        return "no_approved_actions"
    if any(getattr(result, "status", "") == "blocked" for result in phase6_results):
        return "blocked"
    if phase7_packets:
        return "phase7_internal_drafts_ready"
    return "phase6_receipts_ready"


def write_outputs(project_root: Path, result: PipelineClosureResult) -> None:
    data_dir = project_root / "data" / "phase14_pipeline_closure"
    report_dir = project_root / "reports"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = data_dir / "latest_pipeline_closure.json"
    report_path = report_dir / "milestone_c_pipeline_closure_report.md"
    result.summary_path = str(summary_path)
    result.report_path = str(report_path)
    summary_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")


def render_report(result: PipelineClosureResult) -> str:
    counts = "\n".join(f"- {key}: {value}" for key, value in result.authorization_counts.items())
    warnings = "\n".join(f"- {item}" for item in result.warnings) if result.warnings else "- None"
    failures = "\n".join(f"- {item}" for item in result.validation_failures) if result.validation_failures else "- None"
    return f"""# Milestone C Pipeline Closure Report

Generated At: {result.created_at}

Closure ID: {result.closure_id}

Status: {result.status}

Execution Mode: {result.execution_mode}

External Action Performed: No

## Authorization Counts

{counts}

## Phase Outputs

- Phase 6 receipts created: {result.phase6_receipts_created}
- Phase 7 packets created: {result.phase7_packets_created}

## Warnings

{warnings}

## Validation Failures

{failures}

## Safety Boundary

- No proposal sent.
- No application submitted.
- No employer contacted.
- No credentials used.
- No external execution performed.
- Only already-approved Phase 5 packets can reach Phase 6.

## Next Recommended Action

Approve, deny, revise, or refresh expired Phase 5 packets before expecting Phase 6 manual handoffs or Phase 7 employer audit drafts.
"""


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

