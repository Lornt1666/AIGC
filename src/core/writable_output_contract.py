"""Preflight validation for phase output directories.

This validates declared paths before a phase runs; it does not make ephemeral
storage durable or prove that undeclared writes are impossible. Durable outputs
must be routed to the configured shared artifact/state backend.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

StorageClass = Literal["ephemeral", "durable"]


class OutputContractError(ValueError):
    """Raised when an output contract is unsafe or cannot be satisfied."""


@dataclass(frozen=True)
class OutputPath:
    name: str
    path: str
    storage: StorageClass
    required: bool = True


@dataclass(frozen=True)
class OutputCheck:
    name: str
    path: str
    storage: StorageClass
    writable: bool
    reason: str | None = None


def _resolve_under_root(root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise OutputContractError(f"output path must be relative to data root: {relative_path}")
    if not relative_path or any(part == ".." for part in candidate.parts):
        raise OutputContractError(f"output path escapes data root: {relative_path}")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise OutputContractError(f"output path escapes data root: {relative_path}")
    return resolved


def validate_output_contract(
    data_root: str | os.PathLike[str],
    outputs: Iterable[OutputPath],
    *,
    probe_writes: bool = True,
) -> list[OutputCheck]:
    """Validate declared output directories using the current process identity."""
    root = Path(data_root)
    if not root.exists() or not root.is_dir():
        raise OutputContractError(f"data root must be an existing directory: {root}")
    checks: list[OutputCheck] = []
    names: set[str] = set()
    paths: set[str] = set()
    for output in outputs:
        if not output.name.strip() or output.name in names:
            raise OutputContractError(f"output names must be non-empty and unique: {output.name!r}")
        names.add(output.name)
        path = _resolve_under_root(root, output.path)
        normalized = str(path)
        if normalized in paths:
            raise OutputContractError(f"output paths must be unique: {output.path}")
        paths.add(normalized)
        try:
            if path.exists() and not path.is_dir():
                raise OutputContractError(f"output path is not a directory: {output.path}")
            if not path.exists():
                if not output.required:
                    checks.append(OutputCheck(output.name, normalized, output.storage, True))
                    continue
                path.mkdir(parents=True, exist_ok=True)
            if not os.access(path, os.W_OK | os.X_OK):
                raise OutputContractError(f"output directory is not writable by current UID: {output.path}")
            if probe_writes:
                fd, probe = tempfile.mkstemp(prefix=".aigc-write-probe-", dir=path)
                os.close(fd)
                os.unlink(probe)
            checks.append(OutputCheck(output.name, normalized, output.storage, True))
        except OutputContractError:
            raise
        except OSError as exc:
            raise OutputContractError(
                f"cannot prepare output directory {output.path!r}: {type(exc).__name__}"
            ) from exc
    return checks
