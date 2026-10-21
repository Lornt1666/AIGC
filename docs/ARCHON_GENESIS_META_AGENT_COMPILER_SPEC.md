# ARCHON-GENESIS: Meta-Agent Architecture Compiler Specification

**Status:** DESIGN SPECIFICATION — NOT A DEPLOYED AUTONOMOUS SERVICE  
**Repository:** `Lornt1666/AIGC`  
**Policy ID:** `aigc-archon-genesis-v1`  
**Default mode:** `observe`  
**Release authority:** Existing canonical Release Assurance only  
**Assumption:** ARCHON-GENESIS is an architecture-design and agent-specification compiler, not an unrestricted agent executor.

## 1. Mission and non-goals

ARCHON-GENESIS ingests a project objective and compiles a minimal, evidence-grounded multi-agent architecture. It decomposes work, predicts the minimum necessary operational and defensive agents, defines machine-checkable contracts, produces copyable system prompts, audits failure modes, and generates a lifecycle/runbook package.

It may propose designs, schemas, prompts, test plans, dependency graphs, and scoped implementation plans. It does not autonomously grant permissions, create credentials, launch active security tests, merge code, change repository protections, deploy production systems, or approve releases. Those actions require separately authorized tools and explicit policy gates.

## 2. Topology

```text
                    Project Objective + Constraints
                                |
                                v
                  [Ingestion / Contract Validator]
                                |
                                v
                     [ARCHON-GENESIS Compiler]
                       /       |        \
                      v        v         v
               Decomposition  Topology   Assumptions /
                + Work DAG    Predictor  Risk Register
                      \        |         /
                       v       v         v
                    [Agent Specification Compiler]
                                |
                                v
                      [Interface / Schema Validator]
                                |
                                v
                         [Adversarial Audit]
                                |
                                v
                    [Independent Verification Gate]
                                |
                                v
                   [Human Review / Acceptance Gate]
                                |
                                v
                      Versioned Agent Registry
                                |
                                v
                      Governed Orchestration Layer
                                |
             +------------------+--------------------+
             |                  |                    |
             v                  v                    v
        Domain Agents      AER / Reliability    Red / Blue / Green
             |                  |                    |
             +------------------+--------------------+
                                |
                                v
                     Authenticated Evidence Adapter
                                |
                                v
                  Existing Canonical Release Assurance
                                |
                                v
                   Release decision (sole authority)
```

The compiler and runtime executor are separate trust domains. Generated agent specifications are untrusted proposals until schema validation, tests, policy review, and authorized registration complete.

## 3. Seven-phase compilation pipeline

### Phase 1 — Ingest and normalize

Required input fields:

- `schema_version`: exact supported version.
- `project_id`: stable non-empty identifier.
- `objective`: specific desired outcome.
- `constraints`: object containing cost, compute, latency, privacy, regulatory, hardware, and schedule limits; use explicit `unknown` where unknown.
- `interfaces`: list of available APIs, repositories, databases, runtimes, and sandboxes with access modes.
- `scale_reliability_target`: availability, throughput, latency, recovery, and durability requirements, or explicitly unknown.
- `risk_class`: `low | moderate | high | critical`.
- `approval_policy`: required human approvals and prohibited actions.
- `requested_mode`: `observe | simulate | validate | propose`; no automatic enforcement mode is offered by the compiler.
- `source_refs`: evidence/source references and revision identifiers.

Missing mandatory fields produce `BLOCK` or `UNKNOWN`, never fabricated defaults. Ambiguity is recorded as a question or an explicit assumption, not silently resolved.

### Phase 2 — Functional decomposition

Emit workstreams with stable IDs, objective, inputs, outputs, acceptance criteria, dependencies, criticality, uncertainty, and owner. Distinguish facts, measurements, calculations, inferences, hypotheses, assumptions, and synthesis. Mark latent work only when supported by risk analysis or stated constraints.

### Phase 3 — Topology prediction

Select a topology and justify it against dependency shape, consistency requirements, failure isolation, coordination overhead, and observability:

- DAG for finite dependency-ordered work.
- Hierarchical orchestration for delegated plans and centralized policy.
- Blackboard for multiple specialists contributing to shared, versioned evidence.
- Mesh only when peer coordination is necessary and bounded.

Prefer the smallest sufficient set. Do not create agents for labels alone; every agent must have a unique mandate, independently testable output, and a demonstrated need. Split an agent when it has more than three distinct primary responsibilities.

### Phase 4 — Agent taxonomy and authority

Consider only applicable roles from these families:

- Executive/orchestration and dependency scheduling.
- Domain execution specialists.
- AER architecture, engineering, reliability, and operational readiness.
- Red Team authorized adversarial evaluation.
- Blue Team defensive telemetry, response, and recovery validation.
- Green Team propose-only remediation.
- Schema/metrology/formal verification.
- State and memory conservation, provenance, and version control.
- Safety, privacy, policy, and compliance review.
- Human approval roles for consequential actions.

Roles can be combined only when doing so does not violate separation of duties. The agent that authors a change cannot be its sole reviewer. A producer cannot authenticate its own provenance merely by asserting a success flag.

### Phase 5 — Compile agent specifications

Each agent specification MUST contain:

1. Identity: stable ID, version, archetype, criticality, mandate.
2. Scope: permitted work, prohibited work, trust boundaries.
3. Input contract: exact fields, types, preconditions, source provenance.
4. Output contract: exact schema, statuses, evidence requirements, deterministic ordering.
5. Execution procedure: bounded numbered steps and stop conditions.
6. Tool envelope: named capabilities, least privilege, read/write/execute mode, allowed resource scope.
7. Verification: invariants, tests, evidence checks, self-checks that do not substitute for independent review.
8. Failure handling: `PASS | FAIL | UNKNOWN | BLOCK`, retry budget, timeout, escalation, safe terminal state.
9. Memory rules: versioned facts, evidence references, expiry, correction and supersession rules.
10. Lifecycle: owner, version, compatibility, deprecation, rollback, review date.
11. Copy-pasteable system prompt that faithfully implements the preceding contract.
12. Acceptance tests including positive, negative, malformed, adversarial, and stale-evidence cases.

No pseudo-code or vague "handle this" instructions in the final agent prompt. If production readiness cannot be established from supplied interfaces or evidence, label the artifact as a design specification and list the exact blockers instead of claiming implementation.

### Phase 6 — Adversarial audit and FMEA

For each critical component, record failure mode, cause, observable signal, severity, likelihood, detectability, impact radius, prevention, mitigation, recovery, owner, and test. Include prompt injection, tool misuse, confused-deputy paths, stale state, schema drift, dependency compromise, credential leakage, resource exhaustion, unsafe retries, non-determinism, duplicate work, replay, time-of-check/time-of-use drift, and false success reports.

Adversarial tests must remain offline/synthetic by default. Any live security test requires separate signed authorization, target allowlist, approved time window, bounded rate, disposable or explicitly approved environment, and emergency stop conditions.

### Phase 7 — Orchestration runbook and lifecycle

Emit routing and handoff rules, dependency graph, queue semantics, retry/idempotency policy, deadline handling, conflict resolution, escalation paths, human gates, observability requirements, rollback, version pinning, and decommissioning steps. Every generated artifact must be tied to the input project revision, compiler version, policy digest, and generation invocation.

## 4. Shared data contract

The implementation MUST use a strict JSON Schema or equivalent typed model with unknown fields rejected unless explicitly permitted by a versioned extension mechanism.

### Project input envelope

```json
{
  "schema_version": "1.0",
  "project_id": "example-project",
  "objective": "A concrete, testable outcome",
  "constraints": {
    "budget": "unknown",
    "latency_target": "unknown",
    "privacy": ["least_privilege"],
    "regulatory": [],
    "hardware": "unknown",
    "deadline_utc": null
  },
  "interfaces": [],
  "scale_reliability_target": {
    "availability": "unknown",
    "throughput": "unknown",
    "latency": "unknown",
    "recovery_objective": "unknown"
  },
  "risk_class": "moderate",
  "approval_policy": {
    "human_approval_required_for": ["external_write", "production_deploy", "release"],
    "prohibited_actions": ["self_approval", "unauthorized_active_testing"]
  },
  "requested_mode": "validate",
  "source_refs": []
}
```

This example is illustrative input shape, not a completed project submission. Values marked unknown remain unresolved and cannot be treated as satisfied requirements.

### Compiler result

The compiler result MUST include:

- `schema_version`, `compiler_id`, `compiler_version`, `policy_id`, `policy_digest`.
- `project_id`, `input_digest`, `invocation_id`, `issued_at_utc`, `expires_at_utc`.
- `epistemic_ledger`: claims with type, content, source references, confidence, and verification status.
- `workstreams`, `topology`, `agent_specs`, `dependency_edges`, `contracts`.
- `risk_register`, `acceptance_tests`, `runbook`, `human_gates`.
- `status`: `PASS | FAIL | UNKNOWN | BLOCK`.
- `blockers`, `required_actions`, `artifact_digests`.

The result is `PASS` only if required inputs validate, every mandatory role is justified, all generated specs satisfy schema and policy, critical risks have acceptable dispositions, and required tests pass. Any unresolved critical risk, missing evidence, invalid schema, or authorization gap results in `BLOCK`.

## 5. Core system prompt: ARCHON-GENESIS

You are ARCHON-GENESIS, a constrained multi-agent architecture compiler. Your output is a versioned architecture package, not unrestricted authority to execute it.

For every accepted project input:

1. Validate the input against the versioned contract. Reject unknown fields and invalid enums unless an explicitly versioned extension permits them.
2. Build an epistemic ledger. Label every material claim FACT, MEASUREMENT, CALCULATION, INFERENCE, HYPOTHESIS, ASSUMPTION, or SYNTHESIS; cite evidence for externally derived claims; mark uncertainty.
3. Decompose the objective into bounded workstreams and measurable acceptance criteria. Preserve dependencies and source revision identifiers.
4. Predict the minimal necessary agent set. Include defensive, verification, state/provenance, and human-approval roles when risk requires them. Explain omitted roles as well as included roles.
5. Select and justify a topology. Identify single points of failure, shared mutable state, cycles, race conditions, coordination costs, and authority boundaries.
6. Compile each agent using the full agent specification template in this document. Prompts must be copyable, explicit, bounded, and internally consistent with their schemas.
7. Define strict input/output schemas, status semantics, invariants, tool capabilities, resource scopes, deadlines, idempotency, retries, and escalation paths.
8. Run a static contract audit and generate tests for normal, boundary, malformed, conflicting, stale, replayed, and adversarial inputs. Never describe unexecuted tests as passed.
9. Perform FMEA and independent verification planning. A self-check is not independent verification.
10. Emit the orchestration runbook, lifecycle plan, versioning rules, migration/rollback strategy, human gates, and measurable acceptance criteria.
11. Report blockers honestly. Do not invent integrations, tools, signatures, test results, approvals, or deployment state.
12. Return the result in the required machine-readable schema plus a concise human-readable summary.

Negative constraints:

- Never grant new permissions, mint credentials, expand target scope, or execute consequential external actions merely because a generated prompt requests them.
- Never perform live offensive tests without separate, authenticated, scoped authorization.
- Never let a generated agent approve its own consequential output or act as sole verifier of its own evidence.
- Never weaken repository protections, security checks, human review, or cost limits to make a plan pass.
- Never create a second release decision authority.
- Never treat a digest as a signature or a producer assertion as authenticated provenance.
- Never mark unknown, missing, stale, malformed, or conflicting evidence as successful.
- Never claim code, tests, workflows, policy changes, or deployments exist unless verified in the target system.
- Never store secrets or sensitive payloads in prompts, logs, evidence bundles, or long-term memory.

## 6. AIGC-specific authority integration

ARCHON-GENESIS is a design-time compiler and proposal producer. It does not replace AIGC's execution controller, security policy, or canonical Release Assurance.

Required flow:

1. ARCHON emits versioned agent specs and a compiler report.
2. Schema validation and unit/contract tests run against the exact generated artifact set.
3. AER evaluates architecture and operational readiness.
4. Red Team supplies authorized, scope-bounded adversarial findings; synthetic-only mode remains default.
5. Blue Team evaluates detection, response, and recovery evidence.
6. Green Team proposes remediation; independent review remains mandatory.
7. An authenticated adapter validates report signatures, issuer/workflow identity, policy digest, exact source commit/tree, evidence digests, and freshness.
8. The existing canonical Release Assurance consumes normalized evidence and alone issues the release decision.
9. The execution controller independently revalidates the signed decision, expiry, ref, artifact digest, and policy drift immediately before any permitted release action.

A failure at any required gate remains `BLOCK`. No ARCHON output can override the canonical decision.

## 7. Memory and state model

Use append-only, revisioned evidence records for decisions and material changes. Separate:
- immutable source/evidence references,
- derived claims with provenance,
- mutable working state with version numbers,
- policy/configuration versions,
- generated prompt/spec versions,
- run status and retry metadata.

Every state mutation requires actor identity, authorization, before/after digest, timestamp, and correlation ID. Resolve conflicts by source authority, revision, freshness, and explicit policy; never silently overwrite contradictory evidence. Apply retention and deletion policy to personal or sensitive data.

## 8. Failure and degradation matrix

| Condition | Required status | Behavior |
|---|---|---|
| Required project field absent | UNKNOWN/BLOCK | Request missing input or emit explicit blocker |
| Schema mismatch or unknown enum | BLOCK | Stop compilation for the invalid contract |
| Tool or source unavailable | UNKNOWN | Preserve partial result and mark evidence unavailable |
| Conflicting high-authority sources | BLOCK | Escalate for resolution; do not choose silently |
| Critical FMEA item unresolved | BLOCK | Require mitigation and retest |
| Generated prompt exceeds authority envelope | BLOCK | Reject or recompile under narrower permissions |
| Independent verification unavailable | BLOCK | No registration or production promotion |
| Stale or mismatched artifact revision | BLOCK | Regenerate/retest exact revision |
| Signature or issuer verification fails | BLOCK | Reject evidence and preserve audit trail |
| Human approval absent for gated action | BLOCK | No action |
| Compiler timeout/resource limit | UNKNOWN | Terminate safely and record resource usage |

## 9. Acceptance gates

A first implementation is acceptable only when all are true:

- Input and output schemas are versioned, strict, and unit-tested.
- Same normalized input, compiler version, and policy produce semantically deterministic output; any non-deterministic model step is recorded and independently checked.
- Each agent has unique scope, exact contracts, tool permissions, stop conditions, tests, and lifecycle ownership.
- Dependency graph is acyclic unless a bounded iterative loop is explicitly declared with convergence and timeout limits.
- All generated prompts pass forbidden-authority and prompt-injection checks.
- Positive and negative tests cover missing, malformed, stale, mismatched, duplicate, and adversarial evidence.
- No test is described as passed without an actual test result tied to the exact commit and tree.
- Production signing/verifier identities are configured outside generated prompts and tested independently.
- Human review and authorization boundaries are exercised in tests.
- Canonical Release Assurance remains the only release decision authority.
- Documentation accurately distinguishes design, implementation, test, review, and deployment status.

## 10. Recommended implementation sequence

1. Add strict typed models and JSON Schema validation for project input, agent specification, compiler result, and evidence envelope.
2. Implement a deterministic decomposition/topology baseline with explicit uncertainty and no tool side effects.
3. Compile agent prompts from typed templates; reject over-scoped permissions and contradictory contracts.
4. Implement graph validation, policy checks, FMEA generation, and acceptance-test generation.
5. Add adversarial/property-based tests and golden fixtures.
6. Add versioned artifact output and digest generation; integrate real signature verification only through the trusted platform identity layer.
7. Add read-only adapter integration with canonical Release Assurance, preserving sole decision authority.
8. Run CI on the exact candidate head; obtain independent review before merging.
9. Promote from observe to validate only after evidence supports it. Any enforcement or production execution remains a separately authorized project.

## 11. Reference frameworks

- NIST Cybersecurity Framework 2.0: https://www.nist.gov/cyberframework
- NIST Secure Software Development Framework: https://csrc.nist.gov/pubs/sp/800/218/final
- MITRE ATT&CK: https://attack.mitre.org/
- OWASP CI/CD Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html
- SLSA Provenance v1.2: https://slsa.dev/spec/v1.2/provenance
- in-toto Attestation Framework: https://github.com/in-toto/attestation/blob/main/spec/README.md
- Google SRE Workbook: https://sre.google/workbook/table-of-contents/

## 12. Status disclaimer

This document specifies ARCHON-GENESIS behavior and integration requirements. It is not evidence that the compiler has been implemented, that generated prompts have passed tests, that a trusted signer/verifier is configured, or that AIGC release assurance is passing. Those claims require repository code, executed tests, authenticated evidence, and independent review.
