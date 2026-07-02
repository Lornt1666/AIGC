from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FinanceLedgerRecord:
    record_id: str
    created_at: str
    opportunity_id: str
    proposal_id: str
    employer: str
    platform: str
    status: str
    currency: str
    proposed_amount: float
    accepted_amount: float
    pay_min: Optional[float]
    pay_max: Optional[float]
    pay_interval: str
    payment_status: str
    contract_status: str
    invoice_status: str
    value_confidence: str
    blockers: List[str]
    required_approvals: List[str]
    source_url: str = ""
    linked_authorization_ids: List[str] = field(default_factory=list)
    linked_execution_ids: List[str] = field(default_factory=list)
    external_action_performed: bool = False


class Phase15AuditLedger:
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


class FinanceContractsLedger:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.ledger = Phase15AuditLedger(project_root / "data" / "audit" / "aigc_phase15_audit.jsonl")

    def run_from_config(self, config_path: Path) -> List[FinanceLedgerRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        opportunities = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("opportunities", "")))
        proposals = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("proposals", "")))
        authorizations = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("authorizations", "")))
        executions = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("executions", "")))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase15_finance/aigc_phase15_finance_ledger.json"),
        )
        records = self.build_records(
            opportunities=opportunities,
            proposals=proposals,
            authorizations=authorizations,
            executions=executions,
            currency_fallback=str(config.get("currency_fallback", "unknown")),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2), encoding="utf-8")
        self.ledger.record("phase15_finance_ledger_exported", {
            "path": str(output_path),
            "records": len(records),
            "external_action_performed": False,
        })
        report_path = self.project_root / "data" / "reports" / "phase15_signature_update.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        return records

    def build_records(
        self,
        opportunities: List[Dict[str, Any]],
        proposals: List[Dict[str, Any]],
        authorizations: List[Dict[str, Any]],
        executions: List[Dict[str, Any]],
        currency_fallback: str = "unknown",
    ) -> List[FinanceLedgerRecord]:
        opportunities_by_id = {item.get("opportunity_id", ""): item for item in opportunities}
        auth_by_proposal = group_by(authorizations, "proposal_id")
        executions_by_proposal = group_by(executions, "proposal_id")
        records: List[FinanceLedgerRecord] = []
        for proposal in proposals:
            opportunity = opportunities_by_id.get(proposal.get("opportunity_id", ""), {})
            pay_min = numeric_or_none(opportunity.get("pay_min"))
            pay_max = numeric_or_none(opportunity.get("pay_max"))
            currency = str(opportunity.get("pay_currency") or currency_fallback)
            interval = str(opportunity.get("pay_interval") or "unknown")
            proposed_amount = estimate_amount(pay_min, pay_max)
            blockers = finance_blockers(opportunity, proposal, pay_min, pay_max)
            value_confidence = "estimated" if proposed_amount > 0 else "unknown"
            record = FinanceLedgerRecord(
                record_id=make_record_id(proposal, opportunity),
                created_at=utc_now(),
                opportunity_id=proposal.get("opportunity_id", ""),
                proposal_id=proposal.get("proposal_id", ""),
                employer=proposal.get("employer", opportunity.get("employer", "")),
                platform=proposal.get("source_platform", opportunity.get("source_platform", "")),
                status="internal_estimate_only",
                currency=currency,
                proposed_amount=proposed_amount,
                accepted_amount=0.0,
                pay_min=pay_min,
                pay_max=pay_max,
                pay_interval=interval,
                payment_status="not_started",
                contract_status="not_started",
                invoice_status="not_applicable",
                value_confidence=value_confidence,
                blockers=blockers,
                required_approvals=[
                    "operator_approval_before_contract_acceptance",
                    "operator_approval_before_invoice_or_payment_request",
                    "operator_approval_before_external_finance_contact",
                ],
                source_url=proposal.get("source_url", opportunity.get("source_url", "")),
                linked_authorization_ids=[item.get("authorization_id", "") for item in auth_by_proposal.get(proposal.get("proposal_id", ""), []) if item.get("authorization_id")],
                linked_execution_ids=[item.get("execution_id", "") for item in executions_by_proposal.get(proposal.get("proposal_id", ""), []) if item.get("execution_id")],
                external_action_performed=False,
            )
            records.append(record)
        return records

    def signature_update(self, records: List[FinanceLedgerRecord]) -> str:
        unknown_value = [record for record in records if record.value_confidence == "unknown"]
        blocked = [record for record in records if record.blockers]
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 15 - Finance, Contracts, and Asset Ledger",
            "Operational Identity:",
            "Internal Finance / Contract Tracking Layer",
            "Action Performed:",
            "Generated internal finance ledger records from existing opportunity and proposal artifacts.",
            "Safety Review:",
            "No contract accepted.",
            "No invoice sent.",
            "No payment requested.",
            "No credentials used.",
            "No external action performed.",
            f"Finance Records Created: {len(records)}",
            f"Unknown Value Records: {len(unknown_value)}",
            f"Records With Blockers: {len(blocked)}",
            "Approval Required:",
            "Yes, before contract acceptance, invoicing, payment requests, or external finance communication.",
        ]).strip() + "\n"


def finance_blockers(
    opportunity: Dict[str, Any],
    proposal: Dict[str, Any],
    pay_min: Optional[float],
    pay_max: Optional[float],
) -> List[str]:
    blockers: List[str] = []
    if pay_min is None and pay_max is None:
        blockers.append("pay_or_budget_not_visible")
    if str(opportunity.get("pay_interval") or "unknown") == "unknown":
        blockers.append("pay_interval_unknown")
    if not proposal.get("source_url") and not opportunity.get("source_url"):
        blockers.append("source_url_missing")
    if "contract" in json.dumps(proposal, ensure_ascii=False).lower():
        blockers.append("contract_terms_require_operator_review")
    return blockers


def estimate_amount(pay_min: Optional[float], pay_max: Optional[float]) -> float:
    if pay_min is not None and pay_max is not None:
        return round((pay_min + pay_max) / 2, 2)
    if pay_min is not None:
        return float(pay_min)
    if pay_max is not None:
        return float(pay_max)
    return 0.0


def group_by(records: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get(key, "")), []).append(record)
    return grouped


def numeric_or_none(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def make_record_id(proposal: Dict[str, Any], opportunity: Dict[str, Any]) -> str:
    seed = "|".join([
        str(proposal.get("proposal_id", "")),
        str(opportunity.get("opportunity_id", "")),
        str(proposal.get("employer", "")),
    ])
    return "AIGC-FIN-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18].upper()


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 15 finance/contracts ledger.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase15_finance_contracts_ledger.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = FinanceContractsLedger(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nFinance ledger exported: {args.project_root / 'data' / 'phase15_finance' / 'aigc_phase15_finance_ledger.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

