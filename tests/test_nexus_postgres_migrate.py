from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.operations.nexus_postgres_migrate as migrator


class _Cursor:
    def __init__(self) -> None:
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query: str) -> None:
        self.query = query

    def fetchone(self):
        if "to_regclass" in self.query:
            return ("nexus_canary_authority_claim",)
        return (0, False)


class _Connection:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql: str) -> None:
        self.executed.append(sql)

    def cursor(self) -> _Cursor:
        return _Cursor()


def test_migrator_applies_runtime_and_persisted_authority_in_one_connection(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    migration_003 = tmp_path / "003_nexus_provider_runtime_controls.sql"
    migration_004 = tmp_path / "004_nexus_persisted_authority.sql"
    migration_003.write_text("BEGIN;\nSELECT 3;\nCOMMIT;\n", encoding="utf-8")
    migration_004.write_text("BEGIN;\nSELECT 4;\nCOMMIT;\n", encoding="utf-8")
    connection = _Connection()

    class _Resolver:
        def parse_reference(self, reference: str):
            assert reference.endswith("/versions/7")

        def resolve_text(self, _reference: str) -> str:
            return "postgresql://runtime-only"

    monkeypatch.setattr(migrator, "MIGRATIONS", (migration_003, migration_004))
    monkeypatch.setattr(migrator, "RegionalSecretManagerResolver", _Resolver)
    monkeypatch.setattr(migrator.psycopg, "connect", lambda _dsn: connection)
    monkeypatch.setenv(
        "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF",
        "projects/aigc-stage/locations/northamerica-northeast1/"
        "secrets/runtime-control-dsn/versions/7",
    )

    assert migrator.main() == 0
    assert connection.executed == ["SELECT 3;", "SELECT 4;"]
    marker = capsys.readouterr().out.strip()
    assert marker.startswith(migrator.MARKER)
    receipt = json.loads(marker.removeprefix(migrator.MARKER))
    assert receipt["schema_version"] == "aigc.nexus-runtime-control-migration-receipt.v2"
    assert [item["name"] for item in receipt["migrations"]] == [
        migration_003.name,
        migration_004.name,
    ]
    assert receipt["persisted_authority_table_verified"] is True
    assert receipt["secret_value_emitted"] is False


def test_migrator_rejects_missing_authority_migration(
    monkeypatch,
    tmp_path: Path,
) -> None:
    migration_003 = tmp_path / "003_nexus_provider_runtime_controls.sql"
    migration_004 = tmp_path / "004_nexus_persisted_authority.sql"
    migration_003.write_text("SELECT 3;\n", encoding="utf-8")
    monkeypatch.setattr(migrator, "MIGRATIONS", (migration_003, migration_004))
    monkeypatch.setenv(
        "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF",
        "projects/aigc-stage/locations/northamerica-northeast1/"
        "secrets/runtime-control-dsn/versions/7",
    )
    with pytest.raises(SystemExit, match="004_nexus_persisted_authority"):
        migrator.main()
