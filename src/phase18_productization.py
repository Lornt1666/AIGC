from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
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
class ProductizationReleaseRecord:
    release_id: str
    created_at: str
    phase: str
    version: str
    status: str
    release_type: str
    branch: str
    commit: str
    required_files_present: bool
    missing_required_files: List[str]
    checked_files: List[Dict[str, Any]]
    validation_commands: List[str]
    manual_release_gates: List[str]
    forbidden_productization_behaviors: List[str]
    release_artifacts: List[str]
    license_status: str
    all_rights_reserved: bool
    deployment_performed: bool = False
    public_release_allowed: bool = False
    external_action_performed: bool = False


class Phase18AuditLedger:
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


class ProductizationReadiness:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> ProductizationReleaseRecord:
        config = load_json_dict(config_path)
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase18_productization/aigc_phase18_release_readiness.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase18_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase18_audit.jsonl"),
        )
        record = self.build_record(config)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(record), encoding="utf-8")
        Phase18AuditLedger(audit_path).record("phase18_release_readiness_exported", {
            "release_id": record.release_id,
            "status": record.status,
            "version": record.version,
            "missing_required_files": record.missing_required_files,
            "external_action_performed": False,
        })
        return record

    def build_record(self, config: Dict[str, Any]) -> ProductizationReleaseRecord:
        checked_files = [self._check_path(path) for path in config.get("required_files", [])]
        missing = [item["path"] for item in checked_files if not item["present"]]
        license_text = read_text_if_exists(self.project_root / "LICENSE")
        all_rights_reserved = "All Rights Reserved" in license_text
        status = "internal_release_candidate" if not missing and all_rights_reserved else "blocked_until_release_requirements_met"
        branch = git_value(self.project_root, ["branch", "--show-current"])
        commit = git_value(self.project_root, ["rev-parse", "--short", "HEAD"])
        version = str(config.get("version", "0.0.0-internal"))
        return ProductizationReleaseRecord(
            release_id=make_release_id(version, commit),
            created_at=utc_now(),
            phase="phase18_scaling_productization",
            version=version,
            status=status,
            release_type=str(config.get("release_type", "internal_private_kernel")),
            branch=branch,
            commit=commit,
            required_files_present=not missing,
            missing_required_files=missing,
            checked_files=checked_files,
            validation_commands=[str(item) for item in config.get("validation_commands", [])],
            manual_release_gates=[str(item) for item in config.get("manual_release_gates", [])],
            forbidden_productization_behaviors=[str(item) for item in config.get("forbidden_productization_behaviors", [])],
            release_artifacts=[str(item) for item in config.get("release_artifacts", [])],
            license_status="all_rights_reserved_present" if all_rights_reserved else "all_rights_reserved_missing",
            all_rights_reserved=all_rights_reserved,
            deployment_performed=False,
            public_release_allowed=bool(config.get("public_release_allowed", False)),
            external_action_performed=False,
        )

    def _check_path(self, relative_path: str) -> Dict[str, Any]:
        path = self.project_root / relative_path
        return {
            "path": relative_path,
            "present": path.exists(),
            "kind": "directory" if path.is_dir() else "file",
        }

    def signature_update(self, record: ProductizationReleaseRecord) -> str:
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 18 - Scaling, Replication, and Productization",
            "Operational Identity:",
            "Internal Productization Readiness Layer",
            "Action Performed:",
            "Generated an internal release readiness manifest and productization checklist.",
            "Safety Review:",
            "No deployment performed.",
            "No public release performed.",
            "No credentials used.",
            "No external action performed.",
            f"Release ID: {record.release_id}",
            f"Version: {record.version}",
            f"Status: {record.status}",
            f"Missing Required Files: {len(record.missing_required_files)}",
            f"All Rights Reserved Notice: {record.license_status}",
            "Approval Required:",
            "Yes, before any deployment, publication, distribution, live connector enablement, or release outside the private repository.",
        ]).strip() + "\n"


def make_release_id(version: str, commit: str) -> str:
    seed = f"{version}|{commit}|phase18_productization"
    return "AIGC-REL-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def git_value(project_root: Path, args: List[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 18 productization readiness.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase18_productization.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = ProductizationReadiness(project_root=args.project_root)
    record = phase.run_from_config(args.config)
    print(phase.signature_update(record))
    print(f"\nRelease readiness exported: {args.project_root / 'data' / 'phase18_productization' / 'aigc_phase18_release_readiness.json'}")
    return 1 if record.status.startswith("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
