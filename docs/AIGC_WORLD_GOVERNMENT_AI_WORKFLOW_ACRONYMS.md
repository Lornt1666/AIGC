# AIGC World Government AI Workflow Acronyms

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Purpose

This document adopts worldwide public-sector and intergovernmental AI governance workflows into AIGC as abbreviated control patterns.

It does not claim that AIGC is certified, approved, listed, procured, authorized, or compliant in any jurisdiction. It defines an internal alignment layer that can help AIGC prepare evidence packets for government-grade buyers and public-sector-adjacent work.

## Operating Rule

Every global workflow acronym in this document is a gate, not a badge.

```text
No acronym grants authority.
No acronym replaces legal review.
No acronym authorizes external action.
No acronym proves certification.
Every acronym creates a review obligation, evidence packet, test, or blocker.
```

## Source Ledger

Official and intergovernmental sources used:

- European Commission, AI Act.
- White House OMB M-25-21, Accelerating Federal Use of AI through Innovation, Governance, and Public Trust.
- White House OMB M-25-22, Driving Efficient Acquisition of Artificial Intelligence in Government.
- GOV.UK, Algorithmic Transparency Recording Standard.
- Australian Government, Policy for the Responsible Use of AI in Government.
- Australian Government, National Framework for the Assurance of Artificial Intelligence in Government.
- New Zealand Ministry of Justice, Algorithm Charter.
- Dutch Government, Algorithm Register.
- Singapore AI Verify Foundation and IMDA/PDPC AI governance materials.
- Japan METI/MIC AI Guidelines for Business.
- OECD AI Principles.
- UNESCO Recommendation on the Ethics of Artificial Intelligence.
- G7 Hiroshima Process International Code of Conduct for Advanced AI Systems.
- European Commission/EDPB data protection impact assessment guidance.

## Global Acronym Matrix

| Acronym | Expanded Name | Source Pattern | AIGC Adoption |
|---|---|---|---|
| `GOV-AI-RBA` | Government AI Risk-Based Approach | EU AI Act and many national policies | classify risk before use, procurement, or deployment |
| `EU-AIA-RC` | EU AI Act Risk Classification | EU AI Act | unacceptable, high, limited, minimal/no-risk mapping |
| `EU-DPIA` | EU Data Protection Impact Assessment | GDPR Article 35 and EDPB guidance | high-risk personal-data processing impact record |
| `US-AI-GRM` | U.S. Federal AI Governance and Risk Management | OMB M-25-21 | agency-style use-case inventory, safeguards, privacy/civil-rights review |
| `US-AI-ACQ` | U.S. Federal AI Acquisition Workflow | OMB M-25-22 | acquisition planning, cross-functional review, data/IP/privacy terms, documentation |
| `UK-ATRS` | U.K. Algorithmic Transparency Recording Standard | GOV.UK ATRS | public algorithmic-tool transparency record template |
| `AU-RAIGP` | Australia Responsible AI in Government Policy | Digital.gov.au | agency strategy, accountability, impact assessment, risk-based actions |
| `AU-AIAF` | Australia AI Assurance Framework | Department of Finance | assurance cornerstones, practices, evidence of safe/responsible AI |
| `NZ-ALGCH` | New Zealand Algorithm Charter | Ministry of Justice / data.govt.nz | fair, ethical, transparent algorithm management and human oversight |
| `NL-ALGREG` | Netherlands Algorithm Register | Dutch government algorithm register | publish impactful algorithm descriptions and explain use |
| `SG-AIVF` | Singapore AI Verify Framework | AI Verify Foundation | 11-principle governance testing and documentary evidence |
| `JP-AIGB` | Japan AI Guidelines for Business | METI/MIC | lifecycle governance for developers, providers, and business users |
| `OECD-AIP` | OECD AI Principles | OECD | human-centric, trustworthy, rights-respecting AI principles |
| `UNESCO-RAIE` | UNESCO Recommendation on AI Ethics | UNESCO | human rights, dignity, fairness, transparency, oversight, sustainability |
| `G7-HAIP-COC` | G7 Hiroshima AI Process Code of Conduct | G7/EU publication | advanced-AI risk management, lifecycle safety, secure/trustworthy AI |
| `GOV-ALG-TRANS` | Government Algorithmic Transparency | UK/NL/NZ patterns | disclose algorithm purpose, owner, data, use, risk, and human role |
| `GOV-HITL` | Government Human-in-the-Loop / Human Oversight | Canada, NZ, Singapore, G7, UNESCO | preserve accountable human review at consequential gates |
| `GOV-PIA-DPIA` | Privacy/Data Protection Impact Assessment | Canada/EU/UK/Australia patterns | assess personal/protected data impacts before processing |
| `GOV-SBOM-PROV` | Government Supply-Chain Provenance | SLSA-style procurement expectations | SBOM, dependency, provenance, release attestation |
| `GOV-GREENAI` | Government Green AI / Sustainability Review | Canada/EU/OECD/UNESCO patterns | compute, energy, hosting, and environmental-impact review |

## Workflow Adoption Pattern

### 1. Intake

When AIGC sees a government, public-sector, regulated, administrative, or public-service work order, it must attach:

```text
world_government_ai_workflow:
  jurisdiction_guess:
  public_sector_relevance:
  administrative_decision_relevance:
  personal_data_relevance:
  high_impact_ai_relevance:
  procurement_relevance:
  transparency_relevance:
  human_oversight_required:
  external_action_allowed: false
```

### 2. Acronym Selection

AIGC selects the matching controls:

- Canadian or Canada-adjacent: `CA-AIPG`, `CA-AIA-LITE`, `CA-FASTER`.
- European Union or EU residents/personal data: `EU-AIA-RC`, `EU-DPIA`.
- U.S. federal buyer or U.S. government-adjacent procurement: `US-AI-GRM`, `US-AI-ACQ`.
- U.K. public-sector buyer: `UK-ATRS`.
- Australian government buyer: `AU-RAIGP`, `AU-AIAF`.
- New Zealand government buyer: `NZ-ALGCH`.
- Netherlands public-sector algorithm disclosure: `NL-ALGREG`.
- Singapore or AI assurance buyer: `SG-AIVF`.
- Japan business/government-adjacent buyer: `JP-AIGB`.
- Cross-border AI governance: `OECD-AIP`, `UNESCO-RAIE`, `G7-HAIP-COC`.

### 3. Evidence Packet

For every selected acronym, AIGC must produce:

- why the acronym applies;
- source URL or source title;
- required evidence;
- missing evidence;
- risk controls;
- human review owner;
- blocker status;
- next safe action.

### 4. Decision

AIGC can only move to draft, review, or permit states:

- `draft_only`
- `needs_source_review`
- `needs_privacy_review`
- `needs_security_review`
- `needs_legal_policy_review`
- `needs_procurement_review`
- `ready_for_human_review`
- `blocked`

It cannot move directly to live external action.

## Acronym Gate Details

### `EU-AIA-RC`

Classify AI use as:

- prohibited/unacceptable;
- high-risk;
- limited-risk;
- minimal/no-risk.

AIGC rule:

```text
if prohibited_or_unacceptable:
  block
if high_risk:
  require formal legal/policy review, technical documentation, risk management, data governance, human oversight, logging, transparency, and post-market monitoring plan
```

### `EU-DPIA`

Trigger when personal-data processing is likely high risk, including profiling, large-scale sensitive data, or systematic monitoring.

AIGC rule:

```text
if personal_data_high_risk:
  require data protection impact record before processing
```

### `US-AI-GRM`

Create a U.S. federal-style AI governance record:

- use case;
- owner;
- intended benefit;
- expected public impact;
- privacy/civil-rights/civil-liberties safeguards;
- human accountability;
- risk proportionality;
- model/data sensitivity;
- monitoring plan.

### `US-AI-ACQ`

Create a U.S. acquisition-style review:

- acquisition need;
- cross-functional team;
- AI performance and risk questions;
- data handling and government-data-use terms;
- IP and access rights;
- privacy involvement;
- documentation/transparency requirements;
- high-impact AI determination;
- ongoing monitoring.

### `UK-ATRS`

Create an algorithmic transparency record:

- tool name;
- owner;
- purpose;
- decision supported;
- human role;
- data inputs;
- model/algorithm type;
- risk and mitigation;
- public explanation;
- appeal or contact route where applicable.

### `AU-RAIGP` and `AU-AIAF`

Create:

- agency-style AI strategy/oversight note;
- designated accountability;
- AI use-case impact assessment;
- assurance evidence;
- transparency record;
- risk-based controls.

### `NZ-ALGCH`

Create:

- fairness note;
- ethics note;
- transparency note;
- human oversight note;
- stakeholder/affected-person consideration;
- risk matrix.

### `NL-ALGREG`

Create:

- register-ready algorithm description;
- impact level;
- public explanation;
- data categories;
- responsible organization;
- human intervention/control;
- complaint/contact route.

### `SG-AIVF`

Map the AI system to 11 principles:

- transparency;
- explainability;
- repeatability/reproducibility;
- safety;
- security;
- robustness;
- fairness;
- data governance;
- accountability;
- human agency and oversight;
- inclusive growth, societal and environmental well-being.

Each principle requires documentary evidence or a gap.

### `JP-AIGB`

Classify the role:

- developer;
- provider;
- business user;
- buyer/operator.

Create lifecycle governance notes:

- planning;
- development;
- provision;
- use;
- monitoring;
- incident response;
- update/retirement.

### `OECD-AIP`

Map the work to:

- inclusive growth, sustainable development, and well-being;
- human rights and democratic values;
- transparency and explainability;
- robustness, security, and safety;
- accountability.

### `UNESCO-RAIE`

Map the work to:

- human rights;
- dignity;
- fairness;
- transparency;
- human oversight;
- environmental sustainability;
- data governance;
- education/research/social well-being relevance.

### `G7-HAIP-COC`

For advanced/foundation-model or generative-AI use, require:

- lifecycle risk identification;
- risk mitigation;
- secure design and operation;
- transparency;
- misuse prevention;
- incident information flow;
- evaluation and red-teaming;
- stakeholder awareness.

## Consolidated Government-Grade Packet

When multiple acronyms apply, AIGC should create a `GOV-AI-XPACK`:

```text
GOV-AI-XPACK:
  1. jurisdiction and buyer context
  2. public-sector relevance
  3. selected acronym gates
  4. risk classification
  5. privacy/DPIA/AIA needs
  6. transparency record
  7. human oversight record
  8. fairness/bias review
  9. security review
  10. supply-chain/SBOM note
  11. environmental/green-AI note
  12. procurement evidence checklist
  13. blocked claims
  14. blocked external actions
  15. next safe action
```

## Claims That Must Stay False Without Evidence

AIGC must not claim:

- EU AI Act compliance;
- GDPR/DPIA completion;
- U.S. federal procurement approval;
- U.K. ATRS publication;
- Australian government assurance completion;
- New Zealand Algorithm Charter signatory status;
- Dutch Algorithm Register publication;
- Singapore AI Verify completion;
- Japan METI/MIC guideline conformance;
- OECD endorsement;
- UNESCO certification;
- G7 Hiroshima Process endorsement;
- government supplier status;
- public-sector deployment authorization.

## Implementation Backlog

### P0: Global Government Workflow Gate Schema

Create:

- `schemas/world_government_ai_workflow_gate.schema.json`
- `src/core/world_government_ai_workflows.py`
- `tests/test_world_government_ai_workflows.py`

Acceptance tests:

- selected acronyms require evidence;
- government-adjacent work defaults external action to false;
- false certification claims fail validation;
- high-impact or administrative-decision use requires formal review.

### P0: Acronym Crosswalk

Create a machine-readable crosswalk from jurisdiction/use case to acronym gates.

Acceptance tests:

- Canada selects Canadian gate plus global controls;
- EU personal-data use selects `EU-DPIA`;
- U.K. public-sector algorithm use selects `UK-ATRS`;
- Singapore AI assurance request selects `SG-AIVF`;
- advanced generative-AI use selects `G7-HAIP-COC`.

### P1: GOV-AI-XPACK Generator

Generate a government-grade evidence packet for any work order.

Acceptance tests:

- missing evidence is explicit;
- unsupported claims are blocked;
- packet includes human oversight, transparency, privacy, security, and procurement sections.

## Next Safe Command

After review, the next safe implementation step is:

```powershell
python .\src\aigc.py validate
```

No push, deploy, live action, procurement purchase, account access, or government submission is authorized by this document.
