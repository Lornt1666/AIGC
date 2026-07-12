# AIGC Job Lifecycle Transformation Backlog and Procurement Register v1

Status: **Draft / evidence-bound / operator-controlled**  
Register ID: `AIGC-JOB-LIFECYCLE-PROCUREMENT-REGISTER-001`  
Parent program: GitHub Issue `#55`  
Lifecycle PR: GitHub PR `#65`  
External action performed: `false`

## 1. Purpose

This register is the durable coordination record for AIGC job-lifecycle evolution. It separates verified capability state from planned work, records blocking dependencies, and prevents later implementation trains from bypassing contract, security, privacy, review, and rollback gates.

This file is not a readiness receipt and does not authorize merge, deployment, credentials, connectors, production identity, client communication, or external execution.

## 2. Evidence snapshot

| Evidence | Recorded state |
|---|---|
| Current verified base for PR `#65` | `293de53489fe7212fad272c01c698c0ffe2da610` |
| Exact-head CI correction | PR `#53`, open pending operator disposition |
| Persistent authorization-receipt API | PR `#63`, draft pending review and exact-head evidence |
| Governed job-state kernel | PR `#64`, draft pending lifecycle reconciliation |
| Canonical lifecycle reconciliation | PR `#65`, draft |
| Production identity | Blocking / not implemented |
| External connector execution | Blocking / not implemented |
| Public production deployment | Blocking / not authorized |
| Readiness promotion from lifecycle contract | `0` points authorized |

The record must be refreshed whenever a referenced PR head, merge state, CI result, or readiness declaration changes.

## 3. Canonical capability decomposition

The previous broad concept of governed work is decomposed into independently evidenced capabilities:

1. `LEGACY_WORK_PREPARATION` — prepares packets and review artifacts; not a durable canonical lifecycle.
2. `CANONICAL_JOB_LIFECYCLE_CONTRACT` — defines versioned states, transitions, authority, and compatibility.
3. `GOVERNED_JOB_STATE_MACHINE` — calculates legal transitions against the canonical contract.
4. `DURABLE_JOB_ORCHESTRATION` — atomically verifies authority, persists job revision, records audit, and handles idempotency.
5. `LOCAL_OPERATOR_WORKFLOW` — exposes accessible Run/Review/Accept controls without external execution.
6. `CONNECTOR_PROPOSAL_EXECUTION_GATEWAY` — separates approved proposals from externally consequential execution.
7. `PRODUCTION_IDENTITY_AND_DEPLOYMENT` — production authentication, sessions, isolation, recovery, monitoring, and authorization.

No capability inherits completion from another capability merely because files exist.

## 4. Prioritized transformation backlog

| Priority | Transformation | Current status | Principal blocker | Exit evidence |
|---:|---|---|---|---|
| `P0` | Exact-head CI evidence on review path | Open PR `#53` | Operator disposition | Immutable head equals checkout, readiness source revision, and artifact name |
| `P0` | Canonical job-lifecycle semantic resolution | Draft PR `#65` | Operator decisions on acceptance and rework | Zero unresolved blocking semantic conflicts |
| `P1` | Correct or classify PR `#64` | Blocked | PR `#65` ratification | State machine consumes or maps to canonical contract |
| `P1` | Review persistent receipt API PR `#63` | Reviewable but blocked | Exact-head evidence and operator review | Restart/replay tests and exact-head CI |
| `P1` | Reconcile readiness ledger | Not started | Merged evidence inventory | Separate reviewed readiness PR with capability decomposition |
| `P2` | Durable atomic job application service | Planned | PRs `#53`, `#63`, `#64`, and `#65` disposition | Atomic job/audit/idempotency transaction and restart tests |
| `P3` | Local Run/Review/Accept API | Planned | Durable application service | Contract-valid routes with no external action |
| `P3` | Accessible operator interface | Planned | Stable API and lifecycle semantics | WCAG 2.2 AA-oriented tests and operator acceptance |
| `P4` | Connector proposal/execution gateway | Planned and blocked | Security/privacy, identity, platform approvals | Dry-run, scopes, revocation, outbox, and execution receipts |
| `P5` | Production identity, staging, recovery, deployment | Blocking | All prior trains | Staging evidence, recovery drill, monitoring, and explicit deployment authorization |

## 5. Procurement register

| Procurement ID | Capability | Branch / PR | Status | Dependencies | Readiness impact |
|---|---|---|---|---|---:|
| `CI_EXACT_REVISION_EVIDENCE_V1` | Exact-head assurance | PR `#53` | Implemented in open PR; unmerged | Operator review | No automatic score change |
| `PERSISTENT_AUTHORIZATION_RECEIPTS_API_V1` | Restart-safe receipt retrieval | PR `#63` | Draft | PR `#53`, operator review | No score change before merge/evidence |
| `GOVERNED_JOB_STATE_MACHINE_V1` | Pure job transition kernel | PR `#64` | Draft | PR `#65` semantic disposition | No score change before merge/evidence |
| `AIGC-CANONICAL-JOB-LIFECYCLE-CONTRACT-V1` | Canonical lifecycle and compatibility | PR `#65` | Draft | Operator semantic decisions; exact-head evidence | Immediate impact `0` |
| `AIGC-JOB-LIFECYCLE-SEMANTIC-RESOLUTION-V1` | Resolve acceptance and rework findings | PR `#65` | Active procedure | Operator decision issue | Immediate impact `0` |
| `DURABLE_JOB_APPLICATION_SERVICE_V1` | Authorized atomic transitions | Future branch | Blocked | Merged and verified prerequisite trains | Estimated only after evidence model review |
| `LOCAL_RUN_REVIEW_ACCEPT_UI_V1` | Operator workflow | Future branch | Blocked | Durable application service | Not estimated |
| `CONNECTOR_PROPOSAL_EXECUTION_GATEWAY_V1` | External action governance | Future branch | Blocked | Production identity, security/privacy, platform approval | Not estimated |

## 6. Current semantic findings

### `GENERIC_ACCEPTED_SEMANTIC_COLLISION`

Severity: `BLOCKING`

- Architecture-program `ACCEPTED`: work commitment before research.
- PR `#64` `ACCEPTED`: reviewed work accepted before delivery.
- Proposed canonical resolution: `WORK_ACCEPTED` and `ACCEPTED_FOR_DELIVERY`.
- Required authority: accountable operator ratification.

### `PR64_REWORK_EDGE_COMPRESSION`

Severity: `MATERIAL`

- PR `#64`: review can return directly to research.
- Proposed canonical contract: review records `REWORK_REQUIRED` before selecting the next execution stage.
- Required authority: operator chooses explicit canonical rework or formal compressed sub-lifecycle classification.

These findings remain unresolved until an attributable operator decision is recorded. Automated analysis is advisory only.

## 7. Capability-state rules

Use only the following evidence-bound states:

- `UNASSESSED`;
- `PLANNED`;
- `CONTRACTED`;
- `IMPLEMENTED_INTERNAL`;
- `INTEGRATED_INTERNAL`;
- `STAGING_OBSERVED`;
- `PRODUCTION_OBSERVED`;
- `BLOCKED`;
- `SUPERSEDED`.

Rules:

1. A PR does not advance a capability merely by existing.
2. `IMPLEMENTED_INTERNAL` requires working code and tests on a reviewable exact head.
3. `INTEGRATED_INTERNAL` requires merged exact-main evidence across runtime boundaries.
4. `STAGING_OBSERVED` and `PRODUCTION_OBSERVED` require actual environment evidence.
5. Contract-only work may be `CONTRACTED`; it may not be described as runtime capability.
6. Any unresolved critical authority, privacy, security, or compatibility finding makes the affected capability `BLOCKED`.

## 8. Required sequence for every procurement

```text
intake
→ evidence verification
→ scope lock
→ contract-first design
→ implementation plan
→ security/privacy wiring
→ tests
→ CI
→ operator review
→ merge decision
→ post-merge verification
→ readiness-ledger update
```

The detailed procedure is:

`docs/governance/procedures/AIGC_JOB_LIFECYCLE_CONTRACT_RECONCILIATION_PROCEDURE_V1.md`

## 9. Ownership and approvals

| Decision | Accountable authority |
|---|---|
| Canonical lifecycle meaning | Accountable operator |
| Compatibility mapping acceptance | Accountable operator |
| PR head review | Accountable operator |
| Merge decision | Accountable operator |
| Independent review claim | Only a distinct qualified reviewer |
| Production deployment | Not granted |
| External connector execution | Not granted |

Implementation automation cannot approve or merge its own work.

## 10. Risk register

| Risk | Severity | Control | State |
|---|---:|---|---|
| Wrong acceptance meaning becomes durable | Critical | Distinct semantic states and operator ratification | Open |
| Counterparty acceptance is fabricated | Critical | Separate counterparty evidence class | Controlled by contract |
| PR `#64` diverges from canonical contract | High | Compatibility map and separate correction PR | Open |
| Synthetic merge SHA is mistaken for exact-head proof | High | PR `#53` exact-head gate | Open |
| Job update succeeds while audit fails | Critical | Future atomic unit of work | Future blocker |
| Legacy work order is mistaken for canonical lifecycle | High | Explicit capability decomposition | Controlled by register |
| Readiness is inflated by file presence | High | Evidence-bound capability-state rules | Open |
| UI presents ambiguous Accept control | High | Semantic command labels | Future control |
| External action occurs from internal transition | Critical | Separate connector gateway and receipt | Blocked by design |
| Sensitive content enters audit evidence | High | Minimum-necessary identifiers and digests | Future control |

## 11. Governance summary

```text
AIGC-only scope: preserved
Direct write to main: prohibited
Self-approval: prohibited
Automatic merge: prohibited
Deployment: prohibited
Credential use: prohibited
External connector execution: prohibited
Production identity: blocked
Production data: prohibited
Rollback: required
Exact-head CI: required
Security & Privacy Wiring Gate: mandatory
Operator control: required
```

## 12. Register update procedure

Update this register only when repository evidence changes.

For each update:

1. record current `main` and affected PR heads;
2. state what changed and what did not change;
3. update only evidence-supported capability states;
4. preserve unresolved blockers;
5. identify the next single bounded train;
6. run CI on the updated branch;
7. record the change in Issue `#55`;
8. do not promote readiness without a separate reviewed ledger change.

## 13. Next authorized train

The next authorized action is limited to operator-reviewed semantic resolution on PR `#65`.

Do not begin durable job orchestration, API/UI job controls, connector work, production identity, or deployment until:

- PR `#65` has zero blocking semantic conflicts;
- exact-head assurance exists;
- PR `#64` is corrected or formally classified;
- required prerequisites are merged and exact-main verified.

`external_action_performed: false`
