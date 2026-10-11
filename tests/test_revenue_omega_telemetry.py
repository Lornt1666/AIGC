from decimal import Decimal

import pytest

from src.revenue_omega.telemetry import RevenueTelemetryEvent, summarize_telemetry


def event(**overrides):
    values = dict(
        event_id="EV-1",
        event_type="COMMISSION_CALCULATED",
        task_id="TASK-1",
        placement_id="PLACE-1",
        invoice_id="INV-1",
        provider="AIGC",
        duration_ms=25,
        direct_cost=Decimal("0.10"),
        currency="CAD",
        status="PASS",
        evidence_ref="EVIDENCE-1",
        metadata={"revision": "abc123", "mode": "sandbox"},
    )
    values.update(overrides)
    return RevenueTelemetryEvent.create(**values)


def test_telemetry_event_is_hash_bound_and_summarized():
    first = event()
    second = event(
        event_id="EV-2",
        event_type="INVOICE_RENDERED",
        duration_ms=15,
        direct_cost=Decimal("0.05"),
        evidence_ref="EVIDENCE-2",
    )
    report = summarize_telemetry((first, second), currency="CAD")
    assert len(first.event_hash) == 64
    assert report.event_count == 2
    assert report.total_duration_ms == 40
    assert report.total_direct_cost == Decimal("0.15")
    assert len(report.summary_hash) == 64


def test_telemetry_rejects_secret_like_metadata_keys():
    for key in ("password", "api_key", "Authorization", "private-key", "client_secret"):
        with pytest.raises(ValueError, match="prohibited telemetry"):
            event(metadata={key: "do-not-record"})


def test_telemetry_requires_evidence():
    with pytest.raises(ValueError, match="requires an evidence"):
        event(evidence_ref="")


def test_duplicate_event_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate telemetry"):
        summarize_telemetry((event(), event()), currency="CAD")


def test_currency_mismatch_is_rejected():
    with pytest.raises(ValueError, match="currency mismatch"):
        summarize_telemetry((event(currency="USD"),), currency="CAD")
