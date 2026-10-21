# AIGC Security Agent Trio — Parameter Specification

**Status:** Proposed normative design; not yet production-validated.  
**Applies to:** `Lornt1666/AIGC` and the governed release path.  
**Decision invariant:** Any missing, malformed, stale, conflicting, unauthenticated, out-of-scope, or wrong-revision evidence produces `BLOCK` (or `UNKNOWN` at an evidence producer, which the release authority maps to `BLOCK`).  
**Authority model:** Three evidence-producing evaluators remain separate from the canonical Release Assurance Agent and the execution controller. No agent may self-approve its own evidence or modify repository policy as part of assessment.

## 1. Design basis

This specification uses NIST SSDF (secure development lifecycle), GitHub rulesets and protected-branch controls, OWASP CI/CD security guidance, SLSA provenance, and the in-toto attestation model. The intended trust model is explicit: evidence is a claim until its producer identity, scope, subject, integrity, and freshness have been verified.

## 2. Shared parameter contract

All agent calls MUST accept a versioned request envelope. Unknown policy-critical fields MUST cause rejection rather than being silently ignored.

| Field | Type / constraint | Required | Rule |
|---|---|---:|---|
| `schema_version` | string, e.g. `1.0.0` | yes | Reject unsupported major versions. |
| `policy_id` | non-empty immutable identifier | yes | Selects reviewed policy; caller cannot weaken it inline. |
| `policy_digest` | lowercase SHA-256 hex (64 chars) | yes | Must match the loaded, approved policy bytes. |
| `repository` | canonical `owner/name` | yes | Must equal allowlisted repository. |
| `commit_sha` | full Git object ID, 40 hex for SHA-1 repos | yes | Never accept branch names or abbreviated SHAs as release identity. |
| `tree_sha` | full Git tree object ID | yes | Must match the tree under test; re-read from trusted GitHub API. |
| `run_id` | provider run ID, string | yes for CI evidence | Must resolve to a real run for the same repository and SHA. |
| `invocation_id` | unique opaque string | yes | Correlates one execution and its logs/evidence. |
| `requested_at` | RFC 3339 UTC timestamp | yes | Reject invalid/future timestamps beyond 5-minute clock skew. |
| `deadline_seconds` | integer, 1–3600 | yes | Per-call execution timeout; timeout is not a pass. |
| `mode` | `observe`, `evaluate`, `enforce` | yes | Default `observe`; no writes in observe/evaluate. Enforcement requires explicit external authorization. |
| `risk_tier` | `standard`, `elevated`, `critical` | yes | Selects stricter policy; cannot reduce baseline checks. |
| `evidence_uri` | allowlisted URI | where applicable | HTTPS/provider-native references only; reject arbitrary local paths and untrusted redirects. |
| `evidence_sha256` | lowercase SHA-256 hex | where applicable | Recompute over exact downloaded bytes; never trust a supplied digest alone. |
| `producer_identity` | exact workflow/app identity | for signed evidence | Compare issuer, repository, workflow path/ref, event, and builder against policy. |
| `observed_at` | RFC 3339 UTC | yes per evidence | Must be within freshness window and not materially in the future. |
| `expires_at` | RFC 3339 UTC | yes per decision | Decision expires; controller rechecks at use time. |
| `correlation_id` | unique opaque string | yes | Carries across logs, receipts, and decision. |

**Common validation rules:** strict schema; bounded input sizes; no implicit coercion; canonical JSON serialization for hashes; reject duplicate JSON keys; safe path/URL handling; redact secrets; bounded retries; deterministic ordering; explicit UTC; and no reliance on LLM interpretation for pass/fail. An LLM may explain findings, but cannot replace a typed checker or cryptographic verifier.

## 3. GitHub Protector Agent

### Mission
Read authoritative GitHub settings and compare actual state with a versioned desired-state policy. Report drift and evidence; do not silently change settings or grant itself privileges.

### Required inputs
- Repository identity and default branch obtained from GitHub API, not caller assumptions.
- All active repository/organization rulesets that can affect target refs, including inherited rules where available.
- Legacy branch-protection response for each protected ref.
- Ruleset target patterns, enforcement state, rule types, bypass actors/modes, required status-check names and expected GitHub App source.
- CODEOWNERS file and its resolved ownership for security-sensitive paths.
- Repository Actions permissions, fork-PR settings, workflow approval policy, secret scanning/code scanning availability where supported.
- API permission scope, pagination completeness, API version, retrieval timestamps, HTTP status, and response hashes.

### Parameters and proposed defaults
| Parameter | Default | Acceptance rule |
|---|---|---|
| `protected_refs` | `refs/heads/main`, `refs/tags/v*` | Explicit allowlist; exact fnmatch semantics; test positive and negative patterns. |
| `ruleset_enforcement` | `active` | `evaluate` or `disabled` is BLOCK for release refs. |
| `min_approvals_standard` | 1 | At least one approval from a person other than author; stale approvals dismissed on new changes. |
| `min_approvals_elevated` | 2 | Two distinct eligible reviewers for security/control-plane/release-policy changes. |
| `require_code_owner_review` | true | Required for CODEOWNERS-covered security-sensitive paths. |
| `require_latest_push_approval` | true | Approval must cover the latest reviewable push. |
| `require_conversation_resolution` | true | All review threads resolved before merge. |
| `required_checks` | policy-owned exact list | Each check name unique and bound to expected GitHub App where possible; no fuzzy names. |
| `require_up_to_date` | true | Require current base or merge-queue-equivalent validation. |
| `allow_force_push` | false | Must be disabled for protected refs. |
| `allow_deletion` | false | Must be disabled for protected refs/tags. |
| `require_signed_commits` | true where supported by repository workflow | Verify compatibility and actual enforcement; signature alone does not prove safe code. |
| `bypass_policy` | none for normal release path | Any exception must be named, least-privileged, time-bounded, separately approved, and audited; unknown bypass actor/mode is BLOCK. |
| `api_freshness_seconds` | 300 | Re-read settings immediately before final decision; API error/pagination gap = UNKNOWN. |
| `drift_severity` | critical for missing protection or unexpected bypass | Any critical drift blocks. |

### Checks
1. Enumerate every active ruleset targeting each protected ref; account for overlapping rulesets and legacy rules.
2. Verify the exact rules, target patterns, enforcement state, bypass actors and bypass mode—not merely that a ruleset exists.
3. Verify expected status-check source, unique check names, and branch-up-to-date policy.
4. Confirm no actor can bypass critical checks outside the documented break-glass procedure.
5. Validate CODEOWNERS syntax and coverage for workflows, release logic, security agents, dependency lockfiles, and policy files.
6. Compare live observations against policy digest; emit field-level drift with source API, timestamp, and response digest.
7. Re-read after any authorized change and attach before/after observations.

### Output
`ProtectorReport`: `status` (`PASS|FAIL|UNKNOWN`), repo, commit/tree SHA, policy ID/digest, observation timestamp, settings snapshot digest, checks[] with expected/observed values, severity, source API references, pagination completeness, drift list, reviewer/authorization references if a change was made, and canonical report digest.

### Prohibited behavior
No self-granting admin, no direct push to protected branches, no silent policy edits, no suppressing alerts, no assuming API absence means safe, and no reporting configuration as applied until read-back confirms it.

## 4. Cybersecurity Agent

### Mission
Orchestrate and evaluate real security tools against the exact tested source revision. It does not label a scan as passed unless the tool actually ran, its output is available, and the output is bound to the same source tree.

### Required check families
1. Workflow permissions and untrusted event/PR boundaries.
2. Third-party action pinning and supply-chain inventory.
3. Secret scanning, including history where feasible and redacted findings.
4. Dependency/SCA scanning against lockfiles and resolved dependency graph.
5. SAST/lint/security-specific static analysis.
6. IaC/container scanning if those artifacts exist.
7. Adversarial regression tests for agent boundaries, policy tampering, prompt injection, and evidence substitution.
8. SBOM generation and dependency inventory where release artifacts warrant it.
9. Optional DAST/fuzzing for exposed application components; explicitly mark not applicable with justification, never silently omit.
10. Build/test integrity and workflow configuration review.

### Parameters and proposed defaults
| Parameter | Default | Acceptance rule |
|---|---|---|
| `tool_manifest` | policy-pinned tool IDs, versions, and digests | Unpinned or unapproved tool = BLOCK for required checks. |
| `action_pin_mode` | full commit SHA | Tags/branches alone are not acceptable for third-party Actions in privileged workflows. |
| `permissions_baseline` | workflow/job token permissions set explicitly | Default read-only; grant write only to the single job that needs it. |
| `fork_pr_secrets` | prohibited | No secrets or privileged write token in untrusted fork PR execution. |
| `secret_findings_threshold` | 0 confirmed live secrets | Any confirmed secret blocks; rotate/revoke and assess exposure before re-evaluation. |
| `critical_vulnerability_threshold` | 0 unresolved exploitable critical findings | BLOCK; require documented remediation or separately approved exception policy (never automatic waiver). |
| `high_vulnerability_policy` | 0 unresolved exploitable highs in release-critical paths | BLOCK by default; exception requires owner, rationale, compensating controls, expiry, and independent approval. |
| `cvss_source` | scanner's CVSS plus exploitability/context | Do not treat CVSS alone as complete risk ranking. |
| `scan_timeout_seconds` | 900 per tool, configurable per tool | Timeout/error/missing output = UNKNOWN, never PASS. |
| `retry_count` | 1 transient retry | Retry only transient infrastructure failures; preserve all attempts. |
| `evidence_freshness_seconds` | 86400 | Evidence older than 24h is stale for release decision; rerun on current SHA. |
| `finding_suppression` | disabled unless policy-managed | Every suppression must have stable finding ID, rationale, owner, approver, expiry, and compensating control. |
| `max_log_bytes` | 10 MiB per tool output | Truncation must be explicit and cannot hide failure summaries; store full output as controlled artifact. |
| `parallelism` | bounded, e.g. 4 | Avoid resource exhaustion and shared-workspace contamination. |
| `network_policy` | deny by default; allowlist required endpoints | Prevent exfiltration and supply-chain fetches from untrusted code. |

### Per-check evidence contract
Every check record must include: check ID/version; required/optional flag; tool name/version/digest; repository; commit SHA and tree SHA; run ID and attempt; invocation ID; start/end times; exit code; normalized result; raw-output URI and SHA-256; finding count by severity; suppressions; environment/container image digest; and checker identity. Results from a different SHA, missing raw output, missing run ID, or unknown tool identity are not valid evidence.

### Threat cases to test
- Pull-request-controlled workflow or test code tries to read secrets.
- Malicious action tag moves after review; action is not pinned by full SHA.
- Workflow token has write permissions outside the minimal job.
- Scanner exits nonzero but wrapper reports success.
- Scanner output is empty, truncated, forged, or from an earlier run.
- A report claims a different commit/tree than the workflow run.
- Prompt injection in issue/PR/file content instructs an agent to ignore policy or disclose secrets.
- Symlink/path traversal, archive bombs, oversized artifacts, malicious filenames, JSON duplicate keys, and parser disagreement.
- One checker or agent attempts to edit another agent's evidence or policy.

### Output
`CybersecurityReport`: status, exact source identity, required-check inventory, each check record, normalized findings, suppression register, tool manifest digest, evidence digests, run links, coverage gaps, residual risk, and report digest. Findings must distinguish `PASS`, `FAIL`, `UNKNOWN`, and justified `NOT_APPLICABLE`; release policy decides which statuses are acceptable.

## 5. Trustworthiness Assessment Agent

### Mission
Cryptographically validate provenance and attestations for both (a) canonical receipt bundle and (b) actual release artifact. Do not infer trust from filenames, workflow success, JSON fields, or a claimed `verified=true` alone.

### Parameters and proposed defaults
| Parameter | Default | Acceptance rule |
|---|---|---|
| `required_subjects` | exactly `canonical_receipt_bundle`, `release_artifact` | Both must have distinct, correct subject digests and independent subject verification. |
| `digest_algorithm` | SHA-256 | Recompute digest from actual downloaded bytes; compare with attestation subject. |
| `attestation_format` | in-toto Statement / supported GitHub artifact attestation | Reject unknown predicate types and unsupported schema versions. |
| `provenance_predicate` | SLSA provenance predicate accepted by pinned verifier | Pin expected predicate type/version; reject unexpected external parameters. |
| `allowed_issuer` | exact approved issuer | Issuer mismatch = BLOCK. |
| `allowed_repository` | `Lornt1666/AIGC` | Exact repository identity, not display-name matching. |
| `allowed_workflow_path` | exact protected workflow path(s) | No wildcard unless explicitly justified by policy. |
| `allowed_ref` | approved release ref / protected main policy | Verify event and ref; PR workflow identity alone cannot authorize release provenance. |
| `allowed_builder_id` | exact expected builder identity | Accept only approved signer-builder pairs. |
| `source_commit_sha` | exact full SHA | Must match expected commit and provenance dependency. |
| `tree_sha` | exact tree SHA | Must match tested source tree. |
| `maximum_age_seconds` | 86400 | Expired or stale attestation blocks; future timestamp beyond 300s blocks. |
| `clock_skew_seconds` | 300 | Enforce bounded clock skew. |
| `required_signatures` | all required signature/identity checks | Signature validity, certificate chain/issuer, identity, timestamp, and transparency evidence must be verified by a trusted verifier. |
| `unexpected_fields` | reject policy-critical unknowns | Schema evolution must be versioned; unknown trust-bearing claims are not accepted. |
| `verifier_binary` | pinned version and digest | Record verifier version, invocation, exit code, and output digest. |
| `network_fail_closed` | true | If identity/transparency/attestation service cannot be checked, result UNKNOWN/BLOCK. |
| `duplicate_evidence` | reject conflicting duplicates | Multiple conflicting attestations for same subject = BLOCK pending investigation. |

### Verification sequence
1. Fetch exact bytes from an allowlisted source and hash them locally.
2. Parse strictly and validate schema/type.
3. Verify cryptographic envelope, signature, certificate/issuer, signer identity, transparency/timestamp material where applicable.
4. Verify repository, workflow path, event, ref, builder, invocation/run, source commit, tree, and expected predicate.
5. Verify the attestation subject digest equals the digest of the actual artifact bytes.
6. Verify provenance dependencies and external build parameters against policy; reject unexpected external parameters.
7. Verify freshness and revocation/status requirements supported by the format/provider.
8. Produce a report with raw evidence hashes and verifier logs; do not trust caller-provided booleans or a digest without recomputation.

### Output
`TrustworthinessReport`: per-subject `PASS|FAIL|UNKNOWN`, artifact URI, recomputed SHA-256, attestation digest, predicate type, signer/issuer/workflow identity, builder ID, source commit/tree, run ID, verification tool/version/digest, verification timestamp, transparency/timestamp result, mismatch list, and report digest. A report passes only when every mandatory verification succeeds.

## 6. Canonical Release Assurance Agent

### Authority and inputs
This is the only component allowed to issue the canonical release decision. It consumes authenticated, schema-validated reports from the three producers and the exact intended release manifest. It does not run tools itself, mutate repository policy, generate attestations, or deploy artifacts.

### Decision parameters
| Parameter | Default | Rule |
|---|---|---|
| `required_agents` | Protector, Cybersecurity, Trustworthiness | All three required. |
| `required_report_status` | `PASS` | `FAIL`, `UNKNOWN`, missing, malformed, stale, or duplicate report = BLOCK. |
| `repository_match` | exact | All reports must match allowlisted repo. |
| `commit_match` | exact full SHA | Every report, run, receipt and provenance must match the release commit. |
| `tree_match` | exact | No test-tree/release-tree substitution. |
| `policy_digest_match` | exact | All producers use same approved policy digest. |
| `required_subjects` | two required subjects | Receipt bundle and actual release artifact. |
| `max_evidence_age_seconds` | 86400 | Enforce per-evidence age at decision time. |
| `decision_ttl_seconds` | 900 | Decision expires after 15 minutes; re-evaluate before execution. |
| `digest_recompute` | true | Recompute canonical report/evidence digests; reject mismatch. |
| `conflict_policy` | BLOCK | Any conflicting reports or multiple incompatible candidates block. |
| `exception_policy` | disabled by default | Exceptions require policy-owned approval, narrow scope, expiry, rationale, compensating controls, and immutable audit evidence. No LLM-only waiver. |
| `reason_codes` | fixed enum | Every decision includes stable machine-readable reasons and human-readable explanation. |
| `decision_signature` | required before production execution | Sign/attest decision using a protected identity inaccessible to assessed workload. |
| `decision_storage` | append-only / tamper-evident | Record decision and referenced evidence digests; corrections create a new record, never rewrite history. |

### Decision function
- **PASS** only if all required producer reports are authentic, fresh, internally consistent, bound to the same repo + commit + tree + policy digest, and all required checks/subjects pass.
- **BLOCK** for any failed check, critical finding, mismatch, missing evidence, verifier failure, policy drift, unauthorized exception, or expired decision.
- **UNKNOWN** may be used internally to represent inability to assess; externally the release gate treats it as BLOCK.
- A later PASS does not erase an earlier BLOCK; it supersedes it with a new invocation and a new evidence set.

### Minimum decision receipt
Include decision ID, policy version/digest, repo, commit/tree SHA, both artifact subject digests, producer report digests, raw evidence digests, timestamp, expiry, reason codes, verifier identities, and signature/attestation. The receipt itself must be included in the canonical receipt bundle without circular self-hashing; define a manifest that lists the receipt digest externally or use a detached signature.

## 7. Execution Controller (separate enforcement component)

The controller is not a decision authority. Immediately before any release/publish/deploy action it must:
1. Fetch the canonical signed decision from the approved store.
2. Verify the decision signature and expiry.
3. Re-fetch current protected-ref SHA and ensure it still equals the approved SHA.
4. Recompute the actual artifact digest and compare it with the approved subject.
5. Verify no policy/configuration drift invalidates the decision.
6. Confirm the requested action is permitted by the decision scope and environment.
7. Execute with least-privilege, short-lived credentials; record actor, action, target, timestamp, result, and receipt.
8. Abort if any precondition is false or unavailable.

No agent may deploy merely because its own assessment passed. Human approval remains mandatory for first-time policy changes, security exceptions, and irreversible/high-impact operations until separately reviewed automation controls are proven.

## 8. Evidence integrity and report envelope

Each report should use a canonical, versioned JSON schema. At minimum:
- `report_type`, `schema_version`, `policy_id`, `policy_digest`
- `repository`, `commit_sha`, `tree_sha`, `invocation_id`, `run_id`
- `producer_id`, `producer_version`, `produced_at`, `expires_at`
- `status`, `checks[]`, `findings[]`, `evidence_refs[]`
- `raw_output_sha256`, `report_digest`, and signature/attestation reference

Canonicalization must be specified (e.g., a documented canonical JSON profile) before hashing. A plain hash detects accidental changes only when the expected hash is held in a trusted location; it does not authenticate the report. Authenticate reports through a trusted workflow identity/signature or protected storage. Raw evidence must be retained with access controls and redaction.

## 9. Permissions and isolation

- Read-only GitHub permissions for inventory/evaluation.
- Separate, minimal write identity only for approved configuration-as-code workflow; never share it with untrusted PR jobs.
- Set `permissions: contents: read` and other workflow permissions explicitly; add narrowly scoped permissions only in the job that needs them.
- No secrets for fork PR jobs; use OIDC/short-lived credentials for cloud access.
- Isolate untrusted code and scanner execution; no privileged containers or shared mutable workspaces between trust zones.
- Protect agent code, workflow files, policy, verifier adapters, schemas, CODEOWNERS, and release scripts with independent review.
- Redact credentials and sensitive environment data from logs and reports.
- Rate-limit APIs, bound downloads and decompression, pin dependencies, and retain an audit trail for all policy changes.

## 10. Validation and acceptance gates

Before production use, tests must demonstrate:
1. Happy path with synthetic repo, exact commit/tree, successful scans, and two independently verified subjects.
2. Missing/malformed/stale evidence blocks.
3. SHA/tree/repository/policy digest mismatch blocks.
4. Wrong issuer, workflow, ref, builder, event, or predicate blocks.
5. Artifact byte mutation fails digest comparison.
6. Invalid signature, expired certificate/attestation, failed transparency check, verifier crash, and network outage block.
7. Missing required ruleset, inactive ruleset, wrong target pattern, unexpected bypass, wrong status-check source, and stale review block.
8. Scanner nonzero exit, timeout, truncated output, missing raw output, unapproved tool, and secret/high/critical finding block.
9. Tampered report digest/signature and duplicate conflicting reports block.
10. Decision expiry, head movement, artifact substitution, policy drift, and unauthorized controller action abort execution.
11. Tests prove there is no write-capable credential available to assessment jobs.
12. An independent reviewer validates threat model, code, workflow permissions, verifier identity constraints, and negative tests.

Unit tests with mocks are useful but insufficient. Before calling the system production-ready, run end-to-end tests against actual GitHub APIs and the actual attestation verifier on a disposable test artifact, and preserve raw run logs, run IDs, hashes, and the exact commit/tree.

## 11. Implementation order

1. Freeze this parameter policy and its schema under independent review.
2. Implement strict JSON schemas and canonical report hashing.
3. Implement the read-only GitHub API adapter with pagination/completeness checks and drift comparison.
4. Implement real scanner adapters that retain tool output and bind each result to run + commit + tree.
5. Implement pinned provenance/attestation verification for both required subjects.
6. Integrate the three signed reports into the existing canonical Release Assurance authority; do not create a competing authority.
7. Implement controller preflight checks and immutable decision receipts.
8. Add adversarial tests, then validate on a disposable release artifact.
9. Obtain independent security review and authorized admin read-back of real repository rules.
10. Permit release only after exact-head end-to-end evidence passes.

## 12. Research references

- NIST SP 800-218, Secure Software Development Framework: https://csrc.nist.gov/pubs/sp/800/218/final
- GitHub available rules for rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- GitHub creating repository rulesets and bypass configuration: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
- GitHub protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- OWASP CI/CD Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html
- SLSA specification and provenance: https://slsa.dev/spec/v1.1/ and https://slsa.dev/spec/v1.1/provenance
- in-toto Attestation Framework: https://github.com/in-toto/attestation/blob/main/spec/README.md
- GitHub artifact attestations API and verification guidance: https://docs.github.com/en/rest/orgs/attestations

**Important:** These values are proposed secure defaults, not claims that GitHub settings are already configured or that the current AIGC release has passed. Where provider features, repository tier, or existing architecture differ, record the limitation and keep the release blocked until an equivalent control is independently verified.
