# AIGC Revenue-Ω V1

Status: `DETERMINISTIC COMMERCIAL KERNEL — NO EXTERNAL BILLING AUTHORITY`

## 1. Mission

Revenue-Ω converts evidence-backed economic value produced by AIGC into transparent, deterministic, auditable commercial artifacts while preserving the AIGC constitutional separation:

`Reasoning != Verification != Authority != Execution != Evidence`

The V1 kernel is deliberately pure. It can calculate and prepare billing artifacts, but it cannot send email, request payment, collect funds, mutate payroll, accept contracts, or make any other external commercial commitment.

## 2. Economic model

For ordinary employment placement, the default model is:

`verified worker compensation reference × contractual employer success-rate = employer-funded finder/success fee`

Compute, model, browser, API, cloud and other directly attributable resource costs can be recovered separately according to the signed agreement.

Canonical period economics:

```text
finder_fee = eligible_compensation × commission_rate
compute_cost = Σ(quantity × unit_cost)
compute_recovery = pricing_policy(compute_cost, markup)
subtotal = finder_fee + compute_recovery + authorized_services
invoice_total = subtotal + externally calculated applicable tax
```

Worker earnings may be a pricing reference; that fact alone is never authority to deduct from payroll or bill the worker. V1 rejects `WORKER` as a placement-payer mode.

## 3. Trust boundaries

### Commercial agreement

`CommercialAgreement` binds:

- employer identity;
- billing email;
- jurisdiction;
- commission rate;
- compensation basis;
- compute-pricing mode;
- compute markup;
- currency;
- agreement active state;
- jurisdiction approval state;
- terms version.

The agreement has a canonical SHA-256 digest.

### Placement event

`PlacementEvent` binds:

- placement;
- agreement;
- employer;
- pseudonymous worker reference;
- billing period;
- eligible compensation;
- compensation verification state;
- success-event verification state;
- attribution state;
- evidence references.

Only `ATTRIBUTED` may automatically enter billing authorization. Shared, disputed, unknown or not-attributed states fail closed.

### Compute usage

`ComputeUsageEvent` binds provider/resource usage to the exact placement and currency. Compute from another placement or currency is rejected rather than silently pooled.

## 4. Billing authorization

`RevenueOmegaEngine.authorize_billing()` requires, by default:

```text
policy payer == EMPLOYER
agreement/employer/placement lineage matches
agreement active
jurisdiction explicitly approved
commission rate within policy ceiling
compute markup within policy ceiling
compensation verified
success event verified
attribution == ATTRIBUTED
billing email verified
positive compensation base
```

Failure produces a deterministic deny decision with explicit reason codes.

No deny decision can be converted into an invoice candidate.

## 5. Idempotency

The billing idempotency key binds:

```text
agreement_id
placement_id
billing_period
placement_event_hash
agreement_hash
```

A material change to the agreement or placement therefore creates a new lineage instead of silently reusing an old authorization.

Production persistence must enforce this key with a unique constraint before any external effect.

## 6. Commission calculation

Supported compute modes:

- `ABSORBED_BY_PLATFORM`
- `PASS_THROUGH`
- `PASS_THROUGH_PLUS_MARGIN`
- `INCLUDED_IN_SUCCESS_FEE`

All money calculations use `Decimal` and two-decimal half-up quantization. Binary floating-point arithmetic is intentionally excluded from the commercial kernel.

## 7. Invoice lineage

`InvoiceCandidate` binds:

- agreement;
- placement;
- employer;
- billing period;
- finder fee;
- compute recovery;
- authorized service charges;
- tax supplied by a separately governed tax component;
- total;
- billing idempotency key;
- evidence;
- commission calculation hash;
- billing authorization decision hash.

V1 creates only `DRAFT` invoice candidates.

`DRAFT != ISSUED`

## 8. Email boundary

`render_invoice_email()` prepares an `InvoiceEmailDraft` with:

`external_action_performed = false`

Actual delivery must occur through an `EmailBillingPort` implementation that validates a separately issued external-action permit and persists a provider receipt.

Generation of an email body is not evidence that email was sent.

## 9. Payment boundary

`PaymentPort` defines a narrow provider interface. It receives an approved invoice and a separate permit. Raw payment-card material is not part of the interface.

Required production rules:

- provider tokenization;
- webhook signature verification;
- durable event deduplication;
- payment-state reconciliation;
- no blind retry for indeterminate external results;
- receipt binding to invoice and provider transaction;
- distinction between invoiced, receivable, collected, refunded and chargeback states.

## 10. Tax boundary

`TaxPort` isolates jurisdiction-specific tax determination from commission calculation. No global hard-coded GST/HST/PST rate belongs in the kernel.

Production tax inputs must include seller jurisdiction, buyer jurisdiction, service classification, amount, currency and effective date.

## 11. Accounting boundary

The V1 kernel can construct a balanced invoice transaction:

```text
DEBIT  Accounts Receivable
CREDIT AIGC Revenue and Tax Clearing
```

Production accounting should expand this into separate revenue, tax-liability, processor-clearing, refund, chargeback, reserve and owner-distribution accounts.

`business revenue != owner withdrawal`

## 12. Owner/founder economics

Revenue-Ω preserves a traceable economic path from successful AIGC work to platform sustainability:

```text
verified success
→ employer-funded fee
→ compute/runtime recovery
→ collected platform cash
→ operating costs/reserves/taxes
→ lawful founder compensation or owner distribution
→ reinvestment
```

The founder allocation happens only after actual collection and accounting classification. A worker receiving compensation does not by itself establish collected AIGC revenue.

## 13. Security invariants

- no raw payment credentials;
- no secrets in invoice artifacts;
- no worker payroll deduction authority;
- no self-authorization;
- no invoice send from the pure kernel;
- no payment collection from the pure kernel;
- no automatic retry of non-idempotent external effects;
- immutable hashes for agreements, placement events, decisions, calculations and invoices;
- pseudonymous worker references where identity is not operationally necessary;
- jurisdiction approval required before billing authorization.

## 14. Event model

`schemas/revenue_omega/revenue_omega_event.schema.json` provides the V1 append-only commercial event envelope.

Production persistence should support events including:

```text
AGREEMENT_REGISTERED
PLACEMENT_VERIFIED
COMPUTE_USAGE_RECORDED
BILLING_AUTHORIZED / BILLING_DENIED
COMMISSION_CALCULATED
INVOICE_CANDIDATE_CREATED
INVOICE_APPROVED
INVOICE_ISSUED
EMAIL_DELIVERY_RECORDED
PAYMENT_REQUESTED
PAYMENT_SETTLED / PAYMENT_FAILED
REFUND_RECORDED
DISPUTE_OPENED / DISPUTE_RESOLVED
LEDGER_POSTED
```

## 15. Adversarial acceptance suite

The initial test set requires deterministic rejection of:

- unapproved jurisdiction;
- unverified compensation;
- unverified success event;
- disputed/shared/unknown attribution;
- unverified billing email;
- commission above policy ceiling;
- compute usage from another placement;
- invoice creation from a denied billing decision;
- worker placement-payer configuration.

It also verifies:

- exact percentage calculation;
- compute recovery with markup;
- stable idempotency/decision hashes;
- invoice totals;
- email draft is non-executing;
- double-entry balance.

## 16. Production procurement sequence

V1 implementation should advance through these separately authorized increments:

```text
R1 deterministic kernel + schemas + tests
R2 durable PostgreSQL event store and unique idempotency constraints
R3 signed commercial-agreement registry + jurisdiction decision repository
R4 metering ingestion from provider/cloud receipts
R5 invoice lifecycle and PDF rendering
R6 governed Gmail/transactional-email adapter
R7 payment processor customer/invoice/session adapter
R8 signed webhook reconciliation
R9 refunds/disputes/chargebacks
R10 tax-provider integration and accounting export
R11 revenue analytics + founder/business allocation dashboard
R12 controlled sandbox transaction proof
R13 independently reviewed production activation
```

Every increment requires exact-head CI and governed review. External commercial execution remains false until separately authorized.

## 17. V1 completion statement

This architecture establishes the deterministic commercial trust boundary and external-effect ports. It does not claim a live customer agreement, invoice transmission, payment, payroll integration, tax filing, production payment processor, or collected revenue.
