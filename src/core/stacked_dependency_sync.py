from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "schemas" / "stacked_dependency_sync_receipt.schema.json"
DEFAULT_RECEIPT = (
    ROOT
    / "governance"
    / "evolution"
    / "production_deployment_dependency_sync_receipt_v1.json"
)
_GIT_SHA = re.compile(r"^[a-f0-9]{40}$")


class StackedDependencySyncError(ValueError):
    """Raised when stacked dependency evidence is malformed or inconsistent."""


@dataclass(frozen=True)
class DependencyCurrentnessResult:
    """Current pull-request relationship evaluated against a historical receipt."""

    state: str
    current_stack: bool
    reason_codes: tuple[str, ...]
    pull_request: int
    downstream_branch: str
    downstream_head: str
    base_branch: str
    base_head: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "current_stack": self.current_stack,
            "reason_codes": list(self.reason_codes),
            "pull_request": self.pull_request,
            "downstream_branch": self.downstream_branch,
            "downstream_head": self.downstream_head,
            "base_branch": self.base_branch,
            "base_head": self.base_head,
        }


def canonical_receipt_digest(value: Mapping[str, Any]) -> str:
    """Return the deterministic digest for a receipt excluding identity fields."""

    material = deepcopy(dict(value))
    material.pop("receipt_id", None)
    material.pop("receipt_digest", None)
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def receipt_id_for_digest(digest: str) -> str:
    return "DSR-" + digest[:24].upper()


def _strict_validate(schema_path: Path, value: Mapping[str, Any]) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(dict(value)),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        raise StackedDependencySyncError(
            "Stacked dependency receipt validation failed: "
            + "; ".join(error.message for error in errors[:10])
        )


def validate_dependency_sync_receipt(
    value: Mapping[str, Any],
    *,
    schema_path: str | Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    """Validate structural, semantic, and deterministic receipt integrity."""

    receipt = deepcopy(dict(value))
    _strict_validate(Path(schema_path), receipt)

    upstream = dict(receipt["upstream"])
    downstream = dict(receipt["downstream"])
    alignment = dict(receipt["alignment"])

    if downstream["dependency_parent_head"] != upstream["head"]:
        raise StackedDependencySyncError(
            "Dependency merge parent must equal the exact recorded upstream head"
        )
    if downstream["synchronized_head"] == downstream["pre_synchronization_head"]:
        raise StackedDependencySyncError(
            "Synchronized head must differ from the pre-synchronization head"
        )

    imported_paths = list(alignment["imported_paths"])
    if imported_paths != sorted(imported_paths):
        raise StackedDependencySyncError(
            "Imported paths must be lexicographically sorted for deterministic evidence"
        )
    for raw_path in imported_paths:
        path = PurePosixPath(str(raw_path))
        if path.is_absolute() or ".." in path.parts or str(raw_path).startswith("/"):
            raise StackedDependencySyncError(
                f"Imported path is outside the repository boundary: {raw_path}"
            )

    digest = canonical_receipt_digest(receipt)
    if receipt["receipt_digest"] != digest:
        raise StackedDependencySyncError("Dependency receipt digest does not match content")
    if receipt["receipt_id"] != receipt_id_for_digest(digest):
        raise StackedDependencySyncError("Dependency receipt ID does not match content digest")
    return receipt


def load_dependency_sync_receipt(
    path: str | Path = DEFAULT_RECEIPT,
    *,
    schema_path: str | Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise StackedDependencySyncError("Stacked dependency receipt must be an object")
    return validate_dependency_sync_receipt(payload, schema_path=schema_path)


def _required_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise StackedDependencySyncError(f"{name} must be an object")
    return dict(value)


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise StackedDependencySyncError(f"{name} must be a non-empty string")
    return value


def _required_sha(value: Any, name: str) -> str:
    result = _required_string(value, name)
    if _GIT_SHA.fullmatch(result) is None:
        raise StackedDependencySyncError(f"{name} must be a 40-character Git SHA")
    return result


def evaluate_pull_request_dependency_currentness(
    receipt_value: Mapping[str, Any],
    event_value: Mapping[str, Any],
) -> DependencyCurrentnessResult:
    """Compare a receipt with the current GitHub pull-request event snapshot.

    The historical receipt remains immutable. This overlay declares the stack current
    only when the live PR base branch and base SHA still equal the recorded upstream
    branch and head. A temporary combined-main evaluation is recognized separately
    and never reported as a current stacked dependency.
    """

    receipt = validate_dependency_sync_receipt(receipt_value)
    event = _required_mapping(event_value, "GitHub event")
    pull_request = _required_mapping(event.get("pull_request"), "pull_request")
    head = _required_mapping(pull_request.get("head"), "pull_request.head")
    base = _required_mapping(pull_request.get("base"), "pull_request.base")

    number = pull_request.get("number", event.get("number"))
    if not isinstance(number, int) or number < 1:
        raise StackedDependencySyncError("pull_request.number must be a positive integer")

    head_branch = _required_string(head.get("ref"), "pull_request.head.ref")
    head_sha = _required_sha(head.get("sha"), "pull_request.head.sha")
    base_branch = _required_string(base.get("ref"), "pull_request.base.ref")
    base_sha = _required_sha(base.get("sha"), "pull_request.base.sha")

    upstream = dict(receipt["upstream"])
    downstream = dict(receipt["downstream"])
    verification = dict(receipt["verification"])
    reasons: list[str] = []

    if number != downstream["pull_request"]:
        reasons.append("PULL_REQUEST_MISMATCH")
    if head_branch != downstream["branch"]:
        reasons.append("DOWNSTREAM_BRANCH_MISMATCH")

    if base_branch == upstream["branch"]:
        if base_sha != upstream["head"]:
            reasons.append("UPSTREAM_HEAD_DRIFT")
        state = "CURRENT_STACK" if not reasons else "STALE_STACK"
        return DependencyCurrentnessResult(
            state=state,
            current_stack=not reasons,
            reason_codes=tuple(reasons),
            pull_request=number,
            downstream_branch=head_branch,
            downstream_head=head_sha,
            base_branch=base_branch,
            base_head=base_sha,
        )

    if (
        base_branch == "main"
        and verification.get("combined_main_ci_required") is True
        and not reasons
    ):
        return DependencyCurrentnessResult(
            state="COMBINED_MAIN_EVALUATION",
            current_stack=False,
            reason_codes=(),
            pull_request=number,
            downstream_branch=head_branch,
            downstream_head=head_sha,
            base_branch=base_branch,
            base_head=base_sha,
        )

    reasons.append("UPSTREAM_BASE_BRANCH_MISMATCH")
    return DependencyCurrentnessResult(
        state="STALE_STACK",
        current_stack=False,
        reason_codes=tuple(dict.fromkeys(reasons)),
        pull_request=number,
        downstream_branch=head_branch,
        downstream_head=head_sha,
        base_branch=base_branch,
        base_head=base_sha,
    )


def load_github_event_dependency_currentness(
    *,
    event_path: str | Path | None = None,
    receipt_path: str | Path = DEFAULT_RECEIPT,
    schema_path: str | Path = DEFAULT_SCHEMA,
) -> DependencyCurrentnessResult:
    """Load the GitHub Actions event and evaluate the current PR dependency edge."""

    raw_event_path = event_path or os.environ.get("GITHUB_EVENT_PATH")
    if raw_event_path is None or not str(raw_event_path):
        raise StackedDependencySyncError(
            "GITHUB_EVENT_PATH is required for dependency currentness validation"
        )
    resolved_event_path = Path(raw_event_path)
    if not resolved_event_path.is_file():
        raise StackedDependencySyncError(
            f"GitHub event file does not exist: {resolved_event_path}"
        )

    event = json.loads(resolved_event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise StackedDependencySyncError("GitHub event payload must be an object")
    receipt = load_dependency_sync_receipt(
        receipt_path,
        schema_path=schema_path,
    )
    return evaluate_pull_request_dependency_currentness(receipt, event)
