from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

MONEY_QUANTUM = Decimal("0.01")
RATE_QUANTUM = Decimal("0.000001")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def rate(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, Mapping):
            return {str(k): normalize(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
        if isinstance(value, (list, tuple)):
            return [normalize(v) for v in value]
        return value

    encoded = json.dumps(normalize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RevenuePolicy:
    policy_id: str
    currency: str = "CAD"
    placement_payer: str = "EMPLOYER"
    worker_placement_fee_allowed: bool = False
    require_jurisdiction_approval: bool = True
    require_verified_compensation: bool = True
    require_verified_success_event: bool = True
    require_verified_attribution: bool = True
    require_active_agreement: bool = True
    require_invoice_email_verification: bool = True
    maximum_commission_rate: Decimal = Decimal("0.25")
    maximum_compute_markup_rate: Decimal = Decimal("0.50")

    def __post_init__(self) -> None:
        object.__setattr__(self, "maximum_commission_rate", rate(self.maximum_commission_rate))
        object.__setattr__(self, "maximum_compute_markup_rate", rate(self.maximum_compute_markup_rate))
        if not self.policy_id:
            raise ValueError("policy_id is required")
        if self.placement_payer not in {"EMPLOYER", "MARKETPLACE_CUSTOMER", "CONTRACT_DEFINED"}:
            raise ValueError("unsupported placement payer")
        if not Decimal("0") <= self.maximum_commission_rate <= Decimal("1"):
            raise ValueError("maximum_commission_rate must be between 0 and 1")
        if self.maximum_compute_markup_rate < Decimal("0"):
            raise ValueError("maximum_compute_markup_rate cannot be negative")


@dataclass(frozen=True)
class CommercialAgreement:
    agreement_id: str
    employer_id: str
    jurisdiction: str
    billing_email: str
    commission_rate: Decimal
    service_type: str = "EMPLOYMENT_PLACEMENT"
    payer_model: str = "EMPLOYER"
    jurisdiction_decision_id: str = ""
    compensation_base: str = "ELIGIBLE_GROSS_COMPENSATION"
    compute_pricing_mode: str = "PASS_THROUGH_PLUS_MARGIN"
    compute_markup_rate: Decimal = Decimal("0")
    currency: str = "CAD"
    active: bool = True
    jurisdiction_approved: bool = False  # legacy/display-only; engine does not trust this boolean
    starts_at: str = ""
    expires_at: str = ""
    terms_version: str = "v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "commission_rate", rate(self.commission_rate))
        object.__setattr__(self, "compute_markup_rate", rate(self.compute_markup_rate))
        if not self.agreement_id or not self.employer_id:
            raise ValueError("agreement_id and employer_id are required")
        if "@" not in self.billing_email:
            raise ValueError("billing_email must be syntactically email-like")
        if not Decimal("0") <= self.commission_rate <= Decimal("1"):
            raise ValueError("commission_rate must be between 0 and 1")
        if self.compute_markup_rate < Decimal("0"):
            raise ValueError("compute_markup_rate cannot be negative")
        if self.payer_model not in {"EMPLOYER", "MARKETPLACE_CUSTOMER", "CONTRACT_DEFINED"}:
            raise ValueError("unsupported payer_model")
        if self.compute_pricing_mode not in {
            "ABSORBED_BY_PLATFORM",
            "PASS_THROUGH",
            "PASS_THROUGH_PLUS_MARGIN",
            "INCLUDED_IN_SUCCESS_FEE",
        }:
            raise ValueError("unsupported compute_pricing_mode")

    @property
    def agreement_hash(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True)
class PlacementEvent:
    placement_id: str
    agreement_id: str
    employer_id: str
    worker_reference: str
    billing_period: str
    eligible_compensation: Decimal
    compensation_verified: bool
    success_event_verified: bool
    attribution_status: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "eligible_compensation", money(self.eligible_compensation))
        if self.eligible_compensation < Decimal("0"):
            raise ValueError("eligible_compensation cannot be negative")
        if self.attribution_status not in {"ATTRIBUTED", "SHARED_ATTRIBUTION", "DISPUTED", "UNKNOWN", "NOT_ATTRIBUTED"}:
            raise ValueError("unsupported attribution_status")

    @property
    def event_hash(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True)
class ComputeUsageEvent:
    usage_id: str
    task_id: str
    placement_id: str
    provider: str
    resource_type: str
    quantity: Decimal
    unit_cost: Decimal
    currency: str = "CAD"
    evidence_ref: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", Decimal(str(self.quantity)))
        object.__setattr__(self, "unit_cost", money(self.unit_cost))
        if self.quantity < Decimal("0") or self.unit_cost < Decimal("0"):
            raise ValueError("compute quantity and unit cost cannot be negative")

    @property
    def actual_cost(self) -> Decimal:
        return money(self.quantity * self.unit_cost)


@dataclass(frozen=True)
class CommissionCalculation:
    calculation_id: str
    placement_id: str
    agreement_id: str
    billing_period: str
    compensation_base: Decimal
    commission_rate: Decimal
    finder_fee: Decimal
    compute_cost: Decimal
    compute_recovery: Decimal
    subtotal: Decimal
    currency: str
    calculation_hash: str


@dataclass(frozen=True)
class BillingAuthorizationDecision:
    decision_id: str
    placement_id: str
    agreement_id: str
    allowed: bool
    reasons: tuple[str, ...]
    billing_idempotency_key: str
    decision_hash: str


@dataclass(frozen=True)
class InvoiceCandidate:
    invoice_candidate_id: str
    agreement_id: str
    placement_id: str
    employer_id: str
    billing_email: str
    billing_period: str
    currency: str
    finder_fee: Decimal
    compute_recovery: Decimal
    authorized_services: Decimal
    tax: Decimal
    total: Decimal
    billing_idempotency_key: str
    evidence_refs: tuple[str, ...]
    calculation_hash: str
    authorization_decision_hash: str
    status: str = "DRAFT"

    @property
    def invoice_hash(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True)
class InvoiceEmailDraft:
    invoice_candidate_id: str
    recipient: str
    subject: str
    body: str
    invoice_hash: str
    external_action_performed: bool = False


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    account: str
    direction: str
    amount: Decimal
    currency: str
    reference_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", money(self.amount))
        if self.direction not in {"DEBIT", "CREDIT"}:
            raise ValueError("direction must be DEBIT or CREDIT")
        if self.amount < Decimal("0"):
            raise ValueError("ledger amount cannot be negative")


@dataclass(frozen=True)
class LedgerTransaction:
    transaction_id: str
    entries: tuple[LedgerEntry, ...]
    reference_id: str
    transaction_hash: str

    def __post_init__(self) -> None:
        debits = sum((entry.amount for entry in self.entries if entry.direction == "DEBIT"), Decimal("0"))
        credits = sum((entry.amount for entry in self.entries if entry.direction == "CREDIT"), Decimal("0"))
        if money(debits) != money(credits):
            raise ValueError("ledger transaction is not balanced")


def evidence_union(*groups: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({item for group in groups for item in group if item}))
