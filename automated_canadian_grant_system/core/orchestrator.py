from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from automated_canadian_grant_system.agents.agent_financial_auditor import (
    FinancialAuditor,
)
from automated_canadian_grant_system.agents.agent_red_team import (
    RedTeamVerifier,
)
from automated_canadian_grant_system.agents.agent_researcher import (
    GrantResearcher,
)
from automated_canadian_grant_system.agents.agent_rhetorical_writer import (
    RhetoricalWriter,
)
from automated_canadian_grant_system.core.constitutional_guardrails import (
    ACGSGuardrailError,
    load_business_identity,
    load_constitutional_policy,
    load_draft_payload_template,
    load_portal_catalog,
    load_prompt_module_ids,
    require_live_ingestion_blocked,
    submission_boundary,
    validate_request,
)
from automated_canadian_grant_system.core.models import GrantApplicationRequest
from automated_canadian_grant_system.core.vector_retrieval import (
    LocalGrantRetriever,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DRAFT_TEMPLATE_FILENAMES = {
    "alberta_innovates": "alberta_innovates.json",
    "nrc_irap": "nrc_irap.json",
}


class GrantOrchestrator:
    """Coordinates local draft agents while keeping all external paths blocked."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or PACKAGE_ROOT).resolve()
        config = self.project_root / "config"
        self.identity = load_business_identity(config / "business_identity.json")
        self.policy = load_constitutional_policy(
            config / "constitutional_policy.json"
        )
        self.catalog = load_portal_catalog(config / "grant_portals_config.json")
        self.prompt_module_ids = load_prompt_module_ids(
            self.project_root / "prompts" / "class_prompt_registry.json"
        )
        self.retriever = LocalGrantRetriever()
        self.researcher = GrantResearcher()
        self.writer = RhetoricalWriter()
        self.financial_auditor = FinancialAuditor()
        self.red_team = RedTeamVerifier()

    def identity_payload(self) -> dict[str, Any]:
        return self.identity.model_dump()

    def portal_payload(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog.catalog_id,
            "mode": self.catalog.mode,
            "recommended_first_portal_id": self.catalog.recommended_first_portal_id,
            "recommendation_basis": self.catalog.recommendation_basis,
            "live_ingestion_enabled": self.catalog.live_ingestion_enabled,
            "portals": [
                portal.model_dump() for portal in self.catalog.portals
            ],
            "external_action_performed": False,
        }

    def load_draft_payload(self, portal_id: str) -> dict[str, Any]:
        portal = next(
            (
                candidate
                for candidate in self.catalog.portals
                if candidate.portal_id == portal_id
            ),
            None,
        )
        if portal is None:
            raise ACGSGuardrailError("Unknown grant portal.")
        if not portal.local_draft_template_available:
            raise ACGSGuardrailError(
                "No local draft payload template is available for this portal."
            )
        filename = DRAFT_TEMPLATE_FILENAMES.get(portal_id)
        if filename is None:
            raise ACGSGuardrailError(
                "The configured local draft payload template is unavailable."
            )
        template = load_draft_payload_template(
            self.project_root / "config" / "draft_payloads" / filename
        )
        if (
            template.portal_id != portal_id
            or template.grant.portal_id != portal_id
        ):
            raise ACGSGuardrailError(
                "Local draft payload portal identity does not match its catalog entry."
            )
        if (
            template.source_attribution.official_portal_url
            != portal.official_portal_url
            or template.grant.guideline_url != portal.official_portal_url
        ):
            raise ACGSGuardrailError(
                "Local draft payload source attribution does not match its catalog entry."
            )
        return template.model_dump()

    def generate(
        self,
        request: GrantApplicationRequest,
    ) -> dict[str, Any]:
        validate_request(request, self.catalog)
        research = self.researcher.assess(
            self.identity,
            request,
            self.retriever,
        )
        draft = self.writer.draft(self.identity, request, research)
        financial = self.financial_auditor.review(request)
        audit = self.red_team.audit(
            self.identity,
            request,
            research,
            financial,
            draft,
        )
        return {
            "application_id": f"acgs_{uuid4().hex}",
            "status": "AUDITED_REVIEW_REQUIRED",
            "lifecycle": [
                "DISCOVERED",
                "REVIEW_REQUIRED",
                "DRAFTED",
                "AUDITED",
                "SUBMISSION_BLOCKED",
            ],
            "applied_prompt_modules": self.prompt_module_ids,
            "research": research,
            "draft": draft,
            "financial_review": financial,
            "red_team_audit": audit,
            "submission": submission_boundary(self.policy),
            "external_action_performed": False,
        }

    def request_live_ingestion(self, portal_id: str) -> None:
        require_live_ingestion_blocked(
            self.policy,
            self.catalog,
            portal_id,
        )
