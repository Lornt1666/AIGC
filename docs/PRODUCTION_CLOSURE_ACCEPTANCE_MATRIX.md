# AIGC Production Closure: Executable Acceptance Matrix

**Status:** BLOCKED pending evidence. This document defines acceptance criteria; it does not attest that any gate has passed or authorize release.

## Candidate identity

Every closure attempt MUST bind evidence to all of:
- repository: `Lornt1666/AIGC`
- pull request number and current head SHA
- current base SHA
- workflow run ID and run attempt
- artifact archive SHA-256 and embedded manifest digest
- policy/trust-store version
- canonical evidence digest

Acquire these values from live sources. Never substitute a prior commit's successful CI result. Re-read the PR head and base after artifact and receipt verification; if either changed, discard the closure digest and restart.

## Gate matrix

| Gate | Required evidence | Acceptance test | Fail-closed condition |
|---|---|---|---|
| G0 Candidate identity | Live PR head/base and run-attempt identity | Re-fetch after all other gates | SHA, base, attempt, or repository mismatch |
| G1 CI | Complete required workflow on exact head | All required jobs created and completed successfully; inspect logs and step conclusions | Cancelled, skipped-required, absent, stale, or inaccessible job evidence |
| G2 Artifact | Archive digest, signed provenance/receipt, strict manifest and per-file hashes | Independently verify bytes, repository, SHA, run, attempt and workflow identity | Missing signature, trust failure, digest mismatch, unsafe archive, or missing file |
| G3 Security | Independent review bound to exact head; finding ledger and retest evidence | Adversarial tests for authz, permits, replay, AST policy, injection, secrets and fail-closed paths | No qualified independent reviewer, unresolved finding, or stale retest |
| G4 Runtime reliability | Integration and fault-injection results | Exercise duplicate delivery, worker crash, pending reclaim, poison pill, outbox atomicity and compensation reconciliation | Lost work, duplicate external mutation, infinite retry, or untracked failure |
| G5 Supply chain | Hash-locked dependencies, digest-pinned base images, pinned workflow actions, provenance | Rebuild and independently verify artifact provenance and dependency audit | Floating dependency/image/action or provenance mismatch |
| G6 Recovery and observability | Restore drill, measured RPO/RTO, alerts and trace/metric coverage | Restore into isolated environment; reconcile durable ledger and replay claims | Restore not demonstrated, ledger inconsistency, or unobservable critical failure |
| G7 Human acceptance | Authenticated acceptance receipt bound to final SHA and evidence digest | Verify issuer authority, signature, expiry and revocation | Missing, stale, untrusted, or differently bound receipt |
| G8 Release decision | RX-19 signed decision receipt bound to the same candidate and evidence digest | Verify authorized issuer and policy | Missing/invalid decision or candidate changed after decision |

**Release rule:** G0–G8 must all pass on the same immutable candidate and canonical evidence digest. Any UNVERIFIABLE result is BLOCK, not PASS. Only RX-19 may make the release decision.

## Required runtime fault-injection scenarios

1. Crash the worker after an external mutation succeeds but before Redis acknowledgement. Re-delivery must not repeat the mutation; reconcile outcome before compensation.
2. Interrupt PostgreSQL during outbox insertion. A task mutation and its outbox event must commit atomically or neither must commit.
3. Interrupt Redis after database commit. The dispatcher must eventually publish the durable outbox event without creating a second logical operation.
4. Reclaim an idle pending Redis Stream entry after consumer loss. Verify bounded attempts, safe ownership transfer and idempotent processing.
5. Send malformed, oversized, unsupported-version and over-hop-limit messages. Reject or dead-letter them with bounded resource use and no recursive re-enqueue loop.
6. Race two processes claiming the same signed receipt. Exactly one claim may succeed under the database uniqueness/transaction contract.
7. Use expired, revoked, untrusted, wrong-purpose and wrong-candidate receipts/permits. Each must be rejected.
8. Change the PR head or base while evidence is being acquired. The final recheck must invalidate the candidate digest.
9. Corrupt an artifact, inject ZIP traversal/symlink entries, or use a disallowed redirect host. Verification must stop before extraction or execution.
10. Disable the policy/trust service or make a required evidence endpoint unavailable. Mutating actions must remain blocked.

Record test inputs, expected behavior, actual results, logs, artifact hashes, environment identity and reviewer for each run.

## Supply-chain requirements

- Generate a reviewed hash-locked dependency file from the supported Python/runtime matrix; validate it with a clean build and dependency consistency check.
- Pin Docker base images by immutable digest and GitHub Actions by full commit SHA.
- Generate provenance for the exact artifact and verify repository, workflow identity, event, commit and artifact subject digest independently.
- Keep build credentials out of image layers, logs, artifacts and provenance subjects.
- Produce an SBOM and scan the built artifact; define documented remediation policy for critical/high findings.

## Recovery and operations

- Configure PostgreSQL base backups plus continuous WAL archiving if point-in-time recovery is an SLO.
- Restore into an isolated environment and verify schema migrations, event-ledger integrity, receipt-claim uniqueness and replay behavior.
- Document measured RPO/RTO, backup retention, key rotation, secret rotation, incident escalation, and safe rollback.
- Monitor queue latency, pending-entry age/count, dead-letter volume, retry exhaustion, workflow timeout, provider spend (before enabling any provider adapter), auth failures, receipt rejection and evidence acquisition failures.
- Define alert thresholds from measured workload and service objectives. Do not assert latency SLOs without benchmark evidence.

## Operational commands

Run from the repository root in a controlled staging environment with Docker Compose and the project's documented environment file configured.

```bash
# Validate compose interpolation and configuration without starting services.
docker compose config --quiet

# Build the service images.
docker compose build app worker

# Start the configured stack.
docker compose up -d

# Inspect service health and recent logs.
docker compose ps
docker compose logs --no-color --tail=200 app worker

# Run the repository's documented test suite in its project environment.
python -m pytest -q

# Inspect PostgreSQL readiness from its service container.
docker compose exec -T postgres pg_isready

# Capture a logical backup for an additional recovery layer.
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > aigc-staging.dump

# Validate the backup is readable; this does not replace a restore drill.
pg_restore --list aigc-staging.dump

# Stop services without deleting durable volumes.
docker compose down
```

Use the actual service names and database variables declared by the checked-out Compose configuration; never assume the commands prove production recovery. Do not run destructive restore commands against production as part of this checklist. Perform restores only into a separate, isolated target and record evidence.

## Primary standards and system references

- NIST SP 800-218, Secure Software Development Framework: https://csrc.nist.gov/pubs/sp/800/218/final
- Redis Streams, consumer groups and pending-entry recovery: https://redis.io/docs/latest/develop/data-types/stream/
- PostgreSQL continuous archiving and point-in-time recovery: https://www.postgresql.org/docs/current/continuous-archiving.html
- GitHub artifact attestations: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- OWASP Top 10 for Agentic Applications: https://genai.owasp.org/

## Non-goals and safety boundaries

This matrix does not activate disabled/spec-only agents, enable arbitrary Python execution, merge pull requests, deploy production, or override the release authority. Registration is not operational readiness; a passing CI run is not release authorization; a hash is not signer authentication.
