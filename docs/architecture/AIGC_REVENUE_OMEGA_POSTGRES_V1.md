# AIGC Revenue-Ω PostgreSQL V1

Status: `IMPLEMENTED INTERNAL PERSISTENCE SLICE — NO DATABASE MIGRATION OR EXTERNAL FINANCIAL ACTION EXECUTED`

## Purpose

Move Revenue-Ω financial intent from process memory into transactional, restart-safe PostgreSQL state before any consequential invoice/email/payment adapter is activated.

## Core invariant

```text
NO DURABLE BILLING RESERVATION
→ NO EXTERNAL BILLING EFFECT
```

A successful pure billing decision is necessary but not sufficient. The exact billing idempotency key must be atomically reserved in durable storage first.

## Schema

The isolated migration is:

`migrations/revenue_omega/postgresql/0001_revenue_omega_v1.sql`

It is deliberately outside the canonical production-persistence migration sequence while Revenue-Ω remains a separately reviewed stack. It assumes the canonical baseline has already supplied `aigc_reject_append_only_mutation()` before the Revenue-Ω migration is actually applied.

The migration defines:

```text
revenue_omega_agreements
revenue_omega_jurisdiction_decisions
revenue_omega_placements
revenue_omega_compute_usage
revenue_omega_billing_reservations
revenue_omega_commission_calculations
revenue_omega_invoice_events
revenue_omega_payment_events
revenue_omega_ledger_transactions
revenue_omega_audit_events
```

Money uses PostgreSQL `NUMERIC`, never floating-point.

## Exactly-once billing intent

`PostgresRevenueOmegaRepository.reserve_billing()` runs through the repository's canonical `PostgresConnectionFactory` with a governed transaction.

The primary key is:

`billing_idempotency_key`

The reservation additionally binds:

```text
agreement_id
placement_id
billing_period
request_digest
decision_hash
reservation_state
```

First exact request:

```text
INSERT → RESERVED → created=true
```

Exact replay:

```text
ON CONFLICT DO NOTHING
→ read existing immutable lineage
→ same request/decision
→ created=false
```

Conflicting replay:

```text
same idempotency key
+ different request or decision hash
→ FAIL CLOSED
```

## Indeterminate outcomes

An external adapter that returns an indeterminate result must not simply re-run the action.

The reservation may transition to:

`RECONCILIATION_REQUIRED`

with an explicit reason. Reconciliation must inspect provider evidence before another consequential attempt is authorized.

## Append-only evidence

Jurisdiction decisions, compute usage, commission calculations, invoice events, payment events, ledger transactions and Revenue-Ω audit events receive append-only database triggers.

Mutable workflow state is intentionally limited to operational records such as the billing reservation state and active agreement revisions.

## Payment-event deduplication

Provider payment events use:

```text
UNIQUE(provider, provider_event_id)
```

so a duplicated signed webhook cannot silently mint a second canonical event.

## Ledger integrity

The database requires:

```text
debit_total = credit_total
```

in addition to application-level balanced ledger validation.

## Authority boundary

This increment defines schema and repository code only.

```text
database_migration_executed=false
cloud_sql_mutated=false
invoice_send=false
payment_request=false
payment_collection=false
refund=false
owner_distribution=false
tax_filing=false
production_activation=false
```

A future staging migration requires an exact migration receipt and separately governed runtime authority.
