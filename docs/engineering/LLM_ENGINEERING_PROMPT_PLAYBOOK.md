# Governed LLM Engineering Prompt Playbook

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

Status: Proposed engineering standard for repository adoption. Documentation-only; this file does not grant runtime permissions or authorize external actions.

## Purpose

Constrain LLM-assisted engineering to repeatable, evidence-led workflows. Use the smallest workflow that fits the task, preserve contracts and governance, and convert findings into verifiable changes where authorized. The model must inspect the actual repository and environment before choosing a fix; prompts are not substitutes for tests, human review, or CI.

This playbook is intended first for AIGC and is reusable by related 1JGM / RegenExcalibur software projects after adapting their own authority, safety, and release boundaries. Do not copy AIGC-specific runtime permissions into another project without review.

## Operating contract — applies to every engineering task

1. **Establish reality:** inspect the current branch, exact commit, relevant files, tests, runtime configuration, and authoritative CI evidence. Identify what is observed, inferred, assumed, and unknown.
2. **Constrain scope:** state the task objective, non-goals, public contracts, security invariants, allowed actions, and approval boundary before editing.
3. **Diagnose before patching:** trace data/control flow to the earliest meaningful failure. Rank hypotheses only when useful, attach evidence and a falsification test to each, and do not present speculation as root cause.
4. **Prefer minimal, reversible changes:** no unrelated refactors, feature creep, weakened assertions, skipped tests, swallowed exceptions, broad permissions, or behavior changes disguised as cleanup.
5. **Test the invariant, not merely the implementation:** add regression, boundary, adversarial, and property-based tests where proportionate. A test that only repeats the implementation's assumptions is insufficient.
6. **Protect trust boundaries:** validate untrusted input at entry; enforce authentication and authorization server-side; use least privilege; redact logs; keep secrets out of prompts, artifacts, fixtures, and commits.
7. **Verify exact artifacts:** run focused tests, relevant suites, static checks, and the canonical validation workflow. Record the tested commit SHA and distinguish pass, fail, skipped, blocked, and not run.
8. **Review the diff adversarially:** inspect the complete diff for security, concurrency, performance, contract drift, secret leakage, accidental scope expansion, and test weakening.
9. **Report evidence and uncertainty:** provide concrete links, commands, outcomes, changed paths, unresolved blockers, and the next action. Never invent results, sources, measurements, approvals, or capabilities.
10. **Respect authority:** repository write permission is not production authorization. External side effects, secrets access, billing changes, release promotion, deployment, migrations, merge, and communication require the relevant explicit authorization.

### Evidence labels

- **Observed:** directly verified from repository state, command output, CI, or an authoritative source.
- **Derived:** follows from observed evidence with the reasoning stated.
- **Hypothesis:** plausible explanation awaiting a discriminating test.
- **Unknown / blocked:** unavailable or not verified; name the missing evidence or permission.

Do not report a gate as passed because it was skipped, not configured, mocked, or green on a different SHA.

## Workflow router

| Workflow | Use when | Required output | Minimum verification |
|---|---|---|---|
| 1. Root-cause / adversarial debugging | A failure, incident, unexpected state, race, or regression exists | Execution trace, ranked hypotheses with evidence, first failing boundary, minimal reproducer, fix and prevention | Reproduce before fix where practical; prove regression test fails before / passes after |
| 2. Zero-regression refactor | Structure/performance/readability needs improvement without intended contract change | Contract inventory, before/after complexity analysis, diff, trade-offs, edge checklist | Signature/exception/side-effect compatibility, tests, benchmark if performance is claimed |
| 3. Adversarial / property-based testing | Input space, state machine, concurrency, parser, or boundary risk is material | Test matrix, properties/invariants, fixtures, seeded reproductions, mutation/fuzz plan | Tests detect representative bad behavior; no blanket skips or relaxed assertions |
| 4. Schema / API contract synthesis | JSON, OpenAPI, SQL DDL, events, or cross-service payloads need typed models | Typed domain models, runtime validators, serialization mapping, compatibility rules, valid fixtures | Positive/negative schema tests, round-trip and backward-compatibility checks |
| 5. Architecture / technical spike | Several designs or vendors compete | Weighted decision matrix, assumptions, failure modes, operational costs, ADR and reversible spike | Verify critical claims from authoritative sources or measurements; state uncertainty |
| 6. Legacy / AST reverse engineering | Code is undocumented, highly coupled, or hard to safely change | Purpose, call/state graph, mutation points, dependencies, hidden assumptions, extraction plan | Validate graph against code/tests; no rewrite before characterization coverage |
| 7. Senior PR / red-team review | Before review, release, or security-sensitive change | Severity-ranked findings with location, exploit/failure scenario, fix, residual risk | Verify findings against diff; distinguish confirmed vulnerability from concern |

**Selection rule:** choose one primary workflow and any necessary secondary workflows. A trivial documentation edit does not require a fabricated architecture matrix. A production-facing change normally requires diagnosis/design as appropriate, adversarial tests, and a red-team review. Explain which workflows were applied and why when delivering substantive engineering work.

## Prompt 1 — Root-cause analysis and adversarial debugging

~~~text
MISSION: Diagnose the actual defect before changing code.

Inputs: repository and exact SHA, failing command/test, safe logs, expected behavior, observed behavior.

1. TRACE the real path from entry point through state mutations, dependencies, error handling, and the first divergence. Cite file/function/line and observed evidence.
2. Separate facts, deductions, and hypotheses. Rank at most three hypotheses when useful. For each, state evidence for/against and the cheapest discriminating experiment.
3. Inspect boundary conditions, shared mutable state, retries, cancellation, timeouts, concurrency, transaction boundaries, ownership, and cleanup where relevant.
4. Create at least two minimal reproductions or regression cases when practical. Do not fabricate a reproduction if dependencies are unavailable.
5. Implement the smallest fix supported by the evidence. Preserve public contracts and security invariants.
6. Add a prevention mechanism: invariant assertion, type narrowing, schema validation, state-machine guard, static check, or architectural boundary.
7. Run the focused test before and after, then relevant regression tests. Record exact command and result.
8. If evidence is insufficient, improve safe diagnostics or report the blocker; do not guess a fix.

Never dump unrestricted tracebacks, secrets, credentials, personal data, raw request payloads, or artifact contents into CI logs. Use allowlisted, bounded diagnostics and repository-relative frames.
~~~

## Prompt 2 — Zero-regression refactoring and optimization

~~~text
MISSION: Improve structure or measured performance without changing intended behavior.

Before editing, record runtime/language versions, public signatures, return types, exception behavior, ordering guarantees, side effects, persistence semantics, concurrency assumptions, and compatibility constraints.

1. Characterize current behavior with tests; identify existing gaps.
2. State baseline algorithmic time/space complexity only where derivable from code. Measure runtime/memory before claiming an empirical improvement.
3. Propose the smallest structural change; explain alternatives and trade-offs.
4. Preserve external contracts unless a breaking change is explicitly authorized and versioned.
5. Avoid redundant allocations, deep clones, blocking I/O in async paths, unbounded caches, and premature complexity.
6. Add equivalence/regression tests, edge cases, and benchmarks when performance is the objective.
7. Deliver a before/after complexity table, code diff, compatibility checklist, measurements with environment details, and residual risks.
8. Do not describe an unmeasured optimization as faster, or an untested refactor as zero-regression.
~~~

## Prompt 3 — Adversarial and property-based testing

~~~text
MISSION: Test the contract and invariants over nominal, boundary, malformed, and adversarial inputs.

Build a matrix covering:
- Nominal success and expected failure.
- Empty/missing/null values, limits, Unicode/UTF-8, numeric bounds, precision, oversized input, and malformed/truncated payloads.
- Authentication/authorization, tenant/owner isolation, replay/idempotency, injection, path traversal, unsafe deserialization, and data leakage as applicable.
- Concurrency, duplicate delivery, out-of-order responses, timeout, cancellation, retry, partial failure, and resource cleanup.
- State transitions, persistence invariants, recovery after crash/lease expiry, and integrity checks where applicable.

Use deterministic unit tests for known regressions; property-based tests for general invariants; fuzzing/mutation testing where valuable. Seed randomized tests and retain minimized failing examples. Mock external services only for unit isolation; keep real isolated integration tests for behavior that mocks cannot prove. Clean up resources on success and failure. Do not weaken assertions, turn failures into skips, or test only implementation details.
~~~

## Prompt 4 — Schema and API contract synthesis

~~~text
MISSION: Transform the source contract into strongly typed domain primitives and explicit runtime validation.

1. Identify the authoritative source schema and version. Preserve required/optional/null distinctions, defaults, ranges, formats, enums, patterns, and unknown-field policy.
2. Generate idiomatic types plus runtime validators (for example, Pydantic v2, Zod, or Rust Serde plus validation). Do not use 'any'. Permit 'unknown' only at an untrusted boundary and immediately narrow/validate it.
3. Make field-name mappings, aliases, serialization direction, timezone/decimal/binary handling, and compatibility rules explicit.
4. Produce valid factory fixtures. Prefer deterministic seeds for reproducibility; randomness must not make tests flaky.
5. Add valid/invalid examples, round-trip tests, schema conformance tests, and compatibility checks.
6. Flag source-schema ambiguities instead of inventing constraints. Distinguish generated code from manually maintained logic.
~~~

## Prompt 5 — Architecture trade-off matrix and technical spike

~~~text
MISSION: Choose an architecture based on workload evidence and operational constraints.

Define workload, throughput/latency targets, consistency, retention, availability, recovery objectives, data sensitivity, team capability, deployment environment, and cost ceiling. Compare at least the credible candidate options across:
- Throughput/latency and scaling limits.
- Delivery semantics, ordering, idempotency, backpressure, poison messages, and replay.
- Failure behavior under process crash, dependency outage, partition/network split, and partial deployment.
- Security, access control, observability, data residency, and compliance.
- Infrastructure/maintenance burden, cost drivers, migration/lock-in, and rollback.
- Testability, local development, and operational ownership.

For each score, state the source or assumption and confidence. Do not present vendor maximums as expected workload performance. Recommend an option, state conditions that would reverse the recommendation, define a time-boxed proof of concept and acceptance criteria, and write a concise ADR. Prefer reversible decisions until uncertainty is reduced.
~~~

## Prompt 6 — Legacy reverse engineering and AST-level breakdown

~~~text
MISSION: Explain behavior before proposing a rewrite.

1. Describe purpose, inputs, outputs, and observable side effects.
2. Map call graph, state machine, mutations, transitions, error paths, and persistence boundaries. Use language AST/static tooling when available; do not claim AST analysis if only text inspection occurred.
3. Inventory environment variables, global singletons, clocks, randomness, network/disk access, hidden dependency injection, and import-time side effects.
4. Identify implicit invariants, fragile assumptions, cyclic coupling, and untested behavior.
5. Create characterization tests around current behavior, including known defects that must not be accidentally institutionalized.
6. Propose a staged extraction plan with seams, compatibility adapters, rollback, and measurable acceptance gates. Do not replace the system wholesale before behavior is understood.
~~~

## Prompt 7 — Senior PR review and red-team audit

~~~text
MISSION: Review the exact diff and its execution context as a skeptical senior engineer.

Inspect only evidence-backed findings in:
- Security: injection, authn/authz bypass, tenant isolation, path traversal, unsafe deserialization, secrets/logging, cryptography, supply chain.
- Performance: N+1 queries, missing indexes, unbounded memory/work, synchronous blocking in async code, repeated expensive work.
- Resilience: retry storms, idempotency gaps, partial commits, transaction boundaries, cancellation, lease races, poison messages, missing timeouts.
- Contracts/maintainability: schema drift, API compatibility, excessive coupling, unclear ownership, weak error context, missing observability.
- Tests/release: weakened assertions, skipped gates, flaky timing, missing integration evidence, wrong-SHA validation.

For each finding report severity (Critical/Major/Minor/Informational), file and line, confidence, preconditions, concrete failure/exploit scenario, evidence, minimal remediation, regression test, and residual risk. Separate confirmed defects from potential risks. Do not manufacture findings to fill a quota. State what was not checked.
~~~

## Applying the playbook to AIGC

AIGC is contract-first, runtime-governed, secrets-isolated, human-approved, and employer-auditable. The playbook supplements—not overrides—AGENTS.md, AIGC_MASTER_PROMPT.md, phase contracts, security policy, release controls, or operator authorization.

### Current task-lifecycle work

For the PostgreSQL task/outbox → Redis dispatcher → worker → artifact/evidence flow, prioritize:
1. Root-cause debugging with exact commit/run evidence.
2. Integration and adversarial tests for atomic task/outbox creation, owner isolation, idempotency, duplicate delivery, lease expiry, retries, terminal-state guards, artifact-byte digest verification, and cleanup.
3. Red-team review of authentication, ownership, worker registry allowlist, logs, transaction behavior, and failure recovery.
4. Schema/contract review where API or persisted payload shape changes.
5. Architecture matrix only if a real design decision needs comparing.

A green test on a different SHA is not evidence for the current candidate. Skipped locked-release revalidation remains skipped. Keep PRs draft until the repository's required review and release gates are satisfied. No production migrations, deployment, merge, or live provider actions are authorized by this playbook.

### AIGC integration plan (documentation-first, behavior-neutral)

1. Keep this playbook as the canonical prompt/workflow reference.
2. Add short links to it from agent/master instructions so future engineering tasks route through it.
3. When building a prompt router or agent, represent workflow choice as structured metadata: task type, exact SHA, allowed tools/actions, required evidence, approval class, and completion state.
4. Start in advisory/read-only mode. Log workflow selection and evidence references, not secrets or raw sensitive payloads.
5. Add tests for routing determinism, permission denial, missing evidence, prompt injection in repository content, redaction, and fail-closed behavior before any autonomous write path is enabled.
6. Any runtime enforcement or agent behavior change requires its own implementation plan, tests, review, and explicit approval.

### Reuse by related projects

For related 1JGM, RegenExcalibur, cloud orchestration, fabrication/design, or agent projects:
- Reuse the seven workflow families and evidence labels.
- Replace AIGC phase names, allowed actions, schemas, repositories, and release criteria with that project's authoritative contract.
- Keep fabrication concepts marked concept-only until engineering validation and human authorization; do not let prompt templates imply safety certification.
- Separate research/recommendations from actions that change infrastructure, spend money, contact people, deploy code, or affect physical systems.
- Maintain project-local copies or a versioned shared standard; never assume a prompt in one repository automatically governs another.

## Suggested pipeline contract

A future implementation may use this conceptual routing object; it is documentation only, not an executable authorization token:

~~~json
{
  "workflow": "root_cause | refactor | adversarial_test | schema_contract | architecture_spike | reverse_engineering | red_team_review",
  "repository": "owner/name",
  "base_sha": "full immutable commit SHA",
  "scope": ["explicit paths or subsystems"],
  "non_goals": ["explicit exclusions"],
  "authority": {
    "mode": "read_only | branch_write | external_action",
    "approval_reference": null
  },
  "evidence_required": ["reproduction", "focused_tests", "exact_sha_ci", "diff_review"],
  "secrets_policy": "never_emit_secret_values",
  "completion": "pass | in_progress | blocked | failed"
}
~~~

The router must validate this object against a strict schema, reject unknown authority escalation, and independently enforce permissions in tools/services. Prompt text alone is not a security boundary.

## Acceptance checklist for this playbook

- [ ] Each of the seven workflow families has an actionable prompt and verification conditions.
- [ ] Root-cause claims require evidence and falsifiable tests.
- [ ] Refactoring claims distinguish asymptotic reasoning from measured performance.
- [ ] Test generation includes adversarial and concurrency cases where relevant.
- [ ] Schema synthesis preserves nullability and validates untrusted input.
- [ ] Architecture scores expose assumptions and uncertainty.
- [ ] Reverse engineering distinguishes AST-backed analysis from manual inspection.
- [ ] PR review reports evidence, severity, confidence, and residual risk.
- [ ] AIGC's approval, secrets, audit, exact-SHA, draft-PR, and release boundaries remain intact.
- [ ] No runtime behavior changes or production actions are made by documentation adoption alone.

## Reference documentation

- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html)
- [pytest fixtures and cleanup](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
- [OWASP Code Review Guide](https://owasp.org/www-project-code-review-guide/)
- [Property-based testing workflow research](https://www.anthropic.com/research/property-based-testing)

External references are starting points, not substitutes for the versions pinned by the project. Verify current compatibility before implementation.
