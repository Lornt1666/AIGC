from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json

from .models import InvoiceCandidate, InvoiceEmailDraft, canonical_sha256, money
from .permits import CommercialExecutionPermit, SandboxPermitLedger


@dataclass(frozen=True)
class SandboxEmailReceipt:
    provider: str
    message_id: str
    invoice_id: str
    recipient: str
    receipt_hash: str
    simulated: bool = True
    external_action_performed: bool = False


@dataclass(frozen=True)
class SandboxPaymentSession:
    provider: str
    session_id: str
    invoice_id: str
    amount: Decimal
    currency: str
    token_reference: str
    receipt_hash: str
    simulated: bool = True
    external_action_performed: bool = False


@dataclass(frozen=True)
class SandboxWebhook:
    provider: str
    event_id: str
    event_type: str
    invoice_id: str
    session_id: str
    amount: Decimal
    currency: str
    occurred_at: str
    signature: str

    def canonical_payload(self) -> bytes:
        payload = {
            "provider": self.provider,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "invoice_id": self.invoice_id,
            "session_id": self.session_id,
            "amount": format(money(self.amount), "f"),
            "currency": self.currency,
            "occurred_at": self.occurred_at,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class VerifiedSandboxPaymentReceipt:
    provider: str
    event_id: str
    invoice_id: str
    session_id: str
    amount: Decimal
    currency: str
    provider_envelope_hash: str
    receipt_hash: str
    simulated: bool = True
    external_action_performed: bool = False


class SandboxEmailAdapter:
    provider_name = "AIGC_SANDBOX_EMAIL"

    def deliver(
        self,
        draft: InvoiceEmailDraft,
        *,
        invoice: InvoiceCandidate,
        permit: CommercialExecutionPermit,
        ledger: SandboxPermitLedger,
        principal_id: str,
        now: datetime | None = None,
    ) -> SandboxEmailReceipt:
        permit.verify(
            action="SEND_INVOICE_SANDBOX",
            principal_id=principal_id,
            invoice_hash=invoice.invoice_hash,
            amount=invoice.total,
            currency=invoice.currency,
            now=now,
        )
        if draft.invoice_hash != invoice.invoice_hash:
            raise PermissionError("invoice email draft is not bound to this invoice")
        ledger.consume(permit)
        message_seed = canonical_sha256(
            {
                "permit_hash": permit.permit_hash,
                "invoice_hash": invoice.invoice_hash,
                "recipient": draft.recipient,
                "subject": draft.subject,
                "body_hash": hashlib.sha256(draft.body.encode("utf-8")).hexdigest(),
            }
        )
        receipt_hash = canonical_sha256(
            {
                "provider": self.provider_name,
                "message_id": f"sandbox-email-{message_seed[:20]}",
                "invoice_id": invoice.invoice_candidate_id,
                "recipient": draft.recipient,
                "simulated": True,
            }
        )
        return SandboxEmailReceipt(
            provider=self.provider_name,
            message_id=f"sandbox-email-{message_seed[:20]}",
            invoice_id=invoice.invoice_candidate_id,
            recipient=draft.recipient,
            receipt_hash=receipt_hash,
        )


class SandboxPaymentAdapter:
    provider_name = "AIGC_SANDBOX_PAYMENT"

    def create_session(
        self,
        invoice: InvoiceCandidate,
        *,
        permit: CommercialExecutionPermit,
        ledger: SandboxPermitLedger,
        principal_id: str,
        now: datetime | None = None,
    ) -> SandboxPaymentSession:
        permit.verify(
            action="CREATE_PAYMENT_SANDBOX",
            principal_id=principal_id,
            invoice_hash=invoice.invoice_hash,
            amount=invoice.total,
            currency=invoice.currency,
            now=now,
        )
        ledger.consume(permit)
        session_hash = canonical_sha256(
            {
                "permit_hash": permit.permit_hash,
                "invoice_hash": invoice.invoice_hash,
                "amount": invoice.total,
                "currency": invoice.currency,
            }
        )
        token_reference = f"sandbox-token-{session_hash[20:40]}"
        receipt_hash = canonical_sha256(
            {
                "provider": self.provider_name,
                "session_id": f"sandbox-pay-{session_hash[:20]}",
                "invoice_id": invoice.invoice_candidate_id,
                "amount": invoice.total,
                "currency": invoice.currency,
                "token_reference": token_reference,
                "simulated": True,
            }
        )
        return SandboxPaymentSession(
            provider=self.provider_name,
            session_id=f"sandbox-pay-{session_hash[:20]}",
            invoice_id=invoice.invoice_candidate_id,
            amount=invoice.total,
            currency=invoice.currency,
            token_reference=token_reference,
            receipt_hash=receipt_hash,
        )

    def sign_settled_webhook(
        self,
        session: SandboxPaymentSession,
        *,
        signing_secret: bytes,
        occurred_at: str,
    ) -> SandboxWebhook:
        if not signing_secret:
            raise ValueError("sandbox signing secret is required")
        event_seed = canonical_sha256(
            {
                "session_receipt_hash": session.receipt_hash,
                "occurred_at": occurred_at,
                "event_type": "payment.settled",
            }
        )
        unsigned = SandboxWebhook(
            provider=self.provider_name,
            event_id=f"sandbox-event-{event_seed[:20]}",
            event_type="payment.settled",
            invoice_id=session.invoice_id,
            session_id=session.session_id,
            amount=session.amount,
            currency=session.currency,
            occurred_at=occurred_at,
            signature="",
        )
        signature = hmac.new(signing_secret, unsigned.canonical_payload(), hashlib.sha256).hexdigest()
        return SandboxWebhook(**{**asdict(unsigned), "signature": signature})

    def verify_settled_webhook(
        self,
        webhook: SandboxWebhook,
        *,
        session: SandboxPaymentSession,
        signing_secret: bytes,
    ) -> VerifiedSandboxPaymentReceipt:
        if webhook.provider != self.provider_name or webhook.event_type != "payment.settled":
            raise PermissionError("unexpected sandbox payment event")
        if webhook.invoice_id != session.invoice_id or webhook.session_id != session.session_id:
            raise PermissionError("sandbox webhook session lineage mismatch")
        if money(webhook.amount) != money(session.amount) or webhook.currency != session.currency:
            raise PermissionError("sandbox webhook amount/currency mismatch")
        expected = hmac.new(signing_secret, webhook.canonical_payload(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, webhook.signature):
            raise PermissionError("sandbox webhook signature invalid")
        provider_envelope_hash = hashlib.sha256(
            webhook.canonical_payload() + b"|" + webhook.signature.encode("ascii")
        ).hexdigest()
        receipt_hash = canonical_sha256(
            {
                "provider": webhook.provider,
                "event_id": webhook.event_id,
                "invoice_id": webhook.invoice_id,
                "session_id": webhook.session_id,
                "amount": money(webhook.amount),
                "currency": webhook.currency,
                "provider_envelope_hash": provider_envelope_hash,
                "simulated": True,
            }
        )
        return VerifiedSandboxPaymentReceipt(
            provider=webhook.provider,
            event_id=webhook.event_id,
            invoice_id=webhook.invoice_id,
            session_id=webhook.session_id,
            amount=money(webhook.amount),
            currency=webhook.currency,
            provider_envelope_hash=provider_envelope_hash,
            receipt_hash=receipt_hash,
        )
