# AIGC Revenue-Ω V1 Procurement Runbook

Status: `IMPLEMENTATION PROCUREMENT — EXTERNAL COMMERCIAL ACTIONS LOCKED`

## Objective

Advance Revenue-Ω from policy/design maturity into evidence-backed operational capability without silently acquiring contract, invoicing, payment, payroll, or tax authority.

The procurement sequence is:

```text
exact-head deterministic kernel
→ governed review
→ durable commercial persistence
→ agreement + jurisdiction evidence
→ compute receipt ingestion
→ invoice lifecycle
→ email adapter
→ payment adapter
→ webhook reconciliation
→ accounting/tax integration
→ sandbox proof
→ separate production activation
```

## R1 — Deterministic kernel

This branch supplies:

- immutable commercial contracts;
- Decimal money arithmetic;
- employer-funded placement policy;
- explicit jurisdiction approval gate;
- verified compensation/success/attribution gates;
- deterministic percentage finder-fee calculation;
- compute cost and recovery calculation;
- billing idempotency;
- invoice candidates;
- non-sending invoice email drafts;
- external email/payment/tax ports;
- balanced ledger transaction generation;
- event schema;
- adversarial tests.

Authority remains:

```text
contract_acceptance=false
invoice_send=false
payment_request=false
payment_collection=false
refund=false
payroll_deduction=false
tax_filing=false
production_activation=false
```

## R2 — Exact-head CI procurement

After opening the draft PR, require a pull-request-triggered AIGC CI receipt for the exact branch head.

Admission requires:

```text
requested_sha == observed_checkout_sha
all repository tests pass
Revenue-Ω adversarial tests pass
redaction/secret scans pass
retained exact-head artifact exists
```

Any material repair invalidates the prior receipt.

## R3 — Commercial/jurisdiction register

Before any invoice can be approved, persist an accountable jurisdiction decision for each enabled commercial model.

Minimum record:

```text
decision_id
jurisdiction
service_type
payer_model
allowed
conditions[]
reviewer
reviewed_at
expires_at
source_refs[]
decision_hash
```

Do not infer legal approval from configuration. `jurisdiction_approved=true` must originate from an accountable review record.

## R4 — Employer agreement procurement

Create a versioned agreement template containing at least:

```text
legal parties
service description
success/earning event
placement attribution rule
eligible compensation definition
finder/success percentage
compute pricing policy
minimum/maximum fee if any
currency
invoice cadence
payment terms
tax treatment
guarantee/refund terms
dispute terms
privacy/data handling
term/termination
signatures
```

AIGC must not create a billing entitlement before the agreement is active.

## R5 — Durable persistence

Implement PostgreSQL repositories for:

```text
commercial_agreements
jurisdiction_decisions
placement_events
compute_usage_events
billing_decisions
commission_calculations
invoice_candidates
invoice_events
payment_events
refunds
disputes
ledger_transactions
billing_audit_events
```

Required database controls:

- unique billing idempotency key;
- immutable event IDs;
- optimistic revision checks;
- foreign-key lineage;
- exact currency fields;
- `NUMERIC`, never float, for money;
- append-only external receipts;
- transactionally persisted reservation before consequential adapter effect.

## R6 — Compute-meter ingestion

Adapters may ingest evidence from model/cloud/tool providers.

Every usage record must identify:

```text
provider
resource_type
quantity
unit_cost
currency
task_id
placement_id
provider_receipt/evidence reference
```

Observed cost and AIGC markup must remain separate fields.

## R7 — Invoice lifecycle

Implement deterministic states:

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

Exceptional states:

```text
VOID
DISPUTED
OVERDUE
REFUNDED
PARTIALLY_REFUNDED
UNCOLLECTIBLE
```

State transitions must be persisted and validated.

## R8 — Email delivery

Connect `EmailBillingPort` only after an exact external-action permit exists.

Permit must bind:

```text
invoice_hash
recipient
provider
operation=SEND_INVOICE
maximum_calls=1
expiry
decision_hash
```

Required receipt:

```text
provider_message_id
invoice_candidate_id
provider
timestamp
accepted/delivery status
receipt_hash
```

A failed or unknown provider result is reconciled before retry.

## R9 — Payment processor

Use a tokenized processor integration. Do not store raw card details.

Minimum operations:

```text
create_customer
create_invoice_or_checkout_session
retrieve_transaction
verify_payment
issue_refund
```

Every operation requires a bounded permit.

## R10 — Webhook reconciliation

Webhook processing requires:

- provider signature verification;
- event ID deduplication;
- durable raw-envelope hash;
- exact invoice/customer binding;
- state-machine validation;
- transactionally persisted result;
- no trust in caller-supplied payment status.

## R11 — Accounting and owner economics

Separate:

```text
gross platform revenue
compute/provider costs
processor fees
refunds/chargebacks
tax liabilities
operating reserve
business reinvestment
founder compensation/owner distributions
```

Never represent invoiced value as collected cash, and never represent business revenue as a personal withdrawal without the appropriate accounting event.

## R12 — Sandbox proof

Before production, execute one controlled sandbox sequence:

```text
synthetic employer agreement
→ synthetic verified placement
→ synthetic compute receipt
→ billing authorization
→ commission calculation
→ approved sandbox invoice
→ sandbox email/provider delivery receipt
→ sandbox payment
→ signed webhook
→ settlement
→ balanced ledger
→ refund/dispute regression
```

Capture exact code SHA, provider sandbox identifiers, timestamps and redacted receipts.

## R13 — Production activation

Production activation is a separate decision. Require:

```text
exact-head CI PASS
security review PASS
commercial/jurisdiction register current
privacy review PASS
payment-provider production account ready
tax/accounting review complete
secrets provisioned through approved manager
rollback/incident procedures tested
sandbox proof PASS
explicit owner authorization
```

Only then may consequential adapters be activated.

## Current next action

Open a draft PR for R1 and obtain fresh exact-head hosted CI. Keep all external commercial authority false while R1 is reviewed.
