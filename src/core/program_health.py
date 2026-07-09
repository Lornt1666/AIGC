from __future__ import annotations

import importlib.util
import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PATHS = [
    "src/aigc.py",
    "src/dashboard/operator_cockpit_app.py",
    "src/security/redaction_scanner.py",
    "src/core/work_order.py",
    "src/core/paycheque_workflow.py",
    "config/example_work_order.json",
    "config/paycheque_workflow.json",
    "schemas/work_order_packet.schema.json",
    "schemas/paycheque_pipeline.schema.json",
    "tests",
    "reports",
]

OPTIONAL_IMPORTS = [
    "streamlit",
]

REQUIRED_IMPORTS = [
    "json",
    "sqlite3",
    "pathlib",
]


@dataclass(frozen=True)
class HealthCheckItem:
    name: str
    status: str
    summary: str
    severity: str = "info"


@dataclass(frozen=True)
class ProgramHealthReport:
    generated_at: str
    project_root: str
    python_version: str
    platform: str
    safe_mode_default: bool
    external_actions_enabled: bool
    overall_status: str
    checks: List[HealthCheckItem]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_program_health(project_root: Path = PROJECT_ROOT) -> ProgramHealthReport:
    root = project_root.resolve()
    checks: List[HealthCheckItem] = []
    checks.append(check_python_version())
    checks.extend(check_imports(REQUIRED_IMPORTS, required=True))
    checks.extend(check_imports(OPTIONAL_IMPORTS, required=False))
    checks.extend(check_required_paths(root))
    checks.append(check_reports_writable(root))
    checks.append(check_emergency_stop_readable(root))
    checks.append(check_external_action_default())

    failures = [item for item in checks if item.status == "fail"]
    warnings = [item for item in checks if item.status == "warn"]
    if failures:
        overall = "failed"
    elif warnings:
        overall = "warning"
    else:
        overall = "healthy"

    return ProgramHealthReport(
        generated_at=utc_now(),
        project_root=str(root),
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        safe_mode_default=True,
        external_actions_enabled=False,
        overall_status=overall,
        checks=checks,
    )


def write_health_report(project_root: Path = PROJECT_ROOT) -> Path:
    report = run_program_health(project_root)
    path = project_root / "reports" / "artifacts" / "program_health" / "latest_program_health.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def check_python_version() -> HealthCheckItem:
    version = sys.version_info
    ok = version.major == 3 and version.minor >= 10
    return HealthCheckItem(
        name="python_version",
        status="pass" if ok else "fail",
        summary=f"Python {version.major}.{version.minor}.{version.micro}; expected Python 3.10+.",
        severity="info" if ok else "high",
    )


def check_imports(names: List[str], required: bool) -> List[HealthCheckItem]:
    checks: List[HealthCheckItem] = []
    for name in names:
        available = importlib.util.find_spec(name) is not None
        if available:
            checks.append(HealthCheckItem(name=f"import:{name}", status="pass", summary=f"Import available: {name}."))
        elif required:
            checks.append(HealthCheckItem(name=f"import:{name}", status="fail", summary=f"Required import missing: {name}.", severity="high"))
        else:
            checks.append(HealthCheckItem(name=f"import:{name}", status="warn", summary=f"Optional import missing: {name}. Install requirements for UI launch.", severity="medium"))
    return checks


def check_required_paths(project_root: Path) -> List[HealthCheckItem]:
    checks: List[HealthCheckItem] = []
    for relative in REQUIRED_PATHS:
        path = project_root / relative
        exists = path.exists()
        checks.append(HealthCheckItem(
            name=f"path:{relative}",
            status="pass" if exists else "fail",
            summary=f"{'Found' if exists else 'Missing'} {relative}.",
            severity="info" if exists else "high",
        ))
    return checks


def check_reports_writable(project_root: Path) -> HealthCheckItem:
    target = project_root / "reports" / "artifacts" / "program_health"
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".health_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return HealthCheckItem("reports_writable", "pass", "reports/artifacts is writable.")
    except OSError as exc:
        return HealthCheckItem("reports_writable", "fail", f"reports/artifacts is not writable: {exc}", "high")


def check_emergency_stop_readable(project_root: Path) -> HealthCheckItem:
    try:
        from src.core.state_store import AIGCStateStore, DEFAULT_DB_PATH

        store = AIGCStateStore(project_root / DEFAULT_DB_PATH.relative_to(PROJECT_ROOT))
        active = store.emergency_stop_active()
        return HealthCheckItem("emergency_stop", "pass", f"Emergency stop readable; active={active}.")
    except Exception as exc:  # pragma: no cover - defensive health fallback
        return HealthCheckItem("emergency_stop", "warn", f"Emergency stop status could not be read: {exc}", "medium")


def check_external_action_default() -> HealthCheckItem:
    return HealthCheckItem(
        name="external_action_default",
        status="pass",
        summary="External actions are disabled by default in local program mode.",
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
