# AIGC Canadian AI Procurement Alignment

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Purpose

This document adopts Canadian public-sector AI procurement and responsible-AI patterns as an AIGC governance layer.

It does not claim that AIGC is approved by the Government of Canada, listed as a supplier, compliant with every Canadian public-sector requirement, or ready for government contracting. It defines the controls AIGC should satisfy before it is positioned for Canadian public-sector AI work, government-adjacent work, or buyer environments that want Canadian public-sector discipline.

## Official Canadian Source Ledger

Use these sources as the current alignment basis:

- Public Services and Procurement Canada, Artificial Intelligence Source List.
- Treasury Board of Canada Secretariat, Directive on Automated Decision-Making and scope guidance.
- Treasury Board of Canada Secretariat, Algorithmic Impact Assessment tool.
- Treasury Board of Canada Secretariat, Guide on the Use of Generative AI.
- Treasury Board of Canada Secretariat, Responsible Use of Artificial Intelligence in Government.
- Treasury Board of Canada Secretariat, AI Strategy for the Federal Public Service 2025-2027.
- Innovation, Science and Economic Development Canada, Voluntary Code of Conduct on the Responsible Development and Management of Advanced Generative AI Systems.
- Innovation, Science and Economic Development Canada, Implementation Guide for Managers of Artificial Intelligence Systems.
- Canada's National Artificial Intelligence Strategy: AI for All.

## Adoption Doctrine

AIGC adopts Canadian AI procurement posture as:

```text
source-governed
impact-assessed
privacy-aware
security-reviewed
human-accountable
transparent
fairness-aware
environmentally conscious
procurement-evidence-ready
externally permissioned
```

The doctrine does not authorize live external action. It adds a Canadian public-sector readiness gate before any public-sector-facing AI proposal, deployment, integration, or live connector.

## Canadian Procurement Control Plane

### 1. AI Source-List Pattern

The PSPC AI source-list pattern means AIGC should be able to produce a supplier-style evidence packet before any public-sector AI pursuit.

Required AIGC records:

- product/service description;
- intended AI use cases;
- responsible-AI controls;
- privacy/security boundary;
- data residency and data-flow summary;
- model and tool inventory;
- human oversight model;
- quality assurance plan;
- accessibility and official-languages considerations where applicable;
- environmental impact notes;
- support and incident-response model;
- public-sector buyer limitations and assumptions.

### 2. Automated-Decision Scope Gate

Before AIGC supports a public-sector or government-adjacent workflow, it must classify whether the system:

- is used by or for a federal department or similar public-sector buyer;
- was developed, procured, or significantly modified for production use;
- supports an administrative decision;
- replaces or assists human judgment;
- is deployed or intended for production use.

If the answer suggests automated decision-making scope, the work must require:

- Algorithmic Impact Assessment;
- privacy review;
- security assessment;
- legal/policy review;
- human oversight;
- transparency plan;
- quality assurance;
- recourse plan;
- public reporting plan where applicable.

### 3. AIA-Lite Internal Record

AIGC should create an internal AIA-lite record before a full formal assessment is required.

Minimum fields:

- system name;
- purpose;
- affected people or organizations;
- decision or recommendation type;
- automation level;
- data categories;
- protected/classified/personal information status;
- model or algorithm family;
- human role;
- impact hypothesis;
- bias/fairness risks;
- privacy risks;
- security risks;
- transparency requirements;
- recourse requirements;
- mitigation list;
- residual risk;
- formal AIA required: yes/no/unknown;
- professional/government review required: yes/no/unknown.

### 4. FASTER Generative-AI Discipline

AIGC adopts the Treasury Board FASTER framing as a practical control mnemonic:

- Fair: assess bias, represent affected perspectives, and avoid discriminatory outcomes.
- Accountable: assign owners, record decisions, keep audit trails, and preserve human responsibility.
- Secure: protect personal, protected, classified, proprietary, and credential material.
- Transparent: disclose significant AI use and explain system role, limits, and outputs.
- Educated: require operator AI literacy, review of model limits, and training-aware use.
- Relevant: use AI only when it fits the purpose, public value, and environmental cost.

### 5. Voluntary Code Control Mapping

For advanced generative-AI capabilities, AIGC maps controls to:

- Safety;
- Accountability;
- Transparency;
- Fairness and Equity;
- Human Oversight and Monitoring;
- Validity and Robustness.

Each generated agent, workflow, and connector should declare which of these controls it satisfies and which remain open.

### 6. Privacy, Security, and Data Classification

Canadian procurement posture requires a default assumption that public-sector data may include sensitive, personal, protected, classified, proprietary, or regulated information.

AIGC must therefore require:

- data classification before processing;
- no raw secrets in Git;
- no personal/protected/classified information in public model prompts unless explicitly approved and tool-appropriate;
- retention limits;
- audit logs that avoid secret and personal-data leakage;
- Canadian/public-sector data-residency consideration where required;
- incident-response path;
- approved secret store for any credential-bearing deployment.

### 7. Transparency, Recourse, and Human Accountability

For public-sector-facing use, AIGC must produce:

- plain-language AI use description;
- human oversight statement;
- limitations statement;
- quality and validation summary;
- decision-support disclaimer when applicable;
- recourse/escalation route when outputs affect rights, benefits, eligibility, access, or service outcomes.

AIGC must not present AI-generated recommendations as final administrative decisions unless a lawful, reviewed, and properly authorized decision process exists outside AIGC.

### 8. Environmental and Sovereign-Compute Awareness

AIGC should track:

- compute cost;
- energy/carbon consideration;
- hosting region;
- provider sustainability posture;
- sovereign compute/data governance requirements;
- whether a lower-compute method can meet the same need.

This aligns with Canadian guidance that AI procurement should consider environmental impact and with national strategy signals around sovereign compute under Canadian governance.

## Public-Sector Work Order Gate

Any work order involving a Canadian public-sector buyer, government-adjacent service, public benefit, regulated public service, or administrative-decision support must include:

```text
canadian_ai_procurement_gate:
  source_list_relevance:
  automated_decision_scope:
  aia_lite_required:
  privacy_review_required:
  security_review_required:
  legal_policy_review_required:
  transparency_required:
  recourse_required:
  official_languages_consideration:
  accessibility_consideration:
  environmental_impact_consideration:
  data_residency_consideration:
  human_oversight_owner:
  public_sector_buyer_evidence_packet:
  external_action_allowed: false
```

## Evidence Packet Standard

AIGC should generate a Canadian AI procurement evidence packet containing:

1. Executive summary.
2. Buyer/use-case scope.
3. AI capability inventory.
4. Data classification.
5. Automated-decision scope analysis.
6. AIA-lite record.
7. Privacy and security controls.
8. Human oversight and monitoring plan.
9. Fairness/bias risk review.
10. Transparency and public-disclosure plan.
11. Recourse/escalation plan.
12. Validation and robustness evidence.
13. Prompt-injection and excessive-agency test results.
14. Supply-chain and SBOM note.
15. Environmental and hosting note.
16. Incident-response plan.
17. Limitations and buyer responsibilities.
18. External-action permit status.

## Forbidden Canadian Procurement Claims

AIGC must not claim:

- Government of Canada supplier approval;
- PSPC source-list membership;
- formal AIA completion;
- legal compliance certification;
- privacy-law compliance certification;
- security authorization;
- production authority;
- data-residency satisfaction;
- Canadian sovereign-compute compliance;
- public-sector deployment readiness;

unless those claims are evidenced by current, reviewed, authoritative records.

## Implementation Backlog

### P0: Canadian AI Procurement Gate Schema

Create:

- `schemas/canadian_ai_procurement_gate.schema.json`
- `src/core/canadian_ai_procurement.py`
- `tests/test_canadian_ai_procurement_gate.py`

Acceptance tests:

- government-adjacent work orders require the gate;
- administrative-decision scope sets formal review requirement;
- external action defaults to false;
- unsupported compliance claims fail validation.

### P0: AIA-Lite Record

Create:

- `schemas/aia_lite_record.schema.json`
- AIGC CLI command to generate local AIA-lite drafts.

Acceptance tests:

- all required risk categories are present;
- unknown scope blocks public-sector readiness;
- generated record contains no secret values.

### P1: Procurement Evidence Packet

Create:

- `reports/procurement/canadian_ai_procurement_packet_template.md`
- a packet generator linked to work orders.

Acceptance tests:

- packet includes privacy/security/transparency/recourse/oversight sections;
- packet states what is not yet approved;
- packet cannot imply supplier listing or deployment approval.

### P1: FASTER and Voluntary Code Mapping

Add:

- control mappings for FASTER;
- control mappings for Safety, Accountability, Transparency, Fairness and Equity, Human Oversight and Monitoring, Validity and Robustness.

Acceptance tests:

- every AI capability maps to at least one control;
- unmanaged controls produce a blocker.

## Operating Summary

Canadian government AI procurement discipline strengthens AIGC by forcing it to become:

- more transparent;
- more evidence-based;
- more privacy-aware;
- more accountable;
- more reviewable;
- more suitable for public-sector-grade buyers.

The practical adoption rule:

```text
No Canadian public-sector-facing AI work proceeds past internal draft status
until the Canadian AI procurement gate exists, validates, and records
human/professional review requirements.
```
