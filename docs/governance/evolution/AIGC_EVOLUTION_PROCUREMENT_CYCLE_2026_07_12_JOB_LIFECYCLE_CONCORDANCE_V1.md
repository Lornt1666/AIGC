# AIGC Evolution & Procurement Cycle — Job Lifecycle Concordance v1

Status: **draft, bounded, operator-controlled**  
Base revision: `293de53489fe7212fad272c01c698c0ffe2da610`  
Branch: `codex/canonical-job-lifecycle-contract-v1`  
Parent program: GitHub Issue `#55`  
Implementation review: GitHub PR `#65`  
External action performed by AIGC runtime: `false`

## Cycle disposition

This cycle establishes a contract-first reconciliation layer for AIGC job lifecycle semantics. It does not mutate jobs, modify the runtime kernel in PR `#64`, add database migrations, expose API/UI controls, use credentials, deploy, invoke connectors, or perform an external action.

The cycle adds or coordinates:

- a strict lifecycle-contract schema;
- a proposed canonical lifecycle;
- a strict compatibility-map schema and instance;
- a pure reconciliation engine;
- structural, semantic, compatibility, and fail-closed tests;
- a canonical lifecycle standard;
- an operational reconciliation procedure;
- a transformation backlog and procurement register.

No readiness-score increase is claimed. Operator semantic decisions and exact-head CI evidence remain merge gates.

## 1. Evolution Diagnosis

### Ontology health

The recursive engine still models only `code`, `infrastructure`, `devops`, `data`, and `risk`. The repository now requires explicit domains for constitutional governance, identity and authority, approval binding, work acquisition, job lifecycle, application services, persistence, audit evidence, security/privacy, external action, recovery, accessibility, and compatibility.

Updated lifecycle ontology:

```text
constitutional_governance
identity_and_authority
approval_and_decision_binding
work_acquisition
job_lifecycle
application_services
persistence
audit_and_evidence
security_and_privacy
external_action
deployment_and_recovery
accessibility
compatibility_and_migration
```

Assessment: conceptually strong, mechanically stale.

### Taxonomy completeness

The current `layer/function/lifecycle/ownership` taxonomy cannot distinguish lifecycle scope, authority class, action effect, evidence kind, persistence class, compatibility status, external-action boundary, or rollback class.

Required dimensions:

```text
bounded_context
lifecycle_scope
state_contract_version
authority_class
action_effect
evidence_kind
data_sensitivity
persistence_class
deployment_tier
review_requirement
compatibility_status
failure_criticality
rollback_class
external_action_boundary
```

### Methodology coherence

AIGC is coherent around:

```text
contract first
→ fail closed
→ exact-revision evidence
→ explicit operator authority
→ deterministic digest
→ optimistic concurrency
→ immutable receipt
→ append-only audit
→ reversible reviewed change
```

Contract authority ordering remains incomplete because the architecture program and PR `#64` use incompatible meanings for `ACCEPTED`.

### Architecture integrity

The architecture rule is sound:

```text
route
→ application service
→ domain kernel
→ repository port
→ infrastructure adapter
```

The present integrity blocker is lifecycle semantic divergence before durable job orchestration.

Main architecture semantics:

```text
APPROVAL_REQUIRED
→ ACCEPTED
→ RESEARCHING
```

PR `#64` semantics:

```text
READY_FOR_REVIEW
→ ACCEPTED
→ DELIVERED
```

The same state identifier represents two materially different decisions.

### Production-readiness gaps

Production identity, connector execution, deployment, recovery evidence, and exact-head CI on `main` remain blocking. The readiness ledger also lacks evidence paths for merged transactional persistence and conflates legacy work preparation with canonical job orchestration.

Immediate readiness-score impact of this contract-only cycle: `0`.

### Governance stability

Preserved controls:

- separate branch and draft PR;
- no self-approval;
- no direct-main write;
- no merge;
- no deletion;
- no credentials;
- no deployment;
- no external connector;
- no production data;
- rollback available;
- Security & Privacy Wiring Gate mandatory.

### Evolution bottleneck

The next runtime train must not persist or expose job states until one canonical lifecycle vocabulary is approved.

### Dead logic

The recursive architect permits multiple cycles but unconditionally stops after the first cycle. The current behavior errs toward bounded execution, but configuration and runtime contradict each other.

### Redundant modules

The legacy work-order preparation module and PR `#64` lifecycle overlap without a compatibility contract. The legacy module is preserved and classified as a preparation surface rather than deleted or treated as the canonical state aggregate.

### Fragile structures

- generic `ACCEPTED` semantic collision;
- PR `#64` review-to-research edge compresses explicit rework state;
- unmerged exact-head CI correction;
- stale readiness classifications;
- no atomic durable job transition service;
- authorization-receipt references not yet resolved by a job application service;
- legacy and canonical work models remain parallel.

## 2. Contender Arena

1. **Canonical Lifecycle Concordance** — one versioned source of lifecycle truth. Ranked first.
2. **Two-Ring Lifecycle** — acquisition/commitment and execution/delivery bounded contexts.
3. **PR #64 Expansion** — widen the draft kernel to the full canonical graph after contract approval.
4. **PR #64 Sub-Lifecycle Adapter** — preserve the draft kernel as a compressed internal adapter with explicit canonical mappings.
5. **Durable Transition Conductor** — application service and atomic persistence after semantics settle.
6. **Legacy Work-Order Adapter** — translate preparation packets into future canonical commands.
7. **Event-Sourced Chronicle** — future high-assurance option; excessive for the current local MVP.
8. **Parallel Semantics** — rejected because it deepens authority, audit, UI, and migration ambiguity.

Synthesis:

```text
canonical concordance
+ two-ring structure
+ explicit compatibility map
```

## 3. Auto-Design Output

Implemented design artifacts:

- lifecycle contract schema;
- proposed canonical lifecycle instance;
- compatibility-map schema and instance;
- lifecycle reconciliation engine;
- lifecycle standard;
- reconciliation procedure;
- procurement register;
- tests.

Canonical semantic correction:

- `WORK_ACCEPTED` = operator acceptance of the job commitment;
- `ACCEPTED_FOR_DELIVERY` = operator acceptance of completed reviewed work for a separate delivery action;
- generic canonical `ACCEPTED` = prohibited.

Two lifecycle rings:

```text
Ring A — acquisition and commitment
DISCOVERED
→ QUALIFIED
→ PROPOSED
→ APPROVAL_REQUIRED
→ WORK_ACCEPTED

Ring B — execution and delivery evidence
RESEARCHING
→ PLANNING
→ EXECUTING_LOCALLY
→ REVIEW_REQUIRED
→ ACCEPTED_FOR_DELIVERY
→ DELIVERED
→ CLOSED
```

Exception states:

```text
REWORK_REQUIRED
REJECTED
CANCELLED
```

## 4. Auto-Engineer Output

The reconciliation engine checks:

- duplicate states and transitions;
- initial-state count;
- reachability;
- terminal-state protection;
- defined transition endpoints;
- authority-class references;
- generic `ACCEPTED` prohibition;
- delivery receipt boundary;
- compatibility targets;
- duplicate source mappings;
- operator-decision requirements;
- required source revision.

It emits a deterministic reconciliation report with:

- contract and compatibility digests;
- state and transition counts;
- structural and compatibility findings;
- unresolved conflicts;
- runtime-integration readiness;
- operator-review requirement;
- `external_action_performed=false`.

Future runtime sequence, only after ratification:

```text
JobTransitionCommand
→ AuthorizationReceiptVerifier
→ CanonicalLifecycleRegistry
→ GovernedJobStateMachine
→ JobTransitionUnitOfWork
→ job revision + audit event + idempotency
→ transition result
```

## 5. Auto-Architect Output

Target planes:

```text
Acquisition plane
→ identity and authority plane
→ canonical lifecycle plane
→ durability and evidence plane
→ external execution plane (blocked and separate)
```

Integration patterns:

- one source of lifecycle truth;
- ports and adapters;
- explicit legacy anti-corruption layer;
- semantic commands rather than generic `Accept`;
- future transactional unit of work;
- future outbox separation for external action;
- schema-driven UI wording;
- persisted lifecycle contract version;
- fail-closed compatibility migration.

The lifecycle contract becomes the future source for state-machine rules, persistence versioning, API commands, UI wording, audit semantics, and compatibility migration.

## 6. Cognitive and Analytical Review

The repository already possesses persistence ports, SQLite storage, authorization receipts, audit events, and a draft job kernel. The highest-value bounded change is semantic reconciliation before those components are joined.

Tradeoff:

- cost: delayed visible API/UI progress;
- benefit: avoidance of durable state ambiguity, authorization error, misleading operator controls, and later migration debt.

Human-coordination reality:

- automation may detect conflicts and prepare alternatives;
- the accountable operator must choose canonical business meaning;
- automation cannot self-approve, fabricate independent review, or infer counterparty acceptance.

## 7. 2026 Societal Logic Integration

The contract preserves:

- privacy minimization;
- attributable authority;
- separation of operator and counterparty decisions;
- accessible semantic UI wording;
- official-API-only future delivery;
- platform-rule compliance;
- human oversight;
- continued production-identity blocking.

Engineering implications:

- audit stores identifiers, decisions, and digests rather than unnecessary client content;
- state changes never imply consent;
- future UI uses distinct labels such as **Accept work** and **Accept for delivery**;
- employment-related automation remains human-controlled and explainable;
- external delivery requires a separate normalized execution receipt.

## 8. Final Synthesis

```text
canonical lifecycle contract
+ two bounded lifecycle rings
+ explicit compatibility mappings
+ transition-specific authority
+ separate delivery execution receipts
+ future atomic durable orchestration
```

Measurable progress is contract and governance maturity only. Runtime capability and readiness status remain unchanged until separately merged and evidenced.

## 9. Single Highest-Impact Next Implementation Step

Complete and review `AIGC-JOB-LIFECYCLE-SEMANTIC-RESOLUTION-V1` inside PR `#65` before modifying PR `#64` or opening durable job-service, API, UI, or connector work.

Required operator decisions:

1. ratify the separate meanings of `WORK_ACCEPTED` and `ACCEPTED_FOR_DELIVERY`;
2. choose explicit `REWORK_REQUIRED` or formal compressed sub-lifecycle treatment for PR `#64`.

## 10. Procurement Success Packet

### Objective

Establish one machine-validatable lifecycle vocabulary and compatibility map with zero unresolved blocking semantic conflict.

### Scope

Contracts, compatibility mappings, reconciliation logic, tests, procedure, register, and governance documentation only.

### Non-scope

No runtime state mutation, database migration, API/UI, connector, identity-provider, credential, deployment, readiness promotion, legacy deletion, or external action.

### Prerequisites and blockers

- PR `#53` exact-head evidence remains unmerged;
- PR `#64` remains draft and must be corrected or classified after contract review;
- operator semantic decisions are not yet attributed;
- exact-head artifact evidence remains a merge gate.

### Affected ontology domains

`constitutional_governance`, `identity_and_authority`, `approval_and_decision_binding`, `work_acquisition`, `job_lifecycle`, `application_services`, `audit_and_evidence`, `compatibility_and_migration`, `operator_interaction`, `security_and_privacy`.

### Affected taxonomy classes

`bounded_context`, `lifecycle_scope`, `state_contract_version`, `authority_class`, `action_effect`, `evidence_kind`, `compatibility_status`, `review_requirement`, `rollback_class`, `failure_criticality`, `external_action_boundary`.

### Methodologies

Contract-first engineering, domain-driven design, finite-state-machine design, clean architecture, fail-closed validation, semantic versioning, compatibility mapping, test-driven development, privacy by design, GitOps, and reversible change.

### Architecture impact

Defines the future single source of truth for job lifecycle semantics. No runtime integration occurs in this PR.

### Schemas and contracts

- `governance/schemas/jobs/job_lifecycle_contract.schema.json`
- `governance/schemas/jobs/job_state_compatibility_map.schema.json`
- `governance/jobs/canonical_job_lifecycle_v1.json`
- `governance/jobs/job_state_compatibility_map_v1.json`

### Configuration

No secrets or environment configuration.

### Core module

`src/core/jobs/lifecycle_contract.py`

### CLI, API, and UI

None in this bounded PR.

### Persistence

None. Future persisted jobs must carry contract identifier and version and fail closed on unknown versions.

### Security and privacy

No personal data, secrets, network calls, external action, or reduced Security & Privacy Wiring Gate.

### Identity and authorization

Every transition declares an authority class. Operator, policy, connector, counterparty, and verified-outcome evidence remain separate.

### Observability and audit

The reconciliation report is deterministic and revision-bound when called by CI or later application wiring.

### Tests

- schema validation;
- unique states and transitions;
- one initial state;
- reachability;
- terminal protection;
- semantic acceptance split;
- delivery receipt boundary;
- PR `#64` mapping coverage;
- compatibility target validation;
- fail-closed source revision;
- `external_action_performed=false`.

### CI gates

Contracts, AEC-001, secret scan, full tests, exact-head evidence, readiness evaluation without promotion, artifact/source-revision equality, and operator review.

### Rollback and migration

Branch abandonment before merge or one squash revert after merge. No runtime-data migration.

### Documentation and procedure

- `docs/governance/standards/AIGC_CANONICAL_JOB_LIFECYCLE_V1.md`
- `docs/governance/procedures/AIGC_JOB_LIFECYCLE_CONTRACT_RECONCILIATION_PROCEDURE_V1.md`
- `docs/governance/evolution/AIGC_JOB_LIFECYCLE_TRANSFORMATION_BACKLOG_AND_PROCUREMENT_REGISTER_V1.md`

### Ownership

The accountable operator decides canonical semantics and merge. AI analysis is advisory. Independent human review is not claimed.

### Sequencing

```text
evidence verification
→ contract proposal
→ compatibility map
→ procedure and procurement register
→ tests
→ CI
→ operator semantic decision
→ exact-head review
→ merge decision
→ exact-main verification
→ later PR #64 correction
```

### Acceptance criteria and definition of done

- schema-valid contract and map;
- no structural findings;
- blocking semantic conflicts resolved;
- exact-head CI proven;
- operator review recorded;
- no runtime or external-action claim;
- rollback preserved.

### Risk register

Critical risks:

- ambiguous acceptance semantics;
- fabricated counterparty acceptance;
- external action inferred from internal state.

High risks:

- persistence of wrong states;
- misleading UI wording;
- readiness inflation;
- synthetic-merge evidence mistaken for exact-head proof;
- silent lossy legacy migration.

Controls are explicit state names, separate authority and evidence classes, no readiness change, exact-head merge gates, and operator decision tracking.

### Readiness-score impact

Immediate numeric impact: `0`. This change reduces architecture risk but does not provide operational capability.

### Branch and PR plan

- branch: `codex/canonical-job-lifecycle-contract-v1`;
- draft PR: `#65 — docs(jobs): reconcile canonical job lifecycle contract v1`;
- base: current `main` at branch creation;
- squash merge only after operator authorization and exact-head proof.

## 11. Workflow Procurement Procedure

The mandatory order is:

```text
intake
→ evidence verification
→ scope lock
→ contract-first design
→ implementation plan
→ security/privacy wiring
→ tests
→ CI
→ operator review
→ merge decision
→ post-merge verification
→ readiness-ledger update
```

The detailed executable procedure is maintained at:

`docs/governance/procedures/AIGC_JOB_LIFECYCLE_CONTRACT_RECONCILIATION_PROCEDURE_V1.md`

## 12. Engine Evolution v+1

### Cross-Artifact Contract Conflict Detector

The evolution engine should compare domain semantics across:

- architecture documents;
- JSON schemas;
- runtime constants;
- transition maps;
- issue procurement packets;
- readiness declarations.

Proposed bounded modules:

```text
src/core/contract_conflict_detector.py
schemas/contract_conflict_report.schema.json
tests/test_contract_conflict_detector.py
```

Required pipeline:

```text
collect authoritative artifacts
→ extract domain vocabularies
→ normalize identifiers
→ compare meanings and relationships
→ classify exact / rename / lossy / conflicting
→ emit revision-bound finding
→ block runtime procurement
→ require operator resolution
```

Required controls:

- advisory only;
- no repository mutation;
- no automatic canonical selection;
- no self-approval;
- deterministic report;
- exact source revision;
- `external_action_performed=false`.

This detector would have surfaced the two meanings of `ACCEPTED` before runtime implementation.

## 13. Next-Run Directive

Inspect, in this exact order:

1. **PR #53**
   - current state and final head;
   - whether merged;
   - exact-main verification;
   - checkout, readiness source revision, and artifact binding.

2. **PR #65**
   - current exact head;
   - operator semantic decision issue;
   - disposition of `GENERIC_ACCEPTED_SEMANTIC_COLLISION`;
   - disposition of `PR64_REWORK_EDGE_COMPRESSION`;
   - CI artifact and readiness source revision.

3. **PR #64**
   - unchanged, corrected, or classified as a sub-lifecycle;
   - whether generic `ACCEPTED` is renamed;
   - whether `REWORK_REQUIRED` is explicit or represented through an approved adapter.

4. **PR #63**
   - operator disposition;
   - restart and replay evidence;
   - exact-head assurance;
   - truthful persistence metadata.

5. **Readiness ledger**
   - evidence paths for merged persistence;
   - separation of legacy work preparation, canonical lifecycle, and durable orchestration;
   - no unsupported score increase.

6. **Only after lifecycle resolution**
   - inspect atomic unit-of-work feasibility for job update, audit append, idempotency record, and full rollback.

Execution gate:

```text
IF PR #65 has unresolved blocking semantics:
    do not begin durable job service
    do not begin job API/UI
    do not begin connector execution
    report only changed evidence and corrections

IF PR #65 is resolved and exact-head assurance exists:
    correct or classify PR #64 in one separate reviewed change
```

## Governance closeout

```text
AIGC-only scope: preserved
Direct main write: no
Files deleted: no
Self-approval: no
Merge: no
Deployment: no
Credentials: no
Production data: no
External connector: no
External AIGC action: no
Readiness promoted: no
Rollback preserved: yes
Operator authority preserved: yes
Security & Privacy Wiring Gate preserved: yes
```
