from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts.prepare_nexus_build_context import BuildContextError, prepare_build_context


def _run(repo: Path, *command: str) -> str:
    return subprocess.run(
        command, cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, str, str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "git", "init", "-b", "main")
    _run(repo, "git", "config", "user.name", "AIGC Test")
    _run(repo, "git", "config", "user.email", "aigc@example.invalid")
    files = {
        "Dockerfile.nexus": "FROM scratch\n",
        "cloudbuild.nexus.yaml": "steps: []\n",
        "requirements.txt": "\n",
        "migrations/003_nexus_provider_runtime_controls.sql": "SELECT 1;\n",
        "migrations/004_nexus_persisted_authority.sql": "SELECT 1;\n",
        "src/app.py": "print('safe')\n",
        ".env.local": "DO_NOT_COPY=fixture\n",
        "ignored/private.txt": "DO_NOT_COPY=fixture\n",
    }
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (repo / ".gitignore").write_text(".env*\nignored/\n", encoding="utf-8")
    _run(repo, "git", "add", "Dockerfile.nexus", "cloudbuild.nexus.yaml", "requirements.txt", "migrations", "src", ".gitignore")
    _run(repo, "git", "commit", "-m", "fixture")
    sha = _run(repo, "git", "rev-parse", "HEAD")
    tree = _run(repo, "git", "rev-parse", "HEAD^{tree}")
    allowlist = repo / "allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "schema_version": "aigc.nexus-build-context-allowlist.v1",
                "required_files": [
                    "Dockerfile.nexus",
                    "cloudbuild.nexus.yaml",
                    "requirements.txt",
                    "migrations/003_nexus_provider_runtime_controls.sql",
                    "migrations/004_nexus_persisted_authority.sql",
                ],
                "required_prefixes": ["src/"],
            }
        ),
        encoding="utf-8",
    )
    return repo, sha, tree, allowlist


def test_context_contains_only_admitted_tracked_allowlist(tmp_path: Path, monkeypatch):
    repo, sha, tree, allowlist = _repository(tmp_path)
    monkeypatch.chdir(repo)
    output = tmp_path / "context"
    manifest = prepare_build_context(
        expected_sha=sha,
        expected_tree=tree,
        allowlist_path=allowlist,
        output_dir=output,
    )
    assert (output / "src/app.py").is_file()
    assert not (output / ".env.local").exists()
    assert not (output / "ignored/private.txt").exists()
    assert manifest["ignored_worktree_files_included"] is False
    assert manifest["file_count"] == 6
    assert len(manifest["manifest_sha256"]) == 64


def test_context_rejects_wrong_tree_and_missing_required_file(tmp_path: Path, monkeypatch):
    repo, sha, tree, allowlist = _repository(tmp_path)
    monkeypatch.chdir(repo)
    with pytest.raises(BuildContextError, match="SHA/tree"):
        prepare_build_context(
            expected_sha=sha,
            expected_tree="0" * 40,
            allowlist_path=allowlist,
            output_dir=tmp_path / "wrong-tree",
        )
    payload = json.loads(allowlist.read_text(encoding="utf-8"))
    payload["required_files"].append("missing.txt")
    allowlist.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BuildContextError, match="missing required"):
        prepare_build_context(
            expected_sha=sha,
            expected_tree=tree,
            allowlist_path=allowlist,
            output_dir=tmp_path / "missing",
        )
