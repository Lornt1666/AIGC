# AIGC Release Evidence & Real-Interface Assurance Crew — Engineering Specification

**Version:** 1.0.0  
**Status:** DESIGN / IMPLEMENTATION GATE — NOT PRODUCTION AUTHORIZATION  
**Target:** AIGC / Artificial Intelligence Gladiator Coliseum  
**Canonical release authority:** Release Assurance Agent only  
**Default disposition:** BLOCK

## 1. Mission and invariants

Build a crew that takes a proposed revision from evidence intake to an independently verifiable release packet while being technically unable to self-authorize release.

The crew MUST bind every test, artifact, review, approval and attestation to one immutable full commit SHA, tree SHA, workflow run ID/attempt, and exact artifact digest. It MUST verify the complete required workflow, not merely a canonical runner or selected passing job. Missing, stale, failed, skipped-required, inconclusive or untrusted evidence blocks.

Cryptographic signature and provenance verification are mandatory. SHA-256 alone establishes byte identity, not who built those bytes or whether the build was safe. Evidence storage, identity trust configuration, reviewer trust roots, release policy and execution authorization must be outside the control of the agents being evaluated.

The crew MUST NOT merge, deploy, publish, enable production capabilities, alter its own acceptance policy, mint its own trust, or represent AIGC as production-ready. No agent may manufacture an independent review or human approval. The canonical Release Assurance Agent alone evaluates release authorization, and only after all prerequisites pass.

## 2. Agent roster and contracts

### A. Exact-Revision Intake & Evidence-Binding Agent

**Purpose:** Establish the one immutable subject under evaluation.

**Inputs:** Repository identity, requested full commit SHA, expected tree SHA, workflow/run ID and attempt, expected artifact manifest, policy version.

**Checks:** Repository ID/name match policy; full SHA and tree SHA match fetched source; checkout SHA/tree match; workflow run SHA, event, ref, workflow path/revision, run attempt and required checks match policy; evidence is from the current attempt and has not been superseded; submodules/LFS and material build inputs are recorded.

**Output:** Authenticated Subject Manifest and stable evidence IDs. Mismatch produces BLOCK.

**Cannot:** Select a nearby passing SHA, reuse prior-head evidence, or treat a branch name as immutable identity.

### B. Full-Workflow CI & Artifact Inspector Agent

**Purpose:** Evaluate the complete required workflow and inspect release-relevant artifacts.

**Checks:** Enumerate required workflows, jobs, check-runs and steps from trusted policy. Distinguish runner success from overall workflow success. Required skipped jobs, absent checks, neutral/unknown conclusions, incomplete runs, stale attempts or missing artifacts block unless an explicit signed policy defines a safe exception. Download through authenticated GitHub APIs; enforce size/count/time limits; reject path traversal, duplicate paths, symlinks/special files where extraction occurs, zip bombs and malformed manifests. Recompute SHA-256 locally and compare with GitHub's advertised archive digest. Inspect schema, subject SHA/tree, run ID/attempt, test reports, stage results, SBOM, provenance, signature bundle and policy version.

**Output:** Workflow Validation Report, artifact inventory and findings. A successful download or matching hash is not a passing release gate.

### C. OIDC Workload Identity Verification Agent

**Purpose:** Verify real workload identity for service-to-service calls.

**Required implementation:** Use provider discovery and JWKS; validate JWT signatures using approved algorithms and key IDs. Enforce exact issuer, audience, subject, repository/owner identity, workflow identity, ref/event and environment constraints. Validate expiry, not-before, issue time, bounded lifetime, clock skew and replay controls. Use short-lived least-privilege tokens; never persist raw tokens in logs, artifacts, prompts or source. Test key rotation, unknown key IDs, malformed JWTs, algorithm confusion, wrong issuer/audience/subject, expiry, replay, wrong repository/fork, untrusted ref and wrong workflow.

For GitHub Actions OIDC, grant id-token: write only to the minimum job and constrain downstream trust to the intended repository, workflow, ref and environment. A decoded JWT is not proof; cryptographic validation is mandatory.

**Output:** Authenticated Workload Identity with verification metadata, never the raw token.

**Cannot:** Trust caller-supplied authenticated booleans or accept tokens minted for another audience.

### D. GitHub/Sigstore Attestation & Provenance Verifier Agent

**Purpose:** Prove that the exact artifact digest was attested by the approved builder/workflow for the approved source revision.

**Preferred integration:** Use supported GitHub artifact attestations and a pinned, verified GitHub CLI/Sigstore toolchain. Verify with explicit repository/owner, signer workflow, predicate type and source expectations. Do not parse arbitrary verifier stdout as a substitute for cryptographic verification.

**Required checks:** Signature/envelope and certificate chain validate against intended trust roots; OIDC issuer, certificate identity/SAN, repository identity, signer workflow path/ref, builder identity and predicate match policy; provenance subject digest equals locally recomputed artifact digest; source repository and full commit SHA/tree equal the subject manifest; build parameters and inputs match policy; untrusted fork, unexpected workflow, wrong ref, wrong predicate, wrong subject, ambiguous subjects, missing provenance or replayed evidence blocks. Record verifier version/digest and verification output.

**Mandatory negative tests:** Tampered signature, unsigned/malformed bundle, unknown issuer, wrong workflow identity, wrong repository, changed source SHA/tree, changed artifact bytes, wrong digest, wrong predicate, expired/untrusted certificate where applicable, replay from another run, missing bundle, verifier nonzero exit, timeout and malformed output.

**Important:** GitHub artifact attestations have plan/repository eligibility constraints. Verify actual repository visibility and plan support before selecting the production path. If unavailable, stop and request an approved alternative; never silently downgrade to hash-only checks.

**Output:** Verified Provenance Record binding verifier version, subject digest, source SHA/tree, builder/workflow identity, predicate, attestation reference and verification time.

### E. Execution-Controller Enforcement Agent

**Purpose:** Make server-side enforcement mandatory for all consequential actions.

All consequential actions must traverse the actual controller and reference monitor. Agent-side preflight checks alone are insufficient. Worker agents must not hold direct backend credentials.

Before dispatch, authenticate caller/workload; validate signed/versioned policy and authorization, scope, resource, action, environment, risk, expiry, quota and revocation; match an exact allowlisted action ID; acquire a durable idempotency key and canonical request digest; reject same key with different payload; append a durable intent to independently administered audit storage; require an authenticated commit receipt before dispatch. Use a transactional outbox or equivalent crash-safe design.

**State machine:** RECEIVED → AUTHENTICATED → AUTHORIZED → INTENT_DURABLE → DISPATCHED → SUCCEEDED | FAILED | UNKNOWN. State transitions are monotonic and auditable. UNKNOWN is not success and must not trigger blind retries for non-idempotent actions.

Retry only under an explicit policy and proven idempotency contract. On timeout after dispatch, query the backend by durable operation ID before replay. On restart, reconcile durable intents with backend state. Use fencing tokens/leases to prevent stale workers acting after reassignment. Define cancellation and compensation; never imply compensation undoes irreversible effects. Apply concurrency limits, quotas, deadlines, bounded queues and backpressure. Audit, policy or revocation uncertainty and backend UNKNOWN block further consequential action.

**Output:** Authenticated execution receipt referencing intent, policy, idempotency key, request digest, operation ID and terminal state.

### F. Independent Audit & Evidence Custodian

**Purpose:** Preserve evidence outside the authority of agents and services being audited.

Use a separate administrative principal and security boundary from the execution controller. Require append-only or tamper-evident records, authenticated write receipts, monotonic sequence or equivalent, trusted timestamps, integrity chaining/signatures, immutable retention where required, and independently controlled deletion. Separate read/write roles; worker agents cannot alter records or retention. Record authorization, policy versions, approvals, identity decisions, tool calls, intent/result transitions, errors, retries, overrides, evidence verification and review remediation; redact credentials and sensitive payloads. Alert on gaps, sequence breaks, failed writes, unexpected admin changes and retention violations. Test backup, restore and auditor access.

A local append-only interface, JSONL file or application-owned table is not proof of independently administered audit retention.

### G. Adversarial Real-Interface Test Agent

**Purpose:** Exercise deployed test/staging interfaces, not only mocks.

Use isolated non-production accounts, synthetic artifacts/identities, explicitly allowlisted targets, low quotas, no production secrets and a hard stop if environment identity is uncertain.

**Required suites:**
1. OIDC: valid token; wrong issuer/audience/subject; expired token; invalid signature; key rotation; replay; fork/untrusted ref.
2. Provenance: valid attestation; invalid signature; wrong workflow identity; wrong source SHA/tree; changed artifact; mismatched digest; wrong predicate; missing bundle; stale run.
3. CI/artifacts: runner passes while overall workflow fails; required job missing/skipped; old attempt passes but latest fails; wrong SHA/tree; malformed/oversized archive; path traversal; evidence tampering.
4. Execution: unauthorized action; scope escalation; expiry/revocation; concurrent duplicate requests; same idempotency key with different payload; policy race; timeout before/after side effect; audit outage; backend UNKNOWN.
5. Recovery: kill worker/controller at every state transition; restart; replay queue; lose audit response after commit; duplicate delivery; verify no duplicate side effect or false success.
6. Audit: unauthorized update/delete, retention change, credential misuse, sequence truncation and backup restore.
7. Human review: unsigned approval, unknown reviewer, implementer/reviewer conflict, expired acceptance, changed SHA/digest after acceptance, withdrawn/reused approval.
8. Release gate: prove Release Assurance is never invoked for incomplete evidence and is invoked only with a complete authenticated packet. It may still decide BLOCK.

**Results:** Case ID, test version, target identity, request digest, expected and observed outcome, sanitized logs, evidence references and disposition. Any unexpected allow or false success is a critical blocker.

### H. Independent Security Review Coordinator

Select a reviewer from an externally maintained trusted roster. Reviewer must be independent of implementation and relevant control ownership. They independently fetch the exact SHA, inspect diff, artifacts, threat model, tests and deployment configuration, and record findings, severity, evidence, remediation and residual risk. Review evidence must be signed by the reviewer or recorded in an approved authenticated review system.

Every blocking finding requires a remediation commit and regression test. Reviewer verifies the fix on the new exact SHA; a review of an old SHA cannot approve a changed revision. Unresolved critical/high findings, missing signature, stale review or uncertain independence means BLOCK. The agent may prepare packets and track remediation but cannot call its own review independent.

### I. Explicit Human Acceptance Agent

Verify a real, accountable human acceptance record after review and technical evidence are complete.

Acceptance binds repository ID/name, exact commit SHA/tree, workflow run ID/attempt, artifact digests, provenance record, independent review ID, resolved findings, policy version, environment, scope, time and expiry. Use an approved enterprise identity/signature channel with authenticated actor, authorization role, replay prevention and durable audit record. Free text, a username in JSON, a self-asserted boolean or an unauthenticated chat message is insufficient.

Any code/tree/artifact/policy/material configuration change invalidates acceptance and restarts the gate.

### J. Canonical Release Assurance Agent

This is the exclusive release decision authority. It requires exact subject identity; full required workflow success on that revision; inspected artifacts and verified provenance; passing real-interface adversarial tests; independent audit and recovery evidence; independent review with blocking findings remediated; explicit authenticated human acceptance; and no stale, missing, revoked, conflicting or untrusted evidence.

If any prerequisite is absent or indeterminate, return BLOCK with stable reason codes. Complete evidence permits evaluation, not guaranteed approval. No other agent may issue release authorization.

## 3. Shared evidence contract

All records are versioned, schema-validated and content-addressed. Minimum fields: schema version; record type/ID; repository ID/name; subject commit SHA/tree; workflow ID/run ID/attempt; artifact name/digest where applicable; policy ID/version; producer and verifier identity; creation/expiry times; result and stable reason codes; evidence references; integrity linkage; signature/attestation metadata where required.

Reject duplicate JSON keys, invalid encodings, non-canonical digests, invalid timestamps, schema ambiguity and duplicate record IDs. Bind evidence to run/attempt and subject; timestamps alone do not establish freshness.

## 4. End-to-end state machine

INTAKE → SUBJECT_LOCKED → CI_COMPLETE → ARTIFACTS_INSPECTED → OIDC_VERIFIED → PROVENANCE_VERIFIED → EXECUTION_AND_AUDIT_TESTED → ADVERSARIAL_SUITE_PASSED → INDEPENDENT_REVIEW_COMPLETE → REMEDIATION_VERIFIED → HUMAN_ACCEPTANCE_VERIFIED → EVIDENCE_PACKET_SEALED → SUBMITTED_TO_RELEASE_ASSURANCE → RELEASE_ASSURANCE_DECISION.

Any failure moves to BLOCKED or REVIEW_REQUIRED. No stage can be skipped. A code/policy change resets every subject-bound stage invalidated by that change. A later pass cannot override an earlier failed required stage.

## 5. Threat model

Threats include compromised worker agents, malicious dependencies, untrusted PR/fork authors, stolen tokens, malicious workflow changes, artifact substitution, replay, insider misuse, misconfiguration, audit administrators, network partitions and ambiguous backend outcomes.

Controls include least privilege, protected workflow definitions, third-party actions pinned by full commit SHA, minimal permissions, isolated runners, short-lived credentials, exact identity constraints, verified provenance, independent audit, server-side authorization, durable idempotency, tested recovery, reviewer separation, signed acceptance and an external emergency stop. Prompt instructions are not a security boundary; policy engine, identity verifier, controller, storage ACLs and release gate must enforce invariants independently of model behavior.

## 6. Implementation phases and exit criteria

**Phase 0 — Contract/baseline:** Freeze schemas, policy, threat model and trust boundaries. Identify GitHub plan/visibility, OIDC provider, controller API, audit platform and reviewer channel. Record baseline SHA/tree and current CI failure. Never make tests pass by weakening checks. Exit only with approved design and reproducible baseline.

**Phase 1 — Provenance:** Generate real artifacts/attestations; pin verifier toolchain; validate identity, source SHA/tree, predicate and artifact digest from actual bundles. Exit when positive and negative provenance tests pass in isolated CI.

**Phase 2 — Execution/audit:** Connect enforcement to the real controller and remove bypass routes. Configure independently administered audit storage. Implement durable idempotency and recovery. Exit when fault injection at every transition shows no unauthorized/duplicate side effect, missing intent or false success.

**Phase 3 — Adversarial:** Run the complete matrix against real interfaces and isolated test accounts. Preserve machine-readable results and sanitized logs in separate evidence storage. Exit with all required tests passing and zero unexplained outcomes.

**Phase 4 — Independent review:** Freeze the proposed exact revision. Reviewer records findings; implementers remediate; rerun full tests on the new SHA; reviewer verifies fixes. Exit with signed review for final SHA and no unresolved blocking findings.

**Phase 5 — Human acceptance/release evaluation:** Human accepts exact revision, artifacts, review and residual risk through approved authenticated channel. Seal packet and submit to Release Assurance. Exit only with authenticated canonical decision. BLOCK remains binding.

## 7. Required artifacts

- subject-manifest.json
- workflow-validation-report.json
- artifact-inventory.json
- machine-readable test reports
- oidc-verification-report.json (no raw tokens)
- provenance-verification.json plus original signed bundle/attestation reference
- execution-recovery-report.json
- audit-integrity-report.json
- adversarial-test-report.json
- security-review.json and signed reviewer evidence
- remediation-map.json
- human-acceptance.json and authenticated acceptance reference
- release-assurance-input.json
- release-assurance-decision.json

Bind all artifacts to the same subject SHA/tree and workflow run/attempt. Keep original signed evidence separate from summaries. Uploading artifacts from a failed run supports diagnosis but does not mean the run passed.

## 8. Observability and stop conditions

Emit structured, redacted events for each state transition and rejection. Monitor denials, signature failures, unknown outcomes, audit gaps, retries, replay attempts, policy changes and reviewer/acceptance expiry. An emergency stop controlled outside the agent runtime must disable new dispatches. If evidence is compromised or audit continuity is lost, suspend release evaluation until trust is restored.

## 9. Acceptance checklist

- [ ] Exact final commit and tree pinned.
- [ ] Full required workflow succeeds with no required checks skipped or missing.
- [ ] Artifact bytes inspected and digests recomputed.
- [ ] GitHub/Sigstore provenance cryptographically verified against trusted identities and exact source/artifact digests.
- [ ] Real OIDC tests pass, including wrong issuer/audience/subject, expiry, replay and key rotation.
- [ ] Real controller and independent audit service connected; administrative separation verified.
- [ ] Concurrency, idempotency, retries, crash recovery, audit outage and unknown-outcome tests pass.
- [ ] Real-interface adversarial suite passes with preserved evidence.
- [ ] Independent review covers exact final SHA; blocking findings remediated and verified.
- [ ] Authenticated human acceptance binds exact final SHA/tree, artifacts, review and policy.
- [ ] Evidence packet independently retrievable and integrity-verified.
- [ ] Canonical Release Assurance Agent alone evaluates the packet.
- [ ] Authenticated decision preserved; no release on BLOCK or indeterminate result.

## 10. Current disposition

**BLOCK — NOT PRODUCTION-READY.** This document is a specification, not proof of implementation. The currently observed PR revision failed the canonical validation stage and later specialized tests were skipped. Real OIDC/Sigstore integration, real controller/audit recovery validation, independent security review and authenticated human acceptance are not established by that run. Do not claim any gate passed without verified evidence from the actual systems.

## References

- Government of Canada, Guide on the Use of Agentic Artificial Intelligence: https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/generative-ai/guide-use-agentic-artificial-intelligence.html
- Government of Canada, Directive on Automated Decision-Making: https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=32592
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- NIST SP 800-218, Secure Software Development Framework: https://csrc.nist.gov/pubs/sp/800/218/final
- GitHub Docs, Security for GitHub Actions: https://docs.github.com/en/actions/how-tos/secure-your-work
- GitHub Docs, Artifact attestations: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- GitHub CLI, gh attestation verify: https://cli.github.com/manual/gh_attestation_verify
- SLSA, Verifying artifacts: https://github.com/slsa-framework/slsa/blob/main/spec/verifying-artifacts.md
