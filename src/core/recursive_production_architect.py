from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import validate_artifact, validate_file


CYCLE_SCHEMA = "recursive_production_cycle"

CRITICAL_NAMES = {
    ".github",
    "config",
    "schemas",
    "src",
    "tests",
    "requirements.txt",
    "RUN_AIGC_PROGRAM.bat",
    "AIGC_MASTER_PROMPT.md",
    "OMEGA_X_CONSTITUTION.md",
}

HARD_BLOCKS = {
    "self_approval",
    "unbounded_recursion",
    "direct_main_write",
    "destructive_change_without_review",
    "live_deployment_without_approved_connector",
    "credential_use_without_reviewed_integration",
    "raw_secret_logging",
    "platform_rule_bypass",
    "fabricated_completion_state",
}


class RecursiveProductionArchitectError(ValueError):
    """Raised when recursive production policy would weaken AIGC governance."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def load_policy(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RecursiveProductionArchitectError("Recursive architect policy must be an object.")
    validate_policy(payload)
    return payload


def validate_policy(policy: Dict[str, Any]) -> None:
    maximum_cycles = int(policy.get("maximum_cycles_per_run", 0))
    if maximum_cycles < 1 or maximum_cycles > 10:
        raise RecursiveProductionArchitectError("maximum_cycles_per_run must be between 1 and 10.")
    if policy.get("operator_review_required") is not True:
        raise RecursiveProductionArchitectError("Operator review must remain required.")
    if policy.get("external_action_performed") is not False:
        raise RecursiveProductionArchitectError("Policy cannot claim external action.")

    controls = dict(policy.get("preservation_controls", {}))
    required_controls = {
        "preserve_critical_files",
        "no_deletion_without_operator_approval",
        "no_source_rewrite_without_diff_review",
        "no_workflow_rewrite_without_ci_validation",
        "rollback_plan_required",
        "git_branch_required",
    }
    missing_controls = sorted(item for item in required_controls if controls.get(item) is not True)
    if missing_controls:
        raise RecursiveProductionArchitectError(f"Missing preservation controls: {missing_controls}")

    hard_blocks = {str(item) for item in policy.get("hard_blocks", [])}
    missing_blocks = sorted(HARD_BLOCKS - hard_blocks)
    if missing_blocks:
        raise RecursiveProductionArchitectError(f"Missing hard blocks: {missing_blocks}")


def iter_repository_files(root: Path) -> Iterable[Path]:
    excluded = {".git", ".venv", "__pycache__", ".pytest_cache", "reports", "build", "dist"}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        yield path


def classify_file(path: Path, root: Path) -> Dict[str, str]:
    relative = path.relative_to(root).as_posix()
    first = relative.split("/", 1)[0]
    suffix = path.suffix.lower()

    layer = {
        "src": "application",
        "config": "configuration",
        "schemas": "data_contracts",
        "tests": "quality",
        ".github": "devops",
        "docs": "documentation",
        "scripts": "operations",
    }.get(first, "repository_root")

    function = {
        ".py": "program",
        ".json": "configuration_or_schema",
        ".md": "documentation",
        ".yml": "pipeline_or_configuration",
        ".yaml": "pipeline_or_configuration",
        ".ps1": "operations_script",
        ".bat": "launcher",
    }.get(suffix, "artifact")

    lifecycle = "critical" if first in CRITICAL_NAMES or relative in CRITICAL_NAMES else "stable"
    if "experimental" in relative.lower() or "prototype" in relative.lower():
        lifecycle = "experimental"

    ownership = {
        "src": "engineering",
        "tests": "quality_engineering",
        ".github": "devops",
        "schemas": "architecture_governance",
        "config": "operations_governance",
        "docs": "documentation_governance",
    }.get(first, "repository_operator")

    return {
        "path": relative,
        "layer": layer,
        "function": function,
        "lifecycle": lifecycle,
        "ownership": ownership,
    }


def build_baselines(root: Path) -> Dict[str, Any]:
    records = [classify_file(path, root) for path in iter_repository_files(root)]
    by_layer: Dict[str, int] = {}
    by_function: Dict[str, int] = {}
    by_lifecycle: Dict[str, int] = {}
    by_ownership: Dict[str, int] = {}

    for record in records:
        for bucket, key in [
            (by_layer, "layer"),
            (by_function, "function"),
            (by_lifecycle, "lifecycle"),
            (by_ownership, "ownership"),
        ]:
            value = record[key]
            bucket[value] = bucket.get(value, 0) + 1

    ontology = {
        "code": {"module_count": by_layer.get("application", 0), "interfaces": ["CLI", "Streamlit cockpit"]},
        "infrastructure": {"workflow_files": by_layer.get("devops", 0), "deployment_state": "local_and_ci_only"},
        "devops": {"operations_files": by_layer.get("operations", 0), "continuous_delivery": False},
        "data": {"contract_files": by_layer.get("data_contracts", 0), "persistence": "file_first_with_internal_records"},
        "risk": {"governance": "security_privacy_wiring_required", "external_execution": "blocked_by_default"},
    }

    taxonomy = {
        "artifact_count": len(records),
        "by_layer": by_layer,
        "by_function": by_function,
        "by_lifecycle": by_lifecycle,
        "by_ownership": by_ownership,
        "artifacts": records,
    }

    methodology = {
        "design": ["domain_driven_design", "clean_architecture", "separation_of_concerns"],
        "engineering": ["contract_first", "test_driven_development", "secure_coding"],
        "devops": ["branch_based_gitops", "ci_validation", "observability_first"],
        "governance": ["compliance_by_design", "auditability", "operator_approval", "traceability"],
    }
    return {"ontology": ontology, "taxonomy": taxonomy, "methodology": methodology}


def assess_architecture(root: Path, baselines: Dict[str, Any]) -> Dict[str, Any]:
    checks = {
        "has_source": (root / "src").exists(),
        "has_tests": (root / "tests").exists(),
        "has_schemas": (root / "schemas").exists(),
        "has_ci": (root / ".github" / "workflows").exists(),
        "has_dependency_manifest": (root / "requirements.txt").exists(),
        "has_local_setup": (root / "scripts" / "setup_aigc_local.ps1").exists(),
        "has_security_wiring": (root / "src" / "core" / "security_privacy_wiring.py").exists(),
        "has_agent_doctrine": (root / "src" / "core" / "agent_operating_doctrine.py").exists(),
        "has_container_definition": (root / "Dockerfile").exists(),
        "has_iac": any((root / name).exists() for name in ("terraform", "infra", "infrastructure")),
        "has_e2e_tests": any("e2e" in path.name.lower() for path in (root / "tests").glob("*.py")) if (root / "tests").exists() else False,
    }
    score = round(sum(bool(value) for value in checks.values()) / len(checks) * 100)
    gaps = [name for name, present in checks.items() if not present]
    return {
        "production_readiness_score": score,
        "checks": checks,
        "gaps": gaps,
        "status": "target_reached" if score >= 90 else "improvement_required",
        "taxonomy_artifact_count": baselines["taxonomy"]["artifact_count"],
    }


def build_backlog(assessment: Dict[str, Any]) -> List[Dict[str, Any]]:
    recommendations = {
        "has_container_definition": ("Add reproducible container definition", "platform", "medium"),
        "has_iac": ("Add reviewed infrastructure-as-code baseline", "infrastructure", "high"),
        "has_e2e_tests": ("Add end-to-end local operator workflow tests", "quality", "high"),
        "has_security_wiring": ("Wire Security & Privacy Gate into all sensitive paths", "security", "critical"),
        "has_agent_doctrine": ("Require agent doctrine validation during setup and CI", "governance", "high"),
    }
    backlog: List[Dict[str, Any]] = []
    for gap in assessment.get("gaps", []):
        if gap not in recommendations:
            continue
        title, domain, priority = recommendations[gap]
        backlog.append(
            {
                "item_id": make_id("AIGC-BACKLOG", gap),
                "title": title,
                "domain": domain,
                "priority": priority,
                "implementation_mode": "separate_reviewed_pr",
                "destructive": False,
                "operator_approval_required": True,
            }
        )
    return backlog


def build_cycle(root: Path, policy: Dict[str, Any], cycle_number: int) -> Dict[str, Any]:
    baselines = build_baselines(root)
    assessment = assess_architecture(root, baselines)
    backlog = build_backlog(assessment)
    target = int(policy.get("production_readiness_target", 90))
    decision_state = "production_target_reached" if assessment["production_readiness_score"] >= target else "operator_review_required"

    cycle = {
        "cycle_id": make_id("AIGC-RECURSIVE-CYCLE", root, cycle_number, utc_now()),
        "created_at": utc_now(),
        "cycle_number": cycle_number,
        "decision_state": decision_state,
        "ontology": baselines["ontology"],
        "taxonomy": baselines["taxonomy"],
        "methodology": baselines["methodology"],
        "architecture_assessment": assessment,
        "transformation_backlog": backlog,
        "preservation_controls": dict(policy.get("preservation_controls", {})),
        "stop_conditions": list(policy.get("stop_conditions", [])),
        "operator_review_required": True,
        "external_action_performed": False,
    }
    validate_artifact(CYCLE_SCHEMA, cycle)
    return cycle


def run_recursive_production_architect(
    project_root: Path,
    policy_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    policy_path = policy_path or root / "config" / "recursive_production_architect.json"
    artifact_root = artifact_root or root / "reports" / "artifacts" / "recursive_production_architect"
    policy = load_policy(policy_path)

    cycles: List[Dict[str, Any]] = []
    maximum_cycles = int(policy["maximum_cycles_per_run"])
    for cycle_number in range(1, maximum_cycles + 1):
        cycle = build_cycle(root, policy, cycle_number)
        cycles.append(cycle)
        # This engine plans only. It cannot mutate the repository within the same run.
        break

    run_id = make_id("AIGC-RECURSIVE-RUN", root, utc_now())
    run_root = artifact_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    cycle_path = run_root / "recursive_production_cycle.json"
    report_path = run_root / "recursive_production_cycle.md"
    cycle_path.write_text(json.dumps(cycles[-1], indent=2) + "\n", encoding="utf-8")
    validate_file(CYCLE_SCHEMA, cycle_path)
    report_path.write_text(render_cycle(cycles[-1]), encoding="utf-8")

    return {
        "run_id": run_id,
        "cycle": cycles[-1],
        "cycle_path": relative_to_root(root, cycle_path),
        "report_path": relative_to_root(root, report_path),
        "cycles_executed": len(cycles),
        "repository_mutated": False,
        "operator_review_required": True,
        "external_action_performed": False,
    }


def render_cycle(cycle: Dict[str, Any]) -> str:
    assessment = cycle["architecture_assessment"]
    lines = [
        "# AIGC Recursive Production Architect Cycle",
        "",
        f"Cycle ID: `{cycle['cycle_id']}`",
        f"Decision: `{cycle['decision_state']}`",
        f"Production readiness score: `{assessment['production_readiness_score']}`",
        "Repository mutated: No",
        "External action performed: No",
        "",
        "## Architecture Gaps",
        *[f"- {gap}" for gap in assessment.get("gaps", [])],
        "",
        "## Transformation Backlog",
    ]
    for item in cycle.get("transformation_backlog", []):
        lines.append(f"- [{item['priority']}] {item['title']} — separate reviewed PR")
    lines.extend(
        [
            "",
            "## Governance",
            "This cycle may inventory, classify, score, and propose. It may not self-approve, rewrite critical files, deploy, use credentials, or merge its own changes.",
        ]
    )
    return "\n".join(lines) + "\n"


def relative_to_root(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
