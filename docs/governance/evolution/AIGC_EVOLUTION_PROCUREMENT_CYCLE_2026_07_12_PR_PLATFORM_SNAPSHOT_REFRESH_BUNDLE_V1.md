# AIGC Evolution and Procurement Cycle — Platform Snapshot Refresh Bundle v1

## Identity

- project: AIGC only
- parent program: Issue #55
- implementation train: PR #75
- scope: governance and evidence planes only
- readiness-score impact: `0.0`
- production-ready state: `false`
- external action performed by AIGC runtime: `false`

## Diagnosed gap

AIGC already had separate commands for platform-snapshot completeness and graph-drift evaluation. That pathway remained fragile because an operator or later adapter could run drift evaluation against an incomplete or stale snapshot, write receipts to unrelated locations, or accidentally mix evidence from different evaluations.

The correction is not another GitHub connector. It is a repository-native orchestration boundary that accepts one normalized snapshot, evaluates completeness first, runs drift evaluation only when completeness passes, and writes one immutable review directory without overwriting an earlier bundle.

## Objective

Create one deterministic, fail-closed refresh bundle that proves:

1. which normalized snapshot was inspected;
2. whether the acquisition request was complete and fresh;
3. whether drift evaluation was permitted;
4. what graph-drift conclusion resulted;
5. which exact artifact bytes belong to the same review bundle.

## Implemented

- strict Draft 2020-12 refresh-bundle schema;
- one core orchestrator combining the existing request and drift evaluators;
- completeness-first gating;
- explicit `SNAPSHOT_INCOMPLETE` conclusion when drift evaluation is withheld;
- deterministic bundle identity;
- exact SHA-256 digests for the normalized snapshot and generated receipts;
- non-overwriting output directories named by bundle identity;
- CLI for ephemeral normalized snapshot input;
- positive, stale-input, drift, determinism, artifact-integrity and false-evidence tests.

## Governing pipeline

```text
normalized read-only platform snapshot
→ request completeness and freshness evaluation
→ stop if incomplete
→ graph-drift evaluation if complete
→ deterministic bundle manifest
→ isolated review directory
→ operator review
```

## Bundle conclusions

- `SNAPSHOT_INCOMPLETE` — request evidence failed; no drift receipt is permitted;
- `CURRENT` — complete evidence and no graph drift;
- `CURRENT_WITH_DECLARED_EXCLUSIONS` — complete evidence with only approved advisory exclusions;
- `DRIFT_DETECTED` — complete evidence with one or more blocking graph differences.

## Artifact set

Every complete bundle contains:

- `platform_snapshot.json`;
- `snapshot_request_receipt.json`;
- `graph_drift_receipt.json`;
- `refresh_bundle.json`.

An incomplete bundle omits `graph_drift_receipt.json` and records that absence explicitly. Artifact SHA-256 values are calculated from the exact persisted JSON representation.

## Security and privacy boundary

- no GitHub network query is performed by the module;
- no token, credential, secret or production identity is accepted;
- no PR, issue, graph, branch, review or merge state is mutated;
- input is limited to the existing normalized repository-metadata snapshot contract;
- the Security & Privacy Wiring Gate remains unchanged;
- operator review remains mandatory;
- automatic mutation remains prohibited.

## Tests

The bounded test set proves:

1. a complete in-window snapshot writes all four review artifacts;
2. every recorded artifact digest matches its exact file bytes;
3. bundle identity is stable when only evaluation time changes inside the permitted window;
4. a stale snapshot yields `SNAPSHOT_INCOMPLETE` and cannot create drift evidence;
5. a changed PR head yields `DRIFT_DETECTED` after completeness passes;
6. an incomplete bundle cannot falsely claim a drift artifact;
7. the full repository validation suite remains green.

## Architecture impact

The change strengthens the evidence plane only:

```text
snapshot request + graph + normalized snapshot
→ refresh orchestrator
→ review bundle
```

It adds no application runtime, API, UI, database, job-state, identity, connector, deployment or external-action capability.

## Rollback

Before merge, abandon PR #75 or revert the bounded refresh-bundle commits. After any separately authorized merge, perform one bounded revert and rerun exact-main CI. No application-data rollback is required.

## Acceptance criteria

- bundle schema validates;
- completeness always precedes drift evaluation;
- incomplete evidence cannot contain a drift receipt;
- complete evidence must contain a drift receipt;
- bundle and drift conclusions agree;
- artifacts are written to a new bundle-specific directory;
- exact artifact digests are recorded;
- deterministic identity excludes evaluation-time-only variation;
- full CI passes;
- no authority or permission boundary expands;
- PR remains draft and operator-controlled;
- merge remains a separate expected-head-protected decision.

## Remaining blockers

- operator disposition of PR #74;
- exact-main verification after upstream CI hardening;
- reconstruction and fresh evidence for PR #69;
- operator decisions in Issue #66;
- dependent-train revalidation;
- operator review and separate disposition of PR #75.

## Next-run boundary

Inspect only the final PR #75 head, final CI, refresh-bundle tests, current `main`, PR #74 disposition, PR #69 reconstruction requirements, Issue #66 state and any platform-snapshot drift. Do not begin another product runtime subsystem, production identity, deployment, connector execution, credential handling or automatic repository mutation.
