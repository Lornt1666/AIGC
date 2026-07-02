from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.incidents.incident_response import IncidentReport, IncidentResponseLedger


class Phase17IncidentResponse:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(
        self,
        config_path: Path,
        incident_type: str = "",
        severity: str = "",
        summary: str = "",
        evidence: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        config = load_json_dict(config_path)
        incident_log = resolve_project_path(
            self.project_root,
            config.get("incident_log", "data/phase17_incidents/incident_reports.jsonl"),
        )
        summary_file = resolve_project_path(
            self.project_root,
            config.get("summary_file", "data/phase17_incidents/incident_response_summary.json"),
        )
        report_file = resolve_project_path(
            self.project_root,
            config.get("report_file", "reports/phase17_incident_response_report.md"),
        )
        ledger = IncidentResponseLedger(incident_log)
        created_report = None
        if incident_type:
            created_report = ledger.create_report(
                incident_type=incident_type,
                severity=severity or "medium",
                summary=summary or f"Internal incident report created for {incident_type}.",
                evidence=evidence or {},
            )
        reports = ledger.list_reports()
        payload = build_summary(reports, created_report, config)
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(render_report(payload), encoding="utf-8")
        return payload


def build_summary(
    reports: List[IncidentReport],
    created_report: IncidentReport | None,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    for report in reports:
        by_status[report.status] = by_status.get(report.status, 0) + 1
        by_severity[report.severity] = by_severity.get(report.severity, 0) + 1
    return {
        "phase": config.get("phase", "Phase 17 - Incident Response and Recovery"),
        "status": "ready",
        "incident_count": len(reports),
        "open_incidents": len([report for report in reports if report.status.startswith("open")]),
        "by_status": by_status,
        "by_severity": by_severity,
        "created_incident_id": created_report.incident_id if created_report else "",
        "required_controls": config.get("required_controls", []),
        "external_action_performed": False,
        "notes": [
            "Incident response is internal-only.",
            "Emergency stop, containment, recovery, postmortem, and patch proposal remain operator-governed.",
        ],
    }


def render_report(payload: Dict[str, Any]) -> str:
    status_counts = "\n".join(f"- {key}: {value}" for key, value in payload.get("by_status", {}).items()) or "- None"
    severity_counts = "\n".join(f"- {key}: {value}" for key, value in payload.get("by_severity", {}).items()) or "- None"
    controls = "\n".join(f"- {item}" for item in payload.get("required_controls", [])) or "- None"
    notes = "\n".join(f"- {item}" for item in payload.get("notes", [])) or "- None"
    return f"""# Phase 17 Incident Response Report

Status: {payload.get("status")}

Incident Count: {payload.get("incident_count")}

Open Incidents: {payload.get("open_incidents")}

Created Incident ID: {payload.get("created_incident_id") or "None"}

External Action Performed: No

## By Status

{status_counts}

## By Severity

{severity_counts}

## Required Controls

{controls}

## Notes

{notes}
"""


def load_json_dict(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run AIGC Phase 17 incident response readiness/reporting.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase17_incident_response.json")
    parser.add_argument("--incident-type", default="")
    parser.add_argument("--severity", choices=["low", "medium", "high", "critical"], default="medium")
    parser.add_argument("--summary", default="")
    parser.add_argument("--evidence-json", default="{}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence = json.loads(args.evidence_json)
    phase = Phase17IncidentResponse(project_root=args.project_root)
    payload = phase.run_from_config(
        config_path=args.config,
        incident_type=args.incident_type,
        severity=args.severity,
        summary=args.summary,
        evidence=evidence,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
