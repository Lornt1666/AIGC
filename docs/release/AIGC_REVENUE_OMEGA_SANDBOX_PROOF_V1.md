# AIGC Revenue-Ω Sandbox Proof V1

Status: `NETWORK-FREE SYNTHETIC COMMERCIAL PROOF — NO REAL MONEY / NO EXTERNAL COMMERCIAL EFFECT`

## Purpose

Exercise the complete internal Revenue-Ω commercial state chain before any real email provider, payment processor, customer agreement, employment-agency activity, payroll system or production financial account is connected.

## Synthetic proof chain

```text
synthetic persisted jurisdiction decision
→ synthetic employer agreement
→ verified synthetic placement
→ synthetic compute usage
→ billing authorization
→ commission calculation
→ invoice candidate
→ invoice approval
→ deterministic invoice document
→ one-use sandbox email permit
→ simulated email delivery receipt
→ one-use sandbox payment permit
→ tokenized simulated payment session
→ HMAC-signed simulated settled webhook
→ verified payment receipt
→ PAID
→ SETTLED
→ issuance ledger
→ settlement ledger
→ proof receipt
```

## Hard non-production invariants

The proof receipt must state:

```text
status = SANDBOX_SETTLED
final_invoice_state = SETTLED
network_call_performed = false
real_money_moved = false
external_action_performed = false
```

No result that violates one of these fields can be promoted as the canonical sandbox proof.

## Sandbox permits

Every simulated consequential operation is still permit-bound. A permit binds:

```text
permit_id
action
principal
invoice_hash
currency
maximum_amount
maximum_calls = 1
environment = SANDBOX
validity window
decision hash
permit hash
```

The sandbox adapter rejects replay, wrong principal, wrong invoice, wrong currency, over-ceiling amount, wrong action, tampered permit, expired permit or non-sandbox environment.

The in-memory permit ledger exists only for deterministic testing. Production adapters require durable permit consumption before effect.

## Sandbox payment integrity

The payment simulation creates only an opaque token reference. It has no raw card number or payment credential.

The settlement event is HMAC-SHA256 signed over a canonical event envelope. Verification checks:

- provider/event type;
- invoice and session lineage;
- exact amount and currency;
- constant-time signature comparison.

Tampered webhook content is rejected.

## Settlement accounting

Revenue-Ω emits separate balanced entries for:

1. invoice issuance: Accounts Receivable debit / revenue-and-tax-clearing credit;
2. payment settlement: processor-clearing-or-cash debit / Accounts Receivable credit.

This keeps `INVOICED != COLLECTED` explicit even inside the sandbox.

## Execution

The pure proof runner is:

```text
python scripts/run_revenue_omega_sandbox_proof.py
```

It prints a machine-readable synthetic receipt and performs no network operation.

## Production boundary

Passing this proof does not authorize:

```text
employment_agency_activity
contract_acceptance
real invoice send
real payment request
real payment collection
refund execution
payroll deduction
tax filing
owner distribution
production activation
```

Those remain downstream separately governed actions.
