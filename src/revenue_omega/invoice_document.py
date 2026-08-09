from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from html import escape

from .models import InvoiceCandidate, canonical_sha256, money


@dataclass(frozen=True)
class InvoiceDocument:
    invoice_id: str
    media_type: str
    body: str
    document_hash: str
    external_action_performed: bool = False


class InvoiceDocumentRenderer:
    """Deterministic HTML renderer for approved downstream document pipelines.

    The renderer accepts only already-calculated InvoiceCandidate values and
    escapes all textual fields. It performs no email send, payment request, tax
    calculation, browser action, or filesystem write.
    """

    def render_html(
        self,
        invoice: InvoiceCandidate,
        *,
        seller_name: str,
        seller_contact: str,
        payer_name: str,
        issue_date: str,
        due_date: str,
        payment_instructions: str = "Payment instructions supplied through the approved payment channel.",
    ) -> InvoiceDocument:
        for label, value in {
            "seller_name": seller_name,
            "seller_contact": seller_contact,
            "payer_name": payer_name,
            "issue_date": issue_date,
            "due_date": due_date,
        }.items():
            if not str(value).strip():
                raise ValueError(f"{label} is required")

        total_check = money(
            invoice.finder_fee
            + invoice.compute_recovery
            + invoice.authorized_services
            + invoice.tax
        )
        if total_check != money(invoice.total):
            raise ValueError("invoice line items do not add to the stated total")

        values = {
            "invoice_id": escape(invoice.invoice_candidate_id),
            "seller_name": escape(seller_name),
            "seller_contact": escape(seller_contact),
            "payer_name": escape(payer_name),
            "placement_id": escape(invoice.placement_id),
            "billing_period": escape(invoice.billing_period),
            "currency": escape(invoice.currency),
            "issue_date": escape(issue_date),
            "due_date": escape(due_date),
            "payment_instructions": escape(payment_instructions),
        }
        html = f"""<!doctype html>
<html lang=\"en\">
<head><meta charset=\"utf-8\"><title>AIGC Invoice {values['invoice_id']}</title></head>
<body>
<h1>AIGC Revenue-Ω Invoice</h1>
<p><strong>Invoice:</strong> {values['invoice_id']}</p>
<p><strong>Seller:</strong> {values['seller_name']} — {values['seller_contact']}</p>
<p><strong>Payer:</strong> {values['payer_name']}</p>
<p><strong>Placement:</strong> {values['placement_id']}</p>
<p><strong>Billing period:</strong> {values['billing_period']}</p>
<p><strong>Issue date:</strong> {values['issue_date']}</p>
<p><strong>Due date:</strong> {values['due_date']}</p>
<table>
<thead><tr><th>Item</th><th>Amount</th></tr></thead>
<tbody>
<tr><td>Finder / success fee</td><td>{values['currency']} {invoice.finder_fee}</td></tr>
<tr><td>Compute / API / runtime recovery</td><td>{values['currency']} {invoice.compute_recovery}</td></tr>
<tr><td>Other authorized services</td><td>{values['currency']} {invoice.authorized_services}</td></tr>
<tr><td>Applicable tax</td><td>{values['currency']} {invoice.tax}</td></tr>
<tr><td><strong>Total</strong></td><td><strong>{values['currency']} {invoice.total}</strong></td></tr>
</tbody>
</table>
<p>{values['payment_instructions']}</p>
<p>This document reflects the contracted employer/customer obligation represented by the underlying Revenue-Ω evidence. It does not authorize a worker wage deduction.</p>
</body>
</html>
"""
        document_hash = canonical_sha256(
            {
                "invoice_hash": invoice.invoice_hash,
                "media_type": "text/html",
                "body": html,
            }
        )
        return InvoiceDocument(
            invoice_id=invoice.invoice_candidate_id,
            media_type="text/html",
            body=html,
            document_hash=document_hash,
            external_action_performed=False,
        )
