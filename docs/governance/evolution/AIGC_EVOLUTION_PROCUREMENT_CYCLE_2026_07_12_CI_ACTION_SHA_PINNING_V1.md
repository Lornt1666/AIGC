# AIGC Evolution and Procurement Cycle — CI Action SHA Pinning v1

**Cycle date:** 2026-07-12  
**Project scope:** AIGC only  
**Parent assurance train:** PR #69  
**Implementation branch:** `codex/ci-action-sha-pinning-v1`  
**Stacked base:** `codex/ci-dual-revision-evidence-gate-v2-current-main@5e814314eeb8a12f335d214e93a11ac6d8204c34`  
**Readiness-score impact:** `0.0`  
**External action performed by AIGC runtime:** `false`

## 1. Evolution Diagnosis

### Ontology health

AIGC has a strong separation between evidence, authority, implementation, integration, and production operation. The remaining CI supply-chain ontology gap was that a human-readable major tag such as `v4` was treated as though it were an immutable dependency identity. It is not. The corrected model separates:

- `ACTION_NAME` — repository identity;
- `HUMAN_VERSION_LABEL` — explanatory compatibility label;
- `IMMUTABLE_ACTION_REVISION` — exact reviewed commit SHA;
- `ACTION_ALLOWLIST_ENTRY` — locally reviewed action/revision pair.

### Taxonomy completeness

The CI dependency taxonomy now requires:

- source class: `THIRD_PARTY_GITHUB_ACTION`;
- reference class: `FULL_COMMIT_SHA`;
- mutability class: `IMMUTABLE_REFERENCE`;
- review class: `ALLOWLISTED_REVISION`;
- update class: `SEPARATE_REVIEWED_CHANGE`;
- failure criticality: `BLOCKING`.

### Methodology coherence

AIGC already requires exact repository revisions for its own evidence, but the workflow loaded third-party executable action code through movable major tags. That was methodologically inconsistent. The correction extends the same exact-revision principle to CI dependencies.

### Architecture integrity

The dual-revision architecture remains unchanged:

```text
immutable head lane
+ merge-candidate lane
+ mandatory evidence artifacts
+ read-only permissions
+ unpersisted checkout credentials
```

Only the dependency-resolution boundary changes from movable references to exact commits.

### Production-readiness gaps

This correction does not change the structural readiness score. AIGC remains non-production. Production identity, tenant isolation, durable sessions, approved connectors, recovery operations, privacy operations, monitoring, accessibility verification, staging, and deployment authority remain incomplete.

### Governance stability

Governance remains fail closed and operator controlled. The branch is stacked on PR #69 to avoid rewriting PR #69's reviewed head. It must not merge independently into `main` before PR #69 is resolved.

### Evolution bottlenecks

1. Operator disposition of PR #69.
2. Retargeting this stacked change to `main` after PR #69 is merged and exact-main verified.
3. Fresh dual-revision evidence after retargeting.
4. Operator disposition of this final immutable head.
5. Issue #66 semantic decisions.
6. Revalidation of dependent PRs #63, #64, #65, #70, and #72.

### Dead logic

No new executable dead logic was proven in this cycle.

### Redundant modules

No module is proven redundant enough to remove. Documentary overlap between PR #69 and PR #71 remains flagged for consolidation.

### Fragile structures

- movable action tags;
- manually maintained action revisions;
- no automated dependency-update review procedure;
- artifact retention expiry;
- documentary PR dependencies;
- single-operator coordination load.

This cycle closes the first item for the dual-revision workflow branch.

## 2. Contender Arena

| Rank | Identity | Strategy | Strengths | Weaknesses | Evolutionary vector | Contribution |
|---:|---|---|---|---|---|---|
| 1 | Immutable Supply Chain | Pin every third-party action to a full SHA and enforce an allowlist | Small, measurable, reversible, directly closes substitution risk | Manual updates required | CI integrity | Selected implementation |
| 2 | Dependabot Steward | Configure automated action-update PRs | Reduces maintenance burden | Requires additional policy and review configuration | Maintainability | Future companion |
| 3 | Trusted Publishing Only | Permit only GitHub-owned actions | Reduces vendor surface | Does not make tags immutable | Vendor minimization | Partial control |
| 4 | Local Action Mirror | Vendor action code into AIGC | Full local review and availability | High maintenance and duplication | Sovereignty | Rejected for current scale |
| 5 | Workflow Lockfile | Maintain a machine-readable action dependency manifest | Strong provenance and tooling potential | New schema and generator required | Evidence normalization | Future synthesis element |
| 6 | OIDC and Attestation Gate | Require provenance or attestations for action updates | Strong future assurance | Larger platform and policy surface | Supply-chain maturity | Deferred |
| 7 | Freeze CI Entirely | Prohibit all dependency updates | Maximum stability | Accumulates vulnerabilities and incompatibility | Static preservation | Rejected |
| 8 | Tag plus Digest Comment | Retain tags and document observed SHAs | Easy to read | Execution still follows mutable tag | Cosmetic assurance | Rejected |

### Pressure test and hybridization

The selected strategy combines exact SHA references, human-readable major-version comments, and a regression allowlist test. A later Dependabot or controlled update workflow can propose reviewed SHA changes without weakening immutability.

## 3. Auto-Design Output

### Proposed conceptual modules

1. **Action Dependency Allowlist**
   - maps each permitted action to one exact commit;
   - rejects unknown actions and changed revisions.

2. **Future Action Dependency Manifest**
   - records action name, commit, source tag, review date, updater, compatibility notes, and rollback revision.

3. **Future Update Procedure**
   - resolves a requested tag to an exact commit;
   - reviews upstream change notes and diff;
   - updates the allowlist and workflow in one PR;
   - requires CI and operator review.

### Interface

```text
workflow uses entries
    -> pinning regression test
    -> reviewed allowlist
    -> CI contract gate
    -> operator review
```

### Ontology expansion

- `VERSION_LABEL` is descriptive.
- `COMMIT_SHA` is executable identity.
- `ALLOWLIST` is local policy.
- `UPSTREAM_PUBLISHER` is not local authority.
- `CI_SUCCESS` is evidence, not release approval.

## 4. Auto-Engineer Output

### Implemented pipeline

```text
inspect workflow action references
-> resolve each current major tag to its exact commit
-> replace tags with full SHAs
-> retain version comments
-> add full-SHA validation
-> add exact allowlist validation
-> run CI
-> record evidence
```

### Implemented mechanisms

- full 40-character lowercase hexadecimal validation;
- reviewed action/revision allowlist;
- exact usage-count assertions;
- rejection of unknown external actions;
- rejection of silent revision changes.

### Approved revisions in this cycle

| Action | Compatibility label | Immutable revision |
|---|---|---|
| `actions/checkout` | `v4` | `34e114876b0b11c390a56381ad16ebd13914f8d5` |
| `actions/setup-python` | `v5` | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/upload-artifact` | `v4` | `ea165f8d65b6e75b540449e92b4886f43607fa02` |

## 5. Auto-Architect Output

### Macro-architecture

```text
Governance plane
    -> approved dependency policy
Evidence plane
    -> action dependency allowlist and CI receipts
Control plane
    -> GitHub Actions workflow
Data plane
    -> repository, reports, and artifacts
```

### Integration patterns

- immutable dependency references;
- explicit allowlists;
- least-privilege workflow permissions;
- revision-bound evidence;
- stacked PR sequencing;
- expected-head merge protection;
- rollback by one bounded revert.

### Cross-module coherence

The same revision-identity principle now governs both AIGC source evidence and the third-party action code that produces that evidence.

## 6. Cognitive and Analytical Review

### Rationale

PR #69 proves AIGC's immutable source and merge candidate, but its workflow used major tags for executable third-party action code. A tag owner can move a tag without changing AIGC. Pinning exact commits removes that substitution path.

### Assumptions

- the resolved upstream commits corresponded to the workflow's currently selected major tags at inspection time;
- GitHub continues to support full-SHA action references;
- the operator will review future SHA updates separately;
- the stacked branch will be retargeted only after PR #69 is resolved.

### Tradeoffs

- immutable pins improve reproducibility but require deliberate updates;
- an exact SHA does not itself prove upstream code quality;
- a local allowlist improves drift detection but must be maintained;
- stacking avoids mutating PR #69 but delays merge-candidate evidence for this PR until retargeting.

### Long-term stability

The stable end state is exact pins plus a machine-readable dependency manifest, controlled update PRs, upstream-diff review, and regular patch cadence.

## 7. 2026 Societal Logic Integration

### Regulation and privacy

The change does not process personal data. It supports privacy and security accountability by making build dependencies reproducible and reviewable. Existing Alberta and Canadian privacy obligations remain relevant for future personal-data operation.

### Security

The correction addresses CI dependency substitution risk. Read-only permissions, unpersisted checkout credentials, content scanning, and the Security and Privacy Wiring Gate remain intact.

### Accessibility

No user-interface behavior changes. WCAG 2.2 Level AA remains the engineering baseline for future operator surfaces.

### Organizational coordination

One operator currently performs maintainer, security, and release coordination. The action allowlist creates a concrete review surface but does not constitute independent review.

### Deployment feasibility

No deployment capability is added. Production operation remains blocked.

### Platform constraints

- action tags may move;
- exact SHAs are immutable references;
- upstream repositories can still be archived or compromised before a reviewed update;
- GitHub-hosted runner images change over time;
- artifacts expire;
- stacked PRs require deliberate retargeting and revalidation.

## 8. Final Synthesis

The strongest synthesis is:

```text
exact AIGC source revision
+ exact merge-candidate revision
+ exact third-party action revisions
+ mandatory artifact delivery
+ reviewed allowlist
+ operator-controlled merge
```

The mythic metaphor is the **sealed forge chain**: every link has a concrete identity. The engineering controls are full commit SHAs, allowlist tests, read-only permissions, revision receipts, mandatory artifacts, and separate operator decisions.

## 9. Single Highest-Impact Next Implementation Step

**Selected:** pin all third-party actions used by the dual-revision workflow to reviewed full commit SHAs and add a fail-closed regression allowlist.

This is immediately implementable, repository aligned, security material, reversible, and does not expand runtime authority.

## 10. Procurement Success Packet

### Objective

Eliminate movable GitHub Action references from the dual-revision CI workflow.

### Scope

- pin `actions/checkout`, `actions/setup-python`, and `actions/upload-artifact`;
- update all six workflow uses sites;
- add full-SHA and exact-allowlist tests;
- record the bounded cycle.

### Non-scope

- action major-version upgrades;
- runner-image pinning;
- OIDC;
- deployment;
- runtime changes;
- database changes;
- credentials;
- connectors;
- readiness promotion;
- merge of PR #69.

### Prerequisites

- PR #69 final head `5e814314eeb8a12f335d214e93a11ac6d8204c34`;
- resolvable upstream action tags;
- GitHub Actions support for full SHAs;
- branch creation permission;
- CI availability.

### Dependency and evidence check

- current `main` remains `293de53489fe7212fad272c01c698c0ffe2da610`;
- PR #69 remains draft, open, mergeable, and unmerged;
- PR #69's workflow contains six movable major-tag references;
- Issue #66 remains open;
- no operator merge decision is recorded for PR #69.

### Affected ontology domains

- CI supply chain;
- dependency identity;
- evidence provenance;
- reproducibility;
- governance.

### Affected taxonomy classes

- `THIRD_PARTY_ACTION`;
- `IMMUTABLE_REFERENCE`;
- `ALLOWLISTED_DEPENDENCY`;
- `BLOCKING_VALIDATION`;
- `REVIEW_REQUIRED_UPDATE`.

### Governing methodologies

- secure software supply chain;
- contract-first validation;
- fail-closed controls;
- least privilege;
- bounded change;
- reversible delivery;
- operator-controlled release.

### Architecture impact

CI dependency-resolution hardening only. No application plane changes.

### Required schemas and contracts

No new JSON schema is required for v1. The regression allowlist is executable policy. A future manifest should receive a strict schema.

### Required configuration

`.github/workflows/aigc-ci.yml`

### Required core modules

None.

### Required CLI/API/UI wiring

None.

### Persistence requirements

Repository files and normal CI artifacts only.

### Security and privacy controls

- full immutable action references;
- exact allowlist;
- read-only repository permission;
- checkout credential persistence disabled;
- no secrets introduced;
- no personal data;
- content scanner remains mandatory.

### Identity and authorization requirements

CI remains an evidence producer. The operator remains the review and release authority. No production identity is activated.

### Observability and audit requirements

Record:

- upstream action repository;
- compatibility label;
- exact commit;
- AIGC branch head;
- workflow run;
- test conclusion;
- artifact name;
- retargeting state;
- operator decision state.

### Tests

- all external action references are full 40-character SHAs;
- every action is in the reviewed allowlist;
- each action matches its approved revision;
- expected use counts match the workflow;
- full AIGC regression suite.

### CI gates

- contract validation;
- AEC-001 validation;
- content scan;
- procurement smoke stages;
- full tests;
- readiness evaluation without promotion;
- artifact upload;
- dual-revision evidence after retargeting to `main`.

### Rollback plan

Before merge: close or abandon the branch.  
After merge: revert the bounded pinning PR and rerun exact-main CI.  
No data rollback is required.

### Migration plan

No data migration. Retarget the stacked PR to `main` only after PR #69 merges and exact-main verification succeeds.

### Documentation and runbook

This cycle file is the initial runbook. A future dependency-update procedure should formalize upstream diff review and scheduled maintenance.

### Ownership

| Responsibility | Owner |
|---|---|
| Branch implementation | Repository operator |
| CI evidence | GitHub Actions |
| Security review | Operator; independent review not claimed |
| Merge decision | Justice Gray Maciocha, separately exercised |
| Deployment | Not authorized |

### Sequencing

```text
inspect
-> resolve tags
-> create stacked branch
-> pin actions
-> add tests
-> run push CI
-> open draft stacked PR
-> await PR #69 disposition
-> retarget to main
-> run dual-revision CI
-> operator review
-> separate merge decision
-> exact-main verification
```

### Acceptance criteria

1. No movable third-party action ref remains in the workflow.
2. All refs are full lowercase 40-character SHAs.
3. The allowlist test passes.
4. Unknown actions fail.
5. Silent revision changes fail.
6. Workflow permissions remain read only.
7. Checkout credentials remain unpersisted.
8. Full CI passes on the final branch head.
9. The PR remains draft and operator controlled.
10. No readiness increase is claimed.
11. After retargeting, both dual-revision lanes pass.
12. Merge requires a separate expected-head decision.

### Definition of done

Branch-level completion requires implementation, tests, push CI, and a draft stacked PR. Mainline completion additionally requires PR #69 resolution, retargeting, dual-revision CI, operator review, merge decision, and exact-main verification.

### Operator approvals

The requested bounded evolution cycle permits a review branch and draft PR. It does not grant merge, deployment, credential, connector, or production-operation authority.

### Blockers

- PR #69 is unmerged;
- stacked PR cannot obtain its final `main` merge-candidate evidence yet;
- operator review is pending;
- exact-main verification is future work.

### Risk register

| Risk | Consequence | Control | State |
|---|---|---|---|
| Movable tag substitution | CI executes unreviewed code | full SHA pin | Closed on branch |
| Silent SHA change | allowlist drift | regression test | Closed on branch |
| Stale dependency | missed fixes | controlled update procedure | Open |
| Compromised pinned commit | persistent bad dependency | upstream review and rollback | Residual |
| Stacked PR merged out of order | invalid base assumptions | keep draft; retarget only after #69 | Blocking |
| Runner image drift | environmental variability | future runner strategy | Open |
| Artifact expiry | evidence loss | regenerate artifacts | Open |

### Estimated readiness-score impact

`0.0`

The change improves assurance integrity, not product capability maturity.

### Exact separate branch and PR plan

- repository: `Lornt1666/AIGC`;
- branch: `codex/ci-action-sha-pinning-v1`;
- starting revision: `5e814314eeb8a12f335d214e93a11ac6d8204c34`;
- initial PR base: `codex/ci-dual-revision-evidence-gate-v2-current-main`;
- title: `fix(ci): pin third-party actions to immutable SHAs`;
- state: draft and stacked;
- retarget condition: PR #69 merged and exact-main verified;
- eventual base: `main`;
- merge method: expected-head-protected squash only after final evidence and separate operator decision.

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

No stage grants the authority of the next stage.

## 12. Engine Evolution v+1

**Proposed bounded improvement:** add a machine-readable CI dependency manifest containing action name, exact commit, compatibility label, upstream repository, review timestamp, rollback revision, and change rationale.

The manifest should be schema validated and consumed by the pinning test. It must not automatically update workflow dependencies or merge changes.

## 13. Next-Run Directive

The next cycle shall inspect only:

1. final branch head and push CI conclusion;
2. creation and state of the stacked draft PR;
3. whether PR #69 has changed or received an operator decision;
4. whether retargeting is permitted;
5. whether all action references still match the allowlist;
6. changed blocker state, artifact evidence, and rollback state.

It shall not begin deployment, connectors, production identity, credentials, or true autonomous dependency updates.

## Updated Prioritized Transformation Backlog

| Priority | Transformation | State |
|---:|---|---|
| 1 | Operator disposition of PR #69 | Blocking |
| 2 | Retarget and dual-lane validate action pinning | Waiting on #69 |
| 3 | Exact-main verification of dual-revision gate | Waiting on #69 |
| 4 | Reconcile readiness through PR #70 | Draft and dependent |
| 5 | Resolve Issue #66 | Human decision required |
| 6 | Revalidate PRs #63–#65 and #72 | Waiting on upstream gates |
| 7 | Add CI dependency manifest | Proposed |
| 8 | Consolidate PR #71 procedure overlap | Proposed |

## Updated Procurement Register

| Procurement | State |
|---|---|
| Dual-revision evidence gate | PR #69 draft; CI green |
| Immutable CI action pins | Implemented on stacked branch; final evidence pending |
| Honest single-snapshot engine | PR #72 draft; CI green |
| Persistence readiness reconciliation | PR #70 draft and dependent |
| Lifecycle semantics | Issue #66 open |
| Durable authorization receipt API | PR #63 draft and dependent |
| Governed job-state kernel | PR #64 draft and semantically dependent |

## Updated Governance Summary

AIGC remains local, non-production, contract first, fail closed, rollback capable, and operator controlled. This cycle changes no runtime authority. It closes one concrete CI supply-chain fragility on a separate stacked branch while preserving the Security and Privacy Wiring Gate and all external-action blocks.
