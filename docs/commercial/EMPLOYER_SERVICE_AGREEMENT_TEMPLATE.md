# AIGC Revenue-Ω Employer Service Agreement — Draft Template

Status: `DRAFT TEMPLATE — NOT EXECUTABLE — QUALIFIED COMMERCIAL/LEGAL REVIEW REQUIRED`

This document is a structured drafting artifact for employer-funded AIGC services. It is not a signed agreement, legal advice, a licence, an invoice, or authority to perform recruiting, placement, payment, payroll, cloud, or other external actions.

## 1. Parties

**AIGC operating entity:** `[LEGAL_ENTITY_TBD]`  
**Employer/customer:** `[EMPLOYER_LEGAL_NAME_TBD]`  
**Effective date:** `[TBD]`  
**Agreement ID:** `[TBD]`  
**Jurisdiction decision ID:** `[TBD]`

No agreement becomes active while any required operating licence, registration, jurisdiction decision, or signatory authority is unresolved.

## 2. Service scope

AIGC may provide only the services expressly selected in an executed schedule, including one or more of:

- opportunity/job intake and normalization;
- candidate sourcing and matching;
- structured qualification and screening support;
- employer-facing candidate introduction;
- governed AI-assisted assessment;
- interview/workflow coordination;
- placement attribution and evidence administration;
- compute/model/API/tool usage attributable to the employer's authorized work;
- optional enterprise software or analytics services.

AIGC does not guarantee employment, candidate performance, legal compliance by the employer, or business results except to the extent explicitly stated in an executed guarantee schedule.

## 3. Licensing and regulatory precondition

If the selected service is regulated as employment-agency or recruitment activity in the applicable jurisdiction, performance of that regulated service is conditional on the required licence/registration being current and verified.

```text
required_licence_status != VERIFIED
→ regulated_service_activation = BLOCKED
```

## 4. Worker/job-seeker fee boundary

For ordinary Alberta employment-placement services under this template:

```text
worker_placement_fee = 0
placement_payer = EMPLOYER
```

The Employer shall not deduct, recover, charge back, or otherwise transfer AIGC's recruiting/placement fee to the worker where prohibited by applicable law or the governing jurisdiction decision.

A worker's compensation may be used as a contractually defined pricing reference; it is not itself an authorization for AIGC to deduct from payroll or demand payment from the worker.

## 5. Covered jobs and placements

Each covered engagement shall identify:

```text
job_id
job_title
work_location
employment/contract classification
compensation structure
candidate/worker reference method
placement attribution rule
success event
fee schedule
billing cadence
```

Unlisted or disputed placements are not automatically billable.

## 6. Placement attribution

The parties shall select an attribution rule in the applicable schedule. The default AIGC state model is:

```text
ATTRIBUTED
SHARED_ATTRIBUTION
DISPUTED
UNKNOWN
NOT_ATTRIBUTED
```

Only `ATTRIBUTED` may automatically proceed to billing authorization. Other states require a documented resolution or contractual allocation rule.

## 7. Success / earning event

The agreement must define exactly when the success fee is earned. Select one and delete the others in the executed version:

- offer accepted;
- employment start confirmed;
- first shift/work period completed;
- probation/guarantee milestone completed;
- another specifically defined event.

No success fee is earned merely because AIGC generated a candidate, application, recommendation, draft, or introduction unless the executed agreement expressly says so and the model is permitted by the applicable jurisdiction decision.

## 8. Eligible compensation base

The executed schedule must define the exact base used for percentage pricing. Possible bases include:

- first-year base salary;
- eligible gross compensation actually paid during a defined billing period;
- guaranteed first-year cash compensation;
- annualized hourly base compensation;
- defined contract value;
- fixed employer bounty.

Unless expressly included, the calculation excludes uncertain/discretionary bonuses, tips, expense reimbursement, benefits, equity, pensions and other non-guaranteed compensation.

## 9. Success/finder fee

For percentage pricing:

```text
finder_fee_t = eligible_compensation_t × contractual_rate
```

**Contractual rate:** `[RATE_TBD]`  
**Minimum fee:** `[NONE_OR_TBD]`  
**Maximum fee:** `[NONE_OR_TBD]`  
**Fee duration/cadence:** `[TBD]`

The rate must be agreed before the billable placement event. AIGC may not retroactively increase the rate for an existing placement.

## 10. Compute / API / runtime cost recovery

The selected schedule must state one mode:

```text
ABSORBED_BY_PLATFORM
PASS_THROUGH
PASS_THROUGH_PLUS_MARGIN
INCLUDED_IN_SUCCESS_FEE
```

For pass-through plus margin:

```text
compute_recovery = verified_direct_compute_cost × (1 + compute_markup_rate)
```

Direct cost and platform markup shall remain separately auditable. Provider/cloud receipts or equivalent evidence shall support metered charges.

**Compute markup:** `[RATE_TBD]`  
**Per-period compute ceiling:** `[CAD_TBD]`

## 11. Other authorized services

Optional subscription, enterprise, analytics, premium assessment or other fees must be listed separately. No unlabeled charge may be substituted for a prohibited worker placement/recruiting fee.

## 12. Invoicing

An invoice may be issued only when Revenue-Ω verifies:

```text
active agreement
current persisted jurisdiction decision
verified payer identity
verified success event
verified compensation base
verified attribution
fee calculation matches agreement
unique billing idempotency key
approved invoice state
```

Invoice delivery requires a separately authorized external-effect action and provider receipt.

## 13. Payment terms

**Currency:** CAD unless the executed schedule states otherwise.  
**Payment terms:** `[TBD]`  
**Permitted methods:** provider-tokenized methods or other approved business payment methods.  
**Late-payment treatment:** `[TBD — subject to applicable law]`

AIGC shall distinguish invoice issuance from payment settlement. An unpaid invoice is not collected revenue.

## 14. Taxes

Applicable sales taxes are determined separately from the success-fee calculation using the current seller/customer/service/location tax state.

The agreement does not hard-code a universal tax rate. Any invoice tax line must be supported by the applicable tax decision/engine receipt.

## 15. Guarantee / replacement / credits

Select and define one:

```text
NO_GUARANTEE
FREE_REPLACEMENT
PRORATED_CREDIT
PARTIAL_REFUND
OTHER_DEFINED_REMEDY
```

Required fields:

```text
guarantee_start
guarantee_end
qualifying_trigger
exclusions
remedy
maximum_remedy
claim procedure
```

## 16. Disputes

Employer may dispute attribution, compensation base, rate, duplicate billing, success event, tax, payment state or guarantee entitlement.

A disputed invoice must enter the Revenue-Ω `DISPUTED` state and inappropriate automated collection actions are suspended until resolution under the governing process.

## 17. Candidate and worker data

The parties shall process candidate/worker personal information only for legitimate defined purposes and in accordance with the applicable privacy regime.

AIGC should use pseudonymous worker references in billing records whenever full identity is not operationally necessary.

Compensation evidence shall be minimized to what is necessary to establish and audit the contractual billing base.

## 18. AI-assisted processing and human authority

AIGC may use governed AI systems to support sourcing, matching, analysis, workflow coordination, evidence preparation and other authorized functions.

AI output alone does not:

- create a contract;
- authorize an invoice;
- prove payment;
- accept employment on behalf of a candidate;
- authorize external communication beyond granted scope;
- override employer or worker rights;
- override applicable law or provider controls.

## 19. Evidence and audit

AIGC may retain minimum necessary commercial evidence including:

```text
agreement hash
placement event hash
jurisdiction decision ID/hash
compensation evidence reference
compute usage receipts
commission calculation hash
billing decision hash
invoice hash
provider delivery/payment receipts
ledger references
```

Retention periods and access controls must be governed by the applicable privacy/data-retention policy.

## 20. Confidentiality and security

No party shall place raw passwords, API keys, private keys or payment-card credentials into ordinary AIGC prompts, emails, invoices or logs.

Provider credentials must be handled through approved secret/token infrastructure.

## 21. Term and termination

**Initial term:** `[TBD]`  
**Renewal:** `[TBD]`  
**Termination notice:** `[TBD]`

Termination does not create a new fee entitlement. The executed agreement must state how pre-termination introductions/placements are treated.

## 22. Limitation / indemnity / governing law

`[QUALIFIED LEGAL DRAFTING REQUIRED FOR ACTUAL OPERATING ENTITY AND CUSTOMER JURISDICTION]`

Do not deploy placeholder limitation, indemnity, governing-law, arbitration or forum clauses into a live agreement.

## 23. Entire agreement / amendments

Any commercial term affecting rate, payer, earning event, compensation base, duration, refund/guarantee, compute markup or other material billing logic must be versioned and accepted through the parties' authorized amendment process.

A material amendment produces a new agreement version/hash and cannot silently reuse stale billing authorization.

## 24. Signatures

**AIGC operating entity authorized signatory:** `[TBD]`  
Name/title: `[TBD]`  
Date: `[TBD]`

**Employer authorized signatory:** `[TBD]`  
Name/title: `[TBD]`  
Date: `[TBD]`

---

`TEMPLATE_ONLY = TRUE`  
`CONTRACT_ACCEPTANCE_AUTHORITY = FALSE`  
`INVOICE_SEND_AUTHORITY = FALSE`  
`PAYMENT_COLLECTION_AUTHORITY = FALSE`
