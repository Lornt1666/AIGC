from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from automated_canadian_grant_system.core.models import (
    BusinessIdentity,
    ConstitutionalPolicy,
    GrantApplicationRequest,
    GrantPortalCatalog,
)


REQUIRED_PROMPT_MODULE_IDS = {
    f"PR-{number:02d}-{suffix}"
    for number, suffix in (
        (1, "CONSTITUTION"),
        (2, "LINGUISTICS"),
        (3, "ORCHESTRATE"),
        (4, "RAG-MATCH"),
        (5, "CONSTRAINTS"),
        (6, "TRIZ-SOLVE"),
        (7, "VECTOR-EMBED"),
        (8, "STATE-MACHINE"),
        (9, "INFRA-GCP"),
        (10, "TEMPLATE-GEN"),
        (11, "AUTO-SCRAPE"),
        (12, "CAPABILITY"),
        (13, "RED-TEAM"),
        (14, "TELEMETRY"),
        (15, "COMPILATION"),
    )
}


class ACGSGuardrailError(ValueError):
    """Raised when a configuration or requested action violates ACGS policy."""


class LiveIngestionBlocked(ACGSGuardrailError):
    """Raised before any remote portal retrieval can be attempted."""


def load_business_identity(path: Path) -> BusinessIdentity:
    return _load_model(path, BusinessIdentity)


def load_constitutional_policy(path: Path) -> ConstitutionalPolicy:
    policy = _load_model(path, ConstitutionalPolicy)
    if policy.runtime_mode != "local_draft_only":
        raise ACGSGuardrailError("ACGS must remain in local_draft_only mode.")
    if policy.external_action_performed:
        raise ACGSGuardrailError(
            "ACGS configuration cannot claim an external action."
        )
    return policy


def load_portal_catalog(path: Path) -> GrantPortalCatalog:
    catalog = _load_model(path, GrantPortalCatalog)
    portal_ids = [portal.portal_id for portal in catalog.portals]
    if len(portal_ids) != len(set(portal_ids)):
        raise ACGSGuardrailError("Grant portal identifiers must be unique.")
    if catalog.recommended_first_portal_id not in portal_ids:
        raise ACGSGuardrailError(
            "Recommended first portal must be present in the portal catalog."
        )
    if catalog.live_ingestion_enabled or catalog.external_action_performed:
        raise ACGSGuardrailError(
            "Grant portal catalog must not enable or claim external actions."
        )
    return catalog


def load_prompt_module_ids(path: Path) -> list[str]:
    raw = _load_json_object(path)
    if raw.get("execution_mode") != "local_deterministic_draft_pipeline":
        raise ACGSGuardrailError("Prompt registry has an unsupported execution mode.")
    if raw.get("external_action_performed") is not False:
        raise ACGSGuardrailError(
            "Prompt registry cannot claim an external action."
        )
    modules = raw.get("modules")
    if not isinstance(modules, list):
        raise ACGSGuardrailError("Prompt registry requires a modules list.")
    module_ids = [
        str(item.get("module_id", ""))
        for item in modules
        if isinstance(item, dict)
    ]
    if set(module_ids) != REQUIRED_PROMPT_MODULE_IDS or len(module_ids) != 15:
        raise ACGSGuardrailError(
            "Prompt registry must contain exactly Classes 01 through 15."
        )
    return module_ids


def validate_request(
    request: GrantApplicationRequest,
    catalog: GrantPortalCatalog,
) -> None:
    if request.grant.portal_id not in {
        portal.portal_id for portal in catalog.portals
    }:
        raise ACGSGuardrailError(
            "The selected grant portal is not registered in the local catalog."
        )
    criteria = request.grant.eligibility
    if (
        criteria.min_trl is not None
        and criteria.max_trl is not None
        and criteria.min_trl > criteria.max_trl
    ):
        raise ACGSGuardrailError("Minimum TRL cannot exceed maximum TRL.")
    if (
        criteria.min_headcount is not None
        and criteria.max_headcount is not None
        and criteria.min_headcount > criteria.max_headcount
    ):
        raise ACGSGuardrailError(
            "Minimum headcount cannot exceed maximum headcount."
        )


def financial_findings(request: GrantApplicationRequest) -> list[dict[str, str]]:
    criteria = request.grant.eligibility
    project = request.project
    findings: list[dict[str, str]] = []
    if criteria.funding_ceiling_cad is None:
        findings.append(
            _finding(
                "FUNDING_CEILING_NOT_PROVIDED",
                "review_required",
                "No funding ceiling was supplied from an official guideline.",
            )
        )
    elif project.requested_funding_cad > criteria.funding_ceiling_cad:
        findings.append(
            _finding(
                "FUNDING_CEILING_EXCEEDED",
                "blocking",
                "Requested funding exceeds the supplied funding ceiling.",
            )
        )
    if criteria.required_matching_ratio is None:
        findings.append(
            _finding(
                "MATCHING_RATIO_NOT_PROVIDED",
                "review_required",
                "No matching ratio was supplied from an official guideline.",
            )
        )
    else:
        required = (
            project.requested_funding_cad * criteria.required_matching_ratio
        )
        if project.matching_contribution_cad + 1e-9 < required:
            findings.append(
                _finding(
                    "MATCHING_CONTRIBUTION_INSUFFICIENT",
                    "blocking",
                    "Applicant matching contribution is below the supplied ratio.",
                )
            )
    findings.append(
        _finding(
            "FINANCIAL_VALUES_REQUIRE_OPERATOR_VERIFICATION",
            "review_required",
            "ACGS does not verify financial figures or program rules.",
        )
    )
    return findings


def require_live_ingestion_blocked(
    policy: ConstitutionalPolicy,
    catalog: GrantPortalCatalog,
    portal_id: str,
) -> None:
    if portal_id not in {portal.portal_id for portal in catalog.portals}:
        raise ACGSGuardrailError("Unknown grant portal.")
    if (
        policy.external_actions.live_portal_ingestion_enabled
        or catalog.live_ingestion_enabled
    ):
        raise ACGSGuardrailError(
            "Live portal ingestion must remain disabled in this baseline."
        )
    raise LiveIngestionBlocked(
        "Live portal ingestion is blocked pending source review, connector review, "
        "and scoped Phase 5 approval. No network request was made."
    )


def submission_boundary(policy: ConstitutionalPolicy) -> dict[str, Any]:
    if policy.external_actions.external_submission_enabled:
        raise ACGSGuardrailError(
            "External submission must remain disabled in this baseline."
        )
    return {
        "status": "BLOCKED_PENDING_PHASE5_APPROVAL",
        "reason_codes": [
            "PHASE5_APPROVAL_REQUIRED",
            "EXACT_PAYLOAD_OPERATOR_REVIEW_REQUIRED",
            "NO_LIVE_SUBMISSION_CONNECTOR",
            "MANUAL_HANDOFF_ONLY",
        ],
        "phase5_approval_required": True,
        "operator_exact_payload_review_required": True,
        "manual_handoff_only": True,
        "external_submission_performed": False,
        "credential_use_performed": False,
    }


def _load_model(path: Path, model_type: type[Any]) -> Any:
    try:
        return model_type.model_validate(_load_json_object(path))
    except (OSError, ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise ACGSGuardrailError(
            f"Unable to validate required ACGS configuration: {path.name}"
        ) from exc


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ACGSGuardrailError(
            f"Unable to read required ACGS configuration: {path.name}"
        ) from exc
    if not isinstance(value, dict):
        raise ACGSGuardrailError(
            f"Required ACGS configuration must be an object: {path.name}"
        )
    return value


def _finding(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}
