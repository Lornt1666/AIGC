from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.core.contract_validator import validate_artifact, validate_file


LEDGER_SCHEMA = "production_readiness_ledger"
REPORT_SCHEMA = "production_readiness_report"
ALLOWED_STATUSES = {
    "complete",
    "implemented_internal",
    "partial",
    "planned",
    "stale",
    "unimplemented",
    "superseded",
}
STATUS_RANK = {
    "unimplemented": 0,
    "superseded": 0,
    "stale": 1,
    "planned": 2,
    "partial": 3,
    "implemented_internal": 4,
    "complete": 5,
}


class ProductionReadinessLedgerError(ValueError):
    """Raised when the completion ledger would make an unsupported claim."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def load_ledger(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProductionReadinessLedgerError("Production readiness ledger must be a JSON object.")
    validate_artifact(LEDGER_SCHEMA, payload)
    validate_ledger(payload)
    return payload


def validate_ledger(ledger: Dict[str, Any]) -> None:
    controls = dict(ledger.get("truth_controls", {}))
    required_true = {
        "missing_evidence_downgrades_status",
        "completion_claim_requires_all_evidence",
        "production_ready_requires_no_blocking_gaps",
        "operator_review_required",
    }
    missing = sorted(key for key in required_true if controls.get(key) is not True)
    if missing:
        raise ProductionReadinessLedgerError(f"Missing truth controls: {missing}")
    if controls.get("external_action_performed") is not False:
        raise ProductionReadinessLedgerError("Ledger cannot claim an external action.")

    multipliers = dict(ledger.get("status_multipliers", {}))
    if not ALLOWED_STATUSES.issubset(multipliers):
        raise ProductionReadinessLedgerError("Every allowed status requires a multiplier.")

    identifiers: set[str] = set()
    total_weight = 0.0
    for capability in ledger.get("capabilities", []):
        capability_id = str(capability.get("capability_id", ""))
        if not capability_id or capability_id in identifiers:
            raise ProductionReadinessLedgerError(f"Invalid or duplicate capability_id: {capability_id!r}")
        identifiers.add(capability_id)
        status = str(capability.get("declared_status", ""))
        if status not in ALLOWED_STATUSES:
            raise ProductionReadinessLedgerError(f"Unsupported status for {capability_id}: {status}")
        weight = float(capability.get("weight", 0))
        if weight <= 0:
            raise ProductionReadinessLedgerError(f"Capability {capability_id} requires positive weight.")
        total_weight += weight
    if total_weight <= 0:
        raise ProductionReadinessLedgerError("Ledger requires positive total capability weight.")


def evidence_exists(project_root: Path, relative_path: str) -> bool:
    """Return true only for non-empty repository evidence.

    This is deliberately structural evidence, not proof that a capability works.
    Operational maturity requires separate test, runtime, and CI receipts.
    """
    path = project_root / relative_path
    if path.is_file():
        try:
            return path.stat().st_size > 0
        except OSError:
            return False
    if path.is_dir():
        try:
            return any(item.is_file() and item.stat().st_size > 0 for item in path.rglob("*"))
        except OSError:
            return False
    return False


def repository_revision(project_root: Path) -> str:
    """Bind a report to the evaluated revision when Git metadata is available."""
    github_sha = os.environ.get("GITHUB_SHA", "").strip()
    if github_sha:
        return github_sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unbound"
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else "unbound"


def effective_status(declared_status: str, evidence_complete: bool) -> str:
    if evidence_complete:
        return declared_status
    if declared_status == "complete":
        return "partial"
    if declared_status == "implemented_internal":
        return "partial"
    if declared_status == "partial":
        return "planned"
    return declared_status


def evaluate_capability(
    project_root: Path,
    capability: Dict[str, Any],
    multipliers: Dict[str, float],
) -> Dict[str, Any]:
    evidence_paths = [str(item) for item in capability.get("required_evidence", [])]
    evidence = [
        {
            "path": path,
            "kind": "structural_repository_path",
            "present": evidence_exists(project_root, path),
        }
        for path in evidence_paths
    ]
    evidence_complete = bool(evidence_paths) and all(item["present"] for item in evidence)
    if not evidence_paths and capability.get("declared_status") in {"unimplemented", "planned"}:
        evidence_complete = True

    declared = str(capability["declared_status"])
    effective = effective_status(declared, evidence_complete)
    weight = float(capability["weight"])
    earned_weight = weight * float(multipliers[effective])
    missing_evidence = [item["path"] for item in evidence if not item["present"]]

    return {
        "capability_id": capability["capability_id"],
        "name": capability["name"],
        "dimension": capability["dimension"],
        "weight": weight,
        "declared_status": declared,
        "effective_status": effective,
        "evidence_complete": evidence_complete,
        "evidence": evidence,
        "missing_evidence": missing_evidence,
        "blocking_for_production": bool(capability.get("blocking_for_production", False)),
        "earned_weight": round(earned_weight, 3),
        "readiness_percent": round(float(multipliers[effective]) * 100, 2),
    }


def choose_highest_impact_next_step(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    incomplete = [result for result in results if result["effective_status"] != "complete"]
    if not incomplete:
        return {
            "capability_id": "none",
            "action": "maintain_and_monitor",
            "reason": "All registered capabilities are complete with evidence.",
            "operator_review_required": True,
        }

    selected = sorted(
        incomplete,
        key=lambda item: (
            0 if item["blocking_for_production"] else 1,
            STATUS_RANK[item["effective_status"]],
            -float(item["weight"]),
            item["capability_id"],
        ),
    )[0]
    return {
        "capability_id": selected["capability_id"],
        "name": selected["name"],
        "action": "open_one_contract_first_implementation_pr",
        "reason": (
            "This capability is the highest-priority production blocker after applying "
            "evidence and readiness weighting."
        ),
        "effective_status": selected["effective_status"],
        "missing_evidence": selected["missing_evidence"],
        "operator_review_required": True,
    }


def build_report(project_root: Path, ledger: Dict[str, Any]) -> Dict[str, Any]:
    validate_ledger(ledger)
    multipliers = {key: float(value) for key, value in ledger["status_multipliers"].items()}
    results = [evaluate_capability(project_root, item, multipliers) for item in ledger["capabilities"]]
    total_weight = sum(float(item["weight"]) for item in results)
    earned_weight = sum(float(item["earned_weight"]) for item in results)
    overall_score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0

    dimension_totals: Dict[str, float] = {}
    dimension_earned: Dict[str, float] = {}
    status_counts: Dict[str, int] = {}
    blocking_gaps: List[str] = []
    for item in results:
        dimension = str(item["dimension"])
        dimension_totals[dimension] = dimension_totals.get(dimension, 0.0) + float(item["weight"])
        dimension_earned[dimension] = dimension_earned.get(dimension, 0.0) + float(item["earned_weight"])
        status = str(item["effective_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
        if item["blocking_for_production"] and status != "complete":
            blocking_gaps.append(str(item["capability_id"]))

    dimension_scores = {
        key: round((dimension_earned[key] / weight) * 100, 2) if weight else 0.0
        for key, weight in dimension_totals.items()
    }
    threshold = float(ledger["production_readiness_threshold"])
    production_ready = overall_score >= threshold and not blocking_gaps
    next_step = choose_highest_impact_next_step(results)

    report = {
        "report_id": make_id("AIGC-PRODUCTION-READINESS", ledger["ledger_id"], utc_now()),
        "created_at": utc_now(),
        "ledger_id": ledger["ledger_id"],
        "source_revision": repository_revision(project_root),
        "evidence_model": "structural_repository_evidence_v2",
        "evidence_strength": "structural_not_operational_proof",
        "overall_score": overall_score,
        "production_readiness_threshold": threshold,
        "production_ready": production_ready,
        "status_counts": status_counts,
        "capability_results": results,
        "dimension_scores": dimension_scores,
        "blocking_gaps": blocking_gaps,
        "highest_impact_next_step": next_step,
        "governance_summary": {
            "completion_claims_are_structurally_evidenced": True,
            "operational_proof_claimed": False,
            "unsupported_claims_are_downgraded": True,
            "production_ready_requires_no_blocking_gaps": True,
            "result": "production_ready" if production_ready else "not_production_ready",
        },
        "operator_review_required": True,
        "external_action_performed": False,
    }
    validate_artifact(REPORT_SCHEMA, report)
    return report


def run_production_readiness_ledger(
    project_root: Path,
    ledger_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    ledger_path = ledger_path or root / "config" / "production_readiness_ledger.json"
    artifact_root = artifact_root or root / "reports" / "artifacts" / "production_readiness"

    ledger = load_ledger(ledger_path)
    validate_file(LEDGER_SCHEMA, ledger_path)
    report = build_report(root, ledger)

    output_root = artifact_root / report["report_id"]
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "production_readiness_report.json"
    md_path = output_root / "production_readiness_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    validate_file(REPORT_SCHEMA, json_path)
    md_path.write_text(render_report(report), encoding="utf-8")

    return {
        "report": report,
        "report_path": relative_to_root(root, json_path),
        "markdown_report_path": relative_to_root(root, md_path),
        "external_action_performed": False,
    }


def render_report(report: Dict[str, Any]) -> str:
    lines = [
        "# AIGC Production Readiness Ledger",
        "",
        f"Report ID: `{report['report_id']}`",
        f"Source revision: `{report['source_revision']}`",
        f"Evidence strength: `{report['evidence_strength']}`",
        f"Overall score: **{report['overall_score']} / 100**",
        f"Threshold: **{report['production_readiness_threshold']}**",
        f"Production ready: **{'Yes' if report['production_ready'] else 'No'}**",
        "External action performed: **No**",
        "",
        "## Blocking Gaps",
        *([f"- `{item}`" for item in report["blocking_gaps"]] or ["- None"]),
        "",
        "## Capability Results",
    ]
    for item in report["capability_results"]:
        lines.extend(
            [
                f"### {item['name']}",
                f"- Effective status: `{item['effective_status']}`",
                f"- Readiness: {item['readiness_percent']}%",
                f"- Production blocker: {item['blocking_for_production']}",
                f"- Missing evidence: {', '.join(item['missing_evidence']) or 'None'}",
                "",
            ]
        )
    next_step = report["highest_impact_next_step"]
    lines.extend(
        [
            "## Highest-Impact Next Step",
            f"- Capability: `{next_step.get('capability_id', '')}`",
            f"- Action: `{next_step.get('action', '')}`",
            f"- Reason: {next_step.get('reason', '')}",
            "",
            "## Governance Summary",
            "The ledger measures evidence, downgrades unsupported completion claims, and stops for operator review.",
        ]
    )
    return "\n".join(lines) + "\n"


def relative_to_root(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)
