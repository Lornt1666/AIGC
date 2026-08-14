# AIGC Occupational Autonomy Architecture v2

## Purpose

AIGC is an autonomous career, occupation, and discipline worker. Software auto-design is one governed method available to that worker; it is not AIGC's identity, authority source, or completion authority.

This architecture places an Occupational Control Plane between constitutional governance and execution. It preserves the existing evidence-first, bounded-authority posture while making career identity, discipline competence, work acceptance, professional obligations, and continuing learning first-class system state.

## Root invariant

> AIGC is an autonomous occupational actor first. Auto-design is a governed method capability used to perform professional work; it is not AIGC's identity, authority source, or completion authority.

## Authority precedence

```text
CareerConstitution
  > CareerMandate
  > WorkCommission
  > OutcomeContract
  > MethodGenome / TaskGraph
  > WorkAttempt Instructions
  > Model Output
```

A model response, agent plan, generated test, CHCM proposal, Quest transition, autodesign iteration, or mutable WorkAttempt state cannot create permission absent from governing occupational artifacts.

## Canonical object boundary

AIGC distinguishes **occupational truth** from **execution state**.

### Immutable/versioned occupational state

- `CareerConstitution`
- `CareerMandate`
- accepted `WorkCommission` revision
- accepted `OutcomeContract` revision
- occupational `AuthorityEnvelope`
- discipline and competency requirements

### Mutable execution state

- `WorkAttempt`
- TaskGraph node state
- selected MethodGenome execution state
- checkpoints
- retries/rework
- tool-call state
- worktree/artifact staging
- cancellation/rollback/no-progress state

A WorkAttempt may reference occupational state but may never mutate it.

## Six-plane architecture

### 1. Governance Plane

Owns constitutional policy, approval rules, risk classes, emergency stop, audit invariants, evidence standards, and authority ceilings.

### 2. Occupational Control Plane

Owns durable professional identity and occupational contracts.

First-class objects:

- `CareerConstitution`
- `OccupationProfile`
- `DisciplineProfile`
- `CareerMandate`
- immutable accepted `WorkCommission` revisions
- immutable `OutcomeContract` revisions
- `CompetencyGraph`
- `AuthorityEnvelope`
- `StakeholderContext`
- `ProfessionalEthicsProfile`
- evidence-backed `WorkPortfolio`

#### WorkCommission sealing

A proposed commission may be edited during qualification. Once accepted, it is sealed.

```text
PROPOSED_COMMISSION
  -> qualification / approval
  -> ACCEPTED
  -> SEALED WorkCommission@N
```

After sealing, these fields are immutable for that revision:

- discipline;
- source/stakeholder identity;
- requested outcome;
- scope and exclusions;
- acceptance basis;
- authority envelope;
- risk tier;
- budget ceilings;
- governing mandate version.

Material change creates `WorkCommission@N+1` with explicit parent lineage. It does not mutate `N`.

The same rule applies to `OutcomeContract`: a changed completion gate, evidence requirement, delivery obligation, or no-progress budget creates a new contract revision.

### 3. Phase / Method Plane

Owns research, assessment, drafting, design search, planning, testing, transformation, and bounded multi-agent methods. Existing Phase/Batch functions, coordination engine, Alpha Plan, CHCM, and autodesign live here.

Auto-design is generalized as `MethodGenome`: a versioned description of how AIGC proposes to perform a commission. Method discovery cannot silently broaden commission scope or authority. If the selected method needs a materially different effect, budget, recipient, credential, or infrastructure permission, it must request an occupational amendment.

### 4. Work Execution Plane

Plane 4 owns **WorkAttempt**, not WorkCommission.

A `WorkAttempt` is the mutable runtime instance that tries to satisfy one sealed commission/contract pair.

It owns:

- attempt identity and parent lineage;
- mutable execution status;
- TaskGraph progress;
- MethodGenome selection/execution state;
- agent, model, session, and tool-call identities;
- capability leases;
- worktree and staged-artifact references;
- checkpoint/recovery state;
- retry/rework counters;
- no-progress, cancellation, failure, and rollback state.

It does **not** own:

- occupational identity;
- commission scope;
- outcome requirements;
- authority envelope;
- risk ceiling;
- legal/credential claims;
- evidence history.

Every attempt is pinned to exact occupational inputs:

```text
work_attempt_id
commission_id
commission_revision
commission_sha256
outcome_contract_id
outcome_contract_revision
outcome_contract_sha256
career_mandate_id
career_mandate_version
policy_version
method_genome_id / task_graph_version
```

#### Attempt eligibility

```text
ATTEMPT_ELIGIBLE :=
    commission_revision_is_exact
    AND commission_sha256_matches
    AND outcome_contract_revision_is_exact
    AND outcome_contract_sha256_matches
    AND mandate_version_is_current
    AND policy_version_is_current
    AND commission_is_not_superseded
    AND attempt_is_not_revoked
```

The controller rechecks this before every consequential transition.

#### Stale authorization

If a governing record changes, the active attempt cannot simply inherit the new authority.

```text
WorkCommission@N / OutcomeContract@M changes
   -> active WorkAttempt becomes STALE_AUTHORIZATION or SUPERSEDED
   -> read-only reconciliation may occur
   -> consequential execution stops
   -> new WorkAttempt must bind to the admitted new revision
```

This prevents contract/execution drift and stale approval reuse.

#### Quest compatibility

`Quest` is retained only as a migration/UI compatibility concept. It is not a domain authority object.

A legacy Quest must resolve to canonical records such as:

```text
Quest alias
  -> WorkCommission identity/revision
  -> active/latest WorkAttempt identity
```

A Quest transition may never alter a sealed commission or bypass WorkAttempt eligibility.

### 5. Infrastructure Plane

Owns execution environments, deployment surfaces, secret infrastructure, identities, networks, persistence, observability, and recovery. Infrastructure authority remains exact-revision, scoped, time-bounded, and independently revocable.

### 6. Evidence Plane

Owns attempt-bound proof of work, test results, provenance, delivery receipts, competency evidence, portfolio receipts, external-state verification, and release/runtime evidence. Evidence records truth; it never grants authority.

## Occupational lifecycle with ownership separation

```text
OCCUPATIONAL CONTROL
OBSERVE
-> DISCOVER_OPPORTUNITY
-> QUALIFY
-> ACCEPT_WITHIN_MANDATE | APPROVAL_REQUIRED
-> SEAL_COMMISSION_AND_OUTCOME_CONTRACT

METHOD + EXECUTION
-> CREATE_WORK_ATTEMPT
-> DESIGN_METHOD
-> EXECUTE
-> VERIFY
-> DELIVERY_READY

OCCUPATIONAL / EVIDENCE CLOSURE
-> DELIVER (only when separately authorized if consequential)
-> RECORD_EVIDENCE
-> UPDATE_PORTFOLIO
-> REFLECT
-> PROPOSE_LEARNING
-> READY
```

Cross-cutting execution states:

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

## Occupational autonomy levels

```text
O0 OBSERVER
O1 ASSISTANT
O2 INDEPENDENT_TASK_WORKER
O3 BOUNDED_PROFESSIONAL
O4 AUTONOMOUS_CAREER_OPERATOR
O5 GOVERNED_MULTI_DISCIPLINE_PROFESSIONAL
```

AIGC's target is O4/O5. O5 does not include self-licensing, self-contracting beyond mandate, self-payment authority, self-promotion to production, or self-approval.

## Work acceptance rule

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

Acceptance produces a sealed commission revision and a sealed outcome-contract revision. Otherwise the commission remains proposed or enters `APPROVAL_REQUIRED`, `BLOCKED`, or `DECLINED`.

## Work completion rule

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

An agent statement that work is done is never sufficient evidence.

## Evaluator mesh by discipline

Every DisciplineProfile must declare appropriate evaluators. Deterministic and external evidence outrank model judgment.

- Software/API: compile, type, unit, integration, property, mutation, security, architecture tests.
- CAD/building design: dimensional constraints, authoritative code/standard checks, geometry/clash validation, deliverable-format checks, professional review where required.
- Research: source authority, citation traceability, contradiction search, recency, reproducibility, uncertainty labeling.
- Technical documentation: requirement coverage, factual traceability, schema/format conformance, readability/accessibility.
- Automation/DevSecOps: sandbox execution, policy tests, secret scans, least privilege, rollback, idempotency, observability, exact-revision receipts.

A discipline may not claim autonomous completion until its minimum evaluator set is defined.

## Competency graph

```text
UNKNOWN -> LEARNING -> DEMONSTRATED -> VERIFIED
                    \-> RESTRICTED
VERIFIED -> STALE -> REVALIDATION_REQUIRED
```

Demonstrated skill, verified competency, and legal credential status remain separate.

## Method design and evolutionary improvement

For nontrivial commissions AIGC may create several MethodGenome candidates, evaluate hard constraints, and retain Pareto-efficient methods across correctness, safety, quality, latency, cost, maintainability, reversibility, and stakeholder value.

Learning remains governed:

```text
runtime observation
-> learning hypothesis
-> proposed competency/method change
-> isolated evaluation
-> holdout/adversarial evaluation
-> independent verification
-> admission decision
-> bounded adoption
```

AIGC may improve methods and propose competency updates. It may not raise its own authority ceiling, fabricate portfolio evidence, weaken evaluator requirements, mutate sealed commissions, or silently alter the CareerConstitution.

## One-writer and multi-agent rule

Read-only scouts, researchers, critics, and evaluators may operate in parallel. One authoritative writer owns any mutable WorkAttempt/worktree artifact set at a time. Independent verification must not depend solely on that writer's explanation or tests.

## Semantic no-progress circuit breaker

`NO_PROGRESS` belongs to WorkAttempt state, not WorkCommission state.

Default bounded policy:

- maximum three plan/execute/review cycles per task unless the sealed OutcomeContract explicitly permits more;
- maximum two retries for an identical failure class;
- one active implementation writer per mutable artifact set;
- explicit token, tool, time, and financial budgets;
- escalation with a blocker receipt rather than retry-until-green.

## Evidence and provenance identities

At minimum, durable state distinguishes:

```text
career_id
career_mandate_id
career_mandate_version
occupation_profile_id
discipline_profile_id
work_commission_id
work_commission_revision
work_commission_sha256
outcome_contract_id
outcome_contract_revision
outcome_contract_sha256
work_attempt_id
parent_work_attempt_id
task_id
task_graph_version
agent_definition_id
model_id
model_snapshot
method_genome_id
toolchain_digest
base_revision
worktree_id
capability_lease_id
policy_version
action_digest
approval_id
evidence_bundle_hash
delivery_receipt_id
portfolio_entry_id
runtime_observation_id
learning_proposal_id
```

## Architectural acceptance tests

A compliant implementation must prove at least:

1. Phase/autodesign/Quest compatibility code cannot override the CareerConstitution.
2. A commission outside the CareerMandate cannot auto-accept.
3. Accepted WorkCommission and OutcomeContract revisions cannot be mutated by execution code.
4. Every WorkAttempt binds to exact commission and outcome-contract revisions/digests.
5. Governing revision drift forces `STALE_AUTHORIZATION` or `SUPERSEDED` before consequential continuation.
6. A superseded attempt cannot reuse stale approval for a new commission revision.
7. Quest remains an alias and cannot become canonical authority.
8. A discipline without competency/evaluator gates cannot claim autonomous completion.
9. The same attempt lineage cannot authoritatively implement and independently verify a high-risk outcome.
10. Repeated no-progress cycles terminate with evidence.
11. Portfolio entries require verified delivery evidence.
12. Learning proposals cannot raise authority or weaken constitutional gates without independent governance transition.
13. Autodesign remains finite per execution and proposal-first.

## Migration from current AIGC design

1. Insert the Occupational Control Plane between Governance and method/execution.
2. Freeze accepted WorkCommission/OutcomeContract revisions as immutable occupational records.
3. Introduce WorkAttempt as the sole mutable execution aggregate.
4. Convert legacy Quest state to compatibility aliases over WorkCommission + WorkAttempt rather than treating Quest as canonical authority.
5. Generalize software autodesign into MethodGenome candidates.
6. Bind attempts, approvals, evidence, and portfolio claims to exact revisions and digests.
7. Add stale-authorization and supersession gates before runtime implementation.
8. Add semantic no-progress and independent-verification gates.
9. Keep all existing external-action, secret, deployment, spending, and production gates intact.

This architecture turns AIGC into a coherent autonomous professional operating system while preventing the execution engine from rewriting the very contract that authorizes its work.