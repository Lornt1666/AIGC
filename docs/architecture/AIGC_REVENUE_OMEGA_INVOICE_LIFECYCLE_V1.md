# AIGC Revenue-Ω Invoice Lifecycle V1

Status: `DETERMINISTIC INVOICE CONTROL — NO EMAIL/PAYMENT/REFUND EFFECT EXECUTED`

## Purpose

Prevent Revenue-Ω from confusing a calculation, draft, provider delivery, receivable, payment, settlement, dispute, refund, or write-off with any other state.

## Canonical lifecycle

```text
DRAFT
→ APPROVED
→ ISSUED
→ DELIVERED
→ OPEN
→ PARTIALLY_PAID
→ PAID
→ SETTLED
```

Exceptional branches:

```text
OVERDUE
DISPUTED
VOID
CANCELLED
PARTIALLY_REFUNDED
REFUNDED
UNCOLLECTIBLE
```

No arbitrary transition is accepted.

## Receipt gates

- `APPROVED` requires an approval-decision hash.
- `DELIVERED` requires a provider delivery receipt.
- `PARTIALLY_PAID`, `PAID`, and `SETTLED` require a payment receipt.
- `PARTIALLY_REFUNDED` and `REFUNDED` require a refund receipt.
- `DISPUTED` requires a dispute record.
- `UNCOLLECTIBLE` requires an accountable write-off decision.

The state machine validates receipts that already exist. It performs no consequential provider action.

## Monetary invariants

```text
paid_amount >= 0
refunded_amount >= 0
paid_amount <= total
refunded_amount <= paid_amount
paid_amount never decreases
refunded_amount never decreases
PAID/SETTLED => paid_amount == total
REFUNDED => refunded_amount == paid_amount
```

## Deterministic documents

`InvoiceDocumentRenderer` creates escaped HTML from an `InvoiceCandidate`. It recomputes the line-item total and rejects a mismatch before rendering. The output is SHA-256 bound and has `external_action_performed=false`.

The rendered document expressly distinguishes the employer/customer obligation from worker payroll and does not authorize a worker wage deduction.

## Security

Untrusted textual fields are HTML escaped. Secrets, raw card data, provider credentials, OAuth material and payment tokens are outside the renderer contract.

## Persistence expectation

A production adapter should persist each accepted state transition as an append-only `revenue_omega_invoice_events` row, using optimistic current-revision checking so two actors cannot independently advance the same prior revision.

## Authority boundary

```text
invoice_calculation=true
invoice_rendering=true
invoice_state_validation=true
invoice_send=false
payment_request=false
payment_collection=false
refund_execution=false
writeoff_execution=false
payroll_deduction=false
tax_filing=false
production_activation=false
```
