# AIGC Nexus Convergence Manifest V1

Status: `DISCOVERY_BASELINE_V1_MEASURED`
Integration train: `release/aigc-nexus-v1`
Governing migration law: Evolutionary Convergence — No Stranded Capability

## Purpose

Provide an evidence-backed decision surface for converging historical AIGC capability into one canonical Nexus V1 product. This manifest remains intentionally non-destructive: it identifies what should be studied, adapted, fused, shadowed, or deferred before any archive/remove ChangeSet is proposed.

## Exact measured discovery baseline

Repository-intelligence evidence is bound to exact head `8eeb7eae57c41c957bbc66347307057a3ca66c60`.

- AIGC CI `#2544`: `SUCCESS`.
- run ID: `31181012166`.
- retained artifact ID: `8994794049`.
- artifact digest: `sha256:971c31e6c58530e5cc314a832922ced90e65a979033ebb39383668dacf31bf67`.
- repository-intelligence report SHA-256: `9f1412bfe9df4591d4359480c31feb356fd960ac79a3628c97bd7e2d6b3c132c`.

Measured repository facts:

| Metric | Value | Convergence meaning |
|---|---:|---|
| total files | 1008 | repository is large enough that manual intuition is insufficient |
| source files | 246 | capability migration must be module-aware |
| test files | 137 | substantial test inventory exists and should be treated as migration evidence |
| documentation files | 234 | documentation convergence is a major workstream |
| configuration/schema files | 301 | schema/contract accumulation is a major consolidation surface |
| infrastructure files | 18 | infrastructure surface is comparatively bounded |
| Python modules | 383 | import/dependent migration must be graph-driven |
| internal Python import edges | 469 | enough coupling exists to require dependency-aware convergence |
| detected Python import cycles | 0 | current static graph has no multi-module cycles under the analyzer model |
| JSON schemas analyzed | 155 | contract consolidation must be systematic |
| schema-overlap candidates | 141 | high structural overlap warrants semantic/caller investigation, not automatic merging |
| source modules with direct test import | 118/246 | direct static ownership exists for 47.97% of source modules |
| source modules without direct test import | 128 | deeper ownership tracing is required before retirement claims |
| exact duplicate text groups | 2 | byte duplication is limited; semantic duplication is the larger concern |

## Measured convergence findings

### 1. Import/package graph

The corrected most-specific-module resolver found `469` internal import edges and `0` multi-module import cycles.

High-coupling migration-risk nodes include:

- `src.core.contract_validator` — coupling `48`, fan-in `48`;
- `src.domain.identity.production_sessions` — coupling `25`;
- `src.api.app` — coupling `17`;
- `src.domain.nexus.contracts` — coupling `17`;
- `src.domain.quests.candidates` — coupling `15`;
- `src.domain.epistemic.models` — coupling `14`.

Decision impact: these modules should be treated as dependency-migration anchors. Replacing or merging them requires explicit caller maps and shadow/equivalence testing. No removal is authorized from coupling alone.

### 2. Schema-semantic overlap

The analyzer found `141` overlap candidates among `155` schemas.

Priority investigations:

| Left | Right | Jaccard | Current action |
|---|---|---:|---|
| `exact_sha_ci_issue_request.schema.json` | `exact_sha_ci_request.schema.json` | 1.0000 | investigate canonicalization; identical measured feature sets |
| provider discovery authorization | staging plan authorization | 0.7527 | inspect shared authority envelope vs legitimate specialization |
| procured-control-layers catalog | public-research-procurement catalog | 0.6471 | candidate procurement-contract fusion |
| staging apply authorization | staging plan authorization | 0.5692 | preserve distinct plan/apply authority semantics unless a shared base contract is proven safer |
| fidelity review | subagent team plan | 0.5135 | investigate whether overlap is generic metadata rather than duplicate responsibility |

Decision impact: Stage 1 now has concrete schema-fusion candidates. Structural similarity does not authorize deletion or merging; semantic purpose, callers, tests, historical data and compatibility must still be mapped.

### 3. Test-to-capability ownership

Direct import analysis maps `118` of `246` source modules to at least one direct test module (`0.4797`). `128` do not have a direct test import.

Strong direct ownership examples:

- `src.core.contract_validator` — 25 test modules;
- `src.api.app` — 10;
- `src.core.phase_registry` — 9;
- `src.infrastructure.persistence.sqlite.durable_production_identity` — 9;
- `src.domain.identity.production_sessions` — 7;
- `src.domain.nexus.contracts` — 6;
- `src.domain.epistemic.models` — 5.

Decision impact: direct-import ownership is a lower-bound indicator, not coverage. ECS `TestEquivalence` must remain unset for retirement candidates until indirect/API/subprocess/configuration-driven tests are mapped.

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
| Provider runtime | not yet canonicalized | low; Gemini controls to be adapted later |
| Observability / repository intelligence | `scripts/nexus_repository_intelligence.py` + CI-retained evidence | medium-high for structural discovery; churn/runtime analytics pending |

## P0 — immediate convergence work

### P0.1 Repository intelligence and analytics

Status: `PARTIALLY_IMPLEMENTED_AND_CI_VALIDATED`.

Implemented measurements:

- source/test/schema/documentation counts;
- import/package graph;
- import-cycle detection;
- coupling hotspots;
- schema-semantic overlap candidates;
- direct test-to-source ownership;
- exact text duplicates;
- deterministic report hashing and exact-head retention.

Remaining measurements:

- Git churn/staleness;
- indirect test ownership and runtime coverage;
- semantic duplicate state-machine/authority detection;
- direct dependency import/use mapping;
- historical PR capability-to-current-module mapping;
- architectural-fitness violations;
- measured ECS inputs.

### P0.2 Planning/scheduling fusion

Extract from Colosseum (#177):

- Definition-of-Done traceability;
- deterministic TaskDAG;
- readiness/blocking/critical-path logic;
- builder/verifier independence;
- bounded token/compute/deadline reservations.

Adapt beneath Nexus WorkOrder and GovernanceDecision. Do not import a competing state machine or authority hierarchy.

### P0.3 Evidence fusion

Map Evidence Plane (#169) capabilities into Nexus:

- lineage references;
- metric definitions/observations;
- freshness/expiry;
- data-quality findings;
- insufficiency semantics.

Keep `Evidence != Authority` as a fitness invariant.

### P0.4 Policy fusion

Compare Policy Enforcement (#166) with Nexus ToolBroker/Governance contracts. Preserve:

- self-approval prevention;
- direct-main prevention;
- automatic-merge prevention;
- deployment/production locks;
- Gmail/financial/arbitrary-shell/raw-secret prohibitions;
- emergency-stop integration.

One policy evaluator should remain subordinate to one GovernanceDecision authority.

### P0.5 UI convergence

Inventory historical Streamlit cockpit and PR #122 features. Migrate unique operator value into Nexus:

- initialization status;
- audit/transparency;
- emergency stop;
- review/accept workflows;
- repository intelligence;
- evidence and memory exploration.

Avoid two permanent operator dashboards unless role separation proves necessary.

### P0.6 Schema consolidation investigation

New measured priority. Begin caller/test/compatibility analysis for the strongest schema overlap candidates, starting with the two exact-SHA CI request schemas whose measured feature sets are identical. No schema is removed during discovery.

### P0.7 Test ownership completion

New measured priority. Trace the `128` modules without direct test imports through API routes, composition roots, CLI entry points, registries, configuration-driven invocation, fixtures and subprocess tests. Do not equate absence of direct import with absence of test coverage.

## P1 — Nexus V1 product completion

### P1.1 Deterministic planning and structural validation

Adapt OMNI-FORGE graph/budget/repair invariants behind Nexus contracts.

### P1.2 Provider runtime abstraction

Extract generic controls from Gemini work (#170):

- provider isolation;
- durable emergency stop;
- idempotency;
- request/rate/token budgets;
- secret-reference brokerage;
- readiness checks;
- immutable evidence receipts;
- one-call controlled canary semantics.

Gemini becomes an adapter. No provider-specific global governance.

### P1.3 Persistent production-grade storage decision

Do not procure Redis/Vector Search/Cloud SQL merely from architecture preference. Measure local SQLite workload, concurrency, durability, search, and deployment requirements first. Then choose build/reuse/buy based on observed gaps.

### P1.4 Dependency reproducibility

Current broad compatible ranges permit substantial environment drift. Evaluate constraints/lock strategy, Python baseline, major-version compatibility and security advisory scanning. Do not blindly bump versions.

## P2 — after integrated V1 proof

- A2A interop only if remote/heterogeneous agent systems become a real requirement.
- MCP adapters only against the current protocol and only through Nexus capability policy.
- managed agent runtime/memory only after local contracts and cost/residency requirements justify procurement.
- GCP staging resource creation only after exact project, billing, IAM, budget, region and human authorization evidence exists.
- native iOS/App Store work after the Nexus web/runtime product is stable enough to justify a second client surface.

## Initial build/reuse/buy/remove matrix

| Capability | Decision now | Reason |
|---|---|---|
| Nexus contracts/verifier/OCC/memory/ODSE | `BUILD/KEEP` | integrated and exact-head CI validated |
| Repository Intelligence | `KEEP/EVOLVE` | exact-head measured evidence now exists; deeper layers pending |
| Colosseum DAG scheduling | `ADAPT` | strong validated planning value; competing authority unwanted |
| OMNI-FORGE graph validation | `ADAPT` | useful structural invariants; duplicate lifecycle unwanted |
| Evidence Plane metrics/lineage | `ADAPT` | enriches current evidence model |
| Policy Enforcement | `ADAPT` | strengthen existing policy boundary, not duplicate it |
| Gemini-specific controls | `ADAPT` | convert to provider-neutral runtime then bind Gemini adapter |
| legacy Gemini branches | `SUPERSEDE` | later release candidate contains evolved implementation |
| legacy cockpits | `MIGRATE` | UI value should converge into Nexus |
| GCP foundation | `DEFER/ADAPT_DESIGN` | external facts/cost/authority unresolved |
| Redis / managed vector DB | `DO_NOT_PROCURE_YET` | current need not measured |
| A2A | `DEFER` | interoperability option, not current requirement |
| MCP | `DEFER_ADAPTER` | connector need must become concrete first |
| new agent framework | `DO_NOT_PROCURE_YET` | framework fit not yet demonstrated |
| schema-overlap candidates | `INVESTIGATE/CONSOLIDATE_IF_PROVEN` | measured structural overlap now exists; semantic compatibility pending |
| modules without direct test imports | `TRACE_TEST_OWNERSHIP` | direct-import metric is not sufficient evidence of no testing |

## Evolution Confidence Score data requirements

No component may be marked `REMOVE` until all four inputs are measured:

1. Replacement Coverage — feature/invariant mapping complete.
2. Test Equivalence — legacy business/security/regression tests ported or explicitly retired.
3. Dependency Migration — active callers/importers moved to canonical implementation.
4. Evidence Confidence — exact-head CI/shadow/runtime evidence supports the replacement.

Current measured progress:

- Dependency Migration: import topology is now partially measurable (`469` edges, no detected cycles), but component-specific migration percentages are not yet calculated.
- Test Equivalence: direct ownership is partially measurable (`118/246` source modules have direct test imports), but indirect equivalence remains incomplete.
- Replacement Coverage: historical capability mapping remains incomplete.
- Evidence Confidence: exact-head repository-intelligence evidence exists; replacement-specific evidence remains incomplete.

Therefore no retirement ECS is assigned yet.

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
- deprecated provider mechanisms are not introduced;
- duplicate state-machine authorities are rejected by architecture tests;
- every consequential execution path is idempotency-bound and receipt-producing.

## Convergence exit criteria

The Stage-1 discovery phase is complete only when:

- repository topology is quantitatively measured rather than inferred;
- active imports/dependents are known for retirement candidates;
- duplicate responsibilities are mapped;
- direct and transitive dependency audit is recorded;
- historical tests/invariants are assigned migration destinations;
- ECS inputs exist for every proposed retirement;
- procurement recommendations follow observed gaps;
- no destructive cleanup was performed during discovery.
