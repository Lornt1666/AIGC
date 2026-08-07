# AIGC Canonical Domain Contract Foundation

Status: IMPLEMENTED CONTRACT LAYER — RUNTIME BEHAVIOR DEFERRED

## Purpose

This increment converts the Digital Work Colosseum architecture into dependency-light typed contracts. It does not implement live opportunity acquisition, employer communication, cloud mutation, model execution, billing, payment, App Store activity, or autonomous external effects.

## Contract boundaries

### Employer and confidentiality

`EmployerVault` establishes the default-deny employer boundary. Cross-employer document, secret, retrieval, prompt-context and training use are all false. Any future relaxation requires a separately reviewed policy and must not expose confidential employer content.

### Opportunity and engagement

`Opportunity` distinguishes digitally executable work from work requiring physical presence. `Engagement` and `WorkOrder` bind objectives to requirements and acceptance criteria. Authorization is represented explicitly rather than inferred from discovery or planning.

### Colosseum execution

`AgentCell` represents a capability-bounded role with explicit tools, data scopes, output schema, monetary ceiling and token ceiling. `Swarm` aggregates cells under a work order, confidentiality class, jurisdiction policy, verification policy, emergency-stop epoch and overall budgets. Agent-level maxima cannot exceed the parent Swarm ceilings.

### Verification and deliverables

`Deliverable` cannot exist without artifacts and acceptance criteria. `Verification` requires explicit checks, and a passing verification requires retained evidence. Generated output is not equivalent to employer-accepted work.

### Capability proof

`CapabilityEvidence` separates demonstrated capability from model confidence. `VERIFIED_CAPABLE` is invalid without evidence and successful attempts cannot exceed validated attempts.

### Multi-clock work accounting

`WorkLedgerEntry` tracks human, agent, compute, research, review, meeting, revision, blocked and employer-wait time independently. No contract in this package automatically converts compute or agent execution into human billable labor.

## Compute Exchange separation of responsibility

The Compute Exchange has three separate responsibilities:

1. **Admission** — decide whether a candidate satisfies hard capability, quality, reliability, confidentiality, jurisdiction, licensing, employer-policy, deadline and budget requirements.
2. **Procurement** — assemble an `ExecutionPortfolio` of admissible heterogeneous resources for the work order. Cost is a contextual objective, not the governing objective.
3. **Calibration** — compare `PortfolioPrediction` with `ComputePerformanceObservation` and `PortfolioOutcome` evidence to improve future predictions.

The canonical objective remains:

**BEST-FIT ADMISSIBLE EXECUTION PORTFOLIO FOR THE EMPLOYER'S OUTCOME**.

A cheaper candidate cannot satisfy a requirement merely because of price when jurisdiction, quality, reliability, licensing or capability gates fail.

## Typed objects added

- EmployerVault
- Opportunity
- Engagement
- WorkOrder
- AgentCell
- Swarm
- Deliverable
- Verification
- WorkLedgerEntry
- WorkLedger
- CapabilityEvidence
- ComputeRequirement
- ComputeCandidate
- ExecutionPortfolio
- PortfolioPrediction
- ComputePerformanceObservation
- PortfolioOutcome

## Schema bindings

- `schemas/colosseum/domain.schema.json`
- `schemas/compute_exchange/portfolio.schema.json`

These schemas are intended as cross-language contracts for future Swift, Python and cloud implementations. Runtime adapters should validate at trust boundaries rather than relying on Python dataclass construction alone.

## Deferred objects

The following remain architecture-level or future bounded increments rather than partially implemented placeholders:

- EmployerPolicyCompiler
- StatementOfWork parser/compiler
- OpportunityLegitimacyTribunal runtime
- SwarmScheduler
- DefinitionOfDoneCompiler
- OccupationalSkillPack registry
- HumanExpertiseEscalationRegistry
- IP/Licensing/Provenance runtime
- PlatformPolicyEngine runtime
- ChangeOrder/DisputeEngine
- InvoiceDraft compiler
- Reputation/Benchmark aggregation
- provider-specific Compute Exchange adapters
- live cloud/model procurement

## Validation intent

Focused tests assert fail-closed properties including:

- cross-employer access is rejected;
- digital-only opportunity claims cannot conflict with physical-presence requirements;
- child agent budgets cannot exceed Swarm budgets;
- successful verification and verified capability require evidence;
- work clocks remain separate;
- cheap resources cannot bypass jurisdiction, quality or commercial-license gates;
- observed performance measurements require evidence;
- portfolio predictions remain distinct from observed outcomes.

Hosted validation remains required. Repository writes do not constitute test execution.

## Authority

```text
direct_main_write=false
merge=false
automatic_merge=false
job_application_submission=false
employer_message_send=false
contract_acceptance=false
invoice_send=false
payment_collection=false
cloud_resource_creation=false
deployment=false
production_activation=false
public_traffic=false
live_model_call=false
credential_creation=false
financial_action=false
app_store_submission=false
app_store_release=false
```
