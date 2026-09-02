from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.contract_validator import (  # noqa: E402
    ContractValidationError,
    list_schema_names,
    validate_file,
    validate_jsonl_file,
)
from src.core.aigc_master_curriculum import (  # noqa: E402
    AIGCMasterCurriculumError,
    load_aigc_master_curriculum,
    summarize_aigc_master_curriculum,
)
from src.core.paycheque_workflow import run_paycheque_workflow  # noqa: E402
from src.core.phase_registry import build_phase_registry  # noqa: E402
from src.core.phase2_to5_cycle_policy import (  # noqa: E402
    Phase2To5CyclePolicyError,
    load_phase2_to5_cycle_policy,
    next_cycle_policy_snapshot,
    packet_was_generated_by_authorized_native_cycle,
    require_phase2_to5_generation_authorized,
)
from src.core.pipeline_closure import PipelineClosureRunner  # noqa: E402
from src.core.program_health import run_program_health, write_health_report  # noqa: E402
from src.core.production_readiness_ledger import run_production_readiness_ledger  # noqa: E402
from src.core.state_store import AIGCStateStore, DEFAULT_DB_PATH  # noqa: E402
from src.core.work_acquisition import run_work_acquisition  # noqa: E402
from src.core.work_order import run_cockpit_smoke, run_governance_smoke, run_work_order  # noqa: E402
from src.phase17_incident_response import Phase17IncidentResponse  # noqa: E402
from src.phase6_controlled_execution import (  # noqa: E402
    ManualHandoffConfirmationError,
    record_manual_handoff_confirmation,
)
from src.security.approval_tokens import ApprovalTokenStore  # noqa: E402


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    state_db = args.state_db or root / DEFAULT_DB_PATH.relative_to(PROJECT_ROOT)
    store = AIGCStateStore(state_db)

    if args.command == "init-db":
        store.insert_event(
            event_type="state_db_initialized",
            phase="phase14_runtime_engine",
            status="completed",
            summary="AIGC state database initialized.",
        )
        print(json.dumps(store.get_status_summary(), indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(store.get_status_summary(), indent=2))
        return 0
    if args.command == "health":
        report = run_program_health(root)
        payload = report.to_dict()
        if args.write:
            path = write_health_report(root)
            payload["written_report_path"] = str(path)
        store.insert_event(
            event_type="local_program_health_check",
            phase="local_program_runtime",
            status=report.overall_status,
            summary=f"Local program health status: {report.overall_status}.",
            data={
                "overall_status": report.overall_status,
                "external_actions_enabled": report.external_actions_enabled,
                "safe_mode_default": report.safe_mode_default,
            },
            external_action_performed=False,
        )
        print(json.dumps(payload, indent=2))
        return 0 if report.overall_status in {"healthy", "warning"} else 1
    if args.command == "readiness":
        result = run_production_readiness_ledger(root, artifact_root=args.artifact_root)
        report = result["report"]
        store.insert_event(
            event_type="production_readiness_evaluated",
            phase="production_readiness_ledger",
            status="production_ready" if report["production_ready"] else "not_production_ready",
            summary=(
                f"Evaluated structural production readiness at {report['overall_score']} "
                f"against threshold {report['production_readiness_threshold']}."
            ),
            data={
                "report_id": report["report_id"],
                "source_revision": report["source_revision"],
                "evidence_strength": report["evidence_strength"],
                "blocking_gaps": report["blocking_gaps"],
                "production_ready": report["production_ready"],
            },
            external_action_performed=False,
        )
        print(json.dumps(result, indent=2))
        if args.require_production_ready and not report["production_ready"]:
            return 3
        return 0
    if args.command == "cycle-policy":
        try:
            policy = load_phase2_to5_cycle_policy(root)
            print(json.dumps(next_cycle_policy_snapshot(policy), indent=2))
            return 0
        except Phase2To5CyclePolicyError as exc:
            print(f"Phase 2–5 cycle policy is invalid: {exc}")
            return 2
    if args.command == "curriculum":
        try:
            curriculum = load_aigc_master_curriculum(root)
            print(json.dumps(summarize_aigc_master_curriculum(curriculum), indent=2))
            return 0
        except AIGCMasterCurriculumError as exc:
            print(f"Master curriculum is invalid: {exc}")
            return 2
    if args.command == "validate":
        return command_validate(args, root, store)
    if args.command == "run":
        return command_run(args, root, store)
    if args.command == "approve":
        return command_authorization_decision(args, root, store, "approve")
    if args.command == "deny":
        return command_authorization_decision(args, root, store, "deny")
    if args.command == "revise":
        return command_authorization_decision(args, root, store, "revise")
    if args.command == "confirm-manual-handoff":
        return command_manual_handoff_confirmation(args, root, store)
    if args.command == "close-loop":
        runner = PipelineClosureRunner(root, store)
        result = runner.run(execution_mode=args.execution_mode)
        print(json.dumps(asdict(result), indent=2))
        return 1 if result.validation_failures else 0
    if args.command == "create-incident":
        payload = Phase17IncidentResponse(root).run_from_config(
            config_path=root / "config" / "phase17_incident_response.json",
            incident_type=args.incident_type,
            severity=args.severity,
            summary=args.summary,
            evidence=json.loads(args.evidence_json),
        )
        store.insert_event(
            event_type="incident_report_created",
            phase="phase17_incident_response",
            status="open_internal_review",
            summary=args.summary,
            data=payload,
            external_action_performed=False,
        )
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "emergency-stop":
        store.set_flag("emergency_stop", "true")
        store.insert_event(
            event_type="emergency_stop_enabled",
            phase="phase14_runtime_engine",
            status="blocked",
            summary="Emergency stop enabled by operator command.",
        )
        print("Emergency stop enabled. Runtime phase execution is blocked.")
        return 0
    if args.command == "clear-emergency-stop":
        store.set_flag("emergency_stop", "false")
        store.insert_event(
            event_type="emergency_stop_cleared",
            phase="phase14_runtime_engine",
            status="recorded",
            summary="Emergency stop cleared by operator command.",
        )
        print("Emergency stop cleared.")
        return 0
    if args.command == "report":
        return run_subprocess([sys.executable, str(root / "src" / "phase12_observability_dashboard.py"), "--root", str(root), "--export"], root)
    if args.command == "issue-approval-token":
        token_store = ApprovalTokenStore(root / args.token_store)
        issued = token_store.issue_token(
            scope=args.scope,
            phase=args.phase,
            reason=args.reason,
            ttl_minutes=args.ttl_minutes,
            one_time=not args.reusable,
        )
        store.insert_event(
            event_type="approval_token_issued",
            phase=args.phase,
            status="created",
            summary=f"Issued scoped approval token for {args.scope}.",
            data={
                "token_id": issued.record.token_id,
                "scope": issued.record.scope,
                "expires_at": issued.record.expires_at,
                "raw_token_logged": False,
            },
        )
        print(json.dumps({
            "token": issued.token,
            "token_id": issued.record.token_id,
            "scope": issued.record.scope,
            "phase": issued.record.phase,
            "expires_at": issued.record.expires_at,
            "store": str(root / args.token_store),
            "raw_token_stored": False,
        }, indent=2))
        return 0
    raise ValueError(f"Unhandled command: {args.command}")


def command_validate(args: argparse.Namespace, root: Path, store: AIGCStateStore) -> int:
    results: List[Dict[str, Any]] = []
    failures: List[str] = []
    if args.schema and args.path:
        targets = [(args.schema, root / args.path)]
        jsonl_targets: List[tuple[str, Path]] = []
    else:
        registry = build_phase_registry(root)
        targets = [
            ("secret_manifest", root / "config" / "secret_manifest.json"),
            ("work_order_packet", root / "config" / "example_work_order.json"),
            ("paycheque_workflow_config", root / "config" / "paycheque_workflow.json"),
            ("phase2_to5_cycle_policy", root / "config" / "phase2_to5_cycle_policy.json"),
            ("aigc_master_curriculum", root / "config" / "aigc_master_curriculum.json"),
            (registry["phase2"].schema_name, root / registry["phase2"].output_path),
            (registry["phase3"].schema_name, root / registry["phase3"].output_path),
            (registry["phase4"].schema_name, root / registry["phase4"].output_path),
            (registry["phase5"].schema_name, root / registry["phase5"].output_path),
            (registry["phase6"].schema_name, root / registry["phase6"].output_path),
            (registry["phase7"].schema_name, root / registry["phase7"].output_path),
            (registry["phase10"].schema_name, root / registry["phase10"].output_path),
            (registry["phase15"].schema_name, root / registry["phase15"].output_path),
            (registry["phase16"].schema_name, root / registry["phase16"].output_path),
            (registry["phase18"].schema_name, root / registry["phase18"].output_path),
            (registry["phase19"].schema_name, root / registry["phase19"].output_path),
            (registry["phase20"].schema_name, root / registry["phase20"].output_path),
            (registry["phase21"].schema_name, root / registry["phase21"].output_path),
            (registry["phase22"].schema_name, root / registry["phase22"].output_path),
            (registry["phase23"].schema_name, root / registry["phase23"].output_path),
            (registry["phase24"].schema_name, root / registry["phase24"].output_path),
            (registry["phase25"].schema_name, root / registry["phase25"].output_path),
            (registry["phase26"].schema_name, root / registry["phase26"].output_path),
        ]
        jsonl_targets = [
            ("outcome_record", root / "data" / "phase8_evolution" / "outcome_records.jsonl"),
            ("evolution_patch", root / "data" / "phase8_evolution" / "evolution_patches.jsonl"),
            ("incident_report", root / "data" / "phase17_incidents" / "incident_reports.jsonl"),
            (
                "manual_handoff_confirmation",
                root / "data" / "phase6_execution" / "aigc_phase6_manual_handoff_confirmations.jsonl",
            ),
        ]

    for schema_name, path in jsonl_targets:
        if not path.exists():
            continue
        try:
            result = validate_jsonl_file(schema_name, path)
            results.append(asdict(result))
        except (ContractValidationError, FileNotFoundError) as exc:
            failures.append(str(exc))

    for schema_name, path in targets:
        if not path.exists():
            continue
        try:
            result = validate_file(schema_name, path)
            results.append(asdict(result))
        except (ContractValidationError, FileNotFoundError) as exc:
            failures.append(str(exc))

    schema_names = list_schema_names(root / "schemas")
    store.insert_event(
        event_type="contract_validation_run",
        phase="phase14_runtime_engine",
        status="failed" if failures else "completed",
        summary=f"Validated {len(results)} artifact targets against {len(schema_names)} schemas.",
        data={"results": results, "failures": failures, "schemas": schema_names},
    )
    print(json.dumps({"valid": not failures, "results": results, "failures": failures}, indent=2))
    return 1 if failures else 0


def command_run(args: argparse.Namespace, root: Path, store: AIGCStateStore) -> int:
    phase = args.phase.lower()
    if store.emergency_stop_active() and phase != "phase14":
        print("Emergency stop is active. Phase execution is blocked until clear-emergency-stop is run.")
        store.insert_event(
            event_type="phase_run_blocked_by_emergency_stop",
            phase=phase,
            status="blocked",
            summary=f"Blocked attempted run of {phase}.",
        )
        return 2
    if phase in {"phase2", "phase3", "phase4", "phase5"}:
        try:
            require_phase2_to5_generation_authorized(root, phase.replace("phase", "Phase "))
        except Phase2To5CyclePolicyError as exc:
            print(str(exc))
            store.insert_event(
                event_type="phase_run_blocked_by_cycle_policy",
                phase=phase,
                status="blocked",
                summary=f"Blocked attempted {phase} generation under the active read-only hold.",
                data={"reason": str(exc)},
                external_action_performed=False,
            )
            return 2

    if phase == "work-order":
        result = run_work_order(root, args.input or root / "config" / "example_work_order.json", args.artifact_root)
        store.insert_event(
            event_type="governed_work_order_run_completed",
            phase="work_order_execution_slice",
            status=result.run_receipt.status,
            summary=f"Generated governed work-order artifacts for {result.run_receipt.work_order_id}.",
            data={"run_receipt": asdict(result.run_receipt)},
            external_action_performed=False,
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    if phase == "paycheque":
        payload = run_paycheque_workflow(root, args.input or root / "config" / "paycheque_workflow.json", args.artifact_root)
        store.insert_event(
            event_type="paycheque_pipeline_prepared",
            phase="paycheque_workflow",
            status="prepared_internal_only",
            summary="Prepared paycheque pipeline with review/copy/open/mark-done controls only.",
            data={
                "pipeline_path": payload.get("pipeline_path", ""),
                "report_path": payload.get("report_path", ""),
                "audit_receipt_path": payload.get("audit_receipt_path", ""),
            },
            external_action_performed=False,
        )
        print(json.dumps(payload, indent=2))
        return 0
    if phase == "work-acquisition":
        payload = run_work_acquisition(root, args.registry, args.profile, args.artifact_root)
        store.insert_event(
            event_type="work_acquisition_packet_prepared",
            phase="work_acquisition_performance_engine",
            status="prepared_internal_only",
            summary="Prepared work-acquisition and work-performance packets with external commitments blocked.",
            data={
                "acquisition_path": payload.get("acquisition_path", ""),
                "performance_path": payload.get("performance_path", ""),
                "report_path": payload.get("report_path", ""),
            },
            external_action_performed=False,
        )
        print(json.dumps(payload, indent=2))
        return 0
    if phase == "governance-smoke":
        result = run_governance_smoke(root)
        store.insert_event(
            event_type="governance_smoke_completed",
            phase="work_order_execution_slice",
            status=result.run_receipt.status,
            summary="Governance smoke generated work-order artifacts with external actions blocked.",
            data={"run_receipt": asdict(result.run_receipt)},
            external_action_performed=False,
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    if phase == "cockpit-smoke":
        payload = run_cockpit_smoke(root)
        store.insert_event(
            event_type="cockpit_smoke_completed",
            phase="work_order_execution_slice",
            status=str(payload.get("status", "completed")),
            summary="Cockpit smoke verified local cockpit path and work-order dry-run path.",
            data=payload,
            external_action_performed=False,
        )
        print(json.dumps(payload, indent=2))
        return 0
    if phase == "pipeline":
        return run_pipeline(args, root, store)
    if phase == "phase12":
        command = [sys.executable, str(root / "src" / "phase12_observability_dashboard.py"), "--root", str(root), "--export"]
        status = run_subprocess(command, root)
    elif phase == "phase13":
        if args.mode == "real":
            command = [
                sys.executable,
                str(root / "src" / "phase13_real_data_replay.py"),
                "--root",
                str(root),
                "--source",
                args.source,
                "--limit",
                str(args.limit),
            ]
        else:
            command = [sys.executable, str(root / "src" / "phase13_simulation_arena.py"), "--root", str(root)]
        status = run_subprocess(command, root)
    elif phase == "phase14":
        return run_phase14_preflight(root, store)
    elif phase == "phase10":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "phase10_connector_registry.py"),
            "--project-root",
            str(root),
            "--config",
            str(root / "config" / "phase10_connector_registry.json"),
        ]
        status = run_subprocess(command, root)
    elif phase == "phase18":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "phase18_productization.py"),
            "--project-root",
            str(root),
            "--config",
            str(root / "config" / "phase18_productization.json"),
        ]
        status = run_subprocess(command, root)
    elif phase == "phase19":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "phase19_subagent_forge.py"),
            "--project-root",
            str(root),
            "--config",
            str(root / "config" / "phase19_subagent_forge.json"),
        ]
        status = run_subprocess(command, root)
    elif phase == "phase20":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "phase20_fidelity_forge.py"),
            "--project-root",
            str(root),
            "--config",
            str(root / "config" / "phase20_fidelity_forge.json"),
        ]
        status = run_subprocess(command, root)
    elif phase == "phase21":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "phase21_customer_satisfaction_continuum.py"),
            "--project-root",
            str(root),
            "--config",
            str(root / "config" / "phase21_customer_satisfaction_continuum.json"),
        ]
        status = run_subprocess(command, root)
    elif phase == "phase22":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "phase22_quantum_quality_kernel.py"),
            "--project-root",
            str(root),
            "--config",
            str(root / "config" / "phase22_quantum_quality_kernel.json"),
        ]
        status = run_subprocess(command, root)
    elif phase == "phase23":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "phase23_work_order_governor.py"),
            "--project-root",
            str(root),
            "--config",
            str(root / "config" / "phase23_work_order_governor.json"),
        ]
        status = run_subprocess(command, root)
    elif phase == "phase24":
        command = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "phase24_autonomic_business_pipeline.py"),
            "--project-root",
            str(root),
            "--config",
            str(root / "config" / "phase24_autonomic_business_pipeline.json"),
        ]
        status = run_subprocess(command, root)
    else:
        registry = build_phase_registry(root)
        if phase not in registry:
            print(f"Unknown runnable phase: {phase}")
            return 2
        status = run_subprocess(registry[phase].command, root)

    store.insert_event(
        event_type="phase_run_completed" if status == 0 else "phase_run_failed",
        phase=phase,
        status="completed" if status == 0 else "failed",
        summary=f"CLI run {phase} exited with status {status}.",
        external_action_performed=False,
    )
    return status


def run_pipeline(args: argparse.Namespace, root: Path, store: AIGCStateStore) -> int:
    preflight_status = run_phase14_preflight(root, store)
    if preflight_status != 0:
        return preflight_status
    validate_args = argparse.Namespace(schema="", path="")
    validation_status = command_validate(validate_args, root, store)
    if validation_status != 0:
        return validation_status
    mode = "real" if args.mode in {"real", "real_data_read_only"} else "synthetic"
    phase13_args = argparse.Namespace(
        phase="phase13",
        mode=mode,
        source=args.source,
        limit=args.limit,
    )
    phase13_status = command_run(phase13_args, root, store)
    if phase13_status != 0:
        return phase13_status
    phase12_args = argparse.Namespace(phase="phase12", mode="synthetic", source=args.source, limit=args.limit)
    return command_run(phase12_args, root, store)


def command_authorization_decision(
    args: argparse.Namespace,
    root: Path,
    store: AIGCStateStore,
    decision: str,
) -> int:
    if decision == "approve" and store.emergency_stop_active():
        print("Emergency stop is active. Approval is blocked until clear-emergency-stop is run.")
        store.insert_event(
            event_type="authorization_approval_blocked_by_emergency_stop",
            phase="phase5_human_approval_gate",
            status="blocked",
            summary=f"Blocked approval for action {args.action_id}.",
        )
        return 2
    packet_path = Path(args.authorizations_path)
    if not packet_path.is_absolute():
        packet_path = root / packet_path
    if not packet_path.exists():
        print(f"Authorization packet file not found: {packet_path}")
        return 2
    packets = json.loads(packet_path.read_text(encoding="utf-8"))
    if not isinstance(packets, list):
        print("Authorization packet file must contain a JSON list.")
        return 2
    target = None
    for packet in packets:
        if isinstance(packet, dict) and packet.get("action_id") == args.action_id:
            target = packet
            break
    if target is None:
        print(f"Action ID not found: {args.action_id}")
        return 2
    if target.get("decision") != "pending":
        store.insert_event(
            event_type="authorization_decision_rejected",
            phase="phase5_human_approval_gate",
            status="blocked",
            summary=(
                f"Rejected {decision} for action {args.action_id}; "
                "authorization is no longer pending."
            ),
        )
        print(
            "Authorization is no longer pending. Existing approval history and "
            "consumption state cannot be replaced."
        )
        return 2
    approval = target.setdefault("approval", {})
    if decision == "revise":
        expected_prefix = f"Revise action {args.action_id}:"
        if not args.phrase.strip().startswith(expected_prefix) or not args.phrase.strip()[len(expected_prefix):].strip():
            store.insert_event(
                event_type="authorization_decision_rejected",
                phase="phase5_human_approval_gate",
                status="blocked",
                summary=f"Rejected revision for action {args.action_id}; revision phrase mismatch.",
            )
            print("Revision phrase mismatch. No authorization state changed.")
            print(f"Required prefix: {expected_prefix}")
            return 2
    else:
        expected_phrase = approval.get("required_phrase" if decision == "approve" else "denial_phrase", "")
        if args.phrase.strip() != expected_phrase:
            store.insert_event(
                event_type="authorization_decision_rejected",
                phase="phase5_human_approval_gate",
                status="blocked",
                summary=f"Rejected {decision} for action {args.action_id}; exact phrase mismatch.",
            )
            print("Decision phrase mismatch. No authorization state changed.")
            print(f"Required phrase: {expected_phrase}")
            return 2
    if decision == "approve" and authorization_expired(target):
        store.insert_event(
            event_type="authorization_decision_rejected",
            phase="phase5_human_approval_gate",
            status="blocked",
            summary=f"Rejected approval for action {args.action_id}; authorization expired.",
        )
        print("Authorization expired. Return to Phase 5 for a fresh approval packet.")
        return 2
    if decision == "approve":
        try:
            cycle_policy = load_phase2_to5_cycle_policy(root)
        except Phase2To5CyclePolicyError as exc:
            print(f"Cannot evaluate Phase 2–5 cycle policy: {exc}")
            return 2
        if (
            cycle_policy.get("active_hold", {}).get("enabled", False)
            and not packet_was_generated_by_authorized_native_cycle(cycle_policy, target)
        ):
            store.insert_event(
                event_type="authorization_approval_blocked_by_cycle_policy",
                phase="phase5_human_approval_gate",
                status="blocked",
                summary=(
                    f"Blocked approval for action {args.action_id}; it was not generated "
                    "by the authorized native review workflow."
                ),
                external_action_performed=False,
            )
            print(
                "Approval is blocked by the active read-only hold. Only a fresh packet "
                "generated by the separately authorized native Phase 2–5 review workflow "
                "can be accepted."
            )
            return 2
    approval["received_phrase"] = args.phrase.strip()
    if decision == "approve":
        approval["approved"] = True
        approval["denied"] = False
        approval["revision_required"] = False
        approval["approved_at"] = utc_now()
        approval["decision_notes"] = "Approved through unified CLI exact-phrase gate."
        target["decision"] = "approved_for_phase_6"
        phase6_status = target.setdefault("phase6_status", {})
        phase6_status["authorized_for_phase6"] = True
        phase6_status["external_action_performed"] = False
        event_type = "authorization_approved_for_phase6"
        status = "approved_for_phase_6"
    elif decision == "deny":
        approval["approved"] = False
        approval["denied"] = True
        approval["revision_required"] = False
        approval["decision_notes"] = "Denied through unified CLI exact-phrase gate."
        target["decision"] = "denied"
        phase6_status = target.setdefault("phase6_status", {})
        phase6_status["authorized_for_phase6"] = False
        phase6_status["external_action_performed"] = False
        event_type = "authorization_denied"
        status = "denied"
    else:
        approval["approved"] = False
        approval["denied"] = False
        approval["revision_required"] = True
        approval["decision_notes"] = args.phrase.strip().split(":", 1)[1].strip()
        target["decision"] = "revision_required"
        phase6_status = target.setdefault("phase6_status", {})
        phase6_status["authorized_for_phase6"] = False
        phase6_status["external_action_performed"] = False
        event_type = "authorization_revision_required"
        status = "revision_required"
    packet_path.write_text(json.dumps(packets, ensure_ascii=False, indent=2), encoding="utf-8")
    validate_file("authorization_packet", packet_path)
    event = store.insert_event(
        event_type=event_type,
        phase="phase5_human_approval_gate",
        status=status,
        summary=f"Recorded {decision} decision for action {args.action_id}.",
        data={
            "action_id": args.action_id,
            "authorization_id": target.get("authorization_id", ""),
            "proposal_id": target.get("proposal_id", ""),
            "packet_path": str(packet_path),
        },
        external_action_performed=False,
    )
    print(json.dumps({
        "action_id": args.action_id,
        "decision": target["decision"],
        "event_id": event.event_id,
        "external_action_performed": False,
    }, indent=2))
    return 0


def command_manual_handoff_confirmation(
    args: argparse.Namespace,
    root: Path,
    store: AIGCStateStore,
) -> int:
    try:
        confirmation = record_manual_handoff_confirmation(
            project_root=root,
            execution_id=args.execution_id,
            confirmation_phrase=args.phrase,
            completion_reference=args.completion_reference,
            config_path=root / args.phase6_config,
        )
    except (ManualHandoffConfirmationError, FileNotFoundError, ValueError) as exc:
        print(f"Manual handoff confirmation was not recorded: {exc}")
        return 2
    event = store.insert_event(
        event_type="phase6_manual_handoff_confirmation_recorded",
        phase="phase6_controlled_execution",
        status="recorded",
        summary=(
            f"Recorded operator confirmation for manual handoff {confirmation['execution_id']}; "
            "AIGC did not perform the external action."
        ),
        data={
            "confirmation_id": confirmation["confirmation_id"],
            "execution_id": confirmation["execution_id"],
            "authorization_id": confirmation["authorization_id"],
            "action_id": confirmation["action_id"],
            "confirmed_by": "human_operator",
            "aigc_performed_external_action": False,
            "operator_reported_external_action": True,
        },
        external_action_performed=False,
    )
    print(
        json.dumps(
            {
                "confirmation_id": confirmation["confirmation_id"],
                "execution_id": confirmation["execution_id"],
                "authorization_id": confirmation["authorization_id"],
                "state_event_id": event.event_id,
                "aigc_performed_external_action": False,
                "operator_reported_external_action": True,
                "phase7_handoff_ready": True,
            },
            indent=2,
        )
    )
    return 0


def run_phase14_preflight(root: Path, store: AIGCStateStore) -> int:
    registry = build_phase_registry(root)
    validation_failures: List[str] = []
    try:
        validate_file("secret_manifest", root / "config" / "secret_manifest.json")
    except (ContractValidationError, FileNotFoundError) as exc:
        validation_failures.append(str(exc))
    event = store.insert_event(
        event_type="phase14_runtime_preflight",
        phase="phase14_runtime_engine",
        status="failed" if validation_failures else "completed",
        summary="Runtime preflight checked state DB, registry, secret manifest, emergency stop, and external-action block.",
        data={
            "registry_phases": sorted(registry),
            "emergency_stop": store.emergency_stop_active(),
            "validation_failures": validation_failures,
            "external_actions_allowed": False,
        },
        external_action_performed=False,
    )
    report = render_phase14_report(root, store, registry, validation_failures, event.event_id)
    report_path = root / "reports" / "phase14_runtime_preflight.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(report)
    return 1 if validation_failures else 0


def render_phase14_report(
    root: Path,
    store: AIGCStateStore,
    registry: Dict[str, Any],
    validation_failures: List[str],
    event_id: str,
) -> str:
    summary = store.get_status_summary()
    phases = "\n".join(
        f"- {name}: {definition.display_name} ({definition.external_action_risk})"
        for name, definition in sorted(registry.items())
    )
    return f"""# AIGC Phase 14 Runtime Preflight

Generated At: {utc_now()}

Runtime Event ID: {event_id}

State Database: {summary["db_path"]}

Emergency Stop Active: {summary["emergency_stop"]}

External Action Performed: No

Validation Failures:
{bullets(validation_failures)}

Registered Phases:
{phases}

AIGC Signature Update

Phase:
Phase 14 - Runtime Engine

Approval Required:
No approval required for internal preflight.

Next Recommended Action:
Run `python .\\src\\aigc.py validate`, then use `python .\\src\\aigc.py run phase12` to refresh observability.
"""


def run_subprocess(command: List[str], root: Path) -> int:
    result = subprocess.run(command, cwd=root)
    return result.returncode


def bullets(items: List[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def authorization_expired(packet: Dict[str, Any]) -> bool:
    value = packet.get("expires_at", "")
    if not value:
        return True
    try:
        expires_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at.astimezone(timezone.utc)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC unified local runtime CLI.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--state-db", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show AIGC runtime state summary.")
    subparsers.add_parser("init-db", help="Initialize the AIGC SQLite state database.")
    subparsers.add_parser(
        "cycle-policy",
        help="Show the durable read-only Phase 2–5 cycle policy.",
    )
    subparsers.add_parser(
        "curriculum",
        help="Show the governance-bound AIGC master curriculum summary.",
    )
    health_parser = subparsers.add_parser("health", help="Run local program health checks.")
    health_parser.add_argument("--write", action="store_true", help="Write latest health report under reports/artifacts/program_health.")

    readiness_parser = subparsers.add_parser(
        "readiness",
        help="Evaluate structurally evidenced production readiness and blocking gaps.",
    )
    readiness_parser.add_argument("--artifact-root", type=Path, default=None)
    readiness_parser.add_argument(
        "--require-production-ready",
        action="store_true",
        help="Return a nonzero exit when the evaluated revision is not production ready.",
    )

    validate_parser = subparsers.add_parser("validate", help="Validate AIGC artifacts against JSON schemas.")
    validate_parser.add_argument("--schema", default="")
    validate_parser.add_argument("--path", default="")

    phase_choices = [
        "phase2",
        "phase3",
        "phase4",
        "phase5",
        "phase6",
        "phase7",
        "phase8",
        "phase10",
        "phase11",
        "phase12",
        "phase13",
        "phase14",
        "phase15",
        "phase16",
        "phase17",
        "phase18",
        "phase19",
        "phase20",
        "phase21",
        "phase22",
        "phase23",
        "phase24",
        "phase25",
        "phase26",
        "pipeline",
        "work-order",
        "paycheque",
        "work-acquisition",
        "governance-smoke",
        "cockpit-smoke",
    ]
    run_parser = subparsers.add_parser("run", help="Run an internal AIGC phase command.")
    run_parser.add_argument("phase", choices=phase_choices)
    run_parser.add_argument("--mode", choices=["synthetic", "real", "real_data_read_only"], default="synthetic")
    run_parser.add_argument("--source", choices=["remoteok", "remotive", "weworkremotely", "github_issues"], default="remoteok")
    run_parser.add_argument("--limit", type=int, default=10)
    run_parser.add_argument("--input", type=Path, default=None)
    run_parser.add_argument("--artifact-root", type=Path, default=None)
    run_parser.add_argument("--registry", type=Path, default=None)
    run_parser.add_argument("--profile", type=Path, default=None)

    subparsers.add_parser("emergency-stop", help="Enable the runtime emergency stop.")
    subparsers.add_parser("clear-emergency-stop", help="Clear the runtime emergency stop.")
    subparsers.add_parser("report", help="Refresh the Phase 12 observability report.")

    close_loop_parser = subparsers.add_parser("close-loop", help="Run internal Phase 5 to Phase 7 closure without external execution.")
    close_loop_parser.add_argument("--execution-mode", choices=["manual_handoff"], default="manual_handoff")

    incident_parser = subparsers.add_parser("create-incident", help="Create an internal Phase 17 incident report.")
    incident_parser.add_argument("--incident-type", required=True)
    incident_parser.add_argument("--severity", choices=["low", "medium", "high", "critical"], default="medium")
    incident_parser.add_argument("--summary", required=True)
    incident_parser.add_argument("--evidence-json", default="{}")

    token_parser = subparsers.add_parser("issue-approval-token", help="Issue a scoped approval token and store only its hash.")
    token_parser.add_argument("--scope", required=True)
    token_parser.add_argument("--phase", required=True)
    token_parser.add_argument("--reason", required=True)
    token_parser.add_argument("--ttl-minutes", type=int, default=30)
    token_parser.add_argument("--reusable", action="store_true")
    token_parser.add_argument("--token-store", default="memory/approval_tokens.jsonl")

    approve_parser = subparsers.add_parser("approve", help="Approve one Phase 5 authorization packet by exact phrase.")
    approve_parser.add_argument("--action-id", required=True)
    approve_parser.add_argument("--phrase", required=True)
    approve_parser.add_argument("--authorizations-path", default="data/phase5_authorizations/aigc_phase5_authorization_packets.json")

    deny_parser = subparsers.add_parser("deny", help="Deny one Phase 5 authorization packet by exact phrase.")
    deny_parser.add_argument("--action-id", required=True)
    deny_parser.add_argument("--phrase", required=True)
    deny_parser.add_argument("--authorizations-path", default="data/phase5_authorizations/aigc_phase5_authorization_packets.json")

    revise_parser = subparsers.add_parser("revise", help="Mark one Phase 5 authorization packet as revision-required.")
    revise_parser.add_argument("--action-id", required=True)
    revise_parser.add_argument("--phrase", required=True)
    revise_parser.add_argument("--authorizations-path", default="data/phase5_authorizations/aigc_phase5_authorization_packets.json")

    confirm_parser = subparsers.add_parser(
        "confirm-manual-handoff",
        help="Record a human operator's completed, exact Phase 6 manual handoff.",
    )
    confirm_parser.add_argument("--execution-id", required=True)
    confirm_parser.add_argument("--phrase", required=True)
    confirm_parser.add_argument("--completion-reference", required=True)
    confirm_parser.add_argument(
        "--phase6-config",
        default="config/phase6_controlled_execution.json",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
