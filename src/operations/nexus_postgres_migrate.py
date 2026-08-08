from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import psycopg

from src.infrastructure.credentials.regional_secret_manager import RegionalSecretManagerResolver


MIGRATION = Path("/app/migrations/003_nexus_provider_runtime_controls.sql")
MARKER = "AIGC_NEXUS_MIGRATION_RECEIPT:"


def main() -> int:
    secret_ref = os.environ.get("AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF", "").strip()
    if not secret_ref:
        raise SystemExit("AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF is required")
    if not MIGRATION.is_file():
        raise SystemExit("runtime-control migration is not packaged in the image")

    resolver = RegionalSecretManagerResolver()
    resolver.parse_reference(secret_ref)
    dsn = resolver.resolve_text(secret_ref)
    sql = MIGRATION.read_text(encoding="utf-8")
    migration_sha256 = hashlib.sha256(sql.encode()).hexdigest()
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute(sql)
            with conn.cursor() as cur:
                cur.execute("SELECT stop_epoch, emergency_active FROM nexus_runtime_control WHERE singleton = TRUE")
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("migration did not create the runtime-control singleton")
    finally:
        dsn = ""

    receipt = {
        "schema_version": "aigc.nexus-runtime-control-migration-receipt.v1",
        "migration": MIGRATION.name,
        "migration_sha256": migration_sha256,
        "runtime_control_singleton_verified": True,
        "secret_value_emitted": False,
        "provider_call_performed": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    print(MARKER + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
