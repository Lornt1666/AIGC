# AIGC Occupational Autonomy Architecture v2

## Purpose

AIGC is an autonomous career, occupation, and discipline worker. Software auto-design is one governed method available to that worker; it is not AIGC's identity, authority source, or completion authority.

This architecture places an Occupational Control Plane between constitutional governance and execution. It preserves the existing evidence-first, bounded-authority posture while making career identity, discipline competence, work acceptance, professional obligations, and continuing learning first-class system state.

## Root invariant

> AIGC is an autonomous occupational actor first. Auto-design is a governed method capability used to perform professional work; it is not AIGC's identity, authority source, or completion authority.

## Authority precedence

The following order is normative. Lower layers may refine but may never override higher layers.

```text
CareerConstitution
  > CareerMandate
  > WorkCommission
  > OutcomeContract
  > MethodGenome / TaskGraph
  > Attempt Instructions
  > Model Output
```

A model response, agent plan, generated test, CHCM proposal, Quest transition, or autodesign iteration cannot create a permission that is absent from the governing occupational artifacts.

## Six-plane architecture

### 1. Governance Plane

Owns constitutional policy, approval rules, risk classes, emergency stop, audit invariants, evidence standards, and authority ceilings.

### 2. Occupational Control Plane

Owns the durable professional identity of AIGC.

First-class objects:

- `CareerConstitution`: immutable worker mission, professional boundaries, ethics, and evidence obligations.
- `OccupationProfile`: a named occupation and its expected responsibilities, competencies, and standards.
- `DisciplineProfile`: a bounded technical or professional discipline and its competency requirements.
- `CareerMandate`: the currently authorized occupational scope, goals, budgets, and opportunity policy.
- `WorkCommission`: one accepted unit of professional work with client/source, discipline, outcome, scope, and authority envelope.
- `OutcomeContract`: measurable completion and evidence requirements for a commission.
- `CompetencyGraph`: demonstrated, inferred, unverified, and prohibited competency claims with evidence links.
- `AuthorityEnvelope`: explicit autonomous, approval-required, and prohibited actions.
- `StakeholderContext`: accountable humans, clients, users, affected parties, and communication boundaries.
- `ProfessionalEthicsProfile`: discipline-specific ethical and safety obligations.
- `WorkPortfolio`: verified delivered outcomes and provenance; never inflated by generated claims.

The Occupational Plane may discover and qualify opportunities, select methods, schedule bounded work, and propose learning. It may not invent credentials, licenses, contractual authority, payment authority, production authority, or access to secrets.

### 3. Phase / Method Plane

Owns research, assessment, drafting, design search, planning, transformation, testing, and bounded multi-agent methods. The existing Phase / Batch functions, coordination engine, Alpha Plan, CHCM, and autodesign kernel live here.

Auto-design is generalized as a `MethodGenome`: a versioned description of how AIGC proposes to perform a commission. Software architecture search is one possible MethodGenome; CAD design, technical documentation, construction planning, research, API integration, automation, DevSecOps, and other disciplines may define their own method candidates and evaluators.

### 4. Quest / Work Plane

Owns transactional work state. A Quest is a runtime representation of a WorkCommission; it is not the occupational identity itself.

Canonical occupational lifecycle:

```text
OBSERVE
-> DISCOVER_OPPORTUNITY
-> QUALIFY
-> ACCEPT_WITHIN_MANDATE | APPROVAL_REQUIRED
-> CONTRACT
-> DESIGN_METHOD
-> EXECUTE
-> VERIFY
-> DELIVER
-> RECORD_EVIDENCE
-> UPDATE_PORTFOLIO
-> REFLECT
-> PROPOSE_LEARNING
-> READY
```

Cross-cutting interruption states:

```text
BLOCKED
NO_PROGRESS
APPROVAL_REQUIRED
ESCALATED
CANCELLED
FAILED
REWORK_REQUIRED
ROLLED_BACK
```

`DELIVER` remains separately authority-gated when delivery causes a consequential external effect.

### 5. Infrastructure Plane

Owns execution environments, deployment surfaces, secret infrastructure, identities, networks, persistence, observability, and recovery. Infrastructure authority remains exact-revision, scoped, time-bounded, and independently revocable.

### 6. Evidence Plane

Owns attempt-bound proof of work, test results, provenance, delivery receipts, competency evidence, portfolio receipts, external-state verification, and release/runtime evidence. Evidence records truth; it never grants authority.

## Occupational autonomy levels

```text
O0 OBSERVER
   Observe and learn; no independent work execution.

O1 ASSISTANT
   Produce bounded internal artifacts under direct review.

O2 INDEPENDENT_TASK_WORKER
   Execute low-risk tasks within explicit contracts and deterministic gates.

O3 BOUNDED_PROFESSIONAL
   Perform complete commissions inside one or more admitted disciplines.

O4 AUTONOMOUS_CAREER_OPERATOR
   Discover, qualify, accept within mandate, execute, verify, and maintain a portfolio.

O5 GOVERNED_MULTI_DISCIPLINE_PROFESSIONAL
   Operate across admitted disciplines, choose/evolve methods, and conduct continuing learning while authority remains externally bounded.
```

AIGC's target is O4/O5. O5 does not include self-licensing, self-contracting beyond mandate, self-payment authority, self-promotion to production, or self-approval.

## Work acceptance rule

AIGC may autonomously accept a WorkCommission only when all of the following are true:

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

Otherwise the commission enters `APPROVAL_REQUIRED`, `BLOCKED`, or `DECLINED` rather than being silently accepted.

## Work completion rule

A commission is complete only when:

```text
WORK_COMPLETE :=
    career_mandate_is_current
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

Every DisciplineProfile must declare evaluators appropriate to the work. Deterministic and external evidence outrank model judgment.

Examples:

- Software/API: compile, type checks, unit/integration/property/mutation/security/architecture tests.
- CAD/building design: dimensional constraints, code/standard checks where authoritative data is available, geometry validation, clash checks, deliverable-format checks, human professional review when required.
- Research: source quality, citation traceability, contradiction search, recency checks, reproducibility, uncertainty labeling.
- Technical documentation: requirement coverage, factual traceability, schema/format conformance, readability/accessibility review.
- Automation/DevSecOps: sandbox execution, policy tests, secret scans, least privilege, rollback, idempotency, observability, exact-revision receipts.

A discipline may not claim autonomous completion until its minimum evaluator set is defined.

## Competency graph

Competency state is evidence-sensitive:

```text
UNKNOWN -> LEARNING -> DEMONSTRATED -> VERIFIED
                    \-> RESTRICTED
VERIFIED -> STALE -> REVALIDATION_REQUIRED
```

Each claim records:

- discipline and competency identifier;
- evidence references;
- verification method;
- verifier identity or deterministic oracle;
- validity/expiry where relevant;
- legal credential status separately from demonstrated skill.

A demonstrated skill must never be represented as a legally protected credential or license unless external evidence proves that credential.

## Method design and evolutionary improvement

For every nontrivial commission AIGC may create several MethodGenome candidates, evaluate hard constraints, and retain Pareto-efficient methods across correctness, safety, quality, latency, cost, maintainability, reversibility, and stakeholder value.

Learning is governed:

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

AIGC may autonomously improve methods and propose competency updates. It may not raise its own authority ceiling, fabricate portfolio evidence, weaken evaluator requirements, or silently alter the CareerConstitution.

## One-writer and multi-agent rule

Read-only scouts, researchers, critics, and evaluators may operate in parallel. One authoritative writer owns any mutable worktree or commission artifact set at a time. Independent verification must not depend solely on the writer's own explanation or tests.

## Semantic no-progress circuit breaker

An attempt enters `NO_PROGRESS` when any configured stop rule fires, including repeated equivalent failures, repeated plans without new evidence, repeated reviews without accepted change, unchanged implementation with repeated tool calls, or exhaustion of the commission's iteration/cost budget.

Default bounded policy:

- maximum three plan/execute/review cycles per task unless the WorkCommission explicitly permits more;
- maximum two retries for an identical failure class;
- one active implementation writer per mutable artifact set;
- explicit token, tool, time, and financial budgets;
- escalation with a blocker receipt rather than retry-until-green.

## Evidence and provenance identities

At minimum, durable state should distinguish:

```text
career_id
career_mandate_id
career_mandate_version
occupation_profile_id
discipline_profile_id
work_commission_id
outcome_contract_id
task_id
task_graph_version
attempt_id
parent_attempt_id
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

Task identity, execution identity, conversational identity, source revision, approval identity, and delivery identity must never be collapsed into one generic `run_id`.

## Architectural acceptance tests

A compliant implementation must prove at least these properties:

1. Quest/Phase/autodesign code cannot override the CareerConstitution.
2. A commission outside the CareerMandate cannot auto-accept.
3. A discipline without a competency/evaluator gate cannot claim autonomous completion.
4. A model cannot grant credentials, licenses, secrets, money, contractual authority, or production authority.
5. Approval is bound to the exact consequential action and cannot be replayed after material change.
6. The same attempt lineage cannot authoritatively implement and independently verify a high-risk outcome.
7. Repeated no-progress cycles terminate with evidence rather than loop indefinitely.
8. Portfolio entries require verified delivery evidence; generated narratives cannot create experience.
9. Learning proposals cannot raise authority or weaken constitutional gates without an independent governance transition.
10. Autodesign remains finite per execution and proposal-first; capability growth never implies authority growth.

## Migration from the current AIGC design

The existing five-plane architecture remains structurally useful. Migration is additive:

1. Insert the Occupational Control Plane between Governance and Phase/Quest execution.
2. Treat existing Quests as runtime WorkCommissions and map their lifecycle to the occupational lifecycle.
3. Generalize software-oriented autodesign candidates into MethodGenome candidates so all admitted disciplines can use the same search/evaluation machinery.
4. Add CareerConstitution, CareerMandate, WorkCommission, OutcomeContract, CompetencyGraph, and AuthorityEnvelope schemas.
5. Bind evidence and portfolio claims to attempts and delivery receipts.
6. Add semantic no-progress and independent-verification gates to the execution state machine.
7. Keep all current external-action, secret, deployment, spending, and production gates intact until separately authorized and verified.

This architecture changes AIGC from a collection of governed phases plus an autodesign kernel into a coherent autonomous professional operating system: career identity at the top, disciplines beneath it, governed methods beneath disciplines, and evidence underneath every claim.