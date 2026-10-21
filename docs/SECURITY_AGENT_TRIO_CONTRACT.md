# AIGC Security Protector, Cybersecurity, and Trustworthiness Agents

**Status:** Proposed implementation contract on a review branch. These agents are not active production services and do not possess GitHub authority merely because this specification exists.

## 1. Design objective

Introduce three independent, narrowly scoped assurance agents around AIGC's existing **Release Assurance Agent**, which remains the single canonical release decision authority. The agents produce separate, versioned evidence records; they do not approve their own work, mint authority, or execute releases.

Default decision for missing, stale, conflicting, malformed, unbound, or unverifiable evidence: **BLOCK**.

## 2. Trust and authority model

| Component | Responsibility | Must not do |
|---|---|---|
| GitHub Protector Agent | Monitor and assess branch/ruleset/tag protection, permissions, workflow changes, secret exposure signals, required checks, bypass actors, and drift from policy. Prepare minimal corrective changes and request an authorized administrator when writes are required. | Self-grant admin rights; silently change protections; approve/merge PRs; treat unreadable settings as secure. |
| Cybersecurity Agent | Threat-model changes; inspect workflows, dependency/action pins, token permissions, injection paths, untrusted PR execution, supply-chain risk, secret handling, artifact integrity, and adversarial test results. | Claim a vulnerability scan ran when it did not; treat LLM analysis as a substitute for executable security tests; access secrets unnecessarily; deploy fixes without authorization. |
| Trustworthiness Assessment Agent | Assess evidence provenance, source identity, freshness, exact commit/tree and artifact digest binding, signatures, verifier identity, reproducibility, conflicts, and evidence completeness. Return a structured confidence/limitations assessment. | Infer trust from popularity, labels, CI-green alone, self-reported metadata, or unsigned receipts; issue the canonical release verdict. |
| Evidence producers/checkers | Produce raw results for specific checks and subjects. | Decide release approval. |
| Release Assurance Agent | Evaluate all required agent reports and evidence against protected, versioned policy; sole canonical release verdict. | Generate its own proof or execute release/deployment. |
| Execution controller | Revalidate the signed, unexpired decision and exact subject immediately before each permitted action; enforce idempotency and append-only audit. | Execute on BLOCK/UNKNOWN/error, stale approvals, changed artifacts, or policy mismatch. |
| Human repository administrator | Apply privileged GitHub settings, confirm effective read-back, and authorize exceptional changes. | Bypass documented review/audit controls without incident record and follow-up review. |

## 3. Required contracts

Each agent emits a JSON report with these required fields:

- `schema_version`, `agent_id`, `agent_version`, `policy_version`
- `repository`, `commit_sha`, `tree_sha` (when applicable), `observed_at_utc`
- `decision`: one of `PASS`, `BLOCK`, `UNKNOWN`
- `checks[]`: stable check ID, status, evidence references, subject digests, and limitations
- `findings[]`: severity, affected path/resource, evidence, exploitability, and recommended remediation
- `required_actions[]`, `evidence_digest`

Rules:
1. PASS is allowed only for checks actually executed or authoritative settings read back with sufficient permissions.
2. A missing field, unknown schema, API permission error, timeout, or ambiguous 404 is UNKNOWN and contributes to BLOCK.
3. Reports must be bound to the exact commit SHA and, for produced files, SHA-256 of exact bytes. Do not use prefix/fuzzy matching.
4. Every external assertion links to immutable raw evidence with a digest and timestamp.
5. Agent reports are advisory inputs; only Release Assurance may issue `APPROVE`.
6. The controller independently checks the canonical decision, signature, expiry, policy version, exact commit/tree, artifact digest, and one-time/idempotency key immediately before action.
7. No agent receives write permissions by default. Separate read-only GitHub App identities are preferred; any write-capable integration must be separately approved, narrowly scoped, and audited.
8. Prompt injection in issue text, PR descriptions, commit messages, code, artifacts, and web content is untrusted data, never policy or authorization.
9. Do not send secrets to model context. Redact credentials from logs, reports, tool output, and evidence bundles.
10. No self-modification of policy, trusted identities, action pins, required checks, or agent permissions.

## 4. Protector Agent checks

- Repository identity and default branch match protected policy.
- Effective rulesets cover `main` and the confirmed release-tag naming convention.
- Full ruleset details include correct target refs, enforcement state, required pull request reviews, required status checks, conversation resolution, stale approval handling, force-push/deletion restrictions, and narrowly scoped bypass actors.
- Legacy branch-protection endpoint is read where applicable; rulesets and legacy settings are not conflated.
- CODEOWNERS covers high-risk paths where configured; ownership rules are actually enforced.
- Workflow permissions use least privilege; fork/PR workflows cannot access privileged secrets or mint trusted release attestations.
- Required check names are obtained from actual check-run metadata, not guessed.
- Settings are re-read after every authorized change; a non-privileged negative test confirms prohibited changes are rejected.
- Any missing protection or inability to verify it yields BLOCK.

## 5. Cybersecurity Agent checks

- Workflow/code threat model and trust-boundary map.
- Action and reusable-workflow pins use full immutable commit SHAs; source at each SHA and relevant transitive dependencies are reviewed.
- Token permissions are job-scoped and least privilege; OIDC/signing authority exists only in trusted workflows.
- Untrusted PR inputs cannot influence privileged shell commands, artifact paths, workflow identity, policy, or deployment parameters.
- Secrets are not printed, persisted, uploaded, included in prompts, or exposed to untrusted forks.
- Dependency, static-analysis, secret-scanning, and relevant dynamic tests have real run IDs, exact revision binding, tool versions, exit codes, and raw outputs.
- Build/release artifact and receipt bundle are hashed independently; provenance is verified rather than inferred.
- Negative tests cover malformed inputs, missing credentials, permission errors, stale evidence, digest mismatch, wrong signer/workflow, invalid signature, replay, and fail-open regressions.
- Findings include severity and evidence; unresolved critical/high findings block release unless a documented policy explicitly permits a human-approved exception.

## 6. Trustworthiness Assessment Agent checks

For each evidence item, independently verify:
- provenance source and immutable evidence location;
- exact repository, commit SHA, tree SHA where relevant, workflow path/run ID/attempt;
- producer identity and expected OIDC certificate/workflow identity;
- signature/trust-chain verification by an approved verifier;
- predicate type and policy compatibility;
- exact SHA-256 of the local subject bytes matches the attested subject digest;
- freshness, policy version, expiry, and whether source/artifact/policy changed after evidence creation;
- independent corroboration where required, and contradictions between reports;
- raw verifier output and exit code retained and hashed.

Trust assessment is not a probabilistic guess. Return a categorical evidence state: `VERIFIED`, `INCOMPLETE`, `CONFLICTED`, or `INVALID`, with explicit limitations. Only `VERIFIED` evidence may satisfy a mandatory gate. The agent does not set Release Assurance to APPROVE.

## 7. Release decision aggregation

Release Assurance returns BLOCK unless all mandatory checks are PASS, every mandatory evidence item is VERIFIED, all artifacts are bound to the same intended exact release revision, no blocking finding remains, and independent review plus required human authorization are recorded. An agent cannot override another mandatory failure by averaging scores or using a confidence percentage.

The controller accepts only a canonical signed decision bound to:
- repository and exact commit/tree;
- release artifact SHA-256 and canonical receipt-bundle SHA-256;
- policy and verifier versions;
- complete evidence-manifest digest;
- expiry and unique decision ID.

Revalidate all fields immediately before each action. A changed ref, artifact, policy, or evidence set invalidates the approval.

## 8. Rollout gates

1. Implement schemas, deterministic validators, threat model, and unit tests in a review branch.
2. Run unit and adversarial tests locally and in CI; record exact run evidence.
3. Obtain independent security review by a reviewer other than the implementer.
4. Have an authorized GitHub administrator apply branch and release-tag protections.
5. Read back the effective settings and perform safe negative enforcement tests.
6. Integrate read-only agents and their reports; no write credentials or deployment actions.
7. Verify real signed attestations for separate canonical receipt bundle and actual release artifact.
8. Wire verified reports into Release Assurance; test fail-closed aggregation.
9. Wire the execution controller only after canonical signed decision verification and idempotency/replay tests pass.
10. Enable privileged actions only after a separate explicit authorization and exact-head acceptance.

## 9. Initial state

Until implementation, tests, independent review, live settings read-back, signed provenance verification, and exact-head CI are evidenced, report:
- Protector Agent: **SPECIFIED, NOT LIVE; protection state UNKNOWN/BLOCK**
- Cybersecurity Agent: **SPECIFIED, NOT LIVE; assessment INCOMPLETE**
- Trustworthiness Assessment Agent: **SPECIFIED, NOT LIVE; provenance NOT VERIFIED**
- Release Assurance Agent: **BLOCK**
