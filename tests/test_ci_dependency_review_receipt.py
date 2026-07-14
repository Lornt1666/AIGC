from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil

from jsonschema import ValidationError
import pytest

from src.core.ci_dependency_review_receipt import (
    build_dependency_review_receipt,
    validate_receipt,
    write_receipt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "a" * 40
CREATED_AT = "2026-07-12T10:00:00Z"


def _manifest() -> dict:
    path = PROJECT_ROOT / "governance" / "ci" / "ci_action_dependency_manifest_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_dependency_review_receipt_matches_repository_topology(tmp_path: Path) -> None:
    receipt = build_dependency_review_receipt(
        PROJECT_ROOT,
        source_revision=SOURCE_REVISION,
        created_at=CREATED_AT,
    )
    manifest = _manifest()

    assert receipt["validation_conclusion"] == "PASS"
    assert receipt["mismatches"] == []
    assert receipt["source_revision"] == SOURCE_REVISION
    assert receipt["manifest_id"] == manifest["manifest_id"]
    assert receipt["observed_reference_count"] == sum(
        entry["expected_occurrences"] for entry in manifest["actions"]
    )
    assert {item["path"] for item in receipt["workflow_files"]} == {
        ".github/workflows/aigc-ci.yml",
        ".github/workflows/aigc_constellation_trigger.yml",
    }
    assert len(receipt["manifest_sha256"]) == 64
    validate_receipt(PROJECT_ROOT, receipt)

    output = tmp_path / "receipt.json"
    write_receipt(PROJECT_ROOT, receipt, output)
    assert json.loads(output.read_text(encoding="utf-8")) == receipt


def test_dependency_review_receipt_identity_is_content_deterministic() -> None:
    first = build_dependency_review_receipt(
        PROJECT_ROOT,
        source_revision=SOURCE_REVISION,
        created_at="2026-07-12T10:00:00Z",
    )
    second = build_dependency_review_receipt(
        PROJECT_ROOT,
        source_revision=SOURCE_REVISION,
        created_at="2026-07-12T10:05:00Z",
    )

    assert first["receipt_id"] == second["receipt_id"]
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert first["workflow_files"] == second["workflow_files"]
    assert first["created_at"] != second["created_at"]


def test_dependency_review_receipt_fails_closed_on_mutable_reference(
    tmp_path: Path,
) -> None:
    shutil.copytree(PROJECT_ROOT / ".github", tmp_path / ".github")
    shutil.copytree(PROJECT_ROOT / "governance" / "ci", tmp_path / "governance" / "ci")
    shutil.copytree(
        PROJECT_ROOT / "governance" / "schemas" / "ci",
        tmp_path / "governance" / "schemas" / "ci",
    )

    workflow_path = tmp_path / ".github" / "workflows" / "aigc-ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    workflow = workflow.replace(
        "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
        "actions/checkout@v4",
        1,
    )
    workflow_path.write_text(workflow, encoding="utf-8")

    receipt = build_dependency_review_receipt(
        tmp_path,
        source_revision=SOURCE_REVISION,
        created_at=CREATED_AT,
    )

    assert receipt["validation_conclusion"] == "FAIL"
    assert receipt["mismatches"]
    assert any("mutable or invalid revision" in item for item in receipt["mismatches"])
    validate_receipt(tmp_path, receipt)


def test_receipt_contract_rejects_false_pass_with_mismatch() -> None:
    receipt = build_dependency_review_receipt(
        PROJECT_ROOT,
        source_revision=SOURCE_REVISION,
        created_at=CREATED_AT,
    )
    invalid = deepcopy(receipt)
    invalid["mismatches"] = ["fabricated mismatch"]

    with pytest.raises(ValidationError):
        validate_receipt(PROJECT_ROOT, invalid)
