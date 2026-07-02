from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class FidelityCheck:
    name: str
    status: str
    score_delta: int
    evidence: str
    recommendation: str


@dataclass
class FidelityReview:
    review_id: str
    created_at: str
    phase: str
    status: str
    opportunity_id: str
    proposal_id: str
    dossier_id: str
    team_id: str
    compliance_review_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    readiness_decision: str
    compliance_status: str
    fidelity_score: int
    quality_status: str
    checks: List[FidelityCheck]
    risk_flags: List[str]
    revision_recommendations: List[str]
    approval_required_before_external_action: bool = True
    external_action_performed: bool = False


class Phase20AuditLedger:
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


class FidelityForge:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[FidelityReview]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        assessments = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("assessments", "")))
        proposals = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("proposals", "")))
        team_plans = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("subagent_team_plans", "")))
        compliance_reviews = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("compliance_reviews", "")))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase20_fidelity/aigc_phase20_fidelity_reviews.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase20_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase20_audit.jsonl"),
        )
        reviews = self.build_reviews(
            config=config,
            assessments=assessments,
            proposals=proposals,
            team_plans=team_plans,
            compliance_reviews=compliance_reviews,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([review_to_dict(review) for review in reviews], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Phase20AuditLedger(audit_path).record("phase20_fidelity_reviews_exported", {
            "path": str(output_path),
            "reviews": len(reviews),
            "external_action_performed": False,
        })
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(reviews), encoding="utf-8")
        return reviews

    def build_reviews(
        self,
        config: Dict[str, Any],
        assessments: List[Dict[str, Any]],
        proposals: List[Dict[str, Any]],
        team_plans: List[Dict[str, Any]],
        compliance_reviews: List[Dict[str, Any]],
    ) -> List[FidelityReview]:
        eligible = set(str(item) for item in config.get("eligible_readiness_decisions", []))
        max_reviews = int(config.get("max_reviews", 25))
        assessments_by_id = {str(item.get("opportunity_id", "")): item for item in assessments}
        teams_by_proposal = {str(item.get("proposal_id", "")): item for item in team_plans}
        compliance_by_proposal = {str(item.get("proposal_id", "")): item for item in compliance_reviews}
        reviews: List[FidelityReview] = []
        for proposal in proposals:
            if eligible and str(proposal.get("readiness_decision", "")) not in eligible:
                continue
            proposal_id = str(proposal.get("proposal_id", ""))
            opportunity_id = str(proposal.get("opportunity_id", ""))
            reviews.append(self._build_review(
                config=config,
                proposal=proposal,
                assessment=assessments_by_id.get(opportunity_id, {}),
                team_plan=teams_by_proposal.get(proposal_id, {}),
                compliance=compliance_by_proposal.get(proposal_id, {}),
            ))
            if len(reviews) >= max_reviews:
                break
        return reviews

    def _build_review(
        self,
        config: Dict[str, Any],
        proposal: Dict[str, Any],
        assessment: Dict[str, Any],
        team_plan: Dict[str, Any],
        compliance: Dict[str, Any],
    ) -> FidelityReview:
        checks = [
            self._check_source_traceability(proposal, assessment),
            self._check_proposal_message(proposal),
            self._check_ai_disclosure(proposal),
            self._check_deliverables(proposal),
            self._check_scope_boundaries(proposal),
            self._check_clarifying_questions(proposal),
            self._check_subagent_team(team_plan, int(config.get("expected_min_subagents", 5))),
            self._check_compliance(compliance),
            self._check_external_action_blocked(proposal, team_plan, compliance),
            self._check_auditability(proposal, team_plan),
        ]
        score = max(0, min(100, 100 + sum(check.score_delta for check in checks)))
        thresholds = config.get("thresholds", {})
        quality_status = quality_status_for_score(
            score,
            high=int(thresholds.get("high_fidelity", 90)),
            ready=int(thresholds.get("ready_with_minor_review", 80)),
            revision=int(thresholds.get("revision_recommended", 65)),
        )
        risk_flags = collect_risk_flags(checks, compliance)
        recommendations = unique([
            check.recommendation
            for check in checks
            if check.status in {"warning", "failed"} and check.recommendation
        ])
        proposal_id = str(proposal.get("proposal_id", ""))
        opportunity_id = str(proposal.get("opportunity_id", assessment.get("opportunity_id", "")))
        return FidelityReview(
            review_id=make_review_id(proposal_id, opportunity_id, str(team_plan.get("team_id", ""))),
            created_at=utc_now(),
            phase="phase20_fidelity_forge",
            status="internal_review_only",
            opportunity_id=opportunity_id,
            proposal_id=proposal_id,
            dossier_id=str(proposal.get("dossier_id", assessment.get("dossier_id", ""))),
            team_id=str(team_plan.get("team_id", "")),
            compliance_review_id=str(compliance.get("review_id", "")),
            title=str(proposal.get("title") or assessment.get("title") or ""),
            employer=str(proposal.get("employer") or assessment.get("employer") or ""),
            source_platform=str(proposal.get("source_platform") or assessment.get("source_platform") or ""),
            source_url=str(proposal.get("source_url") or assessment.get("source_url") or ""),
            readiness_decision=str(proposal.get("readiness_decision", "")),
            compliance_status=str(compliance.get("compliance_status", "missing")),
            fidelity_score=score,
            quality_status=quality_status,
            checks=checks,
            risk_flags=risk_flags,
            revision_recommendations=recommendations,
            approval_required_before_external_action=True,
            external_action_performed=False,
        )

    def _check_source_traceability(self, proposal: Dict[str, Any], assessment: Dict[str, Any]) -> FidelityCheck:
        source_url = str(proposal.get("source_url") or assessment.get("source_url") or "")
        if source_url.startswith(("http://", "https://")):
            return pass_check("source_traceability", "Source URL is present and traceable.")
        return fail_check(
            "source_traceability",
            -12,
            "No traceable source URL was found.",
            "Add or repair source_url before downstream review.",
        )

    def _check_proposal_message(self, proposal: Dict[str, Any]) -> FidelityCheck:
        message = str(proposal.get("employer_facing_message", ""))
        if len(message.strip()) >= 200:
            return pass_check("proposal_message_present", "Employer-facing proposal message is present.")
        return fail_check(
            "proposal_message_present",
            -15,
            "Employer-facing message is missing or too short.",
            "Regenerate Phase 4 proposal text before approval review.",
        )

    def _check_ai_disclosure(self, proposal: Dict[str, Any]) -> FidelityCheck:
        disclosure = proposal.get("ai_use_disclosure", {})
        if not isinstance(disclosure, dict):
            return fail_check(
                "ai_disclosure_preserved",
                -14,
                "AI-use disclosure object is missing.",
                "Add AI-use disclosure before any approval packet is considered.",
            )
        draft = str(disclosure.get("draft_language", "")).strip()
        required_or_recommended = bool(disclosure.get("required") or disclosure.get("recommended"))
        message_blob = proposal_message_blob(proposal)
        if draft and draft in message_blob:
            return pass_check("ai_disclosure_preserved", "AI-use disclosure language is preserved in proposal text.")
        if draft and required_or_recommended:
            return warn_check(
                "ai_disclosure_preserved",
                -5,
                "Disclosure language exists but was not found in proposal message variants.",
                "Insert the disclosure language into the external-facing variant before Phase 5 approval.",
            )
        return fail_check(
            "ai_disclosure_preserved",
            -14,
            "Required or recommended AI-use disclosure language is missing.",
            "Regenerate Phase 4 with disclosure language preserved.",
        )

    def _check_deliverables(self, proposal: Dict[str, Any]) -> FidelityCheck:
        deliverables = proposal.get("deliverables", [])
        if isinstance(deliverables, list) and deliverables:
            criteria_count = sum(
                len(item.get("acceptance_criteria", []))
                for item in deliverables
                if isinstance(item, dict) and isinstance(item.get("acceptance_criteria", []), list)
            )
            if criteria_count > 0:
                return pass_check("deliverables_present", "Deliverables and acceptance criteria are present.")
        return fail_check(
            "deliverables_present",
            -12,
            "Deliverables or acceptance criteria are missing.",
            "Add deliverables with acceptance criteria before approval review.",
        )

    def _check_scope_boundaries(self, proposal: Dict[str, Any]) -> FidelityCheck:
        scope = proposal.get("scope_of_work")
        forbidden = proposal.get("forbidden_actions", [])
        approval_required = proposal.get("approval_required_before")
        if scope and isinstance(forbidden, list) and forbidden and approval_required:
            return pass_check("scope_boundaries_present", "Scope, forbidden actions, and approval boundary are present.")
        return warn_check(
            "scope_boundaries_present",
            -8,
            "Scope boundaries are incomplete.",
            "Make scope, forbidden actions, and approval boundary explicit before Phase 5.",
        )

    def _check_clarifying_questions(self, proposal: Dict[str, Any]) -> FidelityCheck:
        questions = proposal.get("clarifying_questions", [])
        if isinstance(questions, list) and questions:
            return pass_check("clarifying_questions_present", "Clarifying questions are present.")
        return warn_check(
            "clarifying_questions_present",
            -4,
            "No clarifying questions were found.",
            "Add clarifying questions for unknowns before external review.",
        )

    def _check_subagent_team(self, team_plan: Dict[str, Any], expected_min_subagents: int) -> FidelityCheck:
        members = team_plan.get("team_members", [])
        if not isinstance(members, list) or len(members) < expected_min_subagents:
            return fail_check(
                "subagent_team_present",
                -12,
                "No adequate Phase 19 sub-agent team plan was found.",
                "Run Phase 19 or repair the team plan before fidelity signoff.",
            )
        unsafe_members = [
            item.get("role", "")
            for item in members
            if isinstance(item, dict) and item.get("external_action_allowed") is not False
        ]
        if unsafe_members:
            return fail_check(
                "subagent_team_present",
                -16,
                f"Sub-agent members allow external action: {', '.join(str(item) for item in unsafe_members)}.",
                "Set all sub-agent records to internal-only and rerun Phase 19.",
            )
        return pass_check("subagent_team_present", f"Phase 19 team contains {len(members)} internal-only sub-agent roles.")

    def _check_compliance(self, compliance: Dict[str, Any]) -> FidelityCheck:
        status = str(compliance.get("compliance_status", "missing"))
        if status == "green":
            return pass_check("compliance_review_present", "Compliance review is green.")
        if status == "yellow":
            return warn_check(
                "compliance_review_present",
                -4,
                "Compliance review is yellow.",
                "Resolve compliance required actions or document operator review before external action.",
            )
        if status == "orange":
            return warn_check(
                "compliance_review_present",
                -8,
                "Compliance review is orange and requires operator review.",
                "Operator must review orange compliance concerns before external action.",
            )
        if status == "red":
            return fail_check(
                "compliance_review_present",
                -25,
                "Compliance review is red.",
                "Block external action until compliance risk is redesigned or rejected.",
            )
        return warn_check(
            "compliance_review_present",
            -8,
            "No compliance review was found.",
            "Run Phase 16 before fidelity signoff.",
        )

    def _check_external_action_blocked(
        self,
        proposal: Dict[str, Any],
        team_plan: Dict[str, Any],
        compliance: Dict[str, Any],
    ) -> FidelityCheck:
        proposal_internal = str(proposal.get("status", "")).startswith("internal")
        proposal_approval = bool(proposal.get("approval_required_before"))
        team_blocked = team_plan.get("external_action_performed") is False or not team_plan
        compliance_blocked = compliance.get("external_action_performed") is False or not compliance
        if proposal_internal and proposal_approval and team_blocked and compliance_blocked:
            return pass_check("external_action_blocked", "External action remains blocked behind approval gates.")
        return fail_check(
            "external_action_blocked",
            -20,
            "External-action boundary is not explicit across proposal, team, and compliance artifacts.",
            "Restore internal-only status and approval-required flags before any downstream phase.",
        )

    def _check_auditability(self, proposal: Dict[str, Any], team_plan: Dict[str, Any]) -> FidelityCheck:
        if proposal.get("audit_summary") and team_plan.get("team_id"):
            return pass_check("auditability_present", "Audit summary and Phase 19 team ID are present.")
        return warn_check(
            "auditability_present",
            -5,
            "Audit summary or team ID is missing.",
            "Ensure the proposal audit summary and Phase 19 team ID are available for review.",
        )

    def signature_update(self, reviews: List[FidelityReview]) -> str:
        counts = {
            status: len([review for review in reviews if review.quality_status == status])
            for status in [
                "high_fidelity_ready_for_approval_review",
                "ready_with_minor_review",
                "revision_recommended",
                "blocked_until_revision",
            ]
        }
        average = round(sum(review.fidelity_score for review in reviews) / len(reviews), 2) if reviews else 0
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 20 - Fidelity Forge",
            "Operational Identity:",
            "Internal Quality, Traceability, and Readiness Review Layer",
            "Action Performed:",
            "Generated internal fidelity reviews for proposal and sub-agent team artifacts.",
            "Safety Review:",
            "No external action performed.",
            "No approvals granted.",
            "No proposals sent.",
            "No credentials used.",
            "No external platform contacted.",
            f"Fidelity Reviews Created: {len(reviews)}",
            f"Average Fidelity Score: {average}",
            f"High Fidelity: {counts['high_fidelity_ready_for_approval_review']}",
            f"Ready With Minor Review: {counts['ready_with_minor_review']}",
            f"Revision Recommended: {counts['revision_recommended']}",
            f"Blocked Until Revision: {counts['blocked_until_revision']}",
            "Approval Required:",
            "Yes, before any reviewed artifact can become an external action.",
        ]).strip() + "\n"


def pass_check(name: str, evidence: str) -> FidelityCheck:
    return FidelityCheck(name=name, status="passed", score_delta=0, evidence=evidence, recommendation="")


def warn_check(name: str, penalty: int, evidence: str, recommendation: str) -> FidelityCheck:
    return FidelityCheck(name=name, status="warning", score_delta=penalty, evidence=evidence, recommendation=recommendation)


def fail_check(name: str, penalty: int, evidence: str, recommendation: str) -> FidelityCheck:
    return FidelityCheck(name=name, status="failed", score_delta=penalty, evidence=evidence, recommendation=recommendation)


def quality_status_for_score(score: int, high: int, ready: int, revision: int) -> str:
    if score >= high:
        return "high_fidelity_ready_for_approval_review"
    if score >= ready:
        return "ready_with_minor_review"
    if score >= revision:
        return "revision_recommended"
    return "blocked_until_revision"


def collect_risk_flags(checks: List[FidelityCheck], compliance: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    flags.extend(str(item) for item in compliance.get("risk_flags", []) if item)
    status = str(compliance.get("compliance_status", "missing"))
    if status in {"orange", "red"}:
        flags.append(f"compliance_{status}")
    for check in checks:
        if check.status == "failed":
            flags.append(f"failed_{check.name}")
        elif check.status == "warning":
            flags.append(f"warning_{check.name}")
    return unique(flags)


def proposal_message_blob(proposal: Dict[str, Any]) -> str:
    fields = [
        "employer_facing_message",
        "short_message_variant",
        "technical_message_variant",
        "clarifying_question_variant",
    ]
    return "\n".join(str(proposal.get(field, "")) for field in fields)


def make_review_id(proposal_id: str, opportunity_id: str, team_id: str) -> str:
    seed = f"{proposal_id}|{opportunity_id}|{team_id}|phase20"
    return "AIGC-FID-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def review_to_dict(review: FidelityReview) -> Dict[str, Any]:
    payload = asdict(review)
    payload["checks"] = [asdict(check) for check in review.checks]
    return payload


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 20 fidelity forge.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase20_fidelity_forge.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = FidelityForge(project_root=args.project_root)
    reviews = phase.run_from_config(args.config)
    print(phase.signature_update(reviews))
    print(f"\nFidelity reviews exported: {args.project_root / 'data' / 'phase20_fidelity' / 'aigc_phase20_fidelity_reviews.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
