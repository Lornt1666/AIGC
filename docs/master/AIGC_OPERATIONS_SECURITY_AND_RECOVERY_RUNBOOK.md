# AIGC Operations, Security, and Recovery Runbook

**Version:** 1.0.0-draft  
**Environment assumption:** local MVP or staging unless explicitly stated.  
**Production use:** prohibited until production acceptance gates pass.  
**Never paste secrets into commands, logs, issue comments, or repository files.**

## 1. Operating principles

- Validate before deploying.
- Use synthetic data first; use public data only in the documented read-only mode.
- Do not activate agents merely because they exist in the registry.
- Do not enable live secret retrieval without an approved security review and least-privilege identity.
- Do not run real external actions during a simulation, replay, or preflight.
- Preserve audit evidence and task state during stop/recovery.
- Do not call a failed/unknown external operation a success or failure until reconciled.
- Never use an older CI pass to certify a newer candidate SHA.
- Any missing, stale, conflicting, or inaccessible evidence blocks the affected action.

## 2. Local MVP preflight

Run from the repository root and use the documented Python environment. These commands are examples based on the repository README; confirm they match the checked-out revision before running.

```powershell
python --version
python .\src\aigc.py status
python .\src\aigc.py validate
python .\src\phase11_security_vault.py --fake-test
python .\src\phase13_simulation_arena.py
```

Expected interpretation:
- A zero exit code is evidence only for the command's own checks.
- Fake-secret verification does not prove access to a real secret manager is secure.
- Synthetic simulation does not prove real-provider behavior or external-action safety.
- If status, validation, or a test cannot be run, record it as unverified; do not infer a pass.

Initialize local state only when the selected environment and path are correct:

```powershell
python .\src\aigc.py init-db
```

Before running a phase, inspect its definition in `src/core/phase_registry.py`, input schema, output schema, risk tier, mode, and side effects.

## 3. Safe phase sequence

Recommended local validation order:

1. `python .\src\aigc.py status`
2. `python .\src\aigc.py validate`
3. `python .\src\aigc.py run pipeline --mode synthetic`
4. `python .\src\phase11_security_vault.py --fake-test`
5. `python .\src\phase12_observability_dashboard.py --export`
6. `python .\src\phase13_simulation_arena.py`
7. Run unit, integration, contract, security, and fault-injection tests from the repo's configured environment.

Only after validating that the code's exact command syntax and policy allow it, run real public-data replay:

```powershell
python .\src\aigc.py run pipeline --mode real_data_read_only --source remoteok --limit 10
```

The read-only replay must stop before external actions. Do not add live credentials to make the replay “more complete.”

## 4. Docker/staging preflight

If a Compose manifest is present in the checked-out revision, first inspect it and validate the rendered configuration. Do not assume service names or environment variables.

```bash
docker compose config --quiet
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs --no-color --tail=200
```

The first `docker compose config` command validates syntax and interpolation; it does not prove security. Review the rendered configuration for exposed ports, privileged containers, bind mounts, secret values, mutable image tags, unbounded volumes, missing health checks, and unintended public listeners.

Before staging use:
- non-root application and worker identities;
- read-only root filesystem where compatible;
- explicit CPU, memory, process, and file-size limits;
- internal-only database and Redis networks;
- persistent volumes with backup and restore tests;
- no production credentials;
- digest-pinned images and reviewed dependency locks;
- explicit egress policy;
- health checks that test dependencies, not just process liveness.

Stop immediately if any secret appears in the rendered configuration, logs, container environment dump, artifact, or image layer.

## 5. Deployment order

1. Validate source and candidate SHA.
2. Review dependency lock and image digests.
3. Run unit, contract, integration, security, and fault-injection tests.
4. Build immutable images and generate SBOM/provenance.
5. Verify provenance signer/builder identity and artifact subject.
6. Deploy to isolated staging.
7. Apply database migrations using the approved migration mechanism; take a verified pre-migration backup.
8. Run health checks and synthetic transactions.
9. Exercise emergency stop, retry exhaustion, DLQ, and recovery.
10. Capture evidence packet and exact configuration digests.
11. Obtain independent review and human acceptance.
12. Send complete candidate-bound evidence to RX-19.
13. Do not release until RX-19's authenticated decision is recorded and every gate is PASS.

This sequence is a required process, not a claim that the current repo has all tooling implemented.

## 6. Emergency stop

Use the documented CLI command only after confirming the checked-out revision and its effects:

```powershell
python .\src\aigc.py emergency-stop
python .\src\aigc.py status
```

Emergency stop should block new protected side effects and new dispatch, preserve state and audit records, and expose the stop reason and actor. It must not delete pending tasks or rewrite prior outcomes.

Clearing stop is a separate privileged action:

```powershell
python .\src\aigc.py clear-emergency-stop
python .\src\aigc.py status
```

Do not clear stop until incident containment, scope, state reconciliation, and authorization are reviewed. The exact authorization mechanism for clearing stop must be independently verified; command availability alone is insufficient.

## 7. Incident handling

For any suspected unauthorized action, secret leak, evidence mismatch, or integrity failure:

1. Stop new protected effects using the tested stop control.
2. Preserve logs, event IDs, task IDs, process/container IDs, timestamps, and relevant digests.
3. Do not copy secret values into the incident record.
4. Revoke or rotate affected credentials through the authoritative secret manager.
5. Identify affected candidate SHA, policy version, worker identity, permit, and external target.
6. Reconcile external outcomes; do not blindly retry or compensate.
7. Isolate affected workers and queues if needed without destroying evidence.
8. Record root cause, blast radius, detection gap, corrective action, and regression test.
9. Re-enable only after authorized review and verified recovery.

## 8. Queue and worker operations

Monitor:
- oldest pending message age;
- pending entries by stream/consumer group;
- abandoned consumer messages and claim/reclaim counts;
- retry counts and retry wait age;
- DLQ depth and age;
- idempotency conflicts;
- outbox backlog;
- worker crash/timeout rates;
- downstream adapter uncertainty.

Do not trim/delete stream entries until retention rules prove all required consumers have processed them and durable state contains the corresponding event. Redis Streams supports consumer groups, acknowledgements, pending inspection, and reclaim; these mechanisms require application-level idempotency and careful retention policy.

Operational recovery procedure:
1. pause affected dispatch if processing safety is uncertain;
2. inspect pending messages and durable task/outbox state;
3. identify whether the effect was never started, completed, or is ambiguous;
4. reclaim only after the idle threshold and worker-liveness criteria are met;
5. rely on the idempotency ledger to avoid repeating effects;
6. send poison messages to DLQ with a bounded reason and payload digest;
7. replay only after correction and explicit operator authorization;
8. record the recovery action and result.

## 9. Retry and circuit breaker policy

For transient failures only, use bounded exponential backoff with full jitter:
`delay = random(0, min(cap, base * 2^attempt))`.

The formula is a policy pattern, not a measured value. Configure base, cap, maximum attempts, deadline, concurrency, and provider budget per operation. Do not retry:
- schema or contract violations;
- authorization denial;
- invalid signature or revoked permit;
- digest mismatch;
- policy version mismatch;
- unsupported action;
- deterministic code defect;
- exhausted budget;
- non-idempotent operation with ambiguous outcome.

Open a circuit breaker when downstream failures exceed the configured threshold. Half-open probes must be bounded and safe.

## 10. Database backup and disaster recovery

The production target uses PostgreSQL. Until PostgreSQL is demonstrably wired and configured, any local SQLite store must have a separate backup procedure and must not be represented as PostgreSQL-backed.

Required controls:
- documented backup type and schedule;
- encryption and access control;
- off-host/isolated copy;
- retention policy;
- WAL archiving and point-in-time recovery where required;
- schema migration history;
- restore drill to a separate environment;
- consistency checks for tasks, state transitions, outbox, idempotency claims, permits, and audit references;
- measured RPO/RTO and named owner.

A restore drill must not overwrite production. Example inspection commands for a PostgreSQL environment, after confirming service name and credentials through approved configuration:

```bash
docker compose ps
docker compose exec -T postgres pg_isready
```

Do not use destructive restore commands copied from a generic runbook without verifying target, backup, timeline, and operator authorization.

Recovery acceptance:
- restored database is internally consistent;
- all migrations are known and applied in the intended order;
- outbox and queue reconciliation finds no unaccounted event;
- idempotency keys remain unique and effective;
- audit digests verify;
- replay of a safe test event produces no duplicate effect;
- actual recovery duration and data-loss window are recorded.

## 11. Release closure operations

For every release candidate:
1. Read live PR metadata, head SHA, base SHA, workflow runs, attempts, jobs, logs, artifacts, reviews, and effective branch/ruleset protection.
2. Capture all pages and record query timestamps; incomplete source pagination is not complete evidence.
3. For each workflow run ID, select the highest observed attempt. A later failure, cancellation, queued, or in-progress attempt invalidates an earlier success.
4. Verify artifact bytes, embedded manifest, expected subject, trusted builder/issuer, workflow identity, and build parameters.
5. Verify independent review and all findings' remediation/retest evidence on the exact SHA.
6. Build a canonical evidence packet and digest.
7. Re-read PR head/base and relevant policy/trust state. If changed, discard the digest and restart.
8. Verify human acceptance bound to the same SHA/digest.
9. Deliver to RX-19; RX-144 coordinates but cannot approve.
10. Record RX-19's authenticated decision receipt. A decision cannot override a failed prerequisite gate.

## 12. Production readiness evidence packet

Include:
- repository, PR, exact head/base SHA, policy and trust-store version;
- CI run IDs and attempts, all required job results, logs, and workflow definitions;
- dependency lock, image digests, SBOM, vulnerability results, provenance and verification output;
- unit/integration/contract/security/fault-injection results;
- independent review identity, findings, fixes, and retests;
- branch protection/ruleset readback;
- permit/identity and side-effect adapter tests;
- telemetry coverage, alert tests, redaction scans;
- backup/restore results and measured RPO/RTO;
- staging deployment digest and smoke/failover test results;
- human acceptance receipt and RX-19 decision receipt;
- canonical evidence digest and final post-check candidate re-read.

## 13. Primary references

- Redis Streams: https://redis.io/docs/latest/develop/data-types/stream/
- PostgreSQL backup and restore: https://www.postgresql.org/docs/current/backup.html
- OpenTelemetry signals: https://opentelemetry.io/docs/concepts/signals/
- SLSA provenance: https://slsa.dev/spec/v1.2/provenance
- GitHub artifact attestations: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- NIST SSDF: https://csrc.nist.gov/pubs/sp/800/218/final
