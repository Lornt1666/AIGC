# AIGC Evolution and Procurement Cycle — PR Graph Drift Importer v1

**Project scope:** AIGC only  
**Base:** `main@293de53489fe7212fad272c01c698c0ffe2da610`  
**Branch:** `codex/pr-dependency-graph-v1`  
**Draft PR:** #75  
**Readiness-score impact:** `0.0`  
**External action performed by AIGC runtime:** `false`

## 1. Evolution Diagnosis

The committed PR dependency graph converted repeated coordination prose into a strict topology, but it remained a static repository snapshot. It could not prove that its node state still matched GitHub. This cycle adds a read-only platform snapshot contract and drift evaluator.

The graph implementation PR creates a self-reference problem: committing its own final head would immediately change that head. The platform snapshot therefore records PR #75 explicitly while declaring a bounded `SELF_REFERENTIAL_IMPLEMENTATION_CHANGE` exclusion from the graph node set. The exclusion is visible, reviewable and advisory; it is not silently omitted.

No executable dead logic or redundant runtime module was identified. Fragile structures remain synthetic merge evidence, hosted-runner drift, unresolved lifecycle semantics, stale legacy PRs and operator review concentration.

## 2. Contender Arena

| Rank | Contender | Strategy | Result |
|---:|---|---|---|
| 1 | Drift Sentinel | Compare strict platform snapshot with graph | Selected |
| 2 | Direct GitHub mutation bot | Auto-update graph and branches | Rejected: authority expansion |
| 3 | Manual graph refresh | Continue human-only comparison | Rejected: non-adaptive |
| 4 | Label-only tracking | Encode blockers in GitHub labels | Deferred: weak revision binding |
| 5 | Unified capability snapshot | Combine PR, CI and readiness truth | Future synthesis |
| 6 | Scheduled read-only importer | Refresh snapshots and emit findings | Future operating mode |

## 3. Auto-Design Output

Added:

- strict platform-snapshot schema;
- one connector-derived, read-only snapshot;
- explicit self-change exclusion semantics;
- deterministic drift receipt model.

The snapshot records current main, open PR state, draft state, mergeability, branch, base/head revisions and Issue #66 state.

## 4. Auto-Engineer Output

Pipeline:

`load graph -> validate platform snapshot -> compare main -> compare graph nodes -> compare state/draft/branch/base/head/mergeability -> detect unregistered changes -> emit deterministic receipt`.

Blocking findings include:

- `MAIN_REVISION_CHANGED`;
- `GRAPH_NODE_MISSING_FROM_PLATFORM`;
- `PLATFORM_CHANGE_NOT_IN_GRAPH`;
- `STATE_CHANGED`;
- `DRAFT_STATE_CHANGED`;
- `BRANCH_CHANGED`;
- `BASE_REVISION_CHANGED`;
- `HEAD_REVISION_CHANGED`;
- `DECISION_GATE_STATE_CHANGED`.

`MERGEABILITY_CHANGED` is advisory because GitHub may recompute mergeability without a source revision change. The declared self-change exclusion is also advisory.

## 5. Auto-Architect Output

The implementation remains in the governance and evidence planes:

`GitHub read-only metadata -> platform snapshot -> graph drift evaluator -> receipt -> operator review`.

It does not rebase, edit PRs, submit reviews, merge, deploy or execute connectors from AIGC runtime.

## 6. Cognitive and Analytical Review

A static graph without drift comparison can become confidently wrong. A live mutation bot would solve freshness by weakening operator control. The selected design captures external state as explicit input and produces read-only findings.

The self-reference exclusion is necessary because a commit cannot truthfully contain the immutable final head of the PR that contains that same commit. The exclusion is narrow, typed and auditable.

## 7. 2026 Societal Logic Integration

The snapshot contains repository metadata rather than production personal information. It preserves least authority, no secrets, no production data, no automatic mutation and mandatory operator review. Future user interfaces remain subject to WCAG 2.2 AA engineering targets and applicable privacy/security obligations.

## 8. Final Synthesis

`strict graph + read-only platform snapshot + explicit self-reference handling + deterministic drift findings + operator control`.

The metaphor is a **living constellation chart**: the chart is compared with the sky, but it never moves the stars.

## 9. Single Highest-Impact Next Implementation Step

Implement the read-only graph-drift importer on PR #75. This is the bounded advancement in this cycle.

## 10. Procurement Success Packet

### Objective

Detect when the committed dependency graph diverges from current GitHub PR/issue metadata.

### Scope

Schema, snapshot, evaluator, CLI, tests and this record.

### Non-scope

No automatic snapshot refresh, repository write from runtime, PR edit, review, rebase, merge, deployment, credentials, connectors or readiness promotion.

### Prerequisites

Valid dependency graph, current main verification, read-only PR/issue metadata, JSON Schema support and CI.

### Dependencies and evidence

Current main remains `293de534...`; PR #74, PR #69 and Issue #66 remain the critical path. The snapshot records 13 open PRs plus one decision gate. Twelve PRs and the decision gate are graph-tracked; PR #75 is explicitly self-excluded.

### Ontology and taxonomy

Adds `PLATFORM_SNAPSHOT`, `DRIFT_RECEIPT`, `SELF_REFERENTIAL_IMPLEMENTATION_CHANGE`, blocking drift codes and advisory drift codes.

### Methodology

Contract first, read-only import, fail closed on material drift, deterministic receipts and operator-controlled correction.

### Architecture impact

Governance/evidence planes only.

### Required contracts and configuration

- `governance/schemas/evolution/pr_platform_snapshot.schema.json`
- `governance/evolution/pr_platform_snapshot_2026_07_12T142738Z.json`

### Core and CLI

- `src/core/pr_dependency_graph_drift.py`
- `src/pr_dependency_graph_drift_cli.py`

### Persistence

Repository snapshot plus optional JSON receipt. No database migration.

### Security/privacy and identity

No secrets, credentials, production data or platform write authority. Operator review remains mandatory. Automatic mutation is prohibited.

### Observability

Receipt records graph and snapshot digests, state digest, current main, node/change counts, exclusions, findings and conclusion.

### Tests

- current state with declared self exclusion;
- deterministic receipt identity across timestamp changes;
- head revision drift;
- unregistered platform change;
- missing platform node;
- main revision change.

### CI gates

Contract validation, AEC-001, content scanning, procurement smoke stages, full tests, readiness evaluation without promotion and artifact upload.

### Rollback and migration

Before merge, abandon or revert the PR branch changes. After a separately authorized merge, one bounded revert and exact-main CI are sufficient. Snapshot migration is replacement by a newly reviewed snapshot.

### Ownership and sequencing

Repository operator owns snapshot truth and review. CI supplies technical evidence only.

`verify live metadata -> create snapshot -> validate contract -> compare graph -> tests -> CI -> operator review -> merge decision -> exact-main verification`.

### Acceptance criteria

- snapshot validates;
- all IDs and numbers agree;
- exclusions are explicit and present;
- current graph matches current platform state except declared exclusions;
- material drift returns `DRIFT_DETECTED`;
- equivalent state has stable receipt identity;
- no automatic mutation or external action occurs;
- full CI passes.

### Definition of done

Branch-level completion requires green CI and final-head evidence. Mainline completion requires operator review, separate merge authorization and exact-main verification.

### Blockers and risks

Current blockers remain PR #74 disposition, PR #69 reconstruction and Issue #66 decisions. Risks include snapshot aging, self-exclusion misuse, omitted platform changes and treating read-only findings as authority. Controls are explicit exclusions, schema validation, fail-closed comparison and operator review.

### Exact branch/PR plan

Continue the coherent PR #75 branch `codex/pr-dependency-graph-v1`; do not create an overlapping implementation PR. Merge only through a separately authorized expected-head-protected decision.

## 11. Workflow Procurement Procedure

`intake -> evidence verification -> scope lock -> contract-first design -> implementation plan -> security/privacy wiring -> tests -> CI -> operator review -> merge decision -> post-merge verification -> readiness-ledger update`.

## 12. Engine Evolution v+1

Add a generated snapshot-request packet listing the exact connector queries and expected normalized fields required for the next read-only refresh. The packet must not execute connector writes or mutate the graph.

## 13. Next-Run Directive

Inspect PR #75 final head and CI. Compare current GitHub state with the recorded platform snapshot. Report only changed main, PR/issue state, base/head drift, mergeability drift, review movement, blockers, readiness and rollback state. Do not begin another runtime subsystem.

## Updated Registers

### Backlog

1. Review and disposition PR #74.
2. Exact-main verification after PR #74.
3. Reconstruct PR #69 and regenerate dual-revision evidence.
4. Resolve Issue #66.
5. Review PR #75.
6. Revalidate dependent trains.
7. Triage PRs #11, #15 and #21.

### Procurement register

- dependency graph: PR #75;
- read-only graph drift importer: PR #75;
- immutable CI dependency evidence: PR #74;
- dual-revision gate: PR #69;
- lifecycle decision gate: Issue #66;
- production readiness remains structural and unchanged.

### Governance summary

AIGC remains local, non-production, contract first, fail closed, rollback capable and operator controlled. This cycle creates no runtime authority and performs no consequential external action.
