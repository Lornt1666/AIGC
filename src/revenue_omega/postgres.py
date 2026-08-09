from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any, Mapping

from src.infrastructure.persistence.postgresql.runtime import PostgresConnectionFactory

from .models import BillingAuthorizationDecision, CommercialAgreement, PlacementEvent, canonical_sha256


class RevenueOmegaPersistenceError(RuntimeError):
    """Base Revenue-Ω persistence failure."""


class RevenueOmegaPersistenceConflict(RevenueOmegaPersistenceError):
    """Existing durable state conflicts with the requested immutable lineage."""


@dataclass(frozen=True)
class BillingReservationResult:
    billing_idempotency_key: str
    request_digest: str
    decision_hash: str
    state: str
    created: bool


class PostgresRevenueOmegaRepository:
    """Durable financial-intent repository using the canonical PostgreSQL factory.

    The unique billing idempotency key is reserved transactionally before any
    consequential invoice/email/payment adapter is permitted to execute. Exact
    replay returns the existing reservation; conflicting replay fails closed.
    """

    def __init__(self, factory: PostgresConnectionFactory) -> None:
        self.factory = factory

    @staticmethod
    def _json(value: Mapping[str, Any]) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def persist_agreement(self, agreement: CommercialAgreement, *, revision: int = 1) -> bool:
        if revision < 1:
            raise ValueError("revision must be positive")
        created_at = datetime.now(timezone.utc)
        payload = asdict(agreement)

        def operation(connection: Any) -> bool:
            row = connection.execute(
                """
                INSERT INTO revenue_omega_agreements(
                    agreement_id, revision, employer_id, jurisdiction,
                    service_type, payer_model, jurisdiction_decision_id,
                    currency, agreement_hash, agreement_json, active,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (agreement_id) DO NOTHING
                RETURNING agreement_hash
                """,
                (
                    agreement.agreement_id,
                    revision,
                    agreement.employer_id,
                    agreement.jurisdiction,
                    agreement.service_type,
                    agreement.payer_model,
                    agreement.jurisdiction_decision_id,
                    agreement.currency,
                    agreement.agreement_hash,
                    self._json(payload),
                    agreement.active,
                    created_at,
                    created_at,
                ),
            ).fetchone()
            if row is not None:
                return True
            existing = connection.execute(
                "SELECT agreement_hash FROM revenue_omega_agreements WHERE agreement_id = %s",
                (agreement.agreement_id,),
            ).fetchone()
            existing_hash = _first_value(existing, "agreement_hash")
            if existing_hash != agreement.agreement_hash:
                raise RevenueOmegaPersistenceConflict("agreement_id already exists with different content")
            return False

        return self.factory.run_with_retry(operation, governed_transition=True)

    def persist_placement(self, placement: PlacementEvent, *, currency: str) -> bool:
        created_at = datetime.now(timezone.utc)
        payload = asdict(placement)

        def operation(connection: Any) -> bool:
            row = connection.execute(
                """
                INSERT INTO revenue_omega_placements(
                    placement_id, agreement_id, employer_id, worker_reference,
                    billing_period, currency, eligible_compensation,
                    placement_hash, placement_json, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (placement_id) DO NOTHING
                RETURNING placement_hash
                """,
                (
                    placement.placement_id,
                    placement.agreement_id,
                    placement.employer_id,
                    placement.worker_reference,
                    placement.billing_period,
                    currency,
                    placement.eligible_compensation,
                    placement.event_hash,
                    self._json(payload),
                    created_at,
                ),
            ).fetchone()
            if row is not None:
                return True
            existing = connection.execute(
                "SELECT placement_hash FROM revenue_omega_placements WHERE placement_id = %s",
                (placement.placement_id,),
            ).fetchone()
            existing_hash = _first_value(existing, "placement_hash")
            if existing_hash != placement.event_hash:
                raise RevenueOmegaPersistenceConflict("placement_id already exists with different content")
            return False

        return self.factory.run_with_retry(operation, governed_transition=True)

    def reserve_billing(
        self,
        *,
        agreement: CommercialAgreement,
        placement: PlacementEvent,
        decision: BillingAuthorizationDecision,
    ) -> BillingReservationResult:
        if not decision.allowed:
            raise PermissionError("cannot reserve billing from a denied decision")
        if decision.agreement_id != agreement.agreement_id or decision.placement_id != placement.placement_id:
            raise RevenueOmegaPersistenceConflict("billing decision lineage mismatch")

        request_digest = canonical_sha256(
            {
                "agreement_hash": agreement.agreement_hash,
                "placement_hash": placement.event_hash,
                "billing_period": placement.billing_period,
                "decision_hash": decision.decision_hash,
                "billing_idempotency_key": decision.billing_idempotency_key,
            }
        )
        now = datetime.now(timezone.utc)
        reservation_json = self._json(
            {
                "agreement_id": agreement.agreement_id,
                "placement_id": placement.placement_id,
                "billing_period": placement.billing_period,
                "request_digest": request_digest,
                "decision_hash": decision.decision_hash,
                "billing_idempotency_key": decision.billing_idempotency_key,
            }
        )

        def operation(connection: Any) -> BillingReservationResult:
            inserted = connection.execute(
                """
                INSERT INTO revenue_omega_billing_reservations(
                    billing_idempotency_key, agreement_id, placement_id,
                    billing_period, request_digest, decision_hash,
                    reservation_state, reservation_json, reserved_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 'RESERVED', %s::jsonb, %s, %s)
                ON CONFLICT (billing_idempotency_key) DO NOTHING
                RETURNING billing_idempotency_key, request_digest, decision_hash, reservation_state
                """,
                (
                    decision.billing_idempotency_key,
                    agreement.agreement_id,
                    placement.placement_id,
                    placement.billing_period,
                    request_digest,
                    decision.decision_hash,
                    reservation_json,
                    now,
                    now,
                ),
            ).fetchone()
            if inserted is not None:
                return BillingReservationResult(
                    billing_idempotency_key=decision.billing_idempotency_key,
                    request_digest=request_digest,
                    decision_hash=decision.decision_hash,
                    state="RESERVED",
                    created=True,
                )

            existing = connection.execute(
                """
                SELECT request_digest, decision_hash, reservation_state
                FROM revenue_omega_billing_reservations
                WHERE billing_idempotency_key = %s
                """,
                (decision.billing_idempotency_key,),
            ).fetchone()
            existing_request = _value(existing, 0, "request_digest")
            existing_decision = _value(existing, 1, "decision_hash")
            existing_state = _value(existing, 2, "reservation_state")
            if existing_request != request_digest or existing_decision != decision.decision_hash:
                raise RevenueOmegaPersistenceConflict(
                    "billing idempotency key already reserved for different immutable lineage"
                )
            return BillingReservationResult(
                billing_idempotency_key=decision.billing_idempotency_key,
                request_digest=request_digest,
                decision_hash=decision.decision_hash,
                state=str(existing_state),
                created=False,
            )

        return self.factory.run_with_retry(operation, governed_transition=True)

    def mark_reconciliation_required(self, billing_idempotency_key: str, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("reconciliation reason is required")
        now = datetime.now(timezone.utc)

        def operation(connection: Any) -> None:
            result = connection.execute(
                """
                UPDATE revenue_omega_billing_reservations
                SET reservation_state = 'RECONCILIATION_REQUIRED',
                    reservation_json = reservation_json || %s::jsonb,
                    updated_at = %s
                WHERE billing_idempotency_key = %s
                RETURNING billing_idempotency_key
                """,
                (self._json({"reconciliation_reason": reason}), now, billing_idempotency_key),
            ).fetchone()
            if result is None:
                raise RevenueOmegaPersistenceConflict("billing reservation does not exist")

        self.factory.run_with_retry(operation, governed_transition=True)


def _first_value(row: Any, key: str) -> Any:
    return _value(row, 0, key)


def _value(row: Any, index: int, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[index]
    except (IndexError, KeyError, TypeError):
        return None
