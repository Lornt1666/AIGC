from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .models import InvoiceCandidate, InvoiceEmailDraft


@dataclass(frozen=True)
class ExternalActionPermit:
    permit_id: str
    action: str
    resource_id: str
    maximum_amount: Decimal | None = None
    expires_at: str = ""
    decision_hash: str = ""


@dataclass(frozen=True)
class EmailDeliveryReceipt:
    provider_message_id: str
    invoice_candidate_id: str
    provider: str
    delivered_to_provider: bool
    timestamp: str
    receipt_hash: str


@dataclass(frozen=True)
class PaymentRequestReceipt:
    provider_request_id: str
    invoice_candidate_id: str
    amount: Decimal
    currency: str
    status: str
    receipt_hash: str


class EmailBillingPort(Protocol):
    """Consequential adapter boundary. Implementations must verify the permit."""

    def send_invoice_email(
        self,
        draft: InvoiceEmailDraft,
        permit: ExternalActionPermit,
    ) -> EmailDeliveryReceipt: ...


class PaymentPort(Protocol):
    """Payment-provider boundary. No raw card material belongs in this interface."""

    def create_payment_request(
        self,
        invoice: InvoiceCandidate,
        permit: ExternalActionPermit,
    ) -> PaymentRequestReceipt: ...


class TaxPort(Protocol):
    """Jurisdiction-aware tax calculation boundary."""

    def calculate_tax(
        self,
        *,
        seller_jurisdiction: str,
        buyer_jurisdiction: str,
        service_type: str,
        subtotal: Decimal,
        currency: str,
    ) -> Decimal: ...
