from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.security.redaction_scanner import RedactionScanner


SCHEMA_VERSION = "aigc.xprize-submission-zip-manifest.v1"
RECEIPT_SCHEMA_VERSION = "aigc.xprize-submission-zip-receipt.v1"
FINAL_EVIDENCE_STATES = {"EVIDENCED", "NOT_APPLICABLE"}
ALLOWED_KINDS = {"text", "binary"}
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".csv", ".toml", ".yaml", ".yml"}
BINARY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
INTERNAL_MANIFEST_PATH = "AIGC_SUBMISSION_PACKAGE_MANIFEST.json"


class SubmissionZipError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_source_path(project_root: Path, relative: str) -> Path:
    raw = Path(relative)
    if raw.is_absolute():
        raise SubmissionZipError(f"absolute source path is prohibited: {relative}")
    if any(part in {"", ".", ".."} for part in raw.parts):
        raise SubmissionZipError(f"unsafe source path: {relative}")
    candidate = project_root.joinpath(raw)
    if candidate.is_symlink():
        raise SubmissionZipError(f"symlink source is prohibited: {relative}")
    resolved_root = project_root.resolve()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise SubmissionZipError(f"source path escapes project root: {relative}") from exc
    return candidate


def _safe_archive_path(value: str) -> str:
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts:
        raise SubmissionZipError(f"unsafe archive path: {value}")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise SubmissionZipError(f"unsafe archive path: {value}")
    normalized = pure.as_posix()
    if normalized == INTERNAL_MANIFEST_PATH:
        raise SubmissionZipError("archive path collides with internal package manifest")
    return normalized


def _validate_release_sha(value: Any) -> str:
    text = str(value or "")
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise SubmissionZipError("release_sha must be an exact lowercase 40-character Git SHA")
    if text == "0" * 40:
        raise SubmissionZipError("release_sha cannot remain a placeholder")
    return text


def _validate_output_name(value: Any) -> str:
    name = str(value or "")
    if not name or Path(name).name != name or not name.lower().endswith(".zip"):
        raise SubmissionZipError("output_name must be a simple .zip filename")
    return name


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionZipError("submission ZIP manifest could not be loaded") from exc
    if not isinstance(payload, dict):
        raise SubmissionZipError("submission ZIP manifest must be an object")
    return payload


def _entry_state(entry: dict[str, Any]) -> str:
    state = str(entry.get("evidence_state", ""))
    if state not in FINAL_EVIDENCE_STATES:
        raise SubmissionZipError(
            f"entry {entry.get('path')} is not final evidence: {state or '<missing>'}"
        )
    return state


def _scan_text_files(paths: Iterable[Path]) -> None:
    scanner = RedactionScanner()
    findings = scanner.scan_paths(paths, suffixes=TEXT_SUFFIXES)
    if findings:
        first = findings[0]
        raise SubmissionZipError(
            f"secret-like content detected in {first.path}:{first.line_number}"
        )


def validate_manifest(
    payload: dict[str, Any],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SubmissionZipError("unsupported submission ZIP manifest schema_version")
    if payload.get("template_only") is not False:
        raise SubmissionZipError("template manifest cannot build a submission ZIP")
    if payload.get("repository") != "Lornt1666/AIGC":
        raise SubmissionZipError("manifest targets another repository")
    project_id = payload.get("project_id")
    if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id <= 0:
        raise SubmissionZipError("project_id must be a positive integer")
    _validate_release_sha(payload.get("release_sha"))
    _validate_output_name(payload.get("output_name"))

    authority = payload.get("authority")
    if not isinstance(authority, dict):
        raise SubmissionZipError("manifest authority must be an object")
    if authority.get("internal_zip_build_authorized") is not True:
        raise SubmissionZipError("internal submission ZIP build is not authorized")
    # Building a local package is deliberately separate from uploading/submitting it.
    if authority.get("devpost_upload_authorized") not in {False, None}:
        raise SubmissionZipError("ZIP build manifest cannot grant Devpost upload authority")
    if authority.get("devpost_submission_authorized") not in {False, None}:
        raise SubmissionZipError("ZIP build manifest cannot grant Devpost submission authority")

    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise SubmissionZipError("manifest entries must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen_archive_paths: set[str] = set()
    text_paths: list[Path] = []
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            raise SubmissionZipError("manifest entry must be an object")
        if raw_entry.get("required") is not True:
            raise SubmissionZipError("all packaged entries must be explicitly required")
        _entry_state(raw_entry)
        kind = str(raw_entry.get("kind", ""))
        if kind not in ALLOWED_KINDS:
            raise SubmissionZipError(f"unsupported entry kind: {kind}")
        relative = str(raw_entry.get("path", ""))
        archive_path = _safe_archive_path(str(raw_entry.get("archive_path", "")))
        if archive_path in seen_archive_paths:
            raise SubmissionZipError(f"duplicate archive path: {archive_path}")
        seen_archive_paths.add(archive_path)
        source = _safe_source_path(project_root, relative)
        if not source.is_file():
            raise SubmissionZipError(f"required submission evidence file is missing: {relative}")
        suffix = source.suffix.lower()
        if kind == "text":
            if suffix not in TEXT_SUFFIXES:
                raise SubmissionZipError(f"text entry has unsupported suffix: {relative}")
            text_paths.append(source)
        else:
            if suffix not in BINARY_SUFFIXES:
                raise SubmissionZipError(f"binary entry has unsupported suffix: {relative}")
            if raw_entry.get("redaction_reviewed") is not True:
                raise SubmissionZipError(
                    f"binary evidence requires explicit redaction review: {relative}"
                )

        digest = sha256_file(source)
        expected = raw_entry.get("expected_sha256")
        if not isinstance(expected, str) or len(expected) != 64:
            raise SubmissionZipError(f"exact expected_sha256 is required: {relative}")
        if expected != digest:
            raise SubmissionZipError(f"evidence digest mismatch: {relative}")
        if raw_entry.get("redaction_reviewed") is not True:
            raise SubmissionZipError(f"redaction_reviewed must be true: {relative}")

        normalized.append(
            {
                "source": source,
                "source_path": relative,
                "archive_path": archive_path,
                "kind": kind,
                "sha256": digest,
                "size_bytes": source.stat().st_size,
            }
        )

    _scan_text_files(text_paths)
    return sorted(normalized, key=lambda item: item["archive_path"])


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(filename=name, date_time=FIXED_ZIP_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def build_submission_zip(
    manifest_path: Path,
    *,
    project_root: Path,
    output_dir: Path,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    payload = _load_manifest(manifest_path)
    entries = validate_manifest(payload, project_root=project_root)
    release_sha = _validate_release_sha(payload.get("release_sha"))
    output_name = _validate_output_name(payload.get("output_name"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    internal_manifest = {
        "schema_version": "aigc.xprize-submission-package-manifest.v1",
        "repository": payload["repository"],
        "project_id": payload["project_id"],
        "release_sha": release_sha,
        "files": [
            {
                "archive_path": item["archive_path"],
                "source_path": item["source_path"],
                "sha256": item["sha256"],
                "size_bytes": item["size_bytes"],
            }
            for item in entries
        ],
        "external_action_performed": False,
        "devpost_upload_performed": False,
        "devpost_submission_performed": False,
    }
    internal_bytes = canonical_json_bytes(internal_manifest) + b"\n"
    internal_manifest_sha256 = sha256_bytes(internal_bytes)

    with ZipFile(output_path, "w") as archive:
        archive.writestr(_zip_info(INTERNAL_MANIFEST_PATH), internal_bytes)
        for item in entries:
            archive.writestr(_zip_info(item["archive_path"]), item["source"].read_bytes())

    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "repository": payload["repository"],
        "project_id": payload["project_id"],
        "release_sha": release_sha,
        "zip_file": output_path.name,
        "zip_sha256": sha256_file(output_path),
        "package_manifest_sha256": internal_manifest_sha256,
        "entry_count": len(entries),
        "entries": [
            {
                "archive_path": item["archive_path"],
                "sha256": item["sha256"],
                "size_bytes": item["size_bytes"],
            }
            for item in entries
        ],
        "canonical_text_secret_scan_passed": True,
        "binary_redaction_reviews_required": True,
        "deterministic_zip_timestamp": "1980-01-01T00:00:00Z",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "external_action_performed": False,
        "devpost_upload_performed": False,
        "devpost_submission_performed": False,
    }
    if receipt_path is None:
        receipt_path = output_path.with_suffix(output_path.suffix + ".receipt.json")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, redaction-reviewed XPRIZE evidence ZIP without uploading it."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = build_submission_zip(
            args.manifest,
            project_root=args.project_root,
            output_dir=args.output_dir,
            receipt_path=args.receipt,
        )
    except SubmissionZipError as exc:
        raise SystemExit(f"XPRIZE submission ZIP blocked: {exc}") from exc
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
