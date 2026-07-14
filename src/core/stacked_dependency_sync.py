from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
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


class StackedDependencySyncError(ValueError):
    """Raised when stacked dependency evidence is malformed or inconsistent."""


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
