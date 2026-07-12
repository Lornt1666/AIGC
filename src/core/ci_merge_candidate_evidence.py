from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.ci_revision_evidence import normalize_revision, read_git_head
from src.core.contract_validator import validate_artifact, validate_file


RECEIPT_SCHEMA = "ci_merge_candidate_evidence_receipt"
SCHEMA_VERSION = "2.0.0"
EVIDENCE_CLASS = "pull_request_merge_candidate"
RECEIPT_KEYS = {
    "schema_version",
    "receipt_id",
    "created_at",
    "event_name",
    "base_revision",
    "head_revision",
    "expected_merge_revision",
    "actual_revision",
    "base_is_ancestor",
    "head_is_ancestor",
    "verified",
    "evidence_class",
    "operator_review_required",
    "external_action_performed",
}


class CIMergeCandidateEvidenceError(ValueError):
    """Raised when a pull-request merge candidate cannot be proven."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def git_is_ancestor(project_root: Path, ancestor: str, descendant: str) -> bool:
    ancestor_revision = normalize_revision(ancestor, "ancestor_revision")
    descendant_revision = normalize_revision(descendant, "descendant_revision")
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor_revision, descendant_revision],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CIMergeCandidateEvidenceError(f"Unable to verify merge ancestry: {exc}") from exc
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = result.stderr.strip() or "git merge-base --is-ancestor failed"
    raise CIMergeCandidateEvidenceError(detail)


def validate_receipt(receipt: dict[str, Any]) -> None:
    unknown = sorted(set(receipt) - RECEIPT_KEYS)
    missing = sorted(RECEIPT_KEYS - set(receipt))
    if unknown or missing:
        raise CIMergeCandidateEvidenceError(
            f"Merge-candidate receipt keys invalid; unknown={unknown}, missing={missing}"
        )
    if receipt["schema_version"] != SCHEMA_VERSION:
        raise CIMergeCandidateEvidenceError("Unexpected merge-candidate schema version.")
    if receipt["event_name"] != "pull_request":
        raise CIMergeCandidateEvidenceError("Merge-candidate evidence is valid only for pull requests.")
    if receipt["evidence_class"] != EVIDENCE_CLASS:
        raise CIMergeCandidateEvidenceError("Unexpected merge-candidate evidence class.")
    if receipt["operator_review_required"] is not True:
        raise CIMergeCandidateEvidenceError("Merge-candidate evidence cannot waive operator review.")
    if receipt["external_action_performed"] is not False:
        raise CIMergeCandidateEvidenceError("Merge-candidate verification cannot claim external action.")

    expected_merge = normalize_revision(
        str(receipt["expected_merge_revision"]), "expected_merge_revision"
    )
    actual = normalize_revision(str(receipt["actual_revision"]), "actual_revision")
    normalize_revision(str(receipt["base_revision"]), "base_revision")
    normalize_revision(str(receipt["head_revision"]), "head_revision")
    expected_verified = (
        expected_merge == actual
        and receipt["base_is_ancestor"] is True
        and receipt["head_is_ancestor"] is True
    )
    if bool(receipt["verified"]) != expected_verified:
        raise CIMergeCandidateEvidenceError(
            "Merge-candidate receipt verification state is inconsistent."
        )


def build_receipt(
    base_revision: str,
    head_revision: str,
    expected_merge_revision: str,
    actual_revision: str,
    *,
    base_is_ancestor: bool,
    head_is_ancestor: bool,
) -> dict[str, Any]:
    base = normalize_revision(base_revision, "base_revision")
    head = normalize_revision(head_revision, "head_revision")
    expected_merge = normalize_revision(expected_merge_revision, "expected_merge_revision")
    actual = normalize_revision(actual_revision, "actual_revision")
    verified = expected_merge == actual and base_is_ancestor and head_is_ancestor
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": make_id("AIGC-CI-MERGE", base, head, expected_merge, actual),
        "created_at": utc_now(),
        "event_name": "pull_request",
        "base_revision": base,
        "head_revision": head,
        "expected_merge_revision": expected_merge,
        "actual_revision": actual,
        "base_is_ancestor": bool(base_is_ancestor),
        "head_is_ancestor": bool(head_is_ancestor),
        "verified": bool(verified),
        "evidence_class": EVIDENCE_CLASS,
        "operator_review_required": True,
        "external_action_performed": False,
    }
    validate_receipt(receipt)
    validate_artifact(RECEIPT_SCHEMA, receipt)
    return receipt


def verify_merge_candidate(
    project_root: Path,
    base_revision: str,
    head_revision: str,
    expected_merge_revision: str,
) -> dict[str, Any]:
    root = project_root.resolve()
    actual = read_git_head(root)
    receipt = build_receipt(
        base_revision,
        head_revision,
        expected_merge_revision,
        actual,
        base_is_ancestor=git_is_ancestor(root, base_revision, actual),
        head_is_ancestor=git_is_ancestor(root, head_revision, actual),
    )
    if receipt["verified"] is not True:
        raise CIMergeCandidateEvidenceError(
            "Pull-request merge candidate is not bound to the expected base, head and checkout."
        )
    return receipt


def write_receipt(receipt: dict[str, Any], output_path: Path) -> Path:
    validate_receipt(receipt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    validate_file(RECEIPT_SCHEMA, output_path)
    return output_path
