from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from src.phase2_radar import (
    Classifier,
    OpportunityRecord,
    RadarDecision,
    RadarScorer,
)


_DOMAIN_MAP = {
    "api_documentation": "api_documentation",
    "research": "research",
    "data_analysis": "data_analysis",
    "business_operations": "business_operations",
    "prompt_engineering": "prompt_engineering",
    "writing_content": "writing_content",
    "design_ui_ux": "design_ui_ux",
    "qa_testing": "qa_testing",
    "customer_support": "customer_support",
    "cybersecurity_bug_bounty": "cybersecurity",
    "open_source_contribution": "open_source_contribution",
    "software_coding": "software_development",
}

_SKILL_GROUPS = {
    "frontend": (
        "html",
        "css",
        "javascript",
        "typescript",
        "react",
        "vue",
        "angular",
        "svelte",
        "tailwind",
        "next.js",
        "nextjs",
    ),
    "backend": (
        "python",
        "node",
        "node.js",
        "django",
        "flask",
        "fastapi",
        "express",
        "java",
        "spring",
        "ruby on rails",
        "postgresql",
        "mysql",
    ),
    "machine_learning": (
        "machine learning",
        "artificial intelligence",
        "llm",
        "gpt",
        "tensorflow",
        "pytorch",
        "scikit-learn",
        "computer vision",
        "natural language processing",
    ),
    "devops": (
        "devops",
        "docker",
        "kubernetes",
        "terraform",
        "ansible",
        "aws",
        "azure",
        "gcp",
        "ci/cd",
        "github actions",
    ),
}

_SERIOUS_RISK_FLAGS = frozenset(
    {
        "regulated_or_sensitive_domain",
        "ai_use_forbidden_or_restricted",
        "privacy_or_security_sensitive",
        "suspicious_payment_setup",
    }
)

_QUEUE_DECISIONS = frozenset(
    {
        RadarDecision.QUEUE_FOR_PHASE_3.value,
        RadarDecision.QUEUE_WITH_CAUTION.value,
    }
)


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _contains(text: str, keyword: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(keyword)}(?![A-Za-z0-9_])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


class OlogyAssessor:
    """Classify an opportunity into disciplines, skills, tools, and AI signals."""

    ASSESSOR_ID = "AIGC-OLOGY-ASSESSOR-001"
    ASSESSOR_VERSION = "1.0.0"

    def __init__(self, classifier: Classifier | None = None) -> None:
        self.classifier = classifier or Classifier()

    def assess(
        self,
        record: OpportunityRecord,
    ) -> tuple[OpportunityRecord, dict[str, Any]]:
        classified = self.classifier.classify(record)
        disciplines = sorted(set(classified.discipline_taxonomy))
        text = " ".join(
            [
                classified.title,
                classified.description_plain,
                " ".join(classified.requirements),
                " ".join(classified.responsibilities),
                " ".join(classified.deliverables),
            ]
        ).lower()

        matched_groups: dict[str, list[str]] = {}
        keyword_skills: set[str] = set()
        for group, keywords in _SKILL_GROUPS.items():
            matches = [keyword for keyword in keywords if _contains(text, keyword)]
            if matches:
                matched_groups[group] = matches
                keyword_skills.update(matches)

        detected_skills = sorted(
            {
                str(value).strip().lower()
                for value in [
                    *classified.skills_detected,
                    *keyword_skills,
                ]
                if str(value).strip()
            }
        )[:100]
        detected_tools = sorted(
            {
                str(value).strip().lower()
                for value in classified.tools_detected
                if str(value).strip()
            }
        )[:100]
        required_skills = sorted(set(detected_skills + detected_tools))[:100]
        primary_domain = self._primary_domain(
            disciplines=disciplines,
            matched_groups=matched_groups,
        )

        return classified, {
            "assessor_id": self.ASSESSOR_ID,
            "assessor_version": self.ASSESSOR_VERSION,
            "primary_domain": primary_domain,
            "discipline_taxonomy": disciplines,
            "detected_skills": detected_skills,
            "detected_tools": detected_tools,
            "required_skills": required_skills,
            "automation_signals": dict(classified.automation_signals),
            "ai_use_signals": dict(classified.ai_use_signals),
        }

    @staticmethod
    def _primary_domain(
        *,
        disciplines: list[str],
        matched_groups: Mapping[str, list[str]],
    ) -> str:
        for preferred in (
            "api_documentation",
            "cybersecurity_bug_bounty",
            "data_analysis",
            "research",
            "prompt_engineering",
            "qa_testing",
            "design_ui_ux",
        ):
            if preferred in disciplines:
                return _DOMAIN_MAP[preferred]

        if "machine_learning" in matched_groups:
            return "machine_learning"
        if "devops" in matched_groups:
            return "devops_cloud_engineering"
        if {
            "frontend",
            "backend",
        }.issubset(matched_groups):
            return "full_stack_development"
        if "frontend" in matched_groups:
            return "frontend_development"
        if "backend" in matched_groups:
            return "backend_development"

        return next(
            (
                _DOMAIN_MAP[discipline]
                for discipline in disciplines
                if discipline in _DOMAIN_MAP
            ),
            "general_remote_work",
        )


class RiskScout:
    """Score opportunity risk without confusing seniority with severe risk."""

    ASSESSOR_ID = "AIGC-RISK-SCOUT-001"
    ASSESSOR_VERSION = "1.0.0"

    def __init__(self, scorer: RadarScorer | None = None) -> None:
        self.scorer = scorer or RadarScorer()

    def assess(
        self,
        record: OpportunityRecord,
    ) -> tuple[OpportunityRecord, dict[str, Any]]:
        scored = self.scorer.score(record)
        risk_flags = sorted(set(scored.risk_flags))
        forbidden_flags = sorted(set(scored.forbidden_flags))

        if forbidden_flags:
            risk_class = "restricted"
        elif set(risk_flags).intersection(_SERIOUS_RISK_FLAGS):
            risk_class = "high"
        elif (
            risk_flags
            or scored.radar_decision
            == RadarDecision.HOLD_FOR_HUMAN_REVIEW.value
        ):
            risk_class = "medium"
        else:
            risk_class = "low"

        qualification_recommended = (
            scored.radar_decision in _QUEUE_DECISIONS
            and not forbidden_flags
            and risk_class not in {"high", "restricted"}
        )

        return scored, {
            "assessor_id": self.ASSESSOR_ID,
            "assessor_version": self.ASSESSOR_VERSION,
            "risk_class": risk_class,
            "radar_score": int(scored.radar_score),
            "radar_decision": str(scored.radar_decision),
            "risk_flags": risk_flags,
            "forbidden_flags": forbidden_flags,
            "platform_policy_status": str(scored.platform_policy_status),
            "operator_review_required": True,
            "qualification_recommended": qualification_recommended,
        }


class OpportunityAssessmentPipeline:
    """Create stable, versioned Ology and risk evidence before persistence."""

    ASSESSMENT_VERSION = "1.0.0"

    def __init__(
        self,
        *,
        ology_assessor: OlogyAssessor | None = None,
        risk_scout: RiskScout | None = None,
    ) -> None:
        self.ology_assessor = ology_assessor or OlogyAssessor()
        self.risk_scout = risk_scout or RiskScout()

    def assess(
        self,
        record: OpportunityRecord,
    ) -> tuple[OpportunityRecord, dict[str, Any]]:
        working = deepcopy(record)
        working, ology = self.ology_assessor.assess(working)
        working, risk = self.risk_scout.assess(working)

        basis = {
            "opportunity_id": working.opportunity_id,
            "source_platform": working.source_platform,
            "source_url": working.source_url,
            "title": working.title,
            "description_plain": working.description_plain,
            "ology": ology,
            "risk": risk,
        }
        basis_digest = sha256(_canonical(basis).encode("utf-8")).hexdigest()

        return working, {
            "assessment_version": self.ASSESSMENT_VERSION,
            "status": "ASSESSED",
            "basis_digest": basis_digest,
            "ology": ology,
            "risk": risk,
            "external_action_performed": False,
        }
