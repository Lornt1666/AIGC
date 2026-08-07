# AIGC Nexus Convergence Manifest V1

Status: `DISCOVERY_BASELINE_V1_ADVANCED_MEASURED`
Integration train: `release/aigc-nexus-v1`
Governing migration law: Evolutionary Convergence — No Stranded Capability

## Purpose

Provide an evidence-backed decision surface for converging historical AIGC capability into one canonical Nexus V1 product. This manifest remains intentionally non-destructive: it identifies what should be studied, adapted, fused, shadowed, or deferred before any archive/remove ChangeSet is proposed.

## Exact measured discovery baseline

Baseline repository-intelligence evidence was bound to exact head `8eeb7eae57c41c957bbc66347307057a3ca66c60` and exact-head CI #2544.

Advanced Stage-1 measurements are bound to:

- exact head: `3f714959203594b753085af4be03259896a0e64d`;
- AIGC CI: `#2558` / run ID `31182185660` / `SUCCESS`;
- retained artifact ID: `8995258580`;
- artifact digest: `sha256:c5990e1ec84042d1be64f45a335f0467daf4ef04dd94e076dcd745ca9ad103cf`;
- detailed record: `docs/architecture/AIGC_NEXUS_STAGE1_ADVANCED_MEASUREMENTS_V1.md`.

No measurement in this manifest grants deletion, archival, merge, deployment, provider-execution, procurement, or retirement authority.

## Measured repository facts

| Metric | Value | Convergence meaning |
|---|---:|---|
| total files at advanced head | 1010 | repository scale requires automated convergence analysis |
| source files | 247 | capability migration must be module-aware |
| test files | 138 | substantial test evidence exists and should be migrated with capability |
| documentation files | 234 | documentation convergence remains a major workstream |
| configuration/schema files | 301 | contract/schema fusion remains a major consolidation surface |
| infrastructure files | 18 | infrastructure surface remains comparatively bounded |
| schemas analyzed | 155 | contract consolidation must be systematic |
| schemas with observed static callers | 94 | caller evidence is available for most, but not all, schemas |
| direct test ownership | 47.97% baseline | direct imports alone leave a large evidence gap |
| transitive static test reachability | 53.44% | indirect imports close part, not all, of the ownership gap |
| remote branches | 133 | branch-topology saturation is quantitatively confirmed |
| direct requirements | 11 | dependency surface is bounded enough for package-by-package audit |
| requirements with static import use | 9/11 | HTTPX and psycopg require deeper caller/runtime verification |
| Python dependency lockfile detected | false | reproducibility drift is measured, not hypothetical |

## Advanced convergence findings

### 1. Semantic/caller schema analysis

`94 / 155` schemas have at least one observed static caller by exact path or basename. Absence of a caller is not proof of non-use because dynamic discovery remains possible.

The strongest prior overlap candidate remains:

`schemas/exact_sha_ci_issue_request.schema.json`
vs
`schemas/exact_sha_ci_request.schema.json`

with measured feature-set Jaccard `1.0`. Both are referenced in the repository, so the proper next action is a shadow-compatible semantic/caller consolidation study, not deletion.

Highest-caller schemas include `quest.schema.json` with 11 observed callers and several identity/production schemas with five or six callers. Schema migrations must therefore be caller-aware and data-compatible.

### 2. Indirect test ownership

The baseline direct-import metric mapped `118 / 246` source modules (`47.97%`). Advanced import traversal maps `132 / 247` source modules as transitively reachable from at least one test (`53.44%`). `115` source modules remain without transitive static test reachability.

This metric is still not runtime coverage. APIs, configuration-driven loading, subprocesses, CLIs and fixtures can exercise modules outside the static import graph.

Strong transitive ownership examples include:

- `src.core.contract_validator`: 57 test modules;
- `src.infrastructure.persistence.sqlite`: 26;
- `src.application`: 23;
- `src.infrastructure.identity`: 21;
- `src.api.composition`: 17;
- `src.core.phase_registry`: 17.

Decision impact: ECS TestEquivalence remains incomplete for subsystem retirement until behavior/invariant-level test migration is mapped.

### 3. Canonical-responsibility search surfaces

The advanced analyzer intentionally labels these as `HEURISTIC_CANDIDATE_MAP_NOT_AUTHORITY`.

| Responsibility | Candidate search surface | Canonical Nexus target detected |
|---|---:|---|
| state machine / lifecycle | 33 | `src.core.nexus.state_reducer`, `src.domain.nexus.contracts` |
| policy / governance | 164 | `src.core.epistemic.tool_broker`, `src.domain.nexus.contracts` |
| evidence | 145 | `src.domain.nexus.evidence`, `src.infrastructure.persistence.sqlite.nexus_evidence` |
| agent registry / handoff | 23 | `src.core.nexus.specialist_registry` |
| dashboard / UI | 175 | `src.dashboard.nexus_app`, `src.webapp.nexus_dashboard` |
| provider runtime | 79 | **none yet** |

The large governance/evidence/UI counts reflect broad keyword use; they are investigation surfaces, not duplication counts.

The strongest actionable signal is provider runtime: historical provider/Gemini capability exists, but no canonical Nexus provider-runtime target is currently detected. Therefore PR #170 remains `ADAPT`, and provider-specific controls must be extracted into a generic Nexus runtime before historical provider trains can be retired.

### 4. Branch/PR convergence pressure

The full origin ref set contains `133` remote branches.

Age bands by latest branch commit:

- 0–7 days: 32;
- 8–30 days: 96;
- 31–90 days: 5;
- >90 days: 0 in the measured ref set.

High-divergence examples against current main include:

- `codex/operator-cockpit-run-accept`: 35 ahead / 280 behind;
- `codex/milestone-l-truth-first-procurement-governance`: 6 ahead / 280 behind;
- `phase26-constellation-refactor`: 8 ahead / 273 behind;
- `aigc-constellation-fabric`: 5 ahead / 274 behind;
- `aigc-cognitive-phase-router`: 6 ahead / 271 behind.

Current open PR metadata also spans multiple architectural generations: Nexus, EPI, Colosseum, OMNI-FORGE, Evidence Plane, Policy, Gemini, cloud, cockpit, CI and agent-registry trains remain simultaneously visible.

Decision impact: branch and PR cleanup is justified as a future convergence objective, but not before capability extraction and ECS completion.

### 5. Dependency use, reproducibility and security

Direct requirements measured: `11`; static imports observed for `9`.

No direct static import is currently observed for `httpx` or `psycopg`. This does not prove either is unused: HTTPX can be framework/test-transitive and psycopg can be adapter/extra driven.

CI-resolved versions at the measured environment include Streamlit 1.61.1, FastAPI 0.141.1, Uvicorn 0.52.1, Pydantic 2.13.4, HTTPX 0.28.1, pytest 8.4.2, jsonschema 4.26.0, PyYAML 6.0.3, psycopg 3.3.4, psycopg_pool 3.3.1 and PyJWT 2.13.0.

Measured reproducibility state:

- requirements use broad version ranges: true;
- supported Python lockfile detected: false;
- classification: `MEASURED_ENVIRONMENT_DRIFT_RISK`.

The external advisory review on August 7, 2026 found the measured Streamlit version is above the 1.54.0 fix for CVE-2026-33682, HTTPX 0.28.1 is above the affected `<0.23.0` range for CVE-2021-41945, and PyJWT 2.13.0 is the fixed release for multiple 2026 PyJWT advisories. This is not evidence that the entire transitive graph is vulnerability-free. Package-by-package exact-version OSV review, transitive inventory and SBOM generation remain required.

### 6. Partial ECS inputs

`ECS = ReplacementCoverage × TestEquivalence × DependencyMigration × EvidenceConfidence`

The analyzer now records partial, explicitly non-authorizing inputs:

| Subsystem | ReplacementCoverage proxy | repository TestEquivalence proxy | DependencyMigration | EvidenceConfidence | ECS |
|---|---:|---:|---|---|---|
| state machine | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| policy/governance | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| evidence | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| agent registry | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| dashboard | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| provider runtime | 0.0 | 0.5081 | unmeasured | unmeasured | uncomputed |

The `0.5` replacement value is only a heuristic indicating a plausible canonical target exists while legacy surfaces remain broad. It is not a percentage-complete claim.

No retirement ECS exists yet.

## Canonical responsibility targets

| Responsibility | Canonical Nexus target | Current confidence |
|---|---|---|
| WorkOrder | `src/domain/nexus/contracts.py::WorkOrder` | high |
| Context projection | `src/core/nexus/context_projection.py` | high |
| ArtifactState | `src/domain/epistemic/models.py::ArtifactState` | high |
| ChangeSet | `src/domain/nexus/contracts.py::ChangeSet` | high |
| deterministic verification | `src/core/epistemic/verifier.py` | high |
| GovernanceDecision | `src/domain/nexus/contracts.py::GovernanceDecision` | medium-high; policy fusion pending |
| ToolBroker policy boundary | `src/core/epistemic/tool_broker.py` + future Nexus capability policy | medium; legacy policy fusion pending |
| ExecutionPermit | `src/domain/nexus/contracts.py::ExecutionPermit` | medium; live adapter intentionally absent |
| ExecutionReceipt / reconciliation | Nexus contracts + state reducer | medium-high; resource-specific reducers pending |
| Memory admission | Nexus memory contracts + SQLite repository | high for local bounded persistence |
| Evidence representation | Nexus EvidenceReference + repository | medium-high; Evidence Plane enrichment pending |
| ODSE synthesis | `src/core/nexus/odse.py` | medium-high; external research adapters absent by design |
| Specialist registry | `src/core/nexus/specialist_registry.py` | medium; legacy registry capability fusion pending |
| Orchestration | `src/core/nexus/orchestrator.py` | medium; planning/DAG capability pending |
| Dashboard | `src/dashboard/nexus_app.py` + projection | medium; legacy cockpit migration pending |
| Provider runtime | not yet canonicalized | low; measured gap |
| Repository intelligence | base + advanced analyzers with CI-retained evidence | high for static discovery; runtime/churn depth still expandable |

## P0 — immediate convergence work

### P0.1 Repository intelligence and analytics

Status: `ADVANCED_STATIC_MEASUREMENT_IMPLEMENTED_AND_CI_VALIDATED` at exact head `3f714959...`.

Implemented measurements now include structural topology, import graph/cycles, coupling, schema overlap and callers, direct/transitive test ownership, branch age/divergence, direct dependency static use, reproducibility state, canonical-responsibility search surfaces and partial ECS inputs.

Remaining measurement work:

- behavior-level schema compatibility/shadow validation;
- runtime/API/subprocess/configuration test ownership;
- feature-by-feature historical capability maps;
- component-specific dependent-migration percentages;
- replacement-specific evidence-confidence scores;
- complete transitive dependency/SBOM advisory audit;
- PR-specific capability extraction and final lifecycle decisions.

### P0.2 Planning/scheduling fusion

Extract from Colosseum (#177): Definition-of-Done traceability, deterministic TaskDAG, readiness/blocking/critical-path logic, builder/verifier independence, and bounded resource reservations. Adapt beneath Nexus; do not import competing authority.

### P0.3 Evidence fusion

Map Evidence Plane (#169) lineage, metrics, freshness, data-quality and insufficiency semantics into Nexus. Keep `Evidence != Authority`.

### P0.4 Policy fusion

Compare Policy Enforcement (#166) against Nexus ToolBroker/Governance and preserve fail-closed prohibitions and emergency constraints behind one canonical promotion authority.

### P0.5 UI convergence

Migrate unique cockpit/operator value into Nexus and avoid permanent duplicate dashboards without a proven role boundary.

### P0.6 Exact-SHA schema shadow migration study

Begin semantic equivalence and caller migration analysis for the two measured-identical exact-SHA request schemas. No schema removal during discovery.

### P0.7 Test ownership completion

Trace the remaining 115 modules without transitive static test reachability through runtime/API/configuration/subprocess paths before any “untested” classification.

### P0.8 Branch/PR capability extraction

Prioritize the most divergent branches and open PR generations. Extract unique behavior/tests/evidence before proposing lifecycle cleanup.

### P0.9 Dependency reproducibility and SBOM

Evaluate a constraints/lock strategy, generate a transitive dependency inventory/SBOM, query exact versions against authoritative advisories, and test reproducible resolution. Do not remove HTTPX or psycopg based only on static imports.

## P1 — Nexus V1 product completion

### P1.1 Deterministic planning and structural validation

Adapt OMNI-FORGE graph/budget/repair invariants behind Nexus contracts.

### P1.2 Provider runtime abstraction

This is now a measured architectural gap. Extract generic controls from Gemini work (#170): provider isolation, durable emergency stop, idempotency, rate/request/token budgets, secret-reference brokerage, readiness checks, immutable evidence receipts and controlled canary semantics. Gemini becomes an adapter.

### P1.3 Persistent production-grade storage decision

Do not procure Redis/Vector Search/Cloud SQL from preference. Measure workload/concurrency/durability/search/deployment gaps first.

## Build / reuse / buy / remove matrix

| Capability | Decision now | Reason |
|---|---|---|
| Nexus contracts/verifier/OCC/memory/ODSE | `KEEP/EVOLVE` | integrated and exact-head validated |
| Repository Intelligence | `KEEP/EVOLVE` | advanced exact-head measured evidence exists |
| Colosseum DAG scheduling | `ADAPT` | validated planning value; competing authority unwanted |
| OMNI-FORGE graph validation | `ADAPT` | useful invariants; duplicate lifecycle unwanted |
| Evidence Plane | `ADAPT` | enrich current evidence model |
| Policy Enforcement | `ADAPT` | strengthen one policy boundary |
| Gemini controls | `ADAPT_TO_PROVIDER_RUNTIME` | provider runtime is a measured canonical gap |
| legacy Gemini branches | `SUPERSEDE_AFTER_EXTRACTION` | preserve evolved regression/invariant knowledge |
| legacy cockpits | `MIGRATE_AFTER_SURFACE_MAPPING` | operator value should converge into Nexus |
| highly divergent branches | `CAPABILITY_EXTRACT_BEFORE_LIFECYCLE_DECISION` | divergence is measured but removal ECS is absent |
| schema overlap candidates | `SHADOW_AND_CONSOLIDATE_IF_PROVEN` | structural/caller evidence exists; semantic equivalence pending |
| HTTPX / psycopg | `VERIFY_USAGE` | no direct static import observed; removal is not justified |
| Python dependency lock/constraints | `EVALUATE/IMPLEMENT` | environment drift risk is measured |
| SBOM/advisory automation | `IMPLEMENT` | transitive security state remains incomplete |
| Redis/vector DB/new agent framework | `DO_NOT_PROCURE_YET` | no measured need supports procurement yet |

## ECS governance

No component may be marked `REMOVE` until all four ECS inputs are measured. The current partial proxies are discovery aids only. DependencyMigration and EvidenceConfidence remain unset across the six measured subsystem surfaces, so every ECS remains uncomputed.

## Architectural fitness functions to implement

- one canonical ArtifactState contract;
- one canonical GovernanceDecision contract;
- no agent self-authorization;
- no evidence grants authority;
- no memory grants authority;
- no provider adapter owns global governance;
- no credential material in ExecutionPermit;
- no direct AgentOutput-to-execution path;
- no dashboard write-through without bounded permit;
- archived modules are not imported by active code;
- duplicate state-machine authorities are rejected;
- every consequential execution path is idempotency-bound and receipt-producing;
- dependency resolution is reproducible and auditable;
- schema consolidation preserves accepted-instance semantics and callers.

## Convergence exit criteria

Stage 1 is complete only when repository topology, callers/dependents, duplicate responsibilities, direct/transitive dependency state, historical tests/invariants, subsystem ECS inputs and procurement gaps are sufficiently measured to support migration decisions—and no destructive cleanup occurs before those gates are satisfied.
