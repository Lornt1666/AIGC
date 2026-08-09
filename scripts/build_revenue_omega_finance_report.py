from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path

from src.revenue_omega.finance_reporting import (
    ExpenseEvidenceRecord,
    RevenueEvidenceRecord,
    build_finance_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an evidence-bound Revenue-Ω finance report without external action.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    period = str(payload["period"])
    currency = str(payload.get("currency", "CAD"))
    revenue_records = tuple(
        RevenueEvidenceRecord(
            record_id=str(item["record_id"]),
            state=str(item["state"]),
            amount=Decimal(str(item["amount"])),
            currency=str(item.get("currency", currency)),
            period=str(item.get("period", period)),
            evidence_ref=str(item.get("evidence_ref", "")),
            related_invoice_id=str(item.get("related_invoice_id", "")),
        )
        for item in payload.get("revenue_records", [])
    )
    expense_records = tuple(
        ExpenseEvidenceRecord(
            record_id=str(item["record_id"]),
            expense_class=str(item["expense_class"]),
            amount=Decimal(str(item["amount"])),
            currency=str(item.get("currency", currency)),
            period=str(item.get("period", period)),
            evidence_ref=str(item["evidence_ref"]),
        )
        for item in payload.get("expense_records", [])
    )
    report = build_finance_report(
        period=period,
        currency=currency,
        revenue_records=revenue_records,
        expense_records=expense_records,
    )
    output = {
        **{key: (format(value, "f") if isinstance(value, Decimal) else value) for key, value in asdict(report).items()},
        "external_action_performed": False,
        "accounting_basis_note": "This is an evidence-classified internal business report, not a filed tax return or audited financial statement.",
    }
    encoded = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
