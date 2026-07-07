# AIGC Procurement Procedure

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Status

Procedure instantiated. No purchase, procurement, payment, vendor account change, contract acceptance, credential use, or external submission is authorized by this document.

## Purpose

This procedure defines how AIGC may prepare a procurement decision for human review without bypassing approval, budget, legal, security, or audit controls.

## Prime Boundary

AIGC may coordinate procurement evidence. AIGC may not spend money, accept terms, create paid accounts, upgrade services, submit orders, or modify vendor accounts without a separate explicit procurement permit and human execution approval.

## Procurement Levels

- `P0_RESEARCH_ONLY`: internal market research, notes, and option comparison.
- `P1_OWNER_SANDBOX`: owner-controlled trial or free-tier evaluation with no payment method and no client data.
- `P2_LOW_COST_TOOL`: bounded paid tool or service with preapproved budget, security review, and cancellation path.
- `P3_BUSINESS_CRITICAL_VENDOR`: vendor or service that touches operations, customer data, infrastructure, finance, or compliance scope.
- `P4_CLIENT_OR_PUBLIC_COMMITMENT`: purchase or contract that affects a client, public representation, delivery promise, or external obligation.
- `P5_BLOCKED`: payment, procurement, contract, account-changing, or regulated action without proper authority.

## Required Records

Every procurement candidate must produce:

1. Procurement request ID.
2. Work order ID.
3. Business purpose.
4. Vendor or product name.
5. Procurement level.
6. Expected cost and billing period.
7. Budget owner.
8. Data classification.
9. Security and privacy notes.
10. Terms/license review summary.
11. Alternatives considered.
12. Reversibility/cancellation path.
13. Risk summary.
14. Approval status.
15. Audit event ID.

## Required Gates

Before any purchase or paid commitment, all gates must pass:

- **Scope gate**: need is tied to an approved work order.
- **Budget gate**: cost, renewal period, and owner are explicit.
- **Security gate**: credential, data, and access exposure are reviewed.
- **Privacy gate**: no client or personal data is introduced without approved handling.
- **Legal/terms gate**: license, acceptable use, renewal, cancellation, and liability are reviewed.
- **Operational gate**: rollback, cancellation, and owner support model are clear.
- **Approval gate**: exact procurement approval phrase is typed by the human approver.
- **Audit gate**: immutable local evidence record is written before and after action.
- **Kill switch gate**: emergency stop blocks execution.

## Procedure

1. **Open procurement request**
   Record the work order, need, expected outcome, and candidate vendor/product.

2. **Classify procurement level**
   Assign `P0` through `P5`. Default to the higher-risk level when uncertain.

3. **Collect evidence**
   Gather pricing, terms, data handling notes, support commitments, and alternatives. Do not log secrets or payment information.

4. **Prepare recommendation**
   Summarize value, risks, cost, reversibility, and why the option is better than doing nothing.

5. **Create procurement permit draft**
   Include exact target, exact spend ceiling, exact billing period, exact payload/action, max attempts, expiration, and rollback/cancellation path.

6. **Human review**
   The human approver must type the exact procurement approval phrase. A checkbox, implied approval, stored phrase, or prefilled approval is not enough.

7. **Execution boundary**
   AIGC may not execute the purchase. A separate approved executor procedure is required before any real procurement action.

8. **Result audit**
   After any separately approved action, record the result, receipt/reference summary, amount, status, and next cancellation/review date without storing payment data.

## Explicit Non-Authority

The following are not authorized by this procedure:

- purchase
- procurement execution
- payment
- subscription upgrade
- account modification
- paid trial activation
- vendor contract acceptance
- upload of client data
- credential entry
- deployment
- public release
- client delivery

## Owner Identity Note

The labels Justice Gray Maciocha, Satoshi, and Lornt may identify the human owner/operator context in local approval records. Their presence in this document is not purchase authorization.

## First Safe Procurement Action

The first safe procurement workflow is `P0_RESEARCH_ONLY`: produce a comparison table for candidate tools or vendors with no account creation, no payment method, no external contact, and no credential use.

## Next Safe Command

Run local validation and tests after any implementation change. Do not execute procurement.
