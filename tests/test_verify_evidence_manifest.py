from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts.verify_evidence_manifest import (
    EvidenceManifestError,
    REQUIRED_FILES,
    validate_manifest,
)


REVISION = "a" * 40


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "evidence"
    for relative in REQUIRED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            write_json(path, {"status": "test-evidence"})
        else:
            path.write_text("test-evidence\n", encoding="utf-8")

    write_json(
        root / "production_readiness" / "production-readiness-report.json",
        {"production_ready": False, "source_revision": REVISION},
    )
    write_json(
        root / "evidence-context.json",
        {
            "contract_id": "AIGC-LOCAL-CI-EVIDENCE-CONTEXT-001",
            "contract_version": "1.1.0",
            "source_revision": REVISION,
            "branch_name": "agent/ci-action-pinning-v2",
            "expected_revision": REVISION,
            "expected_pr_number": 123,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "LOCAL_SUPPLEMENTAL_FAIL_CLOSED",
            "hosted_ci_replacement": False,
            "operator_review_required": True,
            "provider_action_performed": False,
            "terraform_apply_performed": False,
            "external_action_performed": False,
        },
    )
    write_json(
        root / "repository-state.json",
        {
            "contract_id": "AIGC-LOCAL-CI-REPOSITORY-STATE-001",
            "source_revision": REVISION,
            "branch_name": "agent/ci-action-pinning-v2",
            "head_object_type": "commit",
            "expected_revision": REVISION,
            "expected_pr_number": 123,
            "expected_pr_assertion_source": "operator_environment",
            "worktree_clean": True,
            "index_clean": True,
            "tracked_diff_clean": True,
            "untracked_clean": True,
            "clean_status_sha256": sha256(b"").hexdigest(),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    artifacts = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in {"evidence-manifest.json", "run-status.json"}:
            continue
        artifacts.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        )
    write_json(
        root / "evidence-manifest.json",
        {
            "contract_id": "AIGC-LOCAL-CI-EVIDENCE-MANIFEST-001",
            "contract_version": "1.1.0",
            "source_revision": REVISION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "hosted_ci_replacement": False,
            "operator_review_required": True,
            "provider_action_performed": False,
            "terraform_apply_performed": False,
            "external_action_performed": False,
        },
    )
    return root


def test_valid_manifest_recomputes_all_artifact_hashes(tmp_path: Path) -> None:
    root = build_bundle(tmp_path)

    result = validate_manifest(root, expected_revision=REVISION)

    assert result["manifest_valid"] is True
    assert result["required_artifacts_present"] is True
    assert result["source_revision"] == REVISION
    assert result["hosted_ci_replacement"] is False
    assert result["external_action_performed"] is False


def test_manifest_rejects_tampered_artifact(tmp_path: Path) -> None:
    root = build_bundle(tmp_path)
    (root / "test_results" / "pytest.log").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(EvidenceManifestError, match="Digest mismatch"):
        validate_manifest(root, expected_revision=REVISION)


def test_manifest_rejects_unexpected_file(tmp_path: Path) -> None:
    root = build_bundle(tmp_path)
    (root / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")

    with pytest.raises(EvidenceManifestError, match="Manifest file-set mismatch"):
        validate_manifest(root, expected_revision=REVISION)


def test_manifest_rejects_wrong_expected_revision(tmp_path: Path) -> None:
    root = build_bundle(tmp_path)

    with pytest.raises(EvidenceManifestError, match="expected revision"):
        validate_manifest(root, expected_revision="b" * 40)
