"""Atomic lock-publication hardening for the Ω Mission OS Connector Kernel."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import socket
import time
from typing import Callable, Iterator

from .connector_kernel_v2 import *  # noqa: F401,F403
from .connector_kernel_v2 import AppendOnlyEvidenceLedger as _BaseEvidenceLedger


class AppendOnlyEvidenceLedger(_BaseEvidenceLedger):
    """Ledger with atomically published lock ownership.

    A candidate directory is built privately, including a durable owner record,
    and then atomically renamed into the canonical lock path. The canonical lock
    is therefore never visible without complete owner metadata.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        lock_timeout_seconds: float = 10.0,
        stale_lock_seconds: float = 30.0,
        publication_hook: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            path,
            lock_timeout_seconds=lock_timeout_seconds,
            stale_lock_seconds=stale_lock_seconds,
        )
        self._publication_hook = publication_hook

    def _lock_age_seconds(self) -> float | None:
        try:
            modified = datetime.fromtimestamp(self.lock_path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return None
        return (datetime.now(timezone.utc) - modified).total_seconds()

    def _recover_stale_lock(self) -> bool:
        """Recover only a proven-old lock whose recorded local owner is dead."""
        lock_age = self._lock_age_seconds()
        if lock_age is None or lock_age <= self.stale_lock_seconds:
            return False
        try:
            owner = json.loads(self.owner_path.read_text(encoding="utf-8"))
            created_at = _parse_utc(owner.get("created_at"), "lock created_at")
            owner_age = (datetime.now(timezone.utc) - created_at).total_seconds()
            hostname = owner.get("hostname")
            pid = int(owner.get("pid", -1))
            token = owner.get("token")
        except (OSError, ValueError, TypeError, json.JSONDecodeError, PermissionError):
            return False
        if owner_age <= self.stale_lock_seconds:
            return False
        if hostname != socket.gethostname():
            return False
        if not isinstance(token, str) or not token:
            return False
        if self._pid_alive(pid):
            return False
        try:
            observed = json.loads(self.owner_path.read_text(encoding="utf-8"))
            if observed.get("token") != token:
                return False
            self.owner_path.unlink()
            self.lock_path.rmdir()
            return True
        except (OSError, json.JSONDecodeError):
            return False

    def _publish_lock_atomically(self, token: str) -> bool:
        candidate = self.lock_path.with_name(
            f".{self.lock_path.name}.candidate.{token}"
        )
        owner_path = candidate / "owner.json"
        try:
            candidate.mkdir(parents=True)
            if self._publication_hook is not None:
                self._publication_hook()
            owner = {
                "token": token,
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            with owner_path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(owner, sort_keys=True))
                handle.flush()
                os.fsync(handle.fileno())
            try:
                candidate.rename(self.lock_path)
                return True
            except OSError:
                return False
        finally:
            try:
                owner_path.unlink(missing_ok=True)
                candidate.rmdir()
            except OSError:
                pass

    @contextmanager
    def transaction(self) -> Iterator[None]:
        deadline = time.monotonic() + self.lock_timeout_seconds
        token = secrets.token_hex(16)
        while True:
            if self._publish_lock_atomically(token):
                break
            self._recover_stale_lock()
            if time.monotonic() >= deadline:
                raise TimeoutError("connector evidence transaction lock timed out")
            time.sleep(0.01)
        try:
            yield
        finally:
            try:
                owner = json.loads(self.owner_path.read_text(encoding="utf-8"))
                if owner.get("token") == token:
                    self.owner_path.unlink()
                    self.lock_path.rmdir()
            except (OSError, json.JSONDecodeError):
                pass
