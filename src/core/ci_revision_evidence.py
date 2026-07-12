from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.contract_validator import validate_artifact, validate_file


RECEIPT_SCHEMA = "ci_revision_evidence_receipt"
SCHEMA_VERSION = "2.0.0"
EVIDENCE_CLASS = "immutable_checked_out_revision"
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_EVENTS = {"push", "pull_request", "workflow_dispatch", "unknown"}
RECEIPT_KEYS = {
    "schema_version",
    "receipt_id",
    "created_at",
    "event_name",
    "expected_revision",
    "actual_revision",
    "verified",
    "evidence_class",
    "operator_review_required",
    "external_action_performed",
}


class CIRevisionEvidenceError(ValueError):
    """Raised when CI evidence is not bound to the immutable checked-out revision."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def normalize_revision(value: str, label: str) -> str:
    revision = value.strip().lower()
    if not REVISION_PATTERN.fullmatch(revision):
        raise CIRevisionEvidenceError(
            f"{label} must be a full 40-character hexadecimal commit SHA."
        )
    return revision


def normalize_event_name(value: str) -> str:
    event_name = value.strip() or "unknown"
    return event_name if event_name in ALLOWED_EVENTS else "unknown"


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
        raise CIRevisionEvidenceError(f"Unable to read checked-out revision: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or "git rev-parse HEAD failed"
        raise CIRevisionEvidenceError(detail)
    return normalize_revision(result.stdout, "actual_revision")


def validate_receipt(receipt: dict[str, Any]) -> None:
    unknown = sorted(set(receipt) - RECEIPT_KEYS)
    missing = sorted(RECEIPT_KEYS - set(receipt))
    if unknown or missing:
        raise CIRevisionEvidenceError(
            f"Revision receipt keys invalid; unknown={unknown}, missing={missing}"
        )
    if receipt["schema_version"] != SCHEMA_VERSION:
        raise CIRevisionEvidenceError("Unexpected revision receipt schema version.")
    if receipt["evidence_class"] != EVIDENCE_CLASS:
        raise CIRevisionEvidenceError("Unexpected revision evidence class.")
    if receipt["operator_review_required"] is not True:
        raise CIRevisionEvidenceError("Revision evidence cannot waive operator review.")
    if receipt["external_action_performed"] is not False:
        raise CIRevisionEvidenceError("Revision verification cannot claim external action.")
    expected = normalize_revision(str(receipt["expected_revision"]), "expected_revision")
    actual = normalize_revision(str(receipt["actual_revision"]), "actual_revision")
    if bool(receipt["verified"]) != (expected == actual):
        raise CIRevisionEvidenceError("Revision receipt verification state is inconsistent.")


def build_receipt(expected_revision: str, actual_revision: str, event_name: str) -> dict[str, Any]:
    expected = normalize_revision(expected_revision, "expected_revision")
    actual = normalize_revision(actual_revision, "actual_revision")
    event = normalize_event_name(event_name)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": make_id("AIGC-CI-REVISION", expected, actual, event),
        "created_at": utc_now(),
        "event_name": event,
        "expected_revision": expected,
        "actual_revision": actual,
        "verified": expected == actual,
        "evidence_class": EVIDENCE_CLASS,
        "operator_review_required": True,
        "external_action_performed": False,
    }
    validate_receipt(receipt)
    validate_artifact(RECEIPT_SCHEMA, receipt)
    return receipt


def verify_ci_revision(project_root: Path, expected_revision: str, event_name: str) -> dict[str, Any]:
    actual_revision = read_git_head(project_root.resolve())
    receipt = build_receipt(expected_revision, actual_revision, event_name)
    if receipt["verified"] is not True:
        raise CIRevisionEvidenceError(
            "CI revision mismatch: "
            f"expected {receipt['expected_revision']}, checked out {receipt['actual_revision']}."
        )
    return receipt


def write_receipt(receipt: dict[str, Any], output_path: Path) -> Path:
    validate_receipt(receipt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    validate_file(RECEIPT_SCHEMA, output_path)
    return output_path
