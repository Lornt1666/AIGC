from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .connection import SQLiteConnectionFactory


@dataclass(frozen=True)
class MigrationResult:
    version: str
    checksum: str
    applied: bool


class SQLiteMigrator:
    def __init__(self, factory: SQLiteConnectionFactory, migration_root: str | Path) -> None:
        self.factory = factory
        self.migration_root = Path(migration_root)

    def apply_all(self) -> list[MigrationResult]:
        results: list[MigrationResult] = []
        for path in sorted(self.migration_root.glob("*.sql")):
            version = path.stem
            sql = path.read_text(encoding="utf-8")
            checksum = sha256(sql.encode("utf-8")).hexdigest()
            connection = self.factory.connect()
            try:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL, checksum TEXT NOT NULL)"
                )
                row = connection.execute(
                    "SELECT checksum FROM schema_migrations WHERE version = ?", (version,)
                ).fetchone()
                if row:
                    if row["checksum"] != checksum:
                        raise RuntimeError(f"Migration checksum mismatch for {version}")
                    results.append(MigrationResult(version, checksum, False))
                    continue
                connection.executescript("BEGIN IMMEDIATE;\n" + sql + "\nCOMMIT;")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at, checksum) VALUES (?, ?, ?)",
                    (version, datetime.now(timezone.utc).isoformat(), checksum),
                )
                connection.execute("COMMIT")
                results.append(MigrationResult(version, checksum, True))
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            finally:
                connection.close()
        return results
