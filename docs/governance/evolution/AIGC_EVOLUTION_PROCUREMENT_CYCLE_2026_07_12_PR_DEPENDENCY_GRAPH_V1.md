# AIGC Evolution and Procurement Cycle — PR Dependency Graph v1

**Cycle date:** 2026-07-12  
**Project scope:** AIGC only  
**Base:** `main@293de53489fe7212fad272c01c698c0ffe2da610`  
**Branch:** `codex/pr-dependency-graph-v1`  
**Draft PR:** #75  
**Readiness-score impact:** `0.0`  
**External action performed by AIGC runtime:** `false`

## 1. Evolution Diagnosis

### Ontology health

AIGC distinguishes evidence, authority, technical validation, operator decision, internal capability, production operation and external action. The repository lacked one canonical object for active PR dependencies, decision gates, stale-base conditions and evidence invalidation triggers. Those relationships were repeated in prose across PR descriptions and issue comments.

This cycle introduces a machine-readable dependency graph and a deterministic read-only status receipt. The graph does not modify branches, approve reviews or merge changes.

### Taxonomy completeness

The graph adds the following governed classes:

- `PULL_REQUEST` and `DECISION_GATE` nodes;
- `CRITICAL_PATH`, `DEPENDENT` and `BACKLOG` criticality;
- `requires`, `blocks`, `conflicts_with` and `revalidate_after` edges;
- `DUAL_REVISION`, `MERGE_CANDIDATE_ONLY`, `STRUCTURAL_ONLY`, `DECISION_REQUIRED`, `STALE_BASE` and `BLOCKED` evidence states;
- `IMMUTABLE_HEAD`, `MERGE_CANDIDATE`, `STRUCTURAL_REPOSITORY` and `DECISION` evidence subjects.

### Methodology coherence

The former method was documentary coordination. The new method is:

`repository evidence -> strict graph contract -> semantic validation -> topological evaluation -> staleness and blocker receipt -> operator review`.

### Architecture integrity

The addition is confined to the governance and evidence planes. It adds no application runtime, persistence, API, UI, connector, identity or deployment authority.

### Production-readiness gaps

Production identity, durable authenticated sessions, tenant separation, secret management, approved connectors, privacy operations, backup/recovery exercises, monitoring, accessible complete workflows, staging and deployment remain incomplete. Structural readiness is not promoted by this change.

### Governance stability

Operator review remains mandatory. Automatic merge is prohibited. No direct write to `main`, merge, deployment, credentials, connector execution or production data processing occurred.

### Evolution bottlenecks

1. Operator disposition of PR #74.
2. Exact-main verification after any approved PR #74 merge.
3. Reconstruction and revalidation of PR #69.
4. Issue #66 lifecycle decisions.
5. Dependent PR revalidation.
6. Legacy PR triage.
7. Canonicalization of PR #69 and PR #71 procedure authority.

### Dead logic

No new executable dead logic was proven. The graph instead exposes non-adaptive coordination paths and unresolved dependencies.

### Redundant modules and records

No executable module is supported for deletion. Repeated dependency prose is reduced by one canonical graph. PR #69 and PR #71 remain overlapping governance authorities.

### Fragile structures

The graph identifies three stale-base PRs (#11, #15 and #21), eight blocked nodes and an unresolved procedure conflict. It also records that current branch evidence frequently represents synthetic merge candidates rather than immutable heads.

## 2. Contender Arena

| Rank | Identity | Strategy | Strength | Weakness | Evolution vector | Contribution |
|---:|---|---|---|---|---|---|
| 1 | Dependency Cartographer | Strict PR graph plus staleness evaluator | Reduces coordination ambiguity | Requires maintained snapshots | Governance throughput | Selected |
| 2 | Review Queue Ledger | Flat priority list | Simple | Cannot express graph dependencies | Operator throughput | Partial |
| 3 | Automated Rebase Steward | Rebase stale PRs automatically | Fast | Violates operator-control boundary | Automation | Rejected |
| 4 | GitHub Label Topology | Encode states in labels | Visible | Weak revision provenance | Coordination | Future supplement |
| 5 | Merge Train | Serial automatic integration | High throughput | Premature and authority-expanding | Release automation | Rejected |
| 6 | Evidence Staleness Receipt | Receipt without canonical graph | Auditable | Lacks source-of-truth relationships | Evidence | Hybrid component |
| 7 | Manual Triage Only | Continue prose coordination | No code cost | Duplicated and non-adaptive | Static governance | Rejected |
| 8 | Unified Capability Snapshot | Merge PR, readiness and runtime evidence | Strong long-term model | Too broad for one cycle | System coherence | Future synthesis |

The selected synthesis combines a strict graph, deterministic receipt, fail-closed semantic tests and operator-controlled updates.

## 3. Auto-Design Output

### Modules

- `pr_dependency_graph.schema.json` — strict contract.
- `pr_dependency_graph_v1.json` — current graph snapshot.
- `pr_dependency_graph.py` — validation, topological ordering and status evaluation.
- `pr_dependency_graph_cli.py` — read-only receipt generation.

### Interfaces

`graph JSON -> schema validator -> semantic validator -> topological evaluator -> status receipt`.

### Conceptual framework

A dependency is not approval. A blocking edge is not an automatic branch action. Evidence freshness is revision-bound. Role consolidation is not independent review.

## 4. Auto-Engineer Output

The implementation validates:

- unique change identifiers;
- identifier and issue/PR number agreement;
- known relationship targets;
- no self-relations;
- symmetric conflicts;
- mirrored `blocks` and `requires` relations;
- acyclic requirements;
- current-main base comparison;
- unresolved dependencies;
- decision-required states.

The CLI writes a deterministic receipt containing graph digest, node and edge counts, topological order, stale-base nodes, blocked nodes, critical path, operator review queue and findings.

## 5. Auto-Architect Output

Target architecture:

`Governance plane (graph contract and operator decisions) -> Evidence plane (status receipt and revision evidence) -> Control plane (CI and local services) -> Data plane (repository, SQLite and artifacts)`.

Future PR #69 integration should provide immutable-head and merge-candidate evidence to the graph evaluator without giving the evaluator mutation authority.

## 6. Cognitive and Analytical Review

The repository has more reviewable branches than reviewed mainline throughput. The principal bottleneck is coordination and accountable disposition, not idea generation. Creating another runtime subsystem would increase branch entropy. A graph is justified because it reduces repeated truth surfaces and makes stale assumptions measurable.

Tradeoffs include manual graph refresh, snapshot aging and the risk of treating the graph as live GitHub state. The graph is therefore explicitly a recorded snapshot, not an autonomous repository controller.

## 7. 2026 Societal Logic Integration

The graph processes repository metadata, not production personal information. Future production operation remains subject to applicable Alberta and federal privacy requirements, security safeguards, accessible interaction standards, platform terms and explicit organizational accountability.

The change preserves least authority, no secrets, no personal data, no external connectors and no automated merge. Future operator interfaces should target WCAG 2.2 Level AA.

## 8. Final Synthesis

The strongest advancement is:

`exact repository evidence + dependency graph + staleness findings + operator review + expected-head merge controls + post-merge verification`.

The mythic metaphor is a **Constellation Chart**: nodes are review trains, edges are gravitational constraints, and the operator remains the navigator. The concrete controls are schemas, revisions, graph invariants, tests, receipts and review gates.

## 9. Single Highest-Impact Next Implementation Step

Create a schema-backed PR dependency graph and deterministic staleness evaluator. This is implemented on PR #75.

Measured initial result:

- 13 graph nodes;
- 12 PR nodes;
- 1 decision gate;
- 10 dependency edges;
- 3 stale-base PRs;
- 8 blocked nodes;
- 4 critical-path nodes;
- conclusion `VALID_WITH_BLOCKERS`.

## 10. Procurement Success Packet

### Objective

Replace repeated prose-based PR coordination with a strict, reviewable dependency graph and read-only status receipt.

### Scope

Schema, graph snapshot, evaluator, CLI, tests and this cycle record.

### Non-scope

No rebase, branch mutation, review submission, merge, deployment, credentials, connectors, API/UI change, database migration or readiness promotion.

### Prerequisites

Verified main revision, current PR/issue metadata, JSON Schema support, separate branch, CI and rollback path.

### Dependency and evidence check

Current main is `293de534...`. PR #74 is open and unreviewed. PR #69 is the dual-revision assurance train. Issue #66 remains a decision gate. Legacy PRs #11, #15 and #21 use older bases.

### Affected ontology domains

Governance, review sequencing, evidence freshness, blocker identity and operator authority.

### Affected taxonomy classes

Node kinds, criticality, relationship types, evidence states, evidence subjects and invalidation triggers.

### Governing methodologies

Contract first, fail closed, evidence based, least authority, bounded change, deterministic output and operator-controlled release.

### Architecture impact

Governance/evidence planes only.

### Required schemas and contracts

`governance/schemas/evolution/pr_dependency_graph.schema.json`.

### Required config

`governance/evolution/pr_dependency_graph_v1.json`.

### Required core modules

`src/core/pr_dependency_graph.py`.

### Required CLI/API/UI wiring

CLI only. No API or UI wiring.

### Persistence requirements

Repository JSON and optional generated report files. No database migration.

### Security/privacy controls

No secrets, personal data, credentials, external action or permission expansion. Security & Privacy Wiring Gate remains unchanged.

### Identity/authorization requirements

The operator identity is recorded. CI and the evaluator provide evidence only. Merge and deployment decisions remain separate.

### Observability and audit

Record graph digest, snapshot time, current main, node/edge counts, topological order, stale and blocked nodes, critical path and findings.

### Tests

Positive graph evaluation, deterministic receipt, unknown dependency rejection, cycle rejection and asymmetric-conflict rejection.

### CI gates

Contract validation, AEC-001, content scanning, procurement smoke stages, full tests, readiness evaluation without promotion and artifact upload.

### Rollback plan

Close or abandon PR #75 before merge. After a separately approved merge, revert the bounded squash commit and rerun exact-main CI.

### Migration plan

No data migration. Refresh graph revisions after any base/head state change.

### Documentation/runbook

This document and the CLI help text.

### Ownership

Repository operator implements and reviews. CI supplies technical evidence. Independent review is not claimed.

### Sequencing

`inspect -> scope lock -> contract -> graph -> evaluator -> tests -> CI -> operator review -> merge decision -> exact-main verification -> graph refresh`.

### Acceptance criteria

Strict schema; all references known; no cycles; symmetric conflicts; mirrored block/require edges; correct stale-base detection; deterministic receipt; tests and CI pass; no authority expansion.

### Definition of done

Branch-level done requires final CI success and a draft PR. Mainline done requires operator review, separate merge decision and exact-main verification.

### Operator approvals

The cycle permits review-branch implementation and CI only. It does not permit merge, deployment, credentials, connectors, external action or readiness promotion.

### Blockers

PR #74 review, exact-main verification, PR #69 reconstruction, Issue #66 decisions and dependent train revalidation.

### Risk register

| Risk | Consequence | Control |
|---|---|---|
| Snapshot becomes stale | Incorrect coordination | revision fields and required refresh |
| Missing node | Incomplete review queue | explicit inventory tests in future v+1 |
| Cyclic dependencies | Deadlocked train | fail-closed cycle detection |
| Asymmetric relationship | Conflicting truth | semantic validation |
| Graph treated as authority | Governance bypass | read-only evaluator and operator gates |
| New PR increases review load | Additional coordination | bounded scope and critical-path priority |

### Estimated readiness impact

`0.0`. Governance observability improves; runtime capability does not.

### Exact branch/PR plan

- branch `codex/pr-dependency-graph-v1`;
- base `main@293de53489fe7212fad272c01c698c0ffe2da610`;
- draft PR #75;
- expected-head-protected squash only after separate approval;
- rollback by branch abandonment or one revert.

## 11. Workflow Procurement Procedure

`intake -> evidence verification -> scope lock -> contract-first design -> implementation plan -> security/privacy wiring -> tests -> CI -> operator review -> merge decision -> post-merge verification -> readiness-ledger update`.

Each stage is separate and does not grant the authority of the next.

## 12. Engine Evolution v+1

Add a connector-fed snapshot importer that accepts explicit GitHub PR metadata as input, compares it with the committed graph and emits drift findings. It must remain read-only and must not update branches, PRs, reviews or merge state.

## 13. Next-Run Directive

Inspect only PR #75 final CI and graph accuracy. Verify current main, PR #74 head/review state, PR #69 dependency sequencing, Issue #66 state, stale-base findings and any new or closed PRs. If the graph differs from repository reality, update PR #75 on the same branch and rerun CI. Do not begin another runtime subsystem.

## Updated Registers

### Production-readiness assessment

Structural score remains unchanged and production readiness remains false. The graph improves governance observability only.

### Prioritized backlog

1. Operator review of PR #74.
2. Exact-main verification after PR #74.
3. Rebuild and validate PR #69.
4. Resolve Issue #66.
5. Revalidate dependent PRs.
6. Review PR #75 and adopt the graph.
7. Triage stale PRs #11, #15 and #21.
8. Reconcile PR #69/#71 authority overlap.

### Procurement register

- PR dependency graph: implemented on PR #75, CI pending.
- Immutable action/dependency receipt: PR #74, review pending.
- Dual-revision gate: PR #69, downstream of #74.
- Persistence readiness reconciliation: PR #70, dependent.
- Single-snapshot engine correction: PR #72, dependent.
- Lifecycle decision gate: Issue #66, unresolved.

### Governance summary

AIGC remains local, non-production, contract first, fail closed, operator controlled and blocked from external action by default. This cycle converts review-train dependency claims from repeated prose into one validated graph without granting the graph execution authority.
