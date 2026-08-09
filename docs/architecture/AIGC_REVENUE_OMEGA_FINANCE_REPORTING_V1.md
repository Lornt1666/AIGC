# AIGC Revenue-Ω Finance Reporting V1

Status: `EVIDENCE-BOUND INTERNAL FINANCE REPORTING — NO TAX FILING / NO OWNER TRANSFER`

## Purpose

Create judge-facing and operator-facing financial reports that never combine projected, contracted, invoiced and collected value into one misleading revenue number.

## Revenue state separation

```text
PIPELINE
CONTRACTED
INVOICED
COLLECTED
REFUNDED
CHARGEBACK
```

Only `COLLECTED`, `REFUNDED` and `CHARGEBACK` records require cash/provider evidence and affect the cash contribution calculation.

`PIPELINE != REVENUE COLLECTED`

`INVOICE != PAYMENT`

## Expense classes

Direct/COGS-like classes:

```text
MODEL_COMPUTE
CLOUD_INFRASTRUCTURE
TOOL_API
PAYMENT_PROCESSOR
```

Operating classes:

```text
MARKETING_ACQUISITION
OTHER_OPERATING
```

Every expense record requires evidence. Zero-dollar periods can be represented truthfully with an empty evidence-backed expense set plus the corresponding source/account review, not fabricated transactions.

## Internal report

For one exact period/currency the report calculates:

```text
pipeline
contracted
invoiced
collected cash
refunds
chargebacks
gross cash after reversals
COGS/direct costs
marketing/customer acquisition
other operating expenses
total expenses
contribution before tax and reserves
```

All values are Decimal-based.

## Founder/business allocation

Founder compensation and owner distributions are downstream allocations from positive contribution cash, not a direct claim on a worker's paycheque.

The allocation policy can reserve positive contribution cash for:

```text
tax reserve
refund/chargeback reserve
operating reserve
business reinvestment
founder compensation
owner distribution
retained unallocated cash
```

Allocation percentages may not exceed 100% in aggregate.

If contribution cash is zero or negative:

```text
founder compensation = 0
owner distribution = 0
```

The allocation result is an internal accounting calculation with `external_action_performed=false`; it does not itself transfer funds.

## XPRIZE support

The reporting model directly supports distinct Build with Gemini XPRIZE fields for:

- revenue generated;
- revenue by month;
- total expenses;
- COGS;
- marketing/customer acquisition spend;
- explanatory P&L evidence.

AIGC still requires real source records before populating those fields. The report builder does not invent missing revenue, users, expenses or billing invoices.

## Report builder

```text
python scripts/build_revenue_omega_finance_report.py INPUT.json --output REPORT.json
```

The generated report is internal evidence preparation only and is not an audited financial statement or tax return.

## Authority boundary

```text
finance_calculation=true
internal_report_generation=true
founder_allocation_calculation=true
payment_transfer=false
owner_withdrawal=false
tax_filing=false
invoice_send=false
production_activation=false
external_action_performed=false
```
