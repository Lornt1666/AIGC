# AIGC Engineering Constitution — AEC-001

Version: `1.0.0`
Authority class: `constitution`
Status: `ratified`

## Purpose

AEC-001 is the highest engineering authority for AIGC. It governs every architecture, agent, workflow, contract, implementation, test, review, deployment, operation, and evolution cycle. Lower-order standards, policies, procedures, controls, and implementations may refine this Constitution but may not contradict it.

## Supremacy and interpretation

When two requirements conflict, the higher authority prevails. If the conflict cannot be resolved deterministically, execution pauses for an accountable human ruling. Machine-readable rules enforce only the portions that can be expressed without unsafe interpretation. Human-readable text remains authoritative for meaning.

## Articles

### AEC-I — Foundational Value
Every capability must measurably improve correctness, safety, explainability, maintainability, measurability, usability, accessibility, production readiness, or operator trust.

### AEC-II — Truth
Planned, inferred, generated, hypothetical, structural, tested, staging, and production states must never be represented as interchangeable. Completion and maturity claims require evidence appropriate to the claim.

### AEC-III — Human Authority
AI may research, reason, engineer, verify, and explain. It may not silently assume organizational, legal, financial, security, or human authority.

### AEC-IV — Deny by Default
Every consequential request begins denied. Permission must be positively established. Possession of a link, token, identifier, reference, or artifact does not establish authority.

### AEC-V — Least Privilege
Authority is minimal, scoped, attributable, expiring, reviewable, and revocable.

### AEC-VI — Evidence
Repository artifacts are structural evidence; tests are behavioural evidence; runtime receipts are operational evidence; production history is observed evidence. Evidence classes must not be confused.

### AEC-VII — Evolution
Every evolution cycle must produce a measurable delta. Language generation alone is not progress.

### AEC-VIII — Architecture
Modules require a clear responsibility, explicit boundaries, deterministic interfaces, versioned contracts, and measurable behaviour.

### AEC-IX — Contract First
Externally consumed interfaces are contract-first. Unknown properties are rejected unless explicitly permitted.

### AEC-X — Identity and Attribution
Every consequential action, decision, authorization, session, and approval must be attributable and explainable.

### AEC-XI — Privacy
Collect, use, disclose, store, and retain only what is necessary for an explicit purpose and authority basis.

### AEC-XII — Accessibility
User-facing interfaces target WCAG 2.2 AA or stronger applicable requirements. Accessibility is designed, tested, and maintained.

### AEC-XIII — Security
Security is architectural. Consequential actions pass through identity, authorization, the Security & Privacy Wiring Gate, human approval where required, execution controls, and evidence recording.

### AEC-XIV — Production Readiness
Production readiness requires governance, testing, security, privacy, accessibility, identity, authorization, persistence, deployment, monitoring, recovery, documentation, and operational evidence.

### AEC-XV — Repository Governance
Every pull request states purpose, scope, exclusions, changed contracts, evidence, tests, risks, rollback, readiness impact, and review path.

### AEC-XVI — AI Role Boundaries
AI output is advisory or implementation evidence according to its actual provenance. AI output is not independent human review.

### AEC-XVII — Public Trust
AIGC must explain what it is doing, why, what information and authority are involved, who approved it, and how it can be stopped, changed, revoked, or recovered.

### AEC-XVIII — Evolution Engine Governance
Every contender records prerequisites, evidence, blocker state, measurable impact, integration risk, rollback boundary, and next unblocking action.

### AEC-XIX — Procurement Lifecycle
Procurement follows intent, requirements, verification, authorization, acquisition strategy, implementation, verification, validation, acceptance, deployment, observation, evolution, and retirement.

### AEC-XX — Engineering Excellence
Every reviewed cycle should make AIGC easier to understand, safer to operate, more correct, more measurable, more accessible, more maintainable, and more trustworthy.

### AEC-XXI — Simplicity
Complexity must justify itself by reducing greater system risk or complexity elsewhere.

### AEC-XXII — Determinism
Identical inputs, policies, contracts, and evidence should produce reproducible decisions. Nondeterminism must be explicit and bounded.

### AEC-XXIII — Observability
Critical systems expose sufficient telemetry to explain what occurred, why, when, under whose authority, and with what evidence.

### AEC-XXIV — Recoverability
Consequential operations define rollback, recovery, and verification before execution.

### AEC-XXV — Compatibility
External interfaces evolve through versioned contracts, deprecation, migration, and compatibility evidence.

### AEC-XXVI — Stewardship
Every governed artifact has an accountable steward for correctness, documentation, security, tests, compatibility, and architectural integrity.

### AEC-XXVII — Continuous Improvement
Improvements are preferred over rewrites unless a rewrite demonstrably reduces long-term risk or complexity.

### AEC-XXVIII — Explainability
Consequential decisions must be explainable to technical and non-technical audiences without exposing secrets or unnecessary personal data.

### AEC-XXIX — Modularity
Subsystems maximize cohesion, minimize coupling, and remain replaceable through explicit interfaces.

### AEC-XXX — Interoperability
External integrations use documented, versioned, platform-compliant interfaces and avoid unnecessary lock-in.

### AEC-XXXI — Resilience
Failures degrade safely and locally. Partial failures must not silently become systemic failures.

### AEC-XXXII — Ethical Engineering
Engineering decisions must consider foreseeable societal effects. High-impact actions retain meaningful human oversight.

## Constitutional invariants

1. No completion claim without evidence.
2. No consequential action without attributable authority.
3. No implicit permit.
4. No cross-tenant access.
5. No secret material in repository configuration.
6. No production-ready claim while blocking capabilities remain.
7. No merge with unresolved mandatory gates.
8. No implicit constitutional amendment.
9. No false human-identity or independence claim.
10. No blocking finding may be averaged away.

## Amendment rule

Every amendment requires a dedicated pull request, affected articles, rationale, threat and risk analysis, compatibility assessment, migration, rollback, version increment, required review path, operator ratification, and immutable amendment receipt.

## Exception and waiver rule

A waiver must be explicit, scoped, owned, risk-assessed, time-limited, revocable, auditable, and fail closed after expiry. Silent nonconformance is prohibited.

## Constitutional traceability

Every governed change must identify affected articles and classify each as:

- `conformant`
- `not_applicable`
- `exception_requested`
- `nonconformant_blocking`

`not_applicable` requires rationale. `exception_requested` requires an approved waiver. `nonconformant_blocking` stops advancement.

## Ratification state

AEC-001 was operator-ratified after exact-head CI, advisory review, scope-limited review-path disclosure, and merge of PR #42. The immutable ratification evidence is recorded in `governance/constitution/aec_001.ratification_receipt.json`. Ratification does not claim independent human review, certification, compliance, staging readiness, or production readiness.