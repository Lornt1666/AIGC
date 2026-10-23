# AIGC Verification and Production Acceptance Plan

**Version:** 1.0.0-draft  
**Status:** Required test plan; not evidence that tests have passed.  
**Release posture:** BLOCKED until all applicable gates are independently evidenced.

## 1. Verification principles

- Test observable behavior, not intention or documentation alone.
- Bind test evidence to the exact commit, configuration, dependencies, image digest, and policy version.
- Include positive, negative, boundary, concurrency, fault-injection, recovery, and adversarial cases.
- Distinguish test failure from unavailable test, skipped test, flaky test, and not-yet-implemented behavior.
- Do not use a successful unit test to claim integration, security, load, or disaster recovery success.
- Never accept a producer's `passed=true` field without verifying source and evidence.

## 2. Test layers

### L0 — static and repository checks
- syntax, import graph, lint/type checks where configured;
- secret scanning;
- dependency lock consistency and vulnerability scanning;
- container/Compose/Terraform manifest validation;
- workflow action SHA pinning and image digest checks;
- schema and migration consistency.

### L1 — unit tests
- contract bounds, enum/state transition rules, canonical serialization and digesting;
- idempotency key conflict behavior;
- retry/deadline/budget calculations;
- AST arbiter limits and documented detections;
- permit decision logic and receipt verification;
- artifact manifest/archive validation;
- redaction and data classification.

### L2 — component integration
- ingress → contract validator → registry → state store;
- state/outbox transaction → publisher → Redis Streams;
- consumer → worker → durable result → acknowledgement;
- secret broker → fake provider and policy decisions;
- phase registry → CLI command and schema;
- memory metadata → retrieval filter;
- telemetry propagation through API/coordinator/worker/adapter.

### L3 — end-to-end staging
- synthetic pipeline across approved phases;
- read-only public data replay;
- approval packet created, denied, revised, expired, and approved in tests;
- approved action remains limited to exact payload/target/scope;
- no action occurs from pending, denied, expired, or modified packet;
- emergency stop blocks new effects;
- closure packet bound to exact SHA and digest.

### L4 — security/adversarial
- prompt injection in documents, feed content, tool output, and memory;
- spoofed producer identity, forged permit, wrong audience, wrong action/resource, revoked/expired permit;
- replay and concurrent duplicate receipt claims;
- malicious or oversized payloads, deep nesting, invalid UTF-8/surrogates, archive traversal, symlinks, unexpected files;
- SSRF/egress attempts, path traversal, shell injection, dynamic imports and execution;
- secret leakage into logs, prompts, artifacts, exception text, and telemetry;
- privilege escalation, confused deputy, agent self-approval, and disabled-agent dispatch;
- artifact digest tampering, wrong signer, wrong workflow, wrong candidate SHA;
- evidence pagination omission and stale CI attempt.

### L5 — reliability and chaos
- crash after DB commit but before publish;
- publish success followed by crash before local acknowledgement;
- duplicate message delivered to two workers;
- worker crash before and after external effect;
- Redis outage, reconnect, pending reclaim, and stream retention/trimming;
- PostgreSQL failover or connection interruption;
- provider timeout, rate limiting, malformed response, and circuit breaker;
- DLQ poison message and controlled replay;
- Saga compensation failure and external outcome ambiguity;
- emergency stop during queued, running, and reconciling states.

### L6 — performance
- define workload, concurrency, payload sizes, provider, hardware, and duration;
- measure p50/p95/p99 latency, queue wait, throughput, error rate, memory/CPU, DB connections, queue growth, and provider cost;
- validate queue latency target (<500 ms) only against a declared load profile;
- validate default per-agent timeout (30 s) and hop cap (10) using boundary tests;
- prove load shedding and budget enforcement before resource exhaustion;
- record variance, sample size, and bottlenecks.

### L7 — recovery and operations
- restore backup into isolated environment;
- reconcile schema migrations, tasks, outbox, idempotency claims, and audit ledger;
- test RPO/RTO against explicitly approved targets;
- test alert delivery and escalation;
- execute runbook during a timed drill;
- verify rollback to a prior immutable artifact and schema-compatible state.

## 3. Mandatory negative tests

| Test | Stimulus | Required result |
|---|---|---|
| T-001 | Unknown agent/phase ID | Reject; no dynamic import or dispatch |
| T-002 | Disabled/spec-only agent | Reject scheduling |
| T-003 | Payload exceeds byte or nesting limit | Deterministic reject before expensive work |
| T-004 | Unknown major schema version | Reject and record reason |
| T-005 | Hop count exceeds limit | Stop chain; no child work |
| T-006 | Deadline or permit expired | Block new protected effect |
| T-007 | Policy source unavailable | Fail closed for protected actions |
| T-008 | Same idempotency key, same digest | Return prior state/result or safely resume |
| T-009 | Same idempotency key, different digest | Conflict; no effect |
| T-010 | Concurrent duplicate claims | One logical effect at most |
| T-011 | Worker crashes after effect, before ACK | Redelivery reconciles; no duplicate effect |
| T-012 | Newer CI attempt fails after older pass | Closure blocked |
| T-013 | Conflicting records for same CI attempt | Closure blocked |
| T-014 | Artifact digest or subject mismatch | Reject artifact |
| T-015 | Provenance signer/builder not trusted | Reject provenance |
| T-016 | Candidate SHA changes during closure | Discard digest and restart |
| T-017 | Human approval binds old payload | Reject changed payload |
| T-018 | Prompt injection asks agent to disclose secret | No secret retrieval/disclosure |
| T-019 | Secret-like value appears in log output | Redaction test fails build |
| T-020 | DLQ message replayed without approval | Reject replay |
| T-021 | Restore omits an outbox or receipt claim | Recovery gate fails |
| T-022 | Telemetry source is stale/unavailable | Show unknown/degraded, never green |
| T-023 | Emergency stop is active | No new protected effect |
| T-024 | Static AST passes but execution permit absent | No code execution |
| T-025 | Unknown external outcome | RECONCILING/NEEDS_OPERATOR, not blind retry |
| T-026 | Disabled external adapter | Request fails closed without network access |

## 4. Fault injection matrix

For each injected fault, record:
- exact SHA/config;
- precondition and injection point;
- task/message/operation IDs;
- expected state;
- observed state;
- side-effect count;
- durable record count;
- recovery time;
- logs/trace/metrics;
- pass/fail and reviewer.

Required crash points:
1. before database transaction;
2. after state write but before transaction commit;
3. after commit before outbox publish;
4. after publish before publisher checkpoint;
5. after message delivery before worker start;
6. after idempotency claim;
7. before external effect;
8. during external effect;
9. after external effect before receipt commit;
10. after receipt commit before Redis ACK;
11. during compensation;
12. during candidate evidence acquisition;
13. after candidate readback but before final decision;
14. during backup restore/reconciliation.

A test passes only if the final state is explainable, no unauthorized or duplicate effect occurred, durable evidence is consistent, and operator escalation is explicit when reconciliation cannot decide safely.

## 5. Evidence acceptance model

Each evidence item must capture:
- source system and authenticated identity;
- observation timestamp and retrieval method;
- raw source reference or retained raw bytes where permitted;
- content digest;
- candidate SHA/config/policy version;
- run ID and attempt if CI-related;
- artifact subject and digest if artifact-related;
- verifier identity and version;
- result and structured failure reason;
- completeness/pagination status;
- expiry/revocation state where relevant.

Evidence lifecycle:
1. **Observed** — read from named source.
2. **Integrity checked** — bytes/digest match.
3. **Authenticated** — source/issuer identity is trusted.
4. **Authorized** — source and action are within policy.
5. **Candidate bound** — exact SHA/run/attempt/subject match.
6. **Fresh and complete** — latest attempts/pages captured; candidate re-read.
7. **Independently evaluated** — acceptance policy checks evidence rather than trusting producer claims.

## 6. Production closure gates

| Gate | Requirement | Pass evidence | Block conditions |
|---|---|---|---|
| G0 Candidate | Live PR/head/base and final re-read | Timestamped source response and SHA match | Changed or unavailable head/base |
| G1 CI | All required jobs pass on exact head and latest attempts | Workflow/run/attempt/job/log records | Missing, queued, failed, stale, conflicting job |
| G2 Artifact | Bytes, manifest, digest, subject and safe archive validated | Verification output and hashes | Mismatch, missing manifest, unsafe path |
| G3 Repository protection | Effective rulesets/protection verified | Authorized readback | Inaccessible or missing required protection |
| G4 Independent security review | Qualified reviewer; findings closed and retested | Reviewer identity, exact SHA, finding evidence | No reviewer, self-review, unresolved blocking finding |
| G5 Supply chain | Lockfile, SBOM, vulnerability policy, trusted provenance | Digests, scan output, verified attestation | Mutable/untrusted build input or unverifiable provenance |
| G6 Runtime security | Permits, isolation, secret boundaries, egress controls | Negative tests and config evidence | Arbitrary execution, missing permit enforcement, secret leak |
| G7 Reliability | Outbox, idempotency, queue recovery, Saga tests | Fault-injection report | Duplicate/lost effect, unbounded retries, ambiguous state ignored |
| G8 Operations | Telemetry, alerts, backup restore, RPO/RTO | Drill and dashboard/alert evidence | Untested restore or silent critical failure |
| G9 Human acceptance | Authenticated acceptance tied to candidate/digest | Signed or otherwise authenticated receipt | Stale or ambiguous approval |
| G10 RX-19 decision | Final authorized decision for same candidate/digest | Authenticated decision receipt | Missing, invalid, or mismatched receipt |

All applicable gates must pass. A gate can be waived only through an explicit, authenticated, policy-compliant risk acceptance by the authorized role; no agent can waive its own blocker. Critical security gates must not be waived merely to release.

## 7. Candidate freshness rules

- Capture all pages of run/review/artifact inventories or mark evidence incomplete.
- Group CI attempts by workflow run ID and evaluate the highest observed attempt.
- A later failed, cancelled, queued, or in-progress attempt invalidates an earlier success.
- Conflicting records for the same attempt block.
- Artifact must correspond to the eligible successful run attempt and expected artifact subject.
- Re-read PR head/base and policy/trust state after verification.
- If anything changes, recalculate all dependent evidence and the canonical digest.
- Never call a run “passed” until the workflow reaches a terminal successful state and every required job is successful.

## 8. Performance and SLO reporting template

Every reported latency/throughput result must include:
- candidate SHA and config digest;
- host/container specs;
- dependency versions;
- test duration and warm-up;
- offered request rate and concurrency;
- payload distribution and workload mix;
- provider and model if applicable;
- p50/p95/p99, throughput, error rate, saturation, and cost;
- sample size and confidence/variance;
- test commands and raw results.

Targets in the prompt (queue latency <500 ms, agent processing timeout <30 s, maximum hops 10) are initial policy candidates. They are not achieved SLOs until measured under a defined workload and approved.

## 9. Required deliverables for each production candidate

- master spec, wiring registry, and runbook reconciled to implementation;
- current component/agent inventory with explicit status;
- schema registry and compatibility policy;
- threat model and FMEA;
- CI results and test logs;
- dependency lock, SBOM, vulnerability report, image digests, provenance verification;
- independent review report and finding closure;
- fault-injection and recovery report;
- telemetry coverage and alert test;
- backup restore report with RPO/RTO;
- effective repository protection evidence;
- human acceptance;
- RX-19 decision receipt;
- canonical evidence digest and post-check candidate SHA.

## 10. References

- NIST AI RMF Generative AI Profile: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- NIST SSDF SP 800-218: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- SLSA provenance: https://slsa.dev/spec/v1.2/provenance
- GitHub artifact attestations: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- Redis Streams: https://redis.io/docs/latest/develop/data-types/stream/
- PostgreSQL backup/restore: https://www.postgresql.org/docs/current/backup.html
- OpenTelemetry signals: https://opentelemetry.io/docs/concepts/signals/


## 11. CI run verification protocol (normative)

This section defines how a reviewer establishes what a GitHub Actions run proves. It does not equate a green badge with production readiness.

### 11.1 Identity tuple — required before interpreting results

Record the complete tuple below in the evidence record:

- repository full name;
- pull request number, state, draft flag, base branch and base SHA;
- current PR **head SHA** and the relevant merge SHA if the event created one;
- workflow name and workflow file revision;
- workflow run ID and run number;
- run attempt number (reruns are distinct attempts of a run);
- triggering event and actor;
- run status and terminal conclusion;
- each required job's name, job ID, status, conclusion and relevant step results;
- tested source SHA and Git tree SHA emitted by the workflow;
- artifact name, artifact ID, digest/subject, and producing run/attempt if artifacts are used;
- UTC retrieval timestamp and source URL/API response evidence.

Use immutable SHA values as identities. Branch names, PR numbers, workflow names, green badges, and run numbers alone are not sufficient candidate identifiers.

### 11.2 Authoritative verification sequence

1. **Resolve the current candidate.** Read the live PR and record its current head SHA and base SHA. Do not use a SHA copied from an earlier report.
2. **Find the run for that candidate.** Query the workflow-run inventory filtered by `head_sha` where supported, but do not assume the run-level `head_sha` equals the PR branch head for a `pull_request` event: GitHub can report a synthetic PR merge commit there. Inspect `pull_requests[].head.sha` and `pull_requests[].base.sha` in the run payload and compare the PR head to the live PR head. Then inspect the workflow's emitted `observed_head_sha` and tested tree SHA; for this AIGC workflow, `REQUESTED_REVISION` is configured from `github.event.pull_request.head.sha`, so the observed checkout must equal that exact PR head. Record any merge SHA separately.
3. **Check event and workflow identity.** Confirm the run was triggered by the intended event and executed the expected workflow definition. A similarly named workflow, a manual run against a branch name, a fork run with different permissions, or an unrelated green workflow does not substitute.
4. **Check the terminal state.** `status=completed` and `conclusion=success` are necessary for a workflow-pass claim. `pending`, `queued`, `in_progress`, `waiting`, or `requested` means no conclusion yet. `cancelled`, `failure`, `timed_out`, `action_required`, or a missing required run is not a pass. Do not infer a pass from green steps inside an incomplete or failed workflow.
5. **Inspect every required job.** Fetch the complete job inventory, not just the summary card. Confirm all policy-required jobs have terminal successful conclusions. A skipped job is acceptable only when the workflow's explicit policy proves that the skip is intentional and the gate is not required for this candidate. Investigate any job omitted from the returned page; paginate if the API reports additional pages.
6. **Inspect failing, skipped and non-authoritative steps.** Read the logs for failed jobs and any diagnostic step marked non-authoritative. A diagnostic step that runs with `if: always()` and exits zero must not hide a preceding authoritative failure. Check test counts and commands against the declared test plan; partial focused tests do not override later failures.
7. **Verify the tested checkout.** Require an exact checkout/identity step or equivalent evidence. Compare the workflow's observed commit SHA and Git tree SHA to the intended candidate. A run for a prior SHA is stale even if it is successful. A documentation-only change still creates a new commit and must receive the required candidate-specific validation.
8. **Verify artifacts and attestations where required.** Match artifact ID/name, digest, subject, producing run and attempt, source SHA, workflow identity and repository. Downloaded test reports are evidence only for the run that produced them. Verify signed provenance using the repository's policy; provenance establishes origin/build claims, not that the code is safe.
9. **Check required repository controls.** Inspect effective branch protection/rulesets, required status checks, required reviewers, and bypass permissions where access allows. A passing workflow is not proof that merge protections are configured or enforced. If protection settings cannot be inspected, record that as unknown rather than assuming they exist.
10. **Re-read candidate and evidence after inspection.** Refresh the PR head SHA and relevant check inventory. If the head changed, the evidence is stale for the new candidate. If any check is still pending or a newer attempt exists, do not make a final pass claim.
11. **Record disposition.** Use only one of: `PASS_FOR_DECLARED_CI_SCOPE`, `FAIL`, `PENDING`, `CANCELLED`, `STALE_SHA`, `INCOMPLETE_EVIDENCE`, or `NOT_APPLICABLE_WITH_POLICY_BASIS`. State the exact scope; never translate CI success into `PRODUCTION_READY` without separate release gates.

### 11.3 Reruns, concurrency cancellation and stale evidence

- A run ID can have more than one attempt. Record the attempt inspected and examine the latest attempt. A successful earlier attempt does not supersede a later failed attempt for the same release evidence.
- A new push changes the candidate SHA. If concurrency uses `cancel-in-progress: true`, a cancelled older PR run may be expected operational behavior, but it remains cancelled—not passed. Verify that a non-cancelled run completed for the new head.
- Rapid commits can repeatedly cancel runs and consume CI capacity without producing usable evidence. Batch related fixes, wait for the current candidate's authoritative workflow to complete, then make a single correction commit when possible.
- Do not manually re-run a failed job and claim the entire workflow passed unless the resulting attempt includes all required dependent jobs and the workflow's overall conclusion is successful.
- A successful run on the PR merge ref may include the base branch in addition to the PR head. Record both the PR head SHA and tested merge/checkout SHA; define which is required by the branch policy. For release-candidate claims, independently validate the final commit that will actually be released.
- A run started before a force-push, policy change, workflow change, dependency update, or relevant configuration change must be re-evaluated. If its tested source/policy does not represent the final candidate, mark it stale.

### 11.4 Suggested read-only GitHub CLI checks

Run from an authenticated terminal with the GitHub CLI installed. Replace the example values with the live repository, PR number and SHA.

```bash
set -euo pipefail
REPO="Lornt1666/AIGC"
PR="336"

# Candidate identity: head/base, state and draft status.
gh pr view "$PR" --repo "$REPO" \
  --json number,state,isDraft,headRefName,headRefOid,baseRefName,baseRefOid,url

# List recent runs; identify the one whose headSha exactly matches headRefOid.
gh run list --repo "$REPO" --limit 30 \
  --json databaseId,number,workflowName,headSha,event,status,conclusion,attempt,createdAt,url

# After selecting a run ID, inspect summary and all job conclusions.
RUN_ID="<verified-run-id>"
gh run view "$RUN_ID" --repo "$REPO" \
  --json databaseId,number,workflowName,headSha,event,status,conclusion,attempt,createdAt,updatedAt,url,jobs

# Download logs only after recording the run ID and attempt.
gh run view "$RUN_ID" --repo "$REPO" --log

# Inspect current required status checks / ruleset separately, subject to permissions.
gh api "repos/$REPO/commits/<candidate-sha>/check-runs?per_page=100"
gh api "repos/$REPO/commits/<candidate-sha>/status"
```

These are inspection examples, not proof that they were executed. If the CLI/API response is truncated or paginated, retrieve all pages and retain the raw responses in the evidence package. Do not print tokens or secrets in logs.

### 11.5 Required evidence receipt schema

For each assessed run, store a JSON or equivalent structured record with at least:

```json
{
  "schema_version": "1.0",
  "repository": "Lornt1666/AIGC",
  "pull_request": 336,
  "candidate_head_sha": "<40-hex-sha>",
  "candidate_base_sha": "<40-hex-sha>",
  "workflow": "AIGC CI",
  "workflow_file_sha": "<sha>",
  "run_id": "<numeric-id>",
  "run_number": "<number>",
  "run_attempt": 1,
  "event": "pull_request",
  "tested_head_sha": "<40-hex-sha>",
  "tested_tree_sha": "<tree-sha>",
  "status": "completed",
  "conclusion": "success",
  "required_jobs": [
    {"name": "<required-job>", "id": "<job-id>", "status": "completed", "conclusion": "success"}
  ],
  "artifacts": [],
  "retrieved_at_utc": "<ISO-8601 timestamp>",
  "evidence_urls": [],
  "disposition": "PASS_FOR_DECLARED_CI_SCOPE",
  "limitations": ["CI success is not production certification"]
}
```

The schema above is a template. Literal placeholders must be replaced with observed evidence before the receipt is accepted; a self-reported JSON receipt is not authoritative unless its source, integrity and candidate binding are verified.

### 11.6 AIGC-specific interpretation

The currently inspected workflow `.github/workflows/aigc-ci.yml` declares pull-request validation, exact requested checkout, Python dependency and vulnerability checks, runtime/registry tests, master-document conformance, and the shared exact-SHA validation runner. Review the actual workflow at the candidate SHA because the set of required steps can change.

At the most recent inspection during this assessment, PR #336 remained open and draft. The run for the then-current PR head `71e68d470f60f3d4324224a1941ea408b3cac296` was #4620, reported as `pending`; its run-level `head_sha` was `9038e046f330af1a9f1f06c5f38dade2ed262d04`, the PR merge commit, while `pull_requests[].head.sha` correctly identified the branch candidate. The preceding runs were cancelled as the head changed. No pass is established by those observations. Re-query the live PR head, the run payload's PR head, and the tested-checkout evidence before using this snapshot; it is time-sensitive.

Even a later successful run would establish only the workflow's declared CI scope. It would not, by itself, establish secure sandbox isolation, successful disaster recovery, production SLO attainment, legal compliance, independent security review, human acceptance, or RX-19 release authorization.

### 11.7 Research basis

- GitHub Actions workflow-run API: run identity, statuses/conclusions, filtering by head SHA, attempts, logs and reruns: https://docs.github.com/en/rest/actions/workflow-runs
- GitHub Actions workflow-job API: job inventory and logs: https://docs.github.com/en/rest/actions/workflow-jobs
- GitHub artifact attestations: provenance verification and explicit warning that attestations are not a guarantee of artifact security: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- NIST SP 800-218 (SSDF): secure development and release practices: https://csrc.nist.gov/pubs/sp/800/218/final

