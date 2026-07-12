# AIGC Evolution and Procurement Cycle — Mainline CI Action SHA Pinning v1

**Cycle date:** 2026-07-12  
**Scope:** AIGC only  
**Base:** `main@293de53489fe7212fad272c01c698c0ffe2da610`  
**Branch:** `codex/ci-action-sha-pinning-main-v1`  
**Readiness-score impact:** `0.0`  
**External action performed by AIGC runtime:** `false`

## 1. Evolution Diagnosis

### Ontology health

AIGC correctly distinguishes evidence, authority, internal capability, external action, and production operation. One CI identity gap remained: movable action tags were used as executable dependency identities while AIGC's own evidence model increasingly requires exact revisions.

The corrected ontology separates:

- action repository identity;
- human-readable compatibility label;
- immutable action commit;
- locally approved action/revision pair;
- operator decision authority.

### Taxonomy completeness

The CI dependency taxonomy now adds:

- `THIRD_PARTY_GITHUB_ACTION`;
- `FULL_COMMIT_SHA`;
- `IMMUTABLE_REFERENCE`;
- `ALLOWLISTED_REVISION`;
- `BLOCKING_VALIDATION`;
- `SEPARATE_REVIEWED_UPDATE`.

### Methodology coherence

Exact source evidence and mutable CI dependencies were inconsistent. Pinning full commits extends AIGC's revision-identity methodology to the executable tooling that produces CI evidence.

### Architecture integrity

The current mainline workflow remains a single validation job. This cycle changes only dependency resolution. PR #69 remains the separate train for immutable-head and merge-candidate evidence lanes.

### Production-readiness gaps

AIGC remains non-production. Unchanged gaps include production identity, durable sessions, tenant isolation, operational recovery evidence, approved secrets and connectors, privacy operations, monitoring, accessibility verification, staging, and deployment authority.

### Governance stability

The change is isolated on a branch from exact current main. No main write, merge, deployment, credential use, connector execution, production operation, or readiness promotion occurs.

### Evolution bottlenecks

1. CI and operator disposition of this branch.
2. Operator disposition of PR #69.
3. PR #69 rebase or reconstruction preserving these pins after any mainline change.
4. Exact-main dual-revision verification.
5. Issue #66 lifecycle decisions.
6. Dependent PR revalidation.

### Dead logic

No new dead runtime logic is proven in this cycle.

### Redundant modules

No executable module is proven redundant. PR #69 and PR #71 retain overlapping procedure authority and require consolidation.

### Fragile structures

- movable third-party action tags;
- manual dependency updates;
- mutable hosted runner images;
- expiring artifacts;
- documentary PR dependencies;
- single-operator coordination load.

This cycle closes movable action tags on the mainline workflow branch.

## 2. Contender Arena

| Rank | Identity | Strategy | Strengths | Weaknesses | Evolutionary vector | Contribution |
|---:|---|---|---|---|---|---|
| 1 | Immutable Supply Chain | Pin actions to full commits and test an allowlist | Bounded, measurable, reversible | Manual updates | CI integrity | Selected |
| 2 | Controlled Update Bot | Propose reviewed SHA updates automatically | Reduces maintenance | More configuration and review load | Maintainability | Future companion |
| 3 | Dependency Manifest | Schema-register every CI dependency | Strong provenance | Additional contract surface | Evidence normalization | Future v+1 |
| 4 | GitHub-Owned Only | Restrict to first-party actions | Smaller vendor surface | Tags remain movable | Vendor minimization | Partial |
| 5 | Vendor Action Code | Commit action code locally | Maximum local control | High duplication and maintenance | Sovereignty | Rejected now |
| 6 | Tag with SHA Comment | Keep tags and document observed commits | Readable | Execution remains mutable | Cosmetic | Rejected |
| 7 | Freeze Dependencies | Never update pins | Stable short term | Security and compatibility decay | Static preservation | Rejected |
| 8 | Attestation Gate | Require upstream provenance for updates | Strong mature control | Too large for this cycle | Supply-chain maturity | Deferred |

Pressure testing selected full SHA pinning plus readable version comments and a fail-closed allowlist. A future dependency manifest and controlled update procedure can complete the synthesis.

## 3. Auto-Design Output

### Modules and interfaces

1. **Executable action allowlist** — action/revision pairs enforced by tests.
2. **Future CI dependency manifest** — schema-backed provenance, review, and rollback metadata.
3. **Future dependency update procedure** — tag resolution, upstream review, tests, operator decision.

```text
workflow uses entries
-> SHA validator
-> reviewed allowlist
-> full regression CI
-> operator review
```

### Ontology expansion

- a version label is descriptive;
- a commit SHA is executable identity;
- an allowlist is local policy;
- upstream publication is not local approval;
- CI success is not merge authority.

## 4. Auto-Engineer Output

### Implemented pipeline

```text
inspect current main workflow
-> resolve current major tags to exact commits
-> replace tags with full SHAs
-> preserve version comments
-> add full-SHA validation
-> add allowlist validation
-> run CI
```

### Approved action revisions

| Action | Label | Exact commit |
|---|---|---|
| `actions/checkout` | `v4` | `34e114876b0b11c390a56381ad16ebd13914f8d5` |
| `actions/setup-python` | `v5` | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/upload-artifact` | `v4` | `ea165f8d65b6e75b540449e92b4886f43607fa02` |

### Operational logic

- mutable ref: fail;
- unknown action: fail;
- changed SHA without allowlist update: fail;
- missing expected action: fail;
- approved exact action/revision: continue.

## 5. Auto-Architect Output

```text
Governance plane
  approved dependency policy
Evidence plane
  action allowlist + CI receipts
Control plane
  GitHub Actions workflow
Data plane
  repository + generated artifacts
```

Patterns:

- immutable dependencies;
- explicit allowlisting;
- least privilege;
- contract-first tests;
- expected-head merge protection;
- rollback by one revert;
- mainline-first sequencing before PR #69 revalidation.

## 6. Cognitive and Analytical Review

### Rationale

Current main used `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/upload-artifact@v4`. Those labels can move without an AIGC commit. Full pins make the executed action revision visible, reviewable, and reproducible.

### Assumptions

- resolved commits represented the referenced major tags at inspection time;
- GitHub supports full commit references;
- future updates receive separate review;
- PR #69 will preserve the pins after mainline movement.

### Tradeoffs

- reproducibility improves while maintenance becomes deliberate;
- a pinned commit can still contain defects;
- hosted runner images remain mutable;
- exact pins reduce one supply-chain path but do not create certification.

### Long-term stability

Stable operation requires periodic reviewed updates, upstream change inspection, rollback metadata, and later runner-image and dependency provenance controls.

## 7. 2026 Societal Logic Integration

### Regulation and privacy

No personal data is processed. The change supports accountability and reproducibility needed by future privacy and security governance.

### Security

Exact pins close a dependency substitution path. Existing content scanning, read-only permissions, approval boundaries, and the Security and Privacy Wiring Gate remain unchanged.

### Accessibility

No interface behavior changes. WCAG 2.2 Level AA remains the future operator-interface baseline.

### Organizational coordination

The operator currently consolidates maintainer, security, and release roles. The allowlist creates a clear review object but is not independent review.

### Deployment feasibility

No deployment capability is added. Production operation remains blocked.

### Platform constraints

- tags can move;
- full commits are immutable references;
- hosted runner images change;
- artifacts expire;
- upstream repositories and dependencies still require maintenance;
- CI evidence cannot grant release authority.

## 8. Final Synthesis

```text
exact application source
+ exact CI action dependencies
+ fail-closed allowlist
+ mandatory validation
+ operator-controlled merge
```

The metaphor is a **sealed forge chain**. The controls are full commit identities, tests, evidence, review, and rollback.

## 9. Single Highest-Impact Next Implementation Step

Pin all third-party actions in the current mainline workflow to reviewed full commit SHAs and enforce the set through a regression allowlist.

## 10. Procurement Success Packet

### Objective

Remove movable third-party action references from current-main CI.

### Scope

- three action references;
- one pinning regression test;
- one evolution and procurement record.

### Non-scope

No dual-revision workflow implementation, action major upgrade, runner change, runtime code, API/UI, database migration, credentials, connectors, deployment, or readiness promotion.

### Prerequisites

- exact current main;
- resolvable action revisions;
- GitHub Actions full-SHA support;
- separate branch;
- CI availability.

### Dependency and evidence check

- main is `293de53489fe7212fad272c01c698c0ffe2da610`;
- main contains three movable action references;
- PR #69 is draft and unmerged;
- Issue #66 is open;
- production readiness remains false.

### Affected ontology domains

CI supply chain, dependency identity, reproducibility, evidence provenance, governance.

### Affected taxonomy classes

`THIRD_PARTY_ACTION`, `IMMUTABLE_REFERENCE`, `ALLOWLISTED_REVISION`, `BLOCKING_GATE`, `REVIEWED_UPDATE`.

### Governing methodologies

Contract first, fail closed, least privilege, secure supply chain, bounded change, rollback, operator control.

### Architecture impact

CI dependency boundary only.

### Required schemas/contracts

No JSON schema in v1. The executable allowlist is the local contract. A future manifest should be schema-backed.

### Required config

`.github/workflows/aigc-ci.yml`

### Required core modules

None.

### Required CLI/API/UI wiring

None.

### Persistence requirements

Repository source and ordinary CI artifacts only.

### Security/privacy controls

Full pins, exact allowlist, read-only permissions, no secrets, no personal data, existing content scan, unchanged Security and Privacy Wiring Gate.

### Identity/authorization requirements

CI produces evidence only. The operator retains review and merge authority.

### Observability and audit requirements

Record action repository, compatibility label, exact commit, branch head, run identity, tests, artifact, operator decision, and rollback revision.

### Tests

- every external action uses a full SHA;
- observed action set equals the allowlist;
- every revision equals its approved commit;
- full repository tests remain green.

### CI gates

Contracts, AEC-001, content scan, procurement smoke stages, tests, readiness evaluation without promotion, and artifact upload.

### Rollback plan

Close the branch before merge or revert one bounded PR after merge; rerun exact-main CI. No data rollback.

### Migration plan

No data migration. After this PR changes main, PR #69 must rebase or be reconstructed and preserve these exact pins before fresh dual-revision evidence.

### Documentation/runbook

This file is the initial operating record. A future update procedure should add upstream-diff review and maintenance cadence.

### Ownership

| Function | Owner |
|---|---|
| Implementation | Repository operator |
| CI evidence | GitHub Actions |
| Security review | Operator; independent review not claimed |
| Merge decision | Justice Gray Maciocha, separately exercised |
| Deployment | Not authorized |

### Sequencing

```text
inspect
-> resolve exact commits
-> branch from main
-> pin actions
-> add tests
-> open draft PR
-> CI
-> operator review
-> separate merge decision
-> exact-main verification
-> revalidate PR #69
```

### Acceptance criteria

1. No movable external action ref remains.
2. Every external action ref is a lowercase 40-character SHA.
3. The action set equals the allowlist.
4. Every revision equals its approved value.
5. Full CI passes.
6. Readiness remains unchanged.
7. PR remains draft and operator controlled.
8. No authority boundary changes.
9. Rollback remains one revert.
10. PR #69 is not treated as valid after a main-base change until rerun.

### Definition of done

Branch-level completion requires implementation, tests, CI, and a draft PR. Mainline completion requires operator review, separate expected-head merge decision, and exact-main verification.

### Operator approvals

The bounded review branch and draft PR are within the requested cycle. Merge, deployment, credentials, connectors, and production operation remain outside the approval boundary.

### Blockers

- final CI evidence;
- operator review;
- separate merge decision;
- exact-main verification;
- PR #69 revalidation after main changes.

### Risk register

| Risk | Consequence | Control | State |
|---|---|---|---|
| Tag substitution | unreviewed action code executes | full SHA | Closed on branch |
| Silent pin drift | dependency changes unnoticed | allowlist test | Closed on branch |
| Stale pin | missed fixes | controlled updates | Open |
| Defective pinned code | stable defect | review and rollback | Residual |
| Hosted runner drift | environment changes | future runner control | Open |
| PR #69 stale base | invalid integration evidence | mandatory rebase/rerun | Blocking after merge |
| Artifact expiry | evidence unavailable | regenerate | Open |

### Estimated readiness-score impact

`0.0`

### Exact separate branch/PR plan

- branch: `codex/ci-action-sha-pinning-main-v1`;
- base: `main@293de53489fe7212fad272c01c698c0ffe2da610`;
- title: `fix(ci): pin mainline actions to immutable SHAs`;
- state: draft and operator controlled;
- changed files: workflow, pinning test, cycle record;
- merge method: expected-head-protected squash only after separate approval;
- post-merge: exact-main CI, then PR #69 base/evidence refresh.

## 11. Workflow Procurement Procedure

```text
intake
-> evidence verification
-> scope lock
-> contract-first design
-> implementation plan
-> security/privacy wiring
-> tests
-> CI
-> operator review
-> merge decision
-> post-merge verification
-> readiness-ledger update
```

No stage implies the next stage's authority.

## 12. Engine Evolution v+1

Add a strict machine-readable CI dependency manifest containing action name, exact commit, compatibility label, upstream repository, review timestamp, change rationale, and rollback commit. The manifest must not auto-update or auto-merge dependencies.

## 13. Next-Run Directive

Inspect only:

1. final PR head and CI result;
2. action pin and allowlist agreement;
3. artifact generation;
4. operator decision state;
5. main revision movement;
6. resulting PR #69 revalidation requirement;
7. blocker, rollback, and readiness changes.

Do not begin deployment, connectors, credentials, production identity, or automated dependency mutation.

## Updated Prioritized Transformation Backlog

| Priority | Transformation | State |
|---:|---|---|
| 1 | Validate and disposition mainline action pinning | In progress |
| 2 | Operator disposition of PR #69 | Blocking |
| 3 | Rebase and rerun PR #69 after any main change | Conditional blocking |
| 4 | Exact-main dual-revision verification | Waiting on #69 |
| 5 | Reconcile readiness through PR #70 | Draft/dependent |
| 6 | Resolve Issue #66 | Human decision required |
| 7 | Revalidate PRs #63–#65 and #72 | Waiting on upstream gates |
| 8 | Add CI dependency manifest | Proposed |
| 9 | Consolidate PR #71 overlap | Proposed |

## Updated Procurement Register

| Procurement | State |
|---|---|
| Mainline CI action pins | Branch implementation; CI pending |
| Dual-revision evidence gate | PR #69 draft; existing evidence valid only against current base |
| Honest single-snapshot engine | PR #72 draft; CI green |
| Persistence readiness reconciliation | PR #70 draft/dependent |
| Lifecycle semantics | Issue #66 open |
| Durable receipt API | PR #63 draft/dependent |
| Governed job kernel | PR #64 draft/semantic dependency |

## Updated Governance Summary

AIGC remains local, non-production, contract first, fail closed, rollback capable, and operator controlled. This cycle adds no runtime authority. It hardens the mainline CI supply chain through exact action identities while preserving every external-action and production-readiness block.
