# AIGC APEX Completion Ledger V1

Status: `DETERMINISTIC COMPLETION CONTROL — NO EXTERNAL AUTHORITY`

## Purpose

Convert the APEX-Ω∞ completion doctrine into machine-enforced scoring so planning, implementation, stale CI, draft artifacts, or missing receipts cannot be promoted into final gate credit.

## Binary final gate law

For G2 through G9:

```text
VERIFIED_COMPLETE + all required current evidence = 10/10
anything else = 0/10 final credit
```

A separate `internal_progress` field may represent work-in-progress maturity without changing the final gate score.

## Evidence states

```text
PRESENT
MISSING
STALE
INVALID
```

A required evidence type receives no credit merely because some other artifact exists.

Examples:

```text
PLAN != DEPLOYMENT_RECEIPT
CODE != LIVE_MODEL_RECEIPT
AUTHORIZATION != EXECUTION_RECEIPT
INVOICE != PAYMENT_RECEIPT
DRAFT_SUBMISSION != SUBMISSION_RECEIPT
```

## Exact-head CI regression

G4 carries additional invariants:

```text
candidate_revision == current integration head
EXACT_HEAD_CI evidence exists
EXACT_HEAD_CI.exact_revision == candidate_revision
```

When the integration head moves, the prior CI receipt becomes insufficient for the new candidate and final G4 credit drops to zero until fresh evidence exists.

## Full APEX completion

`APEX VERIFIED COMPLETE` additionally requires:

```text
strict material facts = 100
24/24 authorization entries terminally completed
Revenue-Ω commercial readiness = 100
Revenue-Ω operational readiness = 100
G2..G9 each = 10/10
critical blockers = zero
```

The evaluator therefore cannot turn a technically passing CI run into whole-program completion.

## Current relationship to live work

This control plane is designed to consume evidence produced by independent workstreams including:

- PR #181 Nexus V1 exact-head CI and future cloud/runtime receipts;
- Revenue-Ω deterministic, jurisdiction, persistence, invoice/payment and sandbox receipts;
- Devpost requirement/claim evidence;
- judge access evidence;
- final merge/submission receipts.

It grants none of those actions.

## Authority boundary

```text
repository_status_evaluation=true
external_action=false
cloud_mutation=false
financial_action=false
merge=false
submission=false
production_activation=false
```
