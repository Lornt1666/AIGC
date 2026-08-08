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

## Quantitative assurance

The assurance plane is separately digested so the accepted cloud action
program and its historical event hashes remain unchanged.

Quantitative observations:

- accept finite plain decimal strings only;
- use `Decimal` precision 50 with half-even rounding;
- reject binary floats, exponent notation, NaN, infinity, unknown units,
  insufficient samples, confidence below policy, or excessive tolerance;
- calculate `max(absolute_tolerance, abs(expected) * relative_tolerance)`;
- use absolute tolerance only when the expected value is zero;
- bind every observation to paired source references and content SHA-256
  digests;
- retain failed observations, while the latest observation per metric controls
  the current verdict;
- never convert a metric result into action completion or Phase 5 authority.

The v1 mode is `exact`. Each required metric is defined by policy with an
immutable unit, target, zero tolerance, source file, JSON pointer, extractor,
and definition digest. Callers cannot choose a target or register a new metric.
The completed-action metric derives the count of unique completed action
identifiers from `/executed_actions`; it does not trust a receipt's summary
field. The execution receipt has a policy-pinned file SHA-256, every referenced
action must belong to the bound program, and any locally present action ledger
must contain the matching terminal completion.
Statistical confidence intervals and cross-unit aggregation are deliberately
not claimed by v1.

## Working memory

Working memory is advisory context, never execution authority. It uses a
separate append-only SQLite chain and stores only closed, non-sensitive
operational facts:

```json
{
  "fact_type": "blocker",
  "subject_ref": "github.issue.124",
  "value": "open_zero_step_ci",
  "reason_codes": ["hosted_ci_zero_steps"],
  "tags": ["ci", "cloud"]
}
```

Arbitrary prose, prompts, logs, nested objects, names, email addresses, phone
numbers, payment data, credentials, tokens, numeric fact values, and
secret-like values are rejected. Quantities belong in the quantitative
assurance plane. Facts require exact scope, confidence, salience, TTL,
provenance, source digests, source revision, a lowercase opaque actor
identifier, and an idempotency key.

Subject references must use an allowlisted operational namespace. Sensitive
semantic components, person-name-shaped values, and compact high-entropy
credential-like values are rejected even when they satisfy the token syntax.
Provenance files are opened once, size-checked on the open descriptor, read
within a fixed byte bound, and rejected if their size changes during that read.

Limits are fail-closed: 32 active facts, 4 KiB per fact, 64 KiB per exact
scope, a 32 KiB recall response, 4,096 total assurance events, and an 8 MiB
database epoch. Default TTL is 24 hours and maximum TTL is seven days. Expiry
is derived at recall and never deletes history.

Supersession appends a new same-scope fact. The predecessor never revives when
its replacement expires. Recall is deterministic by salience, confidence,
sequence, and identity, and returns only the largest ordered prefix within the
byte budget. A repeated identical idempotency request returns the original
event even if ambient repository state changed; reuse with different content
fails. Recall always requires one exact `program`, `action`, or `run` scope.
Backdated writes are rejected before insertion, and historical recall selects
the latest fact that existed at the requested time. TTL values must be actual
integers and are never coerced from booleans, strings, or floats. Run-scoped
facts are accepted only for run/action pairs present in the configured trusted
execution receipt whose exact file digest is pinned in assurance policy.

Source digests are checked when a fact is ingested and again for active facts
during current assurance. Later source drift does not make the append-only
history unreadable. It sets `sources_current` to false, increments
`source_drift_count`, fails current working-memory assurance, and prevents
recall of the affected scope until a new provenanced fact supersedes it.

## Processing speed

Performance results are local observations, not production capacity promises
or comparisons with another system. They are hot-cache SQLite and bounded
workspace probes, not process-startup, cold-disk, network, end-to-end request,
or production throughput measurements. Verification records the exact event
and metric-source workload and uses the monotonic `perf_counter_ns` clock, ten
warmups, and 100 retained samples for:

- SQLite quick-check plus assurance-history replay;
- deterministic working-memory recall;
- quantitative metric summarization.

The receipt stores every warmup and measured nanosecond duration, plus minimum,
integer mean, p50, p95, p99, maximum, and the p95 budget. Percentiles use the
nearest-rank method and no sample is trimmed, retried, or hidden.

## Rigorous verification

Verification runs against a consistent in-memory SQLite snapshot and proves:

- strict program, assurance, and receipt schemas;
- SQLite integrity and enabled foreign keys with at least one declared
  relationship and zero violations;
- immutable binding and event triggers;
- functional append-only trigger probes before every behavior-changing write;
- contiguous sequence, nondecreasing UTC time, exact hash replay, and program
  plus assurance digest binding;
- exact memory supersession, expiry, scope, size, run ancestry, and
  non-sensitive payload rules;
- current active-memory source-drift detection without mutating history;
- exact metric recomputation from decimal inputs and evidence digests;
- read-only validation of the original action ledger when it exists;
- required implementation artifact existence, byte size, and SHA-256;
- all local p95 processing budgets;
- extension of the strongest independently discovered trusted assurance
  checkpoint after the first receipt.

The configured baseline receipt and immutable `*.json` receipts in the runtime
checkpoint directory are discovered independently of SQLite. The strongest
valid receipt anchors the assurance event count and head hash. Later
verification fails if that receipt disappears, the local history is shorter,
the history no longer contains its exact anchored prefix, or the named
checkpoint digest does not own the exact count/head tuple claimed by the later
receipt.
`assurance_passed` reports only these assurance checks, while
`execution_authorized` is always false. Phase 5 remains the only route to
external execution authority.

Current receipt validation rechecks active source provenance. Historical
checkpoint replay intentionally preserves the source-currentness observation
made when that receipt was created, while current `verify` recomputes the
working-memory verdict and all performance samples. Raw historical timing
samples are self-digest protected for internal consistency, not
cryptographically authenticated measurements. A later retained checkpoint,
Git review, or separately approved signature/WORM control must pin historical
receipt authenticity.

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

Record one typed working-memory fact:

```powershell
python .\scripts\cloud_advancement_assurance.py remember `
  --key cloud.current-blocker `
  --scope program `
  --value-json '{"fact_type":"blocker","subject_ref":"github.issue.124","value":"open_zero_step_ci","reason_codes":["hosted_ci_zero_steps"],"tags":["ci","cloud"]}' `
  --actor accountable-operator `
  --source-ref reports/artifacts/cloud_advancement/initial_execution_receipt.json `
  --source-sha256 SHA256 `
  --idempotency-key cloud-blocker-2026-07-20 `
  --derivation-type direct_observation
```

Record one exact metric:

```powershell
python .\scripts\cloud_advancement_assurance.py measure `
  --metric-id cloud.action_catalog_count `
  --idempotency-key cloud-catalog-count-2026-07-20 `
  --actor accountable-operator
```

Recall only program-scoped memory:

```powershell
python .\scripts\cloud_advancement_assurance.py recall `
  --scope program `
  --query cloud
```

Run rigorous verification:

```powershell
python .\scripts\cloud_advancement_assurance.py verify
```

Write a new immutable checkpoint only after verification passes:

```powershell
python .\scripts\cloud_advancement_assurance.py checkpoint `
  --output reports/artifacts/cloud_advancement/cloud_advancement_assurance_baseline_receipt.json
```

Exit code `0` means every assurance check and budget passed, while execution
authority remains false. Exit code `10` means contract, database, history,
anchor, or receipt verification could not be completed. Exit code `11` means
verification completed but an active-memory provenance check, current metric,
memory minimum, or local performance budget did not pass.

`verify` is read-only and never creates the assurance database. `checkpoint`
refuses an existing destination, rechecks the event count and history head,
flushes the new receipt to a temporary file, and atomically publishes it with
a no-replace filesystem operation without changing SQLite. Output is limited
to the configured baseline or a direct `*.json` child of
`.aigc/cloud_advancement/checkpoints/`, ensuring every accepted checkpoint is
discoverable by future verification. A privileged owner capable of deleting
the newest checkpoint and rolling back the SQLite database, or rewriting every
independently retained receipt, remains outside the guarantees of this local
control; production assurance requires a separately approved signed, WORM, or
externally stored checkpoint catalog.

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
