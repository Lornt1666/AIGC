# AIGC XPRIZE Final Claim / Evidence Matrix

Status: `LIVE CLAIM AUDIT — FINAL COPY NOT YET AUTHORIZED`

Machine source:

```text
config/xprize_claim_evidence_matrix.json
scripts/validate_xprize_claim_evidence_matrix.py
```

## Claim classes

```text
PROVEN
DEMONSTRATED
IMPLEMENTED_NOT_RUNTIME_PROVEN
DESIGNED
PLANNED
EXPERIMENTAL
```

`PROVEN` and `DEMONSTRATED` require `VERIFIED` evidence. Runtime-dependent strong claims additionally require an exact runtime receipt; business-dependent strong claims require a business/payment/customer receipt.

## Current material claims

| ID | Topic | Current class | Evidence | Allowed current statement |
|---|---|---|---|---|
| 001 | Nexus architecture | PROVEN | PR #181 / CI #2758 | AIGC implements and exact-head CI validates the governed Nexus V1 architecture. |
| 002 | Gemini implementation | PROVEN | PR #181 / CI #2758 | The repository implements a governed Vertex Gemini provider path and bounded canary procedure. |
| 003 | Live Gemini call | PLANNED | MISSING | A live permit-bound Gemini proof remains a release/submission gate. |
| 004 | Montréal GCP deployment | PLANNED | MISSING | Montréal staging is implemented as design/procedure; empirical deployment remains pending. |
| 005 | Judge access | PLANNED | MISSING | Judge access is prepared as a gated procedure and remains unverified. |
| 006 | Revenue-Ω simulation/finance | PROVEN | PR #208 / CI #2899 | Deterministic commercial, sandbox-settlement and finance logic is exact-head CI validated; no real money is moved by that proof. |
| 007 | Real payment | PLANNED | MISSING | Real payment collection is not currently evidenced. |
| 008 | Real third-party user | PLANNED | MISSING | A real third-party pilot remains required; synthetic/internal tests are excluded. |
| 009 | Competition-specific chronology | DEMONSTRATED | VERIFIED Git history | Representative dedicated Gemini paths were introduced on the post-May-19 PR #145 branch. |
| 010 | Final eligibility | PLANNED | PARTIAL | Eligibility remains fail-closed until all tracked items resolve. |
| 011 | Canada residence | PROVEN | authenticated entrant evidence | Authenticated account records support Canada as the entrant country. |
| 012 | Category | DESIGNED | PARTIAL | Entrepreneurship & Job Creation is the evidence-based recommended category. |
| 013 | P&L evidence model | DEMONSTRATED | working XPRIZE-aligned workbook | A working cash-basis P&L evidence model exists; final recognition remains unresolved. |
| 014 | Final financial figures | PLANNED | MISSING | Final reported revenue/COGS/marketing/expenses remain unresolved. |
| 015 | ZIP builder | IMPLEMENTED_NOT_RUNTIME_PROVEN | current #209 code/tests | A deterministic fail-closed ZIP builder is implemented on the current unadmitted candidate. |
| 016 | Final ZIP | PLANNED | MISSING | Final evidence ZIP is not built/uploaded. |
| 017 | #209 exact-head admission | PLANNED | MISSING | #209 is unadmitted because GitHub-hosted Actions capacity is exhausted. |

## Forbidden promotions until receipts exist

Do not state or imply:

```text
AIGC is deployed in Google Cloud
AIGC has completed the required live Gemini API call
AIGC has real customers/users
AIGC has collected customer revenue
judge access is verified
final P&L is complete
final ZIP is ready/uploaded
PR #209 has passed exact-head CI
AIGC is fully eligible
Sponsor has approved eligibility
Nexus V1 is zero-defect
```

unless the corresponding exact evidence state changes and the machine matrix is updated/revalidated.

## Runtime promotion law

For a runtime-dependent claim:

```text
PROVEN | DEMONSTRATED
requires
runtime_receipt_ref != null
AND evidence_state = VERIFIED
```

Examples:

```text
live Gemini
Cloud deployment
real third-party pilot runtime
```

## Business promotion law

For a business-dependent strong claim:

```text
PROVEN | DEMONSTRATED
requires
business_receipt_ref != null
AND evidence_state = VERIFIED
```

Examples:

```text
collected revenue
paying user
arms-length customer transaction
```

## Current final-copy disposition

The matrix itself is usable as a truth-control artifact, but final Devpost copy is not ready because multiple material runtime/business/eligibility claims remain unresolved.

```text
public Devpost update performed = false
Devpost submission performed = false
```
