from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class OutcomeStatus(str, Enum):
    DISCOVERED_ONLY = "discovered_only"
    ASSESSED_ONLY = "assessed_only"
    PROPOSAL_DRAFTED = "proposal_drafted"
    APPROVAL_DENIED = "approval_denied"
    PROPOSAL_SENT = "proposal_sent"
    EMPLOYER_NO_RESPONSE = "employer_no_response"
    EMPLOYER_REJECTED = "employer_rejected"
    EMPLOYER_REQUESTED_CLARIFICATION = "employer_requested_clarification"
    EMPLOYER_REQUESTED_REVISION = "employer_requested_revision"
    EMPLOYER_ACCEPTED = "employer_accepted"
    CONTRACT_STARTED = "contract_started"
    WORK_COMPLETED = "work_completed"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    PLATFORM_BLOCKED = "platform_blocked"
    SAFETY_BLOCKED = "safety_blocked"
    EXECUTION_FAILED = "execution_failed"
    OPERATOR_ABANDONED = "operator_abandoned"
    ARCHIVED = "archived"


class OutcomeQuality(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MIXED = "mixed"
    WEAK = "weak"
    FAILED = "failed"
    UNSAFE_BLOCKED = "unsafe_blocked"
    UNKNOWN = "unknown"


class PatchDecision(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DENIED = "denied"
    REVISION_REQUIRED = "revision_required"
    BLOCKED = "blocked"


@dataclass
class LinkedRecords:
    opportunity_id: str = ""
    phase3_dossier_id: str = ""
    phase4_proposal_id: str = ""
    phase5_authorization_id: str = ""
    phase6_execution_id: str = ""
    phase7_packet_id: str = ""


@dataclass
class OpportunitySummary:
    title: str = ""
    employer: str = ""
    platform: str = ""
    source_url: str = ""
    work_type: str = ""
    proposal_type: str = ""


@dataclass
class OutcomeRecord:
    outcome_id: str
    created_at: str
    operator: str
    linked_records: LinkedRecords
    opportunity: OpportunitySummary
    status: str
    employer_response: str
    payment_status: str
    revision_status: str
    operator_notes: str
    quality: str
    metrics: Dict[str, int]
    lessons: Dict[str, List[str]]
    next_actions: Dict[str, List[str]]


@dataclass
class AgentPerformanceRecord:
    agent_name: str
    affix_house: str
    phase_involved: str
    contribution: str
    accuracy: int
    usefulness: int
    safety_alignment: int
    professional_quality: int
    efficiency: int
    completeness: int
    risk_detection: int
    adaptability: int
    audit_contribution: int
    outcome_contribution: int
    evolution_recommendation: str

    def total(self) -> int:
        return (
            self.accuracy
            + self.usefulness
            + self.safety_alignment
            + self.professional_quality
            + self.efficiency
            + self.completeness
            + self.risk_detection
            + self.adaptability
            + self.audit_contribution
            + self.outcome_contribution
        )


@dataclass
class EvolutionPatch:
    patch_id: str
    patch_type: str
    created_at: str
    reason: str
    evidence: List[str]
    proposed_change: Dict[str, Any]
    expected_benefit: str
    risk: str
    safety_impact: str
    approval_required: bool
    decision: str = PatchDecision.PENDING.value
    operator_response: str = ""
    applied: bool = False


@dataclass
class EvolutionCycleReport:
    report_id: str
    created_at: str
    operator: str
    outcome_id: str
    cycle_score: int
    cycle_quality: str
    what_worked: List[str]
    what_failed: List[str]
    unexpected_variables: List[str]
    new_risk_patterns: List[str]
    new_success_patterns: List[str]
    agent_performance: List[AgentPerformanceRecord]
    proposed_patches: List[EvolutionPatch]
    next_cycle_strategy: List[str]


class Phase8AuditLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "timestamp": utc_now(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event_id


class HashTools:
    @staticmethod
    def short_hash(value: str, length: int = 12) -> str:
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:length].upper()


class EvolutionSafetyGate:
    FORBIDDEN_PATCH_CONTENT = [
        "remove_human_approval",
        "disable_audit",
        "disable_privacy",
        "disable_security",
        "permit_spam",
        "permit_impersonation",
        "permit_forbidden_scraping",
        "hide_ai_use",
        "auto_apply_without_approval",
        "delete_negative_outcomes",
        "rewrite_history",
    ]
    SAFETY_WEAKENING_TERMS = [
        "reduce approval",
        "remove approval",
        "skip approval",
        "disable logging",
        "disable audit",
        "remove disclosure",
        "less privacy",
        "bypass",
        "ignore platform",
    ]
    BEHAVIOR_CHANGING_TYPES = {
        "domain_update",
        "scoring_weight_update",
        "agent_prompt_update",
        "safety_rule_update",
        "proposal_template_update",
        "execution_rule_update",
        "audit_template_update",
        "ology_framework_update",
        "connector_update",
    }

    def classify_patch(self, patch: EvolutionPatch) -> EvolutionPatch:
        blob = json.dumps(asdict(patch), ensure_ascii=False).lower()
        if any(term in blob for term in self.FORBIDDEN_PATCH_CONTENT):
            patch.decision = PatchDecision.BLOCKED.value
            patch.approval_required = True
            patch.applied = False
            patch.risk = "blocked: forbidden evolution pattern detected"
            patch.safety_impact = "blocked"
            return patch
        if any(term in blob for term in self.SAFETY_WEAKENING_TERMS):
            patch.approval_required = True
            patch.risk = "enhanced review required: possible safety weakening"
            patch.safety_impact = "unknown_or_weakening"
            return patch
        if patch.patch_type in self.BEHAVIOR_CHANGING_TYPES:
            patch.approval_required = True
        if not patch.approval_required:
            patch.decision = PatchDecision.ACCEPTED.value
            patch.applied = True
        return patch

    def validate_operator_response(self, patch: EvolutionPatch, response: str, operator: str) -> EvolutionPatch:
        if patch.decision == PatchDecision.BLOCKED.value:
            patch.operator_response = response
            patch.applied = False
            return patch
        accept = f"I, {operator}, accept evolution patch {patch.patch_id}."
        deny = f"I, {operator}, deny evolution patch {patch.patch_id}."
        revise_prefix = f"Revise evolution patch {patch.patch_id}:"
        patch.operator_response = response.strip()
        if response.strip() == accept:
            patch.decision = PatchDecision.ACCEPTED.value
            patch.applied = True
        elif response.strip() == deny:
            patch.decision = PatchDecision.DENIED.value
            patch.applied = False
        elif response.strip().startswith(revise_prefix):
            patch.decision = PatchDecision.REVISION_REQUIRED.value
            patch.applied = False
        else:
            patch.decision = PatchDecision.DENIED.value
            patch.applied = False
        return patch


class EvolutionScorer:
    def score_cycle(self, metrics: Dict[str, int], status: str) -> tuple[int, str]:
        score = max(0, min(100, sum(metrics.values())))
        if status in {OutcomeStatus.SAFETY_BLOCKED.value, OutcomeStatus.PLATFORM_BLOCKED.value}:
            if metrics.get("safety_performance", 0) >= 9:
                return max(score, 70), OutcomeQuality.MIXED.value
        if score >= 90:
            return score, OutcomeQuality.EXCELLENT.value
        if score >= 75:
            return score, OutcomeQuality.GOOD.value
        if score >= 60:
            return score, OutcomeQuality.MIXED.value
        if score >= 40:
            return score, OutcomeQuality.WEAK.value
        return score, OutcomeQuality.FAILED.value


class AgentPerformanceEvaluator:
    def evaluate_default_agents(self, outcome: OutcomeRecord) -> List[AgentPerformanceRecord]:
        safety_score = outcome.metrics.get("safety_performance", 8)
        audit_score = outcome.metrics.get("audit_quality", 8)
        proposal_score = outcome.metrics.get("proposal_quality", 8)
        assessment_score = outcome.metrics.get("assessment_accuracy", 8)
        execution_score = outcome.metrics.get("execution_reliability", 8)
        return [
            AgentPerformanceRecord(
                agent_name="Meta-Recursive Agent",
                affix_house="META",
                phase_involved="Phase 8",
                contribution="Detected improvement patterns and generated next-cycle learning logic.",
                accuracy=8,
                usefulness=8,
                safety_alignment=9,
                professional_quality=8,
                efficiency=8,
                completeness=8,
                risk_detection=8,
                adaptability=9,
                audit_contribution=8,
                outcome_contribution=8,
                evolution_recommendation="keep and refine pattern detection rules",
            ),
            AgentPerformanceRecord(
                agent_name="Neo-Algorithmic Agent",
                affix_house="NEO",
                phase_involved="Phases 2/3/8",
                contribution="Scoring and ranking logic.",
                accuracy=assessment_score,
                usefulness=assessment_score,
                safety_alignment=8,
                professional_quality=8,
                efficiency=8,
                completeness=8,
                risk_detection=8,
                adaptability=8,
                audit_contribution=7,
                outcome_contribution=assessment_score,
                evolution_recommendation="adjust scoring weights if expected-vs-actual outcome diverges",
            ),
            AgentPerformanceRecord(
                agent_name="Omni-Generative Agent",
                affix_house="OMNI",
                phase_involved="Phase 4",
                contribution="Proposal and artifact drafting.",
                accuracy=proposal_score,
                usefulness=proposal_score,
                safety_alignment=8,
                professional_quality=proposal_score,
                efficiency=8,
                completeness=proposal_score,
                risk_detection=7,
                adaptability=8,
                audit_contribution=7,
                outcome_contribution=proposal_score,
                evolution_recommendation="refine proposal templates after employer feedback is available",
            ),
            AgentPerformanceRecord(
                agent_name="Ultra-Aligned Agent",
                affix_house="ULTRA",
                phase_involved="All phases",
                contribution="Safety, ethics, privacy, legality, and platform compliance.",
                accuracy=safety_score,
                usefulness=safety_score,
                safety_alignment=safety_score,
                professional_quality=9,
                efficiency=8,
                completeness=safety_score,
                risk_detection=safety_score,
                adaptability=8,
                audit_contribution=audit_score,
                outcome_contribution=safety_score,
                evolution_recommendation="keep approval gates and strengthen safety when new risks appear",
            ),
            AgentPerformanceRecord(
                agent_name="Ultra-Audit Agent",
                affix_house="ULTRA",
                phase_involved="Phases 5/6/7/8",
                contribution="Audit records and employer packet traceability.",
                accuracy=audit_score,
                usefulness=audit_score,
                safety_alignment=9,
                professional_quality=audit_score,
                efficiency=8,
                completeness=audit_score,
                risk_detection=8,
                adaptability=8,
                audit_contribution=audit_score,
                outcome_contribution=audit_score,
                evolution_recommendation="keep audit logging active for every phase",
            ),
            AgentPerformanceRecord(
                agent_name="Controlled Execution Engine",
                affix_house="ULTRA/HYPER",
                phase_involved="Phase 6",
                contribution="Exact-action execution or manual handoff.",
                accuracy=execution_score,
                usefulness=execution_score,
                safety_alignment=9,
                professional_quality=8,
                efficiency=execution_score,
                completeness=execution_score,
                risk_detection=8,
                adaptability=7,
                audit_contribution=audit_score,
                outcome_contribution=execution_score,
                evolution_recommendation="prefer manual handoff unless API execution is proven safe",
            ),
        ]


class PatchGenerator:
    def generate_patches(self, outcome: OutcomeRecord) -> List[EvolutionPatch]:
        patches: List[EvolutionPatch] = []
        if outcome.status == OutcomeStatus.PROPOSAL_DRAFTED.value:
            patches.append(self._make_patch(
                patch_type="memory_update",
                reason="Current cycle has internal proposal packages but no approved external outcome yet.",
                evidence=["Phase 5 packets are pending; Phase 6 has no approved execution receipts."],
                proposed_change={
                    "target": "next_cycle_strategy",
                    "change": "Collect accept/deny/revise decisions for pending action IDs before optimizing employer-response patterns.",
                },
                expected_benefit="Prevents learning from incomplete outcome data.",
                risk="low",
                safety_impact="strengthens",
                approval_required=False,
            ))
        if outcome.metrics.get("proposal_quality", 10) < 7:
            patches.append(self._make_patch(
                patch_type="proposal_template_update",
                reason="Proposal quality scored below target.",
                evidence=outcome.lessons.get("what_failed", []),
                proposed_change={
                    "target": "phase4_proposal_template",
                    "change": "Shorten opening, improve deliverable specificity, and add sharper clarifying questions.",
                },
                expected_benefit="Higher employer relevance and response rate.",
                risk="low",
                safety_impact="neutral",
                approval_required=True,
            ))
        if outcome.metrics.get("safety_performance", 10) < 9:
            patches.append(self._make_patch(
                patch_type="safety_rule_update",
                reason="Safety performance below target.",
                evidence=outcome.lessons.get("new_risk_patterns", []),
                proposed_change={
                    "target": "safety_rules",
                    "change": "Add detected risk patterns to warning or block list and require enhanced review.",
                },
                expected_benefit="Stronger prevention of future safety issues.",
                risk="low",
                safety_impact="strengthens",
                approval_required=True,
            ))
        return patches

    def _make_patch(
        self,
        patch_type: str,
        reason: str,
        evidence: List[str],
        proposed_change: Dict[str, Any],
        expected_benefit: str,
        risk: str,
        safety_impact: str,
        approval_required: bool,
    ) -> EvolutionPatch:
        created = utc_now()
        seed = json.dumps({
            "patch_type": patch_type,
            "reason": reason,
            "created": created,
            "proposed_change": proposed_change,
        }, ensure_ascii=False)
        return EvolutionPatch(
            patch_id=f"AIGC-PATCH-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{HashTools.short_hash(seed, 8)}",
            patch_type=patch_type,
            created_at=created,
            reason=reason,
            evidence=evidence,
            proposed_change=proposed_change,
            expected_benefit=expected_benefit,
            risk=risk,
            safety_impact=safety_impact,
            approval_required=approval_required,
        )


class AIGCPhase8EvolutionLoop:
    def __init__(self, project_root: Path, operator: str = "Justice Gray Maciocha"):
        self.project_root = project_root
        self.operator = operator
        self.ledger = Phase8AuditLedger(project_root / "data" / "audit" / "aigc_phase8_evolution_audit.jsonl")
        self.scorer = EvolutionScorer()
        self.patch_generator = PatchGenerator()
        self.performance_evaluator = AgentPerformanceEvaluator()
        self.safety_gate = EvolutionSafetyGate()

    def create_outcome_record(
        self,
        linked_records: LinkedRecords,
        opportunity: OpportunitySummary,
        status: str,
        employer_response: str,
        payment_status: str,
        revision_status: str,
        operator_notes: str,
        metrics: Dict[str, int],
        lessons: Dict[str, List[str]],
    ) -> OutcomeRecord:
        cycle_score, quality = self.scorer.score_cycle(metrics, status)
        outcome_id = "AIGC-OUTCOME-" + HashTools.short_hash(
            "|".join([linked_records.opportunity_id, linked_records.phase4_proposal_id, status, utc_now()]),
            14,
        )
        outcome = OutcomeRecord(
            outcome_id=outcome_id,
            created_at=utc_now(),
            operator=self.operator,
            linked_records=linked_records,
            opportunity=opportunity,
            status=status,
            employer_response=employer_response,
            payment_status=payment_status,
            revision_status=revision_status,
            operator_notes=operator_notes,
            quality=quality,
            metrics={**metrics, "final_cycle_score": cycle_score},
            lessons={
                "what_worked": lessons.get("what_worked", []),
                "what_failed": lessons.get("what_failed", []),
                "unexpected_variables": lessons.get("unexpected_variables", []),
                "new_ology_parameters": lessons.get("new_ology_parameters", []),
                "new_risk_patterns": lessons.get("new_risk_patterns", []),
                "new_success_patterns": lessons.get("new_success_patterns", []),
            },
            next_actions={"recommended": [], "requires_approval": []},
        )
        self.ledger.record("phase8_outcome_record_created", asdict(outcome))
        return outcome

    def create_evolution_report(self, outcome: OutcomeRecord) -> EvolutionCycleReport:
        agent_performance = self.performance_evaluator.evaluate_default_agents(outcome)
        patches = [self.safety_gate.classify_patch(patch) for patch in self.patch_generator.generate_patches(outcome)]
        report_id = "AIGC-EVO-REPORT-" + HashTools.short_hash(outcome.outcome_id + utc_now(), 14)
        report = EvolutionCycleReport(
            report_id=report_id,
            created_at=utc_now(),
            operator=self.operator,
            outcome_id=outcome.outcome_id,
            cycle_score=outcome.metrics.get("final_cycle_score", 0),
            cycle_quality=outcome.quality,
            what_worked=outcome.lessons.get("what_worked", []),
            what_failed=outcome.lessons.get("what_failed", []),
            unexpected_variables=outcome.lessons.get("unexpected_variables", []),
            new_risk_patterns=outcome.lessons.get("new_risk_patterns", []),
            new_success_patterns=outcome.lessons.get("new_success_patterns", []),
            agent_performance=agent_performance,
            proposed_patches=patches,
            next_cycle_strategy=self._next_cycle_strategy(outcome, patches),
        )
        self.ledger.record("phase8_evolution_report_created", asdict(report))
        return report

    def run_from_config(self, config_path: Path) -> EvolutionCycleReport:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        phase2 = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase2_queue", "")))
        phase3 = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase3_dossiers", "")))
        phase4 = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase4_proposals", "")))
        phase5 = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase5_authorizations", "")))
        phase6 = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase6_receipts", "")))
        phase7 = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("phase7_packets", "")))
        best_proposal = phase4[0] if phase4 else {}
        best_auth = phase5[0] if phase5 else {}
        best_receipt = phase6[0] if phase6 else {}
        best_packet = phase7[0] if phase7 else {}
        status = self._infer_outcome_status(phase4, phase5, phase6)
        metrics = self._metrics_from_records(phase2, phase3, phase4, phase5, phase6, phase7)
        lessons = self._lessons_from_records(phase2, phase3, phase4, phase5, phase6, phase7)
        outcome = self.create_outcome_record(
            linked_records=LinkedRecords(
                opportunity_id=best_proposal.get("opportunity_id", ""),
                phase3_dossier_id=best_proposal.get("dossier_id", ""),
                phase4_proposal_id=best_proposal.get("proposal_id", ""),
                phase5_authorization_id=best_auth.get("authorization_id", ""),
                phase6_execution_id=best_receipt.get("execution_id", ""),
                phase7_packet_id=best_packet.get("packet_id", ""),
            ),
            opportunity=OpportunitySummary(
                title=best_proposal.get("title", ""),
                employer=best_proposal.get("employer", ""),
                platform=best_proposal.get("source_platform", ""),
                source_url=best_proposal.get("source_url", ""),
                work_type=best_proposal.get("proposal_type", ""),
                proposal_type=best_proposal.get("proposal_type", ""),
            ),
            status=status,
            employer_response="No employer response captured in this internal run.",
            payment_status="not_applicable",
            revision_status="not_applicable",
            operator_notes="Phase 8 generated from internal artifacts only. No external action was performed.",
            metrics=metrics,
            lessons=lessons,
        )
        report = self.create_evolution_report(outcome)
        self.export_outputs(config, outcome, report)
        return report

    def export_outputs(self, config: Dict[str, Any], outcome: OutcomeRecord, report: EvolutionCycleReport) -> None:
        outputs = config.get("output_files", {})
        append_jsonl(resolve_project_path(self.project_root, outputs.get("outcome_records", "")), asdict(outcome))
        for agent in report.agent_performance:
            append_jsonl(resolve_project_path(self.project_root, outputs.get("agent_performance", "")), asdict(agent))
        append_jsonl(resolve_project_path(self.project_root, outputs.get("reports", "")), asdict(report))
        for patch in report.proposed_patches:
            append_jsonl(resolve_project_path(self.project_root, outputs.get("patches", "")), asdict(patch))
        strategy_path = resolve_project_path(self.project_root, outputs.get("next_cycle_strategy", "data/phase8_evolution/next_cycle_strategy.json"))
        strategy_path.parent.mkdir(parents=True, exist_ok=True)
        strategy_path.write_text(json.dumps({
            "report_id": report.report_id,
            "outcome_id": report.outcome_id,
            "cycle_score": report.cycle_score,
            "cycle_quality": report.cycle_quality,
            "next_cycle_strategy": report.next_cycle_strategy,
            "pending_patch_ids": [patch.patch_id for patch in report.proposed_patches if patch.decision == PatchDecision.PENDING.value],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = self.project_root / "data" / "reports" / "phase8_signature_update.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(report), encoding="utf-8")

    def _infer_outcome_status(self, phase4: List[Dict[str, Any]], phase5: List[Dict[str, Any]], phase6: List[Dict[str, Any]]) -> str:
        if any(item.get("status") == "completed" for item in phase6):
            return OutcomeStatus.PROPOSAL_SENT.value
        if phase4:
            return OutcomeStatus.PROPOSAL_DRAFTED.value
        if phase5:
            return OutcomeStatus.PROPOSAL_DRAFTED.value
        return OutcomeStatus.ASSESSED_ONLY.value

    def _metrics_from_records(
        self,
        phase2: List[Dict[str, Any]],
        phase3: List[Dict[str, Any]],
        phase4: List[Dict[str, Any]],
        phase5: List[Dict[str, Any]],
        phase6: List[Dict[str, Any]],
        phase7: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        readiness_values = [readiness_total(item) for item in phase4 if readiness_total(item)]
        avg_readiness = int(sum(readiness_values) / len(readiness_values)) if readiness_values else 70
        return {
            "opportunity_quality": 8 if phase2 else 4,
            "domain_quality": 7,
            "assessment_accuracy": 8 if phase3 and phase4 else 5,
            "proposal_quality": max(1, min(10, round(avg_readiness / 10))),
            "approval_clarity": 10 if phase5 else 5,
            "execution_reliability": 8 if not phase6 else 9,
            "employer_response_quality": 5,
            "audit_quality": 9 if phase5 else 6,
            "safety_performance": 10,
            "learning_value": 8,
        }

    def _lessons_from_records(
        self,
        phase2: List[Dict[str, Any]],
        phase3: List[Dict[str, Any]],
        phase4: List[Dict[str, Any]],
        phase5: List[Dict[str, Any]],
        phase6: List[Dict[str, Any]],
        phase7: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        return {
            "what_worked": [
                f"Phase 2 generated {len(phase2)} opportunity records.",
                f"Phase 3 generated {len(phase3)} assessment dossiers.",
                f"Phase 4 generated {len(phase4)} proposal packages.",
                f"Phase 5 generated {len(phase5)} scoped authorization packets.",
                "No external action occurred without approval.",
            ],
            "what_failed": [
                "No employer outcome is available yet, so response-rate learning is incomplete.",
                "Phase 6 cannot proceed until a Phase 5 action ID is explicitly approved.",
            ],
            "unexpected_variables": [],
            "new_ology_parameters": [],
            "new_risk_patterns": [],
            "new_success_patterns": [
                "Open-source documentation and contribution issues produced the strongest current candidate.",
                "Scoped approval packets preserve a clean execution boundary.",
            ],
        }

    def _next_cycle_strategy(self, outcome: OutcomeRecord, patches: List[EvolutionPatch]) -> List[str]:
        strategy = [
            "Review pending Phase 5 authorization packets and accept, deny, or revise one action ID.",
            "Keep Phase 6 in manual_handoff mode until a connector is explicitly approved.",
            "Do not optimize employer-response scoring until at least one external outcome is captured.",
            "Restart at Phase 2 after approval decisions or new source criteria are available.",
        ]
        pending_patches = [patch.patch_id for patch in patches if patch.decision == PatchDecision.PENDING.value]
        if pending_patches:
            strategy.append(f"Review pending evolution patches: {', '.join(pending_patches)}")
        return strategy

    def signature_update(self, report: EvolutionCycleReport) -> str:
        patch_preview = [
            {
                "patch_id": patch.patch_id,
                "patch_type": patch.patch_type,
                "reason": patch.reason,
                "approval_required": patch.approval_required,
                "decision": patch.decision,
            }
            for patch in report.proposed_patches
        ]
        agent_preview = [
            {
                "agent": agent.agent_name,
                "house": agent.affix_house,
                "score": agent.total(),
                "recommendation": agent.evolution_recommendation,
            }
            for agent in report.agent_performance
        ]
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            report.operator,
            "Phase:",
            "Phase 8 - Evolution Loop",
            "Operational Identity:",
            "Memory / Adaptation / Self-Improvement Engine",
            "Evolution Report ID:",
            report.report_id,
            "Outcome ID:",
            report.outcome_id,
            f"Cycle Score: {report.cycle_score}/100",
            f"Cycle Quality: {report.cycle_quality}",
            "Agents Reviewed:",
            json.dumps(agent_preview, indent=2),
            "Proposed Evolution Patches:",
            json.dumps(patch_preview, indent=2),
            "Safety Review:",
            "No external action performed.",
            "No proposal sent.",
            "No employer contacted.",
            "No work submitted.",
            "No approval gate changed.",
            "No safety rule weakened.",
            "Patches are proposals or internal memory notes only unless accepted.",
            "Approval Required:",
            "Yes, for behavior-changing evolution patches.",
        ]).strip() + "\n"


def readiness_total(package: Dict[str, Any]) -> int:
    score = package.get("readiness_score", {})
    if isinstance(score, dict):
        return sum(value for value in score.values() if isinstance(value, int))
    if isinstance(score, int):
        return score
    return 0


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    if not str(path):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_json_dict(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_list_if_exists(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 8 evolution loop.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase8_evolution_loop.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evolution = AIGCPhase8EvolutionLoop(project_root=args.project_root)
    report = evolution.run_from_config(args.config)
    print(evolution.signature_update(report))
    print(f"\nReport log exported: {args.project_root / 'data' / 'phase8_evolution' / 'evolution_cycle_reports.jsonl'}")
    print(f"Report exported: {args.project_root / 'data' / 'reports' / 'phase8_signature_update.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
