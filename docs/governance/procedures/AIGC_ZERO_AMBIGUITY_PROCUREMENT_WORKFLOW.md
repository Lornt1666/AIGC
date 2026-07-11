# AIGC Zero-Ambiguity Procurement Control Workflow

**Document ID:** PROCUREMENT-001  
**Status:** Proposed procedure  
**Scope:** Software, agents, reviewers, connectors, infrastructure, services, vendors, data, and professional assessments

## Governing rule

No requirement enters acquisition execution until scope, evidence, authority, risk, dependencies, acceptance criteria, rollback, and post-procurement verification are explicit.

## Phase 1 — Requirement Definition

Every procurement begins with a `ProcurementRequirement` containing:

- stable ID and accountable owner;
- users, beneficiaries, and stakeholders;
- problem statement and operational need;
- rationale, scope, exclusions, and prohibited outcomes;
- functional and non-functional requirements;
- sensitivity, jurisdiction, constraints, assumptions, and dependencies;
- measurable acceptance criteria and success metrics;
- time, budget, and resource boundaries where applicable;
- rollback or exit boundary;
- evidence required for completion.

Decision: `REQUIREMENT_DEFINED` or `CLARIFICATION_REQUIRED`.

## Phase 2 — Procedural Verification

Evaluate alignment with:

- AEC-001 and the governance hierarchy;
- EIAP assurance contracts and Sensorium findings;
- Security & Privacy Wiring Gate;
- identity, authorization, and separation of duties;
- security, privacy, retention, purpose, and jurisdiction;
- accessibility and public trust;
- architecture, contract, evidence, and readiness standards;
- licensing, intellectual property, supply chain, official APIs, and platform terms;
- operations, recovery, monitoring, and documentation requirements.

Decision:

- `VERIFIED`
- `VERIFIED_WITH_OBLIGATIONS`
- `REQUIRES_EXCEPTION`
- `NONCONFORMANT_BLOCKING`
- `INSUFFICIENT_EVIDENCE`

## Phase 3 — Authorization Pathing

Map requester, owner, technical steward, domain reviewers, financial/commitment approver, independent reviewer where required, acceptance authority, merger, deployer, publisher, purchaser, terminator, escalation path, expiry, revocation, and revalidation.

Approvals bind to exact scope, revision, policy version, counterparty/amount where relevant, and expiry. Link possession grants no authority. Author and independent reviewer remain distinct.

## Phase 4 — Acquisition Execution

Evaluate and justify one pathway:

1. internal implementation;
2. reuse or consolidation;
3. open-source adoption;
4. official API or managed service;
5. commercial vendor;
6. independent professional/reviewer;
7. research/prototype engagement;
8. defer or reject.

Candidates are evaluated for fit, evidence, security, privacy, accessibility, interoperability, maintainability, licensing, lifecycle cost, support, maturity, recovery, concentration risk, lock-in, exit cost, and references. Blocking failures cannot be averaged away.

Before execution, produce the selected pathway, alternatives, implementation contract or statement of work, deliverables, tests, milestones, ownership, authorization, confidentiality/data handling, access plan, migration, rollback, communications, escalation, and evidence package.

Repository work follows:

```text
separate branch
→ contracts/schemas first
→ bounded implementation
→ positive/negative tests
→ CI
→ review packet
→ independent review where required
→ operator-controlled merge
→ post-merge verification
```

## Phase 5 — Post-Procurement Assessment

Verify deliverables, criteria, obligations, evidence binding, security/privacy/accessibility gates, documentation, ownership, rollback, costs, and truthful maturity claims.

Outcome:

- `ACCEPTED`
- `ACCEPTED_WITH_REMEDIATION`
- `REJECTED`
- `ROLLED_BACK`
- `TERMINATED`
- `OBSERVATION_PERIOD`

Record delivered revision/capability, planned versus actual cost/time, test results, defects, evidence maturity, readiness delta, risks, decisions, access continuation/revocation, lessons, next review, and renewal/replacement/retirement criteria.

## Procurement state machine

```text
REQUESTED
→ CLARIFICATION_REQUIRED | REQUIREMENT_DEFINED
→ PROCEDURAL_VERIFICATION
→ VERIFIED | VERIFIED_WITH_OBLIGATIONS | BLOCKED
→ AUTHORIZATION_PATHED
→ AUTHORIZATION_BLOCKED | ACQUISITION_AUTHORIZED
→ SOURCING
→ CANDIDATE_SELECTED
→ EXECUTING
→ DELIVERED
→ ACCEPTANCE_ASSESSMENT
→ ACCEPTED | ACCEPTED_WITH_REMEDIATION | REJECTED | ROLLED_BACK
→ OPERATING
→ REVIEWED
→ RENEWED | REPLACED | RETIRED
```

Every transition emits a revision- or transaction-bound receipt.

## Procurement Coordinator

A future bounded coordinator validates completeness, maps authority, compares candidates, calculates gate-aware scores, creates acquisition/acceptance packets, detects stale approvals, feeds EIAP and the Sensorium, and updates readiness. It remains advisory and cannot purchase, sign, contact, merge, deploy, publish, or use credentials without explicit approved execution pathways.

## Current AIGC application

The current dependent implementation train remains blocked until PR #29 receives legitimate independent review. The immediate authorized procurement is reviewer recruitment, consent, least-privilege access, exact-head review, gate revalidation, and operator-controlled merge.

## Definition of done

This workflow is operational when one bounded requirement completes all five phases with valid receipts, preserved human authority, fail-closed behavior, acceptance assessment, and a truthful readiness update.
