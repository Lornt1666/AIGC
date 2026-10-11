# Revenue-Ω Alberta Pre-Launch Commercial Register

Status: `BLOCKED FOR LIVE PLACEMENT BILLING PENDING LICENSING + ACCOUNTABLE REVIEW`

This register converts current public regulatory facts into a fail-closed AIGC launch posture. It is not legal advice, a licence, or a completed jurisdiction decision.

## 1. Service classification

AIGC's proposed Alberta employment-placement activity may fall within the Alberta employment-agency licensing regime because the platform is designed to secure people for employment, secure employment for people, and/or evaluate candidates for employers.

Official reference:

- https://www.alberta.ca/employment-agency-licence

Operational state:

```text
employment_agency_licence_required_review = REQUIRED
active_licence_verified = false
live_placement_billing_allowed = false
```

## 2. Job-seeker fee boundary

The default Revenue-Ω Alberta model SHALL NOT charge an individual a recruiting/placement fee for securing employment.

The economic model is therefore:

```text
worker compensation = pricing reference where contractually defined
employer = commercial payer
AIGC fee = separate employer obligation
```

The employer agreement must prohibit passing the employment-agency fee back to the worker through payroll deduction, cash demand, or other recovery mechanism.

Official references:

- https://www.alberta.ca/work-in-alberta
- https://www.alberta.ca/resources-temporary-foreign-workers
- https://www.alberta.ca/employment-agency-licence

Machine state:

```text
worker_placement_fee_allowed = false
worker_payroll_deduction_for_AIGC_placement_fee = false
employer_funded_success_fee = REQUIRES_ACTIVE_LICENCE_AND_AGREEMENT
```

## 3. Employment-agency agreement gate

Before live recruitment/placement service is activated, obtain and review the standard agreements required for the applicable Alberta employment-agency licence and align Revenue-Ω terms to those requirements.

Required AIGC employer contract fields:

```text
legal parties
licensing representation
covered jobs / employer account
service description
placement attribution rule
success / earning event
eligible compensation definition
success fee percentage
compute/API/runtime recovery method
invoice cadence
payment terms
tax treatment
guarantee / replacement / credit terms
dispute terms
privacy/data processing
term / termination
no worker fee recovery covenant
signatures
```

No executable agreement may be created from the template until the final wording is reviewed for the actual operating entity and jurisdiction.

## 4. Privacy gate

Alberta PIPA is the province's private-sector privacy law for provincially regulated private-sector organizations. Revenue-Ω may process candidate identity, compensation, employer, application, billing, and evidence data, so privacy design must be treated as a launch dependency.

Official reference:

- https://www.alberta.ca/personal-information-protection-act

Required controls:

```text
purpose limitation
data minimization
role-based access
worker-reference pseudonymization where practical
retention schedule
access/correction process
security safeguards
breach/incident procedure
processor/provider inventory
cross-border/service-provider review
```

Compensation evidence should be narrowed to the minimum data required to calculate and audit the contracted employer fee.

## 5. GST/HST gate

CRA guidance states that most businesses making taxable supplies in Canada generally must register for GST/HST when they cease to be a small supplier; the general small-supplier threshold for most businesses is CAD $30,000, subject to the detailed statutory calculation and exceptions. Voluntary registration may also be possible before the threshold.

Official reference:

- https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/when-register-charge.html

Revenue-Ω SHALL therefore keep tax determination outside the commission engine and require a current operating-entity tax state:

```text
gst_hst_registration_state
registration_effective_date
seller_jurisdiction
buyer_jurisdiction
service_type
place_of_supply
tax_rate_source
tax_calculation_receipt
```

No hard-coded global tax rate is permitted.

## 6. Payroll boundary

AIGC is not the employer payroll system in the ordinary placement model. Revenue-Ω SHALL NOT create a worker payroll deduction for the AIGC placement commission.

Any unrelated payroll deduction functionality in future products must be governed independently under applicable employment standards and written authorization requirements and cannot be used to circumvent employment-agency fee prohibitions.

Official reference:

- https://www.alberta.ca/ar/deductions-from-earnings

## 7. Launch decision object

Before `allowed=true` can be persisted for Alberta employment placement, an accountable reviewer must create a signed/digested jurisdiction decision containing:

```text
decision_id
jurisdiction = CA-AB
service_type = EMPLOYMENT_PLACEMENT
payer_model = EMPLOYER
allowed
conditions[]
reviewed_by
reviewed_at
expires_at
source_refs[]
decision_hash
```

The Revenue-Ω engine resolves this decision from trusted persistence by ID and rejects:

```text
missing decision ID
missing repository
non-persisted decision
invalid decision hash
expired/not-current decision
wrong jurisdiction
wrong service type
wrong payer model
decision.allowed == false
```

A caller-supplied `jurisdiction_approved=true` boolean is explicitly non-authoritative.

## 8. Current launch posture

As of the creation of this register:

```text
public_regulatory_sources_reviewed = true
AIGC_active_employment_agency_licence_verified = false
qualified_final_commercial_review_completed = false
live_employer_agreement_approved = false
live_invoice_send_authority = false
payment_collection_authority = false
production_revenue_omega_activation = false
```

Therefore:

`ALBERTA_REVENUE_OMEGA_EMPLOYMENT_PLACEMENT = BLOCKED_PENDING_LICENSING_AND_ACCOUNTABLE_REVIEW`
