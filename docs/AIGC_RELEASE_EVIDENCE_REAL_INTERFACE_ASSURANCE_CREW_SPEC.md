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


## 10. Handoff coordination agents RX-53–RX-57

These five agents extend the existing release-evidence crew with an explicit, fail-closed handoff path. They are specification-only, disabled by default, and not production-integrated.

- **RX-53 — Repository Protection Configuration Evidence Coordinator:** requests and validates an administrator-authenticated readback of the actual `main` protection/ruleset configuration, required check names, bypass actors, and retrieval timestamp. An empty ruleset response or HTTP 403 without proven administrative visibility is not evidence that protection is absent or correct.
- **RX-54 — Independent Reviewer Qualification and Assignment Coordinator:** tracks the authorized assigner, reviewer identity, qualifications, conflict-of-interest declaration, and exact commit/evidence-digest binding. It cannot invent a person or treat an AI agent as the independent human reviewer.
- **RX-55 — Exact-Commit Findings Remediation and Retest Closure Verifier:** requires a finding inventory, immutable finding-to-commit/digest binding, remediation commit, independent retest results, and attributable closure evidence. A changed head invalidates dependent review/closure evidence.
- **RX-56 — Authenticated Human Acceptance Binding Verifier:** verifies authenticated actor identity/authority and explicit acceptance bound to the same final commit and evidence digest, after review and finding closure. A conversational authorization statement is not itself the repository's authenticated acceptance record.
- **RX-57 — Release Handoff Sequencing and Evidence Readiness Orchestrator:** coordinates the sequence but has no administrative, human-approval, merge, or release authority. It preserves RX-19 as the sole release decision authority.

### Required handoff sequence

1. Administrator-authenticated protection and required-check readback.
2. Qualified independent human reviewer assigned by an authorized administrator.
3. Findings bound to the reviewed SHA and digest; remediation and independent retest evidenced; closure verified.
4. Stacked PR lineage advanced in order; full CI rerun against each exact head after every rebase or retarget.
5. Authenticated human acceptance bound to the final SHA and evidence digest.
6. Protected merge only after the protection readback and all required gates are verified.
7. Post-merge live OIDC, cryptographic provenance, artifact digest, independent retention, and retrieval checks.
8. Complete authenticated packet submitted unchanged to RX-19.

Any changed SHA, base/head relationship, run attempt, reviewer, policy, digest, acceptance record, protection configuration, or retention policy invalidates affected evidence and requires revalidation. Missing, stale, inaccessible, contradictory, or unauthenticated evidence results in **BLOCK**. These specifications do not claim that the actions have already occurred.


## 11. Deep research and engineering assurance agents RX-58–RX-68

All eleven agents remain disabled and specification-only. They produce research evidence and recommendations, not administrative actions or release decisions.

| Agent | Mission | Key outputs |
|---|---|---|
| RX-58 — Continuous Research and Standards Intelligence | Track primary-source standards, government guidance, official framework revisions, advisories and source freshness. | Source register, claim-source map, change alerts, conflicts and uncertainty. |
| RX-59 — Agentic System Threat Modeling and Attack-Path Analyst | Map trust boundaries and cross-agent attack paths, including prompt injection, identity abuse, excessive agency and supply-chain compromise. | Threat model, attack graph, mitigations and control mapping. |
| RX-60 — Evaluation Science and Benchmark Integrity Architect | Design reproducible capability/safety evaluations and guard against leakage, contamination, cherry-picking and invalid comparisons. | Evaluation protocol, dataset lineage, uncertainty analysis and regression thresholds. |
| RX-61 — Prompt Injection and Tool-Abuse Red-Team Agent | Test untrusted content, indirect injection, confused-deputy paths, data exfiltration and tool misuse in isolated environments. | Bounded adversarial cases, reproducible evidence and mitigation proposals. |
| RX-62 — AI Governance and Jurisdictional Control Mapping Agent | Distinguish binding obligations from voluntary guidance and map controls by jurisdiction and use case. | Control crosswalk, applicability rationale, compliance gaps and human-review queue. |
| RX-63 — Data Governance, Privacy and Evidence Lifecycle Analyst | Review data minimization, access, residency, retention, deletion, redaction and sensitive evidence handling. | Data-flow inventory, privacy findings and control recommendations. |
| RX-64 — Reliability, Chaos and Recovery Test Architect | Test retries, idempotency, timeouts, queue failure, duplicate delivery, crash recovery and ambiguous outcomes. | Fault matrix, recovery tests and failure reports. |
| RX-65 — Observability, SLO and Cost Efficiency Analyst | Define SLI/SLOs, traces, alerting, budgets, capacity limits and cost attribution without weakening gates. | SLO proposal, telemetry gaps, cost scenarios and capacity-risk report. |
| RX-66 — Architecture Decision and Dependency Risk Reviewer | Compare design alternatives and assess dependency, licensing, coupling, migration and rollback risks. | Architecture decision records, dependency risk register and migration plan. |
| RX-67 — Incident Response and Emergency Stop Coordinator | Prepare response playbooks and verify independently controlled stop, escalation and recovery procedures. | Incident runbooks, escalation matrix and stop-control evidence requirements. |
| RX-68 — Research-to-Implementation Traceability Synthesizer | Convert sourced findings into versioned requirements, implementation tasks, tests and measurable acceptance criteria. | Claim-source-requirement-test traceability matrix and unresolved-assumption register. |

### Research quality and implementation rules

- Prefer primary government, standards-body, official project and original research sources; record publisher, canonical URL, publication/revision date, access date, jurisdiction and source type.
- Separate law/regulation, government policy, standards, normative specifications, voluntary guidance, vendor documentation and opinion. A control crosswalk is not legal advice, certification or proof of compliance.
- Preserve claim-to-source traceability, contradictions, uncertainty, scope limits and superseded guidance. Material recommendations require domain-owner review; high-risk security conclusions require independent human review.
- Evaluation results must state model/version, system prompt/policy version, tools, dataset lineage, sampling method, metrics, uncertainty, limitations and reproducible run references.
- Red-team work must use isolated non-production targets, synthetic data, bounded permissions and explicit stop conditions.
- Research agents cannot alter production policy, grant permissions, perform production side effects, assign reviewers, manufacture acceptance, merge or release. Missing or contradictory release-critical evidence remains **BLOCK**.

### Research baseline consulted

- NIST AI Risk Management Framework and Generative AI Profile: https://www.nist.gov/itl/ai-risk-management-framework and https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- SLSA v1.2 specification and artifact verification: https://slsa.dev/spec/v1.2/ and https://github.com/slsa-framework/slsa/blob/main/spec/verifying-artifacts.md
- OWASP GenAI Security Project 2026 Top 10 and agent-control resources: https://genai.owasp.org/2026/09/01/owasp-genai-security-project-unveils-2026-top-10-for-llm-applications-new-agent-control-standard-and-sponsors-as-community-tops-30000-members/
- CISA Secure by Demand guidance: https://www.cisa.gov/sites/default/files/2024-08/SecureByDemandGuide_080624_508c.pdf

These sources inform design only; they do not establish AIGC conformity or prove implementation, testing, independent verification or production authorization.


## 12. Operational and opportunity-acquisition agents RX-69–RX-83

| Agent | Mission |
|---|---|
| RX-69 — Opportunity Source Policy and Connector Eligibility | Maintains source terms, permissions, rate limits, attribution, licensing and manual-only/prohibited classifications. |
| RX-70 — Multi-Platform Job and Work Opportunity Discovery | Searches approved sources, normalizes postings, deduplicates listings and produces freshness-aware digests. |
| RX-71 — Candidate Evidence and Opportunity Fit | Ranks opportunities using user-controlled job-related evidence and explains fit, gaps and uncertainty. |
| RX-72 — Application Dossier and Truthful Materials Composer | Drafts tailored materials from verified candidate evidence; never fabricates qualifications or employment facts. |
| RX-73 — Human Application Approval and Submission Gate | Requires scoped human approval before external submissions or communications; sensitive declarations remain human-only. |
| RX-74 — Employer, Posting Authenticity and Job-Scam Risk Analyst | Checks impersonation, phishing, suspicious payment requests, employer identity and posting inconsistencies. |
| RX-75 — Opportunity Pipeline and Follow-Up Coordinator | Tracks saved roles, deadlines, approved follow-ups and outcomes in a private user-controlled pipeline. |
| RX-76 — Contracts, Tenders, Grants and Bounty Opportunity Scout | Finds paid contracts, tenders, grants, RFPs, apprenticeships and authorized bounty opportunities. |
| RX-77 — Product and Market Intelligence Analyst | Synthesizes source-backed customer segments, alternatives, market shifts and pricing signals. |
| RX-78 — Customer Discovery and Problem Validation | Structures consent-based discovery and distinguishes evidence from hypotheses. |
| RX-79 — Product Strategy and Roadmap Prioritization | Ranks roadmap options using validated needs, risk, effort, dependencies and measurable outcomes. |
| RX-80 — Go-to-Market, Partnerships and Revenue Operations | Drafts evidence-backed positioning, sales stages, partnerships and revenue experiments. |
| RX-81 — Customer Delivery, Onboarding and Success | Coordinates delivery plans, acceptance criteria, support and customer-outcome measurement. |
| RX-82 — Unit Economics and Financial Planning | Models costs, pricing scenarios, budgets and assumptions without moving funds or making commitments. |
| RX-83 — Runtime Operations and Integration Health | Defines connector health, SLOs, alerting, incident signals and recovery evidence. |

All 15 agents remain disabled and specification-only. The candidate profile is prohibited from repository storage. Unknown sources default to deny automated access. No agent may submit an application, message an employer, accept terms, complete an assessment, sign a contract or commit funds without explicit appropriate human approval.


## 13. Runtime integrity and operational resilience agents RX-84–RX-94

| Agent | Purpose and authority boundary |
|---|---|
| RX-84 Policy and Capability Boundary Auditor | Audits least-privilege decisions and capability scope; cannot grant credentials or change policy. |
| RX-85 Isolated Execution and Sandbox Assurance | Tests sandbox boundaries, network/filesystem restrictions and escape controls using safe test fixtures. |
| RX-86 Connector Contract and Conformance Tester | Exercises schemas, rate limits, timeouts, retries and error contracts using fixtures and approved endpoints. |
| RX-87 Evaluation Benchmark and Regression Integrity | Protects dataset provenance, checks leakage and compares versioned metrics without rewriting baselines to hide regressions. |
| RX-88 Cost, Quota and Resource Budget Guard | Estimates costs, checks quotas and flags anomalies; cannot incur unapproved spend. |
| RX-89 Private Memory and Knowledge Lifecycle Curator | Enforces private-store, retention, export and deletion boundaries; personal profiles must never be committed to Git. |
| RX-90 Evidence Lineage and Reproducibility Auditor | Verifies lineage, artifact digests and reproducibility; hashes alone do not establish trusted provenance. |
| RX-91 Observability, SLO and Incident Triage | Correlates telemetry, calculates SLO burn and drafts incident timelines and recovery recommendations. |
| RX-92 Human Review Queue and Decision Interface | Presents evidence/uncertainty and records authenticated decision references without impersonating humans or manufacturing consent. |
| RX-93 Integration Readiness and Rollback Planning | Maps dependencies, migration risk, feature flags, recovery points and rollback evidence. |
| RX-94 Cloud Build and Deployment Failure Investigator | Correlates commit to provider builds, classifies failure layers and assembles authorized logs for minimal reproducible fixes. |

All remain R0, disabled, specification-only and BLOCK-on-failure. RX-94 may diagnose Cloudflare/other provider builds but cannot deploy, change production secrets, or suppress failed checks. RX-92 does not itself provide a trusted authentication mechanism; that remains a separately implemented and tested identity/approval integration.


## 14. Release operations evidence assurance agents RX-95–RX-102

These eight additional agents decompose the five requested release parameters into independently checkable evidence tasks. They complement RX-94 and RX-53–RX-57 rather than replacing them. All are R0 read-only, disabled, specification-only, and fail closed; none is a production-integrated service.

| Agent | Responsibility | Required evidence / hard stop |
|---|---|---|
| RX-95 — Provider Build Evidence Intake and Redaction Gate | Validate authorized provider logs and evidence custody before analysis. | Build UUID, repository/branch/SHA, attempt and timestamps; redacted log digest; reject secrets or unredacted personal data. |
| RX-96 — Cloudflare Effective Configuration and Build Context Auditor | Compare effective Cloudflare settings and repo configuration for the specific failed attempt. | Root directory, build/deploy/preview commands, branch/repository, variables/secrets presence (never values), Wrangler configuration/name, retry-time settings, config digest. Missing logs/config means root cause UNKNOWN. |
| RX-97 — Independent Reviewer Identity and Independence Evidence Verifier | Validate administrator assignment and reviewer qualification/independence evidence. | Authorized assigner, reviewer identity and qualification, conflict declaration, exact reviewed SHA. AI review is not a substitute for a human reviewer. |
| RX-98 — Finding Ledger and Independent Retest Integrity Verifier | Reconcile finding lifecycle from review through fix and independent retest. | Stable finding ID/severity, reviewed SHA, remediation SHA, retest run and digest, independent closure actor; unresolved high/critical finding blocks. |
| RX-99 — Authenticated Acceptance Receipt and Replay Verifier | Verify trusted human acceptance, exact scope and replay resistance. | Authenticated actor/authority, final SHA, evidence-manifest digest, timestamp, expiry/revocation and unique receipt/nonce; chat text alone is not a receipt. |
| RX-100 — Repository Protection and Merge-State Readback Verifier | Verify authoritative, fresh ruleset/branch protection and actual merge preconditions. | Required checks/reviews, bypass actors, current head, review-thread state and permission-sufficient administrator readback. HTTP 403/empty/incomplete readback is UNKNOWN. |
| RX-101 — Stacked Pull Request Lineage and Evidence Invalidation Guard | Enforce dependency order and prevent advancing a stack with unresolved upstream gates. | Parent/base/head SHAs, PR states, exact-head workflow/run attempts and explicit invalidation of evidence after changes. |
| RX-102 — Release Evidence Manifest Consistency and Retention Reconciler | Reconcile all gate evidence into one packet for RX-19. | Matching subject SHA/digests across CI, review, acceptance, protection, merge, attestation and independent retention/retrieval evidence. Hashes alone do not prove provenance or independent retention. |

### Evidence-based Cloudflare diagnosis protocol

Cloudflare Workers Builds distinguishes build and deploy commands; its root directory determines where the build command runs, and retrying a build applies the settings that exist at retry time. Therefore RX-95/RX-96 must preserve the failed build UUID, source SHA, timestamps, attempt, effective settings snapshot and redacted logs together. Collect the configured Git repository/branch, root directory, build/deploy/preview commands, relevant Wrangler config and dependency-lock metadata, compatibility settings where applicable, and variable/secret names or presence only. Never request or store secret values. Check worker name against Wrangler configuration and classify the failure layer from observed logs. Do not infer that any common Cloudflare error is the cause without evidence. Official references: [Cloudflare configuration](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/) and [build troubleshooting](https://developers.cloudflare.com/workers/ci-cd/builds/troubleshoot/).

### Governance and provenance basis

- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches): reviews, required checks, stale approvals and bypass policy must be checked as live controls.
- [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations) and [SLSA v1.2](https://slsa.dev/spec/v1.2/): verify signer/workflow identity, source, predicate and subject digest; do not treat a digest alone as provenance. Private-repository feature availability must be checked against the repository plan.
- [Government of Canada Guide on the Use of Agentic Artificial Intelligence](https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/generative-ai/guide-use-agentic-artificial-intelligence.html): bounded autonomy, accountable human ownership, recoverability and auditability inform the agent boundaries.

This is a primary-source research baseline, not an exhaustive legal or compliance assessment. Research establishes design inputs, not proof of implementation or conformity. The registry's release operations contract defines required evidence fields, invalidation rules and blocking controls. RX-19 remains the sole release decision authority.


## 15. AIGC Systems Excellence Layer — RX-103–RX-120

This layer fills cross-cutting platform gaps without replacing existing specialists. It defines eighteen R0, disabled, specification-only agents and a systems-excellence contract.

| Agent | Primary mandate |
|---|---|
| RX-103 — Chief Systems Architecture and Architecture Decision Agent | Owns architecture decision records, cross-agent interfaces, dependency boundaries, version compatibility, and architecture drift analysis. |
| RX-104 — Mission Portfolio and Workstream Orchestrator | Decomposes approved objectives into bounded workstreams, dependencies, milestones, owners, evidence gates, and critical paths; cannot authorize external effects. |
| RX-105 — Requirements-to-Executable-Contract Compiler | Compiles traceable requirements into versioned schemas, invariants, acceptance tests, negative cases, and evidence obligations. |
| RX-106 — Durable Workflow and State Integrity Agent | Audits durable execution, idempotency, retries, checkpoint recovery, deduplication, cancellation, compensation, and state-transition safety. |
| RX-107 — Model and Provider Routing and Resilience Optimizer | Evaluates model/provider capability, quality, latency, availability, data residency, policy, and cost to recommend constrained routing and fallback. |
| RX-108 — Tool and MCP Capability Broker and Connector Security Agent | Validates tool identity, schemas, capability grants, consent, server trust, provenance, output handling, and least-privilege connector access. |
| RX-109 — Identity, Secrets and Zero-Trust Access Auditor | Reviews workload identity, short-lived credentials, secret handling, authorization boundaries, rotation evidence, and separation of duties without reading or exposing secret values. |
| RX-110 — Data Classification, Privacy and Tenant Isolation Agent | Enforces classification-aware processing, tenant boundaries, minimization, retention, deletion evidence, residency constraints, and privacy-safe telemetry. |
| RX-111 — Knowledge Retrieval and Context Integrity Agent | Checks retrieval provenance, freshness, source permissions, citation alignment, poisoning indicators, context separation, and unsupported claim risk. |
| RX-112 — Agent Behavior Evaluation and Calibration Scientist | Defines task-level quality and safety metrics, calibration, uncertainty thresholds, representative test sets, statistical validity, and release-blocking regressions. |
| RX-113 — Adversarial Simulation and Continuous Red-Team Agent | Builds authorized sandboxed attack simulations for prompt injection, tool abuse, data poisoning, privilege escalation, and cross-agent trust failures. |
| RX-114 — Quality Engineering, Mutation and Fault-Injection Agent | Designs unit, integration, contract, property, mutation, chaos, and fault-injection tests; measures test sensitivity and recovery behavior. |
| RX-115 — Performance, Capacity and Cost Optimization Agent | Models throughput, queueing, tail latency, token and tool budgets, quota exhaustion, capacity, and quality-cost tradeoffs with bounded optimization. |
| RX-116 — Observability, SLO and Operational Intelligence Agent | Defines traceable agent/tool/workflow telemetry, SLOs, error budgets, redaction, anomaly detection, alert routing, and incident evidence. |
| RX-117 — Human Collaboration and Decision UX Architect | Designs clear approval surfaces, risk-tiered confirmations, reversible actions, accessible explanations, and explicit distinctions between suggestions and executed actions. |
| RX-118 — Legal, License, IP and Regulatory Horizon Scanner | Tracks jurisdiction-specific legal obligations, data/model/tool licenses, IP provenance, contract restrictions, policy changes, and review triggers; does not provide final legal advice. |
| RX-119 — Productization, Customer Delivery and Support Readiness Agent | Checks deployment packaging, operator runbooks, support ownership, onboarding, accessibility, service boundaries, customer commitments, and rollback readiness. |
| RX-120 — Continuous Improvement and Post-Incident Learning Agent | Converts verified incidents, near misses, eval regressions, and operator feedback into prioritized corrective actions with owners, tests, and measurable closure. |

### System-level acceptance invariants

- Architecture and requirements are versioned, traceable and contract-first; dependency graphs are acyclic and interfaces explicit.
- Planning, policy decision, tool execution, verification and human authority are separated. Tool execution requires a separate policy-controlled permit.
- Retrieved content and tool results are untrusted data and cannot override system policy, tool allowlists or user authorization.
- Model/provider routing obeys policy, data residency, quality, availability and budget constraints; fallback cannot silently broaden permissions or weaken controls.
- Durable workflows require idempotency, bounded retries, checkpoint recovery, cancellation, compensation and replay testing.
- Evaluation is reproducible and includes representative tasks, adversarial cases, regression gates, uncertainty handling and test-quality evidence.
- Telemetry correlates agent, workflow and tool spans while minimizing sensitive data capture and redacting secrets.
- No agent can grant itself capabilities, reveal secrets, fabricate evidence, make unapproved external commitments, merge or authorize release.
- Missing, stale, contradictory, unauthorized or unbound evidence results in BLOCK. Research mappings are not certifications or proof of compliance.

### Research baseline and limits

The registry references NIST AI RMF and its Generative AI Profile, OWASP's 2026 agentic and 2025 LLM risk frameworks, MITRE ATLAS, MCP security guidance, NIST SSDF, SLSA v1.2, OpenSSF Scorecard, OpenTelemetry GenAI semantic conventions, and Government of Canada agentic-AI guidance. NIST states that AI RMF 1.0 is being revised, so RX-58 must track revisions and preserve version/date context. OpenTelemetry's agent conventions are marked as development; implementations must check stability and supported instrumentation before depending on them. Research sources are design inputs, not evidence that AIGC has implemented or conforms to them.

Primary references:
- [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
- [OWASP Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [OWASP LLM Applications 2025](https://genai.owasp.org/llm-top-10/)
- [MITRE ATLAS](https://atlas.mitre.org/)
- [MCP security guidance](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)
- [NIST SSDF SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final)
- [SLSA v1.2](https://slsa.dev/spec/v1.2/)
- [OpenSSF Scorecard](https://scorecard.dev/)
- [OpenTelemetry GenAI agent conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- [Government of Canada agentic-AI guide](https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/generative-ai/guide-use-agentic-artificial-intelligence.html)

RX-19 remains the sole release decision authority. The systems-excellence layer cannot override mandatory human gates or change release disposition.
