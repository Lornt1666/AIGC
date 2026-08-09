from dataclasses import replace
from decimal import Decimal

import pytest

from src.revenue_omega.tax import (
    MappingTaxDecisionRepository,
    TaxDecision,
    calculate_tax,
)


def decision(**overrides):
    values = dict(
        decision_id="TAX-1",
        seller_jurisdiction="CA-AB",
        buyer_jurisdiction="CA-AB",
        service_type="EMPLOYMENT_PLACEMENT",
        currency="CAD",
        total_rate=Decimal("0.05"),
        effective_from="2026-01-01",
        effective_to="2027-01-01",
        source_refs=("AUTHORITATIVE-TAX-SOURCE",),
        reviewed_by="ACCOUNTABLE_REVIEWER",
    )
    values.update(overrides)
    return TaxDecision.create(**values)


def calculate(repo=None, **overrides):
    tax = decision()
    repo = repo or MappingTaxDecisionRepository({tax.decision_id: tax})
    values = dict(
        repository=repo,
        decision_id="TAX-1",
        seller_jurisdiction="CA-AB",
        buyer_jurisdiction="CA-AB",
        service_type="EMPLOYMENT_PLACEMENT",
        currency="CAD",
        subtotal=Decimal("100.00"),
        invoice_date="2026-08-09",
    )
    values.update(overrides)
    return calculate_tax(**values)


def test_persisted_current_tax_decision_calculates_deterministically():
    result = calculate()
    assert result.tax_amount == Decimal("5.00")
    assert result.total_after_tax == Decimal("105.00")
    assert len(result.calculation_hash) == 64


def test_missing_persisted_tax_decision_fails_closed():
    with pytest.raises(PermissionError, match="not persisted"):
        calculate(repo=MappingTaxDecisionRepository({}))


def test_tampered_tax_decision_fails_closed():
    exact = decision()
    tampered = replace(exact, decision_hash="0" * 64)
    with pytest.raises(PermissionError, match="integrity"):
        calculate(repo=MappingTaxDecisionRepository({tampered.decision_id: tampered}))


def test_expired_tax_decision_fails_closed():
    expired = decision(effective_from="2025-01-01", effective_to="2026-01-01")
    with pytest.raises(PermissionError, match="not current"):
        calculate(repo=MappingTaxDecisionRepository({expired.decision_id: expired}))


def test_scope_mismatch_fails_closed():
    with pytest.raises(PermissionError, match="scope mismatch"):
        calculate(buyer_jurisdiction="CA-BC")


def test_tax_rate_must_come_from_decision_not_caller():
    result = calculate(subtotal=Decimal("200.00"))
    assert result.tax_rate == Decimal("0.050000")
    assert result.tax_amount == Decimal("10.00")
