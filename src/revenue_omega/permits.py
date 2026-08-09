from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import MutableSet

from .models import canonical_sha256, money


SANDBOX_ACTIONS = {
    "SEND_INVOICE_SANDBOX",
    "CREATE_PAYMENT_SANDBOX",
    "REFUND_PAYMENT_SANDBOX",
}


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("permit timestamps require a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class CommercialExecutionPermit:
    permit_id: str
    action: str
    principal_id: str
    invoice_hash: str
    currency: str
    maximum_amount: Decimal
    maximum_calls: int
    environment: str
    issued_at: str
    expires_at: str
    decision_hash: str
    permit_hash: str

    @classmethod
    def create(
        cls,
        *,
        permit_id: str,
        action: str,
        principal_id: str,
        invoice_hash: str,
        currency: str,
        maximum_amount: Decimal | int | str,
        maximum_calls: int,
        environment: str,
        issued_at: str,
        expires_at: str,
        decision_hash: str,
    ) -> "CommercialExecutionPermit":
        amount = money(maximum_amount)
        payload = {
            "permit_id": permit_id,
            "action": action,
            "principal_id": principal_id,
            "invoice_hash": invoice_hash,
            "currency": currency,
            "maximum_amount": amount,
            "maximum_calls": maximum_calls,
            "environment": environment,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "decision_hash": decision_hash,
        }
        return cls(permit_hash=canonical_sha256(payload), **payload)

    def verify(
        self,
        *,
        action: str,
        principal_id: str,
        invoice_hash: str,
        amount: Decimal | int | str,
        currency: str,
        now: datetime | None = None,
    ) -> None:
        payload = asdict(self)
        supplied_hash = payload.pop("permit_hash")
        if canonical_sha256(payload) != supplied_hash:
            raise PermissionError("commercial permit integrity check failed")
        if self.environment != "SANDBOX":
            raise PermissionError("sandbox adapter refuses non-sandbox permit")
        if self.action not in SANDBOX_ACTIONS or self.action != action:
            raise PermissionError("commercial permit action mismatch")
        if self.principal_id != principal_id:
            raise PermissionError("commercial permit principal mismatch")
        if self.invoice_hash != invoice_hash:
            raise PermissionError("commercial permit invoice mismatch")
        if self.currency != currency:
            raise PermissionError("commercial permit currency mismatch")
        if money(amount) > self.maximum_amount:
            raise PermissionError("commercial permit amount ceiling exceeded")
        if self.maximum_calls != 1:
            raise PermissionError("sandbox commercial permits must be one-use")
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if current < _utc(self.issued_at) or current >= _utc(self.expires_at):
            raise PermissionError("commercial permit is outside its validity window")


class SandboxPermitLedger:
    """Test-only one-use permit ledger; production must use durable persistence."""

    def __init__(self) -> None:
        self._consumed: MutableSet[str] = set()

    def consume(self, permit: CommercialExecutionPermit) -> None:
        if permit.permit_id in self._consumed:
            raise PermissionError("commercial permit already consumed")
        self._consumed.add(permit.permit_id)

    def is_consumed(self, permit_id: str) -> bool:
        return permit_id in self._consumed
