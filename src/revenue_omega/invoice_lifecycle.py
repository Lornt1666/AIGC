from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from .models import canonical_sha256, money


INVOICE_STATES = {
    "DRAFT",
    "APPROVED",
    "ISSUED",
    "DELIVERED",
    "OPEN",
    "PARTIALLY_PAID",
    "PAID",
    "SETTLED",
    "OVERDUE",
    "DISPUTED",
    "VOID",
    "CANCELLED",
    "PARTIALLY_REFUNDED",
    "REFUNDED",
    "UNCOLLECTIBLE",
}

ALLOWED_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "DRAFT": frozenset({"APPROVED", "CANCELLED"}),
    "APPROVED": frozenset({"ISSUED", "CANCELLED", "VOID"}),
    "ISSUED": frozenset({"DELIVERED", "VOID", "DISPUTED"}),
    "DELIVERED": frozenset({"OPEN", "PARTIALLY_PAID", "PAID", "DISPUTED", "VOID"}),
    "OPEN": frozenset({"PARTIALLY_PAID", "PAID", "OVERDUE", "DISPUTED", "VOID"}),
    "PARTIALLY_PAID": frozenset({"PAID", "OVERDUE", "DISPUTED", "VOID"}),
    "PAID": frozenset({"SETTLED", "PARTIALLY_REFUNDED", "REFUNDED", "DISPUTED"}),
    "SETTLED": frozenset({"PARTIALLY_REFUNDED", "REFUNDED", "DISPUTED"}),
    "OVERDUE": frozenset({"PARTIALLY_PAID", "PAID", "DISPUTED", "UNCOLLECTIBLE", "VOID"}),
    "DISPUTED": frozenset({"OPEN", "PARTIALLY_PAID", "PAID", "VOID", "PARTIALLY_REFUNDED", "REFUNDED"}),
    "PARTIALLY_REFUNDED": frozenset({"REFUNDED", "DISPUTED"}),
    "REFUNDED": frozenset(),
    "VOID": frozenset(),
    "CANCELLED": frozenset(),
    "UNCOLLECTIBLE": frozenset(),
}


@dataclass(frozen=True)
class InvoiceTransitionEvidence:
    approval_decision_hash: str = ""
    provider_delivery_receipt_hash: str = ""
    payment_receipt_hash: str = ""
    refund_receipt_hash: str = ""
    dispute_record_hash: str = ""
    writeoff_decision_hash: str = ""


@dataclass(frozen=True)
class InvoiceStateRecord:
    invoice_id: str
    invoice_hash: str
    state: str
    total: Decimal
    paid_amount: Decimal
    refunded_amount: Decimal
    currency: str
    revision: int = 1

    def __post_init__(self) -> None:
        if self.state not in INVOICE_STATES:
            raise ValueError(f"unsupported invoice state: {self.state}")
        object.__setattr__(self, "total", money(self.total))
        object.__setattr__(self, "paid_amount", money(self.paid_amount))
        object.__setattr__(self, "refunded_amount", money(self.refunded_amount))
        if self.total < Decimal("0") or self.paid_amount < Decimal("0") or self.refunded_amount < Decimal("0"):
            raise ValueError("invoice amounts cannot be negative")
        if self.paid_amount > self.total:
            raise ValueError("paid_amount cannot exceed invoice total")
        if self.refunded_amount > self.paid_amount:
            raise ValueError("refunded_amount cannot exceed paid amount")
        if self.revision < 1:
            raise ValueError("revision must be positive")


@dataclass(frozen=True)
class InvoiceTransitionReceipt:
    invoice_id: str
    from_state: str
    to_state: str
    prior_revision: int
    resulting_revision: int
    transition_hash: str
    external_action_performed: bool = False


class InvoiceLifecycle:
    """Pure fail-closed invoice state machine.

    It validates receipts that must already exist. It never sends an invoice,
    charges a payment method, issues a refund, or opens a dispute externally.
    """

    def transition(
        self,
        record: InvoiceStateRecord,
        to_state: str,
        *,
        evidence: InvoiceTransitionEvidence,
        paid_amount: Decimal | int | str | None = None,
        refunded_amount: Decimal | int | str | None = None,
    ) -> tuple[InvoiceStateRecord, InvoiceTransitionReceipt]:
        if to_state not in INVOICE_STATES:
            raise ValueError(f"unsupported invoice target state: {to_state}")
        allowed = ALLOWED_TRANSITIONS.get(record.state, frozenset())
        if to_state not in allowed:
            raise ValueError(f"invalid invoice transition: {record.state} -> {to_state}")

        self._require_transition_evidence(record.state, to_state, evidence)

        next_paid = record.paid_amount if paid_amount is None else money(paid_amount)
        next_refunded = record.refunded_amount if refunded_amount is None else money(refunded_amount)
        if next_paid < record.paid_amount:
            raise ValueError("paid_amount cannot decrease")
        if next_refunded < record.refunded_amount:
            raise ValueError("refunded_amount cannot decrease")
        if next_paid > record.total:
            raise ValueError("paid_amount cannot exceed total")
        if next_refunded > next_paid:
            raise ValueError("refund cannot exceed paid amount")

        if to_state == "PARTIALLY_PAID" and not Decimal("0") < next_paid < record.total:
            raise ValueError("PARTIALLY_PAID requires 0 < paid_amount < total")
        if to_state in {"PAID", "SETTLED"} and next_paid != record.total:
            raise ValueError(f"{to_state} requires paid_amount == total")
        if to_state == "PARTIALLY_REFUNDED" and not Decimal("0") < next_refunded < next_paid:
            raise ValueError("PARTIALLY_REFUNDED requires a positive partial refund")
        if to_state == "REFUNDED" and next_refunded != next_paid:
            raise ValueError("REFUNDED requires refunded_amount == paid_amount")

        resulting = InvoiceStateRecord(
            invoice_id=record.invoice_id,
            invoice_hash=record.invoice_hash,
            state=to_state,
            total=record.total,
            paid_amount=next_paid,
            refunded_amount=next_refunded,
            currency=record.currency,
            revision=record.revision + 1,
        )
        transition_hash = canonical_sha256(
            {
                "invoice_id": record.invoice_id,
                "invoice_hash": record.invoice_hash,
                "from_state": record.state,
                "to_state": to_state,
                "prior_revision": record.revision,
                "resulting_revision": resulting.revision,
                "paid_amount": resulting.paid_amount,
                "refunded_amount": resulting.refunded_amount,
                "evidence": evidence.__dict__,
            }
        )
        return resulting, InvoiceTransitionReceipt(
            invoice_id=record.invoice_id,
            from_state=record.state,
            to_state=to_state,
            prior_revision=record.revision,
            resulting_revision=resulting.revision,
            transition_hash=transition_hash,
            external_action_performed=False,
        )

    @staticmethod
    def _require_transition_evidence(
        from_state: str,
        to_state: str,
        evidence: InvoiceTransitionEvidence,
    ) -> None:
        if to_state == "APPROVED" and not evidence.approval_decision_hash:
            raise PermissionError("APPROVED requires an approval decision hash")
        if to_state == "DELIVERED" and not evidence.provider_delivery_receipt_hash:
            raise PermissionError("DELIVERED requires a provider delivery receipt")
        if to_state in {"PARTIALLY_PAID", "PAID", "SETTLED"} and not evidence.payment_receipt_hash:
            raise PermissionError(f"{to_state} requires a payment receipt")
        if to_state in {"PARTIALLY_REFUNDED", "REFUNDED"} and not evidence.refund_receipt_hash:
            raise PermissionError(f"{to_state} requires a refund receipt")
        if to_state == "DISPUTED" and not evidence.dispute_record_hash:
            raise PermissionError("DISPUTED requires a dispute record")
        if to_state == "UNCOLLECTIBLE" and not evidence.writeoff_decision_hash:
            raise PermissionError("UNCOLLECTIBLE requires a write-off decision")
