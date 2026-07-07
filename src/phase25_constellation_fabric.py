from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/phase25_constellation_fabric.json"
PHASE_NAME = "phase25_constellation_fabric"


Classification = Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def load_config(root: Path, config_path: str) -> Dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        return default_config()
    return json.loads(path.read_text(encoding="utf-8"))


def default_config() -> Dict[str, Any]:
    return {
        "trigger": {"phrase": "AIGC", "case_sensitive": False, "store_raw_chat_text": False},
        "excluded_directories": [
            ".git",
            ".venv",
            "venv",
            "env",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            "node_modules",
        ],
        "excluded_path_prefixes": ["memory/omega_x/memory", "memory/approval_tokens.jsonl"],
        "safety_doctrine": {
            "external_action_allowed": False,
            "physical_file_moves_allowed": False,
            "credential_use_allowed": False,
            "secret_value_logging_allowed": False,
            "default_mode": "dry_run_classification",
        },
        "agent_roster": [],
        "operational_directives": [
            "Classify before moving.",
            "Report before rewriting.",
            "Approve before external action.",
        ],
    }


def trigger_detected(
    *,
    trigger_text: str,
    chat_log_path: str,
    phrase: str,
    case_sensitive: bool,
    force_local: bool,
    root: Path,
) -> Dict[str, Any]:
    trigger_sources: List[Dict[str, Any]] = []
    found = bool(force_local)

    def contains_phrase(text: str) -> bool:
        if case_sensitive:
            return phrase in text
        return phrase.lower() in text.lower()

    if trigger_text:
        text_found = contains_phrase(trigger_text)
        found = found or text_found
        trigger_sources.append(
            {
                "source": "trigger_text_argument",
                "contains_trigger": text_found,
                "raw_text_stored": False,
                "text_sha256": stable_hash(trigger_text),
            }
        )

    if chat_log_path:
        candidate = Path(chat_log_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists() and candidate.is_file():
            # The file is read only to detect the phrase. The raw log text is not persisted.
            text = candidate.read_text(encoding="utf-8", errors="ignore")
            log_found = contains_phrase(text)
            found = found or log_found
            trigger_sources.append(
                {
                    "source": "chat_log_path",
                    "path": candidate.relative_to(root).as_posix() if is_relative_to(candidate, root) else str(candidate),
                    "contains_trigger": log_found,
                    "raw_text_stored": False,
                    "text_sha256": stable_hash(text),
                }
            )
        else:
            trigger_sources.append(
                {
                    "source": "chat_log_path",
                    "path": str(candidate),
                    "contains_trigger": False,
                    "raw_text_stored": False,
                    "error": "path_missing_or_not_file",
                }
            )

    if force_local:
        trigger_sources.append(
            {
                "source": "local_cli_force",
                "contains_trigger": True,
                "raw_text_stored": False,
            }
        )

    return {
        "phrase": phrase,
        "case_sensitive": case_sensitive,
        "detected": found,
        "force_local": force_local,
        "sources": trigger_sources,
    }


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def iter_repository_files(root: Path, config: Dict[str, Any]) -> Iterable[Path]:
    excluded_dirs = set(config.get("excluded_directories", []))
    excluded_prefixes = [normalize_prefix(value) for value in config.get("excluded_path_prefixes", [])]
    excluded_globs = config.get("excluded_globs", [])

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = rel.split("/")
        if any(part in excluded_dirs for part in parts):
            continue
        if any(rel == prefix or rel.startswith(prefix + "/") for prefix in excluded_prefixes):
            continue
        if any(fnmatch.fnmatch(rel, pattern) for pattern in excluded_globs):
            continue
        yield path


def normalize_prefix(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def detect_phase(rel_path: str) -> str:
    match = re.search(r"phase(\d+)", rel_path, flags=re.IGNORECASE)
    return f"phase{match.group(1)}" if match else ""


def classify_file(path: Path, root: Path) -> Classification:
    rel = path.relative_to(root).as_posix()
    parts = rel.split("/")
    first = parts[0] if parts else ""
    suffix = path.suffix.lower()
    name = path.name.lower()
    phase = detect_phase(rel)

    zone = "99_UNCLASSIFIED_SUPPORT"
    ontology = "support_artifact"
    taxonomy = "unclassified_support_file"
    methodology = "supporting_material"
    agent_lane = "audit_archivist"
    risk_class = "metadata_only"

    if rel in {"README.md", "LICENSE", "LICENSE.md", "SECURITY.md", "CONTRIBUTING.md"}:
        zone = "00_COMMAND_DOCTRINE"
        ontology = "project_identity_doctrine"
        taxonomy = "root_doctrine"
        methodology = "operator_orientation"
        agent_lane = "arena_master"
    elif first == ".github":
        zone = "01_CLOUD_TRIGGER_INGRESS"
        ontology = "cloud_automation_control"
        taxonomy = "workflow_or_repository_automation"
        methodology = "cloud_trigger_ingress"
        agent_lane = "cloud_trigger_sentinel"
        risk_class = "cloud_control_metadata"
    elif first == "config":
        zone = "02_CONFIGURATION_CONTROL"
        ontology = "runtime_configuration_object"
        taxonomy = "configuration_manifest"
        methodology = phase_to_methodology(phase) if phase else "configuration_governance"
        agent_lane = "methodology_engineer"
        risk_class = "configuration_metadata"
        if "secret" in name or "token" in name or "credential" in name:
            zone = "05_SECURITY_GOVERNANCE"
            agent_lane = "security_governor"
            risk_class = "secret_reference_metadata_only"
    elif first == "schemas":
        zone = "03_CONTRACT_SCHEMA_ONTOLOGY"
        ontology = "artifact_contract_schema"
        taxonomy = "json_schema_contract" if suffix == ".json" else "contract_support"
        methodology = "contract_validation"
        agent_lane = "ontology_sorter"
    elif first == "src":
        zone = "04_AGENTIC_SOURCE_KERNEL"
        ontology = "agentic_runtime_source"
        taxonomy = "python_phase_engine" if suffix == ".py" else "source_support"
        methodology = phase_to_methodology(phase) if phase else "runtime_kernel"
        agent_lane = "constellation_cartographer"
        if "security" in parts or "approval" in rel or "secret" in rel or "incident" in rel or "compliance" in rel:
            zone = "05_SECURITY_GOVERNANCE"
            ontology = "guardrail_runtime_source"
            taxonomy = "security_governance_module"
            methodology = phase_to_methodology(phase) if phase else "security_governance"
            agent_lane = "security_governor"
            risk_class = "guardrail_source_metadata"
        elif "core" in parts:
            ontology = "core_runtime_kernel"
            taxonomy = "orchestration_core"
            methodology = "runtime_preflight"
            agent_lane = "arena_master"
        elif "dashboard" in parts:
            zone = "07_REPORTING_OBSERVABILITY"
            ontology = "observability_surface"
            taxonomy = "dashboard_module"
            methodology = "observability"
            agent_lane = "audit_archivist"
    elif first == "docs":
        zone = "08_DOCS_OLOGY_LIBRARY"
        ontology = "doctrine_and_methodology_document"
        taxonomy = "ology_doctrine" if any(token in name for token in ["ology", "ontology", "taxonomy", "method", "governance", "doctrine"]) else "documentation"
        methodology = "doctrine_synthesis"
        agent_lane = "taxonomy_librarian"
        if "secret" in name or "security" in name or "governance" in name:
            agent_lane = "security_governor"
            risk_class = "governance_documentation"
    elif first == "data":
        zone = "06_DATA_MEMORY_LEDGER"
        ontology = "generated_data_artifact"
        taxonomy = "audit_ledger" if "audit" in parts else "phase_output_data"
        methodology = phase_to_methodology(phase) if phase else "data_lineage"
        agent_lane = "audit_archivist"
        risk_class = "generated_artifact_metadata_only"
    elif first == "memory":
        zone = "06_DATA_MEMORY_LEDGER"
        ontology = "memory_state_artifact"
        taxonomy = "state_or_memory_record"
        methodology = "evolution_loop"
        agent_lane = "audit_archivist"
        risk_class = "memory_metadata_only"
    elif first == "reports":
        zone = "07_REPORTING_OBSERVABILITY"
        ontology = "reporting_artifact"
        taxonomy = "human_readable_report"
        methodology = phase_to_methodology(phase) if phase else "observability"
        agent_lane = "audit_archivist"
    elif first in {"tests", "test"} or name.startswith("test_"):
        zone = "09_TEST_AND_VALIDATION"
        ontology = "verification_artifact"
        taxonomy = "test_or_validation_file"
        methodology = "verification_tribunal"
        agent_lane = "methodology_engineer"

    return {
        "path": rel,
        "name": path.name,
        "extension": suffix,
        "size_bytes": path.stat().st_size,
        "phase": phase,
        "constellation_zone": zone,
        "ontology": ontology,
        "taxonomy": taxonomy,
        "methodology": methodology,
        "agent_lane": agent_lane,
        "risk_class": risk_class,
        "physical_move_performed": False,
    }


def phase_to_methodology(phase: str) -> str:
    mapping = {
        "phase2": "source_intake",
        "phase3": "ology_assessment",
        "phase4": "proposal_drafting",
        "phase5": "human_approval",
        "phase6": "controlled_execution",
        "phase7": "audit_packet_generation",
        "phase8": "evolution_loop",
        "phase10": "connector_governance",
        "phase11": "security_vault",
        "phase12": "observability",
        "phase13": "simulation_arena",
        "phase14": "runtime_preflight",
        "phase15": "finance_contracts_asset_ledger",
        "phase16": "compliance_legal_review",
        "phase17": "incident_response_recovery",
        "phase18": "productization",
        "phase19": "subagent_forge",
        "phase20": "fidelity_forge",
        "phase21": "customer_satisfaction",
        "phase22": "quality_kernel",
        "phase23": "work_order_governance",
        "phase24": "business_pipeline",
        "phase25": "constellation_fabric",
    }
    return mapping.get(phase, "phase_methodology_unspecified")


def build_manifest(root: Path, config: Dict[str, Any], trigger: Dict[str, Any]) -> Dict[str, Any]:
    classifications = [classify_file(path, root) for path in sorted(iter_repository_files(root, config))]
    zone_counts = Counter(item["constellation_zone"] for item in classifications)
    agent_counts = Counter(item["agent_lane"] for item in classifications)
    method_counts = Counter(item["methodology"] for item in classifications)
    risk_counts = Counter(item["risk_class"] for item in classifications)

    status = "completed" if trigger["detected"] else "blocked_no_trigger"
    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": status,
        "trigger": trigger,
        "safety_doctrine": config.get("safety_doctrine", {}),
        "summary": {
            "total_files_classified": len(classifications),
            "constellation_zone_counts": dict(sorted(zone_counts.items())),
            "agent_lane_counts": dict(sorted(agent_counts.items())),
            "methodology_counts": dict(sorted(method_counts.items())),
            "risk_class_counts": dict(sorted(risk_counts.items())),
            "external_action_performed": False,
            "physical_file_moves_performed": False,
            "raw_chat_text_stored": False,
        },
        "agent_roster": config.get("agent_roster", []),
        "operational_directives": config.get("operational_directives", []),
        "files": classifications,
    }


def render_report(manifest: Dict[str, Any]) -> str:
    summary = manifest["summary"]
    zone_lines = render_counter(summary["constellation_zone_counts"])
    agent_lines = render_counter(summary["agent_lane_counts"])
    method_lines = render_counter(summary["methodology_counts"])
    risk_lines = render_counter(summary["risk_class_counts"])
    directive_lines = "\n".join(f"- {item}" for item in manifest.get("operational_directives", [])) or "- None"

    return f"""# AIGC Phase 25 Constellation Fabric Report

Generated At: {manifest['generated_at']}

Status: {manifest['status']}

Trigger Detected: {manifest['trigger']['detected']}

External Action Performed: No

Physical File Moves Performed: No

Raw Chat Text Stored: No

## Purpose

Phase 25 classifies the repository into operational, ontological, taxonomic, methodological, and agent-lane structure. It is the safe cartography layer before any future physical refactor.

## Constellation Zone Counts

{zone_lines}

## Agent Lane Counts

{agent_lines}

## Methodology Counts

{method_lines}

## Risk Class Counts

{risk_lines}

## Operational Directives

{directive_lines}

## Safety Boundary

This run creates a manifest, a report, and an audit ledger entry only. It does not move files, rewrite source files, publish artifacts, contact external services, spend money, apply to work, use credentials, or bypass Phase 5 approval gates.

## Next Recommended Action

Review `data/phase25_constellation/aigc_phase25_constellation_manifest.json`. If the classification is approved, create a separate human-reviewed refactor PR that physically moves files according to the constellation zones.
"""


def render_counter(counter: Dict[str, int]) -> str:
    if not counter:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items()))


def write_outputs(root: Path, manifest: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    manifest_path = root / "data" / "phase25_constellation" / "aigc_phase25_constellation_manifest.json"
    report_path = root / "reports" / "phase25_constellation_fabric_report.md"
    audit_path = root / "data" / "audit" / "aigc_phase25_audit.jsonl"

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(manifest), encoding="utf-8")

    audit_record = {
        "event_id": f"AIGC-P25-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": manifest["generated_at"],
        "phase": PHASE_NAME,
        "status": manifest["status"],
        "trigger_detected": manifest["trigger"]["detected"],
        "files_classified": manifest["summary"]["total_files_classified"],
        "external_action_performed": False,
        "physical_file_moves_performed": False,
        "raw_chat_text_stored": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")

    return manifest_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC Phase 25 constellation fabric classifier.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--trigger-text", default="")
    parser.add_argument("--chat-log-path", default="")
    parser.add_argument("--force-local", action="store_true", help="Run locally without requiring trigger text. Does not allow external action.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_config(root, args.config)
    trigger_config = config.get("trigger", {})
    trigger = trigger_detected(
        trigger_text=args.trigger_text,
        chat_log_path=args.chat_log_path,
        phrase=str(trigger_config.get("phrase", "AIGC")),
        case_sensitive=bool(trigger_config.get("case_sensitive", False)),
        force_local=args.force_local,
        root=root,
    )
    manifest = build_manifest(root, config, trigger)
    manifest_path, report_path, audit_path = write_outputs(root, manifest)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": manifest["status"],
        "trigger_detected": trigger["detected"],
        "files_classified": manifest["summary"]["total_files_classified"],
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "external_action_performed": False,
        "physical_file_moves_performed": False,
    }, indent=2))
    return 0 if trigger["detected"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
