"""Create deterministic per-file evidence manifest for the current GitHub Actions run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def create_manifest(root: Path, *, repository: str, candidate_sha: str, run_id: int,
                    run_attempt: int, max_files: int = 10_000,
                    max_total_bytes: int = 250_000_000) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("artifact_root_must_be_directory")
    parts = repository.split("/")
    if len(parts) != 2 or any(not p or not re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        raise ValueError("repository_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", candidate_sha):
        raise ValueError("candidate_sha_invalid")
    if run_id < 1 or run_attempt < 1:
        raise ValueError("run_id_or_attempt_invalid")
    manifest_path = root / "manifest.json"
    files = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path == manifest_path:
            continue
        if path.is_symlink():
            raise ValueError("symlink_in_artifact_root:" + path.relative_to(root).as_posix())
        if not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if root not in resolved.parents:
            raise ValueError("artifact_path_escapes_root")
        data = path.read_bytes()
        total += len(data)
        if total > max_total_bytes:
            raise ValueError("artifact_total_size_limit_exceeded")
        files.append({"path": path.relative_to(root).as_posix(),
                      "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
        if len(files) > max_files:
            raise ValueError("artifact_file_count_limit_exceeded")
    if not files:
        raise ValueError("artifact_evidence_files_missing")
    return {"schema_version": "aigc.artifact-manifest.v1", "repository": repository,
            "candidate_sha": candidate_sha, "run_id": run_id, "run_attempt": run_attempt,
            "files": files}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--run-attempt", required=True, type=int)
    args = parser.parse_args()
    manifest = create_manifest(args.root, repository=args.repository, candidate_sha=args.candidate_sha,
                               run_id=args.run_id, run_attempt=args.run_attempt)
    target = args.root / "manifest.json"
    target.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
