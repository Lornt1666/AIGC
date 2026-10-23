# RegenExcalibur AIGC — Runtime Hardening and Operations Blueprint

**Status:** Reference implementation under review; not production authorized.  
**Release decision authority:** RX-19 only.  
**Default execution mode:** dry-run.  
**Candidate release state:** BLOCK until every evidence gate is independently verified.

## TL;DR

The recommended topology is a **hybrid Saga-driven directed graph**: PostgreSQL stores durable task state, append-only events and transactional outbox records; Redis Streams transports at-least-once messages; a bounded coordinator schedules registered handlers; isolated adapters own tool calls; a separate policy verifier authorizes each mutation; and adversarial QA plus human gates verify outcomes. The current implementation is an executable reference foundation, not a fully production-ready workforce. Do not enable live actions until trusted identity/permit integration, exact-head CI, independent security review, staging resilience tests, and release gates pass.

## 1. Epistemic taxonomy

### Hard system facts

- Redis Streams consumer groups track pending messages and require explicit acknowledgement. Delivery can be repeated, so application-level deduplication and idempotency remain necessary. Redis documents a newer idempotent production feature beginning with Redis 8.6; this deployment template uses Redis 7.4 and does **not** rely on that feature. Source: https://redis.io/docs/latest/develop/data-types/stream/
- PostgreSQL Write-Ahead Logging (WAL) supports crash recovery and durability behavior, subject to the actual database and storage configuration. A successful SQL commit is not the same thing as an independently retained backup. Source: https://www.postgresql.org/docs/current/wal.html
- Python's `ast` module parses source into a syntax tree; a static AST screen does not isolate a process or prevent kernel, resource, or dependency abuse. The AST arbiter therefore never executes source. Accepted code still requires a separate OS/container sandbox. Source: https://docs.python.org/3/library/ast.html
- OpenTelemetry supports manual trace instrumentation, span attributes/events, and exporter configuration. The current telemetry helper is opt-in; end-to-end instrumentation coverage and an OTLP collector are deployment work. Source: https://opentelemetry.io/docs/languages/python/instrumentation/
- Docker multi-stage builds keep build tooling out of the runtime image. Production should additionally pin base-image digests, use a reviewed dependency lockfile, scan images, and sign build provenance. Source: https://docs.docker.com/build/building/multi-stage-builds/
- GitHub workflow-run and job APIs expose run/job status and require Actions read permission for private repositories. A REST result is not, by itself, a cryptographic administrator attestation. Sources: https://docs.github.com/en/rest/actions/workflow-runs and https://docs.github.com/en/rest/actions/workflow-jobs
- OWASP identifies excessive agency as a risk when model-driven systems have excessive functionality, permissions, or autonomy. Controls must be enforced at the tool/API boundary rather than delegated to model self-restraint. Source: https://genai.owasp.org/llm-top-10/

### Explicit design assumptions

- Process, worker, network and provider failures are expected; messages may be duplicated, delayed, reordered or malformed.
- The external LLM may return non-deterministic or adversarially influenced content. LLM output is untrusted data, never policy or code authority.
- A side-effecting adapter may time out after the remote system has applied the action. The outcome is UNKNOWN until a read-after-write reconciler checks it.
- PostgreSQL is the durable ledger. Redis is transport/cache, not the only copy of task state.
- A cryptographically valid signature establishes integrity under a key; authorization additionally requires an independently governed trust policy and a permitted purpose.

### Unknowns that require measurement or external owners

- Actual upstream LLM latency, provider quotas, cost per task, tool latency distributions, target throughput and peak concurrency.
- Whether every GitHub required check, branch protection rule, ruleset and bypass actor is effective on the relevant branches.
- Availability, retention and key-management guarantees of the deployment's secret manager, KMS/HSM, artifact store, OTLP collector and backup destination.
- The qualified independent reviewer, authorized human approver, and actual RX-19 receipt/decision interface. These identities and interfaces must not be guessed.
- Recovery-time objective (RTO), recovery-point objective (RPO), jurisdictional retention obligations and operational on-call coverage.

## 2. Topology and contracts

```text
Human / API goal
      |
      v
Authenticated API -> Pydantic v2 TaskContract -> Policy decision (deny by default)
      |                                           |
      v                                           v
PostgreSQL task + append-only event + outbox   Signed, scoped ToolPermit
      |                                           |
      v                                           v
Redis Streams -> bounded coordinator -> allowlisted isolated adapters
      |                                           |
      +----------------- results / receipts ------+
                            |
                            v
               independent QA + red-team review
                            |
                            v
              human gates -> RX-19 decision only
```

### Components delivered on the implementation branch

- `core/contracts.py`: strict, versioned Pydantic contracts for tasks, evidence, results, mutation payloads, trace context and permits.
- `core/orchestrator.py`: bounded async coordinator, transactional outbox, consumer deduplication, operation allowlist, timeouts, bounded full-jitter retries and reverse-order Saga compensation hooks.
- `core/arbiter.py`: static AST policy screen; never compiles or executes candidate source.
- `core/telemetry.py`: opt-in OpenTelemetry traces and metric exporter configuration, with sensitive attribute filtering.
- `core/service.py`: authenticated API for task admission, task validation and static audit. It exposes no arbitrary code execution, merge, deploy or release endpoint.
- `src/aigc_runtime/github_evidence.py`, `receipt_verifier.py`, `closure_workflow.py`, and `scripts/aigc_closure_live.py`: live GitHub read-only acquisition, signed-receipt verification, fail-closed gate evaluation and blocker reporting. Artifact ZIP byte verification remains an explicit blocker until a trusted downloader/verifier is implemented and tested.
- `config/regenexcalibur_aigc_agent_registry.json` and `docs/agents/RX-149_...` through `RX-161_...`: agent contracts registered disabled at R0. Specification/registration does not mean agent services are implemented or production integrated.

### Typed message requirements

Every task/event must bind:
- contract/schema version, task ID, project ID, agent ID/version, policy version;
- objective, scope, exclusions, acceptance criteria and risk tier;
- idempotency key, hop count, attempt count, deadline and budget;
- evidence references, source digests, timestamps, authenticated state and trace context;
- explicit proposed side effects and permit/approval references;
- result status, assumptions, limitations, risks, evidence references and audit-event IDs.

Reject unknown schema versions, extra fields, invalid digests, expired permits, duplicated dependencies, invalid state transitions and missing policy versions. Never use pickle or dynamically import an agent from untrusted registry content.

## 3. Architecture comparison

Scores are relative design judgments (1 = weak, 5 = strong), not benchmark measurements.

| Criterion | A: Central controller | B: Pure event choreography | C: Hybrid Saga graph |
|---|---:|---:|---:|
| Throughput / horizontal scale | 3 | 5 | 4 |
| Consistency / audit ordering | 4 | 2 | 4 |
| Rollback / compensation clarity | 4 | 1 | 5 |
| End-to-end observability | 4 | 2 | 5 |
| Operational simplicity | 4 | 2 | 3 |
| Single-point-of-failure exposure | 2 | 4 | 4 |

**Recommendation: Architecture C.** Keep task planning and policy enforcement centralized enough to make decisions inspectable, use Redis Streams for decoupled delivery, persist authoritative state and an outbox in PostgreSQL, and make each mutating adapter a bounded Saga step with explicit reconciliation/compensation. Add HA database/Redis deployment and failover only after failure-injection tests. Choreography alone is not the preferred choice for a system with human gates and release authority boundaries.

## 4. Explicit operational bounds

These are configured defaults or target SLOs, not claims of measured production performance.

| Parameter | Initial bound | Rationale / status |
|---|---:|---|
| Max dependency hops | 10 | Enforced by task contract and coordinator |
| Agent/tool operation timeout | 30 seconds default; hard ceiling 300 seconds | Configurable per task; validate with real latency data |
| Max concurrent Saga slots | 16 per coordinator process | Local semaphore only; global concurrency needs distributed quota/lease |
| Attempts | 3 by default; maximum 8 | Retries only for declared idempotent operations |
| Retry delay | Full jitter: U(0, min(cap, base × 2^k)) | Bounded exponential backoff; do not retry non-idempotent writes |
| Queue latency target | p95 below 500 ms | **Unvalidated target**; measure enqueue-to-start by workload class |
| Task-processing target | p95 below 30 seconds for bounded tasks | **Unvalidated target**; long research/code tasks need separate classes |
| Source size for AST screening | 128 KiB | Reject oversize input before parsing |
| AST nodes | 10,000 | Reject over-limit trees |
| AST nesting | 64 | Reject excessive nesting; this is not runtime isolation |
| Receipt validity | At most 15 minutes for ToolPermit contract | Verify issuer, key status, purpose, target, candidate, policy and replay state independently |

No LLM output may increase its own timeout, budget, hop count, permissions or retry count.

## 5. Persistence, delivery and Saga semantics

1. Commit task state, event record and outbox row in one PostgreSQL transaction.
2. Publish outbox records to Redis Streams. A crash after Redis accepts a message but before PostgreSQL records publication can duplicate delivery; stable `event_id` plus consumer idempotency is mandatory.
3. Consumer acknowledgement occurs only after successful handling. Poison-pill events must be bounded by delivery count and moved to a dead-letter stream with a reason and correlation ID; never retry in a hot loop.
4. Every side-effect adapter requires a stable idempotency key and read-after-write reconciliation. Timeout does not prove failure.
5. If an action outcome is unknown, stop and reconcile before compensating. If applied, compensate in reverse order only when the compensation is allowlisted, idempotent and separately permitted. If not applied, compensate previously completed steps. If the outcome cannot be established or compensation fails, emit `MANUAL_RECONCILIATION_REQUIRED` and fail-stop.
6. The database event ledger is append-only for the runtime role. Backups and audit exports must be retained independently; a database owner/superuser can still alter schema or disable triggers, so production tamper evidence requires external immutable retention and separate administrative identities.

## 6. Failure Modes and Effects Analysis (FMEA)

| Failure mode | Impact | Required control | Acceptance test |
|---|---|---|---|
| Poison-pill / malformed stream message | Consumer repeatedly fails; backlog grows | Schema validation, hop/delivery ceiling, DLQ, alert, no hot loop | Repeated malformed event reaches DLQ at threshold; no infinite retry |
| Crash after publish before outbox update | Duplicate Redis entry | Stable event ID, consumer dedupe, idempotent adapter key | Inject crash between XADD and commit; only one business effect |
| Adapter timeout after remote success | Duplicate write / inconsistent Saga | Read-after-write reconciliation; UNKNOWN blocks compensation/retry | Simulate applied-but-timeout; reconcile APPLIED then compensate or continue safely |
| Compensation itself fails | Partial mutation persists | Reverse-order receipts, permit for compensation, manual reconciliation state | Fail second compensation; earlier receipts retained; final status INCOMPLETE |
| Untrusted code injection | Arbitrary execution / data theft | AST screening plus isolated runtime with no secrets, seccomp, resource limits and network egress policy | Test eval/exec/import/dunder/oversize/deep AST; all blocked; source never executes |
| Recursive task/cost exhaustion | Budget burn / queue starvation | Max hops, deadlines, concurrency quota, token/spend limits, circuit breaker | Simulate recursive plan and budget overrun; coordinator blocks before dispatch |
| PostgreSQL unavailable | Cannot durably accept tasks | Readiness failure; no volatile-only acceptance | Kill DB; API returns 503 and accepts no task |
| Redis unavailable after DB commit | Outbox backlog, API may time out | Durable outbox; repeated idempotent submit drains pending rows | Kill Redis after DB commit; restore Redis; pending event is published |
| API token missing/invalid | Unauthorized task admission | Constant-time bearer comparison, secret manager, rotation | Missing, wrong and expired credential rejected |
| Receipt signed by untrusted key | Forged approval/provenance | Trusted keyset out-of-band, purpose/issuer/binding checks, revocation | Unknown/revoked key and wrong SHA/digest fail closed |
| Stale candidate SHA | Old CI/review used for new commit | Live-head refresh and exact SHA/attempt binding | Change PR head after snapshot; result STALE/BLOCK |
| Admin protection API returns 403 | Protection status unknown | UNVERIFIABLE, authenticated admin readback required | 403 never maps to PASS or "protection disabled" |
| Required CI job skipped | False green | Require all policy-required jobs successful in one exact run attempt | Missing/skipped job blocks closure |
| Telemetry exporter fails | Observability gap | Fail visibly, health signal, local structured logs without secrets | OTLP unreachable; service reports exporter configuration failure |
| Human/RX-19 interface absent | Unauthorized release risk | Explicit handoff blocker; no guessed endpoint or identity | Missing receipt or RX-19 decision always blocks release |

## 7. Deployment and runbook

### Prerequisites

- Docker Engine / Docker Compose plugin.
- A reviewed deployment environment and backup destination.
- For production: secret manager, TLS termination, network egress policy, immutable log/artifact retention, monitored OTLP collector, dependency/image scanners, signed provenance, key rotation/revocation procedures, and an on-call owner.
- Do not expose Postgres, Redis or Qdrant to the public network.

### Local reference deployment

1. Generate separate URL-safe credentials and create the local environment file:

```bash
cp .env.example .env
openssl rand -hex 32
```

Put separate generated values in `POSTGRES_PASSWORD`, `AIGC_APP_DB_PASSWORD`, `AIGC_RECEIPT_DB_PASSWORD`, and `AIGC_API_BEARER_TOKEN`. The closure runner uses a dedicated `aigc_receipt_verifier` database identity through `AIGC_REPLAY_DATABASE_URL`; it must not fall back to the API role. Keep `.env` out of version control. The app database URL uses a separate limited runtime role; the bootstrap role must not be passed to the app.

2. Validate configuration and start the stack:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 app postgres redis
```

For optional Qdrant, only after the vector retrieval adapter has been configured:

```bash
docker compose --profile vector up --build -d
```

Qdrant is not yet integrated into the active memory path; starting it does not mean semantic memory is operational.

3. Verify readiness:

```bash
curl --fail http://127.0.0.1:8080/health/live
curl --fail http://127.0.0.1:8080/health/ready
```

The local API is bound to loopback by default. Keep it behind authenticated TLS ingress for remote use. Generate the authorization header from the local secret store, not shell history.

4. Run repository validation before considering any deployment:

```bash
python -m pip install -r requirements.txt
python scripts/validate_regenexcalibur_agent_registry.py
PYTHONPATH=. python -m unittest discover -s tests -p 'test_aigc_core_runtime.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_aigc_closure_workflow.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_aigc_evidence_adapters.py' -v
```

Also run the complete existing CI workflow, dependency and secret scans, image scan, SBOM generation, and independent review. A partial local test subset is not a release gate.

### Live closure packet preparation and evaluation

Run this from a controlled host with outbound access to `api.github.com` and the allowlisted GitHub artifact-storage domains. Load `GITHUB_TOKEN` and `AIGC_REPLAY_DATABASE_URL` from the secret manager into the process environment; the latter must use the dedicated `aigc_receipt_verifier` database role, not the application or bootstrap role. Do not put credentials on the command line or in a file committed to Git. The token needs only read access to the repository, pull requests, Actions runs/jobs/artifacts, and whatever readback endpoints its policy permits. If protection readback returns 403/404, the gate remains UNVERIFIABLE.

Set the exact required job names from the signed release policy and current workflow configuration; do not guess them:

```bash
export REQUIRED_CI_JOB_1='validate'
export REQUIRED_CI_JOB_2='revalidate_locked_releases (v0-12, <policy-defined locked SHA>)'
export REQUIRED_CI_JOB_3='revalidate_locked_releases (v0-13, <policy-defined locked SHA>)'
PYTHONPATH=src python scripts/aigc_closure_live.py \
  --repository Lornt1666/AIGC --pr 330 \
  --trusted-keys /secure/policy/trusted-keys.json \
  --receipts /secure/evidence/core-receipts.json \
  --required-ci-job "$REQUIRED_CI_JOB_1" \
  --required-ci-job "$REQUIRED_CI_JOB_2" \
  --required-ci-job "$REQUIRED_CI_JOB_3" \
  --prepare --output /secure/evidence/preparation-report.json
```

The job names above are examples of the invocation shape, not a claim that they match the current workflow. Use the exact job names returned by the live run and required by the authenticated policy. Preparation exits 0 only when G0–G5 pass and the canonical digest is reproducible; it still does not authorize release. It prints `computed_evidence_digest` for authorized human/RX-19 receipt creation. See [RX-148 Evidence Receipt Schema](RX148_EVIDENCE_RECEIPT_SCHEMA.md) for signed claim contracts.

After authorized acceptance, RX-19 handoff and decision receipts have been signed against that digest, run the same command without `--prepare` and with the complete receipt bundle. The final evaluation re-fetches the PR head and evidence. Any changed candidate, run/job result, protection state, review evidence, artifact bytes or policy causes a digest/gate mismatch. Exit code 2 means BLOCK; inspect the JSON gate matrix and blocker report. Never use a nonzero exit as a reason to bypass the gate.
### Database migration notes

On a **new** Compose volume, the Postgres initialization scripts create the limited runtime role and apply `core/migrations/001_runtime.sql`. The application verifies migrations `001_runtime` and `002_receipt_claims` and does not create schema at startup.

For an **existing** database, do not run `docker compose down -v` and do not blindly re-run role creation. Take and verify a backup, inspect `pg_roles` and `aigc_schema_migrations`, then apply the migration under an authorized migration identity after a reviewed maintenance plan. Production migrations should be run by a separate, short-lived migration identity; the API role must not receive DDL or superuser privileges.

### Backup and restore drill

1. Create a protected backup:

```bash
umask 077
docker compose exec -T postgres pg_dump -U aigc -d aigc --format=custom > aigc-$(date -u +%Y%m%dT%H%M%SZ).dump
sha256sum aigc-*.dump
```

2. Copy the dump and digest to a separate encrypted retention system. A digest stored beside a mutable dump is not tamper-proof by itself.
3. Restore into an isolated temporary database using the authorized database administrator, run schema and invariant checks, then verify event counts and selected task/event digests.
4. Only after a tested recovery plan may a database be promoted. Never overwrite the only known-good volume as the first restore attempt.

Postgres is the durable source. After Redis loss, restore Redis and republish events that are not recorded as consumed from the PostgreSQL event/outbox ledger using a reviewed recovery command. Because Redis stream IDs and consumer-group state may be lost, verify consumer group creation, pending events, and adapter idempotency before resuming writes.

### Incident response / fail-stop

- Engage the kill switch and disable external side-effect adapters.
- Capture current PR/candidate SHA, task IDs, run IDs/attempts, event IDs, permit IDs and evidence digests.
- Do not retry an operation until the remote side effect is reconciled.
- Preserve logs and receipts, rotate exposed credentials, and isolate affected worker identities.
- Re-enable only after independent retest, an authorized operator decision, and a documented rollback/recovery test. RX-19 retains sole release decision authority.

## 8. Production exit criteria

All must be true before production activation; any missing item is BLOCK:

1. Full CI passes on the exact candidate commit, including all required jobs; artifact bytes and manifest are independently verified.
2. Dependency lockfile with hashes, SBOM, vulnerability scan, image scan, pinned image digests and signed provenance are present.
3. Separate runtime/migration/admin identities and secret-manager-backed credential rotation are tested.
4. Cryptographic permit verification is integrated with an independently governed trust store, key rotation/revocation and replay protection. Tool permits bind subject, operation, resource, candidate, policy version, idempotency key, expiry and approval receipt.
5. Every write adapter has explicit schema, idempotency, read-after-write reconciliation, timeout behavior, compensation contract and a staging test.
6. Poison-pill, duplicate delivery, process crash, network partition, Redis loss, PostgreSQL failover, compensation failure, kill-switch, budget exhaustion and recovery drills pass.
7. OpenTelemetry traces, metrics, structured logs, alerts, SLO dashboards, retention and on-call escalation are verified end to end.
8. Red-team and independent QA findings are remediated and independently retested against the exact candidate.
9. Authorized administrator supplies authenticated effective protection readback and assigns a qualified independent reviewer; no agent invents identities or approvals.
10. Authorized human acceptance binds the final candidate SHA and canonical evidence digest.
11. RX-19 receives the verified packet and issues the sole authenticated release decision. RX-144 coordinates only.

**Current disposition: BLOCK / reference implementation only.** No agent is activated by this document. No merge, deployment, or release is authorized.
