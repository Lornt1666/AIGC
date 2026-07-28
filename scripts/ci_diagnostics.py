#!/usr/bin/env python3
"""Generate redacted, deterministic CI and repository diagnostics receipts.

This utility intentionally avoids network calls, does not enumerate the complete
environment, and never attempts to diagnose a GitHub Actions failure that occurred
before a runner was allocated. Pre-runner failures require GitHub account/run API
metadata outside this process.

Exit codes:
    0  Diagnostics completed and strict requirements passed.
    2  Diagnostics completed, but --strict requirements failed.
    3  Invalid command-line input or unsafe output path.
    70 Unexpected internal error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "1.0"
COMMAND_TIMEOUT_SECONDS = 8

GITHUB_ENV_ALLOWLIST: tuple[str, ...] = (
    "GITHUB_REPOSITORY",
    "GITHUB_SHA",
    "GITHUB_REF",
    "GITHUB_REF_NAME",
    "GITHUB_EVENT_NAME",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_WORKFLOW",
    "GITHUB_JOB",
    "RUNNER_OS",
    "RUNNER_ARCH",
)

PROJECT_FILE_CANDIDATES: tuple[str, ...] = (
    ".python-version",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "tox.ini",
    "noxfile.py",
    "pytest.ini",
    "ruff.toml",
    ".ruff.toml",
    ".pre-commit-config.yaml",
    "Dockerfile",
    "compose.yaml",
    "docker-compose.yml",
)

REQUIRED_UPDATE_FILES: tuple[str, ...] = (
    "scripts/ci_diagnostics.py",
    ".github/workflows/ci-diagnostics.yml",
    "scripts/validate_secret_manifest.py",
    ".github/workflows/secret-manifest-validate.yml",
    "scripts/run_controlled_gemini_canary_sandbox.py",
    "docs/DEVPOST_SUBMISSION_TEMPLATE.md",
)

SECRET_NAME_RE = re.compile(
    r"(?i)(secret|password|passwd|token|api[_-]?key|private[_-]?key|credential|authorization|cookie)"
)
SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bgithub_pat_[0-9A-Za-z_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[0-9A-Za-z]{20,}\b"),
    re.compile(r"\bsk-[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"(?i)https?://[^/@\s:]+:[^/@\s]+@"),
)


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact_text(value: str, *, field_name: str = "") -> str:
    if not value:
        return value
    if SECRET_NAME_RE.search(field_name):
        return "[REDACTED]"
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            return "[REDACTED]"
    value = re.sub(r"(?i)(https?://)[^/@\s]+@", r"\1[REDACTED]@", value)
    value = re.sub(r"(?i)(https?://)[^/:@\s]+:[^/@\s]+@", r"\1[REDACTED]@", value)
    return value


def safe_command(argv: Sequence[str], *, cwd: Path, timeout: int = COMMAND_TIMEOUT_SECONDS) -> CommandResult:
    try:
        completed = subprocess.run(
            list(argv), cwd=str(cwd), check=False, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        return CommandResult(tuple(argv), completed.returncode,
                             redact_text(completed.stdout.strip())[:4096],
                             redact_text(completed.stderr.strip())[:4096])
    except subprocess.TimeoutExpired:
        return CommandResult(tuple(argv), None, "", "", timed_out=True, error="command_timeout")
    except OSError as exc:
        return CommandResult(tuple(argv), None, "", "", error=f"{type(exc).__name__}: {exc}")


def resolve_repo_root(start: Path) -> tuple[Path, bool]:
    start = start.resolve()
    result = safe_command(("git", "rev-parse", "--show-toplevel"), cwd=start)
    if result.returncode == 0 and result.stdout:
        candidate = Path(result.stdout).resolve()
        if candidate.exists() and candidate.is_dir():
            return candidate, True
    return start, False


def path_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ValueError(f"refusing to replace symlink: {path}")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                    dir=str(path.parent), prefix=f".{path.name}.",
                                    suffix=".tmp", delete=False) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_github_metadata(env: Mapping[str, str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in GITHUB_ENV_ALLOWLIST:
        raw = env.get(name)
        result[name.lower()] = redact_text(raw, field_name=name) if raw else None
    return result


def git_value(repo_root: Path, *args: str) -> str | None:
    result = safe_command(("git", *args), cwd=repo_root)
    if result.returncode == 0:
        value = result.stdout.strip()
        return value or None
    return None


def git_dirty(repo_root: Path) -> tuple[bool | None, int | None]:
    result = safe_command(("git", "status", "--porcelain=v1", "--untracked-files=no"), cwd=repo_root)
    if result.returncode != 0:
        return None, None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return bool(lines), len(lines)


def repository_identity(repo_root: Path, github_repository: str | None) -> dict[str, Any]:
    remote = git_value(repo_root, "config", "--get", "remote.origin.url")
    sanitized_remote = redact_text(remote or "") or None
    identity = github_repository
    if not identity and remote:
        match = re.search(r"github\.com[/:]([^/\s]+/[^/\s]+?)(?:\.git)?$", remote)
        if match:
            identity = match.group(1).removesuffix(".git")
    return {"name_with_owner": identity, "origin": sanitized_remote}


def inventory_workflows(repo_root: Path) -> list[dict[str, Any]]:
    directory = repo_root / ".github" / "workflows"
    if not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted((*directory.glob("*.yml"), *directory.glob("*.yaml"))):
        if path.is_symlink() or not path.is_file():
            continue
        records.append({"path": path.relative_to(repo_root).as_posix(),
                        "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return records


def required_file_results(repo_root: Path) -> list[dict[str, Any]]:
    return [{"path": relative,
             "exists": (repo_root / relative).is_file() and not (repo_root / relative).is_symlink()}
            for relative in REQUIRED_UPDATE_FILES]


def detected_project_files(repo_root: Path) -> list[str]:
    return [name for name in PROJECT_FILE_CANDIDATES if (repo_root / name).is_file()]


def build_receipt(repo_root: Path, *, is_git_repo: bool, env: Mapping[str, str]) -> dict[str, Any]:
    github = safe_github_metadata(env)
    warnings: list[str] = []
    errors: list[str] = []
    git_sha = git_value(repo_root, "rev-parse", "HEAD") if is_git_repo else None
    branch = git_value(repo_root, "branch", "--show-current") if is_git_repo else None
    commit_timestamp = git_value(repo_root, "show", "-s", "--format=%cI", "HEAD") if is_git_repo else None
    dirty, tracked_change_count = git_dirty(repo_root) if is_git_repo else (None, None)
    required = required_file_results(repo_root)
    missing = [item["path"] for item in required if not item["exists"]]
    if missing:
        errors.append(f"required update files missing: {len(missing)}")
    if not is_git_repo:
        errors.append("repository root is not a readable Git worktree")
    if git_sha and not re.fullmatch(r"[0-9a-fA-F]{40,64}", git_sha):
        errors.append("Git revision is not a full hexadecimal object identifier")
    if dirty:
        warnings.append("tracked working tree contains uncommitted changes")
    if not github.get("github_run_id"):
        warnings.append("GitHub Actions run metadata is unavailable; this appears to be a local execution")
    warnings.append("A runner-side script cannot diagnose failures that occurred before runner allocation; inspect GitHub run and account metadata for pre-runner restrictions.")
    identity = repository_identity(repo_root, github.get("github_repository") if isinstance(github.get("github_repository"), str) else None)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "overall_status": "pass" if not errors else "findings",
        "repository": identity,
        "repo_root": ".",
        "git": {"is_repository": is_git_repo, "sha": git_sha, "branch": branch,
                "commit_timestamp": commit_timestamp, "dirty": dirty,
                "tracked_change_count": tracked_change_count},
        "runtime": {"python_version": platform.python_version(),
                    "python_implementation": platform.python_implementation(),
                    "platform": platform.platform(), "system": platform.system(),
                    "machine": platform.machine()},
        "github": github,
        "required_file_results": required,
        "detected_project_files": detected_project_files(repo_root),
        "workflow_inventory": inventory_workflows(repo_root),
        "warnings": warnings,
        "errors": errors,
        "redactions_applied": True,
        "limitations": [
            "No network requests were performed.",
            "No complete environment dump was captured.",
            "Account-level billing, Actions-minutes, runner-allocation, and organization-policy state are not available from inside an unallocated runner.",
            "This receipt is diagnostic evidence, not deployment or production-readiness evidence.",
        ],
    }


def markdown_summary(receipt: Mapping[str, Any]) -> str:
    git = receipt["git"]
    repository = receipt["repository"]
    required = receipt["required_file_results"]
    lines = [
        "# AIGC CI Diagnostics Receipt", "",
        f"- **Generated:** `{receipt['generated_at_utc']}`",
        f"- **Status:** `{receipt['overall_status']}`",
        f"- **Repository:** `{repository.get('name_with_owner') or 'NOT DETERMINED'}`",
        f"- **Git SHA:** `{git.get('sha') or 'NOT DETERMINED'}`",
        f"- **Branch:** `{git.get('branch') or 'DETACHED OR NOT DETERMINED'}`",
        f"- **Tracked tree dirty:** `{git.get('dirty')}`", "",
        "## Required files", "", "| Path | Present |", "|---|---:|",
    ]
    for item in required:
        lines.append(f"| `{item['path']}` | `{str(item['exists']).lower()}` |")
    lines.extend(["", "## Warnings"])
    for warning in receipt["warnings"]:
        lines.append(f"- {warning}")
    lines.extend(["", "## Errors"])
    if receipt["errors"]:
        for error in receipt["errors"]:
            lines.append(f"- {error}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Truth boundary", ""])
    for limitation in receipt["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/ci-diagnostics"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        repo_root, is_git_repo = resolve_repo_root(args.repo_root)
        receipt = build_receipt(repo_root, is_git_repo=is_git_repo, env=os.environ)
        if args.run_id:
            observed = receipt["github"].get("github_run_id")
            receipt["expected_run_id"] = args.run_id
            receipt["run_id_match"] = observed == args.run_id if observed else None
            if observed and observed != args.run_id:
                receipt["errors"].append("supplied run ID does not match allowlisted GitHub metadata")
                receipt["overall_status"] = "findings"
        if args.output:
            json_path = args.output if args.output.is_absolute() else repo_root / args.output
            markdown_path = json_path.with_suffix(".md")
            output_root = json_path.parent
        else:
            output_root = args.output_dir if args.output_dir.is_absolute() else repo_root / args.output_dir
            json_path = output_root / "ci-diagnostics.json"
            markdown_path = output_root / "ci-diagnostics.md"
        if not path_within(repo_root, output_root):
            print("ERROR: output path must remain inside the repository root", file=sys.stderr)
            return 3
        atomic_write(json_path, json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        atomic_write(markdown_path, markdown_summary(receipt))
        print(json.dumps({"status": receipt["overall_status"],
                          "json_receipt": json_path.relative_to(repo_root).as_posix(),
                          "markdown_receipt": markdown_path.relative_to(repo_root).as_posix(),
                          "errors": len(receipt["errors"]),
                          "warnings": len(receipt["warnings"])}, sort_keys=True))
        if args.strict and receipt["errors"]:
            return 2
        return 0
    except (ValueError, argparse.ArgumentError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"INTERNAL_ERROR: {type(exc).__name__}", file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
