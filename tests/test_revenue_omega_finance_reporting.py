from decimal import Decimal

import pytest

from src.revenue_omega.finance_reporting import (
    ExpenseEvidenceRecord,
    FounderAllocationPolicy,
    RevenueEvidenceRecord,
    allocate_founder_and_business_cash,
    build_finance_report,
)


PERIOD = "2026-08"


def revenue(state, amount, *, evidence="", record_id=None):
    return RevenueEvidenceRecord(
        record_id=record_id or f"R-{state}-{amount}",
        state=state,
        amount=Decimal(str(amount)),
        currency="CAD",
        period=PERIOD,
        evidence_ref=evidence,
    )


def expense(kind, amount, *, evidence="E-EXP", record_id=None):
    return ExpenseEvidenceRecord(
        record_id=record_id or f"E-{kind}-{amount}",
        expense_class=kind,
        amount=Decimal(str(amount)),
        currency="CAD",
        period=PERIOD,
        evidence_ref=evidence,
    )


def test_collected_cash_requires_evidence():
    with pytest.raises(ValueError, match="COLLECTED requires evidence"):
        revenue("COLLECTED", "100")


def test_refunds_and_chargebacks_require_evidence():
    with pytest.raises(ValueError, match="REFUNDED requires evidence"):
        revenue("REFUNDED", "10")
    with pytest.raises(ValueError, match="CHARGEBACK requires evidence"):
        revenue("CHARGEBACK", "10")


def test_expenses_require_evidence():
    with pytest.raises(ValueError, match="require evidence"):
        expense("MODEL_COMPUTE", "5", evidence="")


def test_pipeline_and_invoice_are_not_collected_cash():
    report = build_finance_report(
        period=PERIOD,
        currency="CAD",
        revenue_records=(
            revenue("PIPELINE", "1000"),
            revenue("CONTRACTED", "800"),
            revenue("INVOICED", "500"),
        ),
        expense_records=(),
    )
    assert report.pipeline == Decimal("1000.00")
    assert report.invoiced == Decimal("500.00")
    assert report.collected_cash == Decimal("0.00")
    assert report.contribution_before_tax_and_reserves == Decimal("0.00")


def test_cash_report_separates_cogs_marketing_and_other_opex():
    report = build_finance_report(
        period=PERIOD,
        currency="CAD",
        revenue_records=(
            revenue("COLLECTED", "1000", evidence="PAY-1"),
            revenue("REFUNDED", "50", evidence="REF-1"),
            revenue("CHARGEBACK", "25", evidence="CB-1"),
        ),
        expense_records=(
            expense("MODEL_COMPUTE", "100"),
            expense("CLOUD_INFRASTRUCTURE", "50"),
            expense("TOOL_API", "25"),
            expense("PAYMENT_PROCESSOR", "20"),
            expense("MARKETING_ACQUISITION", "75"),
            expense("OTHER_OPERATING", "30"),
        ),
    )
    assert report.gross_cash_after_reversals == Decimal("925.00")
    assert report.cogs == Decimal("195.00")
    assert report.marketing_customer_acquisition == Decimal("75.00")
    assert report.other_operating_expenses == Decimal("30.00")
    assert report.total_expenses == Decimal("300.00")
    assert report.contribution_before_tax_and_reserves == Decimal("625.00")


def test_period_or_currency_mismatch_fails_closed():
    wrong = RevenueEvidenceRecord(
        record_id="WRONG",
        state="PIPELINE",
        amount=Decimal("10"),
        currency="USD",
        period=PERIOD,
    )
    with pytest.raises(ValueError, match="period/currency mismatch"):
        build_finance_report(
            period=PERIOD,
            currency="CAD",
            revenue_records=(wrong,),
            expense_records=(),
        )


def test_founder_allocation_cannot_exceed_one_hundred_percent():
    with pytest.raises(ValueError, match="exceed 100%"):
        FounderAllocationPolicy(
            tax_reserve_rate="0.3",
            refund_reserve_rate="0.2",
            operating_reserve_rate="0.2",
            reinvestment_rate="0.2",
            founder_compensation_rate="0.2",
            owner_distribution_rate="0.1",
        )


def test_founder_allocation_uses_only_positive_contribution_cash():
    report = build_finance_report(
        period=PERIOD,
        currency="CAD",
        revenue_records=(revenue("COLLECTED", "1000", evidence="PAY-1"),),
        expense_records=(expense("MODEL_COMPUTE", "400"),),
    )
    allocation = allocate_founder_and_business_cash(
        report,
        FounderAllocationPolicy(
            tax_reserve_rate="0.20",
            refund_reserve_rate="0.05",
            operating_reserve_rate="0.15",
            reinvestment_rate="0.20",
            founder_compensation_rate="0.15",
            owner_distribution_rate="0.10",
        ),
    )
    assert allocation.allocatable_cash == Decimal("600.00")
    assert allocation.tax_reserve == Decimal("120.00")
    assert allocation.founder_compensation == Decimal("90.00")
    assert allocation.owner_distribution == Decimal("60.00")
    assert allocation.retained_unallocated_cash == Decimal("90.00")
    assert allocation.external_action_performed is False


def test_negative_contribution_produces_zero_founder_allocation():
    report = build_finance_report(
        period=PERIOD,
        currency="CAD",
        revenue_records=(revenue("COLLECTED", "100", evidence="PAY-1"),),
        expense_records=(expense("MODEL_COMPUTE", "150"),),
    )
    allocation = allocate_founder_and_business_cash(
        report,
        FounderAllocationPolicy(
            tax_reserve_rate="0.2",
            refund_reserve_rate="0.1",
            operating_reserve_rate="0.1",
            reinvestment_rate="0.2",
            founder_compensation_rate="0.2",
            owner_distribution_rate="0.1",
        ),
    )
    assert allocation.allocatable_cash == Decimal("0.00")
    assert allocation.founder_compensation == Decimal("0.00")
    assert allocation.owner_distribution == Decimal("0.00")
