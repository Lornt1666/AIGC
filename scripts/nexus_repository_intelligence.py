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


def _parse_python(root: Path, files: list[Path]):
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

    return modules, imports, syntax_errors, function_count, class_count, branch_points


def _resolve_internal_target(target: str, module_names: set[str]) -> str | None:
    candidates = [
        candidate
        for candidate in module_names
        if candidate == target or candidate.startswith(target + ".") or target.startswith(candidate + ".")
    ]
    return max(candidates, key=len) if candidates else None


def _strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph.get(node, set())):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] == indices[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return components


def _python_metrics(root: Path, files: list[Path]) -> tuple[dict, dict[str, set[str]], dict[str, str]]:
    modules, imports, syntax_errors, function_count, class_count, branch_points = _parse_python(root, files)
    module_names = set(modules)
    graph: dict[str, set[str]] = {module: set() for module in module_names}
    fan_in = Counter()
    fan_out = Counter()

    for source, targets in imports.items():
        if source not in module_names:
            continue
        for target in targets:
            chosen = _resolve_internal_target(target, module_names)
            if chosen is None or chosen == source:
                continue
            graph[source].add(chosen)
            fan_out[source] += 1
            fan_in[chosen] += 1

    hotspots = sorted(
        ({"module": module, "path": modules[module], "fan_in": fan_in[module], "fan_out": fan_out[module], "coupling": fan_in[module] + fan_out[module]} for module in module_names),
        key=lambda item: (-item["coupling"], item["module"]),
    )[:25]
    components = _strongly_connected_components(graph)
    cycles = [component for component in components if len(component) > 1]
    package_edges = Counter()
    for source, targets in graph.items():
        source_pkg = ".".join(source.split(".")[:2])
        for target in targets:
            target_pkg = ".".join(target.split(".")[:2])
            if source_pkg != target_pkg:
                package_edges[(source_pkg, target_pkg)] += 1

    return {
        "python_modules": len(modules),
        "functions": function_count,
        "classes": class_count,
        "branch_points_proxy": branch_points,
        "syntax_errors": syntax_errors,
        "internal_import_edges": sum(len(targets) for targets in graph.values()),
        "import_cycles": cycles[:50],
        "import_cycle_count": len(cycles),
        "coupling_hotspots": hotspots,
        "package_edges": [
            {"source": source, "target": target, "count": count}
            for (source, target), count in sorted(package_edges.items(), key=lambda item: (-item[1], item[0]))[:50]
        ],
    }, graph, modules


def _flatten_schema(node: object, prefix: str = "") -> set[str]:
    features: set[str] = set()
    if isinstance(node, dict):
        for key in ("type", "const", "enum", "format", "pattern"):
            if key in node:
                features.add(f"{prefix}@{key}:{json.dumps(node[key], sort_keys=True)}")
        required = node.get("required")
        if isinstance(required, list):
            for item in required:
                features.add(f"{prefix}@required:{item}")
        properties = node.get("properties")
        if isinstance(properties, dict):
            for name, child in properties.items():
                child_prefix = f"{prefix}.{name}" if prefix else name
                features.add(f"property:{child_prefix}")
                features.update(_flatten_schema(child, child_prefix))
        for combinator in ("allOf", "anyOf", "oneOf"):
            value = node.get(combinator)
            if isinstance(value, list):
                for index, child in enumerate(value):
                    features.update(_flatten_schema(child, f"{prefix}${combinator}[{index}]"))
        defs = node.get("$defs")
        if isinstance(defs, dict):
            for name, child in defs.items():
                features.update(_flatten_schema(child, f"$defs.{name}"))
    elif isinstance(node, list):
        for index, child in enumerate(node):
            features.update(_flatten_schema(child, f"{prefix}[{index}]"))
    return features


def _schema_overlap(root: Path, files: list[Path]) -> dict:
    schemas = []
    for path in files:
        if path.suffix.lower() != ".json" or ("schema" not in path.name.lower() and "schemas" not in path.parts):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not any(key in payload for key in ("$schema", "properties", "$defs", "type")):
            continue
        features = _flatten_schema(payload)
        schemas.append({
            "path": str(path.relative_to(root)),
            "id": payload.get("$id"),
            "title": payload.get("title"),
            "features": features,
        })

    pairs = []
    for index, left in enumerate(schemas):
        for right in schemas[index + 1:]:
            union = left["features"] | right["features"]
            if not union:
                continue
            intersection = left["features"] & right["features"]
            score = len(intersection) / len(union)
            if score >= 0.35 or (len(intersection) >= 8 and score >= 0.20):
                pairs.append({
                    "left": left["path"],
                    "right": right["path"],
                    "jaccard": round(score, 4),
                    "shared_features": len(intersection),
                    "left_features": len(left["features"]),
                    "right_features": len(right["features"]),
                })
    pairs.sort(key=lambda item: (-item["jaccard"], -item["shared_features"], item["left"], item["right"]))
    return {
        "schema_count": len(schemas),
        "overlap_candidate_count": len(pairs),
        "top_overlap_candidates": pairs[:50],
    }


def _test_ownership(root: Path, files: list[Path], graph: dict[str, set[str]], modules: dict[str, str]) -> dict:
    source_modules = {module for module, path in modules.items() if not path.startswith("tests/")}
    test_modules = {module for module, path in modules.items() if path.startswith("tests/")}
    owned_by_source: dict[str, set[str]] = defaultdict(set)
    source_by_test: dict[str, set[str]] = defaultdict(set)

    for test_module in sorted(test_modules):
        direct = {target for target in graph.get(test_module, set()) if target in source_modules}
        for target in direct:
            owned_by_source[target].add(test_module)
            source_by_test[test_module].add(target)

    unowned = sorted(source_modules - set(owned_by_source))
    broad_tests = sorted(
        ({"test": test, "owned_source_modules": len(targets), "targets": sorted(targets)[:30]} for test, targets in source_by_test.items()),
        key=lambda item: (-item["owned_source_modules"], item["test"]),
    )[:30]
    heavily_tested = sorted(
        ({"source": source, "test_modules": len(tests), "tests": sorted(tests)[:30]} for source, tests in owned_by_source.items()),
        key=lambda item: (-item["test_modules"], item["source"]),
    )[:30]

    return {
        "source_module_count": len(source_modules),
        "test_module_count": len(test_modules),
        "source_modules_with_direct_test_import": len(owned_by_source),
        "direct_test_ownership_ratio": round(len(owned_by_source) / len(source_modules), 4) if source_modules else None,
        "source_modules_without_direct_test_import_count": len(unowned),
        "source_modules_without_direct_test_import": unowned[:100],
        "broad_test_modules": broad_tests,
        "heavily_tested_source_modules": heavily_tested,
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
    py, graph, modules = _python_metrics(root, files)
    schemas = _schema_overlap(root, files)
    ownership = _test_ownership(root, files, graph, modules)

    tests = category_counts["tests"]
    source = category_counts["source"]
    report = {
        "schema_version": "1.1.1",
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
        "schema_semantic_overlap": schemas,
        "test_capability_ownership": ownership,
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
