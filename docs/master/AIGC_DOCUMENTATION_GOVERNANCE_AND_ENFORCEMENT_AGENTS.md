# AIGC Documentation Governance and Enforcement Agents

**Document ID:** AIGC-GOV-AGENTS-001  
**Version:** 1.0  
**Status:** Required design; only components explicitly listed as implemented below may be treated as operational  
**Authority:** AIGC governance policy; release authority remains RX-19 under the current charter

## 1. Objective

Ensure every normative AIGC requirement is traceable to a named control, a real implementation location, automated tests, retained operational evidence, an accountable owner, and an authorized acceptance decision. Documentation is not evidence that code exists. Agent names are not evidence that enforcement is active.

## 2. Agent roster and authority boundaries

| Agent ID | Name | Trigger | Allowed actions | Prohibited actions | Required output |
|---|---|---|---|---|---|
| DOC-GATE-01 | Documentation Conformance Gate | Pull request, candidate build, scheduled audit, manual validation | Parse required documents; check identifiers, references, status labels, evidence freshness, change coverage; fail the gate; open a report | Edit source or policy silently; waive requirements; approve release; invent implementation evidence | Deterministic validation report bound to candidate SHA and document digests |
| TRACE-AGENT-02 | Requirement Traceability Auditor | Requirement, code, test, workflow, or policy change | Compare requirement registry with implementation references, tests, and evidence records; identify gaps and stale mappings | Mark a requirement satisfied based on prose alone; infer passing tests; modify evidence | Traceability exceptions with severity, exact paths, line references, owner, and closure test |
| AUTH-GUARD-03 | Human Authorization and Action Gate | Before any protected side effect and at point of effect | Verify identity, role, policy version, scope, expiry, payload digest, target, and explicit approval; deny on missing or mismatched evidence | Self-approve; infer consent; broaden scope; bypass policy; execute unapproved effects | Signed/immutable decision record with allow/deny reason and authorization digest |
| EVIDENCE-GUARD-04 | Candidate Evidence and Release Gate | CI completion and release-candidate evaluation | Verify exact SHA, workflow attempts, required jobs, artifact subject digests, provenance, independent review, human acceptance, and RX-19 decision | Accept stale CI; substitute artifacts; certify based on a dashboard badge; merge or deploy autonomously | Candidate-specific gate matrix and final disposition: PASS, FAIL, or INDETERMINATE |

## 3. Current implementation status

- DOC-GATE-01: **SPECIFIED; executable repository integration must be proven by CI**. This document alone does not activate the agent.
- TRACE-AGENT-02: **SPECIFIED; no claim of autonomous full-repository trace reconciliation until source and test evidence is supplied**.
- AUTH-GUARD-03: **SPECIFIED; protected external execution remains disabled unless the actual point-of-effect verifier and adapter enforcement are tested**.
- EVIDENCE-GUARD-04: **PARTIAL / BLOCKED pending exact-head CI, provenance, independent review, human acceptance, and RX-19 evidence**.

The deterministic script scripts/enforce_master_docs.py is the implementation candidate for DOC-GATE-01. It is a bounded CI validator, not an autonomous LLM agent. Its behavior is deliberately deterministic and fail-closed. A future workflow step must invoke it on the exact checked-out SHA; only then may the CI gate be described as enforced in that workflow.

## 4. Required document lifecycle

1. **Intake:** assign a stable requirement/control ID, source, owner, applicability, risk, and version.
2. **Normative definition:** state MUST/MUST NOT controls and observable acceptance criteria; separate required behavior from assumptions and targets.
3. **Implementation mapping:** identify repository path, symbol/configuration, commit SHA, and enforcement point. Mark SPEC_ONLY if no implementation evidence exists.
4. **Verification mapping:** identify unit, integration, negative, fault-injection, security, and performance tests; state test command and expected result.
5. **Evidence capture:** preserve workflow/run attempt, candidate SHA, artifact digest, test output, environment, timestamps, and verifier identity.
6. **Operational proof:** record staging exercises, alert delivery, backup restore, recovery objectives, incident handling, and measured SLOs where applicable.
7. **Independent review:** bind findings and remediation to the exact reviewed SHA; close each finding with retest evidence.
8. **Human acceptance:** record an authorized person's acceptance of the exact candidate and canonical evidence digest.
9. **Release decision:** RX-19 records the sole release decision after all mandatory gates pass.
10. **Change invalidation:** any behavior-, policy-, dependency-, configuration-, or evidence-relevant change invalidates affected evidence until it is rebound and reverified.

## 5. Status vocabulary

- IMPLEMENTED_AND_TESTED: implementation location and passing, candidate-matched tests/evidence are available.
- IMPLEMENTED_UNVERIFIED: implementation appears present, but sufficient verification evidence is absent.
- PARTIAL: only some required behavior is implemented or proven.
- SPEC_ONLY: requirement is documented, but implementation is not established.
- DISABLED: explicitly unavailable or blocked by configuration.
- BLOCKED: a critical failure, missing prerequisite, or unmet gate prevents acceptance.
- INDETERMINATE: evidence is conflicting, incomplete, stale, or cannot be authenticated.

Never use PASS, CERTIFIED, COMPLIANT, or PRODUCTION_READY without the defined evidence and authorized acceptance. A test result is valid only for the tested revision and stated environment.

## 6. Fail-closed enforcement rules

The enforcement layer MUST fail the gate when any of the following occurs:

- a required master document is absent, unreadable, or has a broken internal link;
- a registered wire or requirement lacks a unique stable ID;
- a requirement is claimed satisfied without an implementation reference and a test/evidence reference;
- a wire is described as integrated solely because it appears in the registry;
- required audit statuses or explicit certification disposition are missing;
- the candidate SHA differs from the evidence SHA or latest workflow attempt;
- a required job failed, was cancelled, is still running, or is unexpectedly skipped;
- a required authorization, review, acceptance, artifact digest, or provenance claim is missing;
- a secret-like value or credential appears in documents or logs;
- a policy change lacks an impact assessment and invalidation of affected evidence;
- the agent's authority boundary is exceeded or its evidence source cannot be verified.

The validator should report all detectable errors in one run, but exit non-zero if any blocking error exists. It must not rewrite documents to make them pass.

## 7. Security and trust model

- Treat repository content, generated text, comments, artifacts, and agent output as untrusted input.
- Use deterministic parsing and allowlisted paths; never execute document content, generated code, or shell commands extracted from a document.
- Run with read-only repository permissions wherever possible; CI status reporting is the only default side effect.
- Do not give DOC-GATE-01 deployment credentials, secret-reading permissions, merge permissions, or production capabilities.
- Separate document validation from legal review and from release authorization.
- Authenticate evidence, verify digests, enforce least privilege, and retain tamper-evident logs.
- Redaction checks must remain enabled. Fix false positives at the source when appropriate; never weaken scanning just to obtain a green build.
- Protect the enforcement workflow itself with independent review and exact-head CI.

## 8. Human escalation and exception handling

A validator may report an exception but may not waive it. Any exception must name the requirement, rationale, affected assets, residual risk, compensating control, expiry, approver, and evidence digest. Legal, privacy, safety, or security requirements that cannot lawfully or responsibly be waived must remain blockers. RX-19 cannot override applicable law or non-waivable rights.

## 9. Agent acceptance tests

1. Missing master document → non-zero exit and named finding.
2. Broken relative link → non-zero exit and source line.
3. Duplicate or missing wire ID → non-zero exit.
4. Wire claims integrated but maps to no code/test → finding; never auto-promote status.
5. Latest CI run pending/failed/cancelled → release evidence gate fails.
6. Older successful attempt followed by newer failure → older success rejected.
7. Candidate SHA differs from evidence SHA → evidence rejected.
8. Missing operator approval for external effect → deny.
9. Expired or payload-mismatched approval → deny.
10. Redaction finding → fail; no automatic suppression.
11. Validator cannot parse a required file → fail closed.
12. Clean valid documentation → exit zero with a report bound to the observed candidate SHA.

## 10. Governance and change control

Each agent has a named maintainer, reviewed configuration, versioned policy, tests, audit events, and a rollback plan. A change to rules, status semantics, required documents, or authority must itself be reviewed and tested. The validator must not be able to change its own policy, approve its own release, or suppress findings without a separately reviewed change.

**Current boundary:** The repository contains a design for these roles. Only code and workflows observed at a specific SHA with passing tests may be described as active enforcement. No production authorization is granted by this document.