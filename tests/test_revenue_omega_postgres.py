from dataclasses import replace
from decimal import Decimal

import pytest

from src.revenue_omega.engine import RevenueOmegaEngine
from src.revenue_omega.jurisdiction import JurisdictionDecision, MappingJurisdictionDecisionRepository
from src.revenue_omega.models import CommercialAgreement, PlacementEvent, RevenuePolicy
from src.revenue_omega.postgres import PostgresRevenueOmegaRepository, RevenueOmegaPersistenceConflict


class FakeResult:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeRevenueConnection:
    def __init__(self):
        self.reservations = {}
        self.commands = []

    def execute(self, sql, params=None, prepare=None):
        normalized = " ".join(sql.split())
        self.commands.append((normalized, params, prepare))
        if normalized.startswith("INSERT INTO revenue_omega_billing_reservations"):
            key = params[0]
            if key in self.reservations:
                return FakeResult(None)
            self.reservations[key] = {
                "request_digest": params[4],
                "decision_hash": params[5],
                "reservation_state": "RESERVED",
            }
            return FakeResult((key, params[4], params[5], "RESERVED"))
        if normalized.startswith("SELECT request_digest, decision_hash, reservation_state FROM revenue_omega_billing_reservations"):
            item = self.reservations.get(params[0])
            if item is None:
                return FakeResult(None)
            return FakeResult((item["request_digest"], item["decision_hash"], item["reservation_state"]))
        if normalized.startswith("UPDATE revenue_omega_billing_reservations SET reservation_state = 'RECONCILIATION_REQUIRED'"):
            key = params[2]
            item = self.reservations.get(key)
            if item is None:
                return FakeResult(None)
            item["reservation_state"] = "RECONCILIATION_REQUIRED"
            return FakeResult((key,))
        return FakeResult(None)


class FakeFactory:
    def __init__(self):
        self.connection = FakeRevenueConnection()
        self.governed_flags = []

    def run_with_retry(self, operation, *, governed_transition=False):
        self.governed_flags.append(governed_transition)
        return operation(self.connection)


def jurisdiction_decision():
    return JurisdictionDecision.create(
        decision_id="JUR-CA-AB-EMPLOYER-PLACEMENT-V1",
        jurisdiction="CA-AB",
        service_type="EMPLOYMENT_PLACEMENT",
        payer_model="EMPLOYER",
        allowed=True,
        conditions=("LICENCE_VERIFIED", "EMPLOYER_AGREEMENT_ACTIVE"),
        reviewed_by="QUALIFIED_REVIEWER",
        reviewed_at="2026-08-01T00:00:00+00:00",
        expires_at="2099-01-01T00:00:00+00:00",
        source_refs=("ALBERTA_EMPLOYMENT_AGENCY_RULES",),
    )


def agreement():
    return CommercialAgreement(
        agreement_id="AGR-1",
        employer_id="EMP-1",
        jurisdiction="CA-AB",
        billing_email="billing@example.test",
        commission_rate=Decimal("0.05"),
        service_type="EMPLOYMENT_PLACEMENT",
        payer_model="EMPLOYER",
        jurisdiction_decision_id="JUR-CA-AB-EMPLOYER-PLACEMENT-V1",
        compute_markup_rate=Decimal("0.10"),
        active=True,
    )


def placement():
    return PlacementEvent(
        placement_id="PLACE-1",
        agreement_id="AGR-1",
        employer_id="EMP-1",
        worker_reference="WORKER-HASH",
        billing_period="2026-08-01/2026-08-14",
        eligible_compensation=Decimal("2000"),
        compensation_verified=True,
        success_event_verified=True,
        attribution_status="ATTRIBUTED",
    )


def authorized_decision():
    jurisdiction = jurisdiction_decision()
    repository = MappingJurisdictionDecisionRepository({jurisdiction.decision_id: jurisdiction})
    engine = RevenueOmegaEngine(RevenuePolicy(policy_id="rev-v1"), repository)
    decision = engine.authorize_billing(agreement(), placement(), billing_email_verified=True)
    assert decision.allowed is True
    return decision


def test_exact_duplicate_billing_reservation_replays_without_second_creation():
    factory = FakeFactory()
    repository = PostgresRevenueOmegaRepository(factory)
    decision = authorized_decision()
    first = repository.reserve_billing(agreement=agreement(), placement=placement(), decision=decision)
    second = repository.reserve_billing(agreement=agreement(), placement=placement(), decision=decision)
    assert first.created is True
    assert second.created is False
    assert first.billing_idempotency_key == second.billing_idempotency_key
    assert first.request_digest == second.request_digest
    assert all(factory.governed_flags)
    assert len(factory.connection.reservations) == 1


def test_conflicting_replay_on_reserved_key_fails_closed():
    factory = FakeFactory()
    repository = PostgresRevenueOmegaRepository(factory)
    decision = authorized_decision()
    first = repository.reserve_billing(agreement=agreement(), placement=placement(), decision=decision)
    factory.connection.reservations[first.billing_idempotency_key]["decision_hash"] = "f" * 64
    with pytest.raises(RevenueOmegaPersistenceConflict, match="different immutable lineage"):
        repository.reserve_billing(agreement=agreement(), placement=placement(), decision=decision)


def test_denied_decision_never_reaches_database():
    factory = FakeFactory()
    repository = PostgresRevenueOmegaRepository(factory)
    denied = replace(authorized_decision(), allowed=False, reasons=("DENIED",))
    with pytest.raises(PermissionError):
        repository.reserve_billing(agreement=agreement(), placement=placement(), decision=denied)
    assert factory.governed_flags == []
    assert factory.connection.commands == []


def test_lineage_mismatch_never_reaches_database():
    factory = FakeFactory()
    repository = PostgresRevenueOmegaRepository(factory)
    bad = replace(authorized_decision(), placement_id="OTHER")
    with pytest.raises(RevenueOmegaPersistenceConflict, match="lineage mismatch"):
        repository.reserve_billing(agreement=agreement(), placement=placement(), decision=bad)
    assert factory.connection.commands == []


def test_indeterminate_external_result_can_be_marked_for_reconciliation():
    factory = FakeFactory()
    repository = PostgresRevenueOmegaRepository(factory)
    decision = authorized_decision()
    reservation = repository.reserve_billing(agreement=agreement(), placement=placement(), decision=decision)
    repository.mark_reconciliation_required(reservation.billing_idempotency_key, reason="provider outcome unknown")
    assert factory.connection.reservations[reservation.billing_idempotency_key]["reservation_state"] == "RECONCILIATION_REQUIRED"


def test_reconciliation_requires_existing_reservation():
    factory = FakeFactory()
    repository = PostgresRevenueOmegaRepository(factory)
    with pytest.raises(RevenueOmegaPersistenceConflict, match="does not exist"):
        repository.mark_reconciliation_required("0" * 64, reason="unknown")
