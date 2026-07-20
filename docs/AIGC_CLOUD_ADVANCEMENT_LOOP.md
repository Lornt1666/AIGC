# AIGC Cloud Advancement Loop

## Status

Implemented for bounded internal execution and scheduled read-only monitoring.
External cloud mutation remains disabled.

This loop does not authorize GitHub merge, Terraform apply, provider resource
creation, credential access, connector activation, staging deployment, or
production deployment. Those actions retain their existing review and Phase 5
requirements.

## Current decision

The immediate cloud blocker is not application code. GitHub issue `#124`
remains open, and the required workflow on PR `#123` still fails with an empty
job-step list. A zero-step hosted failure supplies no checkout, test, Terraform,
redaction, readiness, log, or artifact evidence.

The loop therefore executes only:

1. a local governed baseline;
2. read-only observation of the hosted-CI recovery gate;
3. one dependency-eligible internal action per later run after that gate passes;
4. no external mutation unless a separate exact Phase 5 packet is approved.

## Defined next steps

| Stage | Action | Execution boundary | Completion evidence |
|---:|---|---|---|
| 1 | Establish governed loop baseline | Automatic local read-only | Strict catalog, graph digest, SQLite state, revision binding |
| 2 | Verify hosted GitHub Actions recovery | Automatic remote read-only | Closed issue, exact head, successful workflow, nonempty steps |
| 3 | Bind and review source change train | Internal agent, clean worktree | Bounded diff, base/head, rollback, review packet |
| 4 | Prove release and immutable build integrity | Internal agent | Non-root image, digest, SBOM, scan, provenance |
| 5 | Complete durable PostgreSQL execution | Internal agent | Migrations, isolation, idempotency, backup and restore |
| 6 | Complete production identity and sessions | Internal agent | Authorization, revocation, tenant and workload identity tests |
| 7 | Wire secret broker and governed connectors | Internal agent | Reference-only secrets, permissions, idempotency, revocation |
| 8 | Complete governed Terraform planning | Internal agent; apply disabled | Validation, policy, cost, IAM diff, saved-plan contract |
| 9 | Prepare isolated staging authorization packet | Internal preparation only | Target, saved plan, costs, data boundary, rollback and evidence plan |
| 10 | Execute approved staging and assurance | Phase 5 external gate | Digest-bound deployment, TLS, identity, persistence, security and alerts |
| 11 | Execute restore, rollback and canary safety | Phase 5 external gate | Restore, rollback, canary and stop-condition receipts |
| 12 | Submit production deployment packet | Phase 5 external gate | Immutable plan, evidence, risks, costs, rollback and approval |

Dependencies are linear and explicit because AIGC currently needs persistence
before durable identity, identity before connectors, connectors before an exact
infrastructure plan, and staging evidence before production consideration.

## Non-repetition contract

Every action has:

- one stable action identifier;
- one semantic fingerprint derived from its category, objective, outputs, and
  acceptance checks;
- explicit dependencies;
- one priority and stage;
- a bounded attempt count;
- an execution class;
- retained evidence and terminal state.

The scheduler enforces:

- at most one claimed action at a time;
- completed actions are never eligible again;
- two actions cannot share a semantic fingerprint;
- every dependency must be complete before selection;
- actions are selected deterministically by priority, stage, and identifier;
- blocked monitor actions cannot repeat before their cooldown;
- a repeated monitor records that re-observation is operationally necessary;
- failed or expired non-monitor work requires an explicit, substantive
  necessity record;
- all prior blocked, failed, expired, and completed events remain append-only;
- every event is bound to the program digest and previous event hash;
- update and delete statements against the action ledger fail at the database
  layer.

Repeated monitoring of issue `#124` is the only automatic repetition in the
current catalog. It is necessary because the blocker exists outside repository
code and can change without a local commit. The monitor runs no more than once
per governed cooldown and records an evidence fingerprint each time.

## Runtime state

Runtime memory uses ignored local SQLite and evidence paths:

```text
.aigc/cloud_advancement/cloud_advancement.sqlite
.aigc/cloud_advancement/evidence/
```

The database stores append-only, SHA-256-linked events for claim, completion,
blocking, failure, and lease expiry. Raw secrets, credentials, private keys,
tokens, and external-action claims are prohibited. A changed program digest,
broken predecessor hash, or modified event payload blocks future claims.

The committed catalog and schema remain:

```text
config/cloud_advancement_loop.json
schemas/cloud_advancement_loop.schema.json
```

## Commands

Inspect current state:

```powershell
python .\scripts\cloud_advancement_loop.py status --markdown
```

Execute one safe built-in action:

```powershell
python .\scripts\cloud_advancement_loop.py execute-next `
  --actor scheduled-codex-cloud-loop
```

Claim one dependency-eligible internal action for agent implementation:

```powershell
python .\scripts\cloud_advancement_loop.py claim-next `
  --actor scheduled-codex-cloud-loop
```

Complete a claimed internal action:

```powershell
python .\scripts\cloud_advancement_loop.py complete `
  --run-id CLOUD-RUN-ID `
  --actor scheduled-codex-cloud-loop `
  --evidence path/to/reviewed-evidence
```

Record a blocker:

```powershell
python .\scripts\cloud_advancement_loop.py block `
  --run-id CLOUD-RUN-ID `
  --actor scheduled-codex-cloud-loop `
  --blocker-key stable-blocker-key `
  --reason "Exact reason this action cannot complete." `
  --evidence path/to/bounded-evidence
```

Retry only when repetition is necessary:

```powershell
python .\scripts\cloud_advancement_loop.py retry-action `
  --action-id CLD-003 `
  --actor accountable-operator `
  --necessity-reason "The recorded blocker changed and this bounded retry is now necessary."
```

## Scheduled coordination

The Codex automation runs daily at 06:00 in `America/Edmonton`.

Each scheduled run must:

1. read `AGENTS.md` and this document;
2. inspect the append-only loop status;
3. execute no more than one action;
4. use `execute-next` for the safe baseline or hosted-CI observer;
5. use `claim-next` only when an eligible internal action exists and the
   worktree is clean;
6. implement only that claimed action;
7. run its focused checks, repository redaction scan, and appropriate
   regression suite;
8. complete or block the same run with bounded evidence;
9. never select a different action after failure in the same scheduled run;
10. stop before push, merge, Terraform apply, provider mutation, credentials,
    connectors, staging, production, or external communication unless a
    separate exact authorization permits it.

The automation may explain why no action is eligible. It may not invent work to
avoid an honest blocked result.

## Cloud engineering best practices

The action catalog applies these practices throughout:

- immutable artifacts and exact revision binding;
- minimal non-root containers;
- pinned dependencies and build actions;
- SBOM, vulnerability scanning, provenance, and signing;
- transactional migrations and tested recovery;
- private networking and deny-by-default ingress;
- short-lived workload identity instead of service-account key files;
- least-privilege IAM with explicit diffs;
- secrets referenced through the AIGC Secret Broker only;
- idempotency and uncertain-write quarantine;
- remote encrypted Terraform state design with locking;
- policy-as-code, cost, quota, and drift checks;
- environment isolation and synthetic staging data;
- structured redacted telemetry, service objectives, and actionable alerts;
- bounded canaries, automatic stop conditions, rollback, and restore exercises;
- independent security review before production;
- operator-controlled production authorization.

## Definition of done

The loop itself is complete when:

- its strict catalog and schema validate;
- semantic duplicates and dependency cycles fail closed;
- append-only history cannot be updated or deleted;
- concurrency and retry tests pass;
- the first baseline action completes once;
- the hosted-CI gate is observed without mutation;
- the daily Codex automation is active;
- the bounded source change is published for review;
- no unsupported cloud, readiness, deployment, or external-action claim is made.
