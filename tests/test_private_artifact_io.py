from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory

import pytest

from src.core import private_artifact_io as private_io
from src.core.private_artifact_io import (
    PrivateArtifactIOError,
    read_private_json,
    write_private_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


def _private_parent(tmp_path: Path, name: str = "private") -> Path:
    parent = tmp_path / name
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    return parent


def _private_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _assert_no_staging(parent: Path, final_name: str) -> None:
    assert not list(parent.glob(f".{final_name}.staging-*"))


def test_read_private_json_accepts_external_owned_0600_regular_file(
    tmp_path: Path,
) -> None:
    private_parent = _private_parent(tmp_path)
    config_path = private_parent / "financial.json"
    expected = {"tenant_id": "TENANT-SYNTHETIC", "enabled": False}
    _private_json(config_path, expected)

    assert read_private_json(config_path, ROOT) == expected


def test_read_private_json_requires_an_absolute_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _private_json(tmp_path / "financial.json", {"synthetic": True})

    with pytest.raises(PrivateArtifactIOError, match="absolute"):
        read_private_json(Path("financial.json"), ROOT)


def test_read_private_json_rejects_group_or_other_permissions(
    tmp_path: Path,
) -> None:
    config_path = _private_parent(tmp_path) / "financial.json"
    _private_json(config_path, {"synthetic": True})
    config_path.chmod(0o644)

    with pytest.raises(PrivateArtifactIOError, match="permissions"):
        read_private_json(config_path, ROOT)


def test_read_private_json_rejects_non_regular_file(tmp_path: Path) -> None:
    directory = _private_parent(tmp_path) / "not-a-file"
    directory.mkdir(mode=0o700)

    with pytest.raises(PrivateArtifactIOError, match="regular file"):
        read_private_json(directory, ROOT)


def test_read_private_json_rejects_file_not_owned_by_current_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _private_parent(tmp_path) / "financial.json"
    _private_json(config_path, {"synthetic": True})
    owner = config_path.stat().st_uid
    monkeypatch.setattr(private_io.os, "geteuid", lambda: owner + 1)

    with pytest.raises(PrivateArtifactIOError, match="current user"):
        read_private_json(config_path, ROOT)


def test_read_private_json_rejects_symlink(tmp_path: Path) -> None:
    private_parent = _private_parent(tmp_path)
    target = private_parent / "target.json"
    _private_json(target, {"synthetic": True})
    link = private_parent / "linked.json"
    link.symlink_to(target)

    with pytest.raises(PrivateArtifactIOError, match="unavailable"):
        read_private_json(link, ROOT)


def test_read_private_json_rejects_private_file_inside_repository() -> None:
    with TemporaryDirectory(
        dir=ROOT,
        prefix=".private-artifact-io-test-",
    ) as temporary_directory:
        config_path = Path(temporary_directory) / "financial.json"
        _private_json(config_path, {"synthetic": True})

        with pytest.raises(PrivateArtifactIOError, match="outside"):
            read_private_json(config_path, ROOT)


def test_descriptor_bound_read_resists_ancestor_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external_parent = _private_parent(tmp_path, "external")
    moved_parent = tmp_path / "external-original"
    config_path = external_parent / "financial.json"
    _private_json(config_path, {"source": "external"})
    real_resolver = private_io._resolved_descriptor_path
    swapped = False

    with TemporaryDirectory(
        dir=ROOT,
        prefix=".private-artifact-io-test-",
    ) as repository_directory:
        repository_config = Path(repository_directory) / "financial.json"
        _private_json(repository_config, {"source": "repository"})

        def swap_after_open(descriptor: int) -> Path:
            nonlocal swapped
            if not swapped:
                external_parent.rename(moved_parent)
                external_parent.symlink_to(
                    Path(repository_directory),
                    target_is_directory=True,
                )
                swapped = True
            return real_resolver(descriptor)

        monkeypatch.setattr(
            private_io,
            "_resolved_descriptor_path",
            swap_after_open,
        )

        assert read_private_json(config_path, ROOT) == {"source": "external"}


def test_write_private_bundle_publishes_complete_private_bundle(
    tmp_path: Path,
) -> None:
    parent = _private_parent(tmp_path)
    artifact_root = parent / "financial-run"
    contents = {
        "packet.json": '{"schema_version":"1.0.0"}\n',
        "report.md": "# Synthetic report\n",
        "receipt.json": '{"outcome":"SUCCEEDED"}\n',
    }

    result = write_private_bundle(artifact_root, ROOT, contents)

    assert result == {
        name: artifact_root / name
        for name in contents
    }
    assert artifact_root.is_dir()
    assert _mode(artifact_root) == 0o700
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in artifact_root.iterdir()
    } == contents
    assert all(_mode(path) == 0o600 for path in result.values())
    _assert_no_staging(parent, artifact_root.name)


def test_descriptor_bound_write_resists_ancestor_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external_parent = _private_parent(tmp_path, "external")
    moved_parent = tmp_path / "external-original"
    artifact_root = external_parent / "financial-run"
    real_resolver = private_io._resolved_descriptor_path
    swapped = False

    with TemporaryDirectory(
        dir=ROOT,
        prefix=".private-artifact-io-test-",
    ) as repository_directory:
        repository_parent = Path(repository_directory)
        repository_parent.chmod(0o700)

        def swap_after_open(descriptor: int) -> Path:
            nonlocal swapped
            if not swapped:
                external_parent.rename(moved_parent)
                external_parent.symlink_to(
                    repository_parent,
                    target_is_directory=True,
                )
                swapped = True
            return real_resolver(descriptor)

        monkeypatch.setattr(
            private_io,
            "_resolved_descriptor_path",
            swap_after_open,
        )
        paths = write_private_bundle(
            artifact_root,
            ROOT,
            {"packet.json": "{}\n"},
        )

        assert paths["packet.json"] == (
            moved_parent / "financial-run" / "packet.json"
        )
        assert paths["packet.json"].read_text(encoding="utf-8") == "{}\n"
        assert not (repository_parent / "financial-run").exists()


@pytest.mark.parametrize("existing_kind", ["directory", "file"])
def test_write_private_bundle_rejects_preexisting_final_path(
    tmp_path: Path,
    existing_kind: str,
) -> None:
    parent = _private_parent(tmp_path)
    artifact_root = parent / "financial-run"
    if existing_kind == "directory":
        artifact_root.mkdir(mode=0o700)
        artifact_root.chmod(0o700)
    else:
        artifact_root.write_text("preserve me", encoding="utf-8")
        artifact_root.chmod(0o600)

    with pytest.raises(PrivateArtifactIOError, match="create-only"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {"packet.json": "{}\n"},
        )

    if existing_kind == "file":
        assert artifact_root.read_text(encoding="utf-8") == "preserve me"
    else:
        assert list(artifact_root.iterdir()) == []
    _assert_no_staging(parent, artifact_root.name)


def test_staging_name_collision_preserves_preexisting_private_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _private_parent(tmp_path)
    artifact_root = parent / "financial-run"
    collision = parent / ".financial-run.staging-fixed"
    collision.mkdir(mode=0o700)
    collision.chmod(0o700)
    sentinel = collision / "sentinel.txt"
    sentinel.write_text("preserve me", encoding="utf-8")
    sentinel.chmod(0o600)
    monkeypatch.setattr(private_io.secrets, "token_hex", lambda _size: "fixed")

    with pytest.raises(PrivateArtifactIOError, match="create-only"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {"packet.json": "{}\n"},
        )

    assert sentinel.read_text(encoding="utf-8") == "preserve me"
    assert collision.is_dir()
    assert not artifact_root.exists()


def test_write_private_bundle_rejects_symlink_final_path(
    tmp_path: Path,
) -> None:
    parent = _private_parent(tmp_path)
    target = _private_parent(tmp_path, "target")
    artifact_root = parent / "financial-run"
    artifact_root.symlink_to(target, target_is_directory=True)

    with pytest.raises(PrivateArtifactIOError, match="create-only"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {"packet.json": "{}\n"},
        )

    assert artifact_root.is_symlink()
    assert list(target.iterdir()) == []
    _assert_no_staging(parent, artifact_root.name)


def test_write_private_bundle_rejects_repository_parent() -> None:
    with TemporaryDirectory(
        dir=ROOT,
        prefix=".private-artifact-io-test-",
    ) as temporary_directory:
        parent = Path(temporary_directory)
        parent.chmod(0o700)
        artifact_root = parent / "financial-run"

        with pytest.raises(PrivateArtifactIOError, match="outside"):
            write_private_bundle(
                artifact_root,
                ROOT,
                {"packet.json": "{}\n"},
            )

        assert not artifact_root.exists()
        _assert_no_staging(parent, artifact_root.name)


def test_write_private_bundle_rejects_non_private_parent(
    tmp_path: Path,
) -> None:
    parent = _private_parent(tmp_path)
    parent.chmod(0o755)
    artifact_root = parent / "financial-run"

    with pytest.raises(PrivateArtifactIOError, match="permissions"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {"packet.json": "{}\n"},
        )

    assert not artifact_root.exists()
    _assert_no_staging(parent, artifact_root.name)


def test_write_private_bundle_rejects_parent_not_owned_by_current_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _private_parent(tmp_path)
    owner = parent.stat().st_uid
    monkeypatch.setattr(private_io.os, "geteuid", lambda: owner + 1)
    artifact_root = parent / "financial-run"

    with pytest.raises(PrivateArtifactIOError, match="current user"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {"packet.json": "{}\n"},
        )

    assert not artifact_root.exists()
    _assert_no_staging(parent, artifact_root.name)


def test_write_private_bundle_rejects_missing_or_symlink_parent(
    tmp_path: Path,
) -> None:
    actual_parent = _private_parent(tmp_path)
    symlink_parent = tmp_path / "linked-parent"
    symlink_parent.symlink_to(actual_parent, target_is_directory=True)

    for parent in (tmp_path / "missing-parent", symlink_parent):
        artifact_root = parent / "financial-run"
        with pytest.raises(
            PrivateArtifactIOError,
            match="parent directory is unavailable",
        ):
            write_private_bundle(
                artifact_root,
                ROOT,
                {"packet.json": "{}\n"},
            )
        assert not artifact_root.exists()


def test_write_private_bundle_requires_absolute_artifact_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(PrivateArtifactIOError, match="absolute"):
        write_private_bundle(
            Path("financial-run"),
            ROOT,
            {"packet.json": "{}\n"},
        )


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "",
        ".hidden",
        "../escape.json",
        "nested/packet.json",
        "/absolute.json",
        "name with spaces.json",
        "x" * 129,
    ],
)
def test_write_private_bundle_rejects_unsafe_filenames(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    parent = _private_parent(tmp_path)
    artifact_root = parent / "financial-run"

    with pytest.raises(PrivateArtifactIOError, match="filename"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {unsafe_name: "{}\n"},
        )

    assert not artifact_root.exists()
    _assert_no_staging(parent, artifact_root.name)


def test_write_private_bundle_rejects_unsafe_final_name(
    tmp_path: Path,
) -> None:
    parent = _private_parent(tmp_path)
    artifact_root = parent / ".financial-run"

    with pytest.raises(PrivateArtifactIOError, match="root name"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {"packet.json": "{}\n"},
        )

    assert not artifact_root.exists()


def test_write_failure_leaves_neither_final_nor_staging_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _private_parent(tmp_path)
    artifact_root = parent / "financial-run"
    real_write = private_io._write_private_file
    calls = 0

    def partially_failing_write(
        directory_fd: int,
        filename: str,
        content: str,
    ) -> None:
        nonlocal calls
        calls += 1
        real_write(directory_fd, filename, content)
        if calls == 2:
            raise OSError(errno.EIO, "synthetic staged-write failure")

    monkeypatch.setattr(
        private_io,
        "_write_private_file",
        partially_failing_write,
    )

    with pytest.raises(PrivateArtifactIOError, match="failed closed"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {
                "packet.json": "{}\n",
                "receipt.json": "{}\n",
            },
        )

    assert not artifact_root.exists()
    _assert_no_staging(parent, artifact_root.name)


def test_parent_fsync_failure_reports_published_durability_indeterminate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _private_parent(tmp_path)
    artifact_root = parent / "financial-run"
    real_fsync = private_io.os.fsync
    directory_fsync_count = 0

    def fail_parent_fsync(descriptor: int) -> None:
        nonlocal directory_fsync_count
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            directory_fsync_count += 1
            if directory_fsync_count == 2:
                raise OSError(errno.EIO, "synthetic parent fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(private_io.os, "fsync", fail_parent_fsync)

    with pytest.raises(PrivateArtifactIOError, match="indeterminate"):
        write_private_bundle(
            artifact_root,
            ROOT,
            {"packet.json": "{}\n"},
        )

    assert (artifact_root / "packet.json").read_text(encoding="utf-8") == "{}\n"
    assert _mode(artifact_root) == 0o700
    assert _mode(artifact_root / "packet.json") == 0o600
    _assert_no_staging(parent, artifact_root.name)
