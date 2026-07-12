# AIGC Evolution & Procurement Cycle — Job Lifecycle Concordance v1

Status: draft, bounded, operator-controlled  
Base revision: `293de53489fe7212fad272c01c698c0ffe2da610`  
Branch: `codex/canonical-job-lifecycle-contract-v1`  
External action performed by AIGC runtime: `false`

## 1. Evolution Diagnosis

### Ontology health

The recursive engine still models only `code`, `infrastructure`, `devops`, `data`, and `risk`. The repository now requires explicit domains for constitutional governance, identity and authority, approval binding, work acquisition, job lifecycle, application services, persistence, audit evidence, security/privacy, external action, recovery, accessibility, and compatibility.

### Taxonomy completeness

The current `layer/function/lifecycle/ownership` taxonomy cannot distinguish lifecycle scope, authority class, action effect, evidence kind, persistence class, compatibility status, or rollback class.

### Methodology coherence

AIGC is coherent around contract-first design, fail-closed control, exact-revision evidence, operator authority, optimistic concurrency, immutable receipts, append-only audit, and reversible reviewed changes. Contract authority ordering remains incomplete because the architecture program and PR #64 use incompatible meanings for `ACCEPTED`.

### Architecture integrity

The architecture rule `route -> application service -> domain kernel -> repository port -> adapter` is sound. The present integrity blocker is lifecycle semantic divergence before durable job orchestration.

### Production-readiness gaps

Production identity, connector execution, deployment, and exact-head CI on `main` remain blocking. The readiness ledger also lacks evidence paths for merged transactional persistence and conflates legacy work preparation with canonical job orchestration.

### Governance stability

Branch review, rollback, no self-approval, no direct-main write, no credentials, no deployment, and no external action remain preserved.

### Evolution bottleneck

The next runtime train must not persist or expose job states until one canonical lifecycle vocabulary is approved.

### Dead logic

The recursive architect permits multiple cycles but unconditionally stops after the first cycle.

### Redundant modules

The legacy work-order preparation module and PR #64 job lifecycle overlap without a compatibility contract. The legacy module is preserved and classified as a preparation surface rather than deleted.

### Fragile structures

- generic `ACCEPTED` semantic collision;
- PR #64 review-to-research edge compresses explicit rework state;
- unmerged exact-head CI correction;
- stale readiness classifications;
- no atomic durable job transition service yet.

## 2. Contender Arena

1. **Canonical Lifecycle Concordance** — one versioned source of lifecycle truth. Ranked first.
2. **Two-Ring Lifecycle** — acquisition/commitment and execution/delivery bounded contexts.
3. **PR #64 Expansion** — widen the draft kernel to the full canonical graph after contract approval.
4. **Compatibility Adapter** — preserve PR #64 and legacy artifacts through explicit mappings.
5. **Durable Transition Conductor** — application service and atomic persistence after semantics settle.
6. **Event-Sourced Chronicle** — future high-assurance option; excessive for the current MVP.
7. **Legacy Phase Canonization** — rejected as the central model because phase-era semantics are not durable domain authority.

Synthesis: canonical concordance + two-ring structure + explicit compatibility map.

## 3. Auto-Design Output

Added:

- lifecycle contract schema;
- proposed canonical lifecycle instance;
- compatibility-map schema and instance;
- lifecycle reconciliation engine;
- lifecycle standard and tests.

Canonical semantic correction:

- `WORK_ACCEPTED` = acceptance of the job commitment;
- `ACCEPTED_FOR_DELIVERY` = acceptance of completed work after review.

## 4. Auto-Engineer Output

The reconciliation engine checks duplicate states/transitions, initial-state count, reachability, terminal-state protection, defined transition endpoints, authority-class references, generic `ACCEPTED`, delivery receipt boundaries, compatibility targets, duplicate source mappings, and operator-decision requirements.

It emits a deterministic reconciliation report with contract and compatibility digests, counts, findings, unresolved conflicts, runtime-integration readiness, operator-review requirement, and `external_action_performed=false`.

## 5. Auto-Architect Output

Target planes:

```text
Acquisition plane
-> authority plane
-> canonical lifecycle plane
-> durability/evidence plane
-> external execution plane (blocked and separate)
```

The lifecycle contract becomes the future source for state-machine rules, persistence versioning, API commands, UI wording, audit semantics, and compatibility migration.

## 6. Cognitive and Analytical Review

The repository already possesses persistence ports, SQLite storage, authorization receipts, audit events, and a draft job kernel. The highest-value bounded change is semantic reconciliation before those components are joined. The cost is delayed visible UI progress; the benefit is avoiding durable state ambiguity and later migration debt.

## 7. 2026 Societal Logic Integration

The contract preserves privacy minimization, attributable authority, separation of operator and counterparty decisions, WCAG-compatible semantic UI wording, official-API-only future delivery, platform-rule compliance, human oversight, and continued production-identity blocking.

## 8. Final Synthesis

```text
canonical lifecycle contract
+ two bounded lifecycle rings
+ explicit compatibility mappings
+ transition-specific authority
+ separate delivery execution receipts
```

## 9. Single Highest-Impact Next Implementation Step

Complete and review `AIGC-CANONICAL-JOB-LIFECYCLE-CONTRACT-V1` before modifying PR #64 or opening durable job-service/API/UI work.

## 10. Procurement Success Packet

### Objective

Establish one machine-validatable lifecycle vocabulary and compatibility map.

### Scope

Contracts, compatibility mappings, structural analyzer, tests, and documentation only.

### Non-scope

No runtime state mutation, database migration, API/UI, connector, identity-provider, credential, deployment, readiness promotion, or external action.

### Prerequisites and blockers

PR #53 exact-head evidence remains unmerged. PR #64 remains draft and must be corrected or classified after contract review.

### Affected ontology domains

`constitutional_governance`, `approval_and_decision_binding`, `work_acquisition`, `job_lifecycle`, `application_services`, `audit_and_evidence`, `compatibility_and_migration`, `operator_interaction`, `security_and_privacy`.

### Affected taxonomy classes

`bounded_context`, `lifecycle_scope`, `state_contract_version`, `authority_class`, `action_effect`, `evidence_kind`, `compatibility_status`, `review_requirement`, `rollback_class`, `failure_criticality`.

### Methodologies

Contract-first engineering, DDD, finite-state-machine design, clean architecture, fail-closed validation, semantic versioning, compatibility mapping, TDD, privacy by design, GitOps, and reversible change.

### Architecture impact

Defines the future single source of truth for job lifecycle semantics. No runtime integration occurs in this PR.

### Schemas/contracts

- `governance/schemas/jobs/job_lifecycle_contract.schema.json`
- `governance/schemas/jobs/job_state_compatibility_map.schema.json`
- `governance/jobs/canonical_job_lifecycle_v1.json`
- `governance/jobs/job_state_compatibility_map_v1.json`

### Config

No secrets or environment configuration.

### Core module

`src/core/jobs/lifecycle_contract.py`

### CLI/API/UI

None in this bounded PR.

### Persistence

None. Future persisted jobs must carry contract identifier and version and fail closed on unknown versions.

### Security/privacy

No personal data, secrets, network calls, external action, or reduced Security & Privacy Wiring Gate.

### Identity/authorization

Every transition declares an authority class. Operator, policy, connector, and counterparty evidence remain separate.

### Observability/audit

The reconciliation report is deterministic and revision-bound when called by later CI/application wiring.

### Tests

Schema validation, unique states/transitions, reachability, terminal protection, semantic acceptance split, delivery receipt boundary, PR #64 mapping coverage, compatibility target validation, and fail-closed source revision.

### CI gates

Contracts, AEC-001, secret scan, full tests, exact-head evidence, readiness evaluation without promotion, and operator review.

### Rollback/migration

Branch abandonment before merge or one squash revert after merge. No runtime-data migration.

### Documentation/runbook

`docs/governance/standards/AIGC_CANONICAL_JOB_LIFECYCLE_V1.md`

### Ownership

The accountable operator decides canonical semantics and merge. AI analysis is advisory. Independent human review is not claimed.

### Sequencing

Evidence verification -> contract proposal -> compatibility map -> tests -> CI -> operator review -> merge decision -> exact-main verification -> later PR #64 correction.

### Acceptance criteria / definition of done

Schema-valid contract and map, no structural findings, blocking semantic conflicts resolved, exact-head CI proven, operator review recorded, no runtime/external-action claim.

### Risk register

Critical: ambiguous acceptance semantics and fabricated counterparty acceptance. High: persistence of wrong states, UI mislabelling, readiness inflation, synthetic-merge evidence. Controls are explicit state names, separate authority/evidence classes, no readiness change, and exact-head merge gates.

### Readiness-score impact

Immediate numeric impact: `0`. This change reduces architecture risk but does not provide operational capability.

### Branch/PR plan

- branch: `codex/canonical-job-lifecycle-contract-v1`
- draft PR: `docs(jobs): reconcile canonical job lifecycle contract v1`
- base: current `main`
- squash merge only after operator authorization and exact-head proof.

## 11. Workflow Procurement Procedure

`intake -> evidence verification -> scope lock -> contract-first design -> implementation plan -> security/privacy wiring -> tests -> CI -> operator review -> merge decision -> post-merge verification -> readiness-ledger update`

## 12. Engine Evolution v+1

Add cross-artifact contract conflict detection so architecture documents, schemas, runtime constants, transition maps, and readiness declarations are compared before runtime procurement begins.

## 13. Next-Run Directive

Inspect:

1. PR #53 disposition and exact-main evidence;
2. CI and findings for this lifecycle-contract branch;
3. operator decision on `WORK_ACCEPTED` and `ACCEPTED_FOR_DELIVERY`;
4. PR #64 correction or sub-lifecycle classification;
5. only after resolution, the atomic job-update/audit/idempotency unit-of-work boundary.

Do not begin durable job service, API/UI job wiring, connector work, or readiness promotion while blocking lifecycle conflicts remain.
