from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import canonical_sha256, money, rate


REVENUE_STATES = {"PIPELINE", "CONTRACTED", "INVOICED", "COLLECTED", "REFUNDED", "CHARGEBACK"}
EXPENSE_CLASSES = {
    "MODEL_COMPUTE",
    "CLOUD_INFRASTRUCTURE",
    "TOOL_API",
    "PAYMENT_PROCESSOR",
    "MARKETING_ACQUISITION",
    "OTHER_OPERATING",
}


@dataclass(frozen=True)
class RevenueEvidenceRecord:
    record_id: str
    state: str
    amount: Decimal
    currency: str
    period: str
    evidence_ref: str = ""
    related_invoice_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", money(self.amount))
        if self.state not in REVENUE_STATES:
            raise ValueError(f"unsupported revenue state: {self.state}")
        if self.amount < Decimal("0"):
            raise ValueError("revenue amount cannot be negative")
        if self.state in {"COLLECTED", "REFUNDED", "CHARGEBACK"} and not self.evidence_ref:
            raise ValueError(f"{self.state} requires evidence")


@dataclass(frozen=True)
class ExpenseEvidenceRecord:
    record_id: str
    expense_class: str
    amount: Decimal
    currency: str
    period: str
    evidence_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", money(self.amount))
        if self.expense_class not in EXPENSE_CLASSES:
            raise ValueError(f"unsupported expense class: {self.expense_class}")
        if self.amount < Decimal("0"):
            raise ValueError("expense amount cannot be negative")
        if not self.evidence_ref:
            raise ValueError("expense records require evidence")


@dataclass(frozen=True)
class FinanceReport:
    period: str
    currency: str
    pipeline: Decimal
    contracted: Decimal
    invoiced: Decimal
    collected_cash: Decimal
    refunds: Decimal
    chargebacks: Decimal
    gross_cash_after_reversals: Decimal
    cogs: Decimal
    marketing_customer_acquisition: Decimal
    other_operating_expenses: Decimal
    total_expenses: Decimal
    contribution_before_tax_and_reserves: Decimal
    report_hash: str


@dataclass(frozen=True)
class FounderAllocationPolicy:
    tax_reserve_rate: Decimal
    refund_reserve_rate: Decimal
    operating_reserve_rate: Decimal
    reinvestment_rate: Decimal
    founder_compensation_rate: Decimal
    owner_distribution_rate: Decimal

    def __post_init__(self) -> None:
        for name in (
            "tax_reserve_rate",
            "refund_reserve_rate",
            "operating_reserve_rate",
            "reinvestment_rate",
            "founder_compensation_rate",
            "owner_distribution_rate",
        ):
            value = rate(getattr(self, name))
            object.__setattr__(self, name, value)
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{name} must be between 0 and 1")
        total = sum(
            (
                self.tax_reserve_rate,
                self.refund_reserve_rate,
                self.operating_reserve_rate,
                self.reinvestment_rate,
                self.founder_compensation_rate,
                self.owner_distribution_rate,
            ),
            Decimal("0"),
        )
        if total > Decimal("1"):
            raise ValueError("allocation rates cannot exceed 100% in aggregate")


@dataclass(frozen=True)
class FounderAllocationReport:
    source_finance_report_hash: str
    allocatable_cash: Decimal
    tax_reserve: Decimal
    refund_reserve: Decimal
    operating_reserve: Decimal
    business_reinvestment: Decimal
    founder_compensation: Decimal
    owner_distribution: Decimal
    retained_unallocated_cash: Decimal
    allocation_hash: str
    external_action_performed: bool = False


def build_finance_report(
    *,
    period: str,
    currency: str,
    revenue_records: Iterable[RevenueEvidenceRecord],
    expense_records: Iterable[ExpenseEvidenceRecord],
) -> FinanceReport:
    revenue = tuple(revenue_records)
    expenses = tuple(expense_records)
    for item in revenue:
        if item.period != period or item.currency != currency:
            raise ValueError("revenue record period/currency mismatch")
    for item in expenses:
        if item.period != period or item.currency != currency:
            raise ValueError("expense record period/currency mismatch")

    def revenue_sum(state: str) -> Decimal:
        return money(sum((item.amount for item in revenue if item.state == state), Decimal("0")))

    def expense_sum(*classes: str) -> Decimal:
        allowed = set(classes)
        return money(sum((item.amount for item in expenses if item.expense_class in allowed), Decimal("0")))

    pipeline = revenue_sum("PIPELINE")
    contracted = revenue_sum("CONTRACTED")
    invoiced = revenue_sum("INVOICED")
    collected = revenue_sum("COLLECTED")
    refunds = revenue_sum("REFUNDED")
    chargebacks = revenue_sum("CHARGEBACK")
    gross_cash = money(max(Decimal("0"), collected - refunds - chargebacks))

    cogs = expense_sum("MODEL_COMPUTE", "CLOUD_INFRASTRUCTURE", "TOOL_API", "PAYMENT_PROCESSOR")
    marketing = expense_sum("MARKETING_ACQUISITION")
    other_opex = expense_sum("OTHER_OPERATING")
    total_expenses = money(cogs + marketing + other_opex)
    contribution = money(gross_cash - total_expenses)

    payload = {
        "period": period,
        "currency": currency,
        "pipeline": pipeline,
        "contracted": contracted,
        "invoiced": invoiced,
        "collected_cash": collected,
        "refunds": refunds,
        "chargebacks": chargebacks,
        "gross_cash_after_reversals": gross_cash,
        "cogs": cogs,
        "marketing_customer_acquisition": marketing,
        "other_operating_expenses": other_opex,
        "total_expenses": total_expenses,
        "contribution_before_tax_and_reserves": contribution,
        "revenue_evidence": [item.record_id for item in revenue],
        "expense_evidence": [item.record_id for item in expenses],
    }
    return FinanceReport(
        period=period,
        currency=currency,
        pipeline=pipeline,
        contracted=contracted,
        invoiced=invoiced,
        collected_cash=collected,
        refunds=refunds,
        chargebacks=chargebacks,
        gross_cash_after_reversals=gross_cash,
        cogs=cogs,
        marketing_customer_acquisition=marketing,
        other_operating_expenses=other_opex,
        total_expenses=total_expenses,
        contribution_before_tax_and_reserves=contribution,
        report_hash=canonical_sha256(payload),
    )


def allocate_founder_and_business_cash(
    report: FinanceReport,
    policy: FounderAllocationPolicy,
) -> FounderAllocationReport:
    allocatable = money(max(Decimal("0"), report.contribution_before_tax_and_reserves))
    tax_reserve = money(allocatable * policy.tax_reserve_rate)
    refund_reserve = money(allocatable * policy.refund_reserve_rate)
    operating_reserve = money(allocatable * policy.operating_reserve_rate)
    reinvestment = money(allocatable * policy.reinvestment_rate)
    founder_compensation = money(allocatable * policy.founder_compensation_rate)
    owner_distribution = money(allocatable * policy.owner_distribution_rate)
    allocated = money(
        tax_reserve
        + refund_reserve
        + operating_reserve
        + reinvestment
        + founder_compensation
        + owner_distribution
    )
    retained = money(allocatable - allocated)
    payload = {
        "source_finance_report_hash": report.report_hash,
        "allocatable_cash": allocatable,
        "tax_reserve": tax_reserve,
        "refund_reserve": refund_reserve,
        "operating_reserve": operating_reserve,
        "business_reinvestment": reinvestment,
        "founder_compensation": founder_compensation,
        "owner_distribution": owner_distribution,
        "retained_unallocated_cash": retained,
    }
    return FounderAllocationReport(
        **payload,
        allocation_hash=canonical_sha256(payload),
        external_action_performed=False,
    )
