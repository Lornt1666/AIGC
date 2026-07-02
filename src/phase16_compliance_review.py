from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ComplianceReview:
    review_id: str
    created_at: str
    opportunity_id: str
    proposal_id: str
    employer: str
    platform: str
    source_url: str
    status: str
    compliance_status: str
    risk_flags: List[str]
    required_actions: List[str]
    ai_disclosure_status: str
    platform_policy_status: str
    regulated_domain_flags: List[str]
    payment_risk: str
    credential_or_private_data_risk: str
    linked_authorization_ids: List[str] = field(default_factory=list)
    external_action_performed: bool = False


class Phase16AuditLedger:
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


class ComplianceReviewEngine:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.ledger = Phase16AuditLedger(project_root / "data" / "audit" / "aigc_phase16_audit.jsonl")

    def run_from_config(self, config_path: Path) -> List[ComplianceReview]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        opportunities = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("opportunities", "")))
        proposals = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("proposals", "")))
        authorizations = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("authorizations", "")))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase16_compliance/aigc_phase16_compliance_reviews.json"),
        )
        records = self.build_reviews(
            opportunities=opportunities,
            proposals=proposals,
            authorizations=authorizations,
            regulated_terms=[str(item).lower() for item in config.get("regulated_terms", [])],
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2), encoding="utf-8")
        self.ledger.record("phase16_compliance_reviews_exported", {
            "path": str(output_path),
            "records": len(records),
            "external_action_performed": False,
        })
        report_path = self.project_root / "data" / "reports" / "phase16_signature_update.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        return records

    def build_reviews(
        self,
        opportunities: List[Dict[str, Any]],
        proposals: List[Dict[str, Any]],
        authorizations: List[Dict[str, Any]],
        regulated_terms: List[str],
    ) -> List[ComplianceReview]:
        opportunities_by_id = {item.get("opportunity_id", ""): item for item in opportunities}
        authorizations_by_proposal = group_by(authorizations, "proposal_id")
        reviews: List[ComplianceReview] = []
        for proposal in proposals:
            opportunity = opportunities_by_id.get(proposal.get("opportunity_id", ""), {})
            review = self.review_one(proposal, opportunity, authorizations_by_proposal, regulated_terms)
            reviews.append(review)
        return reviews

    def review_one(
        self,
        proposal: Dict[str, Any],
        opportunity: Dict[str, Any],
        authorizations_by_proposal: Dict[str, List[Dict[str, Any]]],
        regulated_terms: List[str],
    ) -> ComplianceReview:
        text_blob = json.dumps({"proposal": proposal, "opportunity": opportunity}, ensure_ascii=False).lower()
        risk_flags = list(dict.fromkeys(
            [str(item) for item in opportunity.get("risk_flags", [])]
            + [str(item) for item in opportunity.get("forbidden_flags", [])]
        ))
        regulated_flags = [term for term in regulated_terms if term and term in text_blob]
        ai_status = ai_disclosure_status(proposal)
        payment_risk = "unclear_payment_terms" if "unclear_pay" in risk_flags or not opportunity.get("pay_currency") else "payment_terms_visible"
        credential_risk = credential_or_private_data_risk(text_blob)
        platform_policy_status = platform_status(opportunity, proposal)
        required_actions = required_compliance_actions(
            risk_flags=risk_flags,
            regulated_flags=regulated_flags,
            ai_status=ai_status,
            payment_risk=payment_risk,
            credential_risk=credential_risk,
            platform_policy_status=platform_policy_status,
        )
        compliance_status = compliance_level(risk_flags, regulated_flags, required_actions)
        status = "cleared_internal" if compliance_status == "green" else "requires_operator_review"
        proposal_id = proposal.get("proposal_id", "")
        return ComplianceReview(
            review_id=make_review_id(proposal, opportunity),
            created_at=utc_now(),
            opportunity_id=proposal.get("opportunity_id", opportunity.get("opportunity_id", "")),
            proposal_id=proposal_id,
            employer=proposal.get("employer", opportunity.get("employer", "")),
            platform=proposal.get("source_platform", opportunity.get("source_platform", "")),
            source_url=proposal.get("source_url", opportunity.get("source_url", "")),
            status=status,
            compliance_status=compliance_status,
            risk_flags=risk_flags,
            required_actions=required_actions,
            ai_disclosure_status=ai_status,
            platform_policy_status=platform_policy_status,
            regulated_domain_flags=regulated_flags,
            payment_risk=payment_risk,
            credential_or_private_data_risk=credential_risk,
            linked_authorization_ids=[
                item.get("authorization_id", "")
                for item in authorizations_by_proposal.get(proposal_id, [])
                if item.get("authorization_id")
            ],
            external_action_performed=False,
        )

    def signature_update(self, records: List[ComplianceReview]) -> str:
        counts = {level: len([record for record in records if record.compliance_status == level]) for level in ["green", "yellow", "orange", "red"]}
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 16 - Compliance and Legal Review Layer",
            "Operational Identity:",
            "Internal Compliance / Legal-Risk Screening Layer",
            "Action Performed:",
            "Generated internal compliance reviews for proposal packages.",
            "Safety Review:",
            "No legal advice provided.",
            "No regulated work accepted.",
            "No platform terms accepted.",
            "No external action performed.",
            f"Compliance Reviews Created: {len(records)}",
            f"Green: {counts['green']}",
            f"Yellow: {counts['yellow']}",
            f"Orange: {counts['orange']}",
            f"Red: {counts['red']}",
            "Approval Required:",
            "Yes, before proceeding with orange/red compliance items or regulated work.",
        ]).strip() + "\n"


def ai_disclosure_status(proposal: Dict[str, Any]) -> str:
    disclosure = proposal.get("ai_use_disclosure", {})
    if not isinstance(disclosure, dict):
        return "missing"
    if disclosure.get("required") and disclosure.get("draft_language"):
        return "required_included"
    if disclosure.get("recommended") and disclosure.get("draft_language"):
        return "recommended_included"
    if disclosure.get("draft_language"):
        return "included"
    return "missing"


def credential_or_private_data_risk(text_blob: str) -> str:
    terms = ["credential", "api key", "token", "password", "private data", "personal data", "authentication", "oauth"]
    return "review_required" if any(term in text_blob for term in terms) else "not_detected"


def platform_status(opportunity: Dict[str, Any], proposal: Dict[str, Any]) -> str:
    blob = json.dumps({"opportunity": opportunity, "proposal": proposal}, ensure_ascii=False).lower()
    if "please mention the word" in blob or "avoid spam" in blob:
        return "anti_spam_reading_check_detected"
    if proposal.get("source_platform") == "GitHub" or opportunity.get("source_platform") == "GitHub":
        return "public_issue_or_repo_review_required"
    return "manual_terms_review_required"


def required_compliance_actions(
    risk_flags: List[str],
    regulated_flags: List[str],
    ai_status: str,
    payment_risk: str,
    credential_risk: str,
    platform_policy_status: str,
) -> List[str]:
    actions: List[str] = []
    if risk_flags:
        actions.append("review_opportunity_risk_flags")
    if regulated_flags:
        actions.append("operator_review_required_for_regulated_domain")
    if ai_status == "missing":
        actions.append("add_or_confirm_ai_use_disclosure")
    if payment_risk == "unclear_payment_terms":
        actions.append("clarify_payment_terms_before_contract")
    if credential_risk == "review_required":
        actions.append("confirm_no_credentials_or_private_data_are_used_without_approval")
    if platform_policy_status != "manual_terms_review_required":
        actions.append("review_platform_specific_submission_rules")
    else:
        actions.append("manually_review_platform_terms_before_external_action")
    return actions


def compliance_level(risk_flags: List[str], regulated_flags: List[str], required_actions: List[str]) -> str:
    if any(flag in {"forbidden", "blocked_by_safety", "malware", "fraud", "credential_misuse"} for flag in risk_flags):
        return "red"
    if regulated_flags:
        return "orange"
    if len(required_actions) >= 3 or risk_flags:
        return "yellow"
    return "green"


def group_by(records: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get(key, "")), []).append(record)
    return grouped


def make_review_id(proposal: Dict[str, Any], opportunity: Dict[str, Any]) -> str:
    seed = "|".join([
        str(proposal.get("proposal_id", "")),
        str(opportunity.get("opportunity_id", "")),
        str(proposal.get("source_url", "")),
    ])
    return "AIGC-COMP-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18].upper()


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 16 compliance review.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase16_compliance_review.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engine = ComplianceReviewEngine(project_root=args.project_root)
    records = engine.run_from_config(args.config)
    print(engine.signature_update(records))
    print(f"\nCompliance reviews exported: {args.project_root / 'data' / 'phase16_compliance' / 'aigc_phase16_compliance_reviews.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

