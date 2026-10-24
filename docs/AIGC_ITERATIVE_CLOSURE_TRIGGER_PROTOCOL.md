# AIGC Iterative Closure Trigger Protocol

**Protocol ID:** AIGC-ICTP-001  
**Scope:** Coliseum owner approval, governed review decisions, exact-head validation, and release assurance  
**Status:** IMPLEMENTATION IN PROGRESS — NOT A PRODUCTION AUTHORIZATION  
**Authority model:** Least privilege; explicit human approval; fail closed  
**Execution location:** Hosted/remote CI and authorized cloud services only; never require a developer's local machine.

## 1. Objective

Run a bounded, evidence-producing iteration loop that joins internal engineering triggers with external verification triggers. Each cycle must articulate what changed, why it changed, which evidence proves the result, which risks remain, and what is permitted next.

The loop must not equate an agent's claim, a green score, a boolean flag, a passing subset of tests, or a successful CI job with owner authorization or production readiness.

## 2. Trigger definitions

### Internal trigger — \`AIGC_INTERNAL_CLOSURE_TRIGGER\`

Fire when any of the following occurs:
- a source, test, configuration, migration, policy, or dependency changes;
- a test or static check fails;
- a threat-model review identifies an authority bypass, unbound approval, replay path, missing evidence, or unsafe fallback;
- a workflow artifact contradicts the expected behavior;
- a proposed remediation changes a state-machine transition or authorization boundary.

Required internal actions:
1. Read the exact branch head, commit SHA, changed-file list, and relevant surrounding code.
2. State the expected behavior and invariants before editing.
3. Inspect both positive and negative paths, including errors, timeouts, missing secrets, unavailable storage, duplicate requests, stale approval, replay, and mismatched commit/proposal bindings.
4. Make the smallest coherent change; do not weaken tests to conceal a defect.
5. Add or update regression tests that prove the invariant and prove prohibited behavior remains impossible.
6. Record known gaps, dependencies, and the next falsifiable acceptance criterion.

### External trigger — \`AIGC_EXTERNAL_EVIDENCE_TRIGGER\`

Fire after a candidate commit is pushed, a hosted workflow completes or fails, a workflow artifact is produced, a reviewer responds, a protected-branch/ruleset fact changes, or staging/identity/storage evidence becomes available.

Required external actions:
1. Fetch the live PR head and workflow run; compare their immutable SHAs.
2. Inspect job-level results and test/validation artifacts, not only the top-level conclusion.
3. Confirm the tested tree SHA and all required validation stages; separate skipped, missing, cancelled, and failed evidence from passed evidence.
4. Verify provenance, secret-scan results, artifact identity, and that authority flags remain false unless independently authorized.
5. Obtain independent review and controlled staging evidence where required.
6. Never manufacture an identity, secret, reviewer approval, database migration result, external receipt, or production acceptance when the source does not provide it.

## 3. Iteration state machine

\`DISCOVER → SPECIFY → IMPLEMENT → LOCAL-TOOL-FREE STATIC REVIEW → HOSTED CI → ARTIFACT AUDIT → ADVERSARIAL REVIEW → STAGING/EXTERNAL EVIDENCE → DISPOSITION\`

The phrase “local-tool-free static review” means review performed against repository content without asking a user to run commands on a local device. All executable tests run in hosted CI or an explicitly authorized cloud environment.

Disposition rules:
- **PASS / continue:** exact-head evidence supports the current acceptance criteria; advance to the next unresolved gate.
- **FAIL / remediate:** a concrete failure is found; create a regression test, fix the underlying cause, and repeat the loop on a new immutable SHA.
- **BLOCKED / external dependency:** progress requires an unavailable identity provider, secret provisioning, reviewer, controlled database, protected setting, or other external authority. Record the exact missing evidence and do not simulate it.
- **STOP / unsafe:** an authorization bypass, unexpected external side effect, secret exposure, or untrusted fallback is detected. Preserve evidence, disable the affected path where authorized, and require human review.

Continue until the defined acceptance gates pass or a specific external dependency prevents further safe progress. Do not repeat unchanged work merely to create activity.

## 4. Owner approval invariants

- A caller-controlled \`owner_gate: bool\` is never proof of identity, intent, or authorization.
- Coliseum ranking is advisory and cannot itself authorize execution.
- An approval must be signed by a trusted issuer and bound to the canonical proposal digest, full commit SHA, actor, issue time, expiry, unique approval ID, and nonce.
- Signature comparison must be constant-time; malformed, stale, mismatched, expired, or replayed approvals are rejected.
- Replay protection must be durable and atomic across replicas. Ledger outage or uncertain consumption means deny and reconcile; never fail open.
- An execution permit is an independent control, not a substitute for owner approval.
- The verified approval must be checked immediately before the protected action and the resulting decision/evidence must be durably recorded.
- HMAC verification code alone does not establish a trusted issuer. Issuance must be controlled by authenticated identity and a protected signing authority.

## 5. Required external evidence for closure

1. Exact-head hosted CI passes for the final candidate SHA; cancelled prior runs do not count.
2. Test artifacts show zero failures across the required test commands, and every required stage is present with an explicit result.
3. Negative tests prove a boolean gate cannot authorize selection or invoke an action callback.
4. Verifier tests cover signature tampering, exact proposal/commit binding, time validity, expiry, replay, and storage failure.
5. PostgreSQL integration proves the replay migration and uniqueness constraints on a controlled test database.
6. The actual review-decision route uses the verified approval result; no local-mode or legacy fallback can bypass shared authority.
7. Independent review covers the exact final SHA.
8. Staging evidence demonstrates approval, denial, replay, outage, timeout, recovery, and audit behavior without production side effects.
9. Release decision, reviewer identity, provenance, acceptance, and rollback plan are recorded. No release is certified merely because CI is green.

## 6. Current iteration record

- Draft PR: [#347 — Fail closed on unverified Coliseum owner approval](https://github.com/Lornt1666/AIGC/pull/347)
- Related draft PR: [#346 — Integrate durable review reads behind explicit storage mode](https://github.com/Lornt1666/AIGC/pull/346)
- Candidate that exposed stale test expectations: \`1bf82cd7042c9d82e8b4fef00f3e62500bc1b2a9\`
- Hosted run: [#4790](https://github.com/Lornt1666/AIGC/actions/runs/40131392871)
- Artifact audit: the contract stages for compilation, schema validation, orchestration round trip, secret scan, redaction, and other listed stages passed, but the test stage failed. Ten legacy tests expected a boolean gate to grant owner acceptance or permit execution.
- Internal remediation: legacy tests were updated to expect \`AWAITING_VERIFIED_OWNER_APPROVAL\`, \`NOT_EXECUTED\`, and zero action-callback invocations when only the boolean gate is supplied.
- Revalidation candidate: \`7f1a571730878069ed5e82dbfbc15f29d15f92f2\`
- Revalidation run: [#4795](https://github.com/Lornt1666/AIGC/actions/runs/40131711240) — pending at time of this record. Do not claim pass until this exact SHA completes and its artifact is inspected.

## 7. Explicit non-claims and release boundary

At this stage, the signed approval verifier and PostgreSQL replay adapter are added, but the verifier is not yet integrated into the live review-decision route. The migration has not been applied to a live database; trusted issuer/identity integration and secret provisioning have not been evidenced; independent review and staging acceptance are outstanding.

Therefore:
- merge authority: not granted;
- deployment authority: not granted;
- production activation: not authorized;
- external action: not performed;
- live-model invocation: not authorized;
- financial authority: not granted.

Maintain draft PRs and fail-closed guards until all applicable gates are independently evidenced and a human release decision is recorded.
