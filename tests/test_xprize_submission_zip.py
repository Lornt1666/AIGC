from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_xprize_submission_zip import (
    SubmissionZipError,
    build_submission_zip,
    validate_manifest,
)


RELEASE = "a" * 40


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    evidence = root / "evidence.md"
    evidence.write_text("Evidence-bound AIGC submission artifact.\n", encoding="utf-8")
    return root, evidence


def manifest_for(evidence: Path, **overrides):
    value = {
        "schema_version": "aigc.xprize-submission-zip-manifest.v1",
        "template_only": False,
        "repository": "Lornt1666/AIGC",
        "project_id": 1289277,
        "release_sha": RELEASE,
        "output_name": "aigc-xprize-evidence.zip",
        "entries": [
            {
                "path": "evidence.md",
                "archive_path": "01/evidence.md",
                "kind": "text",
                "required": True,
                "evidence_state": "EVIDENCED",
                "redaction_reviewed": True,
                "expected_sha256": digest(evidence),
            }
        ],
        "authority": {
            "internal_zip_build_authorized": True,
            "devpost_upload_authorized": False,
            "devpost_submission_authorized": False,
        },
    }
    value.update(overrides)
    return value


def write_manifest(root: Path, value: dict) -> Path:
    path = root / "manifest.json"
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def test_template_manifest_cannot_build(tmp_path: Path):
    root, evidence = project(tmp_path)
    value = manifest_for(evidence, template_only=True)
    with pytest.raises(SubmissionZipError, match="template manifest"):
        validate_manifest(value, project_root=root)


def test_nonfinal_evidence_state_fails_closed(tmp_path: Path):
    root, evidence = project(tmp_path)
    value = manifest_for(evidence)
    value["entries"][0]["evidence_state"] = "PARTIAL"
    with pytest.raises(SubmissionZipError, match="not final evidence"):
        validate_manifest(value, project_root=root)


def test_digest_mismatch_fails_closed(tmp_path: Path):
    root, evidence = project(tmp_path)
    value = manifest_for(evidence)
    value["entries"][0]["expected_sha256"] = "b" * 64
    with pytest.raises(SubmissionZipError, match="digest mismatch"):
        validate_manifest(value, project_root=root)


def test_path_traversal_fails_closed(tmp_path: Path):
    root, evidence = project(tmp_path)
    value = manifest_for(evidence)
    value["entries"][0]["path"] = "../evidence.md"
    with pytest.raises(SubmissionZipError, match="unsafe source path"):
        validate_manifest(value, project_root=root)


def test_archive_traversal_fails_closed(tmp_path: Path):
    root, evidence = project(tmp_path)
    value = manifest_for(evidence)
    value["entries"][0]["archive_path"] = "../evidence.md"
    with pytest.raises(SubmissionZipError, match="unsafe archive path"):
        validate_manifest(value, project_root=root)


def test_binary_requires_redaction_review(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    binary = root / "evidence.pdf"
    binary.write_bytes(b"synthetic-pdf-fixture")
    value = manifest_for(binary)
    value["entries"][0] = {
        "path": "evidence.pdf",
        "archive_path": "01/evidence.pdf",
        "kind": "binary",
        "required": True,
        "evidence_state": "EVIDENCED",
        "redaction_reviewed": False,
        "expected_sha256": digest(binary),
    }
    with pytest.raises(SubmissionZipError, match="redaction review"):
        validate_manifest(value, project_root=root)


def test_canonical_secret_scanner_blocks_text_payload(tmp_path: Path):
    root, evidence = project(tmp_path)
    prohibited_value = "s" + "k-" + ("A" * 32)
    evidence.write_text("api_key = " + prohibited_value + "\n", encoding="utf-8")
    value = manifest_for(evidence)
    value["entries"][0]["expected_sha256"] = digest(evidence)
    with pytest.raises(SubmissionZipError, match="secret-like content"):
        validate_manifest(value, project_root=root)


def test_build_authority_does_not_grant_devpost_upload(tmp_path: Path):
    root, evidence = project(tmp_path)
    value = manifest_for(evidence)
    value["authority"]["devpost_upload_authorized"] = True
    with pytest.raises(SubmissionZipError, match="cannot grant Devpost upload"):
        validate_manifest(value, project_root=root)


def test_deterministic_zip_and_receipt_bind_file_hashes(tmp_path: Path):
    root, evidence = project(tmp_path)
    value = manifest_for(evidence)
    manifest = write_manifest(root, value)

    first = build_submission_zip(manifest, project_root=root, output_dir=tmp_path / "out1")
    second = build_submission_zip(manifest, project_root=root, output_dir=tmp_path / "out2")

    assert first["zip_sha256"] == second["zip_sha256"]
    assert first["entry_count"] == 1
    assert first["entries"][0]["sha256"] == digest(evidence)
    assert first["canonical_text_secret_scan_passed"] is True
    assert first["devpost_upload_performed"] is False
    assert first["devpost_submission_performed"] is False


def test_placeholder_release_sha_is_rejected(tmp_path: Path):
    root, evidence = project(tmp_path)
    value = manifest_for(evidence, release_sha="0" * 40)
    with pytest.raises(SubmissionZipError, match="placeholder"):
        validate_manifest(value, project_root=root)
