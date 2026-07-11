# AIGC Evolution and Procurement Cycle — Exact Revision Evidence Gate v1

Status: **bounded implementation on a separate draft-review branch**  
Scope: **AIGC only**  
Current main evidence revision: `532c62150becdc1b0fa606ddeaeb70bc40197574`  
Implementation branch: `codex/ci-exact-revision-evidence-gate-v1-mainline`  
External action performed by AIGC runtime: `false`  
Deployment performed: `false`  
Readiness status changed: `false`

## 1) Evolution Diagnosis

### Ontology health

AIGC now contains a ratified constitutional substrate, shared assurance contracts, the Assurance Sensorium, review-packet logic, the Identity Scope Authorization Kernel, and the merged Principal Authority Binding v1.1 runtime. The authority ontology is substantially healthier than the earlier request-string model: principal, membership, session, policy, approval, revocation, purpose, context, and decision receipt are first-class concepts.

The evidence ontology is still incomplete. It lacks first-class `ExpectedRevision`, `CheckedOutRevision`, `WorkflowEvent`, `RevisionVerification`, `EvidenceBinding`, and `EvidenceStrength` entities at the CI boundary. The required relationship is:

`governed change -> expected immutable revision -> exact checkout -> validation execution -> revision-bound receipts -> review decision`.

### Taxonomy completeness

The recursive production architect currently recognizes ontology domains `code`, `infrastructure`, `devops`, `data`, and `risk`, and taxonomy dimensions `layer`, `function`, `lifecycle`, and `ownership`. This remains useful for inventory but insufficient for assurance. Required refinements are:

- evidence subject: PR head, synthetic merge candidate, main, release;
- evidence class: structural, semantic test, CI execution, staging observation, production observation;
- authority class: automated verification, AI advisory, operator, independent human, external provider;
- consequence class: internal, sensitive, external, production;
- freshness class: current, stale, superseded, unbound;
- reversibility class: revertible, migratable, externally irreversible;
- accessibility, privacy, recovery, compatibility, identity, and deployment maturity.

### Methodology coherence

Repository methodology consistently declares contract-first design, fail-closed behavior, exact-head review, operator control, rollback, Security & Privacy Wiring, and no unsupported completion claims. The previous CI workflow did not fully implement strict exact-head evidence on pull-request events. Run 633 succeeded for PR #50, but its uploaded readiness artifact was bound to synthetic merge revision `63197dc34ba0ef0ff2e8edaa0d3a714541445571` while the reviewed branch head was `fdfc0ea3622c2eb1b4043dbcb495079488bb4388`.

PR #50 was subsequently squash-merged as main revision `532c62150becdc1b0fa606ddeaeb70bc40197574`. This cycle does not invalidate the successful tests or the bounded implementation. It identifies that the repository cannot yet produce a machine-verifiable chain proving that expected revision, actual checkout, readiness `source_revision`, and artifact name are identical.

### Architecture integrity

Strengths:

- AEC-001 v1.0.0 is ratified and fail-closed;
- principal-authority semantics are merged as a synthetic local simulator;
- strict identity contracts and 36 mutation cases exist;
- CI includes contracts, AEC-001, secret scanning, procurement smoke stages, tests, readiness evaluation, and artifacts;
- runtime external execution remains blocked.

Integrity gap:

- CI relies on event-dependent GitHub revision semantics and does not emit a separate expected-versus-actual checkout receipt.

### Production-readiness gaps

Run 633 reported **53.9/100**, below the threshold of 90, using `structural_repository_evidence_v2`; the report explicitly disclaims operational proof. That score predates the PR #50 squash merge and is not authoritative for current main. No exact-main readiness receipt for `532c62150becdc1b0fa606ddeaeb70bc40197574` was retrieved in this cycle.

Registered blockers remain:

- `security_privacy_wiring`;
- `transactional_persistence`;
- `production_identity_access`;
- `approved_external_connectors`;
- `production_deployment`.

The ledger still declares `production_identity_access: unimplemented`; the merged local simulator may justify at most `partial`, but only after revision-bound exact-main verification and a separate ledger PR. The production blocker must remain active.

### Governance stability

AEC-001 remains ratified. Truth, evidence, human authority, deny-by-default authorization, privacy, accessibility, security, production readiness, repository governance, determinism, recoverability, and no-merge-with-unresolved-gates remain intact. This correction implements existing constitutional intent and does not amend the Constitution.

### Evolution bottlenecks

1. Current main lacks an exact-revision CI evidence receipt.
2. The readiness ledger is stale relative to merged identity runtime but cannot be reconciled honestly until exact-main evidence exists.
3. Transactional persistence is the next capability bottleneck only after evidence binding and ledger reconciliation.
4. The recursive architect's structural path checks do not measure runtime or operational evidence.

### Dead logic, redundancy, and fragile structures

- No executable module is proven dead.
- `maximum_cycles_per_run` can be configured above one, but the recursive architect unconditionally breaks after its first cycle; the multi-cycle setting is currently ineffective.
- Old draft PRs #11, #15, and #21 are stale integration surfaces requiring explicit rebase, supersession, or closure decisions.
- The procurement index still presents already-completed trains as future work and requires reconciliation.
- A first implementation branch for this correction was based on pre-merge main. It is preserved but superseded by the clean mainline reconstruction from `532c62150becdc1b0fa606ddeaeb70bc40197574`.
- The primary fragile structure corrected here is reliance on default pull-request checkout and event-dependent `GITHUB_SHA` without immutable evidence-subject verification.

## 2) Contender Arena

| Rank | Identity | Strategy | Strengths | Weaknesses | Evolutionary vector | Contribution to synthesis |
|---:|---|---|---|---|---|---|
| 1 | Exact Revision Evidence Gate | Explicitly select the evidence revision, check it out, compare with `git rev-parse HEAD`, emit a strict receipt, and bind readiness artifacts | Bounded, deterministic, directly repairs trust | Adds small CI and CLI surface | trustworthy provenance | Winning implementation |
| 2 | Full Evidence Provenance Graph | Model revisions, commands, tests, artifacts, digests, review authorities, and freshness | Strongest long-term assurance | Too broad for one cycle | supply-chain evidence | Engine v+1 direction |
| 3 | Exact Checkout Only | Set checkout `ref` to PR head or push SHA | Minimal workflow change | Does not independently prove the checkout or receipt binding | partial correction | Included but insufficient alone |
| 4 | Receipt-Only Verification | Compare expected and actual SHA after default checkout | Detects mismatch | Default PR merge-ref checkout would intentionally disagree | fail-closed detection | Included with explicit checkout |
| 5 | Post-Merge Main Verification Only | Treat current main as the sole evidence subject | Concrete integrated state | Does not repair future PR-head claims | integration assurance | Required after winner merges |
| 6 | Revert PR #50 | Remove merged identity runtime until provenance is corrected | Restores strict sequencing | Disproportionate; no behavioral failure evidence exists | conservative rollback | Rejected absent failure evidence |
| 7 | Readiness Ledger Update Now | Change identity access to partial immediately | Reconciles visible state | Would repeat the evidence-quality error | score alignment | Deferred |
| 8 | Transactional Identity Spine | Begin SQLite persistence | Major capability progress | Builds above unresolved provenance and stale ledger | durable authority | Deferred successor |
| 9 | External Attestation Service | Use hosted signing/provenance services | Strong future assurance | Credentials, integration, cost, and production scope | external assurance | Deferred option |

Pressure test: exact checkout without a receipt remains an assertion; a verifier without explicit checkout fails against GitHub's synthetic merge ref; a score change without exact-main evidence is premature. The strongest bounded hybrid is explicit evidence-subject selection + exact checkout + expected/actual comparison + strict receipt + revision-bound readiness execution + revision-named artifact.

## 3) Auto-Design Output

### Modules

- `CIRevisionEvidence`: canonical expected/actual revision verification.
- `RevisionBoundReadinessEntrypoint`: invokes the existing readiness engine only after exact revision verification.
- `CIRevisionEvidenceReceipt`: strict machine-readable audit contract.

### Interfaces

- `normalize_revision(value, label) -> sha`;
- `read_git_head(project_root) -> sha`;
- `build_receipt(expected_revision, actual_revision, event_name) -> receipt`;
- `verify_ci_revision(project_root, expected_revision, event_name) -> receipt`;
- `write_receipt(receipt, output_path) -> path`;
- readiness wrapper options: `--expected`, `--event`, `--project-root`, `--ledger`, `--artifact-root`.

### Conceptual framework

`Expected Revision Contract -> Exact Checkout -> Actual Revision Observation -> Equality Gate -> Evidence Receipt -> Existing CI Gates -> Revision-Bound Readiness -> Revision-Named Artifact`.

### Ontology expansion

Add `ExpectedRevision`, `ActualRevision`, `WorkflowEvent`, `RevisionObservation`, `RevisionVerificationReceipt`, and `EvidenceSubject`.

### Taxonomy refinement

Evidence-binding states: `VERIFIED_EXACT`, `MISMATCH`, `MALFORMED`, `UNAVAILABLE`. The v1 receipt uses `verified: true|false` and fails closed on mismatch or malformed SHA.

## 4) Auto-Engineer Output

Implemented pipeline on the review branch:

1. Resolve `AIGC_EXPECTED_REVISION` as pull-request head SHA or push SHA.
2. Check out that exact revision with full history.
3. Read `git rev-parse HEAD`.
4. Validate expected and actual values as full 40-character hexadecimal commit identifiers.
5. Compare them and emit `ci_revision_evidence_receipt.json`.
6. Fail the workflow on mismatch.
7. Run dependency installation, contract validation, AEC-001 validation, redaction scan, procurement smoke stages, and the full test suite.
8. Invoke the existing readiness engine through a revision-bound compatibility wrapper.
9. Assert the readiness report's `source_revision` equals the verified revision.
10. Upload the revision receipt and readiness report together under an artifact named with that revision.

No credentials, database migration, live identity, connector, deployment, approval, or external action is added.

## 5) Auto-Architect Output

### System architecture

`GitHub Event Context -> Expected Revision Resolver -> Exact Checkout -> Revision Evidence Gate -> Existing Validation Pipeline -> Revision-Bound Readiness Adapter -> Evidence Artifact`.

### Integration pattern

The readiness wrapper is an anti-corruption adapter around the existing engine. It preserves the current readiness API while providing a proven revision. A later contract revision should make `source_revision` an explicit argument and remove process-environment coupling.

### Macro-structure improvement

CI gains a declared evidence subject before validation begins. Downstream receipts can be traced to the same immutable revision. Pull-request-head evidence and post-merge-main evidence remain separate and both are required where governance says so.

### Cross-module coherence

- AEC-001 truth and evidence invariants govern the verifier.
- The readiness ledger remains the scoring authority.
- Revision evidence supplies provenance, not authorization.
- CI success supplies evidence, not review approval.
- Operator merge authority remains separate.

## 6) Cognitive and Analytical Review

The evidence supports a narrow correction, not a broad rollback. Run 633 demonstrates that the tested merge candidate passed all listed checks. It does not supply a strict receipt for PR head `fdfc0ea...`. PR #50 is now integrated on main; the responsible response is to bind future evidence exactly, verify the integrated main after the correction merges, and only then reconcile readiness.

Assumptions:

- GitHub Actions remains the CI platform;
- PR branches are in the same private repository;
- commit SHA is the immutable evidence identifier used by repository governance;
- this branch remains non-production and reversible.

Tradeoffs:

- PR-head checkout tests the reviewed implementation exactly but does not test merge integration; exact-main verification remains mandatory;
- full history is slightly slower but improves deterministic revision resolution;
- the compatibility adapter is minimal but should later be replaced by explicit revision injection;
- no direct readiness points are claimed, despite material assurance improvement.

Long-term stability improves because capability progress can no longer outrun evidence identity.

## 7) 2026 Societal Logic Integration

### Regulation and privacy

Canadian private-sector personal-information handling must be assessed against applicable federal and provincial requirements. The control follows PIPEDA-style accountability, identified purpose, collection limitation, safeguards, access, and challenge principles by storing only commit and CI metadata. It introduces no personal identity, credential, or behavioral profile.

For EU-facing use, the EU AI Act's phased obligations must be mapped to actual use case and risk class. This PR does not claim compliance. Revision-bound documentation, logging, traceability, and human-oversight evidence are supporting controls, not certification.

### Security and identity

NIST SP 800-63 Revision 4, finalized in July 2025, preserves separate identity-proofing, authentication, and federation assurance concerns and adds continuous-evaluation considerations. AIGC must retain IAL/AAL/FAL separation and cannot infer production identity maturity from CI provenance.

### Accessibility

Future cockpit and review surfaces should target WCAG 2.2 AA, including keyboard operation, visible and unobscured focus, status messages, understandable errors, target size, and accessible authentication. This change is CLI and workflow only.

### Organizational coordination

Automated CI verifies evidence; it does not approve or merge. The operator remains accountable. Independent human review is not claimed. Release-critical work retains its stronger review path.

### Platform constraints

GitHub documents that pull-request refs and `GITHUB_SHA` depend on event type and may represent a pull-request merge branch. AIGC therefore selects the intended evidence subject explicitly and verifies the actual checkout.

### Deployment feasibility

The correction uses existing GitHub Actions and Python infrastructure and requires no new service. It is feasible within the current private-repository model and remains fully revertible.

## 8) Final Synthesis

Make immutable revision identity the first gate in AIGC's assurance chain. The synthesis combines explicit evidence-subject selection, exact checkout, deterministic comparison, strict contract validation, fail-closed CI, revision-bound readiness reporting, revision-named artifacts, and operator-controlled review. It preserves the merged identity correction while repairing the evidence required to judge current and future changes honestly.

## 9) Single Highest-Impact Next Implementation Step

**Implement Exact Revision Evidence Gate v1.**

This remains the highest-impact immediate step because current main contains the identity runtime while its readiness status is stale and exact-main evidence is not yet bound by contract. Transactional persistence, connectors, or score changes should not advance until CI can prove what revision it validated.

## 10) Procurement Success Packet

### Objective

Guarantee that every AIGC CI validation and readiness artifact names and verifies the exact commit selected as its evidence subject.

### Scope and non-scope

Scope: pull-request and push revision selection; exact checkout; expected/actual comparison; strict receipt; revision-bound readiness; artifact upload; tests; cycle documentation; procurement-register reconciliation.

Non-scope: merge; deployment; credentials; live identity; SQLite; connectors; external action; production-readiness status mutation; branch-protection administration; PR #50 rollback.

### Prerequisites

- AEC-001 ratified;
- current main `532c62150becdc1b0fa606ddeaeb70bc40197574`;
- merged readiness engine and CI workflow;
- Python 3.12 CI runtime;
- separate branch and reviewed PR.

### Dependency and evidence check

Verified repository facts:

- PR #50 head: `fdfc0ea3622c2eb1b4043dbcb495079488bb4388`;
- PR #50 merged main revision: `532c62150becdc1b0fa606ddeaeb70bc40197574`;
- run 633 conclusion: success;
- run 633 readiness artifact source revision: `63197dc34ba0ef0ff2e8edaa0d3a714541445571`;
- run 633 readiness score: 53.9/100;
- exact-main receipt for `532c621...`: not established in this cycle;
- production-ready claim: false.

### Affected ontology domains

Evidence, DevOps, governance, readiness, audit, repository revision, review, identity integration.

### Affected taxonomy classes

CI event, evidence subject, expected revision, actual revision, verification state, evidence strength, freshness, artifact class, rollback class.

### Governing methodologies

Contract-first design, fail-closed validation, test-driven development, GitOps, least privilege, deterministic evidence, traceability, bounded PRs, operator review.

### Architecture impact

Adds one provenance gate before validation and one compatibility adapter before readiness generation. No AIGC application authorization path changes.

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
- no API or UI change.

### Persistence requirements

Write JSON receipts under `reports/artifacts` and upload them as CI artifacts. No database or migration.

### Security/privacy controls

Workflow permissions remain `contents: read`. No token, secret, personal data, or broad repository authority is added. Existing redaction scanning remains mandatory.

### Identity/authorization requirements

Revision provenance neither authenticates the operator nor grants merge authority. GitHub event context selects a candidate revision; operator review remains the decision gate.

### Observability and audit requirements

Record receipt ID, timestamp, event, expected SHA, actual SHA, verification result, evidence class, operator-review requirement, and `external_action_performed=false`. Upload with the readiness receipt.

### Tests

- equal revisions succeed;
- mismatch is recorded and fails closed;
- malformed and non-hex revisions fail;
- unknown events map to a bounded class;
- receipt validates against schema;
- readiness wrapper binds and restores process-local revision state;
- workflow contains exact checkout, verifier, revision-bound readiness, and artifact paths;
- full repository regression suite.

### CI gates

Exact revision verification; dependency install; contract validation; AEC-001 validation; redaction scan; procurement smoke stages; full tests; revision-bound readiness evaluation; artifact upload.

### Rollback plan

One squash revert removes the verifier, wrapper, tests, schema, documentation changes, and workflow wiring. No data rollback is required.

### Migration plan

No data migration. Historical artifacts retain original labels and must not be rewritten. New runs adopt the exact-revision contract.

### Documentation/runbook

This cycle report and the updated procurement index define the evidence defect, operating sequence, review gate, rollback, and next inspection.

### Ownership

Accountable operator: Justice Gray Maciocha / Lornt / Satoshi. Automated CI is evidence-producing only. Independent human review is not claimed.

### Sequencing

1. implement on clean current-main branch;
2. open draft PR;
3. run exact-head CI;
4. inspect revision and readiness receipts;
5. operator review;
6. expected-head-protected squash merge decision;
7. verify the new exact main, which includes PR #50 and this correction;
8. open separate readiness-ledger reconciliation to at most `partial` for production identity access;
9. procure transactional identity persistence afterward.

### Acceptance criteria

- actual checkout SHA equals expected SHA;
- mismatch exits nonzero;
- receipt is schema-valid;
- readiness `source_revision` equals expected SHA;
- artifact name contains expected SHA;
- all existing gates remain present;
- full tests pass;
- no credential, production data, deployment, external action, or readiness-status change;
- rollback is one bounded revert.

### Definition of done

A draft PR demonstrates green CI on its final exact head, uploads both revision and readiness receipts named for that head, receives operator review, merges with expected-head protection, and passes exact-main verification. This cycle stops before merge.

### Operator approvals

Operator approval is required for merge. Software cannot self-approve. No merge authorization is inferred from this document.

### Blockers

- final-head CI success;
- receipt equality and artifact inspection;
- no unresolved mandatory finding or review thread;
- post-merge exact-main verification;
- readiness update remains a separate PR.

### Risk register

| Risk | Likelihood | Impact | Control |
|---|---|---|---|
| GitHub event field absent | Low | Medium | fallback to push SHA; strict validation |
| Wrong revision selected | Low | High | expected/actual comparison and fail-closed exit |
| Readiness inherits event-default SHA | Medium | High | verified revision-bound wrapper and postcondition assertion |
| Receipt omitted after malformed input | Medium | Medium | fail visibly; artifact upload remains `always()` |
| Workflow regression | Medium | High | workflow-wiring tests and full CI |
| Evidence mistaken for approval | Low | High | receipt requires operator review and grants no authority |
| Branch becomes stale during review | Medium | Medium | expected-head protection and current-base reconstruction |

### Estimated readiness-score impact

**0 direct points.** Evidence confidence improves, but registered capability status and blockers do not change in this PR. The later identity-ledger reconciliation may alter the calculated score, but only after exact-main evidence.

### Exact separate branch/PR plan

- Branch: `codex/ci-exact-revision-evidence-gate-v1-mainline`.
- Base: `main` at `532c62150becdc1b0fa606ddeaeb70bc40197574`.
- PR title: `fix(ci): bind assurance evidence to exact revision`.
- State: draft until final exact-head CI and artifact inspection succeed.
- Merge: operator-controlled squash with expected-head protection.
- Post-merge: exact-main CI and receipt verification before readiness reconciliation.
- Superseded branch/PR: preserve the earlier pre-mainline reconstruction for audit; do not merge it.

## 11) Workflow Procurement Procedure

`intake -> evidence verification -> scope lock -> contract-first design -> implementation plan -> security/privacy wiring -> tests -> CI -> operator review -> merge decision -> post-merge verification -> readiness-ledger update`.

Applied here:

- intake: reconcile exact-revision claims after PR #50 integration;
- evidence verification: inspect PR, workflow, run, job, artifact, and current main;
- scope lock: CI provenance only;
- contract-first: receipt schema before workflow adoption;
- implementation: verifier, CLIs, exact checkout, artifact wiring;
- security/privacy: read-only permissions, no secrets, redaction retained;
- tests and CI: pending on final PR head;
- operator review and merge: pending;
- post-merge and readiness ledger: explicitly separate.

## 12) Engine Evolution v+1

Add a **Provenance-Aware Evidence Graph** to the evolution/procurement engine. Replace path-existence-only evidence with bounded nodes and edges for revision, artifact digest, producing command, CI run, gate result, evidence strength, freshness, and review authority. The first increment should require every cycle receipt to contain `expected_revision`, `actual_revision`, `evidence_subject`, and `evidence_strength`, and reject a cycle when they conflict.

This engine change is proposed, not implemented here.

## 13) Next-Run Directive

Inspect only the exact-revision evidence and integrated-main train:

1. read the final draft-PR head SHA;
2. verify checkout equals that SHA;
3. inspect the revision receipt for exact equality;
4. inspect readiness `source_revision` for the same SHA;
5. verify the artifact name contains that SHA;
6. verify every mandatory CI step passed;
7. inspect unresolved review threads and findings;
8. if merged, verify the new exact main and receipts;
9. only then procure the separate readiness-ledger update from `unimplemented` to at most `partial` for production identity access;
10. begin transactional identity persistence only after that reconciliation.

## Updated prioritized transformation backlog

1. **Exact Revision Evidence Gate v1** — implemented on clean current-main branch; CI and review pending.
2. **Exact-main verification of the combined identity runtime and provenance gate**.
3. **Production-readiness ledger reconciliation** — identity access to at most `partial`; blocker retained.
4. **Transactional identity persistence contract and SQLite implementation**.
5. **Security/Privacy and Observer Authority adapter integration tests**.
6. **Provenance-aware evidence graph and operational-evidence maturity model**.
7. **Stale draft PR triage for #11, #15, and #21**.
8. **Deployment, recovery, approved connectors, and hosted observer portal** — deferred.

## Updated governance summary

AEC-001 remains ratified. PR #50 is merged as a local `IAL0/AAL0/FAL0` simulator, not production identity. Operator control, fail-closed decisions, Security & Privacy Wiring, rollback, no direct main write, no unsupported production claim, and no external action remain unchanged. This cycle corrects CI evidence semantics on a separate branch and performs no merge or deployment.
