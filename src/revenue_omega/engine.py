from __future__ import annotations

import hashlib
from dataclasses import asdict
from decimal import Decimal
from typing import Iterable

from .models import (
    BillingAuthorizationDecision,
    CommercialAgreement,
    CommissionCalculation,
    ComputeUsageEvent,
    InvoiceCandidate,
    InvoiceEmailDraft,
    LedgerEntry,
    LedgerTransaction,
    PlacementEvent,
    RevenuePolicy,
    canonical_sha256,
    evidence_union,
    money,
)


class RevenueOmegaEngine:
    """Pure deterministic Revenue-Ω kernel.

    This class performs no email send, payment, payroll mutation, cloud mutation,
    or other external effect. It calculates, authorizes, and prepares artifacts
    that downstream governed adapters may consume after separate authorization.
    """

    def __init__(self, policy: RevenuePolicy):
        self.policy = policy

    def billing_idempotency_key(self, agreement: CommercialAgreement, placement: PlacementEvent) -> str:
        seed = "|".join(
            [
                agreement.agreement_id,
                placement.placement_id,
                placement.billing_period,
                placement.event_hash,
                agreement.agreement_hash,
            ]
        )
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def authorize_billing(
        self,
        agreement: CommercialAgreement,
        placement: PlacementEvent,
        *,
        billing_email_verified: bool,
    ) -> BillingAuthorizationDecision:
        reasons: list[str] = []

        if self.policy.placement_payer != "EMPLOYER":
            reasons.append("POLICY_PAYER_NOT_EMPLOYER")
        if agreement.employer_id != placement.employer_id:
            reasons.append("EMPLOYER_MISMATCH")
        if agreement.agreement_id != placement.agreement_id:
            reasons.append("AGREEMENT_MISMATCH")
        if self.policy.require_active_agreement and not agreement.active:
            reasons.append("AGREEMENT_INACTIVE")
        if self.policy.require_jurisdiction_approval and not agreement.jurisdiction_approved:
            reasons.append("JURISDICTION_NOT_APPROVED")
        if agreement.commission_rate > self.policy.maximum_commission_rate:
            reasons.append("COMMISSION_RATE_EXCEEDS_POLICY")
        if agreement.compute_markup_rate > self.policy.maximum_compute_markup_rate:
            reasons.append("COMPUTE_MARKUP_EXCEEDS_POLICY")
        if self.policy.require_verified_compensation and not placement.compensation_verified:
            reasons.append("COMPENSATION_UNVERIFIED")
        if self.policy.require_verified_success_event and not placement.success_event_verified:
            reasons.append("SUCCESS_EVENT_UNVERIFIED")
        if self.policy.require_verified_attribution and placement.attribution_status != "ATTRIBUTED":
            reasons.append("PLACEMENT_NOT_EXACTLY_ATTRIBUTED")
        if self.policy.require_invoice_email_verification and not billing_email_verified:
            reasons.append("BILLING_EMAIL_UNVERIFIED")
        if placement.eligible_compensation <= Decimal("0"):
            reasons.append("NONPOSITIVE_COMPENSATION_BASE")

        key = self.billing_idempotency_key(agreement, placement)
        allowed = not reasons
        payload = {
            "policy_id": self.policy.policy_id,
            "agreement_hash": agreement.agreement_hash,
            "placement_hash": placement.event_hash,
            "billing_idempotency_key": key,
            "allowed": allowed,
            "reasons": reasons,
        }
        decision_hash = canonical_sha256(payload)
        return BillingAuthorizationDecision(
            decision_id=f"REV-AUTH-{decision_hash[:20].upper()}",
            placement_id=placement.placement_id,
            agreement_id=agreement.agreement_id,
            allowed=allowed,
            reasons=tuple(reasons),
            billing_idempotency_key=key,
            decision_hash=decision_hash,
        )

    def calculate_commission(
        self,
        agreement: CommercialAgreement,
        placement: PlacementEvent,
        compute_events: Iterable[ComputeUsageEvent],
    ) -> CommissionCalculation:
        if agreement.agreement_id != placement.agreement_id:
            raise ValueError("agreement and placement do not match")

        compute_events = tuple(compute_events)
        for event in compute_events:
            if event.placement_id != placement.placement_id:
                raise ValueError("compute usage event belongs to another placement")
            if event.currency != agreement.currency:
                raise ValueError("compute usage currency mismatch")

        finder_fee = money(placement.eligible_compensation * agreement.commission_rate)
        compute_cost = money(sum((event.actual_cost for event in compute_events), Decimal("0")))

        if agreement.compute_pricing_mode == "ABSORBED_BY_PLATFORM":
            compute_recovery = money(0)
        elif agreement.compute_pricing_mode == "PASS_THROUGH":
            compute_recovery = compute_cost
        elif agreement.compute_pricing_mode == "PASS_THROUGH_PLUS_MARGIN":
            compute_recovery = money(compute_cost * (Decimal("1") + agreement.compute_markup_rate))
        elif agreement.compute_pricing_mode == "INCLUDED_IN_SUCCESS_FEE":
            compute_recovery = money(0)
        else:  # guarded by CommercialAgreement validation
            raise ValueError("unsupported compute pricing mode")

        subtotal = money(finder_fee + compute_recovery)
        payload = {
            "agreement_hash": agreement.agreement_hash,
            "placement_hash": placement.event_hash,
            "compute_usage_hashes": [canonical_sha256(asdict(event)) for event in compute_events],
            "compensation_base": placement.eligible_compensation,
            "commission_rate": agreement.commission_rate,
            "finder_fee": finder_fee,
            "compute_cost": compute_cost,
            "compute_recovery": compute_recovery,
            "subtotal": subtotal,
            "currency": agreement.currency,
        }
        calculation_hash = canonical_sha256(payload)
        return CommissionCalculation(
            calculation_id=f"REV-CALC-{calculation_hash[:20].upper()}",
            placement_id=placement.placement_id,
            agreement_id=agreement.agreement_id,
            billing_period=placement.billing_period,
            compensation_base=placement.eligible_compensation,
            commission_rate=agreement.commission_rate,
            finder_fee=finder_fee,
            compute_cost=compute_cost,
            compute_recovery=compute_recovery,
            subtotal=subtotal,
            currency=agreement.currency,
            calculation_hash=calculation_hash,
        )

    def build_invoice_candidate(
        self,
        agreement: CommercialAgreement,
        placement: PlacementEvent,
        calculation: CommissionCalculation,
        decision: BillingAuthorizationDecision,
        *,
        authorized_services: Decimal | int | str = Decimal("0"),
        tax: Decimal | int | str = Decimal("0"),
    ) -> InvoiceCandidate:
        if not decision.allowed:
            raise PermissionError("billing decision is not authorized")
        if calculation.placement_id != placement.placement_id:
            raise ValueError("calculation placement mismatch")
        if decision.placement_id != placement.placement_id:
            raise ValueError("authorization placement mismatch")
        if decision.agreement_id != agreement.agreement_id:
            raise ValueError("authorization agreement mismatch")
        if decision.billing_idempotency_key != self.billing_idempotency_key(agreement, placement):
            raise ValueError("billing authorization is stale or tampered")

        services = money(authorized_services)
        tax_amount = money(tax)
        if services < Decimal("0") or tax_amount < Decimal("0"):
            raise ValueError("authorized services and tax cannot be negative")

        total = money(calculation.subtotal + services + tax_amount)
        evidence = evidence_union(placement.evidence_refs)
        seed = {
            "agreement_id": agreement.agreement_id,
            "placement_id": placement.placement_id,
            "billing_period": placement.billing_period,
            "idempotency_key": decision.billing_idempotency_key,
            "calculation_hash": calculation.calculation_hash,
            "authorization_decision_hash": decision.decision_hash,
            "total": total,
        }
        invoice_id = canonical_sha256(seed)
        return InvoiceCandidate(
            invoice_candidate_id=f"REV-INV-{invoice_id[:20].upper()}",
            agreement_id=agreement.agreement_id,
            placement_id=placement.placement_id,
            employer_id=agreement.employer_id,
            billing_email=agreement.billing_email,
            billing_period=placement.billing_period,
            currency=agreement.currency,
            finder_fee=calculation.finder_fee,
            compute_recovery=calculation.compute_recovery,
            authorized_services=services,
            tax=tax_amount,
            total=total,
            billing_idempotency_key=decision.billing_idempotency_key,
            evidence_refs=evidence,
            calculation_hash=calculation.calculation_hash,
            authorization_decision_hash=decision.decision_hash,
            status="DRAFT",
        )

    def render_invoice_email(self, invoice: InvoiceCandidate) -> InvoiceEmailDraft:
        subject = f"AIGC Invoice Candidate {invoice.invoice_candidate_id} — Placement {invoice.placement_id}"
        body = "\n".join(
            [
                "AIGC Revenue-Ω billing notice",
                "",
                f"Placement: {invoice.placement_id}",
                f"Billing period: {invoice.billing_period}",
                f"Finder/success fee: {invoice.currency} {invoice.finder_fee}",
                f"Compute/runtime recovery: {invoice.currency} {invoice.compute_recovery}",
                f"Authorized services: {invoice.currency} {invoice.authorized_services}",
                f"Tax: {invoice.currency} {invoice.tax}",
                f"Total: {invoice.currency} {invoice.total}",
                "",
                "This draft does not send email, request payment, or deduct wages.",
                "External delivery requires a separately authorized EmailBillingService action and provider receipt.",
            ]
        )
        return InvoiceEmailDraft(
            invoice_candidate_id=invoice.invoice_candidate_id,
            recipient=invoice.billing_email,
            subject=subject,
            body=body,
            invoice_hash=invoice.invoice_hash,
            external_action_performed=False,
        )

    def ledger_for_issued_invoice(self, invoice: InvoiceCandidate) -> LedgerTransaction:
        entries = (
            LedgerEntry(
                entry_id=f"{invoice.invoice_candidate_id}-AR",
                account="ACCOUNTS_RECEIVABLE",
                direction="DEBIT",
                amount=invoice.total,
                currency=invoice.currency,
                reference_id=invoice.invoice_candidate_id,
            ),
            LedgerEntry(
                entry_id=f"{invoice.invoice_candidate_id}-REV",
                account="AIGC_REVENUE_AND_TAX_CLEARING",
                direction="CREDIT",
                amount=invoice.total,
                currency=invoice.currency,
                reference_id=invoice.invoice_candidate_id,
            ),
        )
        tx_hash = canonical_sha256(
            {
                "reference_id": invoice.invoice_candidate_id,
                "entries": [asdict(entry) for entry in entries],
            }
        )
        return LedgerTransaction(
            transaction_id=f"REV-LEDGER-{tx_hash[:20].upper()}",
            entries=entries,
            reference_id=invoice.invoice_candidate_id,
            transaction_hash=tx_hash,
        )
