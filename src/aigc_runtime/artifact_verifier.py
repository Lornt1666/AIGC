"""Independent GitHub Actions artifact ZIP and embedded-manifest verification.

Downloads are bounded, redirects are allowlisted, and authorization headers are never
forwarded to artifact storage. No archive member is extracted to disk. A signed
receipt binds the expected digest/run/attempt; this verifier recomputes bytes itself.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import stat
import urllib.parse
import zipfile
from typing import Any, Mapping

import httpx

from .github_evidence import GitHubEvidenceError, _safe_repo


class ArtifactVerificationError(ValueError):
    pass


_ALLOWED_REDIRECT_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
_ALLOWED_REDIRECT_SUFFIXES = (".blob.core.windows.net", ".amazonaws.com")


def _digest(value: str) -> str:
    value = value.removeprefix("sha256:")
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ArtifactVerificationError("expected_sha256_invalid")
    return value


def verify_artifact_zip(data: bytes, *, expected_sha256: str, manifest_path: str,
                        repository: str, candidate_sha: str, run_id: int, run_attempt: int,
                        api_digest: str | None = None, max_archive_bytes: int = 100_000_000,
                        max_uncompressed_bytes: int = 250_000_000, max_files: int = 10_000,
                        max_compression_ratio: float = 100.0) -> dict[str, Any]:
    if not isinstance(data, bytes) or not data or len(data) > max_archive_bytes:
        raise ArtifactVerificationError("artifact_archive_size_invalid")
    expected = _digest(expected_sha256)
    observed = hashlib.sha256(data).hexdigest()
    if observed != expected:
        raise ArtifactVerificationError("artifact_zip_sha256_mismatch")
    if api_digest and _digest(api_digest) != observed:
        raise ArtifactVerificationError("github_api_artifact_digest_mismatch")
    if not isinstance(candidate_sha, str) or len(candidate_sha) != 40 or any(ch not in "0123456789abcdef" for ch in candidate_sha):
        raise ArtifactVerificationError("candidate_sha_invalid")
    if not isinstance(run_id, int) or run_id < 1 or not isinstance(run_attempt, int) or run_attempt < 1:
        raise ArtifactVerificationError("workflow_run_or_attempt_invalid")
    manifest_path = manifest_path.replace("\\", "/")
    manifest_rel = PurePosixPath(manifest_path)
    if manifest_rel.is_absolute() or not manifest_path or any(part in {"", ".", ".."} for part in manifest_rel.parts):
        raise ArtifactVerificationError("manifest_path_invalid")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()
    except (zipfile.BadZipFile, OSError) as exc:
        raise ArtifactVerificationError("artifact_zip_malformed") from exc
    if len(infos) < 2 or len(infos) > max_files:
        raise ArtifactVerificationError("artifact_file_count_invalid")
    names: set[str] = set()
    total_size = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or name in names:
            raise ArtifactVerificationError("unsafe_or_duplicate_archive_path")
        names.add(name)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ArtifactVerificationError("archive_symlink_rejected")
        if info.is_dir():
            continue
        total_size += info.file_size
        if total_size > max_uncompressed_bytes:
            raise ArtifactVerificationError("artifact_uncompressed_size_limit_exceeded")
        if info.file_size > 0 and info.compress_size == 0:
            raise ArtifactVerificationError("artifact_compression_ratio_invalid")
        if info.compress_size > 0 and info.file_size / info.compress_size > max_compression_ratio:
            raise ArtifactVerificationError("artifact_compression_ratio_limit_exceeded")
    if manifest_path not in names:
        raise ArtifactVerificationError("signed_manifest_missing_from_archive")
    try:
        manifest = json.loads(archive.read(manifest_path).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, KeyError) as exc:
        raise ArtifactVerificationError("artifact_manifest_invalid_json") from exc
    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != "aigc.artifact-manifest.v1":
        raise ArtifactVerificationError("artifact_manifest_schema_invalid")
    expected_bindings = {"repository": repository, "candidate_sha": candidate_sha,
                         "run_id": run_id, "run_attempt": run_attempt}
    for key, value in expected_bindings.items():
        if manifest.get(key) != value:
            raise ArtifactVerificationError("artifact_manifest_binding_mismatch:" + key)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ArtifactVerificationError("artifact_manifest_files_missing")
    expected_files: dict[str, dict[str, Any]] = {}
    for item in files:
        if not isinstance(item, Mapping):
            raise ArtifactVerificationError("artifact_manifest_entry_invalid")
        path = item.get("path")
        if not isinstance(path, str) or path == manifest_path:
            raise ArtifactVerificationError("artifact_manifest_path_invalid")
        normalized = PurePosixPath(path.replace("\\", "/"))
        if normalized.is_absolute() or any(part in {"", ".", ".."} for part in normalized.parts):
            raise ArtifactVerificationError("artifact_manifest_path_unsafe")
        if path in expected_files:
            raise ArtifactVerificationError("artifact_manifest_duplicate_path")
        sha = _digest(item.get("sha256", ""))
        size = item.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ArtifactVerificationError("artifact_manifest_size_invalid")
        expected_files[path] = {"path": path, "sha256": sha, "size": size}
    archive_files = {info.filename for info in infos if not info.is_dir() and info.filename != manifest_path}
    if archive_files != set(expected_files):
        raise ArtifactVerificationError("archive_manifest_file_set_mismatch")
    verified_files = []
    for path in sorted(expected_files):
        content = archive.read(path)
        expected_file = expected_files[path]
        if len(content) != expected_file["size"]:
            raise ArtifactVerificationError("artifact_file_size_mismatch:" + path)
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected_file["sha256"]:
            raise ArtifactVerificationError("artifact_file_sha256_mismatch:" + path)
        verified_files.append({"path": path, "sha256": "sha256:" + actual, "size": len(content)})
    return {
        "status": "VERIFIED",
        "head_sha": candidate_sha,
        "sha256": "sha256:" + observed,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "manifest_path": manifest_path,
        "manifest_sha256": "sha256:" + hashlib.sha256(archive.read(manifest_path)).hexdigest(),
        "files": verified_files,
        "bytes_verified": True,
        "manifest_verified": True,
        "verification_method": "recomputed_sha256_and_embedded_manifest",
    }


def download_and_verify_artifact(repository: str, artifact_id: int, *, expected_sha256: str,
                                 manifest_path: str, candidate_sha: str, run_id: int,
                                 run_attempt: int, token_env: str = "GITHUB_TOKEN",
                                 api_digest: str | None = None, timeout_seconds: float = 30.0,
                                 max_archive_bytes: int = 100_000_000) -> dict[str, Any]:
    token = os.environ.get(token_env, "")
    if not token:
        raise ArtifactVerificationError("github_token_required")
    repo = _safe_repo(repository)
    url = "https://api.github.com/repos/" + repo + "/actions/artifacts/" + str(artifact_id) + "/zip"
    headers = {"Accept": "application/vnd.github+json", "Authorization": "Bearer " + token,
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "AIGC-RX148-ArtifactVerifier/1.0"}
    timeout = httpx.Timeout(timeout_seconds, connect=5.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(url, headers=headers)
            if response.status_code not in {301, 302, 303, 307, 308}:
                raise ArtifactVerificationError("artifact_download_expected_redirect:" + str(response.status_code))
            location = response.headers.get("location", "")
            parsed = urllib.parse.urlparse(location)
            host = (parsed.hostname or "").lower()
            allowed = host in _ALLOWED_REDIRECT_HOSTS or any(host.endswith(suffix) for suffix in _ALLOWED_REDIRECT_SUFFIXES)
            if parsed.scheme != "https" or not allowed:
                raise ArtifactVerificationError("artifact_redirect_host_not_allowlisted")
            # Never forward the GitHub bearer token to the signed object-storage URL.
            with client.stream("GET", location, headers={"Accept": "application/zip"}) as download:
                if download.status_code != 200:
                    raise ArtifactVerificationError("artifact_storage_download_failed:" + str(download.status_code))
                chunks = []
                size = 0
                for chunk in download.iter_bytes():
                    size += len(chunk)
                    if size > max_archive_bytes:
                        raise ArtifactVerificationError("artifact_archive_size_limit_exceeded")
                    chunks.append(chunk)
                data = b"".join(chunks)
    except httpx.HTTPError as exc:
        raise ArtifactVerificationError("artifact_download_transport_error:" + type(exc).__name__) from exc
    result = verify_artifact_zip(data, expected_sha256=expected_sha256, manifest_path=manifest_path,
        repository=repository, candidate_sha=candidate_sha, run_id=run_id, run_attempt=run_attempt,
        api_digest=api_digest, max_archive_bytes=max_archive_bytes)
    result["artifact_id"] = artifact_id
    return result
