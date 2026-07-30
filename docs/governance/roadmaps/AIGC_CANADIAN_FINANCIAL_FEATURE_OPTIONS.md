# AIGC Canadian Financial Feature Options

Status: `OPTIONS_FOR_OPERATOR_SELECTION`  
Baseline: Canadian Financial Work Execution v1  
Jurisdiction: Canadian federal preparation for Alberta (`CA-AB`) only  
Default: every option disabled

This roadmap is an option register, not blanket authorization. Each option requires an
explicit operator choice, its listed dependencies, tests on an exact revision, and any
separate provider or external-action authority. Selecting one option does not authorize
its dependencies, deployment, connector access, import of private records, export,
filing, payment, or government interaction.

The current repository work is an internal contract and local preparation surface, not
proof of hosted-CI verification, staging, production deployment, professional
acceptance, CRA/Alberta acceptance, or regulatory compliance. Any non-Alberta workflow
requires separate research, schemas, tests, and authorization.

## Current contract baseline

Before any option processes private evidence:

- configuration must be supplied as a current-process-owned regular file outside Git,
  with no group/other permissions (`0600` intended) and no final-component symlink;
- output must target a new child beneath an already-existing private `0700` parent
  outside the repository;
- packet, report, and receipt must be staged, durably flushed, and atomically published
  as one create-only private bundle (`0700` directory and `0600` files);
- configuration, packet, run-receipt, and backlog objects must pass their strict JSON
  Schema Draft 2020-12 contracts; and
- the v1 private-file workflow must run on Linux; unsupported operating systems fail
  closed pending equivalent descriptor-bound and atomic-publication controls; and
- schema or local-test success must not be promoted to production, professional, tax,
  accounting, or government acceptance.

Founder-effort selection is allowed only for independently verified, project-scoped
time recorded as `documented_time_verified` and a named reviewed rate. Repository
existence, owner statements, unknown hours, and scenario hours remain scenario-only and
cannot select a management estimate.

## Decision protocol

For an option to move from `proposed`:

1. The operator selects its exact task ID.
2. The implementation plan names the tenant, data classes, provider, read/write
   operations, locations, retention, budget, revision, and expiry.
3. Security, privacy, terms, and professional-review requirements are resolved.
4. The smallest reversible slice is implemented with synthetic fixtures first.
5. Hosted CI and the target staging environment prove the acceptance tests.
6. Read-only provider access is admitted before any write or submission capability.
7. Each later consequential action receives a separate identity-bound permit.

## P0 — Establish trustworthy evidence preparation

| Task | Optional feature | Dependencies | Acceptance evidence | Authority | Principal risk |
| --- | --- | --- | --- | --- | --- |
| `CAFIN-P0-001` | Authenticated tenant-scoped Financial Evidence tab | None | Default-off flag, object authorization, cross-tenant denial, redacted allowlist rendering | Code + staging authorization | Financial-data disclosure |
| `CAFIN-P0-002` | Secure external evidence store | P0-001 | Per-tenant encryption/access, immutable generations, malware/type/size controls, retention/legal-hold/deletion/restore tests | Data-store and privacy approval | Evidence loss or cross-tenant access |
| `CAFIN-P0-003` | Receipt ingestion and reconciliation core | P0-002 | Idempotent import, itemized/processor overlap graph, refund/reversal handling, no silent deletion, deterministic totals | Internal processing approval | Double counting |
| `CAFIN-P0-004` | GitHub billing import | P0-002, P0-003 | Read-only least privilege, billing-period and currency capture, pagination, duplicate/retry tests, provider receipt | GitHub read authorization | Organization billing exposure |
| `CAFIN-P0-005` | AI subscription receipt import | P0-002, P0-003 | Provider-by-provider allowlist, settlement versus renewal separation, tax/currency metadata, revocation | Email/store read authorization | Overbroad mailbox or account access |
| `CAFIN-P0-006` | Apple/App Store receipt import | P0-002, P0-003 | Itemized receipt parser, processor reconciliation, family/personal ambiguity queue, no Apple credential handling | Approved receipt-source read | Personal purchase exposure |
| `CAFIN-P0-007` | Google Play receipt import | P0-002, P0-003 | Itemized parser, subscription-cycle reconciliation, refund handling, no Google account mutation | Approved receipt-source read | Personal purchase exposure |
| `CAFIN-P0-008` | Mobile-carrier bill import | P0-002, P0-003 | Bill-period parsing, device/service separation, mixed-use queue, no carrier login automation | Approved document read | Sensitive communications metadata |
| `CAFIN-P0-009` | Human allocation review | P0-003 | Personal/mixed/candidate/unallocated decisions preserve source and reviewer, no automatic deductibility | Identity-bound internal approval | Unsupported business-purpose claim |
| `CAFIN-P0-010` | Time-evidence import | P0-001, P0-002 | Independently verified project-scoped time enters `documented_time_verified`; overlap rejection, correction trail, and no scenario hours promoted as facts | Time-source read authorization | Inflated or duplicated labor |
| `CAFIN-P0-011` | Accountant export preview | P0-003, P0-009 | Redacted, read-only, content-digested preview; zero external sends; reversible local deletion | Internal preview only | Premature tax/accounting reliance |

Recommended first operator selection: `CAFIN-P0-001`, followed by
`CAFIN-P0-002` and `CAFIN-P0-003`. Source connectors should wait for those controls.

## P1 — Complete the professional-review handoff

| Task | Optional feature | Dependencies | Acceptance evidence | Authority | Principal risk |
| --- | --- | --- | --- | --- | --- |
| `CAFIN-P1-001` | Entity and reporting-period registry | P0-001 | Effective-dated owner-reviewed entity facts; no inferred registrations | Internal owner approval | Wrong entity/period |
| `CAFIN-P1-002` | CRA/Alberta obligation preparation | P1-001, P0-003 | Current official-source registry, unknown-first states, T2125/T2/AT1/GST/payroll questions, no filing | Internal preparation | Mistaken reliance |
| `CAFIN-P1-003` | Records-retention and legal-hold workflow | P0-002, P1-001 | Record-specific retention, hold override, export/delete trace, restore proof | Privacy/records approval | Premature destruction |
| `CAFIN-P1-004` | Accountant review workspace | P0-009, P0-011, P1-002 | Separate reviewer identity, comments and dispositions append-only, no posting or submission | Professional reviewer access | Unauthorized disclosure |
| `CAFIN-P1-005` | GST/HST threshold monitor | P1-001, P1-002 | Single-quarter and rolling-window signals, exceptions remain unresolved, dated source version | Internal monitoring | Incorrect registration timing |
| `CAFIN-P1-006` | WCB-Alberta and Alberta PIPA preparation | P1-001, P1-002 | Worker/industry/privacy unknowns, source-bound checklist, no account action | Internal preparation | Worker/privacy misclassification |

## P2 — Add controlled business-finance capability

| Task | Optional feature | Dependencies | Acceptance evidence | Authority | Principal risk |
| --- | --- | --- | --- | --- | --- |
| `CAFIN-P2-001` | Project and engagement cost allocation | P0-009, P1-001 | Allocation totals reconcile to evidence; shared costs remain explicit; client isolation | Internal reviewer approval | Cross-client contamination |
| `CAFIN-P2-002` | Budget, runway, and variance projection | P2-001 | Assumptions versioned; cash evidence separated from forecasts; sensitivity ranges | Internal planning | Forecast presented as fact |
| `CAFIN-P2-003` | Revenue and invoice evidence register | P0-002, P1-001 | Invoice, receivable, settlement, and revenue recognition remain separate | Finance-review approval | Revenue overstatement |
| `CAFIN-P2-004` | Subscription renewal and anomaly queue | P0-003, source connectors | Alerts reference evidence, never cancel or pay, false-positive tracking | Internal notification approval | Unwanted financial action |
| `CAFIN-P2-005` | Professional export package | P1-003, P1-004, P2-001 | Schema/profile selected by reviewer, manifest/digests, destination preview, revocation | Export-specific approval | Data leakage or incompatible import |
| `CAFIN-P2-006` | Financial-control observability | P0-002, P0-003 | Tenant-safe metrics, no raw financial content, cost/error/SLO alerts | Operations approval | Telemetry leakage |

## P3 — Research consequential integrations

P3 is research-first. Nothing in this tier authorizes a government, payment,
accounting-system, payroll, banking, tax-filing, or regulator-facing action.

| Task | Optional feature | Dependencies | Acceptance evidence | Authority | Principal risk |
| --- | --- | --- | --- | --- | --- |
| `CAFIN-P3-001` | Accounting-system read adapter | P2-005 | Read-only sandbox, account-map preview, reconciliation and revocation | Provider read authorization | Accounting-data exposure |
| `CAFIN-P3-002` | Accounting posting proposal | P3-001, P1-004 | Proposal only, balanced preview, exact source links, independent reviewer; no posting | Internal proposal approval | Incorrect books |
| `CAFIN-P3-003` | Human-controlled accounting post | P3-002 | Single-use permit, immutable payload, provider reconciliation, rollback/compensation | Separate per-post authorization | Consequential financial mutation |
| `CAFIN-P3-004` | Certified tax-software handoff research | P1-004, P2-005 | Terms/API/legal review, sanitized sandbox, no CRA credentials or submission | Research authorization | Filing/representation liability |
| `CAFIN-P3-005` | Government-submission architecture research | P3-004 | Written legal/security/professional decision, identity-bound human control, fail-closed design | Separate research approval | Government-account compromise |
| `CAFIN-P3-006` | Payment/remittance architecture research | P2-005 | Threat model, dual control, amount/destination binding, reconciliation, incident exercise | Separate research approval | Irreversible loss |

No P3 task should be implemented as a live write until the operator separately
authorizes the precise external action after reviewing its preview. Direct CRA login,
credential/MFA handling, autonomous filing, autonomous payment, and autonomous
representative action remain prohibited.

## Suggested execution choices

The operator may choose one of these bounded next slices:

1. **Foundation only:** `CAFIN-P0-001`.
2. **Evidence vault:** `CAFIN-P0-001` + `CAFIN-P0-002`.
3. **Reconciliation core:** P0-001 through P0-003.
4. **One source:** P0-001 through P0-003 plus exactly one of P0-004 through P0-008.
5. **Human review packet:** P0-001 through P0-003, P0-009, and P0-011.
6. **Founder effort:** P0-001, P0-002, and P0-010, with no accounting or tax effect.
7. **Canadian preparation:** required P0 controls, then P1-001 and P1-002.

The smallest safe default is option 1. An exact task selection should be recorded before
another repository change begins.

## Primary official sources

- [CRA records retention](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/keeping-records/where-keep-your-records-long-request-permission-destroy-them-early.html)
- [CRA T2125 expenses](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/sole-proprietorships-partnerships/report-business-income-expenses/completing-form-t2125/expenses-section-form-t2125.html)
- [CRA GST/HST registration](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/when-register-charge.html)
- [CRA payroll remittance due dates](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/remitting-source-deductions/how-when-remit-due-dates.html)
- [CRA representative authorization](https://www.canada.ca/en/revenue-agency/services/tax/representative-authorization/overview.html)
- [Alberta corporate income tax](https://www.alberta.ca/corporate-income-tax)
- [Alberta annual returns](https://www.alberta.ca/corporations-cooperatives-organizations-annual-returns)
- [WCB-Alberta worker coverage](https://www.wcb.ab.ca/insurance-and-premiums/types-of-coverage/worker-coverage.html)
- [Alberta PIPA](https://www.alberta.ca/personal-information-protection-act)
