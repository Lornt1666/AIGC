# AIGC Colosseum Orchestration Kernel V1

Status: implementation candidate; no live execution authority.

## Operational chain

EmployerPolicy → EffectivePolicy → DefinitionOfDone → TaskDAG → SwarmScheduler → AgentAssignment → VerificationPlan → ComputeRequirement → Compute Exchange.

The contract/engagement layer defines the employer outcome. The policy compiler intersects that requirement with mandatory AIGC platform controls. DefinitionOfDone makes completion measurable before work is scheduled. TaskDAG represents dependency and critical-path structure. SwarmScheduler deterministically produces bounded specialist assignments and independent verification assignments. It emits ComputeRequirement objects only; it does not choose providers/models/resources. The Compute Exchange remains the sole procurement boundary for admissible execution portfolios.

## Invariants

- Platform security, privacy, confidentiality, jurisdiction, deny rules, and verification requirements cannot be weakened by employer policy.
- Employer data scopes remain vault-bound and cross-employer scopes cannot be scheduled.
- Capability evidence, rather than model confidence, gates agent-role eligibility.
- NOT_QUALIFIED and RESEARCH_REQUIRED capabilities cannot be assigned for execution.
- LEGALLY_RESTRICTED capabilities require a licensed specialist role.
- CAPABLE_WITH_REVIEW forces review.
- Task DAGs reject unknown dependencies and cycles.
- External-effect tasks require idempotency metadata; V1 still grants no execution authority.
- Agent assignment budgets remain subordinate to the plan budget.
- Builders cannot self-certify when independent verification is required.
- SwarmScheduler cannot select a ComputeCandidate or ExecutionPortfolio; it only emits requirements.
- Scheduling decisions are deterministic for identical inputs and preserve an input digest plus evidence/policy references.

## Scope intentionally deferred

No live agents, provider calls, Gemini/OpenAI calls, job discovery/submission, employer messaging, contract acceptance, invoice transmission, cloud mutation, payment action, production credential, deployment, merge, or App Store action is implemented by this increment.

## Next proof

After exact-head hosted CI and governed review, the preferred proving slice is a synthetic engagement: simulated employer policy and contract → bounded WorkOrder → DefinitionOfDone → TaskDAG → SwarmPlan → ComputeRequirements → mock Compute Exchange portfolio → synthetic artifact → verification receipt → work ledger → mock acceptance → invoice draft.
