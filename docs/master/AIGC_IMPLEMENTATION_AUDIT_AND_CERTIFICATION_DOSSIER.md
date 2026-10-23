# AIGC Requirement-by-Requirement Implementation Audit and Certification Dossier

**Repository:** `Lornt1666/AIGC`  
**Product/business:** RegenExcalibur — Artificial Intelligence Gladiator Coliseum (AIGC)  
**Assessment type:** Remote source-and-CI evidence review; preliminary, non-independent  
**Candidate assessed:** `925f9028b151c14485ebff999d3d3a0853e44005`  
**PR:** #336, draft/open/unmerged; base `docs/aigc-governance-charter`  
**Assessment date:** 2026-10-23 UTC  
**Release authority:** RX-19 under current governance  
**Disposition:** **NOT CERTIFIED — BLOCKED**  
**Important limitation:** This is an evidence-backed assessment record, not a certificate of conformity, penetration-test report, independent assurance opinion, or production authorization.

## 1. Executive determination

The current evidence does **not** establish that AIGC satisfies all production requirements. No certification claim is issued.

The most decisive findings are:

1. GitHub Actions run [#4591](https://github.com/Lornt1666/AIGC/actions/runs/39917274277) tested candidate `925f9028b151c14485ebff999d3d3a0853e44005`. Its main `validate` job reached the canonical validation runner and failed with `validation stage failed: redaction`. At the time of this assessment, the run had not yet reached a final workflow conclusion. This is a blocking CI result, not a pass.
2. The same run showed some earlier focused test steps completing successfully, including closure-workflow tests (19 tests) and core runtime tests (28 tests). Those focused successes do not override the later canonical validation failure or prove the entire workflow passed.
3. The registry diagnostic reported 153 agents, all disabled by default, default disposition BLOCK, and production authorization NOT_GRANTED.
4. `core/worker.py` explicitly says it dispatches no agent because registered agents are disabled/specification-only. Its task processing records a `TASK_BLOCKED` event and durable BLOCKED task state. It is a fail-closed reference worker, not evidence of an operational autonomous agent execution path.
5. `core/arbiter.py` performs static AST inspection and explicitly states that it is not a sandbox. No evidence in this audit establishes a production-grade isolated execution environment for arbitrary generated code.
6. The Compose file configures an application, worker, PostgreSQL, Redis, and optional Qdrant, but manifest presence alone does not prove staging/production deployment, isolation under attack, backup restoration, SLO performance, or recovery objectives.

**Certification decision: BLOCKED.** AIGC must not be described as production-ready or certified until the blocking findings are remediated and the acceptance evidence in Sections 5–9 is collected, independently evaluated, and bound to the exact release candidate.

## 2. Assessment method and evidence boundary

This review examined the repository tree, master specification, wiring registry, verification plan, closure matrix, readiness ledger, core contracts/orchestrator/arbiter/worker, Compose configuration, CI workflow, and the live Actions run and job logs. It is a remote repository review, not a local checkout execution, live production inspection, independent security review, or witnessed recovery drill.

Evidence classifications:
- **Source-observed:** directly visible in the named file at the candidate revision.
- **CI-observed:** directly visible in a specific workflow/run/job log.
- **Requirement-only:** documented intended behavior with no sufficient implementation evidence.
- **Runtime-unverified:** source/configuration exists, but live behavior was not demonstrated.
- **Blocked:** direct evidence of a failure or a missing prerequisite.
- **Unknown:** evidence was not available in this assessment; unknown is not a pass.

The implementation status vocabulary is: `IMPLEMENTED_AND_TESTED`, `IMPLEMENTED_UNVERIFIED`, `PARTIAL`, `SPEC_ONLY`, `DISABLED`, `BLOCKED`. Because the complete exact-head CI workflow has not passed, no component is elevated to `IMPLEMENTED_AND_TESTED` for production acceptance by this audit.

## 3. Candidate-specific CI evidence

| Evidence item | Observation | Assessment |
|---|---|---|
| Candidate SHA | `925f9028b151c14485ebff999d3d3a0853e44005` | Bound to the reviewed run |
| Workflow | AIGC CI, run #4591 / ID `39917274277` | [Live run](https://github.com/Lornt1666/AIGC/actions/runs/39917274277) |
| Exact checkout | Log reports requested and observed SHA match | Pass for checkout identity only |
| Docker Compose validation/runtime image build | Step completed successfully | Pass for that CI step only |
| Dependency installation and vulnerability audit | Steps completed successfully | Pass for those steps only; not a comprehensive supply-chain certification |
| Focused closure tests | 19 tests reported OK | Focused suite only |
| Focused core runtime tests | 28 tests reported OK | Focused suite only |
| Registry diagnostic | `agent_count: 153`, all disabled, disposition BLOCK, production authorization NOT_GRANTED | Registry syntax/consistency check only; not runtime agent readiness |
| Canonical validation runner | `validation stage failed: redaction`, exit code 1 | **FAIL / BLOCKING** |
| Workflow final conclusion | Still in progress at the last query; final conclusion not available | **INCOMPLETE** |
| Artifact upload | CI log reports artifact upload succeeded, SHA-256 `d7b435c289debf0806787cca81fff35aa81adbf9baa6dbeaf36bfbcd917413a3` | Upload/integrity metadata only; does not make failed validation pass |
| Locked-target revalidation jobs | Two jobs completed successfully for historical fixed SHAs | Not evidence for the current candidate's full validation |

The downloaded sanitized artifact for run #4591 narrowed the failure to one scanner finding: `docs/master/AIGC_CONTROL_TO_EVIDENCE_TRACEABILITY_STANDARD.md`, line 96, pattern `(?i)(authorization\\s*:\\s*)[^\\n]+`. The scanner treated a prose label (`Authorization: ...`) as secret-like content. The label was changed to `Authorization requirements — ...` in commit `bf5849a9b73788e1f5fb9c1ecb176b0a2b672b14`; this changes documentation wording only and does not weaken or bypass the scanner. Run #4594 on that candidate was still in progress at the follow-up observation; the correction is therefore **not yet verified by a completed CI run**. Do not disable or weaken redaction to obtain a green result.

## 4. Requirement-by-requirement logical wiring audit

The wiring IDs below match `docs/master/AIGC_WIRING_AND_INTERFACE_REGISTRY.md`. Statuses are conservative source-review dispositions at the candidate SHA, not claims that a live production environment was exercised.

| Wire | Required behavior (short form) | Initial status | Evidence / gap to close |
|---|---|---|---|
| W-001 | Authenticated, bounded ingress and task IDs | PARTIAL | API/CLI surfaces and bearer-token Compose setting exist; validate all ingress paths, identity lifecycle, rate limits, and adversarial payloads end-to-end. |
| W-002 | Strict versioned contract validation | IMPLEMENTED_UNVERIFIED | `core/contracts.py` provides strict Pydantic models; exact-head full validation is not passing. Add/verify API-to-worker contract parity and boundary tests in canonical CI. |
| W-003 | Exact action/resource/scope authorization request | PARTIAL | Permit-verifier interface exists in coordinator design; prove every protected action reaches it and no alternate path bypasses it. |
| W-004 | Authenticated policy/permit result | BLOCKED | No complete current-candidate evidence proves cryptographic issuer/purpose/scope validation is wired into the worker's protected-effect path. |
| W-005 | Resolve only registered, enabled, versioned handlers | PARTIAL | Worker reads registry and rejects enabled entries; all 153 agents disabled. Real handler registration/version compatibility and controlled enablement are not demonstrated. |
| W-006 | Atomic task state + outbox transaction | IMPLEMENTED_UNVERIFIED | PostgreSQL schema/migrations and coordinator code exist; require integration tests for commit/rollback and crash injection against actual migration path. |
| W-007 | Durable outbox publishing to Redis Streams | IMPLEMENTED_UNVERIFIED | Coordinator and Redis Streams code exist; require dispatcher recovery, publish-then-crash, duplicate publish, and backlog tests. |
| W-008 | Consumer group delivery and recovery | PARTIAL | Redis consumer implementation exists; prove pending-entry recovery, concurrent consumers, ownership transfer, and delivery semantics under faults. |
| W-009 | Worker revalidation before processing/effect | PARTIAL | Contract/task identity validation is visible; worker currently blocks rather than dispatching. Demonstrate fresh policy/permit validation at actual effect point. |
| W-010 | Durable idempotency claim and digest conflict | IMPLEMENTED_UNVERIFIED | Receipt/idempotency persistence components and tests exist; demonstrate concurrent process/database races and crash recovery in integration tests. |
| W-011 | Allowlisted adapter call under permit | BLOCKED | Reference worker explicitly dispatches no agent. Production handler-to-adapter path is not demonstrated. |
| W-012 | Scoped external side effect with receipt | BLOCKED | No enabled production adapter/effect evidence or witnessed end-to-end receipt was established. |
| W-013 | Durable result, effect receipt, state and audit | PARTIAL | Database/event code exists; no demonstrated full effect-to-receipt transaction across real adapter failures. |
| W-014 | ACK only after durable result/transfer | IMPLEMENTED_UNVERIFIED | Consumer/coordinator code exists; crash-after-commit-before-ACK and duplicate delivery must pass in integration CI. |
| W-015 | Bounded retries with one deadline | IMPLEMENTED_UNVERIFIED | Coordinator contains bounded retry/deadline logic and focused core tests passed in run #4591; full canonical CI failed later. |
| W-016 | DLQ and controlled operator replay | PARTIAL | Dead-letter schema/logic exists; prove retry ceilings, poison isolation, replay authorization, and no re-enqueue loop. |
| W-017 | Saga compensation and reconciliation | PARTIAL | Saga primitives and focused tests exist; no evidence of real side-effect compensation or external-state reconciliation drill. |
| W-018 | Artifact schema, archive, digest, provenance validation | IMPLEMENTED_UNVERIFIED | Artifact/evidence verifier code and focused tests exist; current-candidate supply-chain acceptance remains incomplete. |
| W-019 | Immutable validated artifact passed downstream | PARTIAL | Digest/manifest patterns exist; verify every consumer rechecks subject, schema, digest and trust policy. |
| W-020 | Authorized partitioned memory retrieval | BLOCKED | Qdrant is optional in Compose; no evidence establishes production ACL/tenant/data-classification enforcement in a live retrieval path. |
| W-021 | Durable source/ACL/retention metadata | BLOCKED | No end-to-end indexing and retrieval provenance exercise was established. |
| W-022 | Audit ledger records decisions and transitions | PARTIAL | Append-only event structures and audit references exist; verify tamper resistance, completeness and behavior when audit writes fail. |
| W-023 | Correlated logs, traces and metrics | PARTIAL | Telemetry modules/configuration exist; no operational coverage, alert test, redaction proof, or exporter-outage drill established. |
| W-024 | Least-privilege secret broker and secret manager | DISABLED | Secret retrieval is documented disabled by default; no live secret access is authorized by this assessment. |
| W-025 | Human approval bound to exact action | PARTIAL | Approval-related schemas/phases exist; demonstrate authenticated reviewer, payload digest, expiry, revocation and audit persistence end-to-end. |
| W-026 | Approval cannot be reused for changed action | PARTIAL | Binding is required in specifications; complete integration evidence for changed payload/target and replay rejection is missing. |
| W-027 | Accurate execution receipt for real action | BLOCKED | Worker does not execute registered agents; no real-action receipt path is demonstrated. |
| W-028 | Evolution proposal requires review | PARTIAL | Evolution proposal controls are documented; prove no self-apply path exists across all entry points. |
| W-029 | Local memory/events obey path and retention policy | UNKNOWN | No targeted source/runtime evidence collected in this audit; inspect implementation and test filesystem/retention boundaries. |
| W-030 | Dashboard health is timestamped and truthful | PARTIAL | Health/readiness surfaces exist; no live telemetry freshness/staleness test was witnessed. |
| W-031 | Phase 13 public-data replay is read-only | PARTIAL | Read-only intent is documented; verify all adapters are non-mutating and network allowlists/rate limits are enforced. |
| W-032 | CLI phase routing validates mode and schema | PARTIAL | CLI/phase registries exist; complete command-surface and unauthorized-mode tests need evidence. |
| W-033 | Emergency stop blocks protected effects | PARTIAL | Emergency-stop controls are documented; require live fault-injection while tasks are queued, running and reconciling. |
| W-034 | Closure reads complete current GitHub evidence | IMPLEMENTED_UNVERIFIED | Closure/acquisition modules and focused tests exist; live evidence source completeness and final workflow pass are not established. |
| W-035 | Canonical evidence packet preserves provenance | PARTIAL | Canonicalization/digest logic exists; prove complete pagination, conflicting records, and cross-SHA evidence rejection in live acquisition. |
| W-036 | CI artifact binds to latest successful exact attempt | IMPLEMENTED_UNVERIFIED | Latest-attempt invalidation logic and focused regression tests are visible/passed; current canonical run failed at redaction, so closure is blocked. |
| W-037 | Independent reviewer and findings ledger | BLOCKED | No qualified independent reviewer assignment and exact-head review/remediation evidence was established. |
| W-038 | Human acceptance binds to final SHA/digest | BLOCKED | No valid current-candidate human acceptance receipt was presented. |
| W-039 | Complete packet delivered to RX-19 | BLOCKED | No complete verified closure packet/digest has passed the prerequisite gates. |
| W-040 | RX-19 decision binds exact candidate | BLOCKED | No valid release decision receipt for this candidate and evidence digest was presented; release remains unauthorized. |
| W-041 | Immutable artifact deployment and rollback | BLOCKED | Compose manifest is present, but no production deployment, immutable artifact promotion, health verification or rollback drill was evidenced. |
| W-042 | Isolated restore and durable-state reconciliation | BLOCKED | No witnessed backup restore with measured RPO/RTO and reconciled task/outbox/receipt ledgers was evidenced. |
| W-043 | Alert routes deliver actionable incident alerts | UNKNOWN | No alert delivery/fallback drill or current operational owner evidence collected. |
| W-044 | Policy updates/revocation invalidate stale cache | BLOCKED | No end-to-end policy version/revocation propagation test evidence established. |
| W-045 | External outcome reconciled before retry/compensation | PARTIAL | Reconciler interface and focused ambiguity tests exist; no external adapter state reconciliation exercise was evidenced. |

### Agent and phase readiness

The registry diagnostic in run #4591 reported `153` agents, all disabled by default and production authorization not granted. This is not a failed safety control by itself; it is evidence that the project currently operates in a guarded/reference posture. Every agent must remain `SPEC_ONLY`, `DISABLED`, or `BLOCKED` until its specific contract, handler, permissions, tests, and evidence pass. Do not infer that an agent is operational because its name appears in a registry or document.

## 5. Cross-cutting controls audit

| Requirement domain | Preliminary disposition | Reason |
|---|---|---|
| Scope, authority, and release governance | PARTIAL | Governance docs and RX-19 decision boundary exist; current candidate has no release receipt and is not certified. |
| Versioned contracts and bounds | IMPLEMENTED_UNVERIFIED | Pydantic contracts and focused tests exist; canonical CI is failing. |
| Durable state and event transport | IMPLEMENTED_UNVERIFIED / PARTIAL | PostgreSQL/Redis implementation exists; real fault-injection and recovery evidence is incomplete. |
| Agent execution and external actions | BLOCKED | Reference worker does not dispatch agents; all agents disabled by default. |
| Execution isolation | BLOCKED | Static AST arbiter explicitly is not a sandbox; no qualifying production isolation evidence was collected. |
| Human approval and permit enforcement | PARTIAL / BLOCKED | Schemas and boundaries exist; complete authenticated point-of-effect enforcement is not demonstrated. |
| Secret management | DISABLED | Default disabled; no production credential retrieval authorized or evidenced. |
| Memory/vector retrieval | BLOCKED | Optional Qdrant service is not proof of authorization-aware retrieval integration. |
| Observability | PARTIAL | Code/configuration exists; production coverage and alert/recovery drills absent from evidence packet. |
| Supply-chain integrity | BLOCKED | CI pins several workflow actions and runs dependency checks, but `requirements.txt` uses version ranges without hashes; Dockerfile uses `python:3.12-slim-bookworm` without an immutable digest, and Compose uses tagged PostgreSQL/Redis/Qdrant images rather than digest-pinned images. The Dockerfile itself states these are pre-production hardening tasks. No accepted release artifact/provenance bundle for this candidate is established. |
| Reliability/recovery | BLOCKED | No witnessed production-like chaos, restore, RPO/RTO, or rollback drill. |
| Performance/SLO | BLOCKED | Queue <500 ms and worker 30 s are proposed targets; no benchmark with workload profile, p95/p99, sample size, or capacity model was established. |
| Independent security assurance | BLOCKED | No independent security review bound to the exact candidate and closed findings ledger was established. |
| Production certification | BLOCKED | Required evidence set is incomplete and exact-head CI has a failed stage. |

## 6. Mandatory remediation order

Do not enable more agents or protected effects before these prerequisites are met.

1. **R-001 — Diagnose canonical CI redaction failure.** Retrieve the runner's complete redaction-stage report and identify the exact offending path/rule/input. Fix the underlying defect or correct a demonstrably false-positive rule with regression coverage. Do not bypass the check. Re-run all required jobs on the new exact SHA.
2. **R-002 — Complete exact-head CI.** The documentation-only scanner false-positive correction is in candidate `bf5849a9b73788e1f5fb9c1ecb176b0a2b672b14`; run #4594 was still in progress at the latest observation. Require all mandatory steps/jobs to finish successfully; inspect skipped jobs, warnings, artifact generation and step conclusions. Any new commit resets candidate-specific evidence.
3. **R-003 — Close supply-chain reproducibility gaps.** Generate and review a hash-locked dependency file for the supported runtime, pin all production base images by immutable digest, and verify the actual built artifact's provenance and subject digest. Keep version-range requirements for development only if the production build consumes the approved lockfile.
4. **R-004 — Prove contract-to-runtime wiring.** Add integration tests for ingress, registry, durable state/outbox, Redis delivery, worker validation, durable terminal state and ACK order.
5. **R-005 — Keep reference worker fail-closed until execution isolation is real.** Choose and implement an OS/container/VM isolation profile with no inherited secrets, restricted egress, filesystem, process, syscall and resource boundaries. AST screening is supplemental.
6. **R-006 — Prove point-of-effect authorization.** Wire cryptographic permit validation and human approval receipt checks into every protected adapter call. Test expiry, revocation, replay, wrong candidate/action/resource, concurrent claims, and policy outage.
7. **R-007 — Exercise crash consistency and external ambiguity.** Fault-inject every critical point from the outbox through effect, receipt and ACK; prove dedupe/reconciliation and Saga compensation without duplicate or unauthorized effects.
8. **R-008 — Validate operations.** Run isolated restore and rollback drills; measure approved RPO/RTO, alert delivery, telemetry loss, queue latency, p95/p99 and resource/cost ceilings.
9. **R-009 — Obtain independent review.** A qualified reviewer not responsible for implementing the reviewed control must inspect the exact SHA, execute agreed adversarial tests, and track findings to verified remediation.
10. **R-010 — Assemble certification evidence packet.** Bind code SHA/tree, workflow IDs and latest attempts, test outputs, artifact/provenance digests, environment/configuration, security review, operational drills, exceptions and human acceptance into a canonical evidence digest.
11. **R-011 — Obtain release decision.** RX-19 reviews the complete packet and records approve/reject/defer for the same candidate and digest. No release before this decision.

## 7. Certification dossier requirements

A formal conformity certificate may only be issued after all of the following are available and independently reviewed:

- Certification scope, intended use, excluded use, system boundary, data classes, threat model, and environment.
- A controlled standards register mapping each requirement to an exact control ID and acceptance criterion.
- Completed requirement-to-code-to-test-to-evidence traceability, including all 45 wires and each enabled agent/adapter.
- Complete exact-head CI evidence with latest run attempts and required jobs passed; raw logs and artifact hashes retained.
- Test report covering unit, integration, end-to-end, adversarial, fault-injection, performance, recovery and regression layers.
- Software bill of materials, dependency/security scan results, artifact digest, build provenance/attestation and independent verification results.
- Deployment configuration, access/identity proof, isolation evidence, secret handling, network policy, and data retention/deletion proof.
- Operational evidence: monitoring/alert drills, backup restore, measured RPO/RTO, rollback, incident response, load/capacity test and observed SLOs.
- Independent reviewer identity, qualification, independence declaration, exact SHA reviewed, findings, remediation and retest results.
- Explicit exceptions with owner, risk acceptance authority, compensating control and expiry; no unapproved critical/high-risk exception.
- Human acceptance bound to candidate SHA and canonical evidence digest.
- RX-19's authenticated final decision bound to the same candidate and digest.

A certificate must identify issuer, scope, candidate SHA/tree, environment, standards version, evidence digest, date, expiry/reassessment triggers, exclusions, unresolved residual risks, and revocation process. It must not imply legal accreditation or third-party certification unless such authority actually exists.

## 8. Certificate status record

| Field | Current value |
|---|---|
| Certification status | **NOT ISSUED** |
| Conformity claim | None |
| Historical audit candidate | `925f9028b151c14485ebff999d3d3a0853e44005` (not the current documentation branch head) |
| CI | Historical candidate's canonical validation stage failed at redaction. The current documentation branch has a separate documentation-conformance gate; its latest exact-head result must be checked independently. |
| Runtime execution | Reference worker blocks dispatch; agents disabled by default |
| Independent review | Not evidenced for this candidate |
| Operational drills | Not evidenced |
| Human acceptance | Not evidenced |
| RX-19 release decision | Not evidenced |
| Production authorization | **NOT GRANTED** |
| Next decision | Reassess after R-001 and R-002, then proceed through remaining gates |

## 9. Reassessment and change control

This audit is a snapshot, not a permanent guarantee. Reassess after any change to source, contracts, policy, agent registry, dependencies, CI workflow, Docker image, infrastructure, permit trust roots, data classification, or operational configuration. New candidate SHA means candidate-specific CI, review, test, and acceptance evidence must be rebound or regenerated. A previously green run cannot override a later failed/in-progress attempt for the same workflow run ID.

## 10. Primary guidance consulted

- NIST AI RMF Generative AI Profile: <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>
- NIST Secure Software Development Framework: <https://csrc.nist.gov/pubs/sp/800/218/final>
- OWASP Top 10 for Agentic Applications 2026: <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>
- SLSA v1.2 provenance: <https://slsa.dev/spec/v1.2/provenance>
- GitHub artifact attestations: <https://docs.github.com/en/actions/concepts/security/artifact-attestations>
- Redis Streams: <https://redis.io/docs/latest/develop/data-types/stream/>
- PostgreSQL backup/recovery: <https://www.postgresql.org/docs/current/backup.html>
- OpenTelemetry signals: <https://opentelemetry.io/docs/concepts/signals/>

These references guide assessment design; they do not certify AIGC.


## 11. Documentation governance and operator-accountability controls

The following controls were added after the historical candidate snapshot above. Their presence in source is not evidence that the current candidate's CI completed successfully.

| Control | Requirement | Implementation/evidence status | Acceptance condition |
|---|---|---|---|
| DOC-001 | Required master documents are present and readable | Implemented candidate: `scripts/enforce_master_docs.py`; exact-head workflow verification pending | Required-document check passes on exact candidate; missing or unreadable files fail closed |
| DOC-002 | Wiring registry contains the expected 45 unique IDs W-001–W-045 | Implemented candidate: deterministic registry parser | All expected IDs present exactly once; any missing, duplicate, or unexpected ID fails |
| DOC-003 | Audit keeps explicit NOT CERTIFIED / BLOCKED status until evidence gates pass | Implemented candidate: structural invariant in DOC-GATE-01 | A status downgrade or unsupported certification claim fails the documentation gate |
| DOC-004 | Local Markdown links in required documents resolve within the repository | Implemented candidate: local-link checker | All checked local links resolve and none escape repository root |
| OPS-001 | Operator responsibility is task-specific, informed, and auditable | Draft policy: `AIGC_OPERATOR_RESPONSIBILITY_AND_AUTHORIZED_USE_ACKNOWLEDGMENT.md` | Qualified legal review, appropriate notice, valid assent workflow, and tested linkage to actual authorization records |
| GOV-001 | Documentation and evidence gates are not permitted to self-approve or release | Role specification: `AIGC_DOCUMENTATION_GOVERNANCE_AND_ENFORCEMENT_AGENTS.md` | Workflow permissions, code, tests, and branch rules demonstrate the stated authority boundary |
| AUTH-001 | Consequential actions require authenticated, scoped, unexpired human authorization bound to the exact payload | Specification only until point-of-effect enforcement is proven | Negative tests demonstrate denial on missing identity, expired permit, changed payload, wrong target, and missing approval |

### Documentation gate current disposition

DOC-GATE-01 is a deterministic structural validator invoked by the AIGC CI workflow and covered by focused unit tests in the current branch. It is **IMPLEMENTED_UNVERIFIED** until the latest candidate's workflow completes successfully and its step output confirms both the validator and tests passed. A green documentation gate only establishes the checked structural invariants; it does not establish legal enforceability, runtime conformance, security, or production readiness.

The operator acknowledgment is a draft and must not be described as a binding blanket liability waiver. It assigns accountability for an operator's own decisions and approvals only to the extent permitted by applicable law, preserves non-waivable rights and duties, and requires qualified counsel to review it before adoption.

Any future audit must record the exact candidate SHA, workflow run and attempt, the DOC-GATE-01 output, test output, and evidence digest. Do not hard-code a self-referential candidate SHA into the document that changes that SHA.


## 12. Follow-up runtime authorization audit — candidate implementation

### Finding: mutable payload TOCTOU across asynchronous permit verification

**Risk:** A frozen `SagaStep` dataclass can still hold mutable dictionaries. If a caller changes a nested payload while the permit verifier is awaited, the coordinator could authorize a digest of one payload and pass a different payload to an adapter. A permit checked only during preflight may also expire or be revoked before the actual effect or a retry.

**Corrective candidate changes:** `core/orchestrator.py` now snapshots payloads through canonical JSON before the first awaited authorization check, rejects invalid canonical JSON/Unicode and payloads larger than 1,000,000 UTF-8 bytes, rechecks permits before each forward adapter attempt, binds compensation authorization to both the original and compensation payload digests, and rechecks compensation permits before each compensation attempt. Point-of-effect denial is represented as a blocked step rather than falsely asserting that the denied step's effect may have occurred. Regression tests were added to `tests/test_aigc_core_runtime.py`.

**Evidence status:** `IMPLEMENTED_UNVERIFIED`. These changes require successful exact-head CI, review of the complete authorization-verifier implementation and its cryptographic trust roots, and integration tests proving that denial prevents adapter invocation. The test design is present in source; it is not yet a passing test result.

**Residual risks:** Static code inspection is not runtime isolation. A trusted adapter can still be defective or compromised; it must validate target/resource scope and must not leak credentials. A timeout after an adapter call remains an ambiguous external outcome and requires trusted read-after-write reconciliation. Compensation is another external effect and can fail; the system must preserve a manual-reconciliation state rather than claim rollback success.

### Current candidate and CI claim policy

The branch advances as follow-up commits are made; therefore a workflow run against an earlier SHA is not evidence for the current branch head. The candidate must be re-read from GitHub immediately before reporting status. No production certification or release decision may be inferred from the presence of these changes.
