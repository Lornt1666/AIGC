from decimal import Decimal

import pytest

from src.revenue_omega.invoice_lifecycle import (
    InvoiceLifecycle,
    InvoiceStateRecord,
    InvoiceTransitionEvidence,
)


def record(state="DRAFT", *, paid="0", refunded="0", revision=1):
    return InvoiceStateRecord(
        invoice_id="INV-1",
        invoice_hash="a" * 64,
        state=state,
        total=Decimal("100.00"),
        paid_amount=Decimal(paid),
        refunded_amount=Decimal(refunded),
        currency="CAD",
        revision=revision,
    )


def evidence(**overrides):
    values = dict(
        approval_decision_hash="approve-hash",
        provider_delivery_receipt_hash="delivery-hash",
        payment_receipt_hash="payment-hash",
        refund_receipt_hash="refund-hash",
        dispute_record_hash="dispute-hash",
        writeoff_decision_hash="writeoff-hash",
    )
    values.update(overrides)
    return InvoiceTransitionEvidence(**values)


def test_happy_path_requires_receipts_and_is_revisioned():
    lifecycle = InvoiceLifecycle()
    current = record()
    current, receipt = lifecycle.transition(current, "APPROVED", evidence=evidence())
    assert receipt.external_action_performed is False
    assert current.revision == 2
    current, _ = lifecycle.transition(current, "ISSUED", evidence=evidence())
    current, _ = lifecycle.transition(current, "DELIVERED", evidence=evidence())
    current, _ = lifecycle.transition(current, "PAID", evidence=evidence(), paid_amount="100")
    current, _ = lifecycle.transition(current, "SETTLED", evidence=evidence(), paid_amount="100")
    assert current.state == "SETTLED"
    assert current.paid_amount == Decimal("100.00")


def test_cannot_skip_approval_and_issue_from_draft():
    with pytest.raises(ValueError, match="invalid invoice transition"):
        InvoiceLifecycle().transition(record(), "ISSUED", evidence=evidence())


def test_approval_requires_decision_hash():
    with pytest.raises(PermissionError, match="approval decision"):
        InvoiceLifecycle().transition(
            record(), "APPROVED", evidence=evidence(approval_decision_hash="")
        )


def test_delivery_requires_provider_receipt():
    with pytest.raises(PermissionError, match="provider delivery"):
        InvoiceLifecycle().transition(
            record("ISSUED"),
            "DELIVERED",
            evidence=evidence(provider_delivery_receipt_hash=""),
        )


def test_payment_state_requires_payment_receipt_and_exact_amount():
    lifecycle = InvoiceLifecycle()
    with pytest.raises(PermissionError, match="payment receipt"):
        lifecycle.transition(
            record("OPEN"), "PAID", evidence=evidence(payment_receipt_hash=""), paid_amount="100"
        )
    with pytest.raises(ValueError, match="paid_amount == total"):
        lifecycle.transition(record("OPEN"), "PAID", evidence=evidence(), paid_amount="90")


def test_partial_payment_requires_strictly_partial_amount():
    lifecycle = InvoiceLifecycle()
    partial, _ = lifecycle.transition(
        record("OPEN"), "PARTIALLY_PAID", evidence=evidence(), paid_amount="25"
    )
    assert partial.paid_amount == Decimal("25.00")
    with pytest.raises(ValueError, match="PARTIALLY_PAID"):
        lifecycle.transition(record("OPEN"), "PARTIALLY_PAID", evidence=evidence(), paid_amount="100")


def test_refund_cannot_exceed_paid_amount():
    with pytest.raises(ValueError, match="refund cannot exceed paid amount"):
        InvoiceLifecycle().transition(
            record("PAID", paid="100"),
            "PARTIALLY_REFUNDED",
            evidence=evidence(),
            refunded_amount="120",
        )


def test_refund_requires_receipt():
    with pytest.raises(PermissionError, match="refund receipt"):
        InvoiceLifecycle().transition(
            record("SETTLED", paid="100"),
            "REFUNDED",
            evidence=evidence(refund_receipt_hash=""),
            refunded_amount="100",
        )


def test_dispute_requires_record_and_can_freeze_normal_path():
    lifecycle = InvoiceLifecycle()
    with pytest.raises(PermissionError, match="dispute record"):
        lifecycle.transition(
            record("OPEN"), "DISPUTED", evidence=evidence(dispute_record_hash="")
        )
    disputed, _ = lifecycle.transition(record("OPEN"), "DISPUTED", evidence=evidence())
    assert disputed.state == "DISPUTED"


def test_uncolllectible_requires_writeoff_decision():
    with pytest.raises(PermissionError, match="write-off decision"):
        InvoiceLifecycle().transition(
            record("OVERDUE"),
            "UNCOLLECTIBLE",
            evidence=evidence(writeoff_decision_hash=""),
        )


def test_terminal_states_do_not_reopen_silently():
    lifecycle = InvoiceLifecycle()
    for state in ("REFUNDED", "VOID", "CANCELLED", "UNCOLLECTIBLE"):
        with pytest.raises(ValueError, match="invalid invoice transition"):
            lifecycle.transition(record(state, paid="100" if state == "REFUNDED" else "0", refunded="100" if state == "REFUNDED" else "0"), "OPEN", evidence=evidence())
