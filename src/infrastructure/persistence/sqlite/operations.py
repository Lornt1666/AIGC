from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .connection import SQLiteConnectionFactory


@dataclass(frozen=True)
class IntegrityReceipt:
    checked_at: str
    database_path: str
    integrity_result: str
    foreign_keys_enabled: bool
    foreign_key_violations: int
    external_action_performed: bool = False


@dataclass(frozen=True)
class BackupReceipt:
    created_at: str
    source_path: str
    backup_path: str
    backup_sha256: str
    integrity_result: str
    external_action_performed: bool = False


def check_integrity(factory: SQLiteConnectionFactory) -> IntegrityReceipt:
    with factory.connect() as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys_enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    return IntegrityReceipt(
        checked_at=datetime.now(timezone.utc).isoformat(),
        database_path=str(factory.database_path),
        integrity_result=integrity,
        foreign_keys_enabled=foreign_keys_enabled,
        foreign_key_violations=len(violations),
    )


def create_backup(factory: SQLiteConnectionFactory, backup_path: str | Path) -> BackupReceipt:
    destination_path = Path(backup_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source = factory.connect()
    destination = sqlite3.connect(destination_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    digest = sha256(destination_path.read_bytes()).hexdigest()
    backup_factory = SQLiteConnectionFactory(destination_path)
    integrity = check_integrity(backup_factory)
    if integrity.integrity_result != "ok" or integrity.foreign_key_violations:
        raise RuntimeError("Backup integrity validation failed")
    return BackupReceipt(
        created_at=datetime.now(timezone.utc).isoformat(),
        source_path=str(factory.database_path),
        backup_path=str(destination_path),
        backup_sha256=digest,
        integrity_result=integrity.integrity_result,
    )


def write_receipt(receipt: IntegrityReceipt | BackupReceipt, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True), encoding="utf-8")
