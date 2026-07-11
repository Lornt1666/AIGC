from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from src.infrastructure.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteAuthorizationReceiptRepository,
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteRecordRepository,
    check_integrity,
    create_backup,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "sqlite"


def prepared(tmp_path: Path) -> SQLiteConnectionFactory:
    factory = SQLiteConnectionFactory(tmp_path / "aigc.sqlite3", busy_timeout_ms=15000)
    results = SQLiteMigrator(factory, MIGRATIONS).apply_all()
    assert results and results[0].applied
    return factory


def test_migration_ledger_and_foreign_keys(tmp_path: Path) -> None:
    factory = prepared(tmp_path)
    second = SQLiteMigrator(factory, MIGRATIONS).apply_all()
    assert second and second[0].applied is False
    with factory.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_restart_persistence_and_optimistic_revision(tmp_path: Path) -> None:
    factory = prepared(tmp_path)
    first_repo = SQLiteRecordRepository(factory, "principals")
    created = first_repo.put("principal-a", {"status": "ACTIVE"})
    assert created.revision == 1

    restarted_repo = SQLiteRecordRepository(SQLiteConnectionFactory(factory.database_path), "principals")
    loaded = restarted_repo.get("principal-a")
    assert loaded and loaded.payload["status"] == "ACTIVE"
    updated = restarted_repo.put(
        "principal-a",
        {"status": "SUSPENDED"},
        expected_revision=loaded.revision,
    )
    assert updated.revision == 2
    with pytest.raises(RuntimeError, match="Optimistic concurrency conflict"):
        restarted_repo.put("principal-a", {"status": "ACTIVE"}, expected_revision=1)


def test_idempotent_replay_and_key_mismatch(tmp_path: Path) -> None:
    repo = SQLiteRecordRepository(prepared(tmp_path), "jobs")
    first = repo.put("job-a", {"state": "PROPOSED"}, idempotency_key="idem-1")
    replay = repo.put("job-a", {"state": "PROPOSED"}, idempotency_key="idem-1")
    assert replay == first
    with pytest.raises(ValueError, match="different payload"):
        repo.put("job-a", {"state": "ACCEPTED"}, idempotency_key="idem-1")


def test_authorization_receipts_are_immutable(tmp_path: Path) -> None:
    repository = SQLiteAuthorizationReceiptRepository(prepared(tmp_path))
    stored = repository.append(
        "receipt-a",
        {"result": "PERMIT", "external_action_performed": False},
        exact_revision="a" * 40,
        request_digest="b" * 64,
    )
    assert repository.get("receipt-a") == stored
    with pytest.raises(ValueError, match="immutable"):
        repository.append(
            "receipt-a",
            {"result": "DENY", "external_action_performed": False},
            exact_revision="a" * 40,
            request_digest="b" * 64,
        )


def test_audit_chain_is_append_only(tmp_path: Path) -> None:
    factory = prepared(tmp_path)
    audit = SQLiteAuditEventRepository(factory)
    first = audit.append("event-1", "operator.decision", {"result": "ACCEPT"}, exact_revision="a" * 40)
    second = audit.append("event-2", "job.transition", {"state": "ACCEPTED"}, exact_revision="a" * 40)
    assert second.payload["previous_event_hash"] == first.payload["event_hash"]
    with factory.connect() as connection:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute("UPDATE audit_events SET event_type = 'changed' WHERE event_id = 'event-1'")


def test_concurrent_distinct_writes(tmp_path: Path) -> None:
    factory = prepared(tmp_path)

    def write(index: int) -> int:
        repo = SQLiteRecordRepository(factory, "artifacts")
        return repo.put(f"artifact-{index}", {"index": index}).revision

    with ThreadPoolExecutor(max_workers=8) as executor:
        revisions = list(executor.map(write, range(24)))
    assert revisions == [1] * 24
    assert len(SQLiteRecordRepository(factory, "artifacts").list()) == 24


def test_integrity_and_backup_restore(tmp_path: Path) -> None:
    factory = prepared(tmp_path)
    SQLiteRecordRepository(factory, "sessions").put("session-a", {"state": "ACTIVE"})
    integrity = check_integrity(factory)
    assert integrity.integrity_result == "ok"
    assert integrity.foreign_keys_enabled is True
    assert integrity.foreign_key_violations == 0

    backup_path = tmp_path / "backup" / "aigc.sqlite3"
    receipt = create_backup(factory, backup_path)
    assert len(receipt.backup_sha256) == 64
    restored = SQLiteRecordRepository(SQLiteConnectionFactory(backup_path), "sessions").get("session-a")
    assert restored and restored.payload["state"] == "ACTIVE"
