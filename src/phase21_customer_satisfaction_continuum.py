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
class CustomerSatisfactionRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    measurement_stage: str
    opportunity_id: str
    proposal_id: str
    fidelity_review_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    chi_score: int
    scores: Dict[str, int]
    confidence: str
    customer_expectation_profile: Dict[str, Any]
    risk_flags: List[str]
    improvement_actions: List[str]
    notes: List[str]
    approval_required_before_external_action: bool = True
    external_action_performed: bool = False


class Phase21AuditLedger:
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


class CustomerSatisfactionContinuum:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[CustomerSatisfactionRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        proposals = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("proposals", "")))
        authorizations = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("authorizations", "")))
        finance_records = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("finance_records", "")))
        compliance_reviews = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("compliance_reviews", "")))
        fidelity_reviews = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("fidelity_reviews", "")))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase21_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase21_audit.jsonl"),
        )
        records = self.build_records(
            config=config,
            proposals=proposals,
            authorizations=authorizations,
            finance_records=finance_records,
            compliance_reviews=compliance_reviews,
            fidelity_reviews=fidelity_reviews,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Phase21AuditLedger(audit_path).record("phase21_customer_satisfaction_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "external_action_performed": False,
        })
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        proposals: List[Dict[str, Any]],
        authorizations: List[Dict[str, Any]],
        finance_records: List[Dict[str, Any]],
        compliance_reviews: List[Dict[str, Any]],
        fidelity_reviews: List[Dict[str, Any]],
    ) -> List[CustomerSatisfactionRecord]:
        max_records = int(config.get("max_records", 25))
        measurement_stage = str(config.get("measurement_stage", "pre_external_action"))
        proposals_by_id = {str(item.get("proposal_id", "")): item for item in proposals}
        authorizations_by_proposal = group_by(authorizations, "proposal_id")
        finance_by_proposal = {str(item.get("proposal_id", "")): item for item in finance_records}
        compliance_by_proposal = {str(item.get("proposal_id", "")): item for item in compliance_reviews}
        records: List[CustomerSatisfactionRecord] = []
        for fidelity in fidelity_reviews:
            proposal_id = str(fidelity.get("proposal_id", ""))
            proposal = proposals_by_id.get(proposal_id, {})
            if not proposal:
                continue
            records.append(self._build_record(
                config=config,
                proposal=proposal,
                fidelity=fidelity,
                finance=finance_by_proposal.get(proposal_id, {}),
                compliance=compliance_by_proposal.get(proposal_id, {}),
                authorizations=authorizations_by_proposal.get(proposal_id, []),
                measurement_stage=measurement_stage,
            ))
            if len(records) >= max_records:
                break
        return records

    def _build_record(
        self,
        config: Dict[str, Any],
        proposal: Dict[str, Any],
        fidelity: Dict[str, Any],
        finance: Dict[str, Any],
        compliance: Dict[str, Any],
        authorizations: List[Dict[str, Any]],
        measurement_stage: str,
    ) -> CustomerSatisfactionRecord:
        scores = score_dimensions(proposal, fidelity, finance, compliance, authorizations)
        chi_score = max(0, min(100, sum(scores.values())))
        thresholds = config.get("thresholds", {})
        status = status_for_chi(
            chi_score,
            strong=int(thresholds.get("strong_customer_fit", 85)),
            good=int(thresholds.get("good_fit_with_review", 75)),
            revision=int(thresholds.get("revision_recommended", 65)),
        )
        risk_flags = collect_risk_flags(scores, fidelity, finance, compliance, authorizations)
        improvement_actions = improvement_actions_for(scores, risk_flags)
        expectation_profile = build_expectation_profile(proposal, fidelity, finance, compliance)
        notes = [
            "CHI is an internal pre-external-action estimate, not a customer outcome.",
            "Actual customer satisfaction must be updated after employer response and delivery/revision events.",
            "Phase 5 approval remains required before any external action.",
        ]
        proposal_id = str(proposal.get("proposal_id", ""))
        opportunity_id = str(proposal.get("opportunity_id", fidelity.get("opportunity_id", "")))
        return CustomerSatisfactionRecord(
            record_id=make_record_id(proposal_id, opportunity_id, measurement_stage),
            created_at=utc_now(),
            phase="phase21_customer_satisfaction_continuum",
            status=status,
            measurement_stage=measurement_stage,
            opportunity_id=opportunity_id,
            proposal_id=proposal_id,
            fidelity_review_id=str(fidelity.get("review_id", "")),
            title=str(proposal.get("title") or fidelity.get("title") or ""),
            employer=str(proposal.get("employer") or fidelity.get("employer") or ""),
            source_platform=str(proposal.get("source_platform") or fidelity.get("source_platform") or ""),
            source_url=str(proposal.get("source_url") or fidelity.get("source_url") or ""),
            chi_score=chi_score,
            scores=scores,
            confidence=confidence_for(proposal, fidelity, finance, compliance),
            customer_expectation_profile=expectation_profile,
            risk_flags=risk_flags,
            improvement_actions=improvement_actions,
            notes=notes,
            approval_required_before_external_action=True,
            external_action_performed=False,
        )

    def signature_update(self, records: List[CustomerSatisfactionRecord]) -> str:
        counts = {
            status: len([record for record in records if record.status == status])
            for status in [
                "strong_customer_fit_ready_for_approval_review",
                "good_fit_with_operator_review",
                "revision_recommended",
                "blocked_until_expectation_repair",
            ]
        }
        average = round(sum(record.chi_score for record in records) / len(records), 2) if records else 0
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 21 - Customer Satisfaction Continuum",
            "Operational Identity:",
            "Internal Customer Happiness Index and Expectation Tracking Layer",
            "Action Performed:",
            "Generated internal CHI records from proposal, fidelity, compliance, finance, and authorization artifacts.",
            "Safety Review:",
            "No external action performed.",
            "No customer contacted.",
            "No contract accepted.",
            "No payment requested.",
            "No satisfaction outcome claimed.",
            f"Customer Satisfaction Records Created: {len(records)}",
            f"Average CHI Score: {average}",
            f"Strong Customer Fit: {counts['strong_customer_fit_ready_for_approval_review']}",
            f"Good Fit With Review: {counts['good_fit_with_operator_review']}",
            f"Revision Recommended: {counts['revision_recommended']}",
            f"Blocked Until Expectation Repair: {counts['blocked_until_expectation_repair']}",
            "Approval Required:",
            "Yes, before any customer-facing action, contract action, or delivery action.",
        ]).strip() + "\n"


def score_dimensions(
    proposal: Dict[str, Any],
    fidelity: Dict[str, Any],
    finance: Dict[str, Any],
    compliance: Dict[str, Any],
    authorizations: List[Dict[str, Any]],
) -> Dict[str, int]:
    message = str(proposal.get("employer_facing_message", ""))
    deliverables = proposal.get("deliverables", [])
    questions = proposal.get("clarifying_questions", [])
    scope = proposal.get("scope_of_work", [])
    fidelity_score = int(fidelity.get("fidelity_score", 0) or 0)
    compliance_status = str(compliance.get("compliance_status", "missing"))
    finance_blockers = finance.get("blockers", [])
    pending_authorizations = sum(1 for item in authorizations if item.get("decision") == "pending")
    criteria_count = sum(
        len(item.get("acceptance_criteria", []))
        for item in deliverables
        if isinstance(item, dict) and isinstance(item.get("acceptance_criteria", []), list)
    )
    scores = {
        "requirement_clarity": clamp10(6 + int(bool(proposal.get("source_url"))) + int(bool(questions)) + int(criteria_count > 0) + int(bool(scope))),
        "communication_quality": clamp10(5 + int(len(message) >= 200) + int(len(message) >= 500) + int("clarify" in message.lower()) + int("review" in message.lower())),
        "response_speed": clamp10(7 + int(bool(proposal.get("timeline"))) - int("To be confirmed" in str(proposal.get("timeline", "")))),
        "deliverable_quality": clamp10(5 + int(bool(deliverables)) + int(criteria_count >= 2) + int(fidelity_score >= 80) + int(fidelity_score >= 90)),
        "professional_tone": clamp10(6 + int("Best regards" in message) + int(bool(proposal.get("employer"))) + int("I can help" in message) + int("review" in message.lower())),
        "scope_alignment": clamp10(5 + int(bool(scope)) + int(bool(proposal.get("forbidden_actions"))) + int(fidelity_score >= 80) + int(compliance_status in {"green", "yellow", "orange"})),
        "revision_handling": clamp10(5 + int(bool(questions)) + int("revision" in message.lower()) + int("unresolved" in json_blob(proposal).lower()) + int("clarify" in message.lower())),
        "employer_trust": clamp10(5 + int(bool(proposal.get("audit_summary"))) + int(bool(proposal.get("ai_use_disclosure"))) + int(fidelity.get("external_action_performed") is False) + int(compliance_status != "red")),
        "over_delivery_value": clamp10(5 + int("Review Notes" in message) + int(bool(proposal.get("technical_message_variant"))) + int(bool(proposal.get("quality_assurance_plan"))) + int(fidelity_score >= 90)),
        "acceptance_likelihood": clamp10(5 + int(fidelity_score >= 80) + int(fidelity_score >= 90) + int(pending_authorizations > 0) - int(bool(finance_blockers)) - int(compliance_status in {"orange", "red"})),
    }
    return scores


def status_for_chi(score: int, strong: int, good: int, revision: int) -> str:
    if score >= strong:
        return "strong_customer_fit_ready_for_approval_review"
    if score >= good:
        return "good_fit_with_operator_review"
    if score >= revision:
        return "revision_recommended"
    return "blocked_until_expectation_repair"


def collect_risk_flags(
    scores: Dict[str, int],
    fidelity: Dict[str, Any],
    finance: Dict[str, Any],
    compliance: Dict[str, Any],
    authorizations: List[Dict[str, Any]],
) -> List[str]:
    flags: List[str] = []
    flags.extend(str(item) for item in fidelity.get("risk_flags", []) if item)
    flags.extend(str(item) for item in compliance.get("risk_flags", []) if item)
    flags.extend(str(item) for item in finance.get("blockers", []) if item)
    if compliance.get("compliance_status") in {"orange", "red"}:
        flags.append(f"compliance_{compliance.get('compliance_status')}")
    if any(item.get("decision") == "pending" for item in authorizations):
        flags.append("phase5_approval_pending")
    for name, score in scores.items():
        if score < 7:
            flags.append(f"low_{name}")
    return unique(flags)


def improvement_actions_for(scores: Dict[str, int], risk_flags: List[str]) -> List[str]:
    actions: List[str] = []
    dimension_actions = {
        "requirement_clarity": "Clarify requirements and source-derived acceptance criteria before external review.",
        "communication_quality": "Tighten the customer-facing message for clarity, specificity, and low-friction review.",
        "response_speed": "Clarify timeline and turnaround expectations before any customer-facing action.",
        "deliverable_quality": "Strengthen deliverables and acceptance criteria.",
        "professional_tone": "Review tone for concise, professional, customer-centered language.",
        "scope_alignment": "Make scope and forbidden actions explicit.",
        "revision_handling": "Add revision-handling expectations and unresolved-question handling.",
        "employer_trust": "Preserve audit summary, AI-use disclosure, and approval boundaries.",
        "over_delivery_value": "Add lightweight review notes or value-add material without expanding scope.",
        "acceptance_likelihood": "Resolve approval, compliance, and payment blockers before external action.",
    }
    for flag in risk_flags:
        if flag.startswith("low_"):
            dimension = flag.removeprefix("low_")
            action = dimension_actions.get(dimension)
            if action:
                actions.append(action)
    if "compliance_orange" in risk_flags or "compliance_red" in risk_flags:
        actions.append("Resolve or explicitly review compliance risks before customer contact.")
    if "phase5_approval_pending" in risk_flags:
        actions.append("Keep Phase 5 approval pending status visible before any Phase 6 handoff.")
    if "pay_or_budget_not_visible" in risk_flags or "pay_interval_unknown" in risk_flags:
        actions.append("Clarify payment terms before contract or delivery commitments.")
    return unique(actions)


def build_expectation_profile(
    proposal: Dict[str, Any],
    fidelity: Dict[str, Any],
    finance: Dict[str, Any],
    compliance: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "expected_deliverables": [
            item.get("name", "")
            for item in proposal.get("deliverables", [])
            if isinstance(item, dict) and item.get("name")
        ],
        "clarifying_questions": proposal.get("clarifying_questions", []),
        "timeline": proposal.get("timeline", "unknown"),
        "fidelity_score": fidelity.get("fidelity_score", 0),
        "quality_status": fidelity.get("quality_status", ""),
        "compliance_status": compliance.get("compliance_status", "missing"),
        "payment_status": finance.get("payment_status", "unknown"),
        "contract_status": finance.get("contract_status", "unknown"),
    }


def confidence_for(
    proposal: Dict[str, Any],
    fidelity: Dict[str, Any],
    finance: Dict[str, Any],
    compliance: Dict[str, Any],
) -> str:
    present = sum(1 for item in [proposal, fidelity, finance, compliance] if item)
    if present == 4:
        return "medium_pre_external_action_estimate"
    if present >= 2:
        return "low_pre_external_action_estimate"
    return "insufficient_internal_evidence"


def clamp10(value: int) -> int:
    return max(0, min(10, value))


def make_record_id(proposal_id: str, opportunity_id: str, measurement_stage: str) -> str:
    seed = f"{proposal_id}|{opportunity_id}|{measurement_stage}|phase21"
    return "AIGC-CHI-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def group_by(records: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get(key, "")), []).append(record)
    return grouped


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def json_blob(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 21 customer satisfaction continuum.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase21_customer_satisfaction_continuum.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = CustomerSatisfactionContinuum(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nCustomer satisfaction records exported: {args.project_root / 'data' / 'phase21_customer_satisfaction' / 'aigc_phase21_customer_satisfaction_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
