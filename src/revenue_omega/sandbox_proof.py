from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib

from .engine import RevenueOmegaEngine
from .invoice_document import InvoiceDocumentRenderer
from .invoice_lifecycle import InvoiceLifecycle, InvoiceStateRecord, InvoiceTransitionEvidence
from .jurisdiction import JurisdictionDecision, MappingJurisdictionDecisionRepository
from .models import CommercialAgreement, ComputeUsageEvent, PlacementEvent, RevenuePolicy, canonical_sha256
from .permits import CommercialExecutionPermit, SandboxPermitLedger
from .sandbox import SandboxEmailAdapter, SandboxPaymentAdapter
from .settlement import ledger_for_payment_settlement


@dataclass(frozen=True)
class RevenueOmegaSandboxProofReceipt:
    status: str
    agreement_hash: str
    jurisdiction_decision_hash: str
    placement_hash: str
    billing_decision_hash: str
    calculation_hash: str
    invoice_hash: str
    invoice_document_hash: str
    email_receipt_hash: str
    payment_session_receipt_hash: str
    payment_receipt_hash: str
    issuance_ledger_hash: str
    settlement_ledger_hash: str
    final_invoice_state: str
    total: str
    currency: str
    network_call_performed: bool
    real_money_moved: bool
    external_action_performed: bool
    proof_hash: str


def run_sandbox_proof() -> RevenueOmegaSandboxProofReceipt:
    proof_time = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)
    proof_time_text = proof_time.isoformat()

    jurisdiction = JurisdictionDecision.create(
        decision_id="JUR-SANDBOX-CA-AB-V1",
        jurisdiction="CA-AB",
        service_type="EMPLOYMENT_PLACEMENT",
        payer_model="EMPLOYER",
        allowed=True,
        conditions=("SANDBOX_ONLY", "NO_REAL_EMPLOYMENT_AGENCY_ACTIVITY"),
        reviewed_by="AIGC_TEST_FIXTURE",
        reviewed_at="2026-08-01T00:00:00+00:00",
        expires_at="2099-01-01T00:00:00+00:00",
        source_refs=("SYNTHETIC_TEST_ONLY",),
    )
    repository = MappingJurisdictionDecisionRepository({jurisdiction.decision_id: jurisdiction})
    engine = RevenueOmegaEngine(RevenuePolicy(policy_id="revenue-omega-sandbox-v1"), repository)

    agreement = CommercialAgreement(
        agreement_id="AGR-SANDBOX-1",
        employer_id="EMP-SANDBOX-1",
        jurisdiction="CA-AB",
        billing_email="billing@example.test",
        commission_rate=Decimal("0.05"),
        service_type="EMPLOYMENT_PLACEMENT",
        payer_model="EMPLOYER",
        jurisdiction_decision_id=jurisdiction.decision_id,
        compute_pricing_mode="PASS_THROUGH_PLUS_MARGIN",
        compute_markup_rate=Decimal("0.10"),
        active=True,
    )
    placement = PlacementEvent(
        placement_id="PLACE-SANDBOX-1",
        agreement_id=agreement.agreement_id,
        employer_id=agreement.employer_id,
        worker_reference="SYNTHETIC-WORKER",
        billing_period="2026-08-01/2026-08-14",
        eligible_compensation=Decimal("2000.00"),
        compensation_verified=True,
        success_event_verified=True,
        attribution_status="ATTRIBUTED",
        evidence_refs=("SYNTHETIC-PLACEMENT-EVIDENCE",),
    )
    compute = ComputeUsageEvent(
        usage_id="USAGE-SANDBOX-1",
        task_id="TASK-SANDBOX-1",
        placement_id=placement.placement_id,
        provider="AIGC_TEST_PROVIDER",
        resource_type="synthetic_compute_unit",
        quantity=Decimal("10"),
        unit_cost=Decimal("0.20"),
        evidence_ref="SYNTHETIC-USAGE-EVIDENCE",
    )

    billing_decision = engine.authorize_billing(agreement, placement, billing_email_verified=True)
    if not billing_decision.allowed:
        raise AssertionError(f"synthetic billing unexpectedly denied: {billing_decision.reasons}")
    calculation = engine.calculate_commission(agreement, placement, [compute])
    invoice = engine.build_invoice_candidate(agreement, placement, calculation, billing_decision)

    lifecycle = InvoiceLifecycle()
    state = InvoiceStateRecord(
        invoice_id=invoice.invoice_candidate_id,
        invoice_hash=invoice.invoice_hash,
        state="DRAFT",
        total=invoice.total,
        paid_amount=Decimal("0"),
        refunded_amount=Decimal("0"),
        currency=invoice.currency,
    )
    approval_hash = canonical_sha256({"kind": "SANDBOX_INVOICE_APPROVAL", "invoice_hash": invoice.invoice_hash})
    state, _ = lifecycle.transition(
        state,
        "APPROVED",
        evidence=InvoiceTransitionEvidence(approval_decision_hash=approval_hash),
    )
    state, _ = lifecycle.transition(state, "ISSUED", evidence=InvoiceTransitionEvidence())

    document = InvoiceDocumentRenderer().render_html(
        invoice,
        seller_name="AIGC SANDBOX",
        seller_contact="sandbox@example.test",
        payer_name="Synthetic Employer",
        issue_date="2026-08-09",
        due_date="2026-09-08",
        payment_instructions="SANDBOX ONLY — no real payment is requested.",
    )
    draft = engine.render_invoice_email(invoice)

    email_permit = CommercialExecutionPermit.create(
        permit_id="PERMIT-SANDBOX-EMAIL-1",
        action="SEND_INVOICE_SANDBOX",
        principal_id="AIGC_SANDBOX_OPERATOR",
        invoice_hash=invoice.invoice_hash,
        currency=invoice.currency,
        maximum_amount=invoice.total,
        maximum_calls=1,
        environment="SANDBOX",
        issued_at="2026-08-09T09:00:00+00:00",
        expires_at="2026-08-09T11:00:00+00:00",
        decision_hash=approval_hash,
    )
    email_ledger = SandboxPermitLedger()
    email_receipt = SandboxEmailAdapter().deliver(
        draft,
        invoice=invoice,
        permit=email_permit,
        ledger=email_ledger,
        principal_id="AIGC_SANDBOX_OPERATOR",
        now=proof_time,
    )
    state, _ = lifecycle.transition(
        state,
        "DELIVERED",
        evidence=InvoiceTransitionEvidence(provider_delivery_receipt_hash=email_receipt.receipt_hash),
    )
    state, _ = lifecycle.transition(state, "OPEN", evidence=InvoiceTransitionEvidence())

    payment_permit = CommercialExecutionPermit.create(
        permit_id="PERMIT-SANDBOX-PAYMENT-1",
        action="CREATE_PAYMENT_SANDBOX",
        principal_id="AIGC_SANDBOX_OPERATOR",
        invoice_hash=invoice.invoice_hash,
        currency=invoice.currency,
        maximum_amount=invoice.total,
        maximum_calls=1,
        environment="SANDBOX",
        issued_at="2026-08-09T09:00:00+00:00",
        expires_at="2026-08-09T11:00:00+00:00",
        decision_hash=approval_hash,
    )
    payment_ledger = SandboxPermitLedger()
    payment_adapter = SandboxPaymentAdapter()
    session = payment_adapter.create_session(
        invoice,
        permit=payment_permit,
        ledger=payment_ledger,
        principal_id="AIGC_SANDBOX_OPERATOR",
        now=proof_time,
    )
    verification_material = hashlib.sha256(b"revenue-omega-sandbox-fixture").digest()
    webhook = payment_adapter.sign_settled_webhook(
        session,
        verification_material=verification_material,
        occurred_at=proof_time_text,
    )
    payment_receipt = payment_adapter.verify_settled_webhook(
        webhook,
        session=session,
        verification_material=verification_material,
    )
    state, _ = lifecycle.transition(
        state,
        "PAID",
        evidence=InvoiceTransitionEvidence(payment_receipt_hash=payment_receipt.receipt_hash),
        paid_amount=invoice.total,
    )
    state, _ = lifecycle.transition(
        state,
        "SETTLED",
        evidence=InvoiceTransitionEvidence(payment_receipt_hash=payment_receipt.receipt_hash),
        paid_amount=invoice.total,
    )

    issuance_ledger = engine.ledger_for_issued_invoice(invoice)
    settlement_ledger = ledger_for_payment_settlement(
        invoice,
        payment_receipt_hash=payment_receipt.receipt_hash,
    )

    payload = {
        "status": "SANDBOX_SETTLED",
        "agreement_hash": agreement.agreement_hash,
        "jurisdiction_decision_hash": jurisdiction.decision_hash,
        "placement_hash": placement.event_hash,
        "billing_decision_hash": billing_decision.decision_hash,
        "calculation_hash": calculation.calculation_hash,
        "invoice_hash": invoice.invoice_hash,
        "invoice_document_hash": document.document_hash,
        "email_receipt_hash": email_receipt.receipt_hash,
        "payment_session_receipt_hash": session.receipt_hash,
        "payment_receipt_hash": payment_receipt.receipt_hash,
        "issuance_ledger_hash": issuance_ledger.transaction_hash,
        "settlement_ledger_hash": settlement_ledger.transaction_hash,
        "final_invoice_state": state.state,
        "total": format(invoice.total, "f"),
        "currency": invoice.currency,
        "network_call_performed": False,
        "real_money_moved": False,
        "external_action_performed": False,
    }
    return RevenueOmegaSandboxProofReceipt(
        proof_hash=canonical_sha256(payload),
        **payload,
    )
