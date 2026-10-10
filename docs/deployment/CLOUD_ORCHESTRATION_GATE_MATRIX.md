# AIGC Cloud Orchestration: Release Gate Matrix

**Status:** planning and evidence coordination only. This document does not provision infrastructure, grant agent permissions, authorize external business actions, or enable public traffic.

## Operating rule

Orchestrate work by explicit capability, least privilege, observable evidence, and reversible stages. “Agent activation” means only agents explicitly configured and authorized in a verified environment. Never infer cloud credentials, agent availability, human approval, or deployment success from repository state. Keep business-cycle execution and external write connectors disabled until separately authorized.

## Current verified snapshot (2026-10-10)

| Workstream | Evidence | State | Required next action |
|---|---|---|---|
| Artifact reference contract | [PR #292](https://github.com/Lornt1666/AIGC/pull/292), head `2122bb99bf15666754db0acebd7337d8c1c7fcdb`; [CI run #3467](https://github.com/Lornt1666/AIGC/actions/runs/38089456669) succeeded | Open; mergeable; independent review absent | Obtain independent review; re-check head SHA and required checks immediately before merge |
| Durable run/review state | [Issue #282](https://github.com/Lornt1666/AIGC/issues/282); `src/webapp/command_center_store.py` has PostgreSQL and in-memory implementations | Open; app-level `RUNS`/locks and recovery acceptance still require verification | Verify transaction/idempotency/restart behavior across two app instances on an exact candidate revision |
| Durable authorization packets and phase evidence | [Issue #290](https://github.com/Lornt1666/AIGC/issues/290); `src/core/operator_cockpit.py` currently loads authorization packets and work-order records from local JSON paths | Open; local adapter in #292 does not close this gap | Implement private versioned S3 plus authoritative PostgreSQL metadata behind the artifact-store contract; route all packet/work-order/phase-evidence paths through it and fail closed in production |
| Emergency-stop and reconciliation audit | [PR #287](https://github.com/Lornt1666/AIGC/pull/287) | Draft; stale base; mergeable false | Rebuild/rebase against current main without overwriting #288 TLS/idempotency safeguards; run exact-head CI and review |
| Unknown review-decision reconciliation | [Issue #289](https://github.com/Lornt1666/AIGC/issues/289) | Open; no versioned human-only reconciliation path verified | Add compare-and-set versioning, exact action ID, expected version, confirmation phrase, operator identity, evidence reference, and audit trail; never auto-replay an unknown decision |
| Authentication and public-deployment hardening | [Issue #275](https://github.com/Lornt1666/AIGC/issues/275) | Open; public traffic prohibited | Complete browser identity/session and protected-route tests, rate/concurrency limits, timeouts, redaction, container/dependency hardening |
| AWS account and infrastructure | [AWS ECS/Fargate runbook](AWS_ECS_FARGATE.md) | Runbook only; no verified AWS provisioning connection or live endpoint | Confirm account/region/owner/budget through authorized AWS session; provision isolated staging only after gates and approval |
| Live deployment evidence | No verified ECR digest, ECS service revision, endpoint, or deployment receipt available in this audit | Not deployed/verified | Build once from exact SHA, scan, deploy by immutable digest, verify HTTPS/auth/readiness/restart/recovery, capture receipt |

## Ordered orchestration plan

**Audit update (2026-10-10):** A fresh source review confirmed that `src/webapp/command_center_store.py` defines both PostgreSQL and `MemoryCommandCenterStore` (`durable = False`), while `src/core/operator_cockpit.py` still declares local JSON packet/work-order paths. The database ledger alone is not evidence that those artifacts or Phase 5/6/7/closure evidence are shared across tasks. Issue #289 additionally tracks the missing human-only, versioned reconciliation path for uncertain review decisions. These are release blockers, not implied runtime capabilities.

### Gate A — repository integrity
1. Confirm the candidate branch SHA, base SHA, changed-file list, and mergeability.
2. Require passing CI for the exact head; stale CI is not evidence for a later commit.
3. Obtain independent review for security-sensitive changes.
4. Do not merge a stale/conflicted branch. Reconcile changes and re-run tests rather than force-merging.

### Gate B — shared durable state
1. Preserve PostgreSQL TLS verification, durable run/review state, actor-scoped idempotency, unknown-outcome reconciliation, and emergency-stop semantics.
2. Implement immutable artifact objects in a private, versioned, encrypted S3 bucket; keep authoritative metadata, digest, provenance, ownership, status, and version references in PostgreSQL/RDS.
3. Route authorization packets, work orders, and phase evidence through the artifact-store interface. Local filesystem storage is development/test-only.
4. Fail closed for missing objects, wrong digest/reference, stale writes, denied access, unavailable dependencies, expired or stale approvals, and missing production configuration.
5. Test independent app/worker instances, restart/task replacement, duplicate operations, concurrency, outage/denial, migrations, provenance, and human-approval freshness.

### Gate C — identity and execution controls
1. Implement a real browser identity/session boundary. Do not expose long-lived operator tokens to browser JavaScript.
2. Verify missing/invalid credentials are rejected on every protected UI/API route.
3. Bound concurrency, request rate, subprocess duration, output size, and total work; implement explicit cancellation and unknown-outcome handling.
4. Keep accept/deny/revise and emergency-stop operations race-safe and auditable; no approval gate may be inferred or bypassed.
5. Keep external side-effecting agents disabled by default; require a scoped, explicit human approval for any separately authorized action.

### Gate D — cloud staging
1. Confirm authorized AWS account, region, owner, domain/DNS ownership, budget threshold, and alert recipients.
2. Use GitHub OIDC with a narrowly scoped deploy role; do not add long-lived cloud keys to GitHub or source files.
3. Build and scan an image from one exact source SHA, push to ECR, and deploy by immutable image digest.
4. Use ECS Fargate private tasks with no public IP, ALB-only ingress, HTTPS via ACM, least-privilege task roles, Secrets Manager, log redaction/retention, bounded scaling, health/readiness checks, and cost alerts.
5. Run staging acceptance with business-cycle and external write capabilities disabled.

### Gate E — release decision
A release receipt must bind together: source SHA, workflow URL and result, image digest, dependency/image scan results, AWS account/region, ECS service and task-definition revision, TLS/auth/protected-route checks, persistence/restart/idempotency tests, secret-redaction evidence, timestamp, operator approval reference, and rollback target.

Do not route public traffic until Gates A–E have inspectable evidence and an authorized human approves the release. A hosting approval is not authorization for business actions. Roll back to the last known-good immutable digest if authentication, authorization, evidence durability, readiness, or emergency-stop controls fail.

## Evidence discipline

Record each item as **PASS**, **FAIL**, **BLOCKED**, or **NOT RUN**, with the exact SHA/environment and evidence URL. Do not convert a missing result into a pass. Do not report “all agents active,” “fully operational,” or “deployed” unless the corresponding runtime telemetry and verification receipt prove it.
