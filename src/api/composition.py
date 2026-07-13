from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.application import (
    AuthorizationApplicationService,
    OpportunityScoutApplicationService,
    QuestApplicationService,
    QuestCandidateApplicationService,
    QuestConductor,
)
from src.infrastructure.persistence.sqlite import (
    SQLiteAgentHandoffRepository,
    SQLiteAuditEventRepository,
    SQLiteAuthorizationReceiptRepository,
    SQLiteConnectionFactory,
    SQLiteMigrator,
    SQLiteQuestCandidateRepository,
    SQLiteQuestRepository,
    SQLiteReviewEvidencePacketRepository,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = ROOT / ".aigc" / "local_operator.sqlite3"
MIGRATION_ROOT = ROOT / "migrations" / "sqlite"
WORK_SOURCE_CATALOG = ROOT / "config" / "aigc_work_source_gate_catalog.json"
PHASE2_SOURCE_CONFIG = ROOT / "config" / "phase2_sources.json"
QUEST_CANDIDATE_SCHEMA = ROOT / "schemas" / "quest_candidate.schema.json"
QUEST_SCHEMA = ROOT / "schemas" / "quest.schema.json"
AGENT_REGISTRY = ROOT / "config" / "agent_registry_v1.json"
AGENT_REGISTRY_SCHEMA = ROOT / "schemas" / "agent_registry.schema.json"
AGENT_HANDOFF_SCHEMA = ROOT / "schemas" / "agent_handoff.schema.json"
REVIEW_EVIDENCE_PACKET_SCHEMA = (
    ROOT / "schemas" / "review_evidence_packet.schema.json"
)


@dataclass(frozen=True)
class ApplicationContainer:
    database_path: Path
    authorization_service: AuthorizationApplicationService
    opportunity_scout_service: OpportunityScoutApplicationService
    quest_candidate_service: QuestCandidateApplicationService
    quest_service: QuestApplicationService
    quest_conductor: QuestConductor | None = None


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
    audit_repository = SQLiteAuditEventRepository(factory)
    candidate_repository = SQLiteQuestCandidateRepository(factory)
    quest_repository = SQLiteQuestRepository(factory)
    handoff_repository = SQLiteAgentHandoffRepository(factory)
    review_repository = SQLiteReviewEvidencePacketRepository(factory)

    authorization_service = AuthorizationApplicationService(
        authorization_repository
    )
    candidate_service = QuestCandidateApplicationService(
        candidate_repository,
        catalog_path=WORK_SOURCE_CATALOG,
        schema_path=QUEST_CANDIDATE_SCHEMA,
        exact_revision=exact_revision,
    )
    quest_service = QuestApplicationService(
        candidate_repository,
        quest_repository,
        authorization_service,
        schema_path=QUEST_SCHEMA,
        exact_revision=exact_revision,
    )
    quest_conductor = QuestConductor(
        quest_repository,
        handoff_repository,
        review_repository,
        audit_repository,
        registry_path=AGENT_REGISTRY,
        registry_schema_path=AGENT_REGISTRY_SCHEMA,
        handoff_schema_path=AGENT_HANDOFF_SCHEMA,
        review_schema_path=REVIEW_EVIDENCE_PACKET_SCHEMA,
        exact_revision=exact_revision,
    )

    return ApplicationContainer(
        database_path=resolved_path,
        authorization_service=authorization_service,
        opportunity_scout_service=OpportunityScoutApplicationService(
            candidate_service,
            audit_repository,
            source_config_path=PHASE2_SOURCE_CONFIG,
            exact_revision=exact_revision,
        ),
        quest_candidate_service=candidate_service,
        quest_service=quest_service,
        quest_conductor=quest_conductor,
    )
