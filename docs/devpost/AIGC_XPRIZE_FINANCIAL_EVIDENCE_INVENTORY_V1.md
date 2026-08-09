# AIGC XPRIZE Financial Evidence Inventory V1

Status: `SOURCE INVENTORY — NO PROJECT ATTRIBUTION OR ACCOUNTING RECOGNITION IMPLIED`

## Purpose

Track real hackathon-period financial source records without converting cash movements, prepaid balances, unrelated infrastructure, or unsupported assumptions into AIGC revenue/expense claims.

## Evidence rules

```text
cash payment != AIGC expense
prepaid API funding != consumed COGS
billing-account payment != project attribution
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

## Required follow-up evidence

Before final P&L:

```text
OpenAI provider billing/usage history for the hackathon period
Google Cloud monthly invoices or zero-dollar/cost-table statements
Google Cloud project/service cost attribution
GitHub Actions billed-overage statement if any
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
final total expenses = UNRESOLVED
final COGS = UNRESOLVED
```
