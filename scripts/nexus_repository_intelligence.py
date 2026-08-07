from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEXT_EXTENSIONS = {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".tf", ".html", ".css", ".js", ".ts", ".tsx", ".sh", ".ps1", ".bat"}
SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".tsx"}
DOC_EXTENSIONS = {".md", ".rst"}
INFRA_EXTENSIONS = {".tf"}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml"}


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        yield path


def _safe_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {"Dockerfile", "requirements.txt"}:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _module_name(root: Path, path: Path) -> str | None:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


def _python_metrics(root: Path, files: list[Path]) -> dict:
    modules: dict[str, str] = {}
    imports: dict[str, set[str]] = defaultdict(set)
    syntax_errors: list[str] = []
    function_count = class_count = branch_points = 0

    for path in files:
        if path.suffix != ".py":
            continue
        text = _safe_text(path)
        if text is None:
            continue
        module = _module_name(root, path)
        if module:
            modules[module] = str(path.relative_to(root))
        try:
            tree = ast.parse(text)
        except SyntaxError:
            syntax_errors.append(str(path.relative_to(root)))
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_count += 1
            elif isinstance(node, ast.ClassDef):
                class_count += 1
            elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.BoolOp, ast.Match, ast.IfExp)):
                branch_points += 1
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports[module or str(path)].add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports[module or str(path)].add(node.module)

    internal_edges: list[tuple[str, str]] = []
    fan_in = Counter()
    fan_out = Counter()
    module_names = set(modules)
    for source, targets in imports.items():
        for target in targets:
            matches = [candidate for candidate in module_names if candidate == target or candidate.startswith(target + ".") or target.startswith(candidate + ".")]
            if not matches:
                continue
            chosen = min(matches, key=len)
            internal_edges.append((source, chosen))
            fan_out[source] += 1
            fan_in[chosen] += 1

    hotspots = sorted(
        ({"module": module, "fan_in": fan_in[module], "fan_out": fan_out[module], "coupling": fan_in[module] + fan_out[module]} for module in module_names),
        key=lambda item: (-item["coupling"], item["module"]),
    )[:25]

    return {
        "python_modules": len(modules),
        "functions": function_count,
        "classes": class_count,
        "branch_points_proxy": branch_points,
        "syntax_errors": syntax_errors,
        "internal_import_edges": len(set(internal_edges)),
        "coupling_hotspots": hotspots,
    }


def analyze(root: Path) -> dict:
    files = list(_iter_files(root))
    extension_counts = Counter()
    category_counts = Counter()
    line_counts = Counter()
    digest_groups: dict[str, list[str]] = defaultdict(list)
    basename_groups: dict[str, list[str]] = defaultdict(list)

    for path in files:
        rel = str(path.relative_to(root))
        suffix = path.suffix.lower() or "<none>"
        extension_counts[suffix] += 1
        basename_groups[path.name.lower()].append(rel)

        text = _safe_text(path)
        if text is not None:
            lines = text.count("\n") + (1 if text else 0)
            line_counts[suffix] += lines
            digest_groups[hashlib.sha256(text.encode("utf-8")).hexdigest()].append(rel)

        parts = set(path.parts)
        if "tests" in parts or path.name.startswith("test_"):
            category_counts["tests"] += 1
        if path.suffix.lower() in SOURCE_EXTENSIONS and "tests" not in parts:
            category_counts["source"] += 1
        if path.suffix.lower() in DOC_EXTENSIONS or "docs" in parts:
            category_counts["documentation"] += 1
        if path.suffix.lower() in INFRA_EXTENSIONS or "infra" in parts:
            category_counts["infrastructure"] += 1
        if path.suffix.lower() in CONFIG_EXTENSIONS or "config" in parts or "schemas" in parts:
            category_counts["configuration_schema"] += 1
        if ".github" in parts:
            category_counts["github_automation"] += 1

    exact_duplicates = [group for group in digest_groups.values() if len(group) > 1]
    repeated_basenames = [group for group in basename_groups.values() if len(group) > 1]
    py = _python_metrics(root, files)

    tests = category_counts["tests"]
    source = category_counts["source"]
    report = {
        "schema_version": "1.0.0",
        "root": str(root),
        "summary": {
            "total_files": len(files),
            "source_files": source,
            "test_files": tests,
            "documentation_files": category_counts["documentation"],
            "infrastructure_files": category_counts["infrastructure"],
            "configuration_schema_files": category_counts["configuration_schema"],
            "github_automation_files": category_counts["github_automation"],
            "test_to_source_ratio": round(tests / source, 4) if source else None,
            "text_lines": sum(line_counts.values()),
        },
        "extensions": dict(sorted(extension_counts.items())),
        "lines_by_extension": dict(sorted(line_counts.items())),
        "python": py,
        "duplication": {
            "exact_duplicate_groups": len(exact_duplicates),
            "exact_duplicate_files": sum(len(group) for group in exact_duplicates),
            "largest_exact_duplicate_groups": sorted(exact_duplicates, key=lambda g: (-len(g), g))[:20],
            "repeated_basename_groups": len(repeated_basenames),
            "largest_repeated_basename_groups": sorted(repeated_basenames, key=lambda g: (-len(g), g))[:20],
        },
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic AIGC Nexus repository intelligence.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="reports/nexus/repository-intelligence.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = analyze(root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "sha256": report["report_sha256"], **report["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
