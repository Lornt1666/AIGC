from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Protocol

from .models import canonical_sha256, money, rate


@dataclass(frozen=True)
class TaxDecision:
    decision_id: str
    seller_jurisdiction: str
    buyer_jurisdiction: str
    service_type: str
    currency: str
    total_rate: Decimal
    effective_from: str
    effective_to: str
    source_refs: tuple[str, ...]
    reviewed_by: str
    decision_hash: str

    @classmethod
    def create(
        cls,
        *,
        decision_id: str,
        seller_jurisdiction: str,
        buyer_jurisdiction: str,
        service_type: str,
        currency: str,
        total_rate: Decimal | str | int,
        effective_from: str,
        effective_to: str,
        source_refs: tuple[str, ...],
        reviewed_by: str,
    ) -> "TaxDecision":
        normalized_rate = rate(total_rate)
        if not Decimal("0") <= normalized_rate <= Decimal("1"):
            raise ValueError("tax rate must be between 0 and 1")
        if not source_refs:
            raise ValueError("tax decision requires source references")
        start = date.fromisoformat(effective_from)
        end = date.fromisoformat(effective_to)
        if end <= start:
            raise ValueError("tax decision effective_to must be after effective_from")
        payload = {
            "decision_id": decision_id,
            "seller_jurisdiction": seller_jurisdiction,
            "buyer_jurisdiction": buyer_jurisdiction,
            "service_type": service_type,
            "currency": currency,
            "total_rate": normalized_rate,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "source_refs": source_refs,
            "reviewed_by": reviewed_by,
        }
        return cls(decision_hash=canonical_sha256(payload), **payload)

    def verify_integrity(self) -> bool:
        payload = asdict(self)
        supplied = payload.pop("decision_hash")
        return canonical_sha256(payload) == supplied

    def applies_on(self, invoice_date: str) -> bool:
        target = date.fromisoformat(invoice_date)
        return date.fromisoformat(self.effective_from) <= target < date.fromisoformat(self.effective_to)


class TaxDecisionRepository(Protocol):
    def get(self, decision_id: str) -> TaxDecision | None: ...


class MappingTaxDecisionRepository:
    def __init__(self, decisions: Mapping[str, TaxDecision]) -> None:
        self._decisions = dict(decisions)

    def get(self, decision_id: str) -> TaxDecision | None:
        return self._decisions.get(decision_id)


@dataclass(frozen=True)
class TaxCalculation:
    decision_id: str
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total_after_tax: Decimal
    currency: str
    calculation_hash: str


def calculate_tax(
    *,
    repository: TaxDecisionRepository,
    decision_id: str,
    seller_jurisdiction: str,
    buyer_jurisdiction: str,
    service_type: str,
    currency: str,
    subtotal: Decimal | str | int,
    invoice_date: str,
) -> TaxCalculation:
    decision = repository.get(decision_id)
    if decision is None:
        raise PermissionError("tax decision is not persisted")
    if not decision.verify_integrity():
        raise PermissionError("tax decision integrity check failed")
    if not decision.applies_on(invoice_date):
        raise PermissionError("tax decision is not current for invoice date")
    expected_scope = (
        seller_jurisdiction,
        buyer_jurisdiction,
        service_type,
        currency,
    )
    actual_scope = (
        decision.seller_jurisdiction,
        decision.buyer_jurisdiction,
        decision.service_type,
        decision.currency,
    )
    if expected_scope != actual_scope:
        raise PermissionError("tax decision scope mismatch")

    normalized_subtotal = money(subtotal)
    if normalized_subtotal < Decimal("0"):
        raise ValueError("tax subtotal cannot be negative")
    tax_amount = money(normalized_subtotal * decision.total_rate)
    total = money(normalized_subtotal + tax_amount)
    payload = {
        "decision_id": decision.decision_id,
        "decision_hash": decision.decision_hash,
        "subtotal": normalized_subtotal,
        "tax_rate": decision.total_rate,
        "tax_amount": tax_amount,
        "total_after_tax": total,
        "currency": currency,
        "invoice_date": invoice_date,
    }
    return TaxCalculation(
        decision_id=decision.decision_id,
        subtotal=normalized_subtotal,
        tax_rate=decision.total_rate,
        tax_amount=tax_amount,
        total_after_tax=total,
        currency=currency,
        calculation_hash=canonical_sha256(payload),
    )
