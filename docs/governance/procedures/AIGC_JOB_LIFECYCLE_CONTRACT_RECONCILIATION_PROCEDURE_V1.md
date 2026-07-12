# AIGC Job Lifecycle Contract Reconciliation Procedure v1

Status: **Proposed / operator-controlled**  
Procedure ID: `AIGC-JOB-LIFECYCLE-RECONCILIATION-PROCEDURE-001`  
Applies to: `AIGC` only  
Parent program: GitHub Issue `#55`  
Implementation PR: GitHub PR `#65`  
Canonical contract: `AIGC-JOB-LIFECYCLE-001` version `1.0.0`  
External action performed: `false`

## 1. Purpose

This procedure governs how AIGC reconciles competing job-lifecycle vocabularies before any lifecycle state is persisted, exposed through an API or UI, used by an agent, or connected to an external-action pathway.

It converts semantic disagreement into an attributable, testable, reversible operator decision. It does not authorize runtime mutation, deployment, credentials, connectors, production identity, client communication, platform interaction, or external execution.

## 2. Governing principles

1. One canonical lifecycle contract is authoritative at a time.
2. Contract semantics precede runtime implementation.
3. Unknown states, contract versions, or mappings fail closed.
4. Operator authorization, policy authorization, counterparty decisions, connector execution, and verified outcomes are distinct facts.
5. An internal lifecycle transition never implies that an external action occurred.
6. Lossy or conflicting compatibility mappings require explicit operator review.
7. Automation may detect and explain conflicts; it may not ratify its own preferred meaning.
8. All implementation occurs on a separate branch and reviewed pull request.
9. Rollback must remain available before and after merge.
10. The Security & Privacy Wiring Gate must not be weakened.

## 3. Roles and authority

| Role | Responsibility | Authority boundary |
|---|---|---|
| Accountable operator | Selects canonical semantics, reviews final head, and decides merge | May approve repository changes; may not fabricate counterparty decisions |
| Implementation author | Prepares contracts, mappings, tests, and documentation | Cannot self-approve or merge without operator authorization |
| CI system | Validates contracts, tests, secret scans, and evidence binding | Cannot make semantic or merge decisions |
| Independent reviewer | Optional future role for additional assurance | Not claimed unless a distinct qualified reviewer actually participates |
| Deployment authority | Future role | Not granted by this procedure |

The accountable operator is currently Justice Gray Maciocha / Lornt / Satoshi. Independent review is not inferred from multiple automated roles.

## 4. Entry conditions

Begin this procedure only when at least one of the following is true:

- architecture documents and runtime code define different state meanings;
- a state identifier has multiple meanings;
- a compatibility mapping is marked `CONFLICTING`, `TRANSITION_EXPANSION_REQUIRED`, or `UNSUPPORTED`;
- a lifecycle change would affect durable storage, authority, UI wording, audit evidence, or external-action preconditions;
- an open PR introduces a lifecycle state or transition not represented by the canonical contract.

Current entry findings:

- `GENERIC_ACCEPTED_SEMANTIC_COLLISION`;
- `PR64_REWORK_EDGE_COMPRESSION`.

## 5. Required evidence inputs

The procedure must inspect and record exact revisions for:

1. current `main`;
2. the canonical lifecycle proposal;
3. the full-stack architecture program;
4. PR `#64` governed job-state kernel;
5. the legacy work-order preparation surface;
6. relevant schemas and tests;
7. CI workflow behavior and readiness evidence;
8. parent program Issue `#55`;
9. all unresolved review findings on the lifecycle PR.

Evidence must identify whether it describes:

- proposed semantics;
- implemented runtime behavior;
- merged behavior;
- structural evidence;
- operational evidence;
- production evidence.

These categories may not be conflated.

## 6. Ordered procedure

### Step 1 — Intake

Record:

- requested capability;
- operator intent;
- affected bounded contexts;
- prohibited outcomes;
- expected evidence;
- proposed branch and PR scope.

**Exit artifact:** bounded intake statement in the lifecycle PR and parent issue.

### Step 2 — Evidence verification

Inspect the exact repository evidence listed in Section 5. Do not rely on stale summaries when files, commits, CI runs, or PR heads have changed.

**Exit artifact:** revision-bound evidence inventory.

### Step 3 — Scope lock

The lifecycle reconciliation PR may contain only:

- schemas;
- canonical contract instances;
- compatibility maps;
- conflict detection or reconciliation logic;
- tests;
- governance documentation;
- registry or procedure metadata.

It may not contain:

- runtime job mutation;
- SQLite job migration;
- FastAPI or UI controls;
- connector invocation;
- credentials;
- deployment;
- readiness promotion;
- deletion of legacy modules.

**Exit artifact:** explicit scope and non-scope declaration.

### Step 4 — Contract-first design

Define or update:

- canonical states and meanings;
- lifecycle scopes;
- allowed transitions;
- authority classes;
- evidence requirements;
- reason requirements;
- rollback or compensation classes;
- external-action boundaries;
- compatibility policy.

Every state must have one unique meaning. Every transition must reference defined states and one defined authority class.

**Exit artifact:** schema-valid canonical lifecycle contract.

### Step 5 — Semantic decision gate

The operator must disposition each blocking or material finding.

For `GENERIC_ACCEPTED_SEMANTIC_COLLISION`, the proposed decision is:

- `WORK_ACCEPTED`: the operator authorizes AIGC to undertake bounded internal work;
- `ACCEPTED_FOR_DELIVERY`: the operator accepts reviewed work for a separate delivery action;
- generic canonical `ACCEPTED`: prohibited.

For `PR64_REWORK_EDGE_COMPRESSION`, the operator must choose exactly one:

1. **Explicit canonical rework:** PR `#64` later adds `REWORK_REQUIRED` before returning to research, planning, or local execution; or
2. **Compressed sub-lifecycle:** PR `#64` is formally classified as a subordinate internal adapter whose direct review-to-research edge maps to canonical `REWORK_REQUIRED` plus a subsequent execution transition.

Automation may recommend but cannot select the option.

**Exit artifact:** attributable operator decision recorded in the decision-tracking issue and referenced by PR `#65`.

### Step 6 — Compatibility reconciliation

For every source state, record:

- source contract and version;
- source state;
- canonical target state, if any;
- mapping status;
- rationale;
- whether operator review is required.

Allowed mapping statuses:

- `EXACT`;
- `SEMANTIC_RENAME`;
- `TRANSITION_EXPANSION_REQUIRED`;
- `CONFLICTING`;
- `UNSUPPORTED`.

Lossy, conflicting, or unsupported mappings must not be silently executed.

**Exit artifact:** schema-valid compatibility map with zero unresolved blocking conflict before ratification.

### Step 7 — Security and privacy wiring

Verify that:

- no personal or production data is introduced;
- examples are synthetic and minimum necessary;
- no state implies consent or counterparty acceptance;
- no state transition performs an external action;
- delivery requires a separate normalized execution receipt;
- no credentials, secrets, or token-shaped examples are committed;
- the Security & Privacy Wiring Gate remains mandatory.

**Exit artifact:** security/privacy control statement in the PR.

### Step 8 — Tests

Required tests include:

- schema validity;
- duplicate state and transition rejection;
- exactly one initial state;
- reachability;
- valid transition endpoints;
- authority-class references;
- terminal-state protection;
- generic `ACCEPTED` rejection;
- separate work and delivery acceptance states;
- delivery execution-receipt boundary;
- complete PR `#64` mapping;
- invalid compatibility target rejection;
- source-revision requirement;
- `external_action_performed=false`.

**Exit artifact:** reproducible test results.

### Step 9 — CI and exact-revision evidence

CI must pass:

1. exact expected revision selection;
2. checkout revision verification;
3. contract validation;
4. AEC-001 validation;
5. secret-like content scan;
6. lifecycle and full-suite tests;
7. readiness evaluation without capability promotion;
8. evidence artifact upload;
9. artifact name and readiness source revision equal to the immutable PR head.

A synthetic pull-request merge revision is not exact-head evidence.

**Exit artifact:** revision-bound CI receipt.

### Step 10 — Operator review

Present:

- final immutable head;
- contract and compatibility digests;
- resolved and residual findings;
- test and CI evidence;
- risk register;
- rollback plan;
- explicit non-capabilities.

**Exit artifact:** attributable operator review comment or decision record. This is not automatic approval.

### Step 11 — Merge decision

The operator may approve, reject, or request changes.

Merge is permitted only when:

- the reviewed head has not changed;
- mandatory CI gates pass;
- no blocking semantic finding remains;
- rollback remains valid;
- expected-head protection is used;
- the operator explicitly authorizes the merge.

**Exit artifact:** merge receipt or explicit rejection.

### Step 12 — Post-merge verification

After an authorized merge:

- record exact resulting `main` revision;
- rerun contract and full-suite validation;
- verify the registry resolves the canonical contract;
- confirm no runtime behavior or readiness status was silently changed;
- confirm rollback remains available.

**Exit artifact:** exact-main verification receipt.

### Step 13 — Readiness-ledger update

This contract-only change has an immediate readiness-score impact of `0`.

A separate reviewed PR may later:

- add evidence paths for the merged contract;
- split legacy work preparation from canonical lifecycle and durable orchestration;
- update capability status only to the level supported by merged evidence.

**Exit artifact:** separately reviewed readiness delta or an explicit no-change record.

### Step 14 — Follow-on implementation authorization

Only after semantic ratification and exact-main verification may a separate PR:

- correct or classify PR `#64`;
- implement a durable job application service;
- add API or UI controls;
- procure connector execution.

Each is an independent bounded train.

## 7. Stop conditions

Stop and return to operator review when:

- exact-head evidence is unavailable;
- a blocking semantic conflict remains;
- an unknown state or contract version appears;
- a mapping is lossy without operator approval;
- a proposed change introduces runtime or persistence scope;
- production identity or external execution is implied;
- the Security & Privacy Wiring Gate would be weakened;
- the PR head changes after review.

## 8. Rollback

Before merge:

- abandon the branch; or
- close the draft PR.

After an authorized squash merge:

1. revert the single squash commit;
2. restore the prior lifecycle registry reference, if present;
3. rerun schemas, lifecycle tests, and the full suite;
4. verify PR `#64` remains unmerged until separately reviewed;
5. record the rollback in Issue `#55`.

No database restoration or external compensation is required because this procedure is contract-only.

## 9. Required repository locations

| Information | Canonical location |
|---|---|
| Machine-readable lifecycle schema | `governance/schemas/jobs/job_lifecycle_contract.schema.json` |
| Canonical lifecycle instance | `governance/jobs/canonical_job_lifecycle_v1.json` |
| Compatibility-map schema | `governance/schemas/jobs/job_state_compatibility_map.schema.json` |
| Compatibility-map instance | `governance/jobs/job_state_compatibility_map_v1.json` |
| Lifecycle standard | `docs/governance/standards/AIGC_CANONICAL_JOB_LIFECYCLE_V1.md` |
| Reconciliation procedure | `docs/governance/procedures/AIGC_JOB_LIFECYCLE_CONTRACT_RECONCILIATION_PROCEDURE_V1.md` |
| Evolution/procurement assessment | `docs/governance/evolution/AIGC_EVOLUTION_PROCUREMENT_CYCLE_2026_07_12_JOB_LIFECYCLE_CONCORDANCE_V1.md` |
| Transformation backlog and procurement register | `docs/governance/evolution/AIGC_JOB_LIFECYCLE_TRANSFORMATION_BACKLOG_AND_PROCUREMENT_REGISTER_V1.md` |
| Program coordination | GitHub Issue `#55` |
| Semantic decision tracking | Dedicated operator decision issue linked from PR `#65` |
| Implementation review | GitHub PR `#65` |

## 10. Acceptance criteria

This procedure is correctly instantiated when:

- all required information has one declared repository location;
- the procedure is linked from PR `#65` and Issue `#55`;
- semantic decisions remain pending until attributed to the operator;
- the canonical contract and map remain machine-validatable;
- no runtime, persistence, UI, connector, credential, or deployment scope is introduced;
- exact-head evidence remains a merge gate;
- rollback and operator control are preserved.

## 11. Definition of done

```text
procedure documented
AND evidence locations declared
AND decision issue created
AND procurement register updated
AND PR body synchronized
AND parent program synchronized
AND CI passes on final head
AND no self-approval
AND no merge
AND no deployment
AND no external action
```

`external_action_performed: false`
