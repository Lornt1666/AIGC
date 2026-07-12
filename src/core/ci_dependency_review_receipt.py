from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA_VERSION = "1.0.0"
EVIDENCE_CLASS = "ci_dependency_topology_review"
MANIFEST_RELATIVE_PATH = Path(
    "governance/ci/ci_action_dependency_manifest_v1.json"
)
MANIFEST_SCHEMA_RELATIVE_PATH = Path(
    "governance/schemas/ci/ci_action_dependency_manifest.schema.json"
)
RECEIPT_SCHEMA_RELATIVE_PATH = Path(
    "governance/schemas/ci/ci_dependency_review_receipt.schema.json"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
USES_LINE = re.compile(
    r"^\s*uses:\s*[\"']?([^\"'\s#]+)[\"']?",
    re.MULTILINE,
)


class CIDependencyReviewError(ValueError):
    """Raised when CI dependency evidence cannot be constructed safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CIDependencyReviewError(f"Unable to read JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CIDependencyReviewError(f"JSON artifact {path} must contain an object.")
    return payload


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise CIDependencyReviewError(f"Unable to hash {path}: {exc}") from exc


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _normalize_revision(value: str, label: str) -> str:
    revision = value.strip().lower()
    if not FULL_SHA.fullmatch(revision):
        raise CIDependencyReviewError(
            f"{label} must be a full 40-character lowercase hexadecimal commit SHA."
        )
    return revision


def read_git_head(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CIDependencyReviewError(f"Unable to read checked-out revision: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or "git rev-parse HEAD failed"
        raise CIDependencyReviewError(detail)
    return _normalize_revision(result.stdout, "source_revision")


def _workflow_paths(project_root: Path, workflow_root: str) -> list[Path]:
    root = project_root / workflow_root
    paths = {*root.rglob("*.yml"), *root.rglob("*.yaml")}
    return sorted(path for path in paths if path.is_file())


def _external_action_references(
    project_root: Path,
    workflow_paths: list[Path],
) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for workflow_path in workflow_paths:
        try:
            workflow = workflow_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CIDependencyReviewError(
                f"Unable to inspect workflow {workflow_path}: {exc}"
            ) from exc
        for token in USES_LINE.findall(workflow):
            if token.startswith("./"):
                continue
            if "@" not in token:
                action, revision = token, ""
            else:
                action, revision = token.rsplit("@", 1)
            references.append(
                {
                    "workflow": workflow_path.relative_to(project_root).as_posix(),
                    "action": action,
                    "revision": revision.lower(),
                }
            )
    return references


def _validate_manifest(
    project_root: Path,
    manifest: dict[str, Any],
) -> None:
    schema = _read_json(project_root / MANIFEST_SCHEMA_RELATIVE_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(manifest)


def _inspect_dependencies(
    project_root: Path,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
    workflow_root = str(manifest["workflow_roots"][0])
    workflow_paths = _workflow_paths(project_root, workflow_root)
    references = _external_action_references(project_root, workflow_paths)
    mismatches: list[str] = []

    if not workflow_paths:
        mismatches.append(f"no workflow files found under {workflow_root}")
    if not references:
        mismatches.append("no external action references were observed")

    approved_entries = list(manifest["actions"])
    approved: dict[str, dict[str, Any]] = {}
    for entry in approved_entries:
        action = str(entry["action_repository"])
        if action in approved:
            mismatches.append(f"duplicate manifest entry for {action}")
        approved[action] = entry

    observed_revisions: dict[str, set[str]] = defaultdict(set)
    observed_workflows: dict[str, set[str]] = defaultdict(set)
    occurrences: Counter[str] = Counter()

    for reference in references:
        action = reference["action"]
        revision = reference["revision"]
        workflow = reference["workflow"]
        occurrences[action] += 1
        observed_revisions[action].add(revision)
        observed_workflows[action].add(workflow)

        if not FULL_SHA.fullmatch(revision):
            mismatches.append(
                f"{workflow}: {action} uses mutable or invalid revision {revision!r}"
            )
        entry = approved.get(action)
        if entry is None:
            mismatches.append(f"{workflow}: unapproved action repository {action}")
            continue
        expected = str(entry["approved_revision"])
        if revision != expected:
            mismatches.append(
                f"{workflow}: {action} revision {revision!r} does not match {expected}"
            )

    observed_action_set = set(occurrences)
    approved_action_set = set(approved)
    for action in sorted(observed_action_set - approved_action_set):
        mismatches.append(f"observed action {action} is absent from the manifest")
    for action in sorted(approved_action_set - observed_action_set):
        mismatches.append(f"approved action {action} is absent from all workflows")

    for action, entry in approved.items():
        expected_occurrences = int(entry["expected_occurrences"])
        observed_occurrences = occurrences[action]
        if observed_occurrences != expected_occurrences:
            mismatches.append(
                f"{action} occurrence count differs: observed={observed_occurrences}, "
                f"approved={expected_occurrences}"
            )

    actions: list[dict[str, Any]] = []
    for action in sorted(observed_action_set):
        entry = approved.get(action)
        actions.append(
            {
                "action_repository": action,
                "approved_revision": (
                    str(entry["approved_revision"]) if entry is not None else None
                ),
                "observed_revisions": sorted(observed_revisions[action]),
                "observed_occurrences": occurrences[action],
                "workflow_paths": sorted(observed_workflows[action]),
            }
        )

    workflow_files = [
        {
            "path": path.relative_to(project_root).as_posix(),
            "sha256": _sha256_file(path),
        }
        for path in workflow_paths
    ]
    return workflow_files, actions, sorted(set(mismatches))


def validate_receipt(project_root: Path, receipt: dict[str, Any]) -> None:
    schema = _read_json(project_root / RECEIPT_SCHEMA_RELATIVE_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(receipt)


def build_dependency_review_receipt(
    project_root: Path,
    source_revision: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    revision = (
        _normalize_revision(source_revision, "source_revision")
        if source_revision is not None
        else read_git_head(root)
    )
    manifest_path = root / MANIFEST_RELATIVE_PATH
    manifest = _read_json(manifest_path)
    _validate_manifest(root, manifest)

    workflow_files, observed_actions, mismatches = _inspect_dependencies(root, manifest)
    conclusion = "PASS" if not mismatches else "FAIL"
    manifest_digest = _sha256_file(manifest_path)
    identity_basis = {
        "source_revision": revision,
        "manifest_sha256": manifest_digest,
        "workflow_files": workflow_files,
        "observed_actions": observed_actions,
        "mismatches": mismatches,
        "validation_conclusion": conclusion,
    }
    receipt_id = (
        "AIGC-CI-DEPENDENCY-REVIEW-"
        + _canonical_digest(identity_basis)[:16].upper()
    )
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "created_at": created_at or utc_now(),
        "source_revision": revision,
        "evidence_class": EVIDENCE_CLASS,
        "manifest_id": str(manifest["manifest_id"]),
        "manifest_version": str(manifest["version"]),
        "manifest_path": MANIFEST_RELATIVE_PATH.as_posix(),
        "manifest_sha256": manifest_digest,
        "workflow_root": str(manifest["workflow_roots"][0]),
        "workflow_files": workflow_files,
        "observed_actions": observed_actions,
        "observed_reference_count": sum(
            int(action["observed_occurrences"]) for action in observed_actions
        ),
        "mismatches": mismatches,
        "validation_conclusion": conclusion,
        "operator_review_required": True,
        "automatic_merge_allowed": False,
        "external_action_performed": False,
    }
    validate_receipt(root, receipt)
    return receipt


def write_receipt(
    project_root: Path,
    receipt: dict[str, Any],
    output_path: Path,
) -> Path:
    validate_receipt(project_root.resolve(), receipt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return output_path
