# AIGC Universal Procurement & Execution Protocol

**Document ID:** UPEP-001  
**Status:** Proposed canonical lifecycle  
**Scope:** All AIGC acquisitions, implementations, reviews, deployments, operations, evolution, and retirement

## Prime directive

No phase may be skipped. No downstream phase may compensate for an incomplete upstream phase. Every transition must produce attributable, revision- or transaction-bound evidence. Missing evidence, authority, scope, or rollback fails closed.

## Canonical lifecycle

```text
INTENT
→ REQUIREMENT_DEFINITION
→ PROCEDURAL_VERIFICATION
→ AUTHORIZATION_PATHING
→ ACQUISITION_STRATEGY
→ IMPLEMENTATION
→ VERIFICATION
→ VALIDATION
→ ACCEPTANCE
→ DEPLOYMENT
→ OBSERVATION
→ EVOLUTION
→ RETIREMENT
```

## Phase 0 — Engineering Intent Engine

Every proposed action begins by defining the desired outcome, affected users, urgency, existing capability fit, alternatives, constitutional applicability, measurable value, cost of action/inaction, risks, unknowns, reversibility, and evidence needed to proceed.

Decision:

- `PROCEED_TO_REQUIREMENTS`
- `REUSE_EXISTING_CAPABILITY`
- `CONSOLIDATE_EXISTING_CAPABILITIES`
- `DEFER`
- `REJECT_NONCONFORMANT`
- `INSUFFICIENT_EVIDENCE`

## Phase 1 — Requirement Definition

Create a bounded, testable requirement with owner, users, scope, exclusions, functional/non-functional requirements, sensitivity, jurisdiction, dependencies, assumptions, constraints, prohibited outcomes, acceptance criteria, metrics, resource limits, rollback, and completion evidence.

## Phase 2 — Procedural Verification

Evaluate AEC-001, EIAP, Sensorium, Security & Privacy Wiring Gate, identity/authorization, security, privacy, accessibility, architecture, contracts, licensing, supply chain, platform terms, recovery, monitoring, evidence, and readiness.

## Phase 3 — Authorization Pathing

Map request, ownership, stewardship, domain review, expenditure/commitment authority, independent review, acceptance, merge, deployment, publication, purchase, termination, escalation, expiry, revocation, and revalidation.

## Phase 4 — Acquisition Strategy

Compare internal build, reuse/consolidation, open source, official API, managed service, vendor, professional reviewer, prototype, defer, or reject. Blocking failures override weighted scores.

## Phase 5 — Implementation

```text
separate reviewed branch
→ contracts and schemas first
→ architecture and adapters
→ implementation
→ positive and negative tests
→ documentation and evidence
→ Review Packet Generator
→ advisory assurance review
→ independent human review where required
→ operator-controlled merge
```

## Phase 6 — Verification

Machine verification may include schema/contract validation, static/type/quality checks, tests, regression, mutation/fuzz testing where justified, secret/dependency scanning, accessibility structure, provenance, migration/rollback tests, Sensorium health, readiness, and traceability receipts.

Verification proves conformance. It does not prove that the original problem was solved.

## Phase 7 — Validation

Validate the delivered capability against original intent, affected users, real workflow, and acceptance outcomes.

Decision:

- `VALIDATED`
- `PARTIALLY_VALIDATED`
- `VALIDATION_FAILED`
- `OBSERVATION_REQUIRED`

## Phase 8 — Acceptance

Acceptance requires satisfied deliverables, resolved/carried obligations, exact evidence binding, documentation, ownership, rollback, required reviews, operator authority, and truthful maturity claims.

## Phase 9 — Deployment

Deployment requires separate authorization for exact revision/environment, identity/secrets, isolation, monitoring, alerts, SLOs where applicable, backup/restore, recovery, rollback, health checks, and post-deployment verification.

## Phase 10 — Observation

Observe reliability, performance, errors, security, privacy, accessibility, user outcomes, costs, dependency/policy/evidence/documentation drift, incidents, reviewer feedback, and unresolved assumptions while minimizing sensitive data.

## Phase 11 — Evolution

Evolution must change measurable evidence, capability status, readiness, defects, latency, accessibility, maintainability, risk, or governance maturity. Language generation alone is not progress.

## Phase 12 — Retirement

```text
ACTIVE
→ DEPRECATED
→ SUPERSEDED
→ ARCHIVED
→ REMOVED
```

Retirement requires dependency analysis, migration/communication, retention/disposal, access revocation, evidence preservation, rollback contingency, and readiness update.

## Machine contracts

Planned contracts include Engineering Intent, Requirement, Procedural Verification, Authorization Path, Acquisition Strategy, Implementation Plan, Verification Receipt, Validation Assessment, Acceptance Receipt, Deployment Authorization, Observation Record, Evolution Cycle, Retirement Plan, and Lifecycle Receipt.

All contracts reuse EIAP shared primitives for actors, artifacts, evidence, decisions, approvals, gates, and traceability.

## Universal decision questions

Every lifecycle packet answers why, what, who, where, when, how, cost, risk, evidence, confidence, authority, expiry, dependencies, unknowns, rollback, recovery, exit, retirement, constitutional basis, standards, policies, procedures, and public/user explanation. Missing mandatory answers become findings.

## Knowledge graph

```text
Intent
→ Requirement
→ Alternatives
→ Decision
→ Implementation
→ Evidence
→ Review
→ Acceptance
→ Deployment
→ Observation
→ Outcome
→ Lessons
→ Best Practice
→ Future Intent
```

## Initial bounded implementation

After PR #29 and AEC-001 prerequisites, implement only the Engineering Intent, Requirement, Procedural Verification, Authorization Path, and Lifecycle Receipt schemas; a deterministic transition validator; local CLI simulation; plain-language/JSON output; and negative tests for skipped phases, stale approvals, missing rollback/evidence, and unauthorized acquisition.

## Definition of done

UPEP-001 reaches its first operational milestone when one bounded AIGC capability moves from Engineering Intent through post-procurement acceptance with valid receipts, fail-closed tests, generated evidence-bound documentation, preserved human authority, and a truthful readiness update.
