from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Callable, Iterator, Mapping, Protocol, TypeVar

from jsonschema import Draft202012Validator, FormatChecker
from psycopg_pool import ConnectionPool


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG_PATH = ROOT / "config" / "production_persistence_baseline.json"
DEFAULT_SCHEMA_PATH = ROOT / "schemas" / "production_persistence_baseline.schema.json"

T = TypeVar("T")
_ALLOWED_ISOLATION = {"READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"}


class ProductionPersistenceError(RuntimeError):
    """Base error for the production persistence baseline."""


class ProductionPersistenceConfigurationError(ProductionPersistenceError):
    """Raised when configuration or authority is insufficient."""


class ProductionPersistenceUnavailable(ProductionPersistenceError):
    """Raised when the managed PostgreSQL runtime cannot be reached safely."""


class SecretReferenceResolver(Protocol):
    def resolve(self, reference: str) -> str:
        """Resolve a secret reference at runtime without logging or persisting its value."""


class PoolProtocol(Protocol):
    def open(self, *, wait: bool = True) -> None: ...
    def close(self) -> None: ...
    def connection(self, *, timeout: float | None = None) -> Any: ...


@dataclass(frozen=True)
class PostgresRuntimeConfig:
    dsn_reference: str
    pool_min_size: int
    pool_max_size: int
    pool_timeout_seconds: int
    connect_timeout_seconds: int
    statement_timeout_ms: int
    lock_timeout_ms: int
    application_name: str
    ssl_mode: str
    default_isolation: str
    governed_transition_isolation: str
    max_attempts: int
    base_backoff_ms: int
    max_backoff_ms: int
    retryable_sqlstates: tuple[str, ...]

    @classmethod
    def from_policy(cls, policy: Mapping[str, Any]) -> "PostgresRuntimeConfig":
        connection = dict(policy["connection"])
        transactions = dict(policy["transactions"])
        return cls(
            dsn_reference=str(connection["dsn_reference"]),
            pool_min_size=int(connection["pool_min_size"]),
            pool_max_size=int(connection["pool_max_size"]),
            pool_timeout_seconds=int(connection["pool_timeout_seconds"]),
            connect_timeout_seconds=int(connection["connect_timeout_seconds"]),
            statement_timeout_ms=int(connection["statement_timeout_ms"]),
            lock_timeout_ms=int(connection["lock_timeout_ms"]),
            application_name=str(connection["application_name"]),
            ssl_mode=str(connection["ssl_mode"]),
            default_isolation=str(transactions["default_isolation"]),
            governed_transition_isolation=str(
                transactions["governed_transition_isolation"]
            ),
            max_attempts=int(transactions["max_attempts"]),
            base_backoff_ms=int(transactions["base_backoff_ms"]),
            max_backoff_ms=int(transactions["max_backoff_ms"]),
            retryable_sqlstates=tuple(
                str(value) for value in transactions["retryable_sqlstates"]
            ),
        )


@dataclass(frozen=True)
class ProductionPersistenceEvaluation:
    status: str
    implemented_internal: bool
    production_complete: bool
    migration_count: int
    blocking_evidence: tuple[str, ...]
    unresolved_configuration: tuple[str, ...]
    resource_creation_authorized: bool
    secret_access_authorized: bool
    data_migration_authorized: bool
    production_deployment_authorized: bool
    external_action_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-PRODUCTION-PERSISTENCE-EVALUATION-001",
            "contract_version": "1.0.0",
            "status": self.status,
            "implemented_internal": self.implemented_internal,
            "production_complete": self.production_complete,
            "migration_count": self.migration_count,
            "blocking_evidence": list(self.blocking_evidence),
            "unresolved_configuration": list(self.unresolved_configuration),
            "resource_creation_authorized": self.resource_creation_authorized,
            "secret_access_authorized": self.secret_access_authorized,
            "data_migration_authorized": self.data_migration_authorized,
            "production_deployment_authorized": self.production_deployment_authorized,
            "external_action_performed": self.external_action_performed,
        }


def load_persistence_policy(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    try:
        policy = json.loads(Path(config_path).read_text(encoding="utf-8"))
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionPersistenceConfigurationError(
            "Unable to load the production persistence baseline"
        ) from exc
    if not isinstance(policy, dict) or not isinstance(schema, dict):
        raise ProductionPersistenceConfigurationError(
            "Persistence policy and schema must be JSON objects"
        )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(policy), key=lambda item: list(item.absolute_path))
    if errors:
        messages: list[str] = []
        for error in errors[:10]:
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        raise ProductionPersistenceConfigurationError(
            "Production persistence validation failed: " + "; ".join(messages)
        )
    return policy


def evaluate_persistence_policy(
    policy: Mapping[str, Any],
    *,
    migration_count: int,
) -> ProductionPersistenceEvaluation:
    value = dict(policy)
    evidence = dict(value["operational_evidence"])
    authority = dict(value["authority"])
    blocking: list[str] = []
    for name in (
        "cloud_sql_instance_observed",
        "migration_lock_observed",
        "prior_schema_upgrade_passed",
        "concurrent_transition_passed",
        "connection_loss_retry_passed",
        "backup_integrity_passed",
        "isolated_restore_passed",
        "cross_tenant_negative_passed",
    ):
        if evidence.get(name) is not True:
            blocking.append(name)
    if evidence.get("rpo_measured_minutes") is None:
        blocking.append("rpo_measurement")
    if evidence.get("rto_measured_minutes") is None:
        blocking.append("rto_measurement")

    unresolved: list[str] = []
    dsn_reference = str(value["connection"]["dsn_reference"])
    if "TBD_" in dsn_reference or "/TBD" in dsn_reference:
        unresolved.append("postgres_dsn_secret_project")
    if value["backup_recovery"]["detailed_schedule_status"] != "APPROVED":
        unresolved.append("detailed_backup_schedule")
    if value["tenant_isolation"]["database_rls_status"] != "VERIFIED":
        unresolved.append("database_row_isolation")
    if value["compatibility"]["postgres_repository_adapter_status"] != "COMPLETE":
        unresolved.append("postgres_repository_adapters")

    implemented = (
        value.get("status") == "IMPLEMENTED_INTERNAL_PENDING_STAGING_EVIDENCE"
        and authority.get("adapter_implementation_authorized") is True
        and authority.get("migration_definition_authorized") is True
        and migration_count >= 3
        and value.get("external_action_performed") is False
    )
    complete = implemented and not blocking and not unresolved
    return ProductionPersistenceEvaluation(
        status="complete" if complete else "implemented_internal",
        implemented_internal=implemented,
        production_complete=complete,
        migration_count=migration_count,
        blocking_evidence=tuple(blocking),
        unresolved_configuration=tuple(unresolved),
        resource_creation_authorized=bool(
            authority.get("cloud_sql_resource_creation_authorized")
        ),
        secret_access_authorized=bool(authority.get("secret_access_authorized")),
        data_migration_authorized=bool(authority.get("data_migration_authorized")),
        production_deployment_authorized=bool(
            authority.get("production_deployment_authorized")
        ),
    )


PoolBuilder = Callable[[str, PostgresRuntimeConfig], PoolProtocol]


def _default_pool_builder(dsn: str, config: PostgresRuntimeConfig) -> PoolProtocol:
    return ConnectionPool(
        conninfo=dsn,
        min_size=config.pool_min_size,
        max_size=config.pool_max_size,
        timeout=float(config.pool_timeout_seconds),
        kwargs={
            "connect_timeout": config.connect_timeout_seconds,
            "application_name": config.application_name,
            "sslmode": config.ssl_mode,
            "autocommit": False,
        },
        open=False,
        name="aigc-production",
    )


class PostgresConnectionFactory:
    """Secret-reference-only pooled PostgreSQL connection factory."""

    def __init__(
        self,
        config: PostgresRuntimeConfig,
        *,
        secret_resolver: SecretReferenceResolver,
        pool_builder: PoolBuilder = _default_pool_builder,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.secret_resolver = secret_resolver
        self.pool_builder = pool_builder
        self.sleeper = sleeper
        self._pool: PoolProtocol | None = None

    @property
    def opened(self) -> bool:
        return self._pool is not None

    def open(self) -> None:
        if self._pool is not None:
            return
        if "TBD_" in self.config.dsn_reference or "/TBD" in self.config.dsn_reference:
            raise ProductionPersistenceConfigurationError(
                "PostgreSQL secret reference is unresolved; resource access is blocked"
            )
        dsn = self.secret_resolver.resolve(self.config.dsn_reference)
        if not isinstance(dsn, str) or not dsn.strip():
            raise ProductionPersistenceConfigurationError(
                "Secret resolver returned no PostgreSQL connection material"
            )
        pool = self.pool_builder(dsn, self.config)
        try:
            pool.open(wait=True)
        except Exception as exc:
            raise ProductionPersistenceUnavailable(
                "PostgreSQL connection pool could not be opened"
            ) from exc
        self._pool = pool

    def close(self) -> None:
        if self._pool is None:
            return
        self._pool.close()
        self._pool = None

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self._pool is None:
            raise ProductionPersistenceUnavailable(
                "PostgreSQL connection pool is not open"
            )
        with self._pool.connection(
            timeout=float(self.config.pool_timeout_seconds)
        ) as connection:
            yield connection

    @contextmanager
    def transaction(
        self,
        *,
        isolation: str | None = None,
    ) -> Iterator[Any]:
        selected = isolation or self.config.default_isolation
        if selected not in _ALLOWED_ISOLATION:
            raise ProductionPersistenceConfigurationError(
                f"Unsupported PostgreSQL isolation level: {selected}"
            )
        with self.connect() as connection:
            with connection.transaction():
                connection.execute(
                    f"SET TRANSACTION ISOLATION LEVEL {selected}"
                )
                connection.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(self.config.statement_timeout_ms),),
                )
                connection.execute(
                    "SELECT set_config('lock_timeout', %s, true)",
                    (str(self.config.lock_timeout_ms),),
                )
                yield connection

    def run_with_retry(
        self,
        operation: Callable[[Any], T],
        *,
        governed_transition: bool = False,
    ) -> T:
        isolation = (
            self.config.governed_transition_isolation
            if governed_transition
            else self.config.default_isolation
        )
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                with self.transaction(isolation=isolation) as connection:
                    return operation(connection)
            except Exception as exc:
                sqlstate = getattr(exc, "sqlstate", None)
                retryable = sqlstate in set(self.config.retryable_sqlstates)
                if not retryable or attempt >= self.config.max_attempts:
                    raise
                backoff_ms = min(
                    self.config.max_backoff_ms,
                    self.config.base_backoff_ms * (2 ** (attempt - 1)),
                )
                self.sleeper(backoff_ms / 1000)
        raise ProductionPersistenceUnavailable("PostgreSQL retry loop exhausted")

    def health_check(self) -> bool:
        def check(connection: Any) -> bool:
            row = connection.execute("SELECT 1").fetchone()
            if row is None:
                return False
            if isinstance(row, Mapping):
                return 1 in row.values()
            return int(row[0]) == 1

        return self.run_with_retry(check)

    def redacted_summary(self) -> dict[str, Any]:
        return {
            "driver": "psycopg3",
            "dsn_reference": self.config.dsn_reference,
            "raw_dsn_present": False,
            "pool_min_size": self.config.pool_min_size,
            "pool_max_size": self.config.pool_max_size,
            "default_isolation": self.config.default_isolation,
            "governed_transition_isolation": (
                self.config.governed_transition_isolation
            ),
            "opened": self.opened,
            "external_action_performed": False,
        }
