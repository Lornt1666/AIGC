from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from automated_canadian_grant_system.core.models import (
    BusinessIdentity,
    ConstitutionalPolicy,
    GrantApplicationRequest,
    GrantCriteriaFields,
    GrantDraftPayloadTemplate,
    GrantPortalCatalog,
    OperatorReviewRequest,
)
from src.security.redactor import Redactor


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


def load_draft_payload_template(path: Path) -> GrantDraftPayloadTemplate:
    return _load_model(path, GrantDraftPayloadTemplate)


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
    portal = _portal_for_id(catalog, request.grant.portal_id)
    if portal is None:
        raise ACGSGuardrailError(
            "The selected grant portal is not registered in the local catalog."
        )
    _validate_portal_url(
        request.grant.guideline_url,
        portal.official_portal_url,
        "Grant guideline URL",
    )
    _reject_secret_like_text(
        "grant and project input",
        [
            request.grant.grant_name,
            request.grant.summary,
            request.project.project_title,
            request.project.project_summary,
            *request.project.evidence_references,
        ],
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


def financial_findings(
    request: GrantApplicationRequest,
    criteria: GrantCriteriaFields | None = None,
) -> list[dict[str, str]]:
    return financial_findings_for_values(
        request.project.requested_funding_cad,
        request.project.matching_contribution_cad,
        criteria or request.grant.eligibility,
    )


def financial_findings_for_values(
    requested_funding_cad: float,
    matching_contribution_cad: float,
    criteria: GrantCriteriaFields,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if criteria.funding_ceiling_cad is None:
        findings.append(
            _finding(
                "FUNDING_CEILING_NOT_PROVIDED",
                "review_required",
                "No funding ceiling was supplied from an official guideline.",
            )
        )
    elif requested_funding_cad > criteria.funding_ceiling_cad:
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
        required = requested_funding_cad * criteria.required_matching_ratio
        if matching_contribution_cad + 1e-9 < required:
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


def validate_operator_review(
    policy: ConstitutionalPolicy,
    catalog: GrantPortalCatalog,
    package: dict[str, Any],
    review: OperatorReviewRequest,
    *,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    source = package.get("source_attribution")
    financial = package.get("financial_review")
    draft = package.get("draft")
    audit = package.get("red_team_audit")
    if not isinstance(source, dict) or not isinstance(financial, dict):
        raise ACGSGuardrailError(
            "Persisted application package is missing source or financial data."
        )
    if not isinstance(draft, dict) or not isinstance(audit, dict):
        raise ACGSGuardrailError(
            "Persisted application package is missing required review artifacts."
        )
    criteria = review.operator_attested_criteria
    if (
        criteria.min_trl is not None
        and criteria.max_trl is not None
        and criteria.min_trl > criteria.max_trl
    ):
        raise ACGSGuardrailError("Reviewed minimum TRL cannot exceed maximum TRL.")
    if (
        criteria.min_headcount is not None
        and criteria.max_headcount is not None
        and criteria.min_headcount > criteria.max_headcount
    ):
        raise ACGSGuardrailError(
            "Reviewed minimum headcount cannot exceed maximum headcount."
        )
    portal_id = str(source.get("portal_id", ""))
    portal = _portal_for_id(catalog, portal_id)
    if portal is None:
        raise ACGSGuardrailError(
            "Persisted application package references an unknown grant portal."
        )
    _validate_portal_url(
        review.source_guideline_url,
        portal.official_portal_url,
        "Reviewed source guideline URL",
    )
    _reject_secret_like_text(
        "operator review",
        [
            review.program_name,
            review.source_version,
            review.operator_attested_criteria.eligibility_criteria_summary,
            review.operator_attested_criteria.financial_criteria_summary,
            review.review_notes,
            *review.source_evidence_references,
            *review.budget_evidence_references,
        ],
    )
    current_date = (now or datetime.now(timezone.utc)).date()
    if review.source_reviewed_at > current_date:
        raise ACGSGuardrailError(
            "Reviewed source date cannot be in the future."
        )
    age_days = (current_date - review.source_reviewed_at).days
    if age_days > policy.truthfulness.source_review_max_age_days:
        raise ACGSGuardrailError(
            "Reviewed source is stale and must be reviewed again before local export."
        )
    _validate_evidence_references(
        review.source_evidence_references,
        "source evidence reference",
    )
    _validate_evidence_references(
        review.budget_evidence_references,
        "budget evidence reference",
    )
    if review.source_guideline_url not in review.source_evidence_references:
        raise ACGSGuardrailError(
            "Source evidence must include the reviewed source guideline URL."
        )
    if not str(draft.get("ai_use_disclosure", "")).strip():
        raise ACGSGuardrailError(
            "Local export requires the AI-use disclosure in the draft package."
        )

    reviewed_findings = financial_findings_for_values(
        float(financial.get("requested_funding_cad", 0)),
        float(financial.get("matching_contribution_cad", 0)),
        criteria,
    )
    if review.decision == "approve_local_export":
        _validate_local_export_approval(package, reviewed_findings)
    return reviewed_findings


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


def _validate_local_export_approval(
    package: dict[str, Any],
    reviewed_financial_findings: list[dict[str, str]],
) -> None:
    research = package.get("research")
    if isinstance(research, dict) and (
        research.get("eligibility_determination")
        == "INELIGIBLE_BY_SUPPLIED_CRITERIA"
    ):
        raise ACGSGuardrailError(
            "Local export cannot be approved while supplied eligibility criteria mismatch."
        )
    red_team = package.get("red_team_audit")
    if isinstance(red_team, dict):
        unsupported_claims = [
            str(finding.get("code", ""))
            for finding in red_team.get("findings", [])
            if isinstance(finding, dict)
            and str(finding.get("code", "")).startswith("UNSUPPORTED_")
        ]
        if unsupported_claims:
            raise ACGSGuardrailError(
                "Local export cannot be approved with unsupported claims: "
                + ", ".join(sorted(unsupported_claims))
            )
    blockers = [
        str(finding.get("code", ""))
        for finding in reviewed_financial_findings
        if finding.get("severity") == "blocking"
    ]
    if blockers:
        raise ACGSGuardrailError(
            "Local export cannot be approved with blocking financial findings: "
            + ", ".join(sorted(blockers))
        )


def _portal_for_id(
    catalog: GrantPortalCatalog,
    portal_id: str,
) -> Any | None:
    return next(
        (
            portal
            for portal in catalog.portals
            if portal.portal_id == portal_id
        ),
        None,
    )


def _validate_portal_url(
    value: str,
    official_portal_url: str,
    label: str,
) -> None:
    parsed = _parse_safe_https_url(value, label)
    expected = _parse_safe_https_url(official_portal_url, "Catalog portal URL")
    if parsed.netloc.lower() != expected.netloc.lower():
        raise ACGSGuardrailError(
            f"{label} must use the registered official portal host."
        )


def _validate_evidence_references(
    references: list[str],
    label: str,
) -> None:
    for reference in references:
        _reject_secret_like_text(label, [reference])
        if reference.startswith("https://"):
            _parse_safe_https_url(reference, label)
        elif reference.startswith("operator-record://"):
            identifier = reference.removeprefix("operator-record://")
            if not re.fullmatch(r"[A-Za-z0-9._/-]{1,300}", identifier):
                raise ACGSGuardrailError(
                    f"{label} has an invalid operator-record identifier."
                )
        elif not re.fullmatch(r"sha256:[a-f0-9]{64}", reference):
            raise ACGSGuardrailError(
                f"{label} must be an HTTPS URL, operator-record reference, or SHA-256 digest."
            )


def _parse_safe_https_url(value: str, label: str) -> Any:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
    ):
        raise ACGSGuardrailError(
            f"{label} must be an HTTPS URL without credentials or query parameters."
        )
    return parsed


def _reject_secret_like_text(label: str, values: list[str]) -> None:
    scanner = Redactor()
    if any(scanner.scan_for_secret_like_content(value) for value in values):
        raise ACGSGuardrailError(
            f"{label} contains secret-like material and cannot be stored."
        )


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
