from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import re
import subprocess
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    from scripts.nexus_repository_intelligence import analyze as base_analyze
except ModuleNotFoundError:  # direct script execution from scripts/
    from nexus_repository_intelligence import analyze as base_analyze


RESPONSIBILITY_PATTERNS = {
    "state_machine": ("state_machine", "lifecycle", "transition", "state_reducer"),
    "policy_governance": ("policy", "governance", "authorization", "approval", "tool_broker"),
    "evidence": ("evidence", "receipt", "lineage", "provenance", "metric"),
    "agent_registry": ("agent_registry", "specialist_registry", "handoff", "conductor", "scheduler"),
    "dashboard": ("dashboard", "cockpit", "streamlit", "webapp", "ui"),
    "provider_runtime": ("provider", "gemini", "model", "vertex", "canary"),
}

CANONICAL_TARGET_HINTS = {
    "state_machine": ("src.core.nexus.state_reducer", "src.domain.nexus.contracts"),
    "policy_governance": ("src.core.epistemic.tool_broker", "src.domain.nexus.contracts"),
    "evidence": ("src.domain.nexus.evidence", "src.infrastructure.persistence.sqlite.nexus_evidence"),
    "agent_registry": ("src.core.nexus.specialist_registry",),
    "dashboard": ("src.dashboard.nexus_app", "src.webapp.nexus_dashboard"),
    "provider_runtime": (),
}

DISTRIBUTION_IMPORTS = {
    "streamlit": ("streamlit",),
    "fastapi": ("fastapi",),
    "uvicorn": ("uvicorn",),
    "pydantic": ("pydantic",),
    "httpx": ("httpx",),
    "pytest": ("pytest",),
    "jsonschema": ("jsonschema",),
    "PyYAML": ("yaml",),
    "psycopg": ("psycopg",),
    "psycopg_pool": ("psycopg_pool",),
    "PyJWT": ("jwt",),
}


def _iter_python(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        yield path


def _module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _python_import_graph(root: Path):
    modules: dict[str, str] = {}
    raw_imports: dict[str, set[str]] = defaultdict(set)
    top_level_imports: Counter[str] = Counter()

    for path in _iter_python(root):
        module = _module_name(root, path)
        modules[module] = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    raw_imports[module].add(alias.name)
                    top_level_imports[alias.name.split(".")[0]] += 1
            elif isinstance(node, ast.ImportFrom) and node.module:
                raw_imports[module].add(node.module)
                top_level_imports[node.module.split(".")[0]] += 1

    names = set(modules)
    graph: dict[str, set[str]] = {name: set() for name in names}
    for source, imports in raw_imports.items():
        for target in imports:
            candidates = [name for name in names if name == target or target.startswith(name + ".")]
            if candidates:
                chosen = max(candidates, key=len)
                if chosen != source:
                    graph[source].add(chosen)
    return modules, graph, raw_imports, top_level_imports


def _schema_callers(root: Path) -> dict:
    schema_paths = sorted({
        path.relative_to(root).as_posix()
        for path in root.rglob("*.json")
        if "schemas" in path.parts or "schema" in path.name.lower()
    })
    text_files = []
    for suffix in ("*.py", "*.md", "*.json", "*.yaml", "*.yml", "*.toml", "*.tf"):
        text_files.extend(root.rglob(suffix))

    callers: dict[str, set[str]] = defaultdict(set)
    for path in sorted(set(text_files)):
        if any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root).as_posix()
        for schema in schema_paths:
            basename = Path(schema).name
            if schema in text or basename in text:
                if rel != schema:
                    callers[schema].add(rel)

    return {
        "schema_count": len(schema_paths),
        "schemas_with_callers": sum(1 for value in callers.values() if value),
        "top_schema_callers": sorted(
            (
                {"schema": schema, "caller_count": len(callers[schema]), "callers": sorted(callers[schema])[:40]}
                for schema in schema_paths
                if callers[schema]
            ),
            key=lambda item: (-item["caller_count"], item["schema"]),
        )[:60],
    }


def _indirect_test_ownership(modules: dict[str, str], graph: dict[str, set[str]]) -> dict:
    sources = {module for module, path in modules.items() if not path.startswith("tests/")}
    tests = {module for module, path in modules.items() if path.startswith("tests/")}
    owned: dict[str, set[str]] = defaultdict(set)

    for test in sorted(tests):
        queue = deque([(test, 0)])
        seen = {test}
        while queue:
            node, depth = queue.popleft()
            if depth >= 8:
                continue
            for target in sorted(graph.get(node, set())):
                if target in seen:
                    continue
                seen.add(target)
                if target in sources:
                    owned[target].add(test)
                queue.append((target, depth + 1))

    unowned = sorted(sources - set(owned))
    return {
        "source_module_count": len(sources),
        "source_modules_with_transitive_test_reachability": len(owned),
        "transitive_test_reachability_ratio": round(len(owned) / len(sources), 4) if sources else None,
        "source_modules_without_transitive_test_reachability_count": len(unowned),
        "source_modules_without_transitive_test_reachability": unowned[:120],
        "highest_transitive_test_ownership": sorted(
            (
                {"source": source, "test_modules": len(test_set), "tests": sorted(test_set)[:40]}
                for source, test_set in owned.items()
            ),
            key=lambda item: (-item["test_modules"], item["source"]),
        )[:50],
        "interpretation": "Static import reachability only; not equivalent to runtime code coverage.",
    }


def _responsibility_map(root: Path, modules: dict[str, str]) -> dict:
    buckets = {}
    for responsibility, patterns in RESPONSIBILITY_PATTERNS.items():
        candidates = []
        for module, rel in modules.items():
            if rel.startswith("tests/"):
                continue
            path = root / rel
            try:
                text = path.read_text(encoding="utf-8").lower()
            except (OSError, UnicodeDecodeError):
                text = ""
            haystack = (module + " " + rel).lower() + " " + text[:12000]
            matches = sorted({pattern for pattern in patterns if pattern in haystack})
            if matches:
                candidates.append({"module": module, "path": rel, "matched_terms": matches})
        canonical = [hint for hint in CANONICAL_TARGET_HINTS[responsibility] if hint in modules]
        buckets[responsibility] = {
            "candidate_count": len(candidates),
            "canonical_targets_present": canonical,
            "candidates": sorted(candidates, key=lambda item: item["module"])[:100],
            "classification": "HEURISTIC_CANDIDATE_MAP_NOT_AUTHORITY",
        }
    return buckets


def _run_git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _branch_analytics(root: Path) -> dict:
    raw = _run_git(root, "for-each-ref", "--format=%(refname:short)|%(objectname)|%(committerdate:iso-strict)", "refs/remotes/origin")
    now = datetime.now(timezone.utc)
    branches = []
    for line in raw.splitlines():
        if not line or line.endswith("/HEAD"):
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        name, sha, date_text = parts
        try:
            committed = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
            age_days = max(0, (now - committed.astimezone(timezone.utc)).days)
        except ValueError:
            age_days = None
        ahead = behind = None
        if name != "origin/main":
            counts = _run_git(root, "rev-list", "--left-right", "--count", f"origin/main...{name}")
            if counts:
                try:
                    behind, ahead = (int(item) for item in counts.split())
                except ValueError:
                    pass
        branches.append({"branch": name.removeprefix("origin/"), "sha": sha, "age_days": age_days, "ahead_main": ahead, "behind_main": behind})

    age_bands = Counter()
    for item in branches:
        age = item["age_days"]
        if age is None:
            age_bands["unknown"] += 1
        elif age <= 7:
            age_bands["0-7d"] += 1
        elif age <= 30:
            age_bands["8-30d"] += 1
        elif age <= 90:
            age_bands["31-90d"] += 1
        else:
            age_bands[">90d"] += 1

    return {
        "remote_branch_count": len(branches),
        "age_bands": dict(age_bands),
        "most_stale": sorted(branches, key=lambda item: (-(item["age_days"] or -1), item["branch"]))[:40],
        "most_divergent": sorted(
            [item for item in branches if item["ahead_main"] is not None],
            key=lambda item: (-(item["ahead_main"] + item["behind_main"]), item["branch"]),
        )[:40],
    }


def _parse_requirements(root: Path) -> list[dict]:
    path = root / "requirements.txt"
    if not path.exists():
        return []
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)(?:\[[^]]+\])?(.*)$", line)
        if not match:
            continue
        name, constraint = match.groups()
        try:
            resolved = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            resolved = None
        entries.append({"distribution": name, "constraint": constraint or "", "resolved_version": resolved})
    return entries


def _dependency_usage(root: Path, top_imports: Counter[str]) -> dict:
    requirements = _parse_requirements(root)
    rows = []
    for item in requirements:
        roots = DISTRIBUTION_IMPORTS.get(item["distribution"], (item["distribution"].lower().replace("-", "_"),))
        count = sum(top_imports[root] for root in roots)
        rows.append({**item, "import_roots": list(roots), "static_import_occurrences": count, "usage_state": "USED" if count else "NO_STATIC_IMPORT_OBSERVED"})
    return {
        "direct_dependency_count": len(rows),
        "used_direct_dependencies": sum(1 for row in rows if row["static_import_occurrences"] > 0),
        "no_static_import_observed": [row["distribution"] for row in rows if row["static_import_occurrences"] == 0],
        "dependencies": rows,
        "reproducibility": {
            "requirements_are_ranges": any(any(token in row["constraint"] for token in (">", "<", "~", "*")) for row in rows),
            "lockfile_detected": any((root / name).exists() for name in ("requirements.lock", "requirements.txt.lock", "poetry.lock", "uv.lock", "Pipfile.lock")),
            "recommendation_state": "MEASURED_ENVIRONMENT_DRIFT_RISK" if rows else "NO_DIRECT_REQUIREMENTS_MEASURED",
        },
        "security_advisory_state": "EXTERNAL_AUTHORITATIVE_AUDIT_REQUIRED",
    }


def _partial_ecs(base: dict, advanced: dict) -> dict:
    direct_ratio = base.get("test_capability_ownership", {}).get("direct_test_ownership_ratio") or 0.0
    transitive_ratio = advanced["indirect_test_ownership"].get("transitive_test_reachability_ratio") or 0.0
    responsibility = advanced["canonical_responsibilities"]
    rows = []
    for name, bucket in responsibility.items():
        canonical_present = bool(bucket["canonical_targets_present"])
        candidate_count = bucket["candidate_count"]
        replacement_coverage_proxy = 1.0 if canonical_present and candidate_count <= len(bucket["canonical_targets_present"]) else (0.5 if canonical_present else 0.0)
        test_equivalence_proxy = round((direct_ratio + transitive_ratio) / 2, 4)
        rows.append({
            "subsystem": name,
            "replacement_coverage_proxy": replacement_coverage_proxy,
            "test_equivalence_repository_proxy": test_equivalence_proxy,
            "dependency_migration": None,
            "evidence_confidence": None,
            "ecs": None,
            "status": "PARTIAL_INPUTS_ONLY_NO_RETIREMENT_AUTHORITY",
        })
    return {"formula": "ECS = ReplacementCoverage * TestEquivalence * DependencyMigration * EvidenceConfidence", "subsystems": rows}


def analyze_advanced(root: Path) -> dict:
    base = base_analyze(root)
    modules, graph, _raw, top_imports = _python_import_graph(root)
    advanced = {
        "schema_caller_analysis": _schema_callers(root),
        "indirect_test_ownership": _indirect_test_ownership(modules, graph),
        "canonical_responsibilities": _responsibility_map(root, modules),
        "branch_analytics": _branch_analytics(root),
        "dependency_usage": _dependency_usage(root, top_imports),
    }
    advanced["partial_ecs_inputs"] = _partial_ecs(base, advanced)
    return {"schema_version": "2.0.0", "base_report": base, **advanced}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate advanced non-destructive Nexus convergence analytics.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="reports/nexus/repository-intelligence-advanced.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    payload = analyze_advanced(root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": str(output),
        "schemas_with_callers": payload["schema_caller_analysis"]["schemas_with_callers"],
        "transitive_test_ratio": payload["indirect_test_ownership"]["transitive_test_reachability_ratio"],
        "remote_branches": payload["branch_analytics"]["remote_branch_count"],
        "direct_dependencies": payload["dependency_usage"]["direct_dependency_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
