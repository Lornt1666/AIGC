from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.revenue_omega.models import InvoiceCandidate, InvoiceEmailDraft
from src.revenue_omega.permits import CommercialExecutionPermit, SandboxPermitLedger
from src.revenue_omega.sandbox import SandboxEmailAdapter, SandboxPaymentAdapter
from src.revenue_omega.sandbox_proof import run_sandbox_proof


NOW = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)
VERIFY_MATERIAL = b"for-tests-revenue-omega-verification-material"


def candidate():
    return InvoiceCandidate(
        invoice_candidate_id="INV-SANDBOX",
        agreement_id="AGR",
        placement_id="PLACE",
        employer_id="EMP",
        billing_email="billing@example.test",
        billing_period="2026-08",
        currency="CAD",
        finder_fee=Decimal("100"),
        compute_recovery=Decimal("2.20"),
        authorized_services=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("102.20"),
        billing_idempotency_key="b" * 64,
        evidence_refs=("E",),
        calculation_hash="c" * 64,
        authorization_decision_hash="d" * 64,
    )


def permit(action, invoice=None, **overrides):
    invoice = invoice or candidate()
    values = dict(
        permit_id=f"PERMIT-{action}",
        action=action,
        principal_id="OPERATOR",
        invoice_hash=invoice.invoice_hash,
        currency=invoice.currency,
        maximum_amount=invoice.total,
        maximum_calls=1,
        environment="SANDBOX",
        issued_at="2026-08-09T09:00:00+00:00",
        expires_at="2026-08-09T11:00:00+00:00",
        decision_hash="e" * 64,
    )
    values.update(overrides)
    return CommercialExecutionPermit.create(**values)


def draft(invoice=None):
    invoice = invoice or candidate()
    return InvoiceEmailDraft(
        invoice_candidate_id=invoice.invoice_candidate_id,
        recipient=invoice.billing_email,
        subject="Sandbox invoice",
        body="Synthetic invoice only",
        invoice_hash=invoice.invoice_hash,
    )


def test_end_to_end_sandbox_proof_settles_without_network_or_money():
    receipt = run_sandbox_proof()
    assert receipt.status == "SANDBOX_SETTLED"
    assert receipt.final_invoice_state == "SETTLED"
    assert receipt.network_call_performed is False
    assert receipt.real_money_moved is False
    assert receipt.external_action_performed is False
    assert len(receipt.proof_hash) == 64


def test_sandbox_email_permit_is_one_use():
    invoice = candidate()
    p = permit("SEND_INVOICE_SANDBOX", invoice)
    ledger = SandboxPermitLedger()
    adapter = SandboxEmailAdapter()
    adapter.deliver(draft(invoice), invoice=invoice, permit=p, ledger=ledger, principal_id="OPERATOR", now=NOW)
    with pytest.raises(PermissionError, match="already consumed"):
        adapter.deliver(draft(invoice), invoice=invoice, permit=p, ledger=ledger, principal_id="OPERATOR", now=NOW)


def test_sandbox_adapter_rejects_wrong_invoice_binding():
    invoice = candidate()
    other = replace(invoice, invoice_candidate_id="OTHER")
    p = permit("SEND_INVOICE_SANDBOX", invoice)
    with pytest.raises(PermissionError, match="invoice mismatch"):
        SandboxEmailAdapter().deliver(
            draft(other),
            invoice=other,
            permit=p,
            ledger=SandboxPermitLedger(),
            principal_id="OPERATOR",
            now=NOW,
        )


def test_sandbox_adapter_rejects_expired_permit():
    invoice = candidate()
    p = permit("CREATE_PAYMENT_SANDBOX", invoice, expires_at="2026-08-09T09:30:00+00:00")
    with pytest.raises(PermissionError, match="validity window"):
        SandboxPaymentAdapter().create_session(
            invoice,
            permit=p,
            ledger=SandboxPermitLedger(),
            principal_id="OPERATOR",
            now=NOW,
        )


def test_sandbox_adapter_rejects_amount_ceiling():
    invoice = candidate()
    p = permit("CREATE_PAYMENT_SANDBOX", invoice, maximum_amount="50")
    with pytest.raises(PermissionError, match="amount ceiling"):
        SandboxPaymentAdapter().create_session(
            invoice,
            permit=p,
            ledger=SandboxPermitLedger(),
            principal_id="OPERATOR",
            now=NOW,
        )


def test_tampered_webhook_signature_fails_closed():
    invoice = candidate()
    adapter = SandboxPaymentAdapter()
    session = adapter.create_session(
        invoice,
        permit=permit("CREATE_PAYMENT_SANDBOX", invoice),
        ledger=SandboxPermitLedger(),
        principal_id="OPERATOR",
        now=NOW,
    )
    webhook = adapter.sign_settled_webhook(
        session,
        verification_material=VERIFY_MATERIAL,
        occurred_at=NOW.isoformat(),
    )
    tampered = replace(webhook, amount=Decimal("1.00"))
    with pytest.raises(PermissionError):
        adapter.verify_settled_webhook(
            tampered,
            session=session,
            verification_material=VERIFY_MATERIAL,
        )


def test_sandbox_webhook_signature_and_lineage_verify():
    invoice = candidate()
    adapter = SandboxPaymentAdapter()
    session = adapter.create_session(
        invoice,
        permit=permit("CREATE_PAYMENT_SANDBOX", invoice),
        ledger=SandboxPermitLedger(),
        principal_id="OPERATOR",
        now=NOW,
    )
    webhook = adapter.sign_settled_webhook(
        session,
        verification_material=VERIFY_MATERIAL,
        occurred_at=NOW.isoformat(),
    )
    verified = adapter.verify_settled_webhook(
        webhook,
        session=session,
        verification_material=VERIFY_MATERIAL,
    )
    assert verified.amount == invoice.total
    assert verified.invoice_id == invoice.invoice_candidate_id
    assert verified.external_action_performed is False
