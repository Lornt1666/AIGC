from __future__ import annotations

import ctypes
import errno
import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import Any, Mapping


MAX_PRIVATE_JSON_BYTES = 5 * 1024 * 1024
SAFE_ARTIFACT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
RENAME_NOREPLACE = 1


class PrivateArtifactIOError(ValueError):
    """Raised when private configuration or artifact I/O cannot fail closed."""


def read_private_json(path: Path, repository_root: Path) -> Any:
    """Read one private JSON file through a verified file descriptor."""

    if not path.is_absolute():
        raise PrivateArtifactIOError("Private config path must be absolute.")
    repository = repository_root.resolve(strict=True)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PrivateArtifactIOError("Private config is unavailable.") from exc

    try:
        metadata = os.fstat(descriptor)
        _assert_private_regular_file(metadata)
        resolved = _resolved_descriptor_path(descriptor)
        _assert_outside_repository(resolved, repository)
        if metadata.st_size > MAX_PRIVATE_JSON_BYTES:
            raise PrivateArtifactIOError("Private config exceeds the size limit.")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            content = handle.read(MAX_PRIVATE_JSON_BYTES + 1)
        if len(content.encode("utf-8")) > MAX_PRIVATE_JSON_BYTES:
            raise PrivateArtifactIOError("Private config exceeds the size limit.")
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise PrivateArtifactIOError("Private config is not valid JSON.") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def write_private_bundle(
    artifact_root: Path,
    repository_root: Path,
    files: Mapping[str, str],
) -> dict[str, Path]:
    """Atomically publish a create-only private bundle outside the repository."""

    if not artifact_root.is_absolute():
        raise PrivateArtifactIOError("Artifact root must be absolute.")
    if not files:
        raise PrivateArtifactIOError("Private artifact bundle cannot be empty.")
    final_name = artifact_root.name
    if not SAFE_ARTIFACT_NAME.fullmatch(final_name):
        raise PrivateArtifactIOError("Artifact root name is unsafe.")
    for filename in files:
        if not SAFE_ARTIFACT_NAME.fullmatch(filename):
            raise PrivateArtifactIOError("Artifact filename is unsafe.")

    repository = repository_root.resolve(strict=True)
    parent_fd = _open_private_directory(artifact_root.parent)
    staging_fd = -1
    staging_name = f".{final_name}.staging-{secrets.token_hex(8)}"
    staging_created = False
    staging_identity: tuple[int, int] | None = None
    published = False
    try:
        parent_metadata = os.fstat(parent_fd)
        _assert_private_directory(parent_metadata)
        resolved_parent = _resolved_descriptor_path(parent_fd)
        _assert_outside_repository(resolved_parent, repository)

        os.mkdir(staging_name, mode=0o700, dir_fd=parent_fd)
        staging_created = True
        created_metadata = os.stat(
            staging_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        staging_identity = (created_metadata.st_dev, created_metadata.st_ino)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        opened_metadata = os.fstat(staging_fd)
        if (
            opened_metadata.st_dev,
            opened_metadata.st_ino,
        ) != staging_identity:
            raise PrivateArtifactIOError(
                "Private staging directory identity changed."
            )
        for filename, content in files.items():
            _write_private_file(staging_fd, filename, content)
        os.fsync(staging_fd)
        current_metadata = os.stat(
            staging_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            current_metadata.st_dev,
            current_metadata.st_ino,
        ) != staging_identity:
            raise PrivateArtifactIOError(
                "Private staging directory identity changed before publication."
            )
        _rename_noreplace(parent_fd, staging_name, final_name)
        published = True
        try:
            os.fsync(parent_fd)
        except OSError as exc:
            raise PrivateArtifactIOError(
                "Private artifact bundle was published, but directory "
                "durability is indeterminate."
            ) from exc
        return {
            filename: resolved_parent / final_name / filename
            for filename in files
        }
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise PrivateArtifactIOError(
                "Private artifact roots are create-only."
            ) from exc
        raise PrivateArtifactIOError(
            "Private artifact bundle publication failed closed."
        ) from exc
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        if (
            not published
            and staging_created
            and staging_identity is not None
        ):
            _remove_staging_bundle(
                parent_fd,
                staging_name,
                staging_identity,
            )
        os.close(parent_fd)


def _open_private_directory(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        return os.open(path, flags)
    except OSError as exc:
        raise PrivateArtifactIOError(
            "Artifact parent directory is unavailable."
        ) from exc


def _write_private_file(directory_fd: int, filename: str, content: str) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(filename, flags, 0o600, dir_fd=directory_fd)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _rename_noreplace(
    directory_fd: int,
    source_name: str,
    destination_name: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise PrivateArtifactIOError(
            "Atomic create-only directory publication is unavailable."
        )
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        directory_fd,
        source_name.encode("utf-8"),
        directory_fd,
        destination_name.encode("utf-8"),
        RENAME_NOREPLACE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _remove_staging_bundle(
    parent_fd: int,
    staging_name: str,
    expected_identity: tuple[int, int],
) -> None:
    try:
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except OSError:
        return
    try:
        metadata = os.fstat(staging_fd)
        if (metadata.st_dev, metadata.st_ino) != expected_identity:
            return
        try:
            filenames = os.listdir(staging_fd)
        except OSError:
            filenames = []
        for filename in filenames:
            try:
                os.unlink(filename, dir_fd=staging_fd)
            except OSError:
                pass
    finally:
        os.close(staging_fd)
    try:
        os.rmdir(staging_name, dir_fd=parent_fd)
    except OSError:
        pass


def _resolved_descriptor_path(descriptor: int) -> Path:
    descriptor_link = Path(f"/proc/self/fd/{descriptor}")
    if not descriptor_link.exists():
        raise PrivateArtifactIOError(
            "Descriptor-bound path verification is unavailable."
        )
    try:
        return descriptor_link.resolve(strict=True)
    except OSError as exc:
        raise PrivateArtifactIOError(
            "Descriptor-bound path verification failed."
        ) from exc


def _assert_outside_repository(path: Path, repository: Path) -> None:
    if path == repository or repository in path.parents:
        raise PrivateArtifactIOError(
            "Private financial artifacts must remain outside the repository."
        )


def _assert_private_regular_file(metadata: os.stat_result) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        raise PrivateArtifactIOError("Private config must be a regular file.")
    _assert_owner_and_mode(metadata, "Private config")


def _assert_private_directory(metadata: os.stat_result) -> None:
    if not stat.S_ISDIR(metadata.st_mode):
        raise PrivateArtifactIOError("Artifact parent must be a directory.")
    _assert_owner_and_mode(metadata, "Artifact parent")


def _assert_owner_and_mode(metadata: os.stat_result, label: str) -> None:
    if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
        raise PrivateArtifactIOError(f"{label} must be owned by the current user.")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PrivateArtifactIOError(
            f"{label} must not grant group or other permissions."
        )
