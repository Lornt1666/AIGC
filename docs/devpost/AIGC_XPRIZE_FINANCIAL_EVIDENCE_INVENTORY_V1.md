# AIGC XPRIZE Financial Evidence Inventory V1

Status: `SOURCE INVENTORY — NO PROJECT ATTRIBUTION OR ACCOUNTING RECOGNITION IMPLIED`

## Purpose

Track real hackathon-period financial source records without converting cash movements, prepaid balances, unrelated infrastructure, mixed-use subscriptions, or unsupported assumptions into AIGC revenue/expense claims.

## Evidence rules

```text
cash payment != AIGC expense
prepaid API funding != consumed COGS
billing-account payment != project attribution
subscription confirmation != project allocation
invoice != payment
payment != revenue attribution
included/free quota != cash expense
```

A record may enter the AIGC XPRIZE P&L only after both:

```text
AIGC business-purpose attribution = VERIFIED
accounting recognition for the competition period = REVIEWED
```

## Candidate source records

### FIN-SRC-001 — OpenAI API credit funding

```text
source = authenticated Gmail receipt
provider = OpenAI
receipt date = 2026-06-07
cash amount = CA$52.50
organization = RegenExcalibur
organization id = org-4DJT0yc5SbOEmFTbRs5LzvNp
payment instrument = card ending 6158
source state = VERIFIED_CASH_FUNDING
AIGC attribution = UNVERIFIED
accounting classification = PREPAID_API_CREDIT_CANDIDATE
AIGC expense recognized = false
AIGC COGS recognized = false
```

The source receipt proves that CA$52.50 was charged to fund the RegenExcalibur OpenAI API credit balance. It does not prove how much, if any, was consumed by AIGC during the hackathon period. Before recognition, obtain provider usage/billing history and bind actual AIGC usage or a reviewed allocation methodology.

### FIN-SRC-002 — Google Cloud Platform & APIs payment

```text
source = authenticated Gmail receipt
provider = Google Cloud Platform & APIs
receipt date = 2026-08-01
cash amount = CA$7.64
payment reference = CLOUD 5WRW2N
billing account = 0156E0-2BDD06-7561F1
payments profile id = 3604-7820-9130
payment instrument = card ending 6158
source state = VERIFIED_CASH_PAYMENT
AIGC project attribution = UNVERIFIED
accounting classification = CLOUD_BILLING_SETTLEMENT_CANDIDATE
AIGC expense recognized = false
AIGC COGS recognized = false
```

The payment proves a CA$7.64 settlement against the billing account. It does not establish which project/service incurred the underlying cost or which calendar period the charge belongs to. Before recognition, obtain Cloud Billing invoices/cost-table statements and project/service lineage.

### FIN-SRC-003 — GitHub Actions included usage

```text
source = authenticated GitHub billing notice
period = current August 2026 billing cycle
included minutes = 2,000
used minutes = 2,000
included-cost statement = no extra cost
cash expense evidenced = 0 for included quota itself
future overage = NOT AUTHORIZED / NOT EVIDENCED
```

The included quota is operational resource consumption but is not itself a cash expense. If Actions overage is later authorized and billed, recognize only from actual billing evidence.

### FIN-SRC-004 — Replit Core subscription confirmation

```text
source = authenticated Apple subscription confirmation
provider = Replit, Inc. via Apple Canada
purchase date = 2026-08-04
subscription = Replit Core
stated renewal price = $25.00/month
source state = PURCHASE_CONFIRMED / SEPARATE TAX RECEIPT_NOT_FOUND
AIGC attribution = POTENTIALLY_ATTRIBUTABLE / UNVERIFIED
accounting classification = SOFTWARE_SUBSCRIPTION_CANDIDATE
AIGC expense recognized = false
AIGC COGS recognized = false
```

Replit is a plausible development tool for AIGC, but the source currently proves only the subscription purchase/renewal price. Before recognition, require the actual charged receipt/payment evidence and an operator/business-purpose allocation to AIGC for the competition period.

### FIN-SRC-005 — LinkedIn Premium Career receipt

```text
source = authenticated Apple receipt
provider = LinkedIn via Apple Canada
receipt date = 2026-07-15
subtotal = CA$49.99
GST/HST = CA$2.50
cash total = CA$52.49
order id = MVL9HD9TT6
source state = VERIFIED_CASH_PURCHASE
AIGC attribution = UNVERIFIED / LIKELY_MIXED_OR_PERSONAL
accounting classification = DO_NOT_RECOGNIZE_WITHOUT_AIGC_PURPOSE_EVIDENCE
AIGC expense recognized = false
AIGC marketing/CAC recognized = false
```

A LinkedIn career subscription must not be relabeled as AIGC marketing/customer-acquisition spend merely because AIGC has employment-oriented use cases. Recognition requires evidence that this exact subscription was incurred for AIGC business/customer acquisition rather than the account holder's personal job search or another purpose.

### FIN-SRC-006 — Vercel Pro + v0 Premium recurring subscriptions

Authenticated Vercel/Stripe receipts and invoices establish two distinct recurring subscriptions in USD during the hackathon window.

#### Pro subscription

```text
2026-06-06  receipt 2381-7630  invoice 81MS8AUN-0001  period Jun 6-Jul 5   USD 21.00 paid
2026-07-06  receipt 2336-1598  invoice 81MS8AUN-0004  period Jul 6-Aug 5   USD 21.00 paid
2026-08-06  receipt 2001-3624  invoice 81MS8AUN-0005  period Aug 6-Sep 5   USD 21.00 paid
```

Each invoice contains:

```text
Pro base charge = USD 20.00
Canada GST/TPS 5% = USD 1.00
cash total = USD 21.00
```

The July/August Pro receipts also list two `Observability Plus` line items at USD 0.00 each.

Pro cash paid in the observed hackathon window:

```text
USD 63.00
```

#### v0 Premium subscription

```text
2026-06-16  receipt 2364-9356  invoice WKX6OYGT-0003  period Jun 16-Jul 15  USD 21.00 paid
2026-07-16  receipt 2863-9099  invoice WKX6OYGT-0004  period Jul 16-Aug 15  USD 21.00 paid
```

Each v0 Premium invoice contains:

```text
v0 Premium base charge = USD 20.00
Canada GST/TPS 5% = USD 1.00
cash total = USD 21.00
```

v0 Premium cash paid in the observed hackathon window:

```text
USD 42.00
```

Combined Vercel/v0 cash paid:

```text
USD 105.00
```

Current attribution state:

```text
source state = VERIFIED_CASH_PURCHASES
billing identity = justlornt95-4786 / justlornt95-4786's projects
AIGC repository reference to Vercel = NONE FOUND
AIGC-named Vercel project/account evidence = NONE FOUND
AIGC attribution = POTENTIALLY_ATTRIBUTABLE / UNVERIFIED
accounting classification = HOSTING_AND_AI_DEVELOPMENT_SUBSCRIPTION_CANDIDATE
AIGC expense recognized = false
AIGC COGS recognized = false
```

Vercel Pro and v0 Premium are plausible software-development/hosting inputs, but their invoices are account-level and do not identify AIGC. The AIGC repository currently contains no `vercel` reference, and authenticated Vercel email search produced no AIGC/Facade/RegenExcalibur project binding. Do not recognize any portion of the USD 105.00 until an operator/business-purpose review or project/account evidence establishes the applicable AIGC allocation.

## Required follow-up evidence

Before final P&L:

```text
OpenAI provider billing/usage history for the hackathon period
Google Cloud monthly invoices or zero-dollar/cost-table statements
Google Cloud project/service cost attribution
GitHub Actions billed-overage statement if any
Replit charged receipt/payment evidence + AIGC-purpose allocation
Vercel/v0 project-purpose evidence or reviewed allocation
other project-specific receipts/subscriptions/domains/services
complete revenue/bank/payment-provider evidence
marketing/customer-acquisition evidence or complete zero-spend review
```

## Competition reporting boundary

The final XPRIZE financial fields are denominated in USD. Do not convert CAD source records until the accounting policy selects and documents the FX basis/date. Retain both source currency and converted amount in the evidence ledger.

Until source attribution and recognition are complete:

```text
FIN-SRC-001 counted in AIGC expenses = false
FIN-SRC-002 counted in AIGC expenses = false
GitHub included minutes counted as cash expense = false
FIN-SRC-004 counted in AIGC expenses = false
FIN-SRC-005 counted in AIGC expenses = false
FIN-SRC-006 counted in AIGC expenses = false
final total expenses = UNRESOLVED
final COGS = UNRESOLVED
final marketing/CAC = UNRESOLVED
```
