from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.application import (
    AuthorizationApplicationService,
    IdentityBoundaryService,
    OpportunityScoutApplicationService,
    QuestApplicationService,
    QuestCandidateApplicationService,
)
from src.infrastructure.identity import LocalDevelopmentIdentityAdapter
from src.infrastructure.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteAuthorizationReceiptRepository,
    SQLiteConnectionFactory,
    SQLiteIdentityEvidenceReceiptRepository,
    SQLiteMigrator,
    SQLiteQuestCandidateRepository,
    SQLiteQuestRepository,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = ROOT / ".aigc" / "local_operator.sqlite3"
MIGRATION_ROOT = ROOT / "migrations" / "sqlite"
WORK_SOURCE_CATALOG = ROOT / "config" / "aigc_work_source_gate_catalog.json"
PHASE2_SOURCE_CONFIG = ROOT / "config" / "phase2_sources.json"
QUEST_CANDIDATE_SCHEMA = ROOT / "schemas" / "quest_candidate.schema.json"
QUEST_SCHEMA = ROOT / "schemas" / "quest.schema.json"
IDENTITY_BOUNDARY_CONFIG = ROOT / "config" / "identity_boundary.json"
LOCAL_IDENTITY_FIXTURE = (
    ROOT / "governance" / "identity" / "local_identity_simulation.json"
)
IDENTITY_CONTEXT_SCHEMA = ROOT / "schemas" / "identity_boundary.schema.json"
IDENTITY_RECEIPT_SCHEMA = (
    ROOT / "schemas" / "identity_evidence_receipt.schema.json"
)


@dataclass(frozen=True)
class ApplicationContainer:
    database_path: Path
    identity_boundary_service: IdentityBoundaryService
    authorization_service: AuthorizationApplicationService
    opportunity_scout_service: OpportunityScoutApplicationService
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
    identity_receipt_repository = SQLiteIdentityEvidenceReceiptRepository(
        factory
    )
    audit_repository = SQLiteAuditEventRepository(factory)
    candidate_repository = SQLiteQuestCandidateRepository(factory)
    quest_repository = SQLiteQuestRepository(factory)

    authorization_service = AuthorizationApplicationService(
        authorization_repository
    )
    identity_adapter = LocalDevelopmentIdentityAdapter(
        LOCAL_IDENTITY_FIXTURE
    )
    identity_boundary_service = IdentityBoundaryService(
        provider=identity_adapter,
        membership_resolver=identity_adapter,
        session_verifier=identity_adapter,
        receipt_repository=identity_receipt_repository,
        config_path=IDENTITY_BOUNDARY_CONFIG,
        context_schema_path=IDENTITY_CONTEXT_SCHEMA,
        receipt_schema_path=IDENTITY_RECEIPT_SCHEMA,
    )
    candidate_service = QuestCandidateApplicationService(
        candidate_repository,
        catalog_path=WORK_SOURCE_CATALOG,
        schema_path=QUEST_CANDIDATE_SCHEMA,
        exact_revision=exact_revision,
    )

    return ApplicationContainer(
        database_path=resolved_path,
        identity_boundary_service=identity_boundary_service,
        authorization_service=authorization_service,
        opportunity_scout_service=OpportunityScoutApplicationService(
            candidate_service,
            audit_repository,
            source_config_path=PHASE2_SOURCE_CONFIG,
            exact_revision=exact_revision,
        ),
        quest_candidate_service=candidate_service,
        quest_service=QuestApplicationService(
            candidate_repository,
            quest_repository,
            authorization_service,
            schema_path=QUEST_SCHEMA,
            exact_revision=exact_revision,
        ),
    )
