# AIGC Control-Plane Agents — MVP++ Contracts

**Status:** Executable prototype with isolated unit tests; production authorization remains BLOCKED.  
**Implementation:** `src/aigc_control_plane_agents.py`  
**Tests:** `tests/test_aigc_control_plane_agents.py`

## Agent roster

| Agent | Responsibility | Authority boundary |
|---|---|---|
| Allowlisted Extension Registry | Register versioned extensions, exact entrypoints, input/output schema IDs, risk tiers, and explicit action IDs | Does not load arbitrary code, grant capabilities, or execute extensions |
| MVP Policy Creator | Produce versioned policy drafts with rule IDs, conditions, effects, rationale, and source references | Draft-only; cannot activate, sign, approve, or grant permissions |
| Authenticated Policy Inputs Agent | Delegate token verification to a trusted identity verifier and enforce issuer/audience/subject allowlists | Does not treat caller-supplied booleans as identity proof; production requires configured OIDC/JWKS validation and revocation controls |
| Cryptographic Evidence Validation Agent | Invoke configured Cosign verification and check exact SHA-256 subject, full source SHA, and expected workflow identity | Must use a pinned verifier binary and trusted bundle; current adapter is an interface prototype and needs integration tests with real Sigstore attestations before trusted use |
| Execution-Controller Enforcement Agent | Independently revalidate a scoped decision, expiry, action allowlist, idempotency key, and audit append before dispatch | No wildcard actions; blocks if the audit append is not confirmed; actual controller/backend integration is still required |
| Adversarial Control Test Agent | Run negative cases against controller behavior and report expected-versus-observed decisions | Test result is not independent security review or release approval |
| Independent Review & Acceptance Agent | Validate the presence of exact-subject review and human-acceptance references and unresolved findings | Does not manufacture reviewers, signatures, or human acceptance |
| Audit Sink Interface | Require a durable append receipt before consequential dispatch and append a result record | The included protocol is not itself an immutable store; production needs an independently administered append-only/tamper-evident service |

## Contracts and invariants

- Extension IDs and action IDs are explicit; wildcard actions are rejected.
- Policy creation returns `DRAFT`; a draft is not an active policy.
- Identity verification is delegated to an injected verifier. Only configured issuers, audiences, and subjects are accepted.
- Evidence checks bind the artifact SHA-256, full source commit SHA, and expected workflow identity. A mocked subprocess test is not proof of a real signature.
- Execution requires a verified `ALLOW_SCOPED` decision, matching action, future timezone-aware expiry, idempotency key, successful decision revalidation, and confirmed audit append.
- An execution result of `FAILED` or `UNKNOWN` is not reported as success.
- Review evidence must reference the exact 40-character source SHA. Missing independent review blocks; missing explicit human acceptance remains `REVIEW_REQUIRED`.
- These agents cannot replace the canonical Release Assurance Agent, security/privacy/policy checkers, or human release approval.

## Validation plan

The canonical workflow now invokes `test_aigc_control_plane_agents.py`. The tests use test doubles for identity, audit storage, execution, and Cosign process output; they validate component behavior, not external service authenticity.

Before production:
1. Run CI against the exact final commit and inspect artifacts.
2. Pin the Cosign binary by verified version and digest; use actual GitHub/Sigstore bundles and verify certificate identity, OIDC issuer, source revision, predicate, and subject digest in an isolated integration job.
3. Use real OIDC/JWKS identity validation with issuer/audience restrictions, key rotation, expiry, replay and revocation tests.
4. Connect a durable, independently administered audit store and a real execution controller; test concurrent idempotency, crash recovery, ambiguous outcomes, and cancellation.
5. Run adversarial and fault-injection integration tests.
6. Obtain a qualified independent review of the exact reviewed commit, remediate findings, and record explicit human acceptance.
7. Keep production disabled until the canonical Release Assurance Agent evaluates authenticated evidence and all release criteria pass.

## Safety statement

This MVP++ implementation creates executable interfaces and isolated tests. It is **not production-ready**: tests with fakes do not establish real cryptographic trust, durable audit retention, cross-process idempotency, live authorization, or safe production execution. Any missing, stale, conflicting, or unauthenticated evidence must leave the consequential action blocked.
