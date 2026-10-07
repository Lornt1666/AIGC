from src.core.omega_worker_evidence_ledger import EvidenceLedger
from src.core.omega_worker_revenue_pipeline import DeliveryRevenuePipeline, RevenueEvidence, RevenueStateError


def delivery():
    return RevenueEvidence("d1", "delivery", "synthetic-proof", {"accepted": True})


def payment():
    return RevenueEvidence("p1", "payment", "synthetic-payment-proof", {"amount": 100, "currency": "CAD"})


def test_delivery_is_evidence_gated():
    result=DeliveryRevenuePipeline().delivered("tc1", delivery())
    assert result.state=="DELIVERED"


def test_payment_is_never_assumed_from_delivery():
    pipe=DeliveryRevenuePipeline()
    result=pipe.payment_pending("tc1", delivery())
    assert result.state=="PAYMENT_PENDING"
    assert not any(e.record.get("state")=="PAID" for e in pipe.ledger.entries)


def test_payment_requires_explicit_payment_evidence():
    try:
        DeliveryRevenuePipeline().paid("tc1", delivery(), amount=100, currency="CAD")
    except RevenueStateError:
        pass
    else:
        raise AssertionError("delivery evidence must not authorize a PAID state")


def test_paid_requires_positive_verified_amount():
    try:
        DeliveryRevenuePipeline().paid("tc1", payment(), amount=0, currency="CAD")
    except RevenueStateError:
        pass
    else:
        raise AssertionError("zero payment must fail closed")


def test_learning_requires_explicit_outcome_and_preserves_ledger_integrity():
    pipe=DeliveryRevenuePipeline()
    result=pipe.learned("tc1", payment(), "customer accepted the deliverable")
    assert result.state=="LEARNED"
    assert pipe.ledger.verify()
    assert len(pipe.ledger.entries)==2


def test_empty_contract_id_fails_closed():
    try:
        DeliveryRevenuePipeline().delivered("", delivery())
    except RevenueStateError:
        pass
    else:
        raise AssertionError("empty contract IDs must fail")
