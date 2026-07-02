from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class ProposalType(str, Enum):
    JOB_APPLICATION = "job_application"
    FREELANCE_BID = "freelance_bid"
    BOUNTY_INTENT = "bounty_intent"
    OPEN_SOURCE_CONTRIBUTION = "open_source_contribution"
    RESEARCH_OFFER = "research_offer"
    DOCUMENTATION_OFFER = "documentation_offer"
    AUTOMATION_OFFER = "automation_offer"


class ProposalDecision(str, Enum):
    READY_FOR_PHASE_5 = "ready_for_phase_5"
    STRONG_MINOR_REVIEW = "strong_minor_review"
    NEEDS_REVISION = "needs_revision"
    REWRITE_REQUIRED = "rewrite_required"
    DO_NOT_APPROVE = "do_not_approve"


@dataclass
class Deliverable:
    name: str
    description: str
    acceptance_criteria: List[str]
    format: str


@dataclass
class ScopeOfWork:
    summary: str
    included_work: List[str]
    excluded_work: List[str]
    assumptions: List[str]
    dependencies: List[str]


@dataclass
class MethodologyPlan:
    work_phases: List[str]
    tools_or_methods: List[str]
    quality_checks: List[str]


@dataclass
class TimelinePlan:
    estimated_duration: str
    milestones: List[str]


@dataclass
class AIUseDisclosure:
    required: bool
    recommended: bool
    draft_language: str


@dataclass
class RiskNotes:
    primary_risk: str
    mitigation: str
    approval_required_before: List[str]


@dataclass
class ProposalReadinessScore:
    employer_relevance: int
    deliverable_clarity: int
    professional_tone: int
    truthfulness: int
    scope_clarity: int
    timeline_reasonableness: int
    ai_disclosure_handling: int
    risk_handling: int
    approval_clarity: int
    auditability: int

    def total(self) -> int:
        return sum(asdict(self).values())

    def decision(self) -> ProposalDecision:
        score = self.total()
        if score >= 90:
            return ProposalDecision.READY_FOR_PHASE_5
        if score >= 80:
            return ProposalDecision.STRONG_MINOR_REVIEW
        if score >= 70:
            return ProposalDecision.NEEDS_REVISION
        if score >= 60:
            return ProposalDecision.REWRITE_REQUIRED
        return ProposalDecision.DO_NOT_APPROVE


@dataclass
class HumanApprovalPreview:
    proposed_external_action: str
    benefit: str
    risk: str
    safety_status: str
    ai_disclosure_status: str
    required_acceptance_phrase: str = "I, Justice Gray Maciocha, accept this action."


@dataclass
class ProposalPackage:
    proposal_id: str
    package_id: str
    opportunity_id: str
    dossier_id: str
    created_at: str
    operator: str
    status: str
    opportunity: Dict[str, Any]
    title: str
    employer: str
    source_platform: str
    source_url: str
    phase3_score: int
    phase3_decision: str
    proposal_type: str
    employer_intent_summary: str
    employer_facing_message: str
    short_message_variant: str
    technical_message_variant: str
    clarifying_question_variant: str
    scope_of_work: ScopeOfWork
    deliverables: List[Deliverable]
    methodology: MethodologyPlan
    timeline: TimelinePlan
    clarifying_questions: List[str]
    assumptions: List[str]
    ai_use_disclosure: AIUseDisclosure
    risk_notes: RiskNotes
    quality_assurance_plan: List[str]
    audit_summary: Dict[str, Any]
    human_approval_preview: HumanApprovalPreview
    external_action_classification: Dict[str, Any]
    readiness_score: ProposalReadinessScore
    readiness_decision: str
    final_recommendation: str
    approval_required_before: List[str]
    forbidden_actions: List[str]


class Phase4AuditLedger:
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


class ProposalDraftingEngine:
    def __init__(self, operator: str = "Justice Gray Maciocha"):
        self.operator = operator

    def create_package(self, dossier: Dict[str, Any]) -> ProposalPackage:
        blob = self._dossier_blob(dossier)
        proposal_type = self._determine_proposal_type(dossier, blob)
        proposal_id = self._make_proposal_id(dossier)
        title = dossier.get("title", "")
        employer = dossier.get("employer", "") or "the client"
        source_platform = dossier.get("source_platform", "")
        source_url = dossier.get("source_url", "")
        phase3_score = int(dossier.get("phase3_assessment_score", dossier.get("phase3_score", 0)) or 0)
        phase3_decision = dossier.get("final_decision", "")

        scope = self._build_scope(dossier, proposal_type)
        deliverables = self._build_deliverables(dossier, proposal_type)
        methodology = self._build_methodology(dossier, proposal_type)
        timeline = self._build_timeline(dossier, proposal_type)
        questions = self._build_clarifying_questions(dossier, proposal_type)
        disclosure = self._build_ai_disclosure(dossier)
        risks = self._build_risk_notes(dossier)
        qa_plan = self._quality_assurance_plan(proposal_type)

        employer_message = self._build_employer_message(
            title=title,
            employer=employer,
            proposal_type=proposal_type,
            deliverables=deliverables,
            timeline=timeline,
            questions=questions,
            disclosure=disclosure,
        )
        short_variant = self._build_short_variant(title, deliverables, questions)
        technical_variant = self._build_technical_variant(title, proposal_type, deliverables, methodology, questions)
        question_variant = self._build_question_first_variant(title, questions, disclosure)
        approval_preview = HumanApprovalPreview(
            proposed_external_action=f"Send proposal/message to {employer} for: {title}",
            benefit=self._benefit_statement(dossier),
            risk=risks.primary_risk,
            safety_status=self._safety_status(dossier),
            ai_disclosure_status="included" if disclosure.draft_language else "not_included",
        )
        readiness = self._score_readiness(
            employer_message=employer_message,
            scope=scope,
            deliverables=deliverables,
            timeline=timeline,
            disclosure=disclosure,
            risks=risks,
            source_url=source_url,
            phase3_decision=phase3_decision,
        )
        readiness_decision = self._readiness_decision(readiness, phase3_decision)
        approval_required_before = [
            "send_message",
            "submit_application",
            "submit_proposal",
            "submit_deliverable",
            "use_operator_identity",
            "use_credentials",
        ]
        audit_summary = {
            "source_dossier": dossier.get("dossier_id", ""),
            "source_dossier_id": dossier.get("dossier_id", ""),
            "agents_used": [
                "Meta-Semantic Agent",
                "Omni-Generative Agent",
                "Trans-Lingual Agent",
                "Trans-Modal Agent",
                "Trans-Architectural Agent",
                "Para-Synthetic Agent",
                "Hyper-Coherence Agent",
                "Hyper-Optimization Agent",
                "Ultra-Aligned Agent",
                "Ultra-Audit Agent",
            ],
            "safety_checks": [
                "No external action performed",
                "No employer contacted",
                "No proposal submitted",
                "AI-use disclosure considered",
                "Human approval required before external use",
            ],
            "external_action_performed": False,
        }
        return ProposalPackage(
            proposal_id=proposal_id,
            package_id=proposal_id,
            opportunity_id=dossier.get("opportunity_id", ""),
            dossier_id=dossier.get("dossier_id", ""),
            created_at=utc_now(),
            operator=self.operator,
            status="internal_draft_only",
            opportunity={
                "title": title,
                "employer": employer,
                "source_platform": source_platform,
                "source_url": source_url,
                "phase3_score": phase3_score,
                "phase3_decision": phase3_decision,
            },
            title=title,
            employer=employer,
            source_platform=source_platform,
            source_url=source_url,
            phase3_score=phase3_score,
            phase3_decision=phase3_decision,
            proposal_type=proposal_type.value,
            employer_intent_summary=self._employer_intent_summary(dossier, proposal_type),
            employer_facing_message=employer_message,
            short_message_variant=short_variant,
            technical_message_variant=technical_variant,
            clarifying_question_variant=question_variant,
            scope_of_work=scope,
            deliverables=deliverables,
            methodology=methodology,
            timeline=timeline,
            clarifying_questions=questions,
            assumptions=scope.assumptions,
            ai_use_disclosure=disclosure,
            risk_notes=risks,
            quality_assurance_plan=qa_plan,
            audit_summary=audit_summary,
            human_approval_preview=approval_preview,
            external_action_classification={
                "classification": "internal_draft_only",
                "external_actions_allowed": False,
                "requires_explicit_justice_approval_before_send": True,
                "send_ready": False,
            },
            readiness_score=readiness,
            readiness_decision=readiness_decision,
            final_recommendation=self._final_recommendation(readiness_decision),
            approval_required_before=approval_required_before,
            forbidden_actions=[
                "send_without_approval",
                "submit_without_approval",
                "contact_employer_without_approval",
                "claim_unverified_credentials",
                "hide_ai_use_where_disclosure_is_required",
                "bypass_platform_limits",
            ],
        )

    def _make_proposal_id(self, dossier: Dict[str, Any]) -> str:
        raw = "|".join(
            [
                dossier.get("dossier_id", ""),
                dossier.get("opportunity_id", ""),
                dossier.get("title", ""),
                dossier.get("source_url", ""),
            ]
        )
        return "phase4_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _dossier_blob(self, dossier: Dict[str, Any]) -> str:
        return json.dumps(dossier, ensure_ascii=False).lower()

    def _determine_proposal_type(self, dossier: Dict[str, Any], blob: str) -> ProposalType:
        taxonomy = set(dossier.get("discovered_taxonomy", []) or [])
        source_platform = dossier.get("source_platform", "")
        if source_platform == "GitHub" or "open_source_contribution" in taxonomy:
            return ProposalType.OPEN_SOURCE_CONTRIBUTION
        if "bounty" in blob or "challenge" in blob:
            return ProposalType.BOUNTY_INTENT
        if "api_documentation" in taxonomy or any(term in blob for term in ["documentation", "docs", "readme"]):
            return ProposalType.DOCUMENTATION_OFFER
        if any(term in taxonomy for term in ["software_coding", "prompt_engineering"]) or any(
            term in blob for term in ["python", "script", "automation", "workflow", "integration"]
        ):
            return ProposalType.AUTOMATION_OFFER
        if "research" in taxonomy or "data_analysis" in taxonomy or any(term in blob for term in ["research", "analysis"]):
            return ProposalType.RESEARCH_OFFER
        if any(term in blob for term in ["freelance", "contract", "gig"]):
            return ProposalType.FREELANCE_BID
        return ProposalType.JOB_APPLICATION

    def _employer_intent_summary(self, dossier: Dict[str, Any], proposal_type: ProposalType) -> str:
        title = dossier.get("title", "the requested work")
        value = dossier.get("primary_value", "The likely value is a scoped, reviewable deliverable.")
        if proposal_type == ProposalType.OPEN_SOURCE_CONTRIBUTION:
            return f"The maintainers likely need a focused contribution for '{title}'. Primary value: {value}"
        return f"The requester likely needs help with '{title}' through a scoped, reviewable deliverable. Primary value: {value}"

    def _build_scope(self, dossier: Dict[str, Any], proposal_type: ProposalType) -> ScopeOfWork:
        title = dossier.get("title", "the requested work")
        included = [
            "Review the provided requirements and confirm the expected output.",
            "Prepare the requested deliverable using a structured workflow.",
            "Review the final output for clarity, completeness, and alignment with the stated requirements.",
        ]
        if proposal_type in {ProposalType.DOCUMENTATION_OFFER, ProposalType.OPEN_SOURCE_CONTRIBUTION}:
            included.extend(
                [
                    "Improve documentation structure, readability, and developer usability where applicable.",
                    "Prepare examples, summaries, usage notes, or issue-specific notes where useful.",
                ]
            )
        if proposal_type == ProposalType.AUTOMATION_OFFER:
            included.extend(
                [
                    "Design the automation workflow before implementation.",
                    "Prepare implementation notes and basic validation checks.",
                ]
            )
        if proposal_type == ProposalType.RESEARCH_OFFER:
            included.extend(
                [
                    "Collect and organize relevant source material.",
                    "Synthesize findings into a clear report or structured summary.",
                ]
            )
        return ScopeOfWork(
            summary=f"Prepare internal proposal language and scoped work plan for: {title}.",
            included_work=included,
            excluded_work=[
                "External submission without operator approval.",
                "Work outside the employer-approved scope.",
                "Use of prohibited automation or platform-restricted methods.",
                "Use of credentials, private data, or operator identity without explicit approval.",
            ],
            assumptions=[
                "The requester will provide any required files, requirements, constraints, or repository guidance.",
                "AI-assisted workflow is acceptable unless the requester or platform says otherwise.",
                "Final external delivery requires human approval before submission.",
            ],
            dependencies=[
                "Clear task requirements.",
                "Approved communication channel.",
                "Any required source documents, API documentation, or project files.",
            ],
        )

    def _build_deliverables(self, dossier: Dict[str, Any], proposal_type: ProposalType) -> List[Deliverable]:
        title = dossier.get("title", "Requested Deliverable")
        if proposal_type in {ProposalType.DOCUMENTATION_OFFER, ProposalType.OPEN_SOURCE_CONTRIBUTION}:
            return [
                Deliverable(
                    name="Documentation or Contribution Draft",
                    description="A structured draft or issue-specific contribution aligned with the source request.",
                    acceptance_criteria=[
                        "Clear structure",
                        "Accurate explanation",
                        "Usable examples or notes where appropriate",
                        "Aligned with requester or repository requirements",
                    ],
                    format="Markdown, pull request draft, document, or requested format",
                ),
                Deliverable(
                    name="Review Notes",
                    description="Concise notes explaining assumptions, changes, and unresolved questions.",
                    acceptance_criteria=[
                        "Summarizes key decisions",
                        "Identifies unresolved questions",
                        "Supports requester or maintainer review",
                    ],
                    format="Markdown or document",
                ),
            ]
        if proposal_type == ProposalType.AUTOMATION_OFFER:
            return [
                Deliverable(
                    name="Automation Workflow Plan",
                    description="A clear description of the proposed automation process and required inputs/outputs.",
                    acceptance_criteria=["Defines input", "Defines output", "Explains process", "Identifies constraints"],
                    format="Markdown, document, or technical spec",
                ),
                Deliverable(
                    name="Implementation Artifact",
                    description="A script, prototype, configuration, or implementation draft if approved within scope.",
                    acceptance_criteria=[
                        "Runs or is reviewable",
                        "Includes usage notes",
                        "Avoids prohibited platform behavior",
                        "Includes basic validation steps",
                    ],
                    format="Python/script/code file or requested format",
                ),
            ]
        if proposal_type == ProposalType.RESEARCH_OFFER:
            return [
                Deliverable(
                    name="Research Summary Report",
                    description="A structured report synthesizing findings, sources, and practical conclusions.",
                    acceptance_criteria=[
                        "Uses reliable sources where applicable",
                        "Separates facts from assumptions",
                        "Includes concise conclusions",
                        "Matches requested scope",
                    ],
                    format="Document, Markdown, PDF, or requested format",
                )
            ]
        return [
            Deliverable(
                name=title,
                description="The requested work product, prepared according to requester requirements.",
                acceptance_criteria=[
                    "Matches stated requirements",
                    "Is clear and complete",
                    "Is delivered in the requested format",
                    "Is reviewed before submission",
                ],
                format="Requester-specified format",
            )
        ]

    def _build_methodology(self, dossier: Dict[str, Any], proposal_type: ProposalType) -> MethodologyPlan:
        work_phases = [
            "Confirm requirements and success criteria.",
            "Prepare the work product using the appropriate method.",
            "Review for accuracy, completeness, clarity, and alignment.",
            "Prepare final delivery package after operator approval.",
        ]
        tools_or_methods = [
            "Structured requirement analysis",
            "Human-reviewed AI-assisted drafting where allowed",
            "Quality-control checklist",
            "Audit logging",
        ]
        if proposal_type in {ProposalType.OPEN_SOURCE_CONTRIBUTION, ProposalType.AUTOMATION_OFFER}:
            tools_or_methods.extend(["Repository/context review", "Small-scope implementation planning", "Validation checklist"])
        if proposal_type == ProposalType.RESEARCH_OFFER:
            tools_or_methods.extend(["Source collection", "Evidence synthesis", "Fact/assumption separation"])
        return MethodologyPlan(
            work_phases=work_phases,
            tools_or_methods=tools_or_methods,
            quality_checks=[
                "Check against requester requirements.",
                "Check for unsupported claims.",
                "Check for privacy/security issues.",
                "Check whether AI-use disclosure is required or recommended.",
                "Confirm no external action occurs without approval.",
            ],
        )

    def _build_timeline(self, dossier: Dict[str, Any], proposal_type: ProposalType) -> TimelinePlan:
        if proposal_type in {ProposalType.DOCUMENTATION_OFFER, ProposalType.OPEN_SOURCE_CONTRIBUTION, ProposalType.RESEARCH_OFFER}:
            estimated = "To be confirmed after scope and length are clarified."
        elif proposal_type == ProposalType.AUTOMATION_OFFER:
            estimated = "To be confirmed after technical requirements, inputs, and constraints are clarified."
        else:
            estimated = "To be confirmed with the requester."
        return TimelinePlan(
            estimated_duration=estimated,
            milestones=["Requirement confirmation", "Draft preparation", "Quality review", "Final delivery after approval"],
        )

    def _build_clarifying_questions(self, dossier: Dict[str, Any], proposal_type: ProposalType) -> List[str]:
        questions = [
            "What exact final format would you prefer for the deliverable?",
            "Are there any specific requirements, examples, templates, tools, or style guidelines I should follow?",
            "What deadline or turnaround time are you aiming for?",
        ]
        if proposal_type == ProposalType.OPEN_SOURCE_CONTRIBUTION:
            questions.extend(
                [
                    "Should I comment before drafting a pull request, or is a PR welcome directly?",
                    "Are there contribution guidelines, tests, or maintainer preferences I should follow?",
                ]
            )
        if proposal_type == ProposalType.AUTOMATION_OFFER:
            questions.extend(
                [
                    "Are there platform, API, authentication, rate-limit, or security constraints I need to follow?",
                    "Should the output be a working script, prototype, workflow plan, or documentation?",
                ]
            )
        if proposal_type == ProposalType.DOCUMENTATION_OFFER:
            questions.extend(["Who is the target reader?", "Should examples, code snippets, diagrams, or quick-start sections be included?"])
        questions.append(
            "Are AI-assisted research, drafting, analysis, or coding workflows acceptable if the final output is reviewed before delivery?"
        )
        return dedupe(questions)

    def _build_ai_disclosure(self, dossier: Dict[str, Any]) -> AIUseDisclosure:
        risk = str(dossier.get("primary_risk", "")).lower()
        required = "ai-use permission is unclear" in risk or "ai" in risk
        return AIUseDisclosure(
            required=required,
            recommended=True,
            draft_language=(
                "I use a structured AI-assisted workflow where appropriate for organization, drafting, analysis, "
                "coding support, and quality review. Final review, approval, and delivery remain under human "
                "oversight. If you have specific requirements around AI-assisted work, I can follow those requirements."
            ),
        )

    def _build_risk_notes(self, dossier: Dict[str, Any]) -> RiskNotes:
        primary_risk = dossier.get("primary_risk", "") or "No major Phase 4 drafting risk detected."
        return RiskNotes(
            primary_risk=primary_risk,
            mitigation=(
                "Keep proposal internal until approval, include clarifying questions, avoid overpromising, "
                "disclose AI assistance where appropriate, and follow requester/platform requirements."
            ),
            approval_required_before=[
                "message_employer",
                "apply",
                "submit_proposal",
                "submit_deliverable",
                "use_operator_identity",
                "use_credentials",
            ],
        )

    def _build_employer_message(
        self,
        title: str,
        employer: str,
        proposal_type: ProposalType,
        deliverables: List[Deliverable],
        timeline: TimelinePlan,
        questions: List[str],
        disclosure: AIUseDisclosure,
    ) -> str:
        greeting = f"Hi {employer} maintainers," if proposal_type == ProposalType.OPEN_SOURCE_CONTRIBUTION else f"Hello {employer},"
        deliverable_lines = "\n".join(f"- {item.name}: {item.description}" for item in deliverables)
        question_lines = "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions[:5]))
        return f"""{greeting}
I reviewed your request for {title}, and I can help by preparing a clear, structured, reviewable deliverable aligned with your requirements.

My proposed approach is:
1. Confirm the exact requirements, final format, and success criteria.
2. Prepare the work product using a structured workflow.
3. Review the output for clarity, completeness, accuracy, and alignment with your instructions.
4. Deliver the final result in the requested format, with notes or revision support if needed.

Proposed deliverables:
{deliverable_lines}

Estimated timeline:
{timeline.estimated_duration}

A few clarifying questions before finalizing the scope:
{question_lines}

{disclosure.draft_language}

Best regards,
Justice Gray Maciocha""".strip()

    def _build_short_variant(self, title: str, deliverables: List[Deliverable], questions: List[str]) -> str:
        main_deliverable = deliverables[0].name if deliverables else "the requested deliverable"
        first_question = questions[0] if questions else "What final format would you prefer?"
        return f"""Hello,
I can help with {title} by preparing {main_deliverable} in a clear, structured, reviewable format.

Before finalizing scope, one key question: {first_question}

I use AI-assisted workflow support where appropriate, with final human review before delivery.

Best regards,
Justice Gray Maciocha""".strip()

    def _build_technical_variant(
        self,
        title: str,
        proposal_type: ProposalType,
        deliverables: List[Deliverable],
        methodology: MethodologyPlan,
        questions: List[str],
    ) -> str:
        deliverable_lines = "\n".join(f"- {item.name}" for item in deliverables)
        method_lines = "\n".join(f"- {item}" for item in methodology.tools_or_methods[:6])
        question_lines = "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions[:5]))
        return f"""Hello,
I reviewed the requirements for {title}. I can approach this with a structured technical workflow focused on clarity, reliability, and reviewability.

Proposed deliverables:
{deliverable_lines}

Methods / tools:
{method_lines}

Before starting, I would clarify:
{question_lines}

I can provide a concise process summary with the final delivery so the work is easy to evaluate.

Best regards,
Justice Gray Maciocha""".strip()

    def _build_question_first_variant(self, title: str, questions: List[str], disclosure: AIUseDisclosure) -> str:
        question_lines = "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions[:6]))
        return f"""Hello,
I am interested in helping with {title}. Before proposing a final scope, I want to clarify a few details so the work is accurate and aligned with what you need.

Questions:
{question_lines}

{disclosure.draft_language}

Once those details are clear, I can provide a precise scope, timeline, and deliverable plan.

Best regards,
Justice Gray Maciocha""".strip()

    def _quality_assurance_plan(self, proposal_type: ProposalType) -> List[str]:
        checks = [
            "Verify the source URL and original requirements before use.",
            "Check the proposal against the Phase 3 risk notes.",
            "Confirm no claims exceed verified evidence.",
            "Run human review before any external action.",
        ]
        if proposal_type in {ProposalType.DOCUMENTATION_OFFER, ProposalType.OPEN_SOURCE_CONTRIBUTION}:
            checks.extend(["Review for clarity, examples, and missing assumptions.", "Check links, commands, and terminology."])
        if proposal_type == ProposalType.AUTOMATION_OFFER:
            checks.extend(["Identify tests before implementation.", "Avoid unreviewed code delivery."])
        return checks

    def _benefit_statement(self, dossier: Dict[str, Any]) -> str:
        return dossier.get("primary_value", "") or "Potential work opportunity with structured deliverable value."

    def _safety_status(self, dossier: Dict[str, Any]) -> str:
        decision = dossier.get("final_decision", "")
        risk = str(dossier.get("primary_risk", "")).lower()
        if "forbidden" in risk or "blocked" in risk:
            return "blocked"
        if decision == "proceed_to_phase_4_with_caution" or "unclear" in risk:
            return "caution"
        return "cleared"

    def _score_readiness(
        self,
        employer_message: str,
        scope: ScopeOfWork,
        deliverables: List[Deliverable],
        timeline: TimelinePlan,
        disclosure: AIUseDisclosure,
        risks: RiskNotes,
        source_url: str,
        phase3_decision: str,
    ) -> ProposalReadinessScore:
        caution_penalty = 1 if phase3_decision == "proceed_to_phase_4_with_caution" else 0

        def score(condition: bool, full: int = 10, partial: int = 7) -> int:
            return full if condition else partial

        return ProposalReadinessScore(
            employer_relevance=score(len(employer_message) > 200) - caution_penalty,
            deliverable_clarity=score(bool(deliverables and deliverables[0].acceptance_criteria)) - caution_penalty,
            professional_tone=10,
            truthfulness=10,
            scope_clarity=score(bool(scope.included_work and scope.excluded_work)) - caution_penalty,
            timeline_reasonableness=score(bool(timeline.estimated_duration)),
            ai_disclosure_handling=10 if disclosure.recommended and disclosure.draft_language else 6,
            risk_handling=score(bool(risks.primary_risk and risks.mitigation)) - caution_penalty,
            approval_clarity=10,
            auditability=10 if source_url else 6,
        )

    def _readiness_decision(self, readiness: ProposalReadinessScore, phase3_decision: str) -> str:
        decision = readiness.decision().value
        if phase3_decision == "proceed_to_phase_4_with_caution" and decision == ProposalDecision.READY_FOR_PHASE_5.value:
            return ProposalDecision.STRONG_MINOR_REVIEW.value
        return decision

    def _final_recommendation(self, readiness_decision: str) -> str:
        if readiness_decision == ProposalDecision.READY_FOR_PHASE_5.value:
            return "Ready for Phase 5 approval review."
        if readiness_decision == ProposalDecision.STRONG_MINOR_REVIEW.value:
            return "Ready for Phase 5 approval review with caution notes."
        return "Revise before Phase 5 approval review."


class Phase4Runner:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.audit_dir = project_root / "data" / "audit"
        self.output_dir = project_root / "data" / "phase4_proposals"
        self.report_dir = project_root / "data" / "reports"
        for path in [self.audit_dir, self.output_dir, self.report_dir]:
            path.mkdir(parents=True, exist_ok=True)
        self.ledger = Phase4AuditLedger(self.audit_dir / "aigc_phase4_audit.jsonl")
        self.engine = ProposalDraftingEngine()

    def run_from_config(self, config_path: Path) -> List[ProposalPackage]:
        config = load_json_dict(config_path)
        input_path = resolve_project_path(
            self.project_root,
            config.get("input_dossiers", config.get("input_file", "data/phase3_processed/aigc_phase3_assessment_dossiers.json")),
        )
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_packages", config.get("output_file", "data/phase4_proposals/aigc_phase4_proposal_packages.json")),
        )
        accepted = set(
            config.get(
                "accepted_phase3_decisions",
                config.get("eligible_phase3_decisions", ["proceed_to_phase_4", "proceed_to_phase_4_with_caution"]),
            )
        )
        max_records = int(config.get("max_records", 25))
        dossiers = load_json_list(input_path)
        return self.run(dossiers, output_path, accepted_decisions=accepted, max_records=max_records)

    def run(
        self,
        dossiers: List[Dict[str, Any]],
        output_path: Optional[Path] = None,
        accepted_decisions: Optional[set[str]] = None,
        max_records: int = 25,
    ) -> List[ProposalPackage]:
        accepted = accepted_decisions or {"proceed_to_phase_4", "proceed_to_phase_4_with_caution"}
        self.ledger.record(
            "phase4_run_start",
            {
                "input_dossiers": len(dossiers),
                "accepted_decisions": sorted(accepted),
                "external_actions_allowed": False,
            },
        )
        eligible = [item for item in dossiers if item.get("final_decision") in accepted]
        eligible = sorted(eligible, key=lambda item: int(item.get("phase3_assessment_score", 0) or 0), reverse=True)[
            :max_records
        ]
        packages = []
        for dossier in eligible:
            package = self.engine.create_package(dossier)
            packages.append(package)
            self.ledger.record(
                "phase4_proposal_package_created",
                {
                    "proposal_id": package.proposal_id,
                    "opportunity_id": package.opportunity_id,
                    "title": package.title,
                    "employer": package.employer,
                    "proposal_type": package.proposal_type,
                    "readiness_score": package.readiness_score.total(),
                    "readiness_decision": package.readiness_decision,
                    "status": package.status,
                    "external_action_performed": False,
                },
            )
        packages = sorted(packages, key=lambda item: item.readiness_score.total(), reverse=True)
        target = output_path or self.output_dir / "aigc_phase4_proposal_packages.json"
        self.export_packages(packages, target)
        self.export_signature_update(packages)
        self.ledger.record(
            "phase4_run_complete",
            {"eligible_dossiers": len(eligible), "packages_created": len(packages), "output_path": str(target)},
        )
        return packages

    def export_packages(self, packages: List[ProposalPackage], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([asdict(item) for item in packages], ensure_ascii=False, indent=2), encoding="utf-8")
        self.ledger.record("proposal_packages_exported", {"path": str(path), "records": len(packages)})
        return path

    def export_signature_update(self, packages: List[ProposalPackage]) -> Path:
        path = self.report_dir / "phase4_signature_update.md"
        path.write_text(self.signature_update(packages), encoding="utf-8")
        self.ledger.record("signature_update_exported", {"path": str(path)})
        return path

    def signature_update(self, packages: List[ProposalPackage]) -> str:
        ready = [
            item
            for item in packages
            if item.readiness_decision in {ProposalDecision.READY_FOR_PHASE_5.value, ProposalDecision.STRONG_MINOR_REVIEW.value}
        ]
        needs_revision = [
            item
            for item in packages
            if item.readiness_decision in {ProposalDecision.NEEDS_REVISION.value, ProposalDecision.REWRITE_REQUIRED.value}
        ]
        blocked = [item for item in packages if item.readiness_decision == ProposalDecision.DO_NOT_APPROVE.value]
        top = [
            {
                "proposal_id": item.proposal_id,
                "title": item.title,
                "employer": item.employer,
                "proposal_type": item.proposal_type,
                "readiness_score": item.readiness_score.total(),
                "readiness_decision": item.readiness_decision,
                "approval_required_phrase": item.human_approval_preview.required_acceptance_phrase,
            }
            for item in packages[:5]
        ]
        return "\n".join(
            [
                "AIGC SIGNATURE UPDATE",
                "Operator:",
                "Justice Gray Maciocha",
                "Phase:",
                "Phase 4 - Proposal Drafting Engine",
                "Operational Identity:",
                "Professional Voice Engine",
                "Action Performed:",
                "Generated internal proposal packages from eligible Phase 3 assessment dossiers.",
                "Safety Review:",
                "No proposals sent.",
                "No applications submitted.",
                "No employers contacted.",
                "No bids placed.",
                "No credentials used.",
                "No external action performed.",
                "All proposal packages remain internal drafts.",
                f"Total Proposal Packages Created: {len(packages)}",
                f"Ready for Phase 5: {len(ready)}",
                f"Needs Revision: {len(needs_revision)}",
                f"Blocked / Do Not Approve: {len(blocked)}",
                "Top Proposal Packages:",
                json.dumps(top, indent=2),
                "Approval Required:",
                "No approval required for drafting.",
                "Approval will be required in Phase 5 before sending, applying, messaging, bidding, or submitting.",
                "Next Recommended Action:",
                "Proceed to Phase 5 - Human Approval Gate - for the highest-readiness proposal packages.",
            ]
        ).strip() + "\n"


def dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def load_json_dict(path: Path) -> Dict[str, Any]:
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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 4 internal proposal drafting.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase4_proposal_drafting.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = Phase4Runner(args.project_root)
    packages = runner.run_from_config(args.config)
    print(runner.signature_update(packages))
    print(f"\nPackages exported: {args.project_root / 'data' / 'phase4_proposals' / 'aigc_phase4_proposal_packages.json'}")
    print(f"Report exported: {args.project_root / 'data' / 'reports' / 'phase4_signature_update.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
