# AIGC Dual-Revision Evidence Gate Procurement Procedure v2

**Document ID:** AIGC-PROC-CI-EVIDENCE-002  
**Status:** Proposed, operator-approved procedure procurement  
**Project scope:** AIGC only  
**Parent program:** Issue #55  
**Reference implementation:** PR #53  
**Independent semantic gate:** Issue #66  
**Procedure branch:** `codex/ci-dual-revision-evidence-gate-v2-procedure`  
**Procedure base:** `main@293de53489fe7212fad272c01c698c0ffe2da610`  
**Readiness-score change:** `0.0`  
**External action performed by AIGC runtime:** `false`

## 1. Purpose

This procedure governs one bounded procurement: rebuild AIGC's CI evidence boundary from the latest reviewed `main` so two different assurance questions are answered independently and truthfully.

1. **Immutable-head assurance** asks whether CI inspected the exact source revision the operator reviews.
2. **Merge-candidate assurance** asks whether that exact source revision integrates successfully with the current target branch.

Neither answer may substitute for the other. A passing immutable-head job does not prove current-base integration. A passing synthetic merge job does not prove that evidence was generated for the immutable PR head.

The procedure maps that distinction into contracts, workflow jobs, receipts, tests, review gates, rollback controls, and an operator-controlled merge decision.

## 2. Operator approval record

Justice Gray Maciocha approved repository update and instantiation of this bounded procedure on 2026-07-11 in the governing operator conversation.

The approval permits:

- creating this procedure on a separate branch;
- opening a draft review PR;
- preparing the future implementation plan;
- running CI against review branches;
- collecting non-sensitive repository and workflow evidence.

The approval does not permit:

- direct writes to `main`;
- self-approval;
- automatic merge;
- production deployment;
- credential use or disclosure;
- connector execution;
- external consequential action;
- readiness promotion without a separate evidence-backed decision;
- resolution of Issue #66 without explicit operator choices.

## 3. Evidence basis

At procedure instantiation:

- current `main` is `293de53489fe7212fad272c01c698c0ffe2da610`;
- current `main` contains the localhost operator API and transactional SQLite authority and audit persistence;
- current `main` still uses the default pull-request checkout and names readiness artifacts with `${{ github.sha }}`;
- PR #53 contains the only implemented exact-head correction;
- PR #53 head `9c7fecd057cf33f79e202e46a3e6bb83d7fa7e48` passed AIGC CI run 671 with matching selected revision, checkout revision, verifier receipt, readiness source revision, and artifact name;
- PR #53 diverged from current `main` and contains repository-state documentation that predates the merged API and storage trains;
- PRs #63, #64, and #65 have successful tests, but their readiness artifacts identify synthetic pull-request merge revisions rather than immutable heads;
- Issue #66 remains open and independently blocks canonical job-lifecycle ratification.

The resulting decisions are:

- retain PR #53 as reference evidence;
- do not merge PR #53 unchanged;
- reconstruct a clean replacement from the latest `main`;
- retain merge-readiness blocks on PRs #63, #64, and #65 until fresh dual-revision evidence exists;
- infer no production capability or readiness increase from this procedure.

## 4. Governing principles

### 4.1 Separate evidence subjects

Every receipt declares exactly one evidence subject:

- `IMMUTABLE_HEAD`; or
- `MERGE_CANDIDATE`.

A receipt shall not report both subjects as though they were one revision.

### 4.2 Evidence is not authority

CI may validate, measure, and report. CI may not approve, merge, deploy, ratify semantics, or authorize external action.

### 4.3 Fail closed

Missing, malformed, stale, ambiguous, mismatched, or unbound revisions are blocking failures. Revision-identity failures cannot be reduced to warnings.

### 4.4 Integration evidence is time-sensitive

Merge-candidate evidence is valid only for the recorded base revision, head revision, and resulting merge-candidate revision. Any base or head change invalidates the previous integration evidence.

### 4.5 Security and privacy remain intact

The replacement shall not use `pull_request_target`, repository write permissions, sensitive values, production data, persisted checkout credentials, live connectors, or privileged execution of untrusted PR code.

### 4.6 Operator control remains intact

The operator reviews the final immutable head and makes a separate expected-head-protected merge decision. Procedure approval does not equal merge approval.

## 5. Scope

### Included

- revision resolution for push and pull-request events;
- explicit immutable-head checkout;
- immutable-head verifier receipt;
- revision-bound readiness execution;
- merge-candidate checkout or deterministic construction;
- merge-candidate parent and identity verification;
- separate artifacts for each evidence subject;
- strict schemas and validation;
- positive, negative, stale-evidence, and workflow-wiring tests;
- read-only workflow permissions;
- rollback and post-merge verification;
- current-state documentation reconciliation;
- controlled supersession of PR #53.

### Excluded

- application runtime changes;
- Issue #66 semantic decisions;
- API or UI changes;
- database migration;
- production identity;
- connector enablement;
- credential access;
- deployment or public networking;
- external action;
- readiness capability promotion;
- unrelated CI modernization.

## 6. Roles and boundaries

| Role | Responsibility | Boundary |
|---|---|---|
| Accountable operator — Justice Gray Maciocha | scope decision, residual-risk decision, final-head review, merge decision | operator authority cannot be inferred from CI |
| Technical implementer | contracts, code, workflow, tests, documentation | may prepare reviewable changes; may not self-approve or merge |
| CI verifier | deterministic evidence generation and validation | advisory evidence only |
| Security and privacy reviewer | checks permission, data, and execution boundaries | may block; cannot merge |
| Independent reviewer when policy requires one | human technical review distinct from authorship | review authority only |
| Repository merger | executes an explicit expected-head-protected merge decision | gains no deployment authority |

## 7. Terminology

- **Head revision** means the immutable PR head or push revision.
- **Base revision** means the target-branch revision recorded for the pull-request event.
- **Merge-candidate revision** means the checked-out or constructed merge of the recorded base and head.
- **Selected revision** means the revision an evidence lane declares it will inspect.
- **Checked-out revision** means the result of `git rev-parse HEAD` in that lane.
- **Source revision** means the revision written into a readiness or evidence receipt.
- **Evidence bundle** means the receipts and artifacts from one workflow run, partitioned by evidence subject.
- **Stale evidence** means evidence whose recorded head or base no longer matches the current PR state.

## 8. Required contracts

Contract-first design precedes workflow implementation.

### 8.1 Immutable-head receipt

The receipt shall require:

- contract ID and version;
- receipt ID;
- repository identity;
- event name;
- evidence subject `IMMUTABLE_HEAD`;
- selected head revision;
- checked-out revision;
- readiness source revision;
- workflow run identity when available;
- verification state;
- failure reason when verification is false;
- operator review required `true`;
- external action performed `false`;
- creation timestamp.

Required invariant:

```text
selected_head_revision
= checked_out_revision
= readiness_source_revision
= immutable-head artifact revision
```

### 8.2 Merge-candidate receipt

The receipt shall require:

- contract ID and version;
- receipt ID;
- repository identity;
- event name `pull_request`;
- evidence subject `MERGE_CANDIDATE`;
- base revision;
- head revision;
- selected merge-candidate revision;
- checked-out merge-candidate revision;
- classified parent or input revisions;
- integration-test conclusion;
- verification state;
- failure reason when verification is false;
- operator review required `true`;
- external action performed `false`;
- creation timestamp.

Required invariants:

```text
selected_merge_candidate_revision
= checked_out_merge_candidate_revision
= merge-candidate artifact revision
```

and:

```text
recorded head revision is a verified parent or merge input
recorded base revision is a verified parent or merge input
```

### 8.3 Evidence-bundle manifest

The manifest shall bind:

- workflow run;
- immutable head;
- base revision;
- merge candidate;
- receipt paths;
- artifact names;
- test conclusions;
- schema conclusions;
- evidence freshness;
- operator-review requirement.

A pull-request bundle fails validation if either mandatory evidence lane is absent.

## 9. Workflow controls

The implementation shall preserve or add:

- top-level `contents: read` permission;
- `persist-credentials: false` for each checkout;
- full 40-character SHA validation;
- no `pull_request_target` event;
- no sensitive values passed to untrusted PR code;
- no repository write permission;
- no deployment environment;
- no connector invocation;
- no artifact name derived from an unverified revision;
- no readiness source revision assigned before checkout verification;
- deterministic failure when required event fields are unavailable.

Workflow expressions select candidate values. Repository code independently verifies those values and the actual checkout.

## 10. Binding execution order

```text
intake
→ evidence verification
→ scope lock
→ contract-first design
→ implementation plan
→ security and privacy wiring
→ implementation
→ tests
→ CI
→ operator review
→ merge decision
→ post-merge verification
→ readiness-ledger update
```

No phase may claim completion of a later phase.

## 11. Phase procedure

### Phase 1 — Intake

1. Record parent program Issue #55.
2. Record operator approval and limits.
3. Resolve the latest `main`; do not reuse this procedure's base without verification.
4. Record open PRs affected by revision assurance.
5. Mark PR #53 `REFERENCE_PENDING_SUPERSESSION`.
6. Record Issue #66 as an independent decision gate.

Exit state: `INTAKE_COMPLETE` or `INTAKE_BLOCKED`.

### Phase 2 — Evidence verification

1. Fetch current `main` and workflow.
2. Inspect PR #53 head, run, receipt, readiness revision, artifact, permissions, and tests.
3. Compare PR #53 with current `main`.
4. identify stale code or documentation assumptions.
5. Inspect heads and artifact revisions for PRs #63, #64, and #65.
6. Reject merge-readiness claims when artifact revision differs from immutable head.
7. Record changed evidence instead of copying historical claims.

Exit state: `EVIDENCE_VERIFIED`, `EVIDENCE_PARTIAL`, or `EVIDENCE_BLOCKED`.

### Phase 3 — Scope lock

Create the future implementation branch from the latest verified `main`:

```text
codex/ci-dual-revision-evidence-gate-v2-current-main
```

Lock implementation to:

- schemas;
- verifier modules and CLIs;
- CI workflow wiring;
- tests;
- exact-revision documentation.

Changes outside that set require a new scope decision.

Exit state: `SCOPE_LOCKED`.

### Phase 4 — Contract-first design

1. Define or revise the immutable-head schema.
2. Define the merge-candidate schema.
3. Define the evidence-bundle manifest schema.
4. Register contracts where repository conventions require it.
5. Add negative fixtures before workflow wiring.
6. Reject unknown fields where compatible with repository conventions.
7. Constrain revisions to full commit SHAs.
8. Constrain evidence-subject vocabulary.
9. Require truthful false states and failure reasons.

Exit state: `CONTRACTS_READY` only after schema tests pass.

### Phase 5 — Implementation planning

The plan shall enumerate:

- affected files;
- dependency direction;
- workflow graph;
- event handling;
- artifact paths and names;
- failure modes;
- test ownership;
- rollback;
- migration impact;
- operator review points.

No database migration is expected. CI artifacts are the persistence mechanism for this train.

Exit state: `IMPLEMENTATION_PLANNED`.

### Phase 6 — Security and privacy wiring

Before executing PR code:

1. Set workflow permissions to read-only.
2. Disable persisted checkout credentials.
3. Confirm no sensitive context is referenced.
4. Confirm `pull_request_target` is absent.
5. Confirm no privileged external action occurs.
6. Limit evidence artifacts to repository metadata and test results.
7. Run the repository content scanner.
8. Preserve the Security and Privacy Wiring Gate without exceptions.

Exit state: `SECURITY_PRIVACY_WIRED` or a blocking finding.

### Phase 7 — Immutable-head implementation

For pull requests:

1. Select `github.event.pull_request.head.sha`.
2. Validate a full commit SHA.
3. Checkout that SHA explicitly.
4. Disable persisted credentials.
5. Read actual `HEAD` independently.
6. Fail unless selected and actual revisions match.
7. Write and validate the immutable-head receipt.
8. Install dependencies.
9. Run contracts, AEC-001, content scanning, procurement smoke stages, tests, and revision-bound readiness.
10. Fail unless readiness source revision equals the verified head.
11. Upload an artifact named with the verified head.

Push events use the immutable push SHA in the same lane.

### Phase 8 — Merge-candidate implementation

For pull requests only:

1. Record event base and head revisions.
2. Select the GitHub merge candidate or construct a deterministic merge in an isolated job.
3. Checkout or construct it without write permissions or sensitive values.
4. Read actual `HEAD` independently.
5. Verify selected and actual merge-candidate revisions match.
6. Verify the recorded base and head are merge inputs or expected parents.
7. Write and validate the merge-candidate receipt.
8. Run contracts, AEC-001, content scanning, procurement smoke stages, and full tests.
9. Upload a separately named merge-candidate artifact.
10. Never write the merge-candidate revision into the immutable-head readiness receipt.

A base-branch change invalidates previous merge-candidate evidence.

### Phase 9 — Tests

Positive coverage shall include:

- matching selected and checked-out head revisions;
- revision-bound readiness source;
- valid head receipt;
- valid merge receipt;
- verified base and head inputs;
- valid bundle manifest;
- push-event handling;
- pull-request dual-lane wiring.

Negative coverage shall include:

- abbreviated or malformed revision;
- selected and checked-out mismatch;
- readiness revision mismatch;
- artifact-name mismatch;
- missing base or head;
- merge candidate missing a required input;
- stale base or head;
- missing mandatory lane;
- malformed receipt;
- unknown evidence subject;
- environment restoration failure;
- permission expansion;
- persisted checkout credentials;
- introduction of `pull_request_target`;
- sensitive-context reference.

Regression coverage shall include:

- API tests;
- SQLite migration, persistence, integrity, backup, and audit tests;
- identity and authority tests;
- full repository test suite.

### Phase 10 — CI gates

A pull request is not eligible for operator merge review until:

1. immutable-head lane passes on the final PR head;
2. merge-candidate lane passes against the current target revision;
3. mandatory tests pass;
4. contracts and AEC-001 validate;
5. content scanning passes;
6. Security and Privacy Wiring remains intact;
7. head receipt, readiness revision, and head artifact agree;
8. merge receipt and merge artifact agree;
9. bundle manifest validates;
10. evidence is current;
11. no blocking review thread remains.

A green check without valid receipts is insufficient.

### Phase 11 — Operator review

The review packet shall present:

- final immutable head;
- current base;
- merge candidate;
- receipt states;
- workflow permissions;
- changed files;
- test result;
- readiness result without unsupported promotion;
- unresolved findings;
- rollback;
- PR #53 comparison and disposition recommendation;
- residual risks.

Any new commit invalidates the previous final-head review.

### Phase 12 — Merge decision

Merge remains a separate operator decision.

When explicitly approved:

- use expected-head protection against the reviewed immutable head;
- use the repository-approved merge method;
- do not enable deployment;
- record the merge result;
- proceed to exact-main verification.

When not approved:

- leave the PR open for correction; or
- close it without merge and record the reason.

### Phase 13 — Post-merge verification

After merge:

1. Resolve the exact new `main` revision.
2. inspect CI bound to that revision.
3. verify the merged workflow on `main`.
4. verify contracts, AEC-001, content scan, full tests, readiness, and receipts.
5. confirm no permission expansion, credential use, deployment, connector execution, or external action.
6. record the post-merge result.
7. revert if exact-main verification fails.

### Phase 14 — PR #53 supersession

PR #53 remains open until the replacement:

- exists on a current-main base;
- passes both evidence lanes;
- receives operator review;
- is merged with expected-head protection;
- passes exact-main verification.

Only then:

1. close PR #53 unmerged;
2. identify the replacement PR;
3. preserve PR #53 as historical reference evidence;
4. retain its branch and artifacts unless separately approved for cleanup.

### Phase 15 — Dependent PR revalidation

After the replacement gate is merged and verified:

1. synchronize or reconstruct PR #63 as appropriate;
2. obtain dual-lane evidence on its final head;
3. preserve its separate review and merge decision;
4. proceed with PR #64 only after Issue #66 and PR #65 establish its classification;
5. finalize PR #65 only after Issue #66 records operator semantic choices;
6. do not batch-merge dependent PRs.

### Phase 16 — Readiness update

The gate improves assurance integrity. It does not by itself close production blockers.

A separate ledger change may record:

- exact-revision evidence implemented;
- merge-candidate evidence implemented;
- evidence confidence increased;
- stale-evidence blocker reduced;
- a direct score change only when the canonical ledger assigns supported weight.

Production identity, deployment, approved connectors, recovery, and external execution remain blocked until separately evidenced.

## 12. Artifact names

Recommended head artifact:

```text
aigc-immutable-head-evidence-<HEAD_SHA>
```

Recommended integration artifact:

```text
aigc-merge-candidate-evidence-<BASE_SHA>-<HEAD_SHA>-<MERGE_SHA>
```

Recommended bundle artifact:

```text
aigc-dual-revision-evidence-<HEAD_SHA>
```

Artifact names are evidence labels, not approval labels.

## 13. Observability and audit

The workflow shall expose, without sensitive values:

- evidence subject;
- selected revision;
- checked-out revision;
- base, head, and merge relationships;
- verification conclusion;
- schema conclusion;
- test conclusion;
- readiness source revision;
- artifact name;
- workflow run identity;
- timestamps;
- blocking failure reason.

Receipts shall be deterministic except for explicitly variable identifiers and timestamps.

## 14. Persistence and retention

This procurement uses GitHub Actions artifacts and repository contracts. It adds no application database migration.

Evidence retention must cover operator review and post-merge verification. Expired artifacts cannot support a new merge-readiness claim and must be regenerated.

## 15. Rollback

Before merge:

- abandon or close the implementation branch.

After merge:

- perform one bounded repository-approved revert;
- restore the previous workflow;
- rerun exact-main CI;
- record the rollback reason;
- keep production and external-action boundaries closed.

No database rollback is expected.

## 16. Risk register

| Risk | Consequence | Control | State |
|---|---|---|---|
| Head evidence only | stale-base defect can pass | mandatory merge-candidate lane | blocking |
| Merge evidence only | reviewed source remains ambiguous | mandatory immutable-head lane | blocking |
| Base changes after CI | integration evidence becomes stale | record base and rerun | blocking |
| Head changes after review | review no longer covers final code | re-review and expected-head protection | blocking |
| Workflow permission expansion | untrusted code gains authority | read-only permission and no privileged event | blocking |
| Persisted checkout credentials | later steps can reuse checkout access | disable persistence | blocking |
| Artifact and receipt mismatch | misleading evidence | schema and naming invariants | blocking |
| Stale PR #53 documentation | incorrect state claims | reconstruct selectively from current `main` | blocking |
| CI interpreted as approval | governance bypass | separate operator decision | blocking |
| Issue #66 conflated with CI | unresolved semantics hidden | preserve independent blocker | blocking |
| Evidence expiry | merge claim becomes unverifiable | regenerate artifacts | blocking |

## 17. Branch and PR plan

### Procedure PR

- branch `codex/ci-dual-revision-evidence-gate-v2-procedure`;
- base `main@293de53489fe7212fad272c01c698c0ffe2da610`;
- one procedure file only;
- draft and operator-controlled;
- merge authority remains ungranted by procedure instantiation.

### Future implementation PR

- branch `codex/ci-dual-revision-evidence-gate-v2-current-main`;
- base is latest verified `main` at implementation start;
- proposed title `fix(ci): separate exact-head evidence from merge-candidate validation`;
- draft until both evidence lanes pass;
- operator-controlled expected-head-protected merge only.

## 18. Acceptance criteria

The procurement succeeds only when:

1. implementation starts from latest verified `main`;
2. head and merge evidence subjects are separate;
3. strict contracts validate both receipts and bundle;
4. selected head, checkout, readiness, and artifact agree;
5. selected merge, checkout, inputs, and artifact agree;
6. base or head changes invalidate stale evidence;
7. full tests pass in appropriate lanes;
8. API and SQLite behavior remains green;
9. workflow permissions remain read-only;
10. persisted checkout credentials are disabled;
11. no sensitive values, production data, deployment, connectors, or external action are introduced;
12. final immutable head receives operator review;
13. any merge uses expected-head protection;
14. exact-main verification succeeds;
15. PR #53 closes unmerged only after verified supersession;
16. PRs #63, #64, and #65 receive fresh evidence and decisions;
17. Issue #66 remains blocking until explicitly resolved;
18. readiness claims remain evidence-bounded.

## 19. Definition of done

This procedure is complete when it is reviewed and merged as a governance document or explicitly rejected.

The underlying procurement is complete only when the future implementation satisfies every acceptance criterion, passes exact-main verification, records PR #53 supersession, and updates the evidence and readiness registers without unsupported production claims.

## 20. Next-run directive

The next AIGC evolution cycle shall inspect only the future dual-revision implementation train:

1. verify the implementation branch base;
2. inspect new or revised contracts;
3. inspect head selection, checkout, receipt, readiness revision, and artifact;
4. inspect merge base, head, merge revision, input verification, tests, and artifact;
5. inspect workflow permissions, persisted credentials, sensitive-context use, and event selection;
6. inspect final CI results for both lanes;
7. reconcile documentation with merged API and SQLite capabilities;
8. preserve PR #53 until supersession gates pass;
9. preserve Issue #66 as blocking;
10. report changed evidence, blockers, coverage, integration, rollback readiness, and readiness impact.

## 21. Governance summary

The dual-revision gate is the evidence anvil for subsequent AIGC work: one face proves what was reviewed; the other proves what will integrate. The metaphor grants no authority. The concrete controls are separate revisions, strict receipts, read-only workflows, negative tests, operator review, expected-head merge protection, rollback, and post-merge verification.
