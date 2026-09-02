from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.core.phase2_to5_cycle_policy import require_phase2_to5_generation_authorized


class Phase3Decision(str, Enum):
    PROCEED_TO_PHASE_4 = "proceed_to_phase_4"
    PROCEED_WITH_CAUTION = "proceed_to_phase_4_with_caution"
    HOLD_FOR_HUMAN_REVIEW = "hold_for_human_review"
    WEAK_HOLD = "weak_hold"
    REJECT = "reject"


@dataclass
class OlogyAssessment:
    name: str
    question: str
    summary: str
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    required_checks: List[str] = field(default_factory=list)
    score: int = 0


@dataclass
class MasterAssessment:
    confidence: int
    legal_platform_alignment: int
    suitability: int
    feasibility: int
    pay_reward_potential: int
    effort_efficiency: int
    impact_value: int
    deliverable_clarity: int
    privacy_security_safety: int
    ethical_professional_quality: int
    reputation_safety: int
    automation_compatibility: int
    human_approval_clarity: int
    employer_acceptance_likelihood: int
    auditability: int

    def total(self) -> int:
        return sum(asdict(self).values())

    def normalized(self) -> int:
        return round((self.total() / 150) * 100)

    def decision(self) -> Phase3Decision:
        score = self.normalized()
        if score >= 90:
            return Phase3Decision.PROCEED_TO_PHASE_4
        if score >= 80:
            return Phase3Decision.PROCEED_WITH_CAUTION
        if score >= 70:
            return Phase3Decision.HOLD_FOR_HUMAN_REVIEW
        if score >= 60:
            return Phase3Decision.WEAK_HOLD
        return Phase3Decision.REJECT


@dataclass
class OpportunityAssessmentDossier:
    dossier_id: str
    opportunity_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    radar_score: int
    discovered_taxonomy: List[str]
    methodology: OlogyAssessment
    taxonomy: OlogyAssessment
    ontology: OlogyAssessment
    epistemology: OlogyAssessment
    teleology: OlogyAssessment
    axiology: OlogyAssessment
    praxeology: OlogyAssessment
    heuristics: OlogyAssessment
    meta_ontology: OlogyAssessment
    master_assessment: MasterAssessment
    phase3_assessment_score: int
    final_decision: str
    recommended_agents: List[str]
    autonomous_next_actions: List[str]
    approval_required_future_actions: List[str]
    forbidden_actions: List[str]
    primary_value: str
    primary_risk: str
    recommended_next_step: str
    created_at: str


class Phase3AuditLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, data: Dict[str, Any]) -> None:
        event = {
            "timestamp": utc_now(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


class Phase3Text:
    @staticmethod
    def lower_join(record: Dict[str, Any]) -> str:
        parts = [
            str(record.get("title", "")),
            str(record.get("description_plain", "")),
            " ".join(record.get("requirements", []) or []),
            " ".join(record.get("responsibilities", []) or []),
            " ".join(record.get("deliverables", []) or []),
            " ".join(record.get("skills_detected", []) or []),
            " ".join(record.get("tools_detected", []) or []),
            " ".join(record.get("discipline_taxonomy", []) or []),
        ]
        return " ".join(parts).lower()

    @staticmethod
    def has_any(text: str, terms: Iterable[str]) -> bool:
        return any(term in text for term in terms)


class OlogyEngine:
    PREFERRED_TAXONOMY = {
        "software_coding",
        "api_documentation",
        "research",
        "data_analysis",
        "writing_content",
        "qa_testing",
        "business_operations",
        "prompt_engineering",
        "open_source_contribution",
    }

    AGENTS_BY_TAXONOMY = {
        "software_coding": [
            "Trans-Architectural Agent",
            "Neo-Algorithmic Agent",
            "Hyper-Optimization Agent",
            "Ultra-Robust Agent",
            "Ultra-Audit Agent",
        ],
        "automation_scripting": [
            "Trans-Architectural Agent",
            "Neo-Algorithmic Agent",
            "Hyper-Optimization Agent",
            "Ultra-Robust Agent",
            "Ultra-Aligned Agent",
        ],
        "api_documentation": [
            "Trans-Lingual Agent",
            "Trans-Modal Agent",
            "Omni-Generative Agent",
            "Hyper-Coherence Agent",
            "Ultra-Audit Agent",
        ],
        "research": [
            "Omni-Research Agent",
            "Epistemology Checker",
            "Meta-Semantic Agent",
            "Hyper-Synthetic Agent",
            "Ultra-Audit Agent",
        ],
        "data_analysis": [
            "Omni-Contextual Agent",
            "Neo-Algorithmic Agent",
            "Hyper-Synthetic Agent",
            "Ultra-Audit Agent",
        ],
        "business_operations": [
            "Omni-Contextual Agent",
            "Omni-Research Agent",
            "Para-Logical Agent",
            "Hyper-Synthetic Agent",
            "Ultra-Audit Agent",
        ],
        "writing_content": [
            "Trans-Lingual Agent",
            "Meta-Semantic Agent",
            "Hyper-Coherence Agent",
            "Ultra-Audit Agent",
        ],
        "open_source_contribution": [
            "Trans-Architectural Agent",
            "Neo-Algorithmic Agent",
            "Ultra-Robust Agent",
            "Ultra-Audit Agent",
        ],
    }

    def assess(self, record: Dict[str, Any]) -> OpportunityAssessmentDossier:
        text = Phase3Text.lower_join(record)
        methodology = self._assess_methodology(record, text)
        taxonomy = self._assess_taxonomy(record, text)
        ontology = self._assess_ontology(record, text)
        epistemology = self._assess_epistemology(record, text)
        teleology = self._assess_teleology(record, text)
        axiology = self._assess_axiology(record, text)
        praxeology = self._assess_praxeology(record, text)
        heuristics = self._assess_heuristics(record, text)
        meta_ontology = self._assess_meta_ontology(
            methodology,
            taxonomy,
            ontology,
            epistemology,
            teleology,
            axiology,
            praxeology,
            heuristics,
        )
        master = self._master_score(
            record,
            text,
            [
                methodology,
                taxonomy,
                ontology,
                epistemology,
                teleology,
                axiology,
                praxeology,
                heuristics,
                meta_ontology,
            ],
        )
        final_decision = self._cap_decision_by_phase2(record, master.decision().value)
        return OpportunityAssessmentDossier(
            dossier_id=self._make_dossier_id(record),
            opportunity_id=record.get("opportunity_id", ""),
            title=record.get("title", ""),
            employer=record.get("employer", "") or record.get("client", ""),
            source_platform=record.get("source_platform", ""),
            source_url=record.get("source_url", ""),
            radar_score=int(record.get("radar_score", 0) or 0),
            discovered_taxonomy=record.get("discipline_taxonomy", []) or [],
            methodology=methodology,
            taxonomy=taxonomy,
            ontology=ontology,
            epistemology=epistemology,
            teleology=teleology,
            axiology=axiology,
            praxeology=praxeology,
            heuristics=heuristics,
            meta_ontology=meta_ontology,
            master_assessment=master,
            phase3_assessment_score=master.normalized(),
            final_decision=final_decision,
            recommended_agents=self._recommend_agents(record, text),
            autonomous_next_actions=self._autonomous_next_actions(final_decision),
            approval_required_future_actions=[
                "message_employer",
                "apply",
                "submit_proposal",
                "submit_deliverable",
                "use_operator_identity",
                "use_credentials",
            ],
            forbidden_actions=[
                "spam",
                "impersonation",
                "fake_qualifications",
                "forbidden_scraping",
                "hidden_ai_use_where_disclosure_required",
                "bypass_platform_limits",
            ],
            primary_value=self._primary_value(record, text),
            primary_risk=self._primary_risk(record, text),
            recommended_next_step=self._recommended_next_step(final_decision),
            created_at=utc_now(),
        )

    def _make_dossier_id(self, record: Dict[str, Any]) -> str:
        raw = "|".join(
            [
                record.get("opportunity_id", ""),
                record.get("title", ""),
                record.get("employer", ""),
                record.get("source_url", ""),
            ]
        )
        return "phase3_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _assess_methodology(self, record: Dict[str, Any], text: str) -> OlogyAssessment:
        strengths: List[str] = []
        weaknesses: List[str] = []
        required_checks: List[str] = []
        if Phase3Text.has_any(text, ["api", "documentation", "report", "analysis", "python", "data", "readme"]):
            strengths.append("Work appears compatible with a structured AI-assisted method.")
        if record.get("description_plain"):
            strengths.append("Source description exists for planning and review.")
        else:
            weaknesses.append("Description is missing or weak.")
            required_checks.append("Verify original listing before proposal drafting.")
        if not record.get("deliverables") and not record.get("automation_signals", {}).get("clear_deliverable"):
            weaknesses.append("Deliverables are not explicit enough.")
            required_checks.append("Clarify the expected deliverable before Phase 4.")
        score = clamp(80 + len(strengths) * 5 - len(weaknesses) * 10)
        return OlogyAssessment(
            name="Methodology",
            question="How should this work be done?",
            summary="Recommended method: inspect the listing, clarify the deliverable, prepare an internal plan, and require human review before external action.",
            strengths=strengths,
            weaknesses=weaknesses,
            required_checks=required_checks,
            score=score,
        )

    def _assess_taxonomy(self, record: Dict[str, Any], text: str) -> OlogyAssessment:
        taxonomy = record.get("discipline_taxonomy", []) or []
        strengths: List[str] = []
        weaknesses: List[str] = []
        if taxonomy:
            strengths.append(f"Detected taxonomy: {', '.join(taxonomy)}.")
        else:
            weaknesses.append("No clear work taxonomy was detected.")
        if self.PREFERRED_TAXONOMY.intersection(set(taxonomy)):
            strengths.append("Opportunity matches AIGC-preferred work categories.")
        automation_level = self._automation_level(record)
        summary = (
            f"Primary category: {taxonomy[0] if taxonomy else 'unknown'}. "
            f"Complexity: {self._complexity(text)}. "
            f"Deliverable type: {self._deliverable_type(record, text)}. "
            f"Automation compatibility: {automation_level}."
        )
        score = clamp(70 + len(strengths) * 10 - len(weaknesses) * 15)
        return OlogyAssessment(
            name="Taxonomy",
            question="What kind of work is this?",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            score=score,
        )

    def _assess_ontology(self, record: Dict[str, Any], text: str) -> OlogyAssessment:
        strengths: List[str] = []
        weaknesses: List[str] = []
        unknowns: List[str] = []
        employer = record.get("employer") or record.get("client")
        if employer:
            strengths.append("Employer/client entity is identified.")
        else:
            unknowns.append("Employer/client entity is unclear.")
        if record.get("source_url"):
            strengths.append("Source URL exists for traceability.")
        else:
            weaknesses.append("No source URL is available.")
        if record.get("title"):
            strengths.append("Work object/title is identified.")
        if not record.get("deliverables"):
            unknowns.append("Deliverable relationship needs clarification.")
        summary = (
            f"Entity map: {employer or 'unknown requester'} needs "
            f"{self._deliverable_type(record, text)} using methods inferred from source data; "
            "AIGC may assess internally, but only Justice can approve external action."
        )
        score = clamp(75 + len(strengths) * 5 - len(weaknesses) * 10 - len(unknowns) * 5)
        return OlogyAssessment(
            name="Ontology",
            question="What entities and relationships exist?",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            unknowns=unknowns,
            score=score,
        )

    def _assess_epistemology(self, record: Dict[str, Any], text: str) -> OlogyAssessment:
        strengths: List[str] = []
        weaknesses: List[str] = []
        unknowns: List[str] = []
        required_checks: List[str] = []
        if record.get("source_platform") and record.get("source_url"):
            strengths.append("Traceable source platform and URL exist.")
        if record.get("platform_policy_status") in {"green", "yellow"}:
            strengths.append("Source was classified as usable for read-only discovery.")
        else:
            weaknesses.append("Platform policy status is not clearly favorable.")
        if record.get("ai_use_signals", {}).get("ai_unclear", True):
            unknowns.append("AI-use permission is unclear.")
            required_checks.append("Check listing, employer, and platform instructions before proposal or execution.")
        if record.get("risk_flags"):
            required_checks.append("Review risk flags before moving into Phase 4.")
        summary = "Known facts come from the source listing and Phase 2 extraction. Unknowns must not be filled by assumption."
        score = clamp(85 + len(strengths) * 3 - len(weaknesses) * 15 - len(unknowns) * 8)
        return OlogyAssessment(
            name="Epistemology",
            question="How do we know what is true?",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            unknowns=unknowns,
            required_checks=required_checks,
            score=score,
        )

    def _assess_teleology(self, record: Dict[str, Any], text: str) -> OlogyAssessment:
        strengths: List[str] = []
        weaknesses: List[str] = []
        if Phase3Text.has_any(text, ["improve", "build", "analyze", "document", "automate", "research", "create"]):
            strengths.append("Purpose can be inferred from task/action language.")
        if record.get("pay_min") or record.get("pay_max") or record.get("pay_currency"):
            strengths.append("Reward/payment signal exists.")
        else:
            weaknesses.append("Payment/reward is not clearly visible.")
        if Phase3Text.has_any(text, ["report", "dashboard", "script", "documentation", "summary", "prototype", "readme"]):
            strengths.append("Likely success condition is deliverable-based.")
        summary = (
            "Purpose: satisfy the requester with a concrete deliverable while preserving auditability, "
            "transparent AI use where needed, and operator approval gates."
        )
        score = clamp(75 + len(strengths) * 7 - len(weaknesses) * 10)
        return OlogyAssessment(
            name="Teleology",
            question="What purpose or end-goal does this work serve?",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            score=score,
        )

    def _assess_axiology(self, record: Dict[str, Any], text: str) -> OlogyAssessment:
        strengths: List[str] = []
        weaknesses: List[str] = []
        required_checks: List[str] = []
        forbidden_flags = record.get("forbidden_flags", []) or []
        risk_flags = record.get("risk_flags", []) or []
        if not forbidden_flags:
            strengths.append("No explicit forbidden flags detected.")
        else:
            weaknesses.append(f"Forbidden flags detected: {', '.join(forbidden_flags)}.")
        if "regulated_or_sensitive_domain" in risk_flags:
            weaknesses.append("Opportunity may involve a regulated or sensitive domain.")
            required_checks.append("Require specialized review before proceeding.")
        if "privacy_or_security_sensitive" in risk_flags:
            weaknesses.append("Opportunity may involve privacy/security-sensitive data.")
            required_checks.append("Review data handling requirements before proposal drafting.")
        if record.get("ai_use_signals", {}).get("ai_forbidden_explicit", False):
            weaknesses.append("AI use appears forbidden or restricted.")
            required_checks.append("Do not use AI assistance unless clarified and permitted.")
        summary = "Ethical status depends on transparent approval gates, no deception, no spam, and no hidden AI use where disclosure is required."
        score = clamp(90 + len(strengths) * 2 - len(weaknesses) * 25)
        return OlogyAssessment(
            name="Axiology",
            question="Is this valuable, ethical, and professionally worthwhile?",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            required_checks=required_checks,
            score=score,
        )

    def _assess_praxeology(self, record: Dict[str, Any], text: str) -> OlogyAssessment:
        strengths = ["Internal assessment can proceed without external action."]
        weaknesses: List[str] = []
        required_checks = [
            "Proposal drafting must remain internal in Phase 4.",
            "External outreach requires Justice approval.",
            "Submission requires Justice approval.",
            "Employer delivery requires Justice approval.",
        ]
        if not record.get("source_url"):
            weaknesses.append("Source URL missing; action path is incomplete.")
        if record.get("forbidden_flags"):
            weaknesses.append("Forbidden flags block the action path.")
        summary = (
            "Action sequence: assess internally, prepare review material if justified, stop before any employer/platform interaction, "
            "then wait for explicit approval."
        )
        score = clamp(85 + len(strengths) * 3 - len(weaknesses) * 30)
        return OlogyAssessment(
            name="Praxeology",
            question="What actions must be taken?",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            required_checks=required_checks,
            score=score,
        )

    def _assess_heuristics(self, record: Dict[str, Any], text: str) -> OlogyAssessment:
        strengths: List[str] = []
        weaknesses: List[str] = []
        if int(record.get("radar_score", 0) or 0) >= 85:
            strengths.append("High radar score from Phase 2.")
        if Phase3Text.has_any(text, ["remote", "documentation", "api", "research", "python", "data", "analysis", "readme"]):
            strengths.append("Matches AIGC preferred heuristic profile.")
        if not (record.get("pay_min") or record.get("pay_max") or record.get("pay_currency")):
            weaknesses.append("Pay is unclear.")
        if record.get("forbidden_flags"):
            weaknesses.append("Forbidden flags override positive heuristics.")
        fast_decision = "Proceed" if len(strengths) > len(weaknesses) and not record.get("forbidden_flags") else "Caution"
        summary = f"Fast decision: {fast_decision}. Positive and negative heuristics are weighted before Phase 4."
        score = clamp(75 + len(strengths) * 10 - len(weaknesses) * 12)
        return OlogyAssessment(
            name="Heuristics",
            question="What practical rules guide fast judgment?",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            score=score,
        )

    def _assess_meta_ontology(self, *assessments: OlogyAssessment) -> OlogyAssessment:
        scores = [item.score for item in assessments]
        avg = round(sum(scores) / len(scores)) if scores else 0
        weak_layers = [item.name for item in assessments if item.score < 70]
        strengths = ["All ology layers produced an internal-only judgment artifact."]
        weaknesses = [f"Weak layers: {', '.join(weak_layers)}."] if weak_layers else []
        summary = (
            "Unified interpretation: opportunity may advance only if source facts, deliverable clarity, "
            "risk status, and approval gates remain coherent."
        )
        return OlogyAssessment(
            name="Meta-Ontology",
            question="How do all reasoning systems connect into one judgment?",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            score=clamp(avg),
        )

    def _master_score(
        self,
        record: Dict[str, Any],
        text: str,
        ologies: List[OlogyAssessment],
    ) -> MasterAssessment:
        taxonomy = set(record.get("discipline_taxonomy", []) or [])
        risk_flags = set(record.get("risk_flags", []) or [])
        forbidden_flags = set(record.get("forbidden_flags", []) or [])
        automation_true_count = sum(1 for value in (record.get("automation_signals", {}) or {}).values() if value)
        ology_avg = round(sum(item.score for item in ologies) / len(ologies)) if ologies else 0
        clarity = 10 if record.get("description_plain") and record.get("title") else 6 if record.get("title") else 3
        deliverable = 10 if record.get("automation_signals", {}).get("clear_deliverable") else 6 if record.get("deliverables") else 4
        legal_alignment = 10 if record.get("platform_policy_status") == "green" else 8 if record.get("platform_policy_status") == "yellow" else 3
        if forbidden_flags:
            legal_alignment = 0
        privacy = 10
        if "privacy_or_security_sensitive" in risk_flags:
            privacy = 4
        if "regulated_or_sensitive_domain" in risk_flags:
            privacy = min(privacy, 5)
        ethical = 10 if not forbidden_flags else 0
        if record.get("ai_use_signals", {}).get("ai_forbidden_explicit", False):
            ethical = min(ethical, 4)
        return MasterAssessment(
            confidence=scale_100_to_10(ology_avg),
            legal_platform_alignment=legal_alignment,
            suitability=10 if self.PREFERRED_TAXONOMY.intersection(taxonomy) else 5,
            feasibility=min(10, max(4, clarity + (1 if automation_true_count else 0))),
            pay_reward_potential=10 if record.get("pay_min") or record.get("pay_max") else 5,
            effort_efficiency=9 if automation_true_count >= 4 else 7 if automation_true_count >= 2 else 5,
            impact_value=8 if Phase3Text.has_any(text, ["build", "improve", "document", "research", "analyze", "automate"]) else 5,
            deliverable_clarity=deliverable,
            privacy_security_safety=privacy,
            ethical_professional_quality=ethical,
            reputation_safety=10 if not risk_flags and not forbidden_flags else 7 if not forbidden_flags else 0,
            automation_compatibility=min(10, 3 + automation_true_count),
            human_approval_clarity=10 if record.get("approval_required_before") else 6,
            employer_acceptance_likelihood=min(10, max(4, round((clarity + deliverable + legal_alignment) / 3))),
            auditability=10 if record.get("source_url") and record.get("source_platform") else 5,
        )

    def _recommend_agents(self, record: Dict[str, Any], text: str) -> List[str]:
        taxonomy = record.get("discipline_taxonomy", []) or []
        agents: List[str] = ["Meta-Coordinational Agent", "Ultra-Aligned Agent", "Ultra-Audit Agent"]
        if "automation" in text or "script" in text:
            taxonomy = list(taxonomy) + ["automation_scripting"]
        for label in taxonomy:
            for agent in self.AGENTS_BY_TAXONOMY.get(label, []):
                if agent not in agents:
                    agents.append(agent)
        return agents

    def _primary_value(self, record: Dict[str, Any], text: str) -> str:
        if record.get("work_type") == "open_source":
            return "Open-source contribution value with portfolio and learning potential."
        if Phase3Text.has_any(text, ["documentation", "docs", "readme"]):
            return "Documentation clarity and developer enablement."
        if Phase3Text.has_any(text, ["research", "analysis", "market"]):
            return "Research synthesis and decision support."
        if Phase3Text.has_any(text, ["automation", "script", "workflow"]):
            return "Workflow automation and repeatable process value."
        return "General opportunity value pending clearer scope."

    def _primary_risk(self, record: Dict[str, Any], text: str) -> str:
        if record.get("forbidden_flags"):
            return f"Forbidden flags present: {', '.join(record.get('forbidden_flags', []))}."
        if record.get("ai_use_signals", {}).get("ai_unclear", True):
            return "AI-use permission is unclear and must be checked before proposal or execution."
        if "unclear_pay" in (record.get("risk_flags", []) or []):
            return "Payment or reward is unclear."
        if record.get("risk_flags"):
            return f"Risk flags require review: {', '.join(record.get('risk_flags', []))}."
        return "No major risk detected in internal assessment."

    def _recommended_next_step(self, decision: str) -> str:
        if decision == Phase3Decision.PROCEED_TO_PHASE_4.value:
            return "Proceed to Phase 4 internal proposal drafting; stop before outreach."
        if decision == Phase3Decision.PROCEED_WITH_CAUTION.value:
            return "Proceed to Phase 4 internal proposal drafting with caution notes; stop before outreach."
        if decision == Phase3Decision.HOLD_FOR_HUMAN_REVIEW.value:
            return "Hold for Justice review before any Phase 4 drafting."
        if decision == Phase3Decision.WEAK_HOLD.value:
            return "Archive unless strategically valuable."
        return "Reject or archive."

    def _cap_decision_by_phase2(self, record: Dict[str, Any], decision: str) -> str:
        if decision != Phase3Decision.PROCEED_TO_PHASE_4.value:
            return decision
        caution_flags = {
            "weak_aigc_preferred_fit",
            "job_board_employment_role",
            "broad_management_role",
            "senior_full_time_role",
            "sales_support_or_admin_role",
            "creative_media_role",
            "location_constrained_role",
            "suspicious_payment_setup",
            "unclear_employer_or_client",
        }
        record_flags = set(record.get("risk_flags", []) or [])
        if record.get("radar_decision") == "queue_with_caution":
            return Phase3Decision.PROCEED_WITH_CAUTION.value
        if caution_flags.intersection(record_flags):
            return Phase3Decision.PROCEED_WITH_CAUTION.value
        return decision

    def _autonomous_next_actions(self, decision: str) -> List[str]:
        if decision in {Phase3Decision.PROCEED_TO_PHASE_4.value, Phase3Decision.PROCEED_WITH_CAUTION.value}:
            return [
                "Draft internal proposal outline",
                "Generate clarifying questions",
                "Prepare Phase 4 proposal package for review",
            ]
        return [
            "Archive assessment",
            "Retain audit record",
            "Use lessons for future filtering",
        ]

    def _automation_level(self, record: Dict[str, Any]) -> str:
        signals = record.get("automation_signals", {}) or {}
        count = sum(1 for value in signals.values() if value)
        if record.get("forbidden_flags"):
            return "forbidden"
        if count >= 5:
            return "high"
        if count >= 3:
            return "medium"
        return "low"

    def _complexity(self, text: str) -> str:
        if Phase3Text.has_any(text, ["senior", "principal", "lead", "architect", "expert"]):
            return "advanced"
        if Phase3Text.has_any(text, ["junior", "entry", "intern", "good first issue"]):
            return "beginner"
        return "intermediate"

    def _deliverable_type(self, record: Dict[str, Any], text: str) -> str:
        if Phase3Text.has_any(text, ["dashboard", "analytics", "spreadsheet", "csv"]):
            return "data artifact"
        if Phase3Text.has_any(text, ["documentation", "docs", "readme", "article"]):
            return "document"
        if Phase3Text.has_any(text, ["script", "code", "api", "software", "bug"]):
            return "code"
        if Phase3Text.has_any(text, ["research", "analysis", "report"]):
            return "report"
        return "unknown deliverable"


class Phase3Runner:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.audit_dir = project_root / "data" / "audit"
        self.processed_dir = project_root / "data" / "phase3_processed"
        self.report_dir = project_root / "data" / "reports"
        for path in [self.audit_dir, self.processed_dir, self.report_dir]:
            path.mkdir(parents=True, exist_ok=True)
        self.ledger = Phase3AuditLedger(self.audit_dir / "aigc_phase3_audit.jsonl")
        self.engine = OlogyEngine()

    def run_from_config(self, config_path: Path) -> List[OpportunityAssessmentDossier]:
        config = load_json(config_path)
        input_path = resolve_project_path(self.project_root, config.get("input_queue", "data/phase2_processed/aigc_phase2_opportunity_queue.json"))
        output_path = resolve_project_path(self.project_root, config.get("output_dossiers", "data/phase3_processed/aigc_phase3_assessment_dossiers.json"))
        max_records = int(config.get("max_records", 100))
        records = load_json_list(input_path)
        return self.run(records, output_path, max_records=max_records)

    def run(
        self,
        records: List[Dict[str, Any]],
        output_path: Optional[Path] = None,
        max_records: int = 100,
    ) -> List[OpportunityAssessmentDossier]:
        require_phase2_to5_generation_authorized(self.project_root, "Phase 3")
        self.ledger.record(
            "phase3_run_start",
            {
                "input_records": len(records),
                "external_actions_allowed": False,
                "allowed_decisions": ["queue_for_phase_3", "queue_with_caution"],
            },
        )
        eligible = [
            record
            for record in records
            if record.get("radar_decision") in {"queue_for_phase_3", "queue_with_caution"}
        ][:max_records]
        dossiers: List[OpportunityAssessmentDossier] = []
        for record in eligible:
            dossier = self.engine.assess(record)
            dossiers.append(dossier)
            self.ledger.record(
                "opportunity_assessed",
                {
                    "dossier_id": dossier.dossier_id,
                    "opportunity_id": dossier.opportunity_id,
                    "title": dossier.title,
                    "source_platform": dossier.source_platform,
                    "phase3_assessment_score": dossier.phase3_assessment_score,
                    "final_decision": dossier.final_decision,
                },
            )
        target = output_path or self.processed_dir / "aigc_phase3_assessment_dossiers.json"
        self.export_dossiers(dossiers, target)
        self.export_signature_update(dossiers)
        self.ledger.record(
            "phase3_run_complete",
            {
                "eligible_records": len(eligible),
                "dossiers_created": len(dossiers),
                "output_path": str(target),
            },
        )
        return sorted(dossiers, key=lambda item: item.phase3_assessment_score, reverse=True)

    def export_dossiers(self, dossiers: List[OpportunityAssessmentDossier], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in dossiers]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.ledger.record("dossiers_exported", {"path": str(path), "records": len(dossiers)})
        return path

    def export_signature_update(self, dossiers: List[OpportunityAssessmentDossier]) -> Path:
        path = self.report_dir / "phase3_signature_update.md"
        path.write_text(self.signature_update(dossiers), encoding="utf-8")
        self.ledger.record("signature_update_exported", {"path": str(path)})
        return path

    def signature_update(self, dossiers: List[OpportunityAssessmentDossier]) -> str:
        counts = top_counts([item.final_decision for item in dossiers])
        highest = [
            {
                "title": item.title,
                "employer": item.employer,
                "source": item.source_platform,
                "score": item.phase3_assessment_score,
                "decision": item.final_decision,
                "url": item.source_url,
            }
            for item in sorted(dossiers, key=lambda dossier: dossier.phase3_assessment_score, reverse=True)[:10]
        ]
        return "\n".join(
            [
                "AIGC SIGNATURE UPDATE",
                "Operator:",
                "Justice Gray Maciocha",
                "Phase:",
                "Phase 3 - Ology Assessment Engine",
                "Operational Identity:",
                "Judgment Engine",
                "Action Performed:",
                "Assessed queued Phase 2 opportunities through internal methodology, taxonomy, ontology, epistemology, teleology, axiology, praxeology, heuristics, and meta-ontology.",
                "Safety Review:",
                "No applications sent.",
                "No messages sent.",
                "No proposals submitted.",
                "No credentials used.",
                "No employer/platform contact occurred.",
                "All external actions remain blocked.",
                f"Total Dossiers Created: {len(dossiers)}",
                "Decision Counts:",
                *(f"- {name}: {count}" for name, count in counts),
                "Highest Phase 3 Scores:",
                json.dumps(highest, indent=2),
                "Approval Required:",
                "No. Internal assessment only.",
                "Next Recommended Action:",
                "Review selected dossiers before any Phase 4 proposal drafting.",
            ]
        ).strip() + "\n"


def clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


def scale_100_to_10(value: int) -> int:
    return max(0, min(10, round(value / 10)))


def top_counts(values: Iterable[str], limit: int = 10) -> List[tuple[str, int]]:
    counts: Dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return payload


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run AIGC Phase 3 internal ology assessment.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase3_ology_assessment.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = Phase3Runner(args.project_root)
    dossiers = runner.run_from_config(args.config)
    print(runner.signature_update(dossiers))
    print(f"\nDossiers exported: {args.project_root / 'data' / 'phase3_processed' / 'aigc_phase3_assessment_dossiers.json'}")
    print(f"Report exported: {args.project_root / 'data' / 'reports' / 'phase3_signature_update.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
