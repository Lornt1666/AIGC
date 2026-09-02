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
    validate_operator_review,
    validate_request,
)
from automated_canadian_grant_system.core.models import (
    GrantApplicationRequest,
    OperatorReviewRequest,
)
from automated_canadian_grant_system.core.vector_retrieval import (
    LocalGrantRetriever,
)
from automated_canadian_grant_system.database.storage import (
    LocalGrantApplicationStore,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DRAFT_TEMPLATE_FILENAMES = {
    "alberta_innovates": "alberta_innovates.json",
    "nrc_irap": "nrc_irap.json",
}


class GrantOrchestrator:
    """Coordinates local draft agents while keeping all external paths blocked."""

    def __init__(
        self,
        project_root: Path | None = None,
        database_path: Path | None = None,
    ) -> None:
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
        self.store = LocalGrantApplicationStore(
            database_path
            or self.project_root / "database" / "acgs_local.sqlite3"
        )

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
        portal = next(
            portal
            for portal in self.catalog.portals
            if portal.portal_id == request.grant.portal_id
        )
        package = {
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
            "source_attribution": {
                "portal_id": portal.portal_id,
                "portal_organization": portal.organization,
                "official_portal_url": portal.official_portal_url,
                "provided_guideline_url": request.grant.guideline_url,
                "source_verification_status": (
                    request.grant.eligibility.source_verification_status
                ),
                "source_fetched_by_acgs": False,
                "current_program_confirmation_required": True,
            },
            "ai_use_disclosure": draft["ai_use_disclosure"],
            "submission": submission_boundary(self.policy),
            "external_action_performed": False,
        }
        record = self.store.create_application(package)
        return {
            **package,
            "persistence": self._record_summary(record),
        }

    def get_application(self, application_id: str) -> dict[str, Any]:
        return self.store.get_application(application_id)

    def review_application(
        self,
        application_id: str,
        review: OperatorReviewRequest,
    ) -> dict[str, Any]:
        record = self.store.get_application(application_id)
        reviewed_financial_findings = validate_operator_review(
            self.policy,
            self.catalog,
            record["package"],
            review,
        )
        return self.store.record_operator_review(
            application_id,
            expected_revision=review.expected_revision,
            review=review.model_dump(mode="json"),
            reviewed_financial_findings=reviewed_financial_findings,
        )

    def local_export(self, application_id: str) -> dict[str, Any]:
        return self.store.local_export(application_id)

    def request_live_ingestion(self, portal_id: str) -> None:
        require_live_ingestion_blocked(
            self.policy,
            self.catalog,
            portal_id,
        )

    @staticmethod
    def _record_summary(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "application_id": record["application_id"],
            "lifecycle_state": record["lifecycle_state"],
            "revision": record["revision"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "external_submission_performed": (
                record["external_submission_performed"]
            ),
            "external_action_performed": False,
        }
