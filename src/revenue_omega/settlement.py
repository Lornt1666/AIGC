from __future__ import annotations

from dataclasses import asdict

from .models import InvoiceCandidate, LedgerEntry, LedgerTransaction, canonical_sha256


def ledger_for_payment_settlement(
    invoice: InvoiceCandidate,
    *,
    payment_receipt_hash: str,
) -> LedgerTransaction:
    if not payment_receipt_hash:
        raise ValueError("payment receipt hash is required")
    entries = (
        LedgerEntry(
            entry_id=f"{invoice.invoice_candidate_id}-CASH",
            account="PROCESSOR_CLEARING_OR_CASH",
            direction="DEBIT",
            amount=invoice.total,
            currency=invoice.currency,
            reference_id=payment_receipt_hash,
        ),
        LedgerEntry(
            entry_id=f"{invoice.invoice_candidate_id}-AR-CLEAR",
            account="ACCOUNTS_RECEIVABLE",
            direction="CREDIT",
            amount=invoice.total,
            currency=invoice.currency,
            reference_id=payment_receipt_hash,
        ),
    )
    tx_hash = canonical_sha256(
        {
            "invoice_hash": invoice.invoice_hash,
            "payment_receipt_hash": payment_receipt_hash,
            "entries": [asdict(entry) for entry in entries],
        }
    )
    return LedgerTransaction(
        transaction_id=f"REV-SETTLE-{tx_hash[:20].upper()}",
        entries=entries,
        reference_id=payment_receipt_hash,
        transaction_hash=tx_hash,
    )
