from decimal import Decimal

import pytest

from src.revenue_omega.metering import build_metering_report
from src.revenue_omega.models import ComputeUsageEvent


def event(**overrides):
    values = dict(
        usage_id="U1",
        task_id="T1",
        placement_id="P1",
        provider="PROVIDER-A",
        resource_type="MODEL_TOKENS",
        quantity=Decimal("10"),
        unit_cost=Decimal("0.20"),
        currency="CAD",
        evidence_ref="E1",
    )
    values.update(overrides)
    return ComputeUsageEvent(**values)


def test_metering_report_aggregates_direct_cost_and_evidence():
    result = build_metering_report(
        (
            event(),
            event(
                usage_id="U2",
                provider="PROVIDER-B",
                resource_type="CLOUD_RUNTIME",
                quantity=Decimal("2"),
                unit_cost=Decimal("1.50"),
                evidence_ref="E2",
            ),
        ),
        placement_id="P1",
        currency="CAD",
    )
    assert result.usage_count == 2
    assert result.total_direct_cost == Decimal("5.00")
    assert result.providers == ("PROVIDER-A", "PROVIDER-B")
    assert result.evidence_refs == ("E1", "E2")
    assert len(result.report_hash) == 64


def test_duplicate_usage_event_is_rejected():
    with pytest.raises(ValueError, match="duplicate usage"):
        build_metering_report((event(), event()), placement_id="P1", currency="CAD")


def test_billable_usage_requires_evidence():
    with pytest.raises(ValueError, match="requires evidence"):
        build_metering_report((event(evidence_ref=""),), placement_id="P1", currency="CAD")


def test_cross_placement_usage_is_rejected():
    with pytest.raises(ValueError, match="placement mismatch"):
        build_metering_report((event(placement_id="OTHER"),), placement_id="P1", currency="CAD")


def test_currency_mismatch_is_rejected():
    with pytest.raises(ValueError, match="currency mismatch"):
        build_metering_report((event(currency="USD"),), placement_id="P1", currency="CAD")
