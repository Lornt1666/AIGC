# AIGC Nexus Convergence Manifest V1

Status: `DISCOVERY_BASELINE_V1`
Integration train: `release/aigc-nexus-v1`
Governing migration law: Evolutionary Convergence — No Stranded Capability

## Purpose

Provide the first evidence-backed decision surface for converging historical AIGC capability into one canonical Nexus V1 product. This manifest is intentionally non-destructive: it identifies what should be studied, adapted, fused, shadowed, or deferred before any archive/remove ChangeSet is proposed.

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
| Observability / repository intelligence | not yet canonicalized | low; historical analytics should be mined first |

## P0 — immediate convergence work

### P0.1 Repository intelligence and analytics

Build a provider-free analysis surface that measures:

- active source/test/schema/documentation counts;
- duplicate canonical responsibility implementations;
- import/dependency graph;
- stale/unused modules;
- duplicate schemas and state machines;
- test ownership by capability;
- open-PR capability inventory;
- branch/PR age and supersession;
- dependency ranges versus current stable ecosystem;
- architectural-fitness violations.

Output should feed the Nexus Repository Intelligence dashboard rather than exist only as prose.

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

Current broad compatible ranges permit substantial environment drift. Evaluate:

- constraints or lockfile strategy;
- Python version baseline;
- pytest 9 migration compatibility;
- Streamlit 1.60 compatibility;
- Pydantic 2.13 compatibility;
- psycopg 3.3 compatibility;
- security advisory scanning.

Do not blindly bump major versions.

## P2 — after integrated V1 proof

- A2A interop only if remote/heterogeneous agent systems become a real requirement.
- MCP adapters only against the current 2026-07-28 protocol and only through Nexus capability policy.
- managed Agent Platform Runtime/Memory Bank only after local contracts and cost/residency requirements justify procurement.
- GCP staging resource creation only after exact project, billing, IAM, budget, region, and human authorization evidence exists.
- native iOS/App Store work after the Nexus web/runtime product is stable enough to justify a second client surface.

## Mandatory migration findings

### Google Vertex AI Extensions

Current Google Cloud release notes mark Vertex AI Extensions deprecated with shutdown after November 26, 2026. Any AIGC dependency or planned integration using Extensions must be classified `MIGRATE` to Agent Platform/ADK-compatible mechanisms. Do not create new Extensions integration.

### MCP historical assumptions

The current MCP specification (2026-07-28) uses a stateless protocol core and includes updated authorization, task, routing, and multi-round-trip semantics. Any older AIGC MCP design assuming mandatory persistent protocol sessions must be reviewed before reuse.

## Initial build/reuse/buy/remove matrix

| Capability | Decision now | Reason |
|---|---|---|
| Nexus contracts/verifier/OCC/memory/ODSE | `BUILD/KEEP` | already integrated and exact-head CI validated |
| Colosseum DAG scheduling | `ADAPT` | strong validated planning value; competing authority unwanted |
| OMNI-FORGE graph validation | `ADAPT` | useful structural invariants; duplicate lifecycle unwanted |
| Evidence Plane metrics/lineage | `ADAPT` | enriches current evidence model |
| Policy Enforcement | `ADAPT` | strengthen existing policy boundary, not duplicate it |
| Gemini-specific controls | `ADAPT` | convert to provider-neutral runtime then bind Gemini adapter |
| legacy Gemini branches | `SUPERSEDE` | later release candidate contains evolved implementation |
| legacy cockpits | `MIGRATE` | UI value should converge into Nexus |
| GCP foundation | `DEFER/ADAPT_DESIGN` | external facts/cost/authority unresolved |
| Redis / managed vector DB | `DO_NOT_PROCURE_YET` | current need not measured |
| A2A | `DEFER` | useful interoperability option, not current product requirement |
| MCP | `DEFER_ADAPTER` | current protocol is useful, but connector need must be concrete |
| new agent framework | `DO_NOT_PROCURE_YET` | Nexus already has internal orchestration contracts; framework fit must be measured |
| pytest 9 | `EVALUATE` | current requirement intentionally caps `<9`; compatibility data needed |
| current Streamlit/Pydantic/psycopg minor upgrades | `EVALUATE_WITH_TESTS` | current ranges already allow modern stable versions |

## Evolution Confidence Score data requirements

No component may be marked `REMOVE` until all four inputs are measured:

1. Replacement Coverage — feature/invariant mapping complete.
2. Test Equivalence — legacy business/security/regression tests ported or explicitly retired.
3. Dependency Migration — active callers/importers moved to canonical implementation.
4. Evidence Confidence — exact-head CI/shadow/runtime evidence supports the replacement.

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
- deprecated Vertex AI Extensions are not introduced;
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
