from __future__ import annotations

import json
from pathlib import Path

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.research import DeepResearchPolicy, ResearchProcurementRequest
from src.security.redactor import Redactor


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config" / "aigc_deep_research_policy.v1.json"


def load_deep_research_policy(
    path: Path = DEFAULT_POLICY_PATH,
) -> DeepResearchPolicy:
    return DeepResearchPolicy.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _reject_secret_material(request: ResearchProcurementRequest) -> None:
    redactor = Redactor()
    for value in (request.question, request.intended_decision, *request.jurisdictions):
        if redactor.redact_text(value) != value:
            raise ValueError("research request contains credential-like material")


def build_deep_research_plan(
    request: ResearchProcurementRequest,
    *,
    policy: DeepResearchPolicy | None = None,
) -> dict[str, object]:
    """Build a deterministic procurement plan without retrieving data or calling a provider."""

    _reject_secret_material(request)
    active_policy = policy or load_deep_research_policy()
    request_payload = request.model_dump(mode="json")
    request_digest = canonical_sha256(request_payload)
    stages: list[dict[str, str]] = []
    for index, stage in enumerate(active_policy.stages):
        if index == 0:
            status = "READY_LOCAL"
            blocker = "NONE"
        elif index == 1:
            status = "BLOCKED_EXTERNAL"
            blocker = "APPROVED_SOURCE_RETRIEVAL_OR_PROVIDER_PERMIT"
        else:
            status = "WAITING_ON_PRIOR_STAGE"
            blocker = "SOURCE_EVIDENCE_NOT_RETRIEVED"
        stages.append({"stage": stage, "status": status, "first_blocker": blocker})

    return {
        "plan_id": "RPLAN-" + request_digest[:24].upper(),
        "request_id": request.request_id,
        "request_sha256": request_digest,
        "question": request.question,
        "intended_decision": request.intended_decision,
        "jurisdictions": list(request.jurisdictions),
        "maximum_sources": request.maximum_sources,
        "maximum_spend_cad": format(request.maximum_spend_cad, ".2f"),
        "stages": stages,
        "source_strategy": [item.model_dump(mode="json") for item in active_policy.source_ladder],
        "planned_queries": [
            request.question,
            f"{request.question} official primary source",
            f"evidence against: {request.question}",
        ],
        "quality_gates": {
            "minimum_primary_sources": active_policy.minimum_primary_sources,
            "minimum_independent_domains": active_policy.minimum_independent_domains,
            "material_claim_citation_coverage_minimum": active_policy.material_claim_citation_coverage_minimum,
            "unsupported_material_claims_maximum": active_policy.unsupported_material_claims_maximum,
            "unresolved_material_conflicts_maximum": active_policy.unresolved_material_conflicts_maximum,
            "disconfirming_search_required": active_policy.require_disconfirming_search,
            "prompt_injection_screening_required": active_policy.require_prompt_injection_screening,
            "source_provenance_required": active_policy.require_source_provenance,
        },
        "provider_contracts": [
            item.model_dump(mode="json") for item in active_policy.provider_contracts
        ],
        "provider_dispatch_enabled": False,
        "provider_call_count": 0,
        "credentials_accessed": False,
        "authority_granted": False,
        "external_action_performed": False,
        "external_publication_performed": False,
        "first_blocker": "APPROVED_SOURCE_RETRIEVAL_OR_PROVIDER_PERMIT",
        "final_status": "BLOCKED_BEFORE_SOURCE_RETRIEVAL",
    }
