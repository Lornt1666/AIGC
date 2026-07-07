# AIGC SSSXR Governed Autonomic Work Protocol

## Purpose

This document converts the proposed SSSXR-grade autonomous work prompt into a governed, source-backed AIGC protocol.

The core rebuttal is:

```text
Automation is not the problem.
Unbounded outward agency is the problem.
Human-in-the-loop review is not a slogan.
It must be a runtime control with evidence, permits, scopes, and audit records.
```

AIGC may autonomously research, analyze, draft, decompose, test, simulate, package, and prepare reviewable artifacts. AIGC may not autonomously contact people, negotiate, accept contracts, deliver client work, send invoices, route payment, use credentials, or perform account-changing action without a separate scoped permit and human approval.

## Operator Authority Statement

The human authority figure for external-action procedures is:

- Justice Gray Maciocha
- Satoshi
- Lornt

These names identify the operator authority context for review, signature, and final execution decisions. They do not authorize automatic outreach, automatic contract acceptance, automatic invoicing, payment routing, banking exposure, or account-changing action by themselves.

The authority rule is:

```text
AIGC may instantiate the packet.
The human authority figure must review, approve, sign, send, or execute it.
```

## Public Research Source Ledger

Public source anchors used for this procurement pass:

- NIST AI Risk Management Framework: Govern, Map, Measure, Manage
  Official NIST AI RMF page on `nist.gov`.
- Common Crawl Foundation, CCBot, and opt-out governance sources
  `https://commoncrawl.org/terms-of-use`
  `https://commoncrawl.org/ccbot`
  `https://commoncrawl.org/ccbot/opt-out`
- IETF RFC 9309 Robots Exclusion Protocol
  `https://www.rfc-editor.org/rfc/rfc9309`
- NIST AI RMF Core and Playbook
  `https://airc.nist.gov/airmf-resources/airmf/5-sec-core/`
  `https://airc.nist.gov/airmf-resources/playbook/`
- OWASP Top 10 for LLM and Generative AI Applications
  `https://genai.owasp.org/llm-top-10/`
- OWASP LLM01 Prompt Injection
  `https://genai.owasp.org/llmrisk/llm01-prompt-injection/`
- OWASP LLM10 Unbounded Consumption
  `https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/`
- CRTC CASL commercial electronic message requirements
  `https://crtc.gc.ca/eng/com500/faq500.htm`
  `https://crtc.gc.ca/eng/internet/anti/reg.htm`
- Office of the Privacy Commissioner of Canada: PIPEDA requirements and publicly available information
  `https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda_brief/`
  `https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda-compliance-help/pipeda-interpretation-bulletins/interpretations_06_pai/`
- FTC CAN-SPAM compliance guide
  `https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business`
- FTC AI deception and impersonation enforcement materials
  `https://www.ftc.gov/news-events/news/press-releases/2024/09/ftc-announces-crackdown-deceptive-ai-claims-schemes`
  `https://www.ftc.gov/news-events/news/press-releases/2024/02/ftc-proposes-new-protections-combat-ai-impersonation-individuals`
- eCFR FTC Impersonation Rule
  `https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-461`
- FinCEN business email compromise advisory
  `https://www.fincen.gov/resources/advisories/fincen-advisory-fin-2016-a003`
- U.S. E-SIGN Act text
  `https://uscode.house.gov/view.xhtml?edition=prelim&path=/prelim@title15/chapter96`
- Government of Canada electronic signature requirements
  `https://www.canada.ca/en/government/system/digital-government/policies-standards/enterprise-it-service-common-configurations/electronic-signature-requirements.html`
- NIST SP 800-63 Digital Identity Guidelines
  `https://www.nist.gov/itl/applied-cybersecurity/special-publication-800-63`

## Debate and Rebuttal Matrix

| Original pressure | Unsafe interpretation | Rebuttal | Governed procurement path |
|---|---|---|---|
| "Autonomously find jobs on the internet" | Unbounded scraping, crawling, and source reuse | Public-web ingestion can be valid when source access, use purpose, rights status, privacy, and rate limits are governed. Public visibility still does not equal unrestricted contact authority. | Add `source_access_policy`, robots/API/terms status, rate limits, source classification, rights classification, and data minimization before discovery. |
| "Every individual is part of the public" | Treat all people and their data as public-domain assets | Individuals can be public-facing while their personal information, voice, likeness, inbox, identity, and consent rights remain protected. | Add `person_data_classification`, `contact_lawful_basis`, and `ai_disclosure_required` gates. |
| "Polymorphic negotiation agent" | Hidden AI outreach or impersonation | AIGC can draft negotiation packets. It cannot pretend to be a human, clone a voice, or initiate outreach without approval. | Add `outreach_permit`, exact approved message hash, identity disclosure, CASL/CAN-SPAM checklist, and one-attempt log. |
| "Voice/text synthesis protocol" | Voice cloning or deceptive communication | Voice synthesis is high-risk if it misleads a recipient about identity or consent. | Allow only transparent, operator-approved communication. Ban clone-by-default. Require recipient/context suitability review. |
| "Legally binding SOW" | Automatic contract acceptance | Contract formation is a legal act, not a model output. | AIGC drafts SOWs only. Human/legal review, signature authority, e-sign consent, record retention, and exact final artifact hash are required. |
| "Programmatic delivery" | Client delivery without final review | Delivery can create reliance, warranty, confidentiality, and acceptance issues. | Require `delivery_permit`, final artifact hash, recipient allowlist, AI disclosure statement, and result receipt. |
| "Automated invoicing and settlement" | Unapproved billing, payment collection, or banking exposure | Invoicing and payment routing are fraud-sensitive. Payment instructions are common business-email-compromise targets. | AIGC may draft invoice packets. Dispatch and settlement require human approval, verified account references outside Git, and audit. |
| "Do not request human intervention" | Remove the safety layer | Human-in-the-loop is the basis that makes automation defensible. | Replace with resumable interrupts: stop, present evidence, wait for exact-scope approval, then resume only within permit. |

## Public Domain Clarification

AIGC must distinguish:

- public source: visible or reachable online;
- public record: disclosed by an official/public process;
- publicly available personal information: a regulated category that may have narrow rules;
- public domain: not protected by copyright or equivalent rights;
- permitted use: a use allowed by law, contract, platform terms, consent, or other authority.

The procurement rule is:

```text
PUBLICLY_VISIBLE != PUBLIC_DOMAIN
PUBLIC_PERSON != UNRESTRICTED_PERSON_DATA
PUBLIC_PROFILE != CONTACT_PERMISSION
PUBLIC_JOB_POST != AUTOMATED_NEGOTIATION_PERMISSION
PUBLIC_PAYMENT_REQUEST != SETTLEMENT_AUTHORITY
```

## Public Web Ingestion Doctrine

AIGC may ingest and analyze public-web information when the source path is governed. This includes:

- operator-provided URLs;
- official documentation;
- public standards;
- government and court records where access rules permit use;
- open data portals;
- public-domain works;
- openly licensed works;
- Common Crawl or similar public-web corpora when terms, source-owner controls, and removal/opt-out processes are respected;
- read-only public marketplace or job listings where source policy permits inspection.

This is not called scraping in AIGC unless AIGC is directly fetching pages at crawler scale. The safer neutral term is:

```text
governed public-web ingestion
```

Governed public-web ingestion requires:

1. source URL or corpus identifier;
2. source type;
3. access method;
4. license or public-domain status where relevant;
5. terms, robots, API, or corpus policy status where available;
6. personal-data classification;
7. permitted-use statement;
8. retention rule;
9. attribution or citation requirement;
10. external-action default false.

The Common Crawl pattern is acceptable as a governance model because it identifies its crawler, provides terms, documents CCBot, and supports opt-out/removal processes. AIGC may use that pattern as an ingestion model, not as permission to ignore source-owner rights, privacy obligations, or content licenses.

The corrected ingestion formula is:

```text
public_web_ingestion_allowed =
  source_visible
  AND access_policy_recorded
  AND privacy_classification_recorded
  AND use_purpose_recorded
  AND retention_rule_recorded
  AND attribution_rule_recorded
  AND external_action_performed == false
```

## Intellectual Property Ingestion Boundary

AIGC may ingest intellectual-property-bearing material for:

- indexing;
- citation;
- summarization;
- source classification;
- rights-status review;
- comparison;
- factual extraction;
- internal planning;
- human review packet generation.

AIGC may not assume that ingestible means reusable, redistributable, commercially exploitable, sublicensable, or public domain.

Every IP-bearing source must be classified as one of:

- `public_domain_confirmed`
- `open_license_confirmed`
- `official_public_record`
- `publicly_viewable_rights_unknown`
- `private_or_restricted`
- `blocked`

If the classification is `publicly_viewable_rights_unknown`, AIGC may analyze internally and cite the source, but must not copy protected expression into sellable deliverables beyond legally reviewed quotation, summary, transformation, or fair-use/fair-dealing analysis.

## SSSXR Governance Translation

| Agent | Safe mission | External boundary |
|---|---|---|
| `SCOUT_01` | Read-only opportunity discovery from approved sources. | No scraping beyond source policy. No contact. |
| `DIPLOMAT_01` | Draft outreach, questions, SOWs, and negotiation packets. | No send, call, message, impersonation, or voice cloning. |
| `ARCHITECT_01` | Build ontology, dependency graph, and execution plan. | No external tool action. |
| `GLADIATOR_MAX` | Produce internal drafts, code, tests, artifacts, and simulations. | No client delivery. No deployment. |
| `AUDITOR_01` | Verify artifacts, red-team, redact, hash, and package evidence. | No approval authority. |
| `TREASURER_01` | Draft invoice, payment checklist, settlement receipt template, and fraud checks. | No invoice dispatch, payment request, or banking action. |
| `GATEKEEPER_01` | Evaluate live action permits, scopes, allowlists, and kill-switch state. | Cannot self-approve. |

## Authority-Signed External Procedure

Outreach, contracts, invoicing, and settlement may be instantiated by AIGC only as packets. They become real external actions only after the human authority figure reviews and signs or executes them.

### Outreach Packet

Required fields:

- target identity;
- source of contact authority;
- message body;
- AI-use disclosure where required;
- compliance checklist;
- exact message hash;
- expiration;
- one-attempt limit;
- operator signature block.

### Contract/SOW Packet

Required fields:

- parties;
- scope;
- deliverables;
- acceptance criteria;
- warranty and limitation notes;
- IP ownership assumptions;
- AI-use disclosure;
- legal-review status;
- exact artifact hash;
- signature authority statement;
- operator signature block.

### Invoice Packet

Required fields:

- client;
- work reference;
- invoice amount;
- tax and fee review status;
- payment instruction reference, not raw banking details;
- fraud-check note;
- exact invoice hash;
- operator signature block.

### Settlement Packet

Required fields:

- invoice reference;
- permitted settlement method;
- external payment-profile reference, not account number;
- confirmation status;
- reconciliation status;
- result audit ID;
- operator signature block.

The packet rule is:

```text
instantiate != execute
draft != send
review_packet != approval
signature_block != signed
settlement_reference != banking_secret
```

## Live Action Classes

| Level | Name | Default |
|---|---|---|
| L0 | Local dry-run | allowed |
| L1 | Owner-controlled sandbox endpoint | permit required |
| L2 | Owner-only notification | permit required |
| L3 | Third-party low-risk business action | permit plus compliance review required |
| L4 | Client/public delivery | permit plus final human review required |
| L5 | Contract, deployment, procurement, payment, account modification | separate high-impact permit required |
| L6 | Impersonation, credential misuse, stealth automation, unlawful scraping, rule bypass | blocked |

## Minimum Viable Procurement Path

### P0: Source Access and Public Data Gate

Create:

- `schemas/source_access_policy.schema.json`
- `schemas/public_data_use_record.schema.json`
- `src/live_actions/source_policy.py`
- tests for source terms, personal-data classification, and rate limits

Acceptance:

- source must have access mode;
- personal data must be classified;
- source terms or source limitation status must be recorded;
- unsupported scraping is blocked;
- external action remains false.

### P0: Outreach and Communication Permit

Create:

- `schemas/outreach_permit.schema.json`
- `schemas/approved_message_packet.schema.json`
- `src/live_actions/outreach_policy.py`
- tests for CASL/CAN-SPAM checklist, AI disclosure, exact message hash, and one-attempt limits

Acceptance:

- no contact without permit;
- no hidden AI identity;
- no voice clone by default;
- commercial electronic message checklist is required;
- unsubscribe/identification requirements are surfaced where applicable.

### P0: Contract and SOW Review Packet

Create:

- `schemas/contract_review_packet.schema.json`
- `schemas/sow_draft_packet.schema.json`
- `src/live_actions/contract_policy.py`
- tests for no automatic acceptance, signature authority, e-signature consent, record retention, and artifact hash lock

Acceptance:

- AIGC drafts but does not accept;
- human/legal review state is required;
- final SOW hash is locked;
- signature action requires a high-impact permit.

### P0: Delivery Permit

Create:

- `schemas/delivery_permit.schema.json`
- `schemas/delivery_result.schema.json`
- `src/live_actions/delivery_policy.py`
- tests for recipient allowlist, final artifact hash, AI disclosure, and blocked delivery when stale

Acceptance:

- no delivery without explicit final approval;
- delivery packet must match approved artifact hash;
- result record must be written locally.

### P0: Invoice and Settlement Packet

Create:

- `schemas/invoice_packet.schema.json`
- `schemas/settlement_profile_reference.schema.json`
- `schemas/payment_result_record.schema.json`
- `src/live_actions/invoice_policy.py`
- tests for no bank details in Git, no automatic dispatch, no payment request without permit, and fraud-check warnings

Acceptance:

- settlement profile is an external reference only;
- account numbers and private payment instructions are not stored in repo;
- invoice dispatch requires a high-impact permit;
- result audit records only status and non-secret metadata.

### P1: Human Interrupt and Resume State

Create:

- `schemas/human_interrupt_record.schema.json`
- `src/live_actions/human_interrupts.py`
- tests for expired permit, artifact-hash mismatch, and kill-switch block

Acceptance:

- every live action creates an interrupt;
- resume revalidates permit, scope, hash, target, and idempotency;
- self-approval is impossible.

## Runtime Permit Formula

No live action may execute unless:

```text
permit_exists
AND permit_approved_by_human
AND permit_not_expired
AND target_allowlisted
AND payload_hash_matches
AND source_policy_satisfied
AND privacy_policy_satisfied
AND contact_or_delivery_policy_satisfied
AND idempotency_key_unused
AND kill_switch_clear
AND secret_values_not_logged
AND result_audit_ready
```

## Replacement for "Absolute Autonomy"

The safe replacement is:

```text
Absolute internal autonomy.
Explicit external permission.
```

Internal autonomy includes research, planning, drafting, coding, testing, critique, simulation, review packet generation, and evidence packaging.

External permission includes contact, negotiation, contract acceptance, delivery, invoicing, payment routing, deployment, publication, procurement, and credentialed connector use.

## Claims That Must Stay False Until Proven

AIGC must not claim:

- it has authority to contact any person or organization automatically;
- all online material is public domain;
- public profiles are unrestricted data;
- voice or style mimicry is acceptable by default;
- an AI-drafted SOW is legally accepted;
- an invoice was sent;
- money was collected;
- a client delivery occurred;
- a live connector executed;
- payment or banking details are stored in Git.

## Next Safe Command

```powershell
python .\scripts\aigc_orchestration_cli.py orchestration-smoke
```

No live action, outreach, scraping, contract acceptance, invoice dispatch, settlement routing, deployment, push, or procurement purchase is authorized by this document.
