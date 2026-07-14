from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Iterator

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.infrastructure.persistence.postgresql import (
    PostgresConnectionFactory,
    PostgresMigrator,
    PostgresRuntimeConfig,
    ProductionPersistenceConfigurationError,
    evaluate_persistence_policy,
    load_persistence_policy,
    load_postgres_migration_plan,
    migration_versions,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "production_persistence_baseline.json"
SCHEMA_PATH = ROOT / "schemas" / "production_persistence_baseline.schema.json"
MIGRATION_ROOT = ROOT / "migrations" / "postgresql"


class FakeResult:
    def __init__(self, row: Any = None) -> None:
        self.row = row

    def fetchone(self) -> Any:
        return self.row


class FakeConnection:
    def __init__(self) -> None:
        self.commands: list[tuple[str, Any, Any]] = []
        self.migration_checksums: dict[str, str] = {}

    @contextmanager
    def transaction(self) -> Iterator["FakeConnection"]:
        yield self

    def execute(
        self,
        sql: str,
        params: Any = None,
        prepare: Any = None,
    ) -> FakeResult:
        normalized = " ".join(sql.split())
        self.commands.append((normalized, params, prepare))
        if normalized == "SELECT 1":
            return FakeResult((1,))
        if normalized.startswith(
            "SELECT checksum FROM schema_migrations WHERE version ="
        ):
            version = str(params[0])
            checksum = self.migration_checksums.get(version)
            return FakeResult((checksum,) if checksum is not None else None)
        if normalized.startswith("INSERT INTO schema_migrations"):
            version = str(params[0])
            checksum = str(params[2])
            self.migration_checksums[version] = checksum
            return FakeResult()
        return FakeResult()


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection_value = connection
        self.opened = False
        self.closed = False
        self.connection_timeouts: list[float | None] = []

    def open(self, *, wait: bool = True) -> None:
        assert wait is True
        self.opened = True

    def close(self) -> None:
        self.closed = True

    @contextmanager
    def connection(self, *, timeout: float | None = None) -> Iterator[FakeConnection]:
        self.connection_timeouts.append(timeout)
        yield self.connection_value


class FakeResolver:
    def __init__(self, resolved_connection_material: str) -> None:
        self.resolved_connection_material = resolved_connection_material
        self.references: list[str] = []

    def resolve(self, reference: str) -> str:
        self.references.append(reference)
        return self.resolved_connection_material


class RetryableDatabaseError(RuntimeError):
    sqlstate = "40001"


def runtime_config(*, resolved: bool) -> PostgresRuntimeConfig:
    policy = load_persistence_policy(POLICY_PATH, SCHEMA_PATH)
    config = PostgresRuntimeConfig.from_policy(policy)
    if resolved:
        return replace(
            config,
            dsn_reference="gcp_secret://approved-project/aigc-postgres-dsn",
        )
    return config


def test_persistence_policy_is_internal_and_staging_incomplete() -> None:
    policy = load_persistence_policy(POLICY_PATH, SCHEMA_PATH)
    plan = load_postgres_migration_plan(MIGRATION_ROOT)
    evaluation = evaluate_persistence_policy(
        policy,
        migration_count=len(plan.migrations),
    )

    assert evaluation.implemented_internal is True
    assert evaluation.production_complete is False
    assert evaluation.status == "implemented_internal"
    assert evaluation.migration_count == 3
    assert set(evaluation.unresolved_configuration) == {
        "postgres_dsn_secret_project",
        "detailed_backup_schedule",
        "database_row_isolation",
        "postgres_repository_adapters",
    }
    assert evaluation.resource_creation_authorized is False
    assert evaluation.secret_access_authorized is False
    assert evaluation.data_migration_authorized is False
    assert evaluation.production_deployment_authorized is False
    assert evaluation.external_action_performed is False


def test_postgresql_migration_plan_is_forward_only_and_append_only() -> None:
    first = load_postgres_migration_plan(MIGRATION_ROOT)
    second = load_postgres_migration_plan(MIGRATION_ROOT)

    assert migration_versions(first) == (
        "0001_transactional_storage",
        "0002_identity_boundary_v1",
        "0003_review_evidence_packet_v1",
    )
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert set(first.relations) == {
        "schema_migrations",
        "records",
        "idempotency_records",
        "authorization_receipts",
        "audit_events",
        "identity_evidence_receipts",
        "review_evidence_packets",
        "review_judgment_receipts",
    }
    assert set(first.append_only_relations) == {
        "authorization_receipts",
        "audit_events",
        "identity_evidence_receipts",
        "review_evidence_packets",
        "review_judgment_receipts",
    }
    assert all(len(item.checksum) == 64 for item in first.migrations)
    assert all("JSONB" in item.sql.upper() or item.version == "0002_identity_boundary_v1" for item in first.migrations)
    assert all("TIMESTAMPTZ" in item.sql.upper() for item in first.migrations)


def test_unresolved_reference_blocks_before_resolver_or_pool_use() -> None:
    resolver = FakeResolver("postgresql://db.example.invalid/aigc")
    pool_created = False

    def builder(value: str, config: PostgresRuntimeConfig) -> FakePool:
        nonlocal pool_created
        del value, config
        pool_created = True
        return FakePool(FakeConnection())

    factory = PostgresConnectionFactory(
        runtime_config(resolved=False),
        secret_resolver=resolver,
        pool_builder=builder,
    )

    with pytest.raises(
        ProductionPersistenceConfigurationError,
        match="unresolved",
    ):
        factory.open()

    assert resolver.references == []
    assert pool_created is False
    assert factory.opened is False


def test_resolved_reference_opens_pool_and_summary_never_contains_material() -> None:
    resolved_connection_material = "postgresql://db.example.invalid/aigc"
    resolver = FakeResolver(resolved_connection_material)
    connection = FakeConnection()
    pool = FakePool(connection)
    received: list[str] = []

    def builder(value: str, config: PostgresRuntimeConfig) -> FakePool:
        received.append(value)
        assert config.ssl_mode == "verify-full"
        return pool

    factory = PostgresConnectionFactory(
        runtime_config(resolved=True),
        secret_resolver=resolver,
        pool_builder=builder,
    )
    factory.open()
    summary = factory.redacted_summary()

    assert pool.opened is True
    assert resolver.references == [
        "gcp_secret://approved-project/aigc-postgres-dsn"
    ]
    assert received == [resolved_connection_material]
    assert summary["raw_dsn_present"] is False
    assert resolved_connection_material not in json.dumps(summary)
    assert summary["dsn_reference"].startswith("gcp_secret://")
    assert summary["external_action_performed"] is False

    factory.close()
    assert pool.closed is True
    assert factory.opened is False


def test_governed_transition_retries_serialization_failure_with_backoff() -> None:
    resolver = FakeResolver("postgresql://db.example.invalid/aigc")
    connection = FakeConnection()
    pool = FakePool(connection)
    sleeps: list[float] = []
    factory = PostgresConnectionFactory(
        runtime_config(resolved=True),
        secret_resolver=resolver,
        pool_builder=lambda value, config: pool,
        sleeper=sleeps.append,
    )
    factory.open()
    attempts = 0

    def operation(current: FakeConnection) -> str:
        nonlocal attempts
        assert current is connection
        attempts += 1
        if attempts == 1:
            raise RetryableDatabaseError("retry this transaction")
        return "completed"

    result = factory.run_with_retry(operation, governed_transition=True)

    assert result == "completed"
    assert attempts == 2
    assert sleeps == [0.05]
    isolation_commands = [
        command
        for command, _, _ in connection.commands
        if command.startswith("SET TRANSACTION ISOLATION LEVEL")
    ]
    assert isolation_commands == [
        "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE",
        "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE",
    ]
    assert any("statement_timeout" in command for command, _, _ in connection.commands)
    assert any("lock_timeout" in command for command, _, _ in connection.commands)


def test_health_check_uses_pooled_read_committed_transaction() -> None:
    resolver = FakeResolver("postgresql://db.example.invalid/aigc")
    connection = FakeConnection()
    pool = FakePool(connection)
    factory = PostgresConnectionFactory(
        runtime_config(resolved=True),
        secret_resolver=resolver,
        pool_builder=lambda value, config: pool,
    )
    factory.open()

    assert factory.health_check() is True
    assert any(command == "SELECT 1" for command, _, _ in connection.commands)
    assert any(
        command == "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
        for command, _, _ in connection.commands
    )


class FakeMigrationFactory:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.governed_flags: list[bool] = []

    def run_with_retry(self, operation: Any, *, governed_transition: bool = False) -> Any:
        self.governed_flags.append(governed_transition)
        return operation(self.connection)


def test_migrator_is_idempotent_advisory_locked_and_checksum_bound() -> None:
    plan = load_postgres_migration_plan(MIGRATION_ROOT)
    connection = FakeConnection()
    factory = FakeMigrationFactory(connection)
    migrator = PostgresMigrator(factory, plan)

    first = migrator.apply_all()
    replay = migrator.apply_all()

    assert [item.applied for item in first] == [True, True, True]
    assert [item.applied for item in replay] == [False, False, False]
    assert factory.governed_flags == [True] * 6
    advisory_locks = [
        command
        for command, _, _ in connection.commands
        if command.startswith("SELECT pg_advisory_xact_lock")
    ]
    assert len(advisory_locks) == 6
    assert connection.migration_checksums == {
        item.version: item.checksum for item in plan.migrations
    }

    first_migration = plan.migrations[0]
    connection.migration_checksums[first_migration.version] = "f" * 64
    with pytest.raises(
        ProductionPersistenceConfigurationError,
        match="checksum mismatch",
    ):
        migrator.apply_all()


def test_future_database_recovery_receipt_contract_is_strict() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "database_recovery_receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    receipt = {
        "contract_id": "AIGC-DATABASE-RECOVERY-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "DBR-" + "A" * 24,
        "environment": "isolated_staging",
        "exact_revision": "a" * 40,
        "source_backup_reference": "cloudsql-backup://staging/example",
        "source_backup_digest": "sha256:" + "b" * 64,
        "restore_target_reference": "cloudsql-instance://isolated-restore/example",
        "started_at": "2026-07-14T02:00:00+00:00",
        "completed_at": "2026-07-14T03:00:00+00:00",
        "measured_rpo_minutes": 10,
        "measured_rto_minutes": 60,
        "integrity_checks": [
            "schema_migrations",
            "record_counts",
            "foreign_keys",
            "receipt_digests",
            "audit_chain",
            "tenant_project_bindings",
            "application_health",
        ],
        "audit_chain_preserved": True,
        "append_only_receipts_preserved": True,
        "tenant_isolation_negative_passed": True,
        "result": "PASS",
        "reason_codes": [],
        "operator_review_required": True,
        "production_data_used": False,
        "external_action_performed": False,
    }

    assert not list(validator.iter_errors(receipt))
    injected = dict(receipt)
    injected["claimed_production_ready"] = True
    assert list(validator.iter_errors(injected))
