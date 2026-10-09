from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any


MANIFEST_NAME = "evidence-manifest.json"
STATUS_NAME = "run-status.json"
EXPECTED_CONTRACT = "AIGC-LOCAL-CI-EVIDENCE-MANIFEST-001"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_FILES = {
    "evidence-context.json",
    "repository-state.json",
    "logs/contract-validation.log",
    "logs/aec-001-validation.log",
    "logs/redaction-scan.log",
    "logs/provider-discovery-mock.log",
    "provider_discovery_simulation/target_specification_submission.json",
    "provider_discovery_simulation/command_plan.json",
    "provider_discovery_simulation/discovery_simulation_report.json",
    "provider_discovery_simulation/provenance_envelope.json",
    "terraform_validation/terraform.lock.hcl",
    "terraform_validation/terraform-fmt.log",
    "terraform_validation/terraform-init.log",
    "terraform_validation/terraform-validate.log",
    "terraform_validation/terraform-plan.log",
    "terraform_validation/inert-plan.json",
    "terraform_validation/inert-plan-summary.json",
    "test_results/pytest.log",
    "logs/production-readiness.log",
}


class EvidenceManifestError(ValueError):
    """Raised when a local evidence bundle is incomplete or has drifted."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceManifestError(f"Unable to load JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise EvidenceManifestError(f"Expected JSON object: {path}")
    return value


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise EvidenceManifestError(f"Unsafe manifest path: {value!r}")
    return path


def bundle_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise EvidenceManifestError(f"Symlinks are prohibited in evidence bundles: {path}")
        if not path.is_file() or path.name in {MANIFEST_NAME, STATUS_NAME}:
            continue
        relative = path.relative_to(root).as_posix()
        files[relative] = path
    return files


def validate_context(root: Path, source_revision: str) -> None:
    context = load_json(root / "evidence-context.json")
    state = load_json(root / "repository-state.json")

    if context.get("contract_id") != "AIGC-LOCAL-CI-EVIDENCE-CONTEXT-001":
        raise EvidenceManifestError("Evidence context contract mismatch")
    if context.get("source_revision") != source_revision:
        raise EvidenceManifestError("Evidence context revision mismatch")
    if context.get("mode") != "LOCAL_SUPPLEMENTAL_FAIL_CLOSED":
        raise EvidenceManifestError("Evidence context mode mismatch")

    expected_flags = {
        "hosted_ci_replacement": False,
        "operator_review_required": True,
        "provider_action_performed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }
    for key, expected in expected_flags.items():
        if context.get(key) is not expected:
            raise EvidenceManifestError(f"Evidence context flag mismatch: {key}")

    if state.get("contract_id") != "AIGC-LOCAL-CI-REPOSITORY-STATE-001":
        raise EvidenceManifestError("Repository-state contract mismatch")
    if state.get("source_revision") != source_revision:
        raise EvidenceManifestError("Repository-state revision mismatch")
    for key in ("worktree_clean", "index_clean", "tracked_diff_clean", "untracked_clean"):
        if state.get(key) is not True:
            raise EvidenceManifestError(f"Repository state is not clean: {key}")
    if state.get("head_object_type") != "commit":
        raise EvidenceManifestError("HEAD is not bound to a commit object")

    expected_revision = str(state.get("expected_revision", ""))
    if expected_revision and expected_revision != source_revision:
        raise EvidenceManifestError("Operator-supplied expected revision mismatch")
    expected_pr = state.get("expected_pr_number")
    if expected_pr is not None and (not isinstance(expected_pr, int) or expected_pr <= 0):
        raise EvidenceManifestError("expected_pr_number must be a positive integer or null")


def validate_manifest(root: Path, expected_revision: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    manifest = load_json(manifest_path)

    if manifest.get("contract_id") != EXPECTED_CONTRACT:
        raise EvidenceManifestError("Manifest contract mismatch")
    source_revision = str(manifest.get("source_revision", ""))
    if not HEX40.fullmatch(source_revision):
        raise EvidenceManifestError("Manifest source_revision is not an exact SHA-1")
    if expected_revision and source_revision != expected_revision:
        raise EvidenceManifestError("Manifest does not match the expected revision")

    expected_flags = {
        "hosted_ci_replacement": False,
        "operator_review_required": True,
        "provider_action_performed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }
    for key, expected in expected_flags.items():
        if manifest.get(key) is not expected:
            raise EvidenceManifestError(f"Manifest flag mismatch: {key}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise EvidenceManifestError("Manifest artifacts must be a list")
    if manifest.get("artifact_count") != len(artifacts):
        raise EvidenceManifestError("Manifest artifact_count mismatch")

    declared: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            raise EvidenceManifestError("Manifest artifact entries must be objects")
        relative = safe_relative_path(str(item.get("path", ""))).as_posix()
        if relative in declared:
            raise EvidenceManifestError(f"Duplicate manifest path: {relative}")
        digest = str(item.get("sha256", ""))
        size = item.get("size_bytes")
        if not HEX64.fullmatch(digest):
            raise EvidenceManifestError(f"Invalid SHA-256 for {relative}")
        if not isinstance(size, int) or size < 0:
            raise EvidenceManifestError(f"Invalid size for {relative}")
        declared[relative] = item

    actual = bundle_files(root)
    if set(actual) != set(declared):
        missing = sorted(set(declared) - set(actual))
        unexpected = sorted(set(actual) - set(declared))
        raise EvidenceManifestError(
            f"Manifest file-set mismatch; missing={missing}, unexpected={unexpected}"
        )

    missing_required = sorted(REQUIRED_FILES - set(actual))
    if missing_required:
        raise EvidenceManifestError(f"Required evidence files are missing: {missing_required}")
    readiness_json = list((root / "production_readiness").rglob("*.json"))
    if not readiness_json:
        raise EvidenceManifestError("Canonical production-readiness JSON evidence is missing")

    for relative, path in actual.items():
        digest = sha256(path.read_bytes()).hexdigest()
        size = path.stat().st_size
        declared_item = declared[relative]
        if digest != declared_item["sha256"]:
            raise EvidenceManifestError(f"Digest mismatch: {relative}")
        if size != declared_item["size_bytes"]:
            raise EvidenceManifestError(f"Size mismatch: {relative}")

    validate_context(root, source_revision)
    return {
        "contract_id": "AIGC-LOCAL-CI-EVIDENCE-VERIFICATION-001",
        "source_revision": source_revision,
        "artifact_count": len(actual),
        "manifest_valid": True,
        "required_artifacts_present": True,
        "hosted_ci_replacement": False,
        "operator_review_required": True,
        "provider_action_performed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify an AIGC local CI evidence bundle.")
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("--expected-revision", default="")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_manifest(
        args.evidence_root,
        expected_revision=args.expected_revision or None,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
