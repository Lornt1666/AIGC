from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
from typing import Any, Sequence


SCHEMA = "aigc.nexus-build-context-allowlist.v1"
MANIFEST_SCHEMA = "aigc.nexus-build-context-manifest.v1"
ALLOWED_MODES = frozenset({"100644", "100755"})


class BuildContextError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitEntry:
    mode: str
    object_type: str
    object_sha: str
    path: str


def _run(command: Sequence[str], *, binary: bool = False) -> bytes | str:
    completed = subprocess.run(
        list(command),
        capture_output=True,
        text=not binary,
        check=False,
    )
    if completed.returncode != 0:
        raise BuildContextError(f"command failed: {' '.join(command[:3])}")
    return completed.stdout


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _safe_path(path: str) -> str:
    value = PurePosixPath(path)
    if value.is_absolute() or not value.parts or any(part in {"", ".", ".."} for part in value.parts):
        raise BuildContextError("build-context path is unsafe")
    return value.as_posix()


def _load_allowlist(path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA:
        raise BuildContextError("unsupported build-context allowlist")
    if set(payload) != {"schema_version", "required_files", "required_prefixes"}:
        raise BuildContextError("build-context allowlist contains unsupported fields")
    files = tuple(_safe_path(item) for item in payload.get("required_files", ()))
    prefixes = tuple(_safe_path(item).rstrip("/") + "/" for item in payload.get("required_prefixes", ()))
    if not files or not prefixes or len(files) != len(set(files)) or len(prefixes) != len(set(prefixes)):
        raise BuildContextError("build-context allowlist must contain unique files and prefixes")
    return files, prefixes


def _tree_entries(revision: str) -> tuple[GitEntry, ...]:
    raw = _run(["git", "ls-tree", "-r", "-z", revision, "--"], binary=True)
    assert isinstance(raw, bytes)
    entries: list[GitEntry] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", 1)
        mode, object_type, object_sha = metadata.decode("ascii").split(" ", 2)
        path = _safe_path(encoded_path.decode("utf-8"))
        entries.append(GitEntry(mode, object_type, object_sha, path))
    return tuple(entries)


def prepare_build_context(
    *,
    expected_sha: str,
    expected_tree: str,
    allowlist_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    observed_sha = str(_run(["git", "rev-parse", expected_sha])).strip()
    observed_tree = str(_run(["git", "rev-parse", f"{expected_sha}^{{tree}}"])).strip()
    if observed_sha != expected_sha or observed_tree != expected_tree:
        raise BuildContextError("build context is not bound to the admitted Git SHA/tree")

    required_files, required_prefixes = _load_allowlist(allowlist_path)
    all_entries = _tree_entries(expected_sha)
    selected = tuple(
        entry
        for entry in all_entries
        if entry.path in required_files
        or any(entry.path.startswith(prefix) for prefix in required_prefixes)
    )
    selected_paths = {entry.path for entry in selected}
    missing_files = sorted(set(required_files) - selected_paths)
    missing_prefixes = sorted(
        prefix for prefix in required_prefixes if not any(path.startswith(prefix) for path in selected_paths)
    )
    if missing_files or missing_prefixes:
        raise BuildContextError(
            "admitted tree is missing required build-context paths: "
            + ", ".join(missing_files + missing_prefixes)
        )
    unsafe = [
        entry.path
        for entry in selected
        if entry.object_type != "blob" or entry.mode not in ALLOWED_MODES
    ]
    if unsafe:
        raise BuildContextError("build context contains links or unsupported Git modes")

    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise BuildContextError("build-context output directory must be empty")
    else:
        output_dir.mkdir(parents=True)

    archive = _run(
        ["git", "archive", "--format=tar", expected_sha, "--", *sorted(selected_paths)],
        binary=True,
    )
    assert isinstance(archive, bytes)
    archive_path = output_dir.parent / f".{output_dir.name}.tar"
    archive_path.write_bytes(archive)
    try:
        with tarfile.open(archive_path, mode="r:") as handle:
            members = [member for member in handle.getmembers() if member.isfile()]
            member_paths = {_safe_path(member.name) for member in members}
            if member_paths != selected_paths or any(
                member.issym() or member.islnk() for member in handle.getmembers()
            ):
                raise BuildContextError("Git archive did not preserve the exact regular-file allowlist")
            for member in members:
                source = handle.extractfile(member)
                if source is None:
                    raise BuildContextError("Git archive member could not be read")
                target = output_dir / _safe_path(member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    finally:
        archive_path.unlink(missing_ok=True)

    records = [
        {
            "path": entry.path,
            "git_blob_sha": entry.object_sha,
            "mode": entry.mode,
            "sha256": hashlib.sha256((output_dir / entry.path).read_bytes()).hexdigest(),
        }
        for entry in sorted(selected, key=lambda item: item.path)
    ]
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "repository": "Lornt1666/AIGC",
        "release_sha": expected_sha,
        "release_tree_sha": expected_tree,
        "file_count": len(records),
        "files": records,
        "ignored_worktree_files_included": False,
    }
    manifest["manifest_sha256"] = _canonical_sha256(manifest)
    (output_dir / "BUILD_CONTEXT_MANIFEST.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_build_context(
        expected_sha=args.expected_sha,
        expected_tree=args.expected_tree,
        allowlist_path=args.allowlist,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildContextError as exc:
        raise SystemExit(f"Nexus build context blocked: {exc}") from exc
