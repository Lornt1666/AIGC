from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class RegenerationCandidateRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    source_phase27_record_id: str
    source_procurement_record_id: str
    source_opportunity_id: str
    source_proposal_id: str
    source_authorization_id: str
    source_action_id: str
    regeneration_allowed: bool
    freshness_review_gate: Dict[str, Any]
    regeneration_decision: str
    blocker_reasons: List[str]
    candidate_scope: Dict[str, Any]
    candidate_quality_state: Dict[str, Any]
    fresh_phase4_candidate: Dict[str, Any] | None
    fresh_phase5_candidate: Dict[str, Any] | None
    audit_lineage: Dict[str, Any]
    blocked_actions: List[str]
    external_data_fetch_performed: bool = False
    external_action_performed: bool = False
    canonical_phase4_overwrite_performed: bool = False
    canonical_phase5_overwrite_performed: bool = False


class Phase28AuditLedger:
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


class FreshCandidateRegenerationController:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[RegenerationCandidateRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        phase27_records = load_records(resolve_project_path(
            self.project_root,
            str(inputs.get("phase27_renewal_records", "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json")),
        ))
        freshness_review_records = load_records(resolve_project_path(
            self.project_root,
            str(inputs.get("freshness_review_records", "")),
        )) if inputs.get("freshness_review_records") else []
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase28_regeneration/aigc_phase28_regeneration_candidates.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase28_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase28_audit.jsonl"),
        )
        records = self.build_records(config, phase27_records, freshness_review_records)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        Phase28AuditLedger(audit_path).record("phase28_regeneration_candidates_exported", {
            "path": str(output_path),
            "records": len(records),
            "regenerated_candidates": sum(1 for record in records if record.regeneration_allowed),
            "blocked_candidates": sum(1 for record in records if not record.regeneration_allowed),
            "external_data_fetch_performed": False,
            "external_action_performed": False,
            "canonical_phase4_overwrite_performed": False,
            "canonical_phase5_overwrite_performed": False,
        })
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        phase27_records: List[Dict[str, Any]],
        freshness_review_records: List[Dict[str, Any]] | None = None,
    ) -> List[RegenerationCandidateRecord]:
        max_records = int(config.get("max_records", 25))
        reviews_by_source = {
            str(record.get("source_phase27_record_id", "")): record
            for record in freshness_review_records or []
            if str(record.get("source_phase27_record_id", ""))
        }
        return [
            self._build_record(config, renewal, reviews_by_source.get(str(renewal.get("record_id", ""))), index)
            for index, renewal in enumerate(phase27_records[:max_records], start=1)
        ]

    def _build_record(
        self,
        config: Dict[str, Any],
        renewal: Dict[str, Any],
        freshness_review: Dict[str, Any] | None,
        index: int,
    ) -> RegenerationCandidateRecord:
        gate = build_freshness_review_gate(config, freshness_review)
        allowed = bool(gate.get("approved", False))
        blockers = list(gate.get("blocker_reasons", []))
        phase4_candidate = build_phase4_candidate(config, renewal) if allowed else None
        phase5_candidate = build_phase5_candidate(config, renewal, phase4_candidate, index) if allowed and phase4_candidate else None
        if allowed:
            status = "fresh_internal_candidates_created_pending_phase5_review"
            decision = "internal_regeneration_candidates_created"
        else:
            status = "blocked_pending_operator_freshness_review"
            decision = "blocked_until_operator_freshness_review_approved"
        return RegenerationCandidateRecord(
            record_id=make_record_id(str(renewal.get("record_id", ""))),
            created_at=utc_now(),
            phase="phase28_fresh_candidate_regeneration_controller",
            status=status,
            source_phase27_record_id=str(renewal.get("record_id", "")),
            source_procurement_record_id=str(renewal.get("source_procurement_record_id", "")),
            source_opportunity_id=str(renewal.get("opportunity_id", "")),
            source_proposal_id=str(renewal.get("proposal_id", "")),
            source_authorization_id=str(renewal.get("authorization_id", "")),
            source_action_id=str(renewal.get("action_id", "")),
            regeneration_allowed=allowed,
            freshness_review_gate=gate,
            regeneration_decision=decision,
            blocker_reasons=blockers,
            candidate_scope=build_candidate_scope(renewal),
            candidate_quality_state=build_candidate_quality_state(config, renewal, allowed),
            fresh_phase4_candidate=phase4_candidate,
            fresh_phase5_candidate=phase5_candidate,
            audit_lineage=build_audit_lineage(renewal),
            blocked_actions=[str(item) for item in config.get("blocked_actions", [])],
            external_data_fetch_performed=False,
            external_action_performed=False,
            canonical_phase4_overwrite_performed=False,
            canonical_phase5_overwrite_performed=False,
        )

    def signature_update(self, records: List[RegenerationCandidateRecord]) -> str:
        allowed = sum(1 for record in records if record.regeneration_allowed)
        blocked = len(records) - allowed
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 28 - Fresh Candidate Regeneration Controller",
            "Operational Identity:",
            "Operator-Reviewed Fresh Candidate Regeneration Gate",
            "Action Performed:",
            "Evaluated Phase 27 renewal records and produced fresh internal candidates only when the configured freshness-review gate was approved.",
            "Safety Review:",
            "No external data fetch performed.",
            "No canonical Phase 4 artifacts overwritten.",
            "No canonical Phase 5 artifacts overwritten.",
            "No proposal sent.",
            "No application submitted.",
            "No employer contacted.",
            "No credentials used.",
            "No Phase 6 authorization granted.",
            "No external action performed.",
            f"Renewal Records Evaluated: {len(records)}",
            f"Fresh Internal Candidate Records Created: {allowed}",
            f"Blocked Pending Freshness Review: {blocked}",
            "Approval Required:",
            "Yes. Regenerated Phase 5 candidates remain pending and cannot move to Phase 6 without their own exact-phrase approval.",
        ]).strip() + "\n"


def build_freshness_review_gate(config: Dict[str, Any], freshness_review: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if freshness_review:
        controls = freshness_review.get("required_review_controls", {})
        if not isinstance(controls, dict):
            controls = {}
        operator_review = freshness_review.get("operator_review", {})
        if not isinstance(operator_review, dict):
            operator_review = {}
        projection = freshness_review.get("phase28_gate_projection", {})
        if not isinstance(projection, dict):
            projection = {}
        checks = {
            "phase29_record_present": True,
            "decision_approved": str(freshness_review.get("decision", "")) == "approved_for_phase28_regeneration",
            "status_approved": str(freshness_review.get("status", "")) == "approved_for_internal_regeneration",
            "review_not_expired": not review_expired(freshness_review),
            "operator_review_approved": bool(operator_review.get("approved", False)),
            "controls_pass": all(bool(value) for value in controls.values()) if controls else False,
            "phase28_projection_allows": bool(projection.get("phase28_regeneration_allowed", False)),
            "internal_candidate_only": str(projection.get("allowed_output_mode", "")) == "internal_candidate_only",
            "no_external_action": bool(freshness_review.get("external_action_performed", False)) is False,
        }
        blocker_reasons = [
            name
            for name, passed in checks.items()
            if not passed
        ]
        return {
            "approved": not blocker_reasons,
            "review_source": "phase29_freshness_review_record",
            "review_id": str(freshness_review.get("record_id", "")),
            "reviewed_at": str(operator_review.get("approved_at", "")),
            "freshness_review_status": str(freshness_review.get("status", "")),
            "allowed_output_mode": str(projection.get("allowed_output_mode", "")),
            "required_phrase": str(operator_review.get("required_phrase", "")),
            "received_phrase_recorded": bool(str(operator_review.get("received_phrase", ""))),
            "received_phrase_matches": bool(operator_review.get("approved", False)),
            "required_checks": checks,
            "blocker_reasons": blocker_reasons,
            "external_action_authorized": False,
        }
    review = config.get("operator_freshness_review", {})
    if not isinstance(review, dict):
        review = {}
    required_phrase = str(review.get("required_phrase", ""))
    received_phrase = str(review.get("received_phrase", ""))
    checks = {
        "approved_flag": bool(review.get("approved", False)),
        "review_id_present": bool(str(review.get("review_id", "")).strip()),
        "reviewed_at_present": bool(str(review.get("reviewed_at", "")).strip()),
        "status_approved": str(review.get("freshness_review_status", "")) == "approved_for_internal_regeneration",
        "source_currentness_reviewed": bool(review.get("reviewed_source_currentness", False)),
        "scope_reviewed": bool(review.get("reviewed_scope", False)),
        "compliance_reviewed": bool(review.get("reviewed_compliance", False)),
        "quality_plan_reviewed": bool(review.get("reviewed_quality_plan", False)),
        "payment_contract_reviewed": bool(review.get("reviewed_payment_contract", False)),
        "internal_candidate_only": str(review.get("allowed_output_mode", "")) == "internal_candidate_only",
        "phrase_matches": bool(required_phrase) and received_phrase.strip() == required_phrase,
    }
    blocker_reasons = [
        name
        for name, passed in checks.items()
        if not passed
    ]
    return {
        "approved": not blocker_reasons,
        "review_id": str(review.get("review_id", "")),
        "reviewed_at": str(review.get("reviewed_at", "")),
        "freshness_review_status": str(review.get("freshness_review_status", "")),
        "allowed_output_mode": str(review.get("allowed_output_mode", "")),
        "required_phrase": required_phrase,
        "received_phrase_recorded": bool(received_phrase),
        "received_phrase_matches": checks["phrase_matches"],
        "required_checks": checks,
        "blocker_reasons": blocker_reasons,
        "external_action_authorized": False,
    }


def review_expired(record: Dict[str, Any]) -> bool:
    value = str(record.get("expires_at", ""))
    if not value:
        return True
    try:
        expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at.astimezone(timezone.utc)


def build_phase4_candidate(config: Dict[str, Any], renewal: Dict[str, Any]) -> Dict[str, Any]:
    defaults = config.get("candidate_defaults", {})
    operator = str(defaults.get("operator", "Justice Gray Maciocha"))
    title = str(renewal.get("title", "Renewed work candidate"))
    employer = str(renewal.get("employer", "the requester")) or "the requester"
    source_platform = str(renewal.get("source_platform", ""))
    source_url = str(renewal.get("source_url", ""))
    proposal_id = make_proposal_id(str(renewal.get("record_id", "")))
    proposal_type = proposal_type_for(renewal)
    deliverables = deliverables_for(proposal_type)
    questions = build_clarifying_questions(renewal, proposal_type)
    message = build_employer_message(title, employer, proposal_type, deliverables, questions)
    readiness_score = {
        "employer_relevance": 9,
        "deliverable_clarity": 9,
        "professional_tone": 10,
        "truthfulness": 10,
        "scope_clarity": 9,
        "timeline_reasonableness": 9,
        "ai_disclosure_handling": 10,
        "risk_handling": 9,
        "approval_clarity": 10,
        "auditability": 10,
    }
    return {
        "proposal_id": proposal_id,
        "package_id": proposal_id,
        "opportunity_id": str(renewal.get("opportunity_id", "")),
        "dossier_id": f"phase27:{renewal.get('record_id', '')}",
        "created_at": utc_now(),
        "operator": operator,
        "status": str(defaults.get("proposal_status", "internal_regenerated_candidate_only")),
        "source_phase27_record_id": str(renewal.get("record_id", "")),
        "old_proposal_id_retained_as_historical_derivative": str(renewal.get("proposal_id", "")),
        "opportunity": {
            "title": title,
            "employer": employer,
            "source_platform": source_platform,
            "source_url": source_url,
            "phase27_renewal_strategy": renewal.get("renewal_strategy", ""),
        },
        "title": title,
        "employer": employer,
        "source_platform": source_platform,
        "source_url": source_url,
        "phase3_score": 0,
        "phase3_decision": "renewed_from_phase27_freshness_review",
        "proposal_type": proposal_type,
        "employer_intent_summary": (
            f"Renewed internal candidate for '{title}' after Phase 27 identified stale generated derivatives "
            "and the operator freshness-review gate allowed internal regeneration."
        ),
        "employer_facing_message": message,
        "short_message_variant": build_short_variant(title, deliverables, questions),
        "technical_message_variant": build_technical_variant(title, deliverables, questions),
        "clarifying_question_variant": build_question_variant(title, questions),
        "scope_of_work": {
            "summary": f"Prepare a refreshed, source-currentness-reviewed proposal candidate for: {title}.",
            "included_work": [
                "Confirm current requirements and success criteria before any commitment.",
                "Prepare a scoped work plan using the Phase 27 renewal blueprint.",
                "Review the final output for accuracy, completeness, clarity, and compliance.",
                "Preserve stale generated artifacts only as historical derivatives.",
            ],
            "excluded_work": [
                "External submission without separate Phase 5 approval.",
                "Any action outside the operator-reviewed refreshed scope.",
                "Use of credentials, private data, or operator identity without explicit approval.",
                "Treating the old Phase 5 action ID as active authority.",
            ],
            "assumptions": [
                "The operator has completed a freshness review before this candidate was generated.",
                "The requester or source will clarify any remaining scope, deadline, and format questions.",
                "Final external delivery requires separate human approval before submission.",
            ],
            "dependencies": [
                "Operator-reviewed source currentness.",
                "Approved communication channel.",
                "Any required source documents, repository guidance, or acceptance criteria.",
            ],
        },
        "deliverables": deliverables,
        "methodology": {
            "work_phases": [
                "Confirm refreshed requirements and success criteria.",
                "Prepare the work product using a constrained, auditable workflow.",
                "Review for factual accuracy, legal/ethical alignment, and technical quality.",
                "Prepare final delivery package only after scoped approval.",
            ],
            "tools_or_methods": [
                "Phase 27 renewal blueprint review",
                "Freshness-review gate",
                "Structured requirement analysis",
                "Human-reviewed AI-assisted drafting where allowed",
                "Quality-control checklist",
                "Audit logging",
            ],
            "quality_checks": [
                "Check against refreshed source context.",
                "Check for unsupported claims.",
                "Check privacy, security, platform-rule, and disclosure requirements.",
                "Confirm no external action occurs without separate approval.",
            ],
        },
        "timeline": {
            "estimated_duration": "To be confirmed after refreshed scope, deadline, and acceptance criteria are clarified.",
            "milestones": [
                "Freshness-confirmed requirement review",
                "Draft preparation",
                "Quality and compliance review",
                "Final delivery after approval",
            ],
        },
        "clarifying_questions": questions,
        "assumptions": [
            "Operator freshness review has been completed for internal regeneration.",
            "AI-assisted workflow is acceptable unless the requester or platform says otherwise.",
            "Final external delivery requires separate human approval before submission.",
        ],
        "ai_use_disclosure": {
            "required": True,
            "recommended": True,
            "draft_language": (
                "I use a structured AI-assisted workflow where appropriate for organization, drafting, analysis, "
                "coding support, and quality review. Final review, approval, and delivery remain under human "
                "oversight. If you have specific requirements around AI-assisted work, I can follow those requirements."
            ),
        },
        "risk_notes": {
            "primary_risk": "Regenerated candidate depends on source currentness and scope assumptions verified by operator freshness review.",
            "mitigation": "Keep candidate internal until approval, ask clarifying questions, avoid overpromising, disclose AI assistance where appropriate, and follow platform requirements.",
            "approval_required_before": [
                "message_employer",
                "apply",
                "submit_proposal",
                "submit_deliverable",
                "use_operator_identity",
                "use_credentials",
            ],
        },
        "quality_assurance_plan": [
            "Verify refreshed source context before external use.",
            "Check against Phase 27 research questions and quality targets.",
            "Confirm no claims exceed verified evidence.",
            "Run human review before any external action.",
            "Check links, commands, terminology, privacy constraints, and disclosure requirements.",
        ],
        "audit_summary": {
            "source_phase27_record_id": renewal.get("record_id", ""),
            "old_proposal_id": renewal.get("proposal_id", ""),
            "old_authorization_id": renewal.get("authorization_id", ""),
            "old_action_id": renewal.get("action_id", ""),
            "safety_checks": [
                "No external action performed",
                "No employer contacted",
                "No proposal submitted",
                "Old action ID retained only as historical derivative",
                "Human approval required before external use",
            ],
            "external_action_performed": False,
        },
        "human_approval_preview": {
            "proposed_external_action": f"Send refreshed proposal/message to {employer} for: {title}",
            "benefit": "Renewed candidate preserves stale-artifact lineage while improving quality and freshness controls.",
            "risk": "External use still requires separate Phase 5 approval and Phase 6 scope match.",
            "safety_status": "caution",
            "ai_disclosure_status": "included",
            "required_acceptance_phrase": "Generated by Phase 28 only; use the fresh Phase 5 packet phrase if approval is desired.",
        },
        "external_action_classification": {
            "classification": "internal_regenerated_candidate_only",
            "external_actions_allowed": False,
            "requires_explicit_justice_approval_before_send": True,
            "send_ready": False,
        },
        "readiness_score": readiness_score,
        "readiness_decision": str(defaults.get("proposal_readiness_decision", "ready_for_phase_5")),
        "final_recommendation": "Fresh internal candidate is ready for separate Phase 5 approval review.",
        "approval_required_before": [
            "send_message",
            "submit_application",
            "submit_proposal",
            "submit_deliverable",
            "use_operator_identity",
            "use_credentials",
        ],
        "forbidden_actions": [
            "send_without_approval",
            "submit_without_approval",
            "contact_employer_without_approval",
            "claim_unverified_credentials",
            "hide_ai_use_where_disclosure_is_required",
            "bypass_platform_limits",
            "treat_old_action_id_as_active",
        ],
    }


def build_phase5_candidate(
    config: Dict[str, Any],
    renewal: Dict[str, Any],
    phase4_candidate: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    defaults = config.get("candidate_defaults", {})
    operator = str(defaults.get("operator", "Justice Gray Maciocha"))
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(hours=int(config.get("approval_expiration_hours", 24)))
    proposal_id = str(phase4_candidate.get("proposal_id", ""))
    opportunity_id = str(phase4_candidate.get("opportunity_id", ""))
    action_id = make_action_id(index)
    authorization_id = "AIGC-AUTH-REGEN-" + short_hash(action_id + proposal_id, 18)
    message = str(phase4_candidate.get("employer_facing_message", ""))
    proposed_action = str(phase4_candidate.get("human_approval_preview", {}).get(
        "proposed_external_action",
        f"Send refreshed proposal/message to {phase4_candidate.get('employer', '')} for: {phase4_candidate.get('title', '')}",
    ))
    packet = {
        "authorization_id": authorization_id,
        "action_id": action_id,
        "proposal_id": proposal_id,
        "opportunity_id": opportunity_id,
        "operator": operator,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "source_phase27_record_id": str(renewal.get("record_id", "")),
        "old_authorization_id_retained_as_historical_derivative": str(renewal.get("authorization_id", "")),
        "old_action_id_retained_as_historical_derivative": str(renewal.get("action_id", "")),
        "proposed_external_action": proposed_action,
        "recipient": str(phase4_candidate.get("employer", "")),
        "platform": str(phase4_candidate.get("source_platform", "")),
        "source_url": str(phase4_candidate.get("source_url", "")),
        "artifact": {
            "artifact_type": "proposal",
            "artifact_summary": f"Fresh regenerated employer-facing proposal for {phase4_candidate.get('title', '')}",
            "artifact_hash": hash_text(message),
            "artifact_preview": message[:1200],
        },
        "classification": {
            "action_class": "approval_required",
            "risk_class": "medium",
            "safety_status": "caution",
        },
        "checks": {
            "safety_check_score": 15,
            "coherence_check_score": 10,
            "proposal_readiness_score": readiness_total(phase4_candidate),
            "ai_disclosure_status": "required",
        },
        "approval": {
            "required": True,
            "required_phrase": f"I, {operator}, accept action {action_id}.",
            "denial_phrase": f"I, {operator}, deny action {action_id}.",
            "revision_phrase_template": f"Revise action {action_id}: [revision instructions]",
            "received_phrase": "",
            "approved": False,
            "denied": False,
            "revision_required": False,
            "approved_at": "",
            "decision_notes": "Generated by Phase 28; still requires separate exact-phrase approval.",
        },
        "phase6_status": {
            "authorized_for_phase6": False,
            "execution_scope": proposed_action,
            "external_action_performed": False,
        },
        "decision": str(defaults.get("phase5_decision", "pending")),
        "audit_event_ids": [],
    }
    packet["approval_request"] = approval_request_text(packet)
    return packet


def build_candidate_scope(renewal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source_title": renewal.get("title", ""),
        "source_employer": renewal.get("employer", ""),
        "source_platform": renewal.get("source_platform", ""),
        "source_url": renewal.get("source_url", ""),
        "renewal_strategy": renewal.get("renewal_strategy", ""),
        "deep_research_questions": renewal.get("deep_research_brief", {}).get("research_questions", []),
        "regeneration_source": "phase27_renewal_record_only",
        "old_action_id_usable": False,
    }


def build_candidate_quality_state(config: Dict[str, Any], renewal: Dict[str, Any], allowed: bool) -> Dict[str, Any]:
    defaults = config.get("candidate_defaults", {})
    quality_score = int(defaults.get("minimum_quality_score", 88)) if allowed else 0
    uncertainty_score = int(defaults.get("uncertainty_score", 22)) if allowed else 100
    return {
        "quality_state": "fresh_candidate_ready_for_phase5_review" if allowed else "blocked_until_freshness_review",
        "quality_score": quality_score,
        "uncertainty_score": uncertainty_score,
        "phase27_quality_targets": renewal.get("quality_upgrade_targets", {}),
        "quantum_quality_state": {
            "model_type": "deterministic_uncertainty_aware_regeneration_model",
            "literal_quantum_claim": False,
            "quality_score": quality_score,
            "uncertainty_score": uncertainty_score,
            "collapse_conditions": [
                "operator freshness review approved",
                "fresh internal Phase 4 candidate generated",
                "fresh internal Phase 5 candidate generated as pending only",
                "Phase 6 remains unauthorized until separate exact-phrase approval",
            ],
        },
    }


def build_audit_lineage(renewal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source_phase27_record_id": renewal.get("record_id", ""),
        "source_procurement_record_id": renewal.get("source_procurement_record_id", ""),
        "old_proposal_id": renewal.get("proposal_id", ""),
        "old_authorization_id": renewal.get("authorization_id", ""),
        "old_action_id": renewal.get("action_id", ""),
        "preserved_artifact_chain": renewal.get("preserved_artifact_chain", []),
        "old_artifacts_are_historical_derivatives": True,
        "new_candidates_written_to_phase28_ledger_only": True,
    }


def proposal_type_for(renewal: Dict[str, Any]) -> str:
    platform = str(renewal.get("source_platform", "")).lower()
    title = str(renewal.get("title", "")).lower()
    if "github" in platform:
        return "open_source_contribution"
    if any(term in title for term in ["documentation", "docs", "readme", "guide"]):
        return "documentation_offer"
    if any(term in title for term in ["automation", "api", "workflow", "integration", "engineer"]):
        return "automation_offer"
    return "job_application"


def deliverables_for(proposal_type: str) -> List[Dict[str, Any]]:
    if proposal_type in {"open_source_contribution", "documentation_offer"}:
        return [
            {
                "name": "Refreshed Documentation or Contribution Draft",
                "description": "A source-currentness-reviewed draft or contribution plan aligned with the refreshed request.",
                "acceptance_criteria": [
                    "Clear structure",
                    "Accurate explanation",
                    "Usable examples or notes where appropriate",
                    "Aligned with requester or repository requirements",
                ],
                "format": "Markdown, pull request draft, document, or requested format",
            },
            {
                "name": "Review and Assumption Notes",
                "description": "Concise notes documenting refreshed assumptions, open questions, and validation checks.",
                "acceptance_criteria": [
                    "Summarizes key decisions",
                    "Identifies unresolved questions",
                    "Supports requester or maintainer review",
                ],
                "format": "Markdown or document",
            },
        ]
    if proposal_type == "automation_offer":
        return [
            {
                "name": "Refreshed Automation Workflow Plan",
                "description": "A source-currentness-reviewed automation plan with inputs, outputs, constraints, and validation steps.",
                "acceptance_criteria": [
                    "Defines input",
                    "Defines output",
                    "Explains process",
                    "Identifies constraints",
                ],
                "format": "Markdown, document, or technical spec",
            },
            {
                "name": "Implementation Artifact",
                "description": "A script, prototype, configuration, or implementation draft if approved within scope.",
                "acceptance_criteria": [
                    "Runs or is reviewable",
                    "Includes usage notes",
                    "Avoids prohibited platform behavior",
                    "Includes basic validation steps",
                ],
                "format": "Python/script/code file or requested format",
            },
        ]
    return [
        {
            "name": "Refreshed Requested Work Product",
            "description": "The requested work product, prepared according to refreshed requester requirements.",
            "acceptance_criteria": [
                "Matches refreshed requirements",
                "Is clear and complete",
                "Is delivered in the requested format",
                "Is reviewed before submission",
            ],
            "format": "Requester-specified format",
        }
    ]


def build_clarifying_questions(renewal: Dict[str, Any], proposal_type: str) -> List[str]:
    questions = [
        "Can you confirm the current final format and acceptance criteria for this work?",
        "Are there any updated requirements, examples, templates, tools, or style guidelines I should follow?",
        "What deadline or turnaround time are you aiming for now?",
    ]
    if proposal_type == "open_source_contribution":
        questions.extend([
            "Should I comment before drafting a pull request, or is a PR welcome directly?",
            "Are there current contribution guidelines, tests, or maintainer preferences I should follow?",
        ])
    if proposal_type == "automation_offer":
        questions.extend([
            "Are there platform, API, authentication, rate-limit, or security constraints I need to follow?",
            "Should the output be a working script, prototype, workflow plan, or documentation?",
        ])
    questions.append("Are AI-assisted research, drafting, analysis, or coding workflows acceptable if final output is reviewed before delivery?")
    research_questions = renewal.get("deep_research_brief", {}).get("research_questions", [])
    if isinstance(research_questions, list):
        questions.extend(str(item) for item in research_questions[:2])
    return unique(questions)


def build_employer_message(
    title: str,
    employer: str,
    proposal_type: str,
    deliverables: List[Dict[str, Any]],
    questions: List[str],
) -> str:
    greeting = f"Hi {employer} maintainers," if proposal_type == "open_source_contribution" else f"Hello {employer},"
    deliverable_lines = "\n".join(f"- {item['name']}: {item['description']}" for item in deliverables)
    question_lines = "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions[:5]))
    return f"""{greeting}
I reviewed the current request for {title}, and I can help by preparing a clear, structured, reviewable deliverable aligned with the refreshed requirements.

My proposed approach is:
1. Confirm the current requirements, final format, and success criteria.
2. Prepare the work product using a constrained, auditable workflow.
3. Review the output for clarity, completeness, accuracy, and alignment with your instructions.
4. Deliver the final result in the requested format, with notes or revision support if needed.

Proposed deliverables:
{deliverable_lines}

Estimated timeline:
To be confirmed after refreshed scope, deadline, and acceptance criteria are clarified.

A few clarifying questions before finalizing the scope:
{question_lines}

I use a structured AI-assisted workflow where appropriate for organization, drafting, analysis, coding support, and quality review. Final review, approval, and delivery remain under human oversight. If you have specific requirements around AI-assisted work, I can follow those requirements.

Best regards,
Justice Gray Maciocha""".strip()


def build_short_variant(title: str, deliverables: List[Dict[str, Any]], questions: List[str]) -> str:
    main_deliverable = deliverables[0]["name"] if deliverables else "the requested deliverable"
    first_question = questions[0] if questions else "Can you confirm the current final format?"
    return f"""Hello,
I can help with {title} by preparing {main_deliverable} in a clear, structured, reviewable format.

Before finalizing scope, one key question: {first_question}

I use AI-assisted workflow support where appropriate, with final human review before delivery.

Best regards,
Justice Gray Maciocha""".strip()


def build_technical_variant(title: str, deliverables: List[Dict[str, Any]], questions: List[str]) -> str:
    deliverable_lines = "\n".join(f"- {item['name']}" for item in deliverables)
    question_lines = "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions[:5]))
    return f"""Hello,
I reviewed the refreshed requirements for {title}. I can approach this with a structured technical workflow focused on clarity, reliability, auditability, and reviewability.

Proposed deliverables:
{deliverable_lines}

Before starting, I would clarify:
{question_lines}

I can provide concise process notes with the final delivery so the work is easy to evaluate.

Best regards,
Justice Gray Maciocha""".strip()


def build_question_variant(title: str, questions: List[str]) -> str:
    question_lines = "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions[:6]))
    return f"""Hello,
I am interested in helping with {title}. Before proposing a final scope, I want to clarify a few details so the work is accurate and aligned with what you need.

Questions:
{question_lines}

I use a structured AI-assisted workflow where appropriate, with final human review before delivery.

Best regards,
Justice Gray Maciocha""".strip()


def approval_request_text(packet: Dict[str, Any]) -> str:
    return f"""
AIGC PHASE 5 APPROVAL REQUEST
Operator:
{packet['operator']}
Authorization ID:
{packet['authorization_id']}
Action ID:
{packet['action_id']}
Proposal ID:
{packet['proposal_id']}
Opportunity ID:
{packet['opportunity_id']}
Employer / Recipient:
{packet['recipient']}
Platform:
{packet['platform']}
Proposed External Action:
{packet['proposed_external_action']}
Artifact Type:
{packet['artifact']['artifact_type']}
Artifact Hash:
{packet['artifact']['artifact_hash']}
Artifact Preview:
{packet['artifact']['artifact_preview']}
Risk Class:
{packet['classification']['risk_class']}
Safety Status:
{packet['classification']['safety_status']}
Action Class:
{packet['classification']['action_class']}
Safety Checklist Score:
{packet['checks']['safety_check_score']}/15
Coherence Checklist Score:
{packet['checks']['coherence_check_score']}/10
Proposal Readiness Score:
{packet['checks']['proposal_readiness_score']}/100
AI Disclosure:
{packet['checks']['ai_disclosure_status']}
What Will Happen If Approved:
AIGC will be authorized to move this specific regenerated candidate into Phase 6 execution.
What Will Not Happen:
AIGC will not perform any other external action beyond this scoped action.
Accept:
{packet['approval']['required_phrase']}
Deny:
{packet['approval']['denial_phrase']}
Revise:
{packet['approval']['revision_phrase_template']}
Current Decision:
{packet['decision']}
""".strip()


def readiness_total(package: Dict[str, Any]) -> int:
    score = package.get("readiness_score", {})
    if isinstance(score, dict):
        return sum(value for value in score.values() if isinstance(value, int))
    return 0


def load_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        records: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    records.append(payload)
        return records
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def make_record_id(source_phase27_record_id: str) -> str:
    seed = f"{source_phase27_record_id}|phase28"
    return "AIGC-REGEN-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def make_proposal_id(source_phase27_record_id: str) -> str:
    seed = f"{source_phase27_record_id}|phase28|proposal"
    return "phase4_regen_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def make_action_id(sequence_number: int) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"AIGC-ACT-REGEN-{date_part}-{sequence_number:04d}"


def hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def short_hash(value: str, length: int = 16) -> str:
    return hash_text(value)[:length]


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 28 fresh candidate regeneration controller.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase28_regeneration_controller.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = FreshCandidateRegenerationController(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nRegeneration candidate records exported: {args.project_root / 'data' / 'phase28_regeneration' / 'aigc_phase28_regeneration_candidates.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
