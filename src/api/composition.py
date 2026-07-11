from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.application.authorization_service import AuthorizationApplicationService
from src.infrastructure.persistence.sqlite import (
    SQLiteAuthorizationReceiptRepository,
    SQLiteConnectionFactory,
    SQLiteMigrator,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = ROOT / ".aigc" / "local_operator.sqlite3"
MIGRATION_ROOT = ROOT / "migrations" / "sqlite"


@dataclass(frozen=True)
class ApplicationContainer:
    database_path: Path
    authorization_service: AuthorizationApplicationService


def build_container(database_path: str | Path | None = None) -> ApplicationContainer:
    resolved_path = Path(
        database_path
        or os.environ.get("AIGC_LOCAL_DATABASE_PATH")
        or DEFAULT_DATABASE_PATH
    )
    factory = SQLiteConnectionFactory(resolved_path)
    SQLiteMigrator(factory, MIGRATION_ROOT).apply_all()
    repository = SQLiteAuthorizationReceiptRepository(factory)
    return ApplicationContainer(
        database_path=resolved_path,
        authorization_service=AuthorizationApplicationService(repository),
    )
