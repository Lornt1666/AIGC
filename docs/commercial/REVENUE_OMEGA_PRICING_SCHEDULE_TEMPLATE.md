# Revenue-Ω Pricing & Compute Recovery Schedule — Draft Template

Status: `TEMPLATE_ONLY — NO LIVE PRICE OR BILLING AUTHORITY`

## A. Commercial identifiers

```text
agreement_id          = [TBD]
employer_id           = [TBD]
jurisdiction          = [TBD]
jurisdiction_decision = [TBD]
pricing_version       = [TBD]
effective_date        = [TBD]
expiry/review_date    = [TBD]
currency              = CAD
```

## B. Placement success pricing

```text
payer_model        = EMPLOYER
worker_fee         = 0
rate_type          = PERCENTAGE | FIXED | BOUNTY
compensation_base  = [DEFINED_IN_EXECUTED_SCHEDULE]
commission_rate    = [TBD]
minimum_fee        = [NONE_OR_TBD]
maximum_fee        = [NONE_OR_TBD]
earning_event      = [TBD]
billing_cadence    = [TBD]
fee_duration       = [TBD]
```

Percentage formula:

```text
finder_fee = eligible_compensation × contractual_commission_rate
```

No percentage is effective until the executed agreement/schedule identifies the exact rate and base.

## C. Compute / model / API / runtime recovery

Select exactly one mode:

```text
ABSORBED_BY_PLATFORM
PASS_THROUGH
PASS_THROUGH_PLUS_MARGIN
INCLUDED_IN_SUCCESS_FEE
```

Meterable cost classes may include:

```text
model input tokens
model output tokens
cached tokens where billed
provider reasoning/compute units where billed
CPU/GPU/runtime duration
managed database usage
object storage
network egress
browser/search/API actions
email provider actions
payment processor costs
other expressly contracted third-party services
```

Every pass-through cost must retain provider/resource evidence or an auditable normalized receipt.

For pass-through plus margin:

```text
compute_recovery = direct_verified_cost × (1 + contractual_compute_markup)
```

Required controls:

```text
compute_markup_rate     = [TBD]
per_task_ceiling_cad    = [TBD]
per_period_ceiling_cad  = [TBD]
over_ceiling_behavior   = STOP | REQUIRE_NEW_AUTHORIZATION
```

Provider cost and AIGC markup must remain separately reportable.

## D. Optional recurring platform pricing

Any subscription/enterprise component must be separately named:

```text
plan_name
billing_interval
base_fee
included_usage
usage_overage_basis
cancellation_terms
```

Subscription pricing cannot be used to disguise a worker-paid recruitment/placement charge where that charge is prohibited.

## E. Invoice composition

```text
finder/success fee
+ compute/runtime recovery
+ other specifically authorized services
- contractual credits/discounts
+ applicable sales tax
= invoice total
```

Tax is resolved by a separately governed jurisdiction-aware tax component.

## F. Contribution margin

Internal business metric:

```text
contribution_margin =
collected_revenue
- direct_model_compute_cost
- direct_cloud_tool_cost
- processor_cost
- attributable_refunds_chargebacks
- allocated_operating_cost
```

`invoiced != collected`

`business_revenue != founder_withdrawal`

## G. Founder/business allocation

Only after settlement/accounting classification may net platform funds be allocated among:

```text
tax reserve
refund/chargeback reserve
operating reserve
business reinvestment
founder compensation
owner distribution
```

The allocation policy must not treat a worker's paycheque as cash already collected by AIGC.

## H. Change control

Changing any of the following invalidates stale billing authorization and creates a new pricing/agreement revision:

```text
payer
commission rate
compensation base
fee duration
compute pricing mode
compute markup
minimum/maximum fee
earning event
currency
material guarantee/refund rule
```

---

`TEMPLATE_ONLY = TRUE`  
`FINANCIAL_AUTHORITY_GRANTED = FALSE`
