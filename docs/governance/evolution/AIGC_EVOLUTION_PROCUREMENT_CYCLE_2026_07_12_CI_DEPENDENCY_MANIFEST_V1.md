# AIGC Evolution and Procurement Cycle — CI Dependency Manifest v1

**Cycle date:** 2026-07-12  
**Scope:** AIGC only  
**Base:** `main@293de53489fe7212fad272c01c698c0ffe2da610`  
**Branch:** `codex/ci-action-sha-pinning-main-v1`  
**Review PR:** #74  
**Readiness-score impact:** `0.0`  
**External action performed by AIGC runtime:** `false`

## 1. Evolution Diagnosis

### Ontology health

The action-pinning branch distinguishes readable compatibility labels from executable dependency identity. The remaining weakness was that the reviewed action set lived only as a Python constant in one test file. That made test implementation and governance policy the same artifact and left no independent machine-readable procurement record.

The corrected ontology adds:

- `DEPENDENCY_MANIFEST` as the reviewed policy record;
- `WORKFLOW_REFERENCE` as observed executable wiring;
- `APPROVED_REVISION` as the permitted immutable action identity;
- `EXPECTED_OCCURRENCE` as wiring cardinality;
- `UPDATE_POLICY` as a fail-closed governance boundary.

### Taxonomy completeness

Added classes:

- `SCHEMA_BACKED_DEPENDENCY_RECORD`;
- `REPOSITORY_WIDE_WORKFLOW_SCAN`;
- `UNKNOWN_ACTION_BLOCK`;
- `OCCURRENCE_DRIFT_BLOCK`;
- `MUTABLE_REFERENCE_BLOCK`;
- `OPERATOR_REVIEW_REQUIRED`;
- `AUTOMATIC_MERGE_PROHIBITED`.

### Methodology coherence

Contract-first governance now applies to the dependency allowlist itself. The workflow is measured against a strict manifest instead of a hard-coded test dictionary.

### Architecture integrity

The change remains inside the CI evidence plane. It does not modify application runtime, API, UI, persistence, identity, connectors, or deployment.

### Production-readiness gaps

No product capability advances. Production identity, durable authenticated sessions, tenant isolation, recovery evidence, secret management, approved connectors, privacy operations, monitoring, accessibility verification, staging, and deployment authority remain unresolved.

### Governance stability

The manifest requires operator review, prohibits automatic merge, requires rollback, rejects unknown actions, and records `external_action_performed=false`.

### Evolution bottlenecks

1. Operator disposition of PR #74.
2. Exact-main verification after any approved merge.
3. PR #69 rebase or reconstruction after main movement.
4. Fresh dual-revision evidence for dependent trains.
5. Issue #66 lifecycle decisions.
6. Draft-PR coordination load.

### Dead logic

No new dead runtime logic is proven.

### Redundant modules

The Python allowlist constant is removed as the policy authority. The test remains the enforcement mechanism and the JSON manifest becomes the source of dependency truth.

### Fragile structures

The prior test inspected one workflow path. The new test recursively inspects every `.yml` and `.yaml` workflow under `.github/workflows`, closing a future-workflow bypass path.

## 2. Contender Arena

| Rank | Identity | Strategy | Strengths | Weaknesses | Vector | Contribution |
|---:|---|---|---|---|---|---|
| 1 | Manifest Sentinel | Strict manifest plus repository-wide workflow validation | Bounded, machine-readable, reusable | Manifest maintenance required | Supply-chain governance | Selected |
| 2 | Python Allowlist | Retain the in-test dictionary | Simple | Policy and enforcement remain coupled | Local testing | Superseded |
| 3 | Workflow-Local Comments | Treat SHA comments as the registry | Readable | Not structured or independently validatable | Documentation | Supporting only |
| 4 | Dependabot Steward | Propose action updates | Reduces manual discovery | Does not perform review | Maintenance | Future companion |
| 5 | CODEOWNERS Gate | Require workflow review | Clear accountability | Limited independence for one operator | Human governance | Future |
| 6 | Vendored Actions | Commit action source locally | Maximum control | High maintenance and duplication | Repository sovereignty | Deferred |
| 7 | Attestation Gate | Verify upstream provenance | Strong mature assurance | Larger tooling surface | Supply-chain maturity | Deferred |

The selected synthesis combines immutable SHA pins, a strict manifest, repository-wide scanning, explicit occurrence counts, negative contract tests, operator review, and rollback.

## 3. Auto-Design Output

### Added artifacts

- `governance/ci/ci_action_dependency_manifest_v1.json`;
- `governance/schemas/ci/ci_action_dependency_manifest.schema.json`.

### Interface

```text
all workflow files
-> uses-reference extractor
-> full-SHA validator
-> dependency manifest
-> action-set comparison
-> revision comparison
-> occurrence comparison
-> CI gate
```

### Conceptual rules

- a compatibility label is not executable identity;
- a manifest entry is policy, not approval to merge;
- an unknown action is blocking;
- a changed action revision is blocking;
- a changed occurrence count is blocking;
- a local action is outside this third-party manifest.

## 4. Auto-Engineer Output

The test suite now:

1. validates the manifest against Draft 2020-12;
2. requires unique action repositories;
3. requires review and rollback controls;
4. recursively discovers all workflow files;
5. extracts all non-local `uses:` references;
6. requires full lowercase 40-character SHAs;
7. rejects unknown actions;
8. rejects revision drift;
9. rejects occurrence drift;
10. proves the schema rejects automatic merge and mutable revision values.

## 5. Auto-Architect Output

```text
Governance plane
  dependency manifest + update policy
Evidence plane
  workflow scan + tests + CI receipts
Control plane
  GitHub Actions workflows
Data plane
  repository files + artifacts
```

The manifest is reusable by future review packets, dependency-update tooling, and procurement reports without making the test file the sole policy store.

## 6. Cognitive and Analytical Review

The improvement is justified by direct branch evidence: the previous test defined `APPROVED_ACTION_REVISIONS` internally and read only `.github/workflows/aigc-ci.yml`. A new workflow could therefore exist outside the inspected path. The new design separates policy from enforcement and scans the complete workflow directory.

Tradeoffs:

- policy clarity improves, but manifest updates become mandatory;
- occurrence counts catch silent wiring expansion, but legitimate reuse requires an explicit reviewed update;
- strict unknown-action rejection can slow experimentation, which is appropriate at the CI execution boundary.

## 7. 2026 Societal Logic Integration

This change processes no production personal data and adds no user interface. It supports secure-software-development accountability, reproducible review, minimum-authority operation, and auditable dependency change control. Privacy, accessibility, deployment, and external-platform obligations remain unchanged and blocking where applicable.

## 8. Final Synthesis

```text
immutable action SHA
+ strict dependency manifest
+ all-workflow discovery
+ unknown-action rejection
+ occurrence-drift rejection
+ operator review
+ rollback
```

The metaphor is the **forge inventory seal**: every tool entering the forge is named, counted, revision-bound, and reviewable. The controls are the schema, manifest, scanner, tests, CI, and operator decision.

## 9. Single Highest-Impact Next Implementation Step

Add the schema-backed CI dependency manifest and make the action-pinning test validate every workflow against it.

## 10. Procurement Success Packet

### Objective

Create one machine-readable source of truth for approved CI actions and close the single-workflow inspection gap.

### Scope

- one strict schema;
- one dependency manifest;
- one strengthened test module;
- one cycle record;
- PR #74 description and evidence update.

### Non-scope

No application runtime, API, UI, persistence, identity, connector, deployment, runner-image, Python-dependency, or readiness-score change.

### Prerequisites

Exact current-main base, PR #74 branch, immutable pins, JSON Schema support, CI availability, and one-revert rollback.

### Dependency and evidence check

PR #74 already pins `checkout`, `setup-python`, and `upload-artifact`. The prior allowlist was embedded in `tests/test_ci_action_pinning.py`, and the prior workflow discovery was a single constant path.

### Affected ontology domains

Dependency identity, evidence provenance, CI governance, policy/enforcement separation, and rollback.

### Affected taxonomy classes

Manifest, workflow reference, approved revision, occurrence count, update policy, and blocking mismatch.

### Governing methodologies

Contract first, fail closed, least privilege, immutable dependency identity, bounded change, test-driven correction, and operator-controlled release.

### Architecture impact

CI evidence plane only.

### Required schemas/contracts

`governance/schemas/ci/ci_action_dependency_manifest.schema.json`

### Required config

`governance/ci/ci_action_dependency_manifest_v1.json`

### Required core modules

None. Enforcement remains a pure repository test.

### Required CLI/API/UI wiring

None.

### Persistence requirements

Repository files and standard CI evidence only.

### Security/privacy controls

Full SHAs, unknown-action rejection, manifest review gate, automatic-merge prohibition, rollback requirement, read-only workflow permissions, no secrets, and no personal data.

### Identity/authorization requirements

The named operator is accountable for review. CI validates; it does not authorize merge or release.

### Observability and audit requirements

Record manifest version, action repositories, approved revisions, compatibility labels, occurrence counts, branch head, workflow run, artifact, operator decision, and rollback revision.

### Tests

Schema-positive validation, unique action entries, review-policy invariants, all-workflow SHA validation, action-set equality, revision equality, occurrence equality, automatic-merge negative test, and mutable-revision negative test.

### CI gates

Contracts, AEC-001, content scan, procurement smoke stages, full tests, readiness evaluation without promotion, and artifact upload.

### Rollback plan

Before merge, abandon PR #74. After merge, revert the bounded PR and rerun exact-main CI. No data rollback.

### Migration plan

No data migration. PR #69 must preserve the manifest and update occurrence counts when its two-lane workflow is reconstructed against a changed main base.

### Documentation/runbook

This cycle record and the manifest update policy are the v1 runbook. A future controlled-update procedure should define upstream diff review and pin refresh cadence.

### Ownership

- implementation: repository operator;
- CI evidence: GitHub Actions;
- review and merge decision: Justice Gray Maciocha, separately exercised;
- deployment and external action: not authorized.

### Sequencing

```text
inspect prior pin test
-> define manifest contract
-> register approved actions
-> scan all workflows
-> add negative tests
-> CI
-> operator review
-> separate merge decision
-> exact-main verification
-> downstream revalidation
```

### Acceptance criteria

1. Manifest validates against its strict schema.
2. Every action repository is unique.
3. Operator review and rollback are required.
4. Automatic merge is prohibited.
5. Every workflow file is inspected.
6. Every external action uses a full SHA.
7. Unknown actions fail.
8. Revision drift fails.
9. Occurrence drift fails.
10. Full CI passes.
11. Readiness score remains unchanged.
12. PR remains draft and operator controlled.

### Definition of done

Branch-level completion requires committed artifacts and successful final-head CI. Mainline completion requires separate operator review, expected-head-protected merge authorization, exact-main verification, and downstream evidence refresh.

### Operator approvals

The requested cycle covers review-branch implementation and CI. Merge, deployment, credentials, connectors, production identity, external action, and readiness promotion are not granted.

### Blockers

Final-head CI, operator review, separate merge decision, exact-main verification, PR #69 reconstruction, and Issue #66 decisions.

### Risk register

| Risk | Consequence | Control | State |
|---|---|---|---|
| Manifest/test drift | false policy confidence | test consumes manifest directly | Closed on branch |
| New workflow bypass | uninspected action execution | recursive workflow scan | Closed on branch |
| Unknown action | expanded supply-chain surface | exact action-set equality | Closed on branch |
| Occurrence expansion | unnoticed execution growth | expected occurrence counts | Closed on branch |
| Stale pin | missed upstream fix | future reviewed update procedure | Open |
| Hosted runner drift | changing environment | future runner provenance | Open |
| Synthetic PR artifact | exact-head ambiguity | PR #69 dual-revision train | Blocking |

### Estimated readiness-score impact

`0.0`

### Exact separate branch/PR plan

Continue the coherent supply-chain train on branch `codex/ci-action-sha-pinning-main-v1`, PR #74, based on `main@293de53489fe7212fad272c01c698c0ffe2da610`. Keep the PR draft, preserve expected-head protection, and do not create an overlapping dependency-manifest PR.

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

No stage grants the authority of the next.

## 12. Engine Evolution v+1

Add a deterministic dependency-manifest review receipt that records the manifest digest, workflow digest set, observed action set, mismatch findings, source revision, and `external_action_performed=false`.

## 13. Next-Run Directive

Inspect only PR #74 final-head CI, manifest/workflow consistency, operator review state, main movement, and the resulting need to reconstruct PR #69 with preserved pins and corrected occurrence counts. Do not begin connectors, deployment, credentials, production identity, or automated dependency mutation.
