from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .omega_worker_evidence_ledger import EvidenceLedger, EvidenceLedgerError


class RevenueStateError(ValueError):
    pass


@dataclass(frozen=True)
class RevenueEvidence:
    evidence_id: str
    kind: str
    source: str
    details: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.kind or not self.source:
            raise RevenueStateError("Revenue evidence requires identity, kind, and source.")
        if not isinstance(self.details, Mapping):
            raise RevenueStateError("Revenue evidence details must be a mapping.")


@dataclass(frozen=True)
class RevenueState:
    contract_id: str
    state: str
    evidence_id: str | None = None
    amount: int | None = None
    currency: str | None = None
    learning: str | None = None


class DeliveryRevenuePipeline:
    """Evidence-gated commercial state pipeline; never infers delivery or payment."""

    STATES = ("DELIVERED", "PAYMENT_PENDING", "PAID", "LEARNED")

    def __init__(self, ledger: EvidenceLedger | None = None) -> None:
        self.ledger = ledger or EvidenceLedger()

    def delivered(self, contract_id: str, evidence: RevenueEvidence) -> RevenueState:
        self._require_contract(contract_id)
        self._require_kind(evidence, "delivery")
        self.ledger.append(
            f"{contract_id}:DELIVERED:{evidence.evidence_id}",
            {"state": "DELIVERED", "evidence_id": evidence.evidence_id, "source": evidence.source},
        )
        return RevenueState(contract_id, "DELIVERED", evidence.evidence_id)

    def payment_pending(self, contract_id: str, delivery_evidence: RevenueEvidence) -> RevenueState:
        delivered = self.delivered(contract_id, delivery_evidence)
        self.ledger.append(
            f"{contract_id}:PAYMENT_PENDING",
            {"state": "PAYMENT_PENDING", "delivery_evidence_id": delivered.evidence_id},
        )
        return RevenueState(contract_id, "PAYMENT_PENDING", delivered.evidence_id)

    def paid(
        self,
        contract_id: str,
        payment_evidence: RevenueEvidence,
        *,
        amount: int,
        currency: str,
    ) -> RevenueState:
        self._require_contract(contract_id)
        self._require_kind(payment_evidence, "payment")
        if amount <= 0 or not currency:
            raise RevenueStateError("Verified payment requires a positive amount and currency.")
        self.ledger.append(
            f"{contract_id}:PAID:{payment_evidence.evidence_id}",
            {
                "state": "PAID",
                "evidence_id": payment_evidence.evidence_id,
                "source": payment_evidence.source,
                "amount": amount,
                "currency": currency,
            },
        )
        return RevenueState(contract_id, "PAID", payment_evidence.evidence_id, amount, currency)

    def learned(self, contract_id: str, payment_evidence: RevenueEvidence, learning: str) -> RevenueState:
        if not learning:
            raise RevenueStateError("Learning outcome is required.")
        paid = self.paid(
            contract_id,
            payment_evidence,
            amount=int(payment_evidence.details.get("amount", 0)),
            currency=str(payment_evidence.details.get("currency", "")),
        )
        self.ledger.append(
            f"{contract_id}:LEARNED",
            {"state": "LEARNED", "payment_evidence_id": paid.evidence_id, "learning": learning},
        )
        return RevenueState(contract_id, "LEARNED", paid.evidence_id, paid.amount, paid.currency, learning)

    @staticmethod
    def _require_contract(contract_id: str) -> None:
        if not contract_id:
            raise RevenueStateError("contract_id is required.")

    @staticmethod
    def _require_kind(evidence: RevenueEvidence, expected: str) -> None:
        if evidence.kind != expected:
            raise RevenueStateError(f"Expected {expected} evidence, received {evidence.kind}.")
