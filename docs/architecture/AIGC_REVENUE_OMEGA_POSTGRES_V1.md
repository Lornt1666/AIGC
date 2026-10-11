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

## Converged authority lineage

This integrated candidate combines:

```text
persisted jurisdiction decision
→ commercial agreement binding
→ verified placement
→ deterministic billing authorization
→ durable exactly-once billing reservation
→ invoice candidate
```

The caller cannot self-certify jurisdiction approval. The billing decision must already be bound to the persisted jurisdiction decision before its idempotency key can be durably reserved.

## Schema

The isolated migration is:

`migrations/revenue_omega/postgresql/0001_revenue_omega_v1.sql`

It remains outside the canonical production-persistence migration sequence while Revenue-Ω is separately reviewed. It assumes the canonical baseline has already supplied `aigc_reject_append_only_mutation()` before the Revenue-Ω migration is actually applied.

The migration defines agreements, jurisdiction decisions, placements, compute usage, billing reservations, commission calculations, invoice events, payment events, ledger transactions and audit events. Money uses PostgreSQL `NUMERIC`, never floating-point.

## Exactly-once billing intent

`PostgresRevenueOmegaRepository.reserve_billing()` runs through the canonical `PostgresConnectionFactory` with a governed transaction.

The primary key is `billing_idempotency_key`, additionally binding agreement, placement, billing period, request digest, decision hash and reservation state.

Exact first request creates `RESERVED`. Exact replay returns the durable reservation with `created=false`. A conflicting replay under the same key fails closed.

## Indeterminate outcomes

External adapters that return an indeterminate result must not simply retry. The reservation transitions to `RECONCILIATION_REQUIRED` with a reason; provider evidence must be reconciled before another consequential attempt.

## Append-only evidence

Jurisdiction decisions, compute usage, commission calculations, invoice events, payment events, ledger transactions and Revenue-Ω audit events are append-only in the database. Provider payment events additionally use `UNIQUE(provider, provider_event_id)` to prevent duplicated webhook events from silently minting duplicate canonical events.

## Ledger integrity

The database requires `debit_total = credit_total` in addition to application-level balanced-ledger validation.

## Authority boundary

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
