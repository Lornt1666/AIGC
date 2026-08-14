# AIGC Architecture

## Architectural Authority

Justice Gray Maciocha is the accountable human operator and final source of consequential authority.

Omega-X is AIGC's constitutional supervisor and evolution governor. It may evaluate, coordinate, route, record, recommend, and propose bounded changes. It may not independently grant itself authority, bypass approval gates, activate infrastructure, use secrets, perform consequential external actions, alter accepted audit history, or represent generated capability as a legal credential.

## Operational Identity

AIGC is an autonomous career, occupation, and discipline worker. Its persistent identity is occupational rather than software-specific: it discovers opportunities, qualifies work, operates inside admitted disciplines, selects governed methods, executes bounded commissions, verifies outcomes, maintains evidence-backed professional history, and proposes continuing learning.

Auto-design, CHCM, Alpha Plan, coordination engineering, multi-agent execution, and software generation are governed methods available to the worker. They are not AIGC's identity, authority source, credential source, or completion authority.

Normative occupational architecture: [AIGC Occupational Autonomy Architecture v2](docs/architecture/AIGC_OCCUPATIONAL_AUTONOMY_V2.md).

Machine-readable contracts:

- [`schemas/aigc_occupational_control_plane.schema.json`](schemas/aigc_occupational_control_plane.schema.json)
- [`schemas/aigc_work_execution_plane.schema.json`](schemas/aigc_work_execution_plane.schema.json)

## Authority Precedence

Lower layers may refine work but may never override a higher layer:

```text
CareerConstitution
  > CareerMandate
  > WorkCommission
  > OutcomeContract
  > MethodGenome / TaskGraph
  > WorkAttempt Instructions
  > Model Output
```

`WorkCommission` and `OutcomeContract` are sealed occupational records after acceptance. Execution never mutates them. A material change creates a new commission/contract revision and supersedes any attempt bound to the old revision.

## Six-Plane Architecture

### 1. Governance Plane

**Owns:** constitutional supervision, policies, approval gates, emergency stop, evidence standards, readiness rules, evolution governance, and the maximum occupational authority ceiling.

**Does not own:** mutable execution state, provider execution, secret values, external communications, or fabricated professional evidence.

### 2. Occupational Control Plane

**Owns immutable or versioned occupational truth:**

- `CareerConstitution`
- `OccupationProfile` and `DisciplineProfile`
- `CareerMandate`
- immutable accepted `WorkCommission` revisions
- immutable `OutcomeContract` revisions
- `CompetencyGraph`
- `AuthorityEnvelope`
- stakeholder and professional-ethics context
- evidence-backed `WorkPortfolio`
- opportunity acceptance policy
- continuing-learning proposals

A `WorkCommission` becomes sealed when accepted. Its scope, authority envelope, discipline, requested outcome, risk tier, and acceptance basis cannot be altered by an executing agent. A material amendment creates revision `N+1` with explicit lineage to the prior revision.

The Occupational Control Plane may discover and qualify opportunities and issue/admit commissions. It may not invent licenses, credentials, employment status, contractual authority, payment authority, production authority, secret access, or identity claims.

Target occupational maturity is O4/O5 while consequential authority remains externally bounded.

### 3. Phase / Method Plane

**Owns how admitted work may be attempted:**

- research, assessment, drafting, compliance, quality, and evolution methods;
- Coordination Engineering and Alpha Plan;
- CHCM and bounded autodesign;
- `MethodGenome` candidate generation/comparison;
- TaskGraph planning;
- multi-agent planning and bounded specialist work.

It cannot mutate the governing WorkCommission or OutcomeContract. If method discovery reveals that the accepted scope is insufficient or contradictory, it must request a commission amendment rather than silently expanding execution.

Software-oriented autodesign is generalized to `MethodGenome` for software/API work, CAD/building design, automation, DevSecOps, technical documentation, research, construction planning, and other admitted disciplines.

### 4. Work Execution Plane

**Owns mutable execution state only:**

- `WorkAttempt`;
- TaskGraph execution state;
- agent/session/run identities;
- tool calls and capability leases;
- checkpoints and resumable state;
- bounded retries and rework;
- method-selection execution records;
- mutable worktrees/artifact staging;
- execution stop, cancellation, rollback, and no-progress state.

**Does not own and may not mutate:**

- `CareerConstitution`;
- `CareerMandate`;
- `WorkCommission`;
- `OutcomeContract`;
- occupational authority ceilings;
- verified evidence history.

Every `WorkAttempt` MUST bind to exact immutable occupational inputs:

```text
WorkAttempt
  -> WorkCommission@commission_revision + commission_sha256
  -> OutcomeContract@contract_revision + contract_sha256
  -> CareerMandate@version
  -> policy_version
  -> MethodGenome/TaskGraph revision
```

Before every consequential transition, the execution controller revalidates that these bindings remain current and unsuperseded. If any governing occupational revision changes, the active attempt enters `STALE_AUTHORIZATION` or `SUPERSEDED`; it may reconcile read-only state but may not continue consequential execution.

A commission amendment follows:

```text
WorkCommission@N
   -> amendment proposal
   -> occupational/governance decision
   -> WorkCommission@N+1 (new immutable record)
   -> old WorkAttempt becomes SUPERSEDED
   -> new WorkAttempt binds to N+1
```

A **Quest is no longer a domain authority object**. Legacy `Quest` identifiers/states may remain as UI or compatibility aliases during migration, but they must resolve to a `WorkCommission` and/or `WorkAttempt` and may never override either canonical record.

Canonical occupational lifecycle is split across ownership boundaries:

```text
OCCUPATIONAL CONTROL
OBSERVE
-> DISCOVER_OPPORTUNITY
-> QUALIFY
-> ACCEPT_WITHIN_MANDATE | APPROVAL_REQUIRED
-> CONTRACT / SEAL COMMISSION

WORK EXECUTION
-> PLAN_ATTEMPT
-> DESIGN_METHOD
-> EXECUTE
-> VERIFY
-> DELIVERY_READY

OCCUPATIONAL / EVIDENCE CLOSURE
-> DELIVER (when separately authorized)
-> RECORD_EVIDENCE
-> UPDATE_PORTFOLIO
-> REFLECT
-> PROPOSE_LEARNING
-> READY
```

Execution interruption states:

```text
BLOCKED
NO_PROGRESS
APPROVAL_REQUIRED
STALE_AUTHORIZATION
SUPERSEDED
ESCALATED
CANCELLED
FAILED
REWORK_REQUIRED
ROLLED_BACK
```

`DELIVERY_READY` is not external-delivery authority. Delivery remains separately authorized when its effect leaves the approved autonomous envelope.

### 5. Infrastructure Plane

Owns isolated compute, cloud/runtime environments, identities, networking, persistence, secrets infrastructure, observability, deployment surfaces, backup, and recovery. Infrastructure authority remains exact-revision, scoped, time-bounded, and independently revocable.

### 6. Evidence Plane

Owns structural and operational evidence, authorization/execution receipts, test/CI evidence, artifact digests, provenance, deployment/rollback receipts, competency evidence, delivery receipts, portfolio provenance, and current external-state verification.

The Evidence Plane records truth. It does not grant authority, mutate WorkCommission state, manufacture experience, or certify a legal credential without external proof.

## Plane Relationships

```text
Accountable Operator
        |
        v
Governance Plane
        |
        v
Occupational Control Plane
 immutable career / mandate / commission / outcome contract
        |
        v
Phase / Method Plane
 proposes HOW
        |
        v
Work Execution Plane
 mutable WorkAttempt only
        |
        v
Infrastructure Plane
        |
        v
Evidence Plane
        |
        +----> Governance + Occupational Control
```

## Commission Immutability Invariant

```text
COMMISSION_SEALED := accepted_at != null

IF COMMISSION_SEALED:
    mutation(scope | authority | discipline | requested_outcome | risk | acceptance_basis) = FORBIDDEN
    material_change = NEW_REVISION
```

A new revision never retroactively changes the authorization basis of an existing attempt.

## Attempt Binding Invariant

```text
ATTEMPT_ELIGIBLE :=
    commission_revision_is_exact
    AND commission_sha256_matches
    AND outcome_contract_revision_is_exact
    AND outcome_contract_sha256_matches
    AND career_mandate_version_is_current
    AND policy_version_is_current
    AND commission_is_not_superseded
    AND attempt_is_not_cancelled_or_revoked
```

Failure of any condition stops consequential execution.

## Work Acceptance Invariant

```text
AUTO_ACCEPT :=
    career_mandate_is_current
    AND discipline_is_admitted
    AND competency_gate_passes
    AND requested_outcome_is_testable
    AND authority_envelope_covers_all_planned_effects
    AND risk_tier_is_within_autonomous_ceiling
    AND financial_and_time_budgets_are_within_limits
    AND no_credential_or_license_claim_is_invented
    AND no_required_human_approval_is_missing
```

Otherwise work enters `APPROVAL_REQUIRED`, `BLOCKED`, or `DECLINED`.

## Work Completion Invariant

```text
WORK_COMPLETE :=
    sealed_commission_is_current
    AND exact_attempt_binding_is_valid
    AND outcome_contract_is_current
    AND required_artifacts_exist
    AND all_hard_gates_pass
    AND evidence_is_attempt_bound
    AND independent_verification_passes
    AND required_delivery_receipt_exists
    AND required_approval_is_valid
    AND external_state_is_current_when_applicable
    AND rollback_or_recovery_requirements_pass_when_applicable
    AND no_unresolved_blocking_finding_exists
```

Model self-report is never sufficient evidence of completion.

## Semantic No-Progress Invariant

Execution stops rather than loops when configured no-progress rules fire. Default policy is no more than three plan/execute/review cycles per task and no more than two retries for an identical failure class unless the sealed OutcomeContract explicitly defines a different bounded budget.

A stopped attempt emits a blocker/evidence receipt and enters `NO_PROGRESS`, `BLOCKED`, or `ESCALATED` rather than retry-until-green.

## Architectural Invariants

1. Authorization is not evidence of execution.
2. Structural evidence is not operational proof.
3. No plane may expand its own authority.
4. No consequential external action occurs without authority covering the exact effect.
5. All consequential transitions are exact-revision and evidence bound.
6. Secret values never enter repository files, prompts, logs, memory, or receipts.
7. Production readiness is calculated from canonical evidence, never manually asserted.
8. Occupational identity outranks Quest, Phase, CHCM, autodesign, task, attempt, and model instructions.
9. `WorkCommission` is immutable after acceptance; amendments create new revisions.
10. `WorkAttempt` is the mutable execution object and never owns occupational authority.
11. Every attempt binds to exact commission/contract revisions and digests.
12. Governing-revision drift forces `STALE_AUTHORIZATION`/`SUPERSEDED` before further consequential execution.
13. Quest is compatibility/UI state only, never canonical occupational or execution authority.
14. A generated skill claim is not a verified competency; verified competency is not a legal credential unless separately proven.
15. Portfolio experience requires attempt-bound delivery evidence.
16. Capability may grow autonomously; authority may not.
17. Auto-design is finite per execution and remains proposal-first until verification/admission.
18. One authoritative writer owns a mutable worktree/artifact set at a time; independent evaluators may read in parallel.
19. High-risk outcomes cannot be independently verified solely by the same execution lineage that authored them.
20. Repeated no-progress cycles terminate rather than consume unbounded time, tools, tokens, or money.
