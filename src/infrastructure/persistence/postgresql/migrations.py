from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .runtime import (
    PostgresConnectionFactory,
    ProductionPersistenceConfigurationError,
)


_MIGRATION_NAME = re.compile(r"^[0-9]{4}_[a-z0-9_]+\.sql$")
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-z_][a-z0-9_]*)",
    flags=re.IGNORECASE,
)
_PROHIBITED_DESTRUCTIVE = (
    re.compile(r"\bDROP\s+TABLE\b", flags=re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", flags=re.IGNORECASE),
    re.compile(r"\bALTER\s+TABLE\b.*\bDROP\b", flags=re.IGNORECASE | re.DOTALL),
)
_REQUIRED_RELATIONS = {
    "schema_migrations",
    "records",
    "idempotency_records",
    "authorization_receipts",
    "audit_events",
    "identity_evidence_receipts",
    "review_evidence_packets",
    "review_judgment_receipts",
}
_REQUIRED_APPEND_ONLY_RELATIONS = {
    "authorization_receipts",
    "audit_events",
    "identity_evidence_receipts",
    "review_evidence_packets",
    "review_judgment_receipts",
}


@dataclass(frozen=True)
class PostgresMigration:
    version: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True)
class PostgresMigrationResult:
    version: str
    checksum: str
    applied: bool


@dataclass(frozen=True)
class PostgresMigrationPlan:
    migrations: tuple[PostgresMigration, ...]
    relations: tuple[str, ...]
    append_only_relations: tuple[str, ...]
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-POSTGRES-MIGRATION-PLAN-001",
            "contract_version": "1.0.0",
            "migration_count": len(self.migrations),
            "versions": [item.version for item in self.migrations],
            "relations": list(self.relations),
            "append_only_relations": list(self.append_only_relations),
            "fingerprint": self.fingerprint,
            "forward_only": True,
            "external_action_performed": False,
        }


def load_postgres_migration_plan(migration_root: str | Path) -> PostgresMigrationPlan:
    root = Path(migration_root)
    if not root.exists() or not root.is_dir():
        raise ProductionPersistenceConfigurationError(
            f"PostgreSQL migration root does not exist: {root}"
        )
    migrations: list[PostgresMigration] = []
    for path in sorted(root.glob("*.sql")):
        if not _MIGRATION_NAME.fullmatch(path.name):
            raise ProductionPersistenceConfigurationError(
                f"Invalid PostgreSQL migration filename: {path.name}"
            )
        sql = path.read_text(encoding="utf-8")
        if not sql.strip():
            raise ProductionPersistenceConfigurationError(
                f"PostgreSQL migration is empty: {path.name}"
            )
        for pattern in _PROHIBITED_DESTRUCTIVE:
            if pattern.search(sql):
                raise ProductionPersistenceConfigurationError(
                    f"Destructive PostgreSQL migration statement prohibited: {path.name}"
                )
        migrations.append(
            PostgresMigration(
                version=path.stem,
                path=path,
                checksum=sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )
    if not migrations:
        raise ProductionPersistenceConfigurationError(
            "At least one PostgreSQL migration is required"
        )
    versions = [item.version for item in migrations]
    if len(versions) != len(set(versions)):
        raise ProductionPersistenceConfigurationError(
            "PostgreSQL migration versions must be unique"
        )

    combined_sql = "\n".join(item.sql for item in migrations)
    relations = tuple(sorted(set(_CREATE_TABLE.findall(combined_sql))))
    missing_relations = sorted(_REQUIRED_RELATIONS - set(relations))
    if missing_relations:
        raise ProductionPersistenceConfigurationError(
            "PostgreSQL migration plan lacks required relations: "
            + ", ".join(missing_relations)
        )
    append_only = tuple(
        sorted(
            relation
            for relation in _REQUIRED_APPEND_ONLY_RELATIONS
            if re.search(
                rf"CREATE\s+TRIGGER\s+{re.escape(relation)}_no_mutation",
                combined_sql,
                flags=re.IGNORECASE,
            )
        )
    )
    missing_append_only = sorted(
        _REQUIRED_APPEND_ONLY_RELATIONS - set(append_only)
    )
    if missing_append_only:
        raise ProductionPersistenceConfigurationError(
            "PostgreSQL migration plan lacks append-only triggers: "
            + ", ".join(missing_append_only)
        )
    if "JSONB" not in combined_sql.upper() or "TIMESTAMPTZ" not in combined_sql.upper():
        raise ProductionPersistenceConfigurationError(
            "PostgreSQL migration plan must use JSONB and TIMESTAMPTZ"
        )

    fingerprint_material = "|".join(
        f"{item.version}:{item.checksum}" for item in migrations
    )
    fingerprint = sha256(fingerprint_material.encode("utf-8")).hexdigest()
    return PostgresMigrationPlan(
        migrations=tuple(migrations),
        relations=relations,
        append_only_relations=append_only,
        fingerprint=fingerprint,
    )


def _lock_identifier(name: str) -> int:
    raw = int.from_bytes(sha256(name.encode("utf-8")).digest()[:8], "big")
    return raw - (1 << 64) if raw >= (1 << 63) else raw


def _row_checksum(row: Any) -> str | None:
    if row is None:
        return None
    if isinstance(row, Mapping):
        value = row.get("checksum")
        return str(value) if value is not None else None
    try:
        return str(row[0])
    except (IndexError, KeyError, TypeError):
        return None


class PostgresMigrator:
    """Forward-only, checksum-bound PostgreSQL migration runner."""

    def __init__(
        self,
        factory: PostgresConnectionFactory,
        plan: PostgresMigrationPlan,
        *,
        lock_name: str = "aigc-production-schema-migrations-v1",
    ) -> None:
        self.factory = factory
        self.plan = plan
        self.lock_id = _lock_identifier(lock_name)

    def apply_all(self) -> list[PostgresMigrationResult]:
        results: list[PostgresMigrationResult] = []
        for migration in self.plan.migrations:
            result = self.factory.run_with_retry(
                lambda connection, current=migration: self._apply_one(
                    connection,
                    current,
                ),
                governed_transition=True,
            )
            results.append(result)
        return results

    def _apply_one(
        self,
        connection: Any,
        migration: PostgresMigration,
    ) -> PostgresMigrationResult:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL,
                checksum TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (self.lock_id,),
        )
        row = connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version = %s",
            (migration.version,),
        ).fetchone()
        existing_checksum = _row_checksum(row)
        if existing_checksum is not None:
            if existing_checksum != migration.checksum:
                raise ProductionPersistenceConfigurationError(
                    f"PostgreSQL migration checksum mismatch for {migration.version}"
                )
            return PostgresMigrationResult(
                migration.version,
                migration.checksum,
                False,
            )

        connection.execute(migration.sql, prepare=False)
        connection.execute(
            """
            INSERT INTO schema_migrations(version, applied_at, checksum)
            VALUES (%s, %s, %s)
            """,
            (
                migration.version,
                datetime.now(timezone.utc),
                migration.checksum,
            ),
        )
        return PostgresMigrationResult(
            migration.version,
            migration.checksum,
            True,
        )


def migration_versions(plan: PostgresMigrationPlan) -> Sequence[str]:
    return tuple(item.version for item in plan.migrations)
