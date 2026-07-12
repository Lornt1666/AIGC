# AIGC Dual-Revision Evidence Gate Procurement Procedure v2

**Document ID:** AIGC-PROC-CI-EVIDENCE-002  
**Status:** Proposed, operator-authorized procedure procurement  
**Project scope:** AIGC only  
**Parent program:** Issue #55  
**Related evidence implementation:** PR #53  
**Independent semantic gate:** Issue #66  
**Procedure branch:** `codex/ci-dual-revision-evidence-gate-v2-procedure`  
**Procedure base at instantiation:** `main@293de53489fe7212fad272c01c698c0ffe2da610`  
**Readiness-score change authorized by this procedure:** `0.0`  
**External action performed by AIGC runtime:** `false`

## 1. Purpose

This procedure governs one bounded procurement: reconstruct AIGC's CI evidence boundary from the latest reviewed `main` so that two different assurance questions are answered independently and truthfully:

1. **Immutable-head assurance:** Did CI inspect the exact source revision the operator will review?
2. **Merge-candidate assurance:** Does that exact source revision integrate successfully with the current target branch?

Neither answer may be substituted for the other. A passing immutable-head job does not prove current-base integration. A passing synthetic merge job does not prove that evidence was generated for the immutable PR head.

The procedure converts that distinction into contracts, workflow jobs, receipts, tests, review gates, rollback controls, and an operator-controlled merge decision.

## 2. Operator authorization record

Justice Gray Maciocha authorized repository update and instantiation of this bounded procedure on 2026-07-11 in the governing operator conversation.

That authorization permits:

- creation of this procedure on a separate branch;
- creation of a draft review PR;
- preparation of the future implementation plan;
- CI execution against review branches;
- collection of non-secret repository and workflow evidence.

That authorization does **not** permit:

- direct writes to `main`;
- self-approval;
- automatic merge;
- production deployment;
- credential or secret use;
- connector execution;
- external consequential action;
- readiness promotion without a separate evidence-backed decision;
- resolution of Issue #66 without the operator's explicit semantic choices.

## 3. Evidence basis

At procedure instantiation:

- current `main` is `293de53489fe7212fad272c01c698c0ffe2da610`;
- current `main` contains the localhost operator API and transactional SQLite authority/audit persistence;
- current `main` still uses the default pull-request checkout and names readiness artifacts with `${{ github.sha }}`;
- PR #53 contains the only implemented exact-head evidence correction;
- PR #53 head `9c7fecd057cf33f79e202e46a3e6bb83d7fa7e48` passed AIGC CI run 671 with matching selected revision, checkout revision, verifier receipt, readiness source revision, and artifact name;
- PR #53 diverged from current `main` and contains repository-state documentation that predates the merged API and storage trains;
- PRs #63, #64, and #65 have successful tests, but their readiness artifacts identify synthetic pull-request merge revisions rather than their immutable heads;
- Issue #66 remains open and independently blocks canonical job-lifecycle ratification.

Therefore:

- PR #53 is retained as reference evidence;
- PR #53 is not merged unchanged;
- a clean replacement must be reconstructed from the latest `main`;
- PRs #63, #64, and #65 remain blocked from merge-readiness claims until the replacement gate produces exact-head and merge-candidate evidence;
- no production capability or readiness increase is inferred from this procedure.

## 4. Governing principles

### 4.1 Evidence subjects remain distinct

Every receipt shall declare exactly one evidence subject:

- `IMMUTABLE_HEAD`; or
- `MERGE_CANDIDATE`.

A receipt shall never report both as though they were one revision.

### 4.2 Evidence is not authority

CI may validate, measure, and report. CI may not approve, merge, deploy, ratify semantics, or authorize external action.

### 4.3 Fail closed

Missing, malformed, stale, ambiguous, mismatched, or unbound revisions are blocking failures. A non-blocking warning is not allowed for revision identity failures.

### 4.4 Current-base integration is time-sensitive

Merge-candidate evidence is valid only for the recorded base revision, head revision, and resulting merge-candidate revision. A change to the PR head or target branch invalidates the prior merge-candidate evidence.

### 4.5 Security and privacy are preserved

The replacement shall not use `pull_request_target`, repository write permissions, secrets, production data, persisted checkout credentials, live connectors, or privileged untrusted-code execution.

### 4.6 Operator control is preserved

The operator reviews the final immutable head and makes a separate expected-head-protected merge decision. Procedure approval is not merge approval.

## 5. Scope

### 5.1 Included

The implementation procurement includes:

- exact revision resolution for push and pull-request events;
- explicit immutable-head checkout;
- immutable-head verifier receipt;
- revision-bound production-readiness execution;
- merge-candidate checkout or deterministic construction;
- merge-candidate parent and identity verification;
- separate evidence artifacts for each lane;
- strict schemas and validation;
- positive, negative, stale-evidence, and workflow-wiring tests;
- read-only workflow permissions;
- rollback and post-merge verification;
- current-state documentation reconciliation;
- controlled supersession of PR #53.

### 5.2 Excluded

This procurement does not include:

- changes to application runtime behavior;
- job-state semantics or Issue #66 decisions;
- API or UI changes;
- database schema migration;
- production identity;
- connector enablement;
- credentials or secret-manager access;
- deployment or public networking;
- external action;
- readiness-ledger capability promotion;
- broad CI supply-chain modernization unrelated to revision evidence.

## 6. Roles and authority

| Role | Responsibility | Authority boundary |
|---|---|---|
| Accountable operator — Justice Gray Maciocha | scope approval, residual-risk decision, final head review, merge decision | sole operator authority; may not be inferred from CI |
| Technical implementer | contracts, code, workflow, tests, documentation | may prepare and push reviewable changes; may not self-approve or merge |
| CI verifier | deterministic evidence generation and validation | advisory evidence only |
| Security/privacy reviewer | confirms no permission, secret, privacy, or execution-boundary regression | may block; cannot merge |
| Independent reviewer, when required by policy | human technical review distinct from authorship | review authority only |
| Repository merger | executes only an explicit expected-head-protected merge decision | no implied deployment authority |

## 7. Required terminology

- **Head revision:** immutable commit at `github.event.pull_request.head.sha`, or the push revision for a push event.
- **Base revision:** immutable target-branch commit recorded for the pull-request event.
- **Merge-candidate revision:** checked-out or constructed merge commit combining the recorded base and head revisions.
- **Selected revision:** revision the current evidence lane declares it will inspect.
- **Checked-out revision:** result of `git rev-parse HEAD` in that lane.
- **Source revision:** revision written into a readiness or evidence receipt.
- **Evidence bundle:** artifacts and receipts from one workflow run, partitioned by evidence subject.
- **Stale evidence:** evidence whose recorded head or base no longer matches the PR's current head or target branch.

## 8. Required contracts

Contract-first design shall precede workflow implementation.

### 8.1 Immutable-head evidence receipt

The v2 immutable-head receipt shall require at minimum:

- contract identifier and version;
- receipt identifier;
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

### 8.2 Merge-candidate evidence receipt

The merge-candidate receipt shall require at minimum:

- contract identifier and version;
- receipt identifier;
- repository identity;
- event name `pull_request`;
- evidence subject `MERGE_CANDIDATE`;
- base revision;
- head revision;
- selected merge-candidate revision;
- checked-out merge-candidate revision;
- ordered or explicitly classified parent revisions;
- integration test conclusion;
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
recorded head revision is a verified parent or verified merged input
recorded base revision is a verified parent or verified merged input
```

### 8.3 Evidence-bundle manifest

The bundle manifest shall bind:

- workflow run;
- immutable head;
- base revision;
- merge candidate;
- receipt paths;
- artifact names;
- test conclusions;
- schema-validation conclusions;
- evidence freshness state;
- operator-review requirement.

The bundle shall fail validation when either mandatory lane is absent for a pull request.

## 9. Required configuration and workflow controls

The implementation shall preserve or add:

- top-level workflow permission `contents: read`;
- `persist-credentials: false` for every checkout;
- explicit full 40-character SHA validation;
- no `pull_request_target` event;
- no secrets passed to untrusted PR code;
- no repository write token;
- no deployment environment;
- no connector invocation;
- no artifact name derived from an unverified revision;
- no readiness source revision assigned before checkout verification;
- explicit artifact retention through GitHub Actions configuration;
- deterministic failure when required event fields are unavailable.

Workflow expressions select candidate values. Repository code independently validates those values and the actual checkout.

## 10. Procurement execution procedure

The binding order is:

```text
intake
→ evidence verification
→ scope lock
→ contract-first design
→ implementation plan
→ security/privacy wiring
→ implementation
→ tests
→ CI
→ operator review
→ merge decision
→ post-merge verification
→ readiness-ledger update
```

No phase may claim the completion of a later phase.

### Phase 1 — Intake

1. Record parent program Issue #55.
2. Record the operator authorization and its limits.
3. Resolve latest `main`; do not reuse the procedure-instantiation SHA without verification.
4. Record all open PRs affected by exact-revision assurance.
5. Record PR #53 as `REFERENCE_PENDING_SUPERSESSION`.
6. Record Issue #66 as an independent blocking decision gate.

Exit receipt: `INTAKE_COMPLETE` or `INTAKE_BLOCKED`.

### Phase 2 — Evidence verification

1. Fetch current `main` SHA and current workflow.
2. Inspect PR #53 immutable head, run result, verifier receipt, readiness source revision, artifact name, permissions, and tests.
3. Compare PR #53 with current `main`.
4. Identify stale documentation or code assumptions.
5. Inspect the final heads and current CI artifact revisions of PRs #63, #64, and #65.
6. Reject any merge-readiness claim whose artifact revision differs from its immutable head.
7. Record changed evidence rather than copying historic claims.

Exit receipt: `EVIDENCE_VERIFIED`, `EVIDENCE_PARTIAL`, or `EVIDENCE_BLOCKED`.

### Phase 3 — Scope lock

Create a new implementation branch using the latest verified `main`:

```text
codex/ci-dual-revision-evidence-gate-v2-current-main
```

The exact branch name may be versioned if already occupied, but the base must be recorded.

Lock the implementation to:

- schemas;
- verifier modules and CLIs;
- CI workflow wiring;
- tests;
- exact-revision documentation.

Changes outside that set require a new scope decision.

Exit receipt: `SCOPE_LOCKED`.

### Phase 4 — Contract-first design

1. Define or revise the immutable-head receipt schema.
2. Define the merge-candidate receipt schema.
3. Define the evidence-bundle manifest schema.
4. Register schemas through the repository contract registry where required.
5. Add negative contract fixtures before workflow wiring.
6. Require `additionalProperties: false` where compatible with repository schema conventions.
7. Constrain revisions to full hexadecimal commit SHAs.
8. Constrain evidence-subject vocabulary.
9. Require truthful false states and failure reasons.

Exit receipt: `CONTRACTS_READY` only after schema tests pass.

### Phase 5 — Implementation plan

The implementation plan shall enumerate:

- affected files;
- dependency direction;
- workflow job graph;
- event handling;
- artifact paths and names;
- failure modes;
- test ownership;
- rollback;
- migration impact;
- operator review points.

No database migration is expected. CI artifacts remain the persistence mechanism for this train.

Exit receipt: `IMPLEMENTATION_PLANNED`.

### Phase 6 — Security and privacy wiring

Before executing PR code:

1. Set permissions to read-only.
2. Disable persisted checkout credentials.
3. Confirm no secret context is referenced.
4. Confirm `pull_request_target` is absent.
5. Confirm the workflow does not execute privileged external actions.
6. Confirm evidence artifacts contain repository metadata and test results only, not secrets or production data.
7. Run the repository secret-like-content scan.
8. Preserve the Security & Privacy Wiring Gate; do not add bypasses or exceptions.

Exit receipt: `SECURITY_PRIVACY_WIRED` or blocking finding.

### Phase 7 — Immutable-head lane implementation

For pull requests:

1. Select `github.event.pull_request.head.sha`.
2. Validate it as a full commit SHA.
3. Checkout that SHA explicitly with full history only where required.
4. Set `persist-credentials: false`.
5. Read actual `HEAD` independently.
6. Fail unless selected and actual revisions match.
7. Write and schema-validate the immutable-head receipt.
8. Install dependencies.
9. Run contracts, AEC-001, secret scanning, procurement smoke stages, tests, and revision-bound readiness.
10. Fail unless readiness source revision equals the verified head.
11. Upload an artifact named with the verified immutable head.

For push events, the same lane uses the immutable push SHA.

### Phase 8 — Merge-candidate lane implementation

For pull requests only:

1. Record the event's base and head revisions.
2. Select the GitHub merge candidate or construct a deterministic merge in an isolated job.
3. Checkout or construct it without write permissions or secrets.
4. Read actual `HEAD` independently.
5. Verify the selected and actual merge-candidate revisions match.
6. Verify that the recorded base and head are the merge inputs or expected parents.
7. Write and schema-validate the merge-candidate receipt.
8. Run contracts, AEC-001, secret scanning, procurement smoke stages, and the full tests.
9. Upload an artifact whose name separately identifies the base, head, and merge-candidate evidence subject.
10. Do not write this merge-candidate revision into the immutable-head readiness receipt.

If the base branch changes, prior merge-candidate evidence becomes stale and a new run is mandatory.

### Phase 9 — Test requirements

At minimum, tests shall cover:

#### Positive tests

- matching immutable selected and checked-out revisions;
- revision-bound readiness source;
- valid immutable-head receipt;
- valid merge-candidate receipt;
- valid base/head parent verification;
- valid evidence-bundle manifest;
- push-event immutable revision handling;
- pull-request dual-lane workflow wiring.

#### Negative tests

- abbreviated SHA;
- uppercase or malformed revision where disallowed by the contract;
- selected/checked-out mismatch;
- readiness source mismatch;
- artifact-name mismatch;
- missing base or head revision;
- merge candidate without both required merge inputs;
- stale base;
- stale head;
- missing mandatory lane;
- malformed receipt;
- unknown evidence subject;
- environment restoration failure;
- workflow permission expansion;
- persisted checkout credentials;
- `pull_request_target` introduction;
- secret reference in the workflow.

#### Regression tests

- existing API tests;
- existing SQLite migration, persistence, integrity, backup, and audit tests;
- existing identity and authorization tests;
- full repository test suite.

### Phase 10 — CI and evidence gates

A pull request is not eligible for operator merge review until:

1. immutable-head lane passes on the final PR head;
2. merge-candidate lane passes against the current target-branch revision;
3. all mandatory tests pass;
4. contracts and AEC-001 validate;
5. secret-like-content scan passes;
6. Security & Privacy Wiring remains intact;
7. immutable-head receipt, readiness source revision, and immutable-head artifact agree;
8. merge-candidate receipt and merge-candidate artifact agree;
9. bundle manifest validates;
10. no mandatory evidence is expired or stale;
11. no unresolved blocking review thread remains.

A green check without valid receipts is insufficient.

### Phase 11 — Operator review

The review packet shall present:

- final immutable head;
- current base revision;
- merge-candidate revision;
- receipt verification states;
- workflow permissions;
- changed files;
- test result;
- readiness result without unsupported promotion;
- unresolved findings;
- rollback procedure;
- PR #53 comparison and disposition recommendation;
- residual risks.

The operator shall review the final immutable head. Any new commit invalidates the prior review decision.

### Phase 12 — Merge decision

Merge remains a separate decision.

If authorized:

- use expected-head protection against the reviewed immutable head;
- use the repository-approved merge method;
- do not enable automatic deployment;
- record the merge result;
- proceed immediately to exact-main post-merge verification.

If not authorized:

- leave the PR open for correction;
- or close it without merge and record the reason.

### Phase 13 — Post-merge verification

After merge:

1. Resolve the exact new `main` revision.
2. Run or inspect CI bound to that exact revision.
3. Verify the merged workflow on `main`.
4. Verify contracts, AEC-001, secret scan, full tests, readiness, and evidence receipts.
5. Confirm no permission expansion, credential use, deployment, connector execution, or external action occurred.
6. Record the post-merge receipt.
7. Reopen or revert if exact-main verification fails.

### Phase 14 — PR #53 supersession

PR #53 shall remain open until the replacement:

- exists on a current-main base;
- passes immutable-head and merge-candidate lanes;
- receives operator review;
- is merged with expected-head protection;
- passes exact-main post-merge verification.

Only then:

1. close PR #53 unmerged;
2. identify the replacement PR;
3. state that PR #53 remains historical reference evidence;
4. do not delete its branch or artifacts as part of this bounded procedure unless separately authorized.

### Phase 15 — Dependent PR revalidation

After the replacement gate is merged and verified:

1. synchronize or reconstruct PR #63 from the verified current `main` as appropriate;
2. obtain dual-lane evidence on its final immutable head;
3. preserve its independent operator review and merge decision;
4. repeat for PR #64 only after Issue #66 and PR #65 establish its proper classification;
5. finalize PR #65 only after Issue #66 records the operator's semantic decisions;
6. do not batch-merge dependent PRs.

### Phase 16 — Readiness-ledger update

The evidence gate primarily improves assurance integrity. It does not by itself close production capability blockers.

A separate readiness-ledger change may record:

- exact-revision evidence capability implemented;
- merge-candidate integration evidence implemented;
- evidence confidence increased;
- stale-evidence blocker reduced;
- direct production-readiness score increase only if the canonical ledger explicitly assigns supported weight.

Production identity, deployment, approved connectors, recovery, and external execution remain blocked until separately evidenced.

## 11. Artifact naming standard

Recommended immutable-head artifact:

```text
aigc-immutable-head-evidence-<HEAD_SHA>
```

Recommended merge-candidate artifact:

```text
aigc-merge-candidate-evidence-<BASE_SHA>-<HEAD_SHA>-<MERGE_SHA>
```

Recommended bundle manifest artifact:

```text
aigc-dual-revision-evidence-<HEAD_SHA>
```

Artifact names are evidence labels, not approval labels.

## 12. Observability and audit

The workflow shall expose, without secrets:

- evidence subject;
- selected revision;
- checked-out revision;
- base/head/merge relationships;
- verification conclusion;
- schema conclusion;
- test conclusion;
- readiness source revision;
- artifact name;
- workflow run identity;
- timestamps;
- blocking failure reason.

Receipts shall be deterministic except for identifiers and timestamps whose variability is explicitly defined.

## 13. Persistence and retention

This procurement uses GitHub Actions artifacts and repository contracts. It introduces no application database migration.

Evidence retention shall be long enough for operator review and post-merge verification. Expired artifacts cannot support a new merge-readiness claim and must be regenerated.

## 14. Rollback and recovery

Before merge:

- abandon or close the implementation branch.

After merge:

- perform one bounded squash revert or equivalent repository-approved revert;
- restore the previous workflow;
- rerun exact-main CI;
- record why rollback occurred;
- keep production and external-action boundaries closed.

No database rollback is expected.

## 15. Risk register

| Risk | Consequence | Control | Blocking state |
|---|---|---|---|
| Exact-head evidence only | stale-base integration defect can pass | mandatory merge-candidate lane | blocking |
| Merge-candidate evidence only | reviewed source revision remains ambiguous | mandatory immutable-head lane | blocking |
| Base changes after CI | integration evidence becomes stale | record base SHA and rerun | blocking |
| Head changes after review | review no longer covers final code | expected-head protection and re-review | blocking |
| Workflow permission expansion | untrusted code may gain write authority | `contents: read`, no secrets, no `pull_request_target` | blocking |
| Persisted checkout credentials | later steps could reuse repository credential | `persist-credentials: false` | blocking |
| Artifact/receipt mismatch | misleading evidence package | schema and naming invariants | blocking |
| Stale PR #53 documentation | incorrect current-state claims | reconstruct from current `main`; selective reuse only | blocking |
| CI interpreted as approval | governance bypass | explicit operator-review field and separate merge decision | blocking |
| Issue #66 conflated with CI work | unresolved lifecycle semantics hidden | preserve independent blocker | blocking |
| Evidence expires before review | unverifiable merge claim | regenerate artifacts | blocking |

## 16. Branch and pull-request plan

### Procedure PR

- branch: `codex/ci-dual-revision-evidence-gate-v2-procedure`;
- base: `main@293de53489fe7212fad272c01c698c0ffe2da610`;
- change: this procedure only;
- state: draft and operator-controlled;
- merge authorization: not granted by procedure instantiation.

### Future implementation PR

- branch: `codex/ci-dual-revision-evidence-gate-v2-current-main`;
- base: latest verified `main` at implementation start;
- proposed title: `fix(ci): separate exact-head evidence from merge-candidate validation`;
- state: draft until both evidence lanes pass;
- merge: operator-controlled and expected-head-protected only.

## 17. Acceptance criteria

The procurement succeeds only when all of the following are true:

1. implementation begins from the latest verified `main`;
2. immutable-head and merge-candidate evidence subjects are separate;
3. strict contracts validate both receipts and the bundle manifest;
4. immutable selected, checked-out, readiness, and artifact revisions agree;
5. merge-candidate selected, checked-out, parent inputs, and artifact revisions agree;
6. base or head changes invalidate stale evidence;
7. full tests pass in both appropriate lanes;
8. current API and SQLite storage behavior remains green;
9. workflow permissions remain read-only;
10. persisted checkout credentials are disabled;
11. no secrets, production data, deployment, connectors, or external actions are introduced;
12. final immutable head receives operator review;
13. merge, if authorized, uses expected-head protection;
14. exact-main post-merge verification succeeds;
15. PR #53 is closed unmerged only after verified supersession;
16. PRs #63, #64, and #65 receive their own fresh evidence and decisions;
17. Issue #66 remains blocking until explicitly resolved by the operator;
18. readiness claims remain evidence-bounded.

## 18. Definition of done

This procedure is complete when it is reviewed and merged as a governance document or explicitly rejected.

The underlying procurement is complete only when the future implementation PR satisfies every acceptance criterion, passes post-merge exact-main verification, records PR #53 supersession, and updates the evidence/readiness registers without unsupported production claims.

## 19. Immediate next-run directive

The next scheduled AIGC evolution cycle shall inspect only the future dual-revision implementation train:

1. verify the implementation branch was created from the latest `main`;
2. inspect all new or revised contracts;
3. inspect immutable-head selection, checkout, receipt, readiness source revision, and artifact name;
4. inspect merge-candidate base, head, merge revision, parent verification, tests, and artifact name;
5. inspect workflow permissions, persisted credentials, secret usage, and event selection;
6. inspect final CI results for both lanes;
7. compare current-state documentation with merged API and SQLite capabilities;
8. preserve PR #53 until supersession gates are satisfied;
9. preserve Issue #66 as blocking;
10. report changed evidence, blocker state, test coverage, integration status, rollback readiness, and readiness impact.

## 20. Governance summary

The dual-revision gate is the evidence anvil for subsequent AIGC work: one face proves what was reviewed; the other proves what will integrate. The metaphor grants no authority. The concrete controls are separate immutable revisions, strict receipts, read-only workflows, negative tests, operator review, expected-head merge protection, rollback, and post-merge verification.
