# AIGC Evolution and Procurement Cycle — Exact Revision Evidence Gate v1

Status: **bounded implementation proposed on a separate review branch**  
Scope: **AIGC only**  
Evidence base: `main` at `b76d6ac966ef41df00066db4bbbbead64eec8dd6`  
Implementation branch: `codex/ci-exact-revision-evidence-gate-v1`  
External action performed by AIGC runtime: `false`  
Deployment performed: `false`  
Readiness status changed: `false`

## 1) Evolution Diagnosis

### Ontology health

AIGC has a strong constitutional and authorization ontology: AEC-001 is ratified; shared assurance contracts, the Assurance Sensorium, review packets, and identity contracts exist; and PR #50 implements a local principal-authority binding simulator. The evidence ontology is less complete. It lacks first-class representations for `ExpectedRevision`, `CheckedOutRevision`, `WorkflowEvent`, `RevisionVerification`, `EvidenceBinding`, and `EvidenceStrength` at the CI boundary.

The missing relationship is:

`governed change -> expected head revision -> exact checkout -> validation execution -> revision-bound receipts -> review decision`.

Without this relationship, a successful job can be associated with a PR head while its uploaded readiness receipt names a different synthetic merge revision.

### Taxonomy completeness

The recursive production architect currently classifies ontology into `code`, `infrastructure`, `devops`, `data`, and `risk`, and taxonomy into `layer`, `function`, `lifecycle`, and `ownership`. This is useful inventory, but incomplete for assurance. Add the following dimensions:

- evidence subject: head, merge candidate, main, release;
- evidence class: structural, semantic test, CI execution, staging observation, production observation;
- authority class: AI advisory, operator, independent human, provider;
- consequence class: internal, sensitive, external, production;
- freshness class: current, stale, superseded, unbound;
- reversibility class: revertible, migratable, externally irreversible;
- accessibility, privacy, recovery, compatibility, and deployment maturity.

### Methodology coherence

The repository consistently declares contract-first design, fail-closed behavior, exact-head review, operator control, rollback, and no unsupported completion claims. The present CI implementation does not fully realize its exact-head claim for pull-request evidence because GitHub pull-request workflows normally expose a merge ref and event-dependent `GITHUB_SHA`. Run 633 passed, but its readiness artifact was named for and bound to `63197dc34ba0ef0ff2e8edaa0d3a714541445571`, while PR #50's head was `fdfc0ea3622c2eb1b4043dbcb495079488bb4388`. The job result remains useful, but the uploaded receipt is not strict exact-head evidence.

### Architecture integrity

Strengths:

- ratified constitutional substrate;
- strict identity contracts and local authorization kernel;
- modular CLIs and core modules;
- CI, redaction scanning, tests, readiness reporting, and artifact upload;
- external execution blocked by default.

Integrity gap:

- CI does not prove that the checked-out commit, the expected reviewed head, the readiness report's `source_revision`, and the artifact name are the same revision.

### Production-readiness gaps

Run 633 reported **53.9/100**, below the threshold of 90, using `structural_repository_evidence_v2`. The report explicitly states that this is structural evidence, not operational proof. Current production blockers remain:

- `security_privacy_wiring`;
- `transactional_persistence`;
- `production_identity_access`;
- `approved_external_connectors`;
- `production_deployment`.

PR #50 is open, not merged. No production-readiness status or score is advanced in this cycle.

### Governance stability

AEC-001 v1.0.0 is ratified and preserves truth, human authority, deny-by-default authorization, evidence, contract-first design, privacy, accessibility, security, production readiness, repository governance, determinism, recoverability, and no merge with unresolved mandatory gates. The exact-revision correction strengthens those existing rules; it does not amend the Constitution.

### Evolution bottlenecks

1. CI evidence cannot yet prove exact-head execution end to end.
2. PR #50 should not be merged under an exact-head claim until this is corrected and rerun.
3. The readiness ledger remains structural and cannot independently establish runtime, staging, or production maturity.
4. Transactional persistence is the next architecture bottleneck only after the evidence boundary and PR #50 integration are resolved.

### Dead logic, redundant modules, and fragile structures

- No executable module is proven dead.
- The recursive architect exposes `maximum_cycles_per_run`, but its implementation unconditionally stops after one cycle. The multi-cycle configuration is therefore currently ineffective and should be labelled one-cycle or made evidence-delta driven.
- Old draft PRs #11, #15, and #21 remain open. They are not proven useless, but they are stale integration surfaces and require explicit rebase, supersession, or closure decisions.
- The procurement index contains an outdated implementation sequence that still treats already-completed work as future work.
- The fragile structure corrected here is reliance on event-dependent CI revision variables without a separate expected-versus-actual verification receipt.

## 2) Contender Arena

| Rank | Identity | Strategy | Strengths | Weaknesses | Evolutionary vector | Contribution to synthesis |
|---:|---|---|---|---|---|---|
| 1 | Exact Revision Evidence Gate | Check out the explicit PR head or push SHA, compare it to `git rev-parse HEAD`, emit a strict receipt, and bind readiness artifacts to that revision | Bounded, testable, directly repairs evidence integrity | Adds one schema, verifier, CLI, and workflow step | trustworthy CI provenance | Winning implementation |
| 2 | Full Evidence Provenance Graph | Model every test, artifact, source, and review relationship as a graph | Highest long-term assurance | Too broad for one bounded cycle | supply-chain-grade evidence | Engine v+1 direction |
| 3 | Exact Checkout Only | Configure `actions/checkout` with the PR head SHA | Small change | Does not prove the actual checkout or receipt binding | partial exact-head control | Included but insufficient alone |
| 4 | Receipt-Only Verification | Compare expected and actual SHA after default checkout | Detects mismatch | Default checkout can still select the merge ref and fail every PR | fail-closed detection | Included with explicit checkout |
| 5 | Rerun PR #50 Without Workflow Change | Start another CI run | Fast | Reproduces the same ambiguous evidence semantics | no architectural improvement | Rejected |
| 6 | Merge PR #50 Then Verify Main | Use main verification as the definitive receipt | Main would be concrete | Merges before satisfying the stated exact-head gate | integration-first | Rejected for governance order |
| 7 | Transactional Identity Spine | Begin SQLite persistence now | Major capability progress | Builds on an unresolved evidence and open integration train | durable authority state | Deferred successor |
| 8 | External Attestation Service | Use hosted signing/provenance infrastructure | Strong future supply-chain assurance | Credentials, service integration, cost, and operational scope | external assurance | Deferred production option |

Pressure test result: exact checkout alone does not establish proof; a verifier alone can make every PR fail under default merge-ref checkout; a readiness receipt alone can still inherit the wrong revision. The strongest bounded hybrid is explicit expected revision selection + exact checkout + actual checkout verification + strict receipt + revision-bound readiness generation + artifact naming.

## 3) Auto-Design Output

### Modules

- `CIRevisionEvidence`: canonical expected/actual revision verification.
- `RevisionBoundReadinessEntrypoint`: invokes the existing readiness engine only after exact revision verification.
- `CIRevisionEvidenceReceipt`: machine-readable audit contract.

### Interfaces

- `normalize_revision(value, label) -> sha`;
- `read_git_head(project_root) -> sha`;
- `build_receipt(expected_revision, actual_revision, event_name) -> receipt`;
- `verify_ci_revision(project_root, expected_revision, event_name) -> receipt`;
- `write_receipt(receipt, output_path) -> path`;
- revision-bound readiness CLI using `--expected`, `--event`, `--project-root`, `--ledger`, and `--artifact-root`.

### Conceptual framework

`Expected Revision Contract -> Exact Checkout -> Actual Revision Observation -> Equality Gate -> Evidence Receipt -> Tests and Readiness -> Revision-Named Artifact`.

### Ontology expansion

Add `ExpectedRevision`, `ActualRevision`, `WorkflowEvent`, `RevisionObservation`, `RevisionVerificationReceipt`, and `EvidenceSubject`.

### Taxonomy refinement

Add evidence-binding states: `VERIFIED_EXACT`, `MISMATCH`, `MALFORMED`, `UNAVAILABLE`. This implementation emits `verified: true|false` and fails closed on mismatch or malformed SHA.

## 4) Auto-Engineer Output

Implemented pipeline on the review branch:

1. Resolve `AIGC_EXPECTED_REVISION` as PR head SHA for pull-request runs or `github.sha` for push runs.
2. Check out that exact revision with full history.
3. Read `git rev-parse HEAD`.
4. Validate both values as full 40-character SHA-1 identifiers.
5. Compare expected and actual revision.
6. Emit `ci_revision_evidence_receipt.json`.
7. Fail the workflow on mismatch.
8. Run dependency installation, contract validation, AEC-001 validation, redaction scan, procurement smoke stages, and tests.
9. Invoke the existing readiness engine through a revision-bound wrapper.
10. Assert the readiness report's `source_revision` equals the verified revision.
11. Upload revision and readiness receipts together under an artifact named with the expected revision.

Operational logic remains local and CI-only. No credential, connector, deployment, approval, or external-action capability is added.

## 5) Auto-Architect Output

### System architecture

`GitHub Event Context -> Expected Revision Resolver -> Exact Checkout -> Revision Evidence Gate -> Existing Validation Pipeline -> Revision-Bound Readiness Adapter -> Evidence Artifact`.

### Integration pattern

This is an anti-corruption adapter around the existing readiness engine. It avoids broad modification of the readiness model while ensuring the engine receives a verified source revision. Later, `source_revision` should become an explicit function argument rather than process environment state.

### Macro-structure improvement

The CI pipeline now has a declared evidence subject before validation begins. Every downstream receipt can be traced to the same immutable revision. This closes the gap between repository governance language and workflow execution semantics.

### Cross-module coherence

- AEC-001 truth and evidence invariants govern the verifier.
- The readiness ledger remains the scoring authority.
- The exact-revision receipt supplies provenance, not authorization.
- PR review and operator authority remain separate from automated CI success.

## 6) Cognitive and Analytical Review

Evidence supports a correction before further integration. Run 633's successful tests are not discarded; they demonstrate that the synthetic merge candidate passed. The unsupported part was calling its uploaded readiness receipt exact-head evidence. The correction is therefore narrow: preserve all existing tests and controls, change only revision selection and evidence binding, and rerun.

Assumptions:

- the repository remains private and GitHub Actions is the active CI platform;
- PR branches are in the same repository;
- SHA-1 commit identifiers remain the GitHub commit identity exposed to this workflow;
- no production release depends on this branch.

Tradeoffs:

- checking the PR head tests the reviewed branch exactly, but does not test GitHub's synthetic merge result; exact-main verification remains mandatory after merge;
- full checkout history is slightly slower but supports deterministic revision resolution and future provenance checks;
- the adapter preserves compatibility but should eventually be replaced by explicit revision injection into the readiness API.

Systemic consequence: evidence quality improves without increasing application capability. This is the correct ordering because future readiness-score movement is only trustworthy when its receipts are revision-bound.

## 7) 2026 Societal Logic Integration

### Regulation and privacy

For Canadian private-sector operation, personal-information handling must be assessed against applicable federal and provincial law. The design follows PIPEDA-style accountability, identified purpose, consent, collection limitation, safeguards, access, and challenge principles by storing only commit identifiers and CI metadata. No personal identity or credential is introduced.

For EU-facing deployment, the EU AI Act's phased obligations must be mapped by use case and risk class. This CI change does not establish compliance; it improves documentation, logging, traceability, and human-oversight evidence that may support later obligations.

### Security

NIST SP 800-63 Revision 4, finalized in July 2025, separates identity proofing, authentication, and federation assurance and adds continuous evaluation considerations. AIGC should retain its IAL/AAL/FAL separation and must not infer production identity maturity from CI evidence.

### Accessibility

Future cockpit and review interfaces should target WCAG 2.2 AA, including keyboard operation, visible and unobscured focus, status messages, target size, understandable errors, and accessible authentication. This CLI-only change has no visual UI impact.

### Organizational coordination

Automated CI verifies artifacts; it does not approve them. The accountable operator retains merge authority, and release-critical work still requires the review path defined by governance. Evidence receipts must remain understandable to a human reviewer.

### Deployment and platform constraints

GitHub documents that pull-request refs and `GITHUB_SHA` are event-dependent. AIGC must therefore select the intended evidence subject explicitly rather than treating a default event SHA as universally equal to the PR head. No deployment is performed.

## 8) Final Synthesis

Advance AIGC by making immutable revision identity the first gate in its CI assurance chain. The synthesized control combines explicit head selection, exact checkout, deterministic comparison, strict contract validation, fail-closed behavior, revision-bound readiness reporting, and operator-controlled review. It preserves the successful identity implementation while correcting the evidence required to integrate it honestly.

## 9) Single Highest-Impact Next Implementation Step

**Implement Exact Revision Evidence Gate v1.**

This is the single highest-impact immediate step because PR #50's next decision depends on an exact-head claim, while the current uploaded receipt is bound to a different synthetic merge revision. Transactional persistence and other production capabilities should not advance until CI evidence can reliably identify what was tested.

## 10) Procurement Success Packet

### Objective

Guarantee that every AIGC CI validation and readiness artifact names and verifies the exact commit selected for review.

### Scope

- pull-request and push CI revision selection;
- exact checkout;
- expected/actual comparison;
- strict evidence receipt;
- revision-bound readiness execution;
- artifact upload and tests;
- one documentation and procurement-index update.

### Non-scope

- merging PR #50 or this PR;
- changing authorization semantics;
- SQLite persistence;
- live identities, credentials, connectors, deployments, or external actions;
- production-readiness status changes;
- branch protection administration.

### Prerequisites

- AEC-001 ratified;
- existing AIGC CI workflow;
- production-readiness ledger and CLI;
- Python 3.12 CI runtime;
- separate review branch.

### Dependency and evidence check

Verified: main `b76d6ac966ef41df00066db4bbbbead64eec8dd6`; PR #50 head `fdfc0ea3622c2eb1b4043dbcb495079488bb4388`; run 633 success; artifact source revision `63197dc34ba0ef0ff2e8edaa0d3a714541445571`; current readiness score 53.9; no production-ready claim.

### Affected ontology domains

Evidence, DevOps, governance, readiness, audit, repository revision, review.

### Affected taxonomy classes

CI event, expected revision, actual revision, evidence class, verification state, artifact subject, freshness, rollback class.

### Governing methodologies

Contract-first design, fail-closed validation, test-driven development, GitOps, least privilege, deterministic evidence, traceability, bounded PRs, operator review.

### Architecture impact

Adds a small provenance gate before validation and a compatibility adapter before readiness generation. No runtime application path is changed.

### Required schemas/contracts

- `schemas/ci_revision_evidence_receipt.schema.json`.

### Required config

- workflow-scoped `AIGC_EXPECTED_REVISION` derived from GitHub event context;
- no secret or persistent configuration.

### Required core modules

- `src/core/ci_revision_evidence.py`.

### Required CLI/API/UI wiring

- `src/ci_revision_evidence_cli.py`;
- `src/production_readiness_revision_bound_cli.py`;
- `.github/workflows/aigc-ci.yml`;
- no API or UI surface.

### Persistence requirements

Write JSON receipts only under `reports/artifacts`; upload as ephemeral CI artifacts. No database migration.

### Security and privacy controls

No secrets, tokens, personal data, or broad permissions. Workflow permissions remain `contents: read`. Receipt contains only revision and event metadata. Redaction scan remains mandatory.

### Identity and authorization requirements

CI evidence does not authenticate the operator and cannot grant authority. GitHub's event context identifies the candidate revision; operator review and merge authority remain separate gates.

### Observability and audit requirements

Record expected revision, actual revision, event, verification result, timestamp, evidence class, operator-review flag, and `external_action_performed=false`. Upload alongside readiness evidence.

### Tests

- matching revision succeeds;
- mismatch is recorded and fails closed;
- malformed and non-hex revisions fail;
- unknown events map to a bounded class;
- receipt validates against schema;
- readiness wrapper binds and restores process environment;
- workflow contains explicit checkout, verifier, revision-bound readiness, and artifact paths;
- full repository test suite.

### CI gates

Exact revision verification, dependency installation, contract validation, AEC-001 validation, redaction scan, procurement smoke stages, full tests, revision-bound readiness evaluation, artifact upload.

### Rollback plan

One squash revert of the bounded PR restores the prior CI workflow and removes the new verifier files. No data rollback is required.

### Migration plan

No data migration. Existing artifacts retain their original revision labels and must not be rewritten. New runs use the exact-revision contract.

### Documentation and runbook

This cycle report and the procurement assurance index describe the evidence defect, operation, review order, and next-run checks.

### Ownership

Accountable operator: Justice Gray Maciocha / Lornt / Satoshi. Automated CI is evidence-producing only. Independent review is not claimed.

### Sequencing

1. complete branch implementation;
2. open draft PR to `main`;
3. run CI on the exact PR head;
4. inspect receipt and readiness artifact;
5. operator review;
6. merge decision for this PR;
7. exact-main verification;
8. rerun or refresh PR #50 under corrected workflow;
9. only then decide PR #50 merge;
10. update readiness ledger separately after exact-main identity evidence.

### Acceptance criteria

- checked-out SHA equals expected SHA;
- mismatch exits nonzero;
- receipt is schema-valid;
- readiness `source_revision` equals expected SHA;
- artifact name contains expected SHA;
- existing CI gates remain present;
- full tests pass;
- no secret, credential, deployment, external action, or readiness-status change;
- rollback remains one bounded revert.

### Definition of done

A reviewed PR demonstrates green CI on its exact head, uploads both revision and readiness receipts named for that head, receives operator merge authorization, merges with expected-head protection, and passes exact-main verification.

### Operator approvals

Required for merge. No self-approval by software. This cycle does not execute the merge.

### Blockers

- CI must pass on the final branch head;
- artifact contents must show exact revision equality;
- unresolved mandatory findings or review threads block merge;
- exact-main verification remains required after merge.

### Risk register

| Risk | Likelihood | Impact | Control |
|---|---|---|---|
| GitHub event field absent | Low | Medium | fallback to `github.sha`; strict SHA validation |
| Wrong revision selected | Low | High | actual checkout comparison and fail-closed exit |
| Readiness still binds default SHA | Medium | High | verified revision-bound readiness wrapper and assertion |
| Receipt omitted after failure | Medium | Medium | build/write receipt before mismatch exit where input is valid; artifact upload uses `always()` |
| Workflow regression | Medium | High | workflow-wiring tests and full CI |
| False implication of approval | Low | High | receipt explicitly requires operator review and grants no authority |

### Estimated readiness-score impact

**0 direct points in this PR.** Governance evidence confidence improves, but capability maturity and blocker state do not change. A future ledger model may score evidence provenance separately after reviewed adoption.

### Exact separate branch/PR plan

- Branch: `codex/ci-exact-revision-evidence-gate-v1`.
- Base: `main` at `b76d6ac966ef41df00066db4bbbbead64eec8dd6`.
- PR title: `fix(ci): bind assurance evidence to exact revision`.
- PR state: draft until final exact-head CI succeeds.
- Merge method: operator-controlled squash with expected-head protection.
- Post-merge: exact-main CI and artifact verification before PR #50 integration resumes.

## 11) Workflow Procurement Procedure

`intake -> evidence verification -> scope lock -> contract-first design -> implementation plan -> security/privacy wiring -> tests -> CI -> operator review -> merge decision -> post-merge verification -> readiness-ledger update`.

Applied here:

- intake: reconcile PR #50 exact-head claim;
- evidence verification: inspect PR, workflow, run, job, and artifact;
- scope lock: CI evidence only;
- contract-first design: revision receipt schema first;
- implementation: verifier, CLIs, workflow wiring;
- security/privacy: read-only permissions, no secrets, redaction retained;
- tests and CI: exact-revision and full regression gates;
- operator review and merge: pending;
- post-merge and ledger: explicitly deferred.

## 12) Engine Evolution v+1

Add a **Provenance-Aware Evidence Graph** to the evolution/procurement engine. Replace path-existence-only evidence with bounded nodes and edges for revision, artifact digest, producing command, CI run, gate result, evidence strength, freshness, and review authority. First bounded increment: require every cycle receipt to include `expected_revision`, `actual_revision`, `evidence_subject`, and `evidence_strength`, and reject a cycle when those values conflict.

This improvement is proposed, not implemented in this PR.

## 13) Next-Run Directive

Inspect only the exact-revision evidence train:

1. read the final PR head SHA;
2. verify the workflow checked out that exact SHA;
3. verify the revision receipt has equal expected and actual SHA;
4. verify the readiness report `source_revision` equals that SHA;
5. verify the artifact name equals that SHA;
6. verify every CI step passed;
7. verify no unresolved review thread or mandatory finding;
8. if merged, verify exact-main CI and receipts;
9. refresh PR #50 under the corrected workflow;
10. do not begin transactional persistence until PR #50 integration and the separate readiness reconciliation are complete.

## Updated transformation backlog

1. **Exact Revision Evidence Gate v1** — implemented on review branch; CI/review pending.
2. **PR #50 exact-head revalidation and controlled integration** — blocked by item 1.
3. **Production-readiness ledger reconciliation** — change identity access to at most `partial` only after exact-main behavioral evidence.
4. **Transactional identity persistence contract and SQLite implementation** — next capability train after item 3.
5. **Security/Privacy and Observer Authority adapter integration tests**.
6. **Evidence graph and operational-evidence maturity model**.
7. **Stale draft PR triage for #11, #15, and #21**.
8. **Deployment, recovery, connectors, and hosted observer portal** — remain deferred and production-blocking where registered.

## Updated governance summary

AEC-001 remains ratified. Operator control, fail-closed decisions, Security & Privacy Wiring, rollback, no direct main write, no unsupported production claim, and no external action remain unchanged. This cycle corrects CI evidence semantics on a separate branch and does not approve, merge, deploy, or change readiness status.
