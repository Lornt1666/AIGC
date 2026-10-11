from decimal import Decimal

import pytest

from src.revenue_omega.invoice_document import InvoiceDocumentRenderer
from src.revenue_omega.models import InvoiceCandidate


def invoice(**overrides):
    values = dict(
        invoice_candidate_id="REV-INV-1",
        agreement_id="AGR-1",
        placement_id="PLACE-1",
        employer_id="EMP-1",
        billing_email="billing@example.test",
        billing_period="2026-08-01/2026-08-14",
        currency="CAD",
        finder_fee=Decimal("100.00"),
        compute_recovery=Decimal("2.20"),
        authorized_services=Decimal("10.00"),
        tax=Decimal("5.61"),
        total=Decimal("117.81"),
        billing_idempotency_key="b" * 64,
        evidence_refs=("E1",),
        calculation_hash="c" * 64,
        authorization_decision_hash="d" * 64,
        status="DRAFT",
    )
    values.update(overrides)
    return InvoiceCandidate(**values)


def render(candidate=None, **kwargs):
    return InvoiceDocumentRenderer().render_html(
        candidate or invoice(),
        seller_name=kwargs.get("seller_name", "AIGC Operating Entity"),
        seller_contact=kwargs.get("seller_contact", "billing@example.test"),
        payer_name=kwargs.get("payer_name", "Employer Inc."),
        issue_date="2026-08-09",
        due_date="2026-09-08",
    )


def test_invoice_renderer_is_deterministic_and_non_executing():
    first = render()
    second = render()
    assert first.document_hash == second.document_hash
    assert first.body == second.body
    assert first.external_action_performed is False
    assert "CAD 117.81" in first.body


def test_invoice_renderer_escapes_untrusted_text():
    doc = render(payer_name="<script>alert(1)</script>")
    assert "<script>" not in doc.body
    assert "&lt;script&gt;" in doc.body


def test_invoice_renderer_rejects_line_item_total_mismatch():
    with pytest.raises(ValueError, match="do not add"):
        render(invoice(total=Decimal("999.00")))


def test_invoice_renderer_requires_identity_and_dates():
    with pytest.raises(ValueError, match="seller_name"):
        InvoiceDocumentRenderer().render_html(
            invoice(),
            seller_name="",
            seller_contact="billing@example.test",
            payer_name="Employer",
            issue_date="2026-08-09",
            due_date="2026-09-08",
        )


def test_document_states_no_worker_wage_deduction_authority():
    assert "does not authorize a worker wage deduction" in render().body
