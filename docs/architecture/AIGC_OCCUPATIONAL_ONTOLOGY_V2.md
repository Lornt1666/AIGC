# AIGC Occupational Ontology V2

## Purpose

Extend AIGC from a task-capable autonomous worker into an evidence-governed multi-disciplinary occupational operating system.

The occupational lifecycle is:

```text
Identity -> Scope -> Competence -> Commission -> Method -> Execution -> Evidence -> Experience -> Development
```

The earlier execution invariant remains supreme:

> Occupational Control issues immutable truth. Method proposes how. WorkAttempt executes. Evidence proves what happened. Execution can never rewrite the contract that authorized it.

## Canonical ontology

```text
Career
├── Profession
│   └── Occupation
│       └── Discipline
│           └── Specialization
│               └── Role
│                   ├── Capability
│                   ├── Competency
│                   ├── Skill
│                   └── Technique
├── CredentialGraph
├── ExperienceGraph
├── Portfolio
├── Reputation
├── ContinuingDevelopment
└── CareerTrajectory
```

These are distinct concepts. Capability is not competency. Competency is not credential. Credential is not authority. Reputation is not authority. Evidence is not authority.

## Scope-of-practice law

```text
ACTION_PERMITTED :=
    CapabilityPresent
    AND CompetencySufficient
    AND ScopeOfPracticePermits
    AND AuthorityValid
    AND JurisdictionValid
```

A discipline may independently permit, permit only with review, mark credential-restricted, prohibit, or attach jurisdictional dependencies to work classes.

## Competency law

Competency levels are evidence-sensitive and may progress through:

```text
UNKNOWN -> EXPOSED -> LEARNING -> ASSISTED -> DEMONSTRATED -> INDEPENDENT -> VERIFIED -> ADVANCED -> EXPERT
```

Staleness and revalidation are explicit states. VERIFIED-or-higher claims require evidence receipts. AIGC may never infer a protected credential from demonstrated capability.

## Experience law

A completed WorkCommission can enter ExperienceGraph only through an ExperienceNode tied to evidence receipts. Accepted work without evidence is not accepted experience.

## Career development law

DevelopmentPlan expresses a target competency, current state, required state, gaps, development actions, and promotion evidence. Reading material alone does not promote competency.

## Interdisciplinary practice

Cross-domain work is modeled as composition, not a new unrestricted super-discipline. InterdisciplinaryPractice lists contributing disciplines, required competencies, synthesis MethodGenomes, and evaluator profile.

## Engagement and economics

Engagement groups client-level terms and one or more WorkCommissions. It never replaces WorkCommission as the execution authorization object.

CommissionEconomics measures expected utility from compensation, portfolio value, learning value, strategic value, execution costs, review costs, opportunity costs, and risk costs. Economics may rank opportunities but may not override authority or risk policy.

## Registry

`config/aigc_occupational_registry.v2.json` is the plugin-oriented registry. New disciplines should be registered through profiles that reference ScopeOfPractice, StandardOfPractice, competency requirements, evaluator profile, MethodGenomes, risk ceiling, credentials, and tool capabilities.

## Non-authority objects

The following may inform decisions but never grant execution authority:

- CompetencyRecord
- CredentialRecord
- ExperienceNode
- Reputation score
- CareerTrajectory
- CommissionEconomics
- DevelopmentPlan
- EngineeringMemory

Only the active WorkCommission/OutcomeContract/AuthorityEnvelope lineage authorizes execution.
