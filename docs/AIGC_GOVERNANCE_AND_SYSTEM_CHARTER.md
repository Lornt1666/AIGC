# RegenExcalibur AIGC — Governance and System Charter

**Document status:** Proposed governance baseline; requires owner review and controlled adoption.  
**Version:** 1.0.0-draft  
**Last reviewed:** 2026-10-23  
**Repository:** `Lornt1666/AIGC`  
**Release posture:** NOT PRODUCTION AUTHORIZED  
**Default posture:** deny by default, dry-run, read-only evidence acquisition, no unapproved external side effects.

## 1. Identity and ownership

### 1.1 Business and product identity

- **Business/project identity:** RegenExcalibur.
- **Product/system name:** AIGC — Artificial Intelligence Gladiator Coliseum.
- **Project principal / owner-designated accountable person:** Justice Gray Maciocha.
- **Source repository:** `Lornt1666/AIGC`.
- **System class:** a governed multi-agent software platform for controlled task intake, orchestration, tool-mediated work, evidence collection, artifact production, verification, and accountable human decision-making.

These are project identity declarations. They do not independently establish incorporation, registered business status, trademark registration, legal ownership of every contribution, or repository administration privileges. Those claims require separate authoritative records. GitHub account identity and repository permissions must be checked independently.

### 1.2 Purpose

AIGC is intended to coordinate multiple specialized agents and deterministic services to complete bounded tasks while preserving provenance, least privilege, auditability, recoverability, and human control. Agent output is untrusted until validated against the task contract and policy. A registration entry or agent specification does not mean that the agent is implemented, enabled, independently reviewed, or production-ready.

### 1.3 Business boundary

RegenExcalibur is the business/project identity associated with this AIGC initiative. AIGC is a software product/system, not a synonym for all RegenExcalibur ventures or engineering concepts. Any other RegenExcalibur project must have its own scope, data boundary, authority, and release controls unless explicitly integrated through a reviewed contract.

## 2. Governance and authority

### 2.1 Authority hierarchy

1. **Owner-designated principal — Justice Gray Maciocha:** sets business objectives and approves governance changes through authenticated, recorded channels. This declaration does not bypass repository branch protection or independent review.
2. **RX-19 — sole release decision authority under current project governance:** makes the final release decision only against a complete, independently verified evidence packet for one exact candidate SHA and canonical evidence digest.
3. **RX-144 — coordination only:** coordinates the closure workflow and evidence handoff; it cannot approve release, waive blockers, or substitute for RX-19.
4. **Human approvers and independent reviewers:** act only within explicitly granted roles; their approvals must be authenticated, unexpired, unrevoked, and bound to the exact candidate and evidence digest.
5. **Policy verifier / execution controller:** enforces authenticated, scoped, time-bounded permits immediately before each protected side effect. A coordinator or model cannot bypass this boundary.
6. **Agents and workers:** execute only registered, enabled, versioned handlers within assigned capabilities. They cannot grant permissions, change their own authority tier, approve their own work, or issue a release decision.

### 2.2 Release invariants

- A green CI run is necessary evidence, not release authorization.
- Evidence from an earlier SHA, base revision, workflow attempt, policy version, or trust-store state cannot certify a newer candidate.
- Missing, stale, conflicting, inaccessible, unauthenticated, unauthorized, incomplete, or revoked evidence is BLOCK/UNVERIFIABLE—not PASS.
- Re-read live PR head and base after evidence collection. If either changes, discard the closure digest and restart.
- No merge, deployment, production write, live external action, or agent activation is authorized by this document or by a successful CI run.
- RX-19's authenticated decision receipt must bind to the same candidate SHA and canonical evidence digest as the accepted evidence packet.

## 3. System definition and boundaries

AIGC contains multiple related surfaces. They must not be confused with one another:

### 3.1 Application workflow / phase surface

The repository README documents phased workflows for public read-only opportunity ingestion, assessment, proposal drafting, human approval packets, controlled execution receipts/manual handoffs, audit-packet drafts, outcome recording, governed improvement proposals, local memory, a secrets-vault scaffold, observability, and simulation/replay. These are separate workflow stages with distinct input/output contracts. A phase being documented or runnable does not imply that all phases are safe for live production use.

External communication, submissions, bids, purchases, credential use, or other consequential actions require a separate explicit authorization contract and a trusted enforcement adapter. Public data replay remains read-only unless a distinct, reviewed scope authorizes otherwise.

### 3.2 Runtime and orchestration surface

The current hardening direction includes:

- **Contracts:** versioned task/result/evidence/permit models with bounded hops, timeouts, budgets, and exact-candidate bindings.
- **Coordinator:** bounded scheduling, event-driven dispatch, deadline enforcement, idempotency, retry ceilings, dead-letter handling, and Saga compensation only after outcome reconciliation.
- **Durable state:** PostgreSQL-backed task/event state, append-only ledger protections, transactional outbox, and durable receipt-claim/replay controls.
- **Transport:** Redis Streams with at-least-once delivery semantics; consumers must assume duplicate delivery and implement idempotent effects.
- **Static arbiter:** AST and payload screening only. It never executes source and is not an OS sandbox.
- **Worker/API boundary:** authenticated API plus a separate worker process; disabled/spec-only agents are blocked rather than dispatched.
- **Evidence closure:** read-only live GitHub acquisition, attempt-aware CI evaluation, signed receipt checks, artifact-byte/manifest verification, candidate recheck, and a gate-by-gate blocker matrix.
- **Telemetry:** structured events and opt-in tracing/metrics, with sensitive attributes filtered.
- **Deployment:** non-root/read-only containers, internal-only database and transport networks, separate database identities, explicit health checks, and dry-run defaults.

This is an architecture and implementation inventory, not proof that every path is production-integrated or independently verified.

### 3.3 Memory layers

Use three distinct conceptual layers with explicit data classification:

- **L1 — ephemeral execution context:** short-lived task-local state; no assumption of durability.
- **L2 — retrieval/index layer:** optional search or vector retrieval. Qdrant is currently optional and must not be described as operationally integrated until the data path, access controls, retention, and tests exist.
- **L3 — durable system of record:** transactional task state, event/outbox ledger, receipt claims, and audit records in PostgreSQL/approved durable storage.

Retrieved text, agent memory, external documents, and tool output are untrusted data—not policy or authority. Memory may inform planning but cannot override signed contracts, policy, permissions, or human decisions.

### 3.4 Observability

Critical state transitions must emit structured, correlated evidence without logging secrets or unnecessary personal data. Required coverage includes task lifecycle, queue latency and pending age, retries, dead letters, worker crashes, permit denials, receipt rejections, artifact verification, external adapter outcomes, spend ceilings before provider enablement, and release-gate results. Instrumentation code alone does not establish coverage; coverage and alert behavior require measured tests.

## 4. Agent registry and role contracts

The registry currently includes RX-149 through RX-161 as disabled, R0, `SPECIFIED_NOT_PRODUCTION_INTEGRATED` agents. Their responsibilities are:

| ID | Role | Allowed responsibility | Non-negotiable boundary |
|---|---|---|---|
| RX-149 | Live GitHub Evidence Acquisition | Read-only PR, CI, review, status, and protection evidence collection | GET-only; incomplete/inaccessible evidence is not PASS |
| RX-150 | Cryptographic Receipt Verification | Verify signed receipts, issuer/key purpose, candidate binding, expiry, revocation, and replay claims | Trusted-key policy is external; signature alone grants no authority |
| RX-151 | Master Orchestrator / Meta-Planner | Decompose and schedule bounded tasks | Cannot elevate permissions or authorize release |
| RX-152 | Governance and Policy Enforcement | Evaluate policy and report enforcement outcomes | Must use authenticated policy inputs and fail closed |
| RX-153 | State and Memory Manager | Manage task state and approved memory operations | Cannot rewrite audit history or treat retrieved content as authority |
| RX-154 | Telemetry and Watchdog | Observe health, deadlines, and failures | Must not expose secrets; cannot silently override policy |
| RX-155 | Research and Evidence Synthesis | Gather sources, compare claims, distinguish facts from assumptions | Must preserve source provenance and uncertainty |
| RX-156 | Operations and API Actions | Perform explicitly permitted operations through approved adapters | No permit, no side effect; no arbitrary shell/code execution |
| RX-157 | Software and Systems Engineering | Propose code/design changes and tests | Changes require review, exact-head CI, and controlled deployment |
| RX-158 | Data Extraction and Analytics | Parse, validate, and analyze authorized datasets | Enforce schema, minimization, and data-access scope |
| RX-159 | Adversarial Red Team / Security Auditor | Test attack paths and policy boundaries | Must be separated from implementation approval and release authority |
| RX-160 | QA and Verification Gatekeeper | Run acceptance checks and bind results to candidate/evidence | Cannot self-certify missing evidence or waive a failing gate |
| RX-161 | Human-in-the-Loop Dispatcher | Route requests for human decisions and record receipts | Cannot impersonate a human or infer consent |

The above table defines intended roles, not operational status. Each agent remains disabled until its implementation, contracts, identity, tests, telemetry, failure behavior, independent review, and activation approval are evidenced. RX-19 is not part of this worker-role table; it is the release decision authority.

## 5. Target architecture and decision

### 5.1 Recommended topology: hybrid Saga-driven directed graph

Use PostgreSQL as the durable system of record and transactional outbox, Redis Streams as at-least-once transport, a bounded coordinator for dependency-aware scheduling, independently authorized tool adapters, and explicit compensation/reconciliation steps for multi-step mutations. This provides a practical balance between centralized policy control and distributed worker execution.

| Architecture | Strengths | Principal risks | Disposition |
|---|---|---|---|
| Centralized orchestrator | Easier global policy and traceability | Controller bottleneck and single control-plane failure | Useful for policy decisions, not a single unreplicated execution bottleneck |
| Pure event choreography | Decoupled and scalable workers | Harder global state, compensation, and causal tracing | Not sufficient alone for high-consequence workflows |
| Hybrid Saga + directed graph | Durable state, explicit dependencies, local workers, controlled compensation | More operational complexity; requires strong idempotency and reconciliation | Recommended target |

### 5.2 Boundaries and defaults

- Maximum hop count: 10 unless an approved versioned policy sets a stricter bound.
- Agent processing timeout: default 30 seconds per bounded unit; provider/tool-specific budgets must be measured and separately configured.
- Queue latency target: under 500 ms is a proposed SLO, not a measured fact or guarantee.
- Retries: finite attempt ceiling, exponential backoff with full jitter, explicit deadline, and dead-lettering for poison messages.
- Budget: hard task/agent/provider ceilings enforced before execution; never rely only on model instructions to control cost.
- Idempotency: stable operation key plus payload digest; same key with a different payload is a conflict, not a retry.
- Side effects: reconcile unknown outcomes before retry or compensation. A timeout does not prove an operation failed.
- Isolation: no arbitrary generated-code execution in the main service. Any future execution sandbox requires OS/container isolation, non-root identity, resource limits, restricted network, read-only filesystem where feasible, and no secrets by default.
- Security: authentication, authorization, and permit verification are separate checks; validate permissions immediately before the effect.
- Secrets: secret values must not enter Git, prompts, logs, artifacts, images, or telemetry. Use a dedicated secret manager and scoped identities.
- Network: databases and Redis are private/internal; public access requires a documented threat model and explicit approval.

## 6. Evidence model and acceptance gates

Evidence must be treated as seven separate properties:

1. **Observed** from a named source at a recorded time.
2. **Integrity-checked** against bytes or a canonical digest.
3. **Authenticated** to a known source/issuer.
4. **Authorized** for the specific role, purpose, scope, and policy version.
5. **Bound** to repository, PR, head/base SHA, workflow/run/attempt, artifact subject, and policy version as applicable.
6. **Fresh and complete**, including all required pages/attempts and a final live candidate recheck.
7. **Independently evaluated** against acceptance policy rather than trusting producer-supplied booleans.

Production closure requires every applicable gate to pass for one immutable candidate and evidence digest:

- G0: live candidate identity and post-check revalidation.
- G1: exact-head CI; every required job created, completed, and successful; logs and artifacts inspected.
- G2: artifact integrity, strict manifest, file digests, safe archive handling, and exact run/attempt binding.
- G3: effective branch/ruleset protection independently evidenced.
- G4: qualified independent review, findings ledger, remediation, and independent retest tied to exact SHA.
- G5: trusted provenance and supply-chain checks.
- G6: authenticated human acceptance bound to the candidate and digest.
- G7: authenticated handoff to RX-19.
- G8: RX-19's authenticated decision receipt for the same candidate and digest.

A CI attempt inventory must be complete. For each workflow run ID, only the highest observed attempt is eligible; a later failed, cancelled, queued, or in-progress attempt invalidates an earlier success. Conflicting same-attempt records fail closed. An old artifact cannot be substituted for the latest successful attempt.

## 7. Threat model and FMEA minimum

| Failure mode | Impact | Required controls / acceptance evidence |
|---|---|---|
| Prompt injection or untrusted retrieved instructions | Unauthorized tool use or data disclosure | Treat content as data; tool allowlists; scoped permits; adversarial tests |
| Excessive agent agency or confused deputy | High-impact unauthorized mutation | Least privilege, per-effect authorization, identity separation, human gates |
| Generated code or AST bypass | Arbitrary execution or resource abuse | Static screen is not a sandbox; execution disabled unless isolated and independently reviewed |
| Duplicate delivery / lost acknowledgement | Repeated external mutation | Idempotency key, durable effect ledger, outcome reconciliation, crash fault-injection |
| Outbox/transport inconsistency | Lost or duplicate logical work | Transactional outbox, eventual publish, atomicity and replay tests |
| Poison message / retry storm | Queue exhaustion and cascading failure | Size/schema/hop bounds, retry ceilings, jitter, dead-letter queue, alerting |
| Saga compensation after ambiguous success | Data corruption or double action | Reconcile external outcome before compensation; idempotent compensation; operator escalation |
| Receipt replay or cross-process race | Reuse of stale authorization | Signed scoped receipts, persistent uniqueness/claim ledger, expiry/revocation tests |
| Stale CI/artifact evidence | False release confidence | Attempt-aware exact-head checks, artifact subject binding, final head/base recheck |
| Supply-chain compromise | Compromised build or dependency | Hash-locked dependencies, digest-pinned images, SHA-pinned actions, SBOM, vulnerability policy, provenance verification |
| Secret leakage | Account or infrastructure compromise | Secret manager, scoped identities, redaction, log/artifact scans, rotation procedure |
| Recovery illusion | Irrecoverable ledger/state after outage | Isolated restore drill, integrity reconciliation, measured RPO/RTO, retained backups/WAL as configured |
| Telemetry gaps | Silent failure and weak incident response | Coverage tests, synthetic alerts, redaction checks, operational dashboards |

## 8. Production exit criteria

Do not label AIGC production-grade until all of the following are complete and evidenced:

- [ ] Current exact-head CI passes and every required job, test log, and artifact is inspected.
- [ ] A reviewed hash-locked dependency file is used in clean builds; base images are digest-pinned; workflow actions are pinned by full commit SHA.
- [ ] SBOM, vulnerability scan, remediation policy, and trusted build provenance are produced and independently verified.
- [ ] Permit verifier and side-effect adapters use a separately protected identity/trust service and enforce authorization immediately before mutation.
- [ ] Qualified independent security reviewer is assigned by an authorized administrator; review and all finding retests bind to the exact candidate SHA.
- [ ] Staging fault injection covers outbox atomicity, Redis outage, duplicate delivery, worker crash/reclaim, poison messages, receipt replay races, artifact tampering, and candidate changes during closure.
- [ ] Observability coverage and alert paths are tested; no secrets are emitted.
- [ ] Backup restore is demonstrated in an isolated target; ledger, migrations, replay claims, RPO and RTO are reconciled and recorded.
- [ ] Effective repository protection is verified through an authorized source; inaccessible readback remains unverifiable.
- [ ] Human acceptance, RX-19 handoff, and RX-19 decision receipts are authenticated and bound to the same candidate SHA and canonical evidence digest.
- [ ] All agent activation decisions are explicit, scoped, and separately evidenced. No bulk activation based solely on registry presence.
- [ ] Owner review of this charter and the production runbook is recorded.

## 9. Operational runbook principles

Use a controlled staging environment first. From the repository root:

```bash
# Validate configuration only; does not start services.
docker compose config --quiet

# Build configured app and worker images.
docker compose build app worker

# Start the configured stack in staging.
docker compose up -d

# Inspect health and recent logs.
docker compose ps
docker compose logs --no-color --tail=200 app worker

# Run tests using the repository's configured Python environment.
python -m pytest -q

# Check PostgreSQL readiness using the configured service.
docker compose exec -T postgres pg_isready
```

Service names, environment variables, and migration behavior must be taken from the checked-out Compose file and migration scripts, not assumed from this example. A successful build or test suite is not a recovery drill.

For recovery, restore into a separate isolated environment, validate schema and migration state, reconcile durable task/event/outbox records and receipt claims, verify replay/idempotency behavior, and record measured RPO/RTO. Do not run destructive restore operations against production as a checklist exercise.

## 10. Research basis

- NIST AI RMF Generative AI Profile, NIST AI 600-1: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- NIST Secure Software Development Framework, SP 800-218: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- SLSA provenance specification: https://slsa.dev/spec/v1.2/provenance
- SLSA artifact verification guidance: https://github.com/slsa-framework/slsa/blob/main/spec/verifying-artifacts.md
- GitHub artifact attestations: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- Redis Streams: https://redis.io/docs/latest/develop/data-types/stream/
- PostgreSQL continuous archiving and PITR: https://www.postgresql.org/docs/current/continuous-archiving.html

These references inform controls and acceptance criteria. They do not prove that AIGC currently satisfies them.

## 11. Change control

This charter is a proposed governance baseline, not a production approval. Changes to release authority, agent authority tiers, permit policy, evidence acceptance, secret access, or external side-effect permissions require authenticated owner/governance review, versioned policy, tests, and an auditable change record. RX-19 remains the sole release decision authority unless an explicit authenticated governance change is approved and independently validated.
