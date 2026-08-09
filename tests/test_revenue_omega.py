from decimal import Decimal

import pytest

from src.revenue_omega.engine import RevenueOmegaEngine
from src.revenue_omega.models import CommercialAgreement, ComputeUsageEvent, PlacementEvent, RevenuePolicy


def policy(**overrides):
    values = {
        "policy_id": "revenue-omega-v1",
        "maximum_commission_rate": Decimal("0.25"),
        "maximum_compute_markup_rate": Decimal("0.50"),
    }
    values.update(overrides)
    return RevenuePolicy(**values)


def agreement(**overrides):
    values = {
        "agreement_id": "AGR-1",
        "employer_id": "EMP-1",
        "jurisdiction": "CA-AB",
        "billing_email": "billing@example.test",
        "commission_rate": Decimal("0.05"),
        "compute_pricing_mode": "PASS_THROUGH_PLUS_MARGIN",
        "compute_markup_rate": Decimal("0.10"),
        "currency": "CAD",
        "active": True,
        "jurisdiction_approved": True,
    }
    values.update(overrides)
    return CommercialAgreement(**values)


def placement(**overrides):
    values = {
        "placement_id": "PLACE-1",
        "agreement_id": "AGR-1",
        "employer_id": "EMP-1",
        "worker_reference": "WORKER-HASH-1",
        "billing_period": "2026-08-01/2026-08-14",
        "eligible_compensation": Decimal("2000.00"),
        "compensation_verified": True,
        "success_event_verified": True,
        "attribution_status": "ATTRIBUTED",
        "evidence_refs": ("EVIDENCE-1", "EVIDENCE-2"),
    }
    values.update(overrides)
    return PlacementEvent(**values)


def compute(**overrides):
    values = {
        "usage_id": "USAGE-1",
        "task_id": "TASK-1",
        "placement_id": "PLACE-1",
        "provider": "provider",
        "resource_type": "model_tokens",
        "quantity": Decimal("10"),
        "unit_cost": Decimal("0.20"),
        "currency": "CAD",
        "evidence_ref": "USAGE-EVIDENCE-1",
    }
    values.update(overrides)
    return ComputeUsageEvent(**values)


def test_exact_verified_employer_placement_is_billable():
    engine = RevenueOmegaEngine(policy())
    decision = engine.authorize_billing(agreement(), placement(), billing_email_verified=True)
    assert decision.allowed is True
    assert decision.reasons == ()


def test_unapproved_jurisdiction_fails_closed():
    engine = RevenueOmegaEngine(policy())
    decision = engine.authorize_billing(
        agreement(jurisdiction_approved=False), placement(), billing_email_verified=True
    )
    assert decision.allowed is False
    assert "JURISDICTION_NOT_APPROVED" in decision.reasons


def test_unverified_success_or_compensation_fails_closed():
    engine = RevenueOmegaEngine(policy())
    decision = engine.authorize_billing(
        agreement(),
        placement(compensation_verified=False, success_event_verified=False),
        billing_email_verified=True,
    )
    assert decision.allowed is False
    assert "COMPENSATION_UNVERIFIED" in decision.reasons
    assert "SUCCESS_EVENT_UNVERIFIED" in decision.reasons


def test_disputed_or_shared_attribution_does_not_auto_bill():
    engine = RevenueOmegaEngine(policy())
    for state in ("DISPUTED", "SHARED_ATTRIBUTION", "UNKNOWN", "NOT_ATTRIBUTED"):
        decision = engine.authorize_billing(agreement(), placement(attribution_status=state), billing_email_verified=True)
        assert decision.allowed is False
        assert "PLACEMENT_NOT_EXACTLY_ATTRIBUTED" in decision.reasons


def test_unverified_billing_email_blocks_delivery_lineage():
    engine = RevenueOmegaEngine(policy())
    decision = engine.authorize_billing(agreement(), placement(), billing_email_verified=False)
    assert decision.allowed is False
    assert "BILLING_EMAIL_UNVERIFIED" in decision.reasons


def test_policy_rate_ceiling_is_enforced():
    engine = RevenueOmegaEngine(policy(maximum_commission_rate=Decimal("0.04")))
    decision = engine.authorize_billing(agreement(), placement(), billing_email_verified=True)
    assert decision.allowed is False
    assert "COMMISSION_RATE_EXCEEDS_POLICY" in decision.reasons


def test_finder_fee_and_compute_recovery_are_deterministic():
    engine = RevenueOmegaEngine(policy())
    result = engine.calculate_commission(agreement(), placement(), [compute()])
    assert result.finder_fee == Decimal("100.00")
    assert result.compute_cost == Decimal("2.00")
    assert result.compute_recovery == Decimal("2.20")
    assert result.subtotal == Decimal("102.20")


def test_compute_usage_for_wrong_placement_is_rejected():
    engine = RevenueOmegaEngine(policy())
    with pytest.raises(ValueError, match="another placement"):
        engine.calculate_commission(agreement(), placement(), [compute(placement_id="OTHER")])


def test_invoice_requires_authorized_exact_lineage():
    engine = RevenueOmegaEngine(policy())
    calc = engine.calculate_commission(agreement(), placement(), [compute()])
    denied = engine.authorize_billing(
        agreement(), placement(success_event_verified=False), billing_email_verified=True
    )
    with pytest.raises(PermissionError):
        engine.build_invoice_candidate(agreement(), placement(), calc, denied)


def test_invoice_totals_and_idempotency_are_stable():
    engine = RevenueOmegaEngine(policy())
    agr = agreement()
    evt = placement()
    decision1 = engine.authorize_billing(agr, evt, billing_email_verified=True)
    decision2 = engine.authorize_billing(agr, evt, billing_email_verified=True)
    assert decision1.billing_idempotency_key == decision2.billing_idempotency_key
    assert decision1.decision_hash == decision2.decision_hash

    calc = engine.calculate_commission(agr, evt, [compute()])
    invoice = engine.build_invoice_candidate(
        agr, evt, calc, decision1, authorized_services="10.00", tax="5.61"
    )
    assert invoice.total == Decimal("117.81")
    assert invoice.finder_fee == Decimal("100.00")
    assert invoice.compute_recovery == Decimal("2.20")


def test_email_rendering_is_a_draft_not_an_external_effect():
    engine = RevenueOmegaEngine(policy())
    agr = agreement()
    evt = placement()
    decision = engine.authorize_billing(agr, evt, billing_email_verified=True)
    calc = engine.calculate_commission(agr, evt, [compute()])
    invoice = engine.build_invoice_candidate(agr, evt, calc, decision)
    draft = engine.render_invoice_email(invoice)
    assert draft.recipient == agr.billing_email
    assert draft.external_action_performed is False
    assert "does not send email" in draft.body


def test_issued_invoice_ledger_is_balanced():
    engine = RevenueOmegaEngine(policy())
    agr = agreement()
    evt = placement()
    decision = engine.authorize_billing(agr, evt, billing_email_verified=True)
    calc = engine.calculate_commission(agr, evt, [compute()])
    invoice = engine.build_invoice_candidate(agr, evt, calc, decision)
    tx = engine.ledger_for_issued_invoice(invoice)
    debits = sum(entry.amount for entry in tx.entries if entry.direction == "DEBIT")
    credits = sum(entry.amount for entry in tx.entries if entry.direction == "CREDIT")
    assert debits == credits == invoice.total


def test_default_policy_cannot_be_reconfigured_to_worker_placement_payer():
    with pytest.raises(ValueError, match="unsupported placement payer"):
        policy(placement_payer="WORKER")
