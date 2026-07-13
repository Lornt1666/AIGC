from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.application import (
    AuthorizationApplicationService,
    QuestApplicationService,
    QuestCandidateApplicationService,
)
from src.infrastructure.persistence.sqlite import (
    SQLiteAuthorizationReceiptRepository,
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteQuestCandidateRepository,
    SQLiteQuestRepository,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = ROOT / ".aigc" / "local_operator.sqlite3"
MIGRATION_ROOT = ROOT / "migrations" / "sqlite"
WORK_SOURCE_CATALOG = ROOT / "config" / "aigc_work_source_gate_catalog.json"
QUEST_CANDIDATE_SCHEMA = ROOT / "schemas" / "quest_candidate.schema.json"
QUEST_SCHEMA = ROOT / "schemas" / "quest.schema.json"


@dataclass(frozen=True)
class ApplicationContainer:
    database_path: Path
    authorization_service: AuthorizationApplicationService
    quest_candidate_service: QuestCandidateApplicationService
    quest_service: QuestApplicationService


def build_container(
    database_path: str | Path | None = None,
) -> ApplicationContainer:
    resolved_path = Path(
        database_path
        or os.environ.get("AIGC_LOCAL_DATABASE_PATH")
        or os.environ.get("AIGC_DATABASE_PATH")
        or DEFAULT_DATABASE_PATH
    )
    exact_revision = os.environ.get(
        "AIGC_EXACT_REVISION",
        "LOCAL_UNVERIFIED",
    )

    factory = SQLiteConnectionFactory(resolved_path)
    SQLiteMigrator(factory, MIGRATION_ROOT).apply_all()

    authorization_repository = SQLiteAuthorizationReceiptRepository(factory)
    candidate_repository = SQLiteQuestCandidateRepository(factory)
    quest_repository = SQLiteQuestRepository(factory)

    return ApplicationContainer(
        database_path=resolved_path,
        authorization_service=AuthorizationApplicationService(
            authorization_repository
        ),
        quest_candidate_service=QuestCandidateApplicationService(
            candidate_repository,
            catalog_path=WORK_SOURCE_CATALOG,
            schema_path=QUEST_CANDIDATE_SCHEMA,
            exact_revision=exact_revision,
        ),
        quest_service=QuestApplicationService(
            candidate_repository,
            quest_repository,
            schema_path=QUEST_SCHEMA,
            exact_revision=exact_revision,
        ),
    )
