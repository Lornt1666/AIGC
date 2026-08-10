from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import psycopg

from src.infrastructure.credentials.regional_secret_manager import RegionalSecretManagerResolver


MIGRATIONS = (
    Path("/app/migrations/003_nexus_provider_runtime_controls.sql"),
    Path("/app/migrations/004_nexus_persisted_authority.sql"),
)
MARKER = "AIGC_NEXUS_MIGRATION_RECEIPT:"


def _transaction_body(sql: str) -> str:
    normalized = sql.strip()
    if normalized.upper().startswith("BEGIN;"):
        normalized = normalized[len("BEGIN;"):].lstrip()
    if normalized.upper().endswith("COMMIT;"):
        normalized = normalized[: -len("COMMIT;")].rstrip()
    if not normalized:
        raise ValueError("runtime-control migration body is empty")
    return normalized


def main() -> int:
    secret_ref = os.environ.get("AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF", "").strip()
    if not secret_ref:
        raise SystemExit("AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF is required")
    missing = [migration.name for migration in MIGRATIONS if not migration.is_file()]
    if missing:
        raise SystemExit(
            "required Nexus migrations are not packaged in the image: "
            + ", ".join(missing)
        )

    resolver = RegionalSecretManagerResolver()
    resolver.parse_reference(secret_ref)
    dsn = resolver.resolve_text(secret_ref)
    migration_sources = [
        (migration, migration.read_text(encoding="utf-8"))
        for migration in MIGRATIONS
    ]
    migration_receipts = [
        {
            "name": migration.name,
            "sha256": hashlib.sha256(source_sql.encode()).hexdigest(),
        }
        for migration, source_sql in migration_sources
    ]
    migration_bundle_sha256 = hashlib.sha256(
        json.dumps(
            migration_receipts,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    try:
        with psycopg.connect(dsn) as conn:
            for _migration, source_sql in migration_sources:
                conn.execute(_transaction_body(source_sql))
            with conn.cursor() as cur:
                cur.execute("SELECT stop_epoch, emergency_active FROM nexus_runtime_control WHERE singleton = TRUE")
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("migration did not create the runtime-control singleton")
                cur.execute("SELECT to_regclass('public.nexus_canary_authority_claim')")
                authority_table = cur.fetchone()
                if authority_table is None or authority_table[0] is None:
                    raise RuntimeError("migration did not create the persisted-authority table")
    finally:
        dsn = ""

    receipt = {
        "schema_version": "aigc.nexus-runtime-control-migration-receipt.v2",
        "migrations": migration_receipts,
        "migration_bundle_sha256": migration_bundle_sha256,
        "runtime_control_singleton_verified": True,
        "persisted_authority_table_verified": True,
        "secret_value_emitted": False,
        "provider_call_performed": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    print(MARKER + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
