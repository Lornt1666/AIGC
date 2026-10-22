# AIGC Evidence Verifier Agent — Research-Backed Engineering Specification

**Version:** 1.0.0  
**Status:** IMPLEMENTATION / INTEGRATION GATE — NOT A RELEASE AUTHORITY  
**Owner project:** `Lornt1666/AIGC`  
**Canonical release authority:** Release Assurance Agent only  
**Default result:** `BLOCK`

## 1. Mission

The Evidence Verifier Agent independently determines whether the evidence packet for one exact AIGC revision is complete, authentic, internally consistent, current, and sufficient to be submitted to the canonical Release Assurance Agent. It must be deterministic, read-only by default, fail-closed, minimally privileged, and incapable of authorizing a release.

It does not infer that a feature is safe because CI is green. It verifies a chain:
`repository identity → commit/tree → workflow run/attempt → required checks → exact artifact digest → signed provenance → runtime control evidence → independent audit evidence → adversarial results → independent review → authenticated human acceptance → handoff receipt`.

The agent's strongest permitted result is `READY_FOR_CANONICAL_REVIEW`. The field `release_decision` remains `BLOCK` because only the canonical Release Assurance Agent may decide release authorization.

## 2. Research basis and interpretation

1. **GitHub Actions OIDC:** Verify the JWT signature using the issuer's discovery/JWKS keys and enforce issuer, audience, subject, expiry, not-before, issue time, repository and owner IDs, repository visibility, ref, event, workflow path and SHA, reusable workflow identity where applicable, run ID, run attempt, and narrowly scoped permissions. Do not treat decoded claims as authenticated. Give `id-token: write` only to the job that needs it. GitHub documents standard claims and workflow-level/job-level token permissions.
2. **GitHub artifact attestations:** Verify eligibility before relying on this mechanism. Current GitHub documentation says Free/Pro/Team support is for public repositories; private/internal repositories require Enterprise Cloud, and legacy plans may not support the feature. Eligibility is necessary but not evidence of an issued attestation. No silent hash-only fallback is permitted.
3. **GitHub/Sigstore verification:** Use the official `gh attestation verify` or a pinned, verified Sigstore verifier with explicit trust constraints. Check verifier exit code, structured output, signer workflow, repository, source revision, predicate, and subject digest. A hash proves byte identity only; it does not prove builder identity or provenance.
4. **SLSA provenance:** Compare the attestation's subject digest with locally recomputed bytes and verify builder identity, canonical source repository, build type, external parameters, and resolved dependencies against policy. Reject unrecognized or disallowed external parameters.
5. **Secure SDLC:** Treat required tests, vulnerability findings, review, approval, and provenance as separate gates. A passing subset cannot override a missing or failed required check.
6. **Audit evidence:** Retain attributable, time-bounded, tamper-evident evidence with independent administrative control, defined retention, access review, and restore testing. Hash chaining alone is not independent administration or immutability.
7. **Repository governance:** Required checks and reviews must be configured in repository rulesets/branch protection, with bypass narrowly restricted. The verifier reads and reports these controls; it must not silently change them.

## 3. Trust boundary

### Trusted only after independent validation
- GitHub API response obtained over authenticated TLS using a read-only, least-privilege credential.
- OIDC JWT accepted only after signature, issuer, audience, temporal, identity, and claim-policy validation.
- Attestation accepted only after a pinned official verifier succeeds against explicit trust policy and its structured result is bound to the exact artifact/source.
- Audit receipt accepted only when signed/authenticated by the separately administered audit service and bound to the submitted event digest.
- Review accepted only from an authenticated reviewer identity meeting independence policy, for the exact SHA/tree and artifact manifest.
- Human acceptance accepted only from an authenticated authorized approver and bound to the same subject, evidence manifest, policy version, and review.

### Never trusted alone
- Branch name, green badge, workflow summary, job display name, a CI artifact filename, an unverified JSON file, a caller-supplied `verified: true`, a Git SHA without source binding, an unsigned checksum, a test mock, a PR comment, an agent's self-attestation, or a screenshot.
- A passing older run, a run from a different SHA, a previous attempt, or an artifact from a different workflow.
- A local `pytest` success as proof of real OIDC, Sigstore, controller, or audit integration.

## 4. Required policy inputs

All policy is versioned, immutable for one evaluation, and loaded from an independently controlled source. Empty allowlists are configuration errors.

- Repository: canonical full name, numeric repository ID, owner ID, allowed visibility and allowed plan/feature eligibility evidence.
- Subject: full 40-character commit SHA, Git tree SHA, expected source ref/event, optional merge-group identity, submodule/LFS/dependency manifest digests.
- CI: required workflow path, workflow identity, workflow file SHA, allowed events/refs, expected required check IDs/names, allowed conclusions, retry policy, maximum evidence age, required job/step set, and ruleset snapshot.
- OIDC: issuer, audience, immutable subject format if configured, repository/owner IDs, workflow/ref/event/environment allowlists, token lifetime/clock-skew policy, JWKS/key-rotation rules, replay/revocation storage, allowed action scopes.
- Provenance: approved verifier name/version and executable/action digest; trusted issuer/root; signer identity/workflow; predicate type; builder identity; exact source and subject digest; allowed build parameters and dependency policy.
- Artifacts: required artifact roles, names, digests, schemas, maximum sizes/counts, expiry policy, archive extraction constraints, and deterministic manifest rules.
- Runtime controller: service identity, endpoint identity, authorization policy digest, action allowlist, policy version, idempotency semantics, intent-before-dispatch guarantee, and tested failure-state model.
- Audit service: independent owner/admin boundary, authentication trust root, append-only/retention controls, sequence/receipt semantics, clock source, retention duration, access logs, restore evidence, and deletion/break-glass policy.
- Adversarial tests: required attack-case IDs and expected outcome for each; the suite itself must be tied to the same SHA/tree and tested service versions.
- Review: reviewer identity/role trust source, independence requirements, required scope, exact subject/artifact/policy bindings, finding severity thresholds, remediation evidence, and re-review requirements.
- Acceptance: approver identity/role trust source, distinctness from author/implementer/reviewer where policy requires, exact subject/tree/artifact manifest/policy/review bindings, authentication mechanism, expiry and revocation checks.
- Output: evidence store, schema version, signing/receipt method, retention, and canonical Release Assurance handoff endpoint.

## 5. Evaluation contract

Input is a bounded evidence bundle of structured records. External adapters must perform cryptographic/network verification; the policy engine independently checks the returned verification receipts and their exact bindings. A plain boolean from an adapter is insufficient.

Each evidence record must carry:
- schema version and evidence type;
- repository ID/name and full commit/tree SHA;
- workflow run ID and attempt when applicable;
- producer identity and verification method/version;
- raw evidence locator and content SHA-256;
- authenticated acquisition/verification result;
- creation time, freshness bound, and revocation status;
- policy version and correlation ID.

The agent performs these stages in fixed order:

1. Validate policy completeness and canonical subject.
2. Fetch current repository metadata and exact source commit/tree.
3. Enumerate all required workflow runs/check suites for the exact SHA and allowed event/ref; reconcile run ID, attempt, workflow path/SHA, status and conclusions.
4. Verify all required jobs/checks completed successfully; fail on missing, skipped-required, neutral, cancelled, timed out, stale, unknown, or contradictory results.
5. Fetch artifacts from the exact run/attempt; enforce archive safety limits; hash actual bytes; verify subject/tree/run/attempt bindings.
6. Verify actual OIDC identity using provider keys and policy. Never emit raw tokens.
7. Verify attestation/provenance with the pinned official verifier, including certificate/signature/transparency evidence, signer workflow, repository, source SHA/tree, predicate, builder, parameters, and exact subject digest.
8. Verify controller and audit-service integration receipts from actual interfaces, not mocks. Validate idempotency and restart/ambiguous-outcome test results.
9. Verify every required adversarial case executed against real interfaces and produced the expected secure outcome. Missing tests are not passes.
10. Verify independent security review, findings closure, remediation reruns, and authenticated human acceptance, all bound to the exact same revision and evidence manifest.
11. Write a deterministic evidence manifest and independently retained audit receipt.
12. Submit a read-only handoff packet to the canonical Release Assurance Agent only if all prerequisites are satisfied. The submission request is not an authorization decision.

## 6. Fail-closed rules

Any of the following produces `BLOCK`: absent/ambiguous evidence; mismatch in repository ID, SHA, tree, run, attempt, workflow or digest; stale or superseded run; missing required check; required job skipped; verifier failure/nonzero exit/timeout; unrecognized predicate or build parameter; unsupported artifact-attestation eligibility; invalid signature/certificate/transparency proof; OIDC issuer/audience/subject/ref/workflow mismatch; replay or unavailable replay store; controller bypass; audit receipt from same administrative boundary; non-durable intent; untested or unsafe retry; ambiguous operation reported as success; missing adversarial case; unresolved finding above threshold; reviewer/approver not authenticated or not independent; approval bound to older evidence; changed revision after acceptance; evidence store unavailable; policy version mismatch.

No fail-open retry, hash-only fallback, policy weakening, automatic review, auto-acceptance, auto-merge, auto-deploy, or self-authorization.

## 7. Runtime and controller assurance

The verifier checks the execution-controller contract and evidence for the state machine:
`RECEIVED → AUTHENTICATED → AUTHORIZED → INTENT_DURABLE → DISPATCHED → SUCCEEDED | FAILED | UNKNOWN`.

- Authorization is checked server-side at the last responsible moment.
- Workers have no bypass credentials.
- An idempotency key is scoped to principal, action, canonical request digest, and policy version.
- The intent is durable before dispatch; a durable audit receipt binds intent ID, request digest, decision, and idempotency key.
- Restart recovery reconciles backend state before any retry.
- A timeout or lost response becomes `UNKNOWN`, never success.
- Repeating the same idempotency key returns the recorded outcome or `UNKNOWN`; it must not duplicate a side effect.
- The verifier must demand test receipts for concurrent duplicates, crash before dispatch, crash after dispatch before response, audit outage, controller restart, expired/revoked identity, policy change mid-flight, and backend status unavailable.

## 8. Evidence packet and receipt

Output schema `aigc-evidence-verifier-receipt/1.0` contains:
- policy ID/version/digest;
- repository numeric ID/name, subject SHA/tree, event/ref;
- workflow ID/path/SHA, run ID/attempt, run conclusion and required-check inventory;
- artifact inventory with recomputed digest, size, source and run binding;
- OIDC verification receipt metadata without token material;
- attestation verifier identity/version/digest, trust policy digest, signer identity, issuer, predicate, source binding, subject digest, verifier output digest;
- controller and audit service identities/versions/policy digests and real-interface test evidence references;
- adversarial test matrix with case ID, test version, actual outcome and evidence digest;
- independent review identity, signature/receipt, findings and closure evidence;
- human acceptance identity, authentication method, timestamp, exact bindings and revocation check;
- all reasons, evidence locators, acquisition times, and final agent disposition;
- canonical JSON digest and independent audit receipt.

No secrets, raw JWTs, bearer tokens, private keys, or unrestricted log dumps may appear in the receipt. Diagnostics are bounded and redacted.

## 9. Determinism, resilience, and operations

- Stable schema, canonical JSON serialization, sorted maps/reasons, stable evidence IDs, and explicit schema versioning.
- Bounded retries only for idempotent reads; exponential backoff with jitter; respect rate limits and Retry-After; no blind retry of writes or side effects.
- Timeout, cancellation, partial API pagination, rate limiting, expired credentials, network partition, clock skew, corrupt archive, missing artifact, malformed JSON, tool upgrade, JWKS rotation, and evidence-store outage all result in bounded recovery or `BLOCK`.
- Re-evaluation is idempotent and creates a new evaluation ID; it never overwrites evidence from a prior attempt.
- Preserve raw evidence securely and separately from sanitized summaries; log who accessed or exported it.
- Use read-only GitHub credentials for observation; any evidence submission credential is separate, narrowly scoped, and cannot merge or deploy.
- Pin all actions/tools to verified immutable versions/digests; upgrades require review and conformance tests.
- Observability: correlation ID, stage timings, rate-limit/retry counts, reason codes, evidence freshness, and tool versions. Never log credentials.

## 10. Acceptance test matrix

The implementation is not accepted until the following are demonstrated with real interfaces and retained evidence:

1. Exact SHA/tree accepted; one-character SHA/tree mutation rejected.
2. Stale run, wrong run attempt, wrong workflow SHA, wrong event/ref, fork, missing required job, skipped required job, cancelled run, partial pagination, and older passing run rejected.
3. Archive tampering, digest mismatch, path traversal, duplicate paths, symlink/special-file extraction, zip bomb, malformed schema, and cross-run artifact rejected.
4. Valid live OIDC token accepted only for configured audience/issuer/subject/workflow/ref/repository; wrong issuer/audience/subject, expired/not-yet-valid, signature tamper, unknown key, key rotation, replay, unavailable replay store and unauthorized scope rejected.
5. Real GitHub attestation verified by pinned tool; wrong signer workflow, repository, source SHA/tree, predicate, builder, artifact digest, signature, certificate, transparency proof, malformed output, timeout and nonzero exit rejected.
6. Feature eligibility verified; unsupported private/internal plan stops without downgrade.
7. Controller denies unauthorized action, stale policy, expired principal, replay, mismatched request digest and worker bypass.
8. Concurrent duplicates, crash before/after dispatch, retry, restart, lost response, audit outage, backend unavailable and policy rotation do not duplicate actions or turn `UNKNOWN` into success.
9. Audit event has authenticated receipt, independent administrative boundary, sequence/integrity validation, retention, access-control and restore evidence; tampering or deletion is detected.
10. Every adversarial suite case is present, bound to exact source and service versions, and has the expected result.
11. Review/acceptance missing, forged, revoked, non-independent, stale, wrong-SHA, wrong-tree, wrong-manifest, or policy-mismatched all block.
12. Changing any evidence after evaluation invalidates the manifest/handoff.
13. A completely passing evidence packet yields only `READY_FOR_CANONICAL_REVIEW`, never `RELEASE_AUTHORIZED`.
14. Any unknown or missing required field yields `BLOCK`.

## 11. Out of scope and non-goals

The agent does not generate its own trust roots, issue identities, review its own code, accept on behalf of a human, alter repository rulesets, grant cloud permissions, change policy to make evidence pass, merge pull requests, deploy, or declare production readiness. It cannot prove independence merely from a name string; reviewer and audit trust must be anchored to externally controlled identities and administration.

## 12. Implementation plan

**Phase A — Policy engine:** deterministic schemas, strict binding checks, reason codes, unit and mutation tests.  
**Phase B — Read-only GitHub adapter:** exact-head workflow/check/artifact enumeration, pagination, run-attempt binding, ruleset snapshot.  
**Phase C — Trust adapter:** pinned official GitHub/Sigstore verification and exact provenance expectations; live main-branch OIDC test.  
**Phase D — Runtime evidence adapters:** actual execution-controller and independent audit service; fault injection and recovery receipts.  
**Phase E — Review/acceptance adapter:** externally authenticated independent review and human acceptance.  
**Phase F — Evidence custodian/handoff:** canonical manifest, independent storage, signed/receipted submission to canonical Release Assurance.  
**Phase G — Independent review and final acceptance:** exact final SHA/tree only; any change restarts affected gates.

## 13. Current evidence status

This specification and policy-engine reference implementation are not proof that real infrastructure is connected. The verifier must report missing integrations honestly. PR CI success proves only the checks in that run. Main-only OIDC/attestation jobs are expected to be skipped on an unmerged pull request; a trusted main run is required to exercise them. Controller/audit integration, real-interface adversarial evidence, independent review and authenticated human acceptance remain separate gates until demonstrated.

## 14. Research references

- GitHub Actions OIDC reference: https://docs.github.com/en/actions/reference/security/oidc
- GitHub artifact attestations: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- GitHub secure use / pin actions to full SHA: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- GitHub workflow-runs API (exact head SHA): https://docs.github.com/en/rest/actions/workflow-runs
- GitHub CLI attestation verifier: https://cli.github.com/manual/gh_attestation_verify
- Sigstore Cosign verification: https://docs.sigstore.dev/cosign/verifying/verify/
- SLSA provenance v1: https://slsa.dev/spec/v1.2/build-provenance
- SLSA artifact verification: https://slsa.dev/spec/v1.2/verifying-artifacts
- NIST SP 800-218 SSDF: https://csrc.nist.gov/pubs/sp/800/218/final
- NIST SP 800-204D CI/CD supply-chain security: https://csrc.nist.gov/pubs/sp/800/204/d/final
- NIST SP 800-92 log management: https://csrc.nist.gov/pubs/sp/800/92/final
