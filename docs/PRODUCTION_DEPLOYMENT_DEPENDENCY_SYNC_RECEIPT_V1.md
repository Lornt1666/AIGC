# Production Deployment Dependency Synchronization Receipt v1

Status: `IMPLEMENTED_INTERNAL_PENDING_OPERATOR_REVIEW`  
External action performed: **No**  
Cloud resources changed: **No**  
Terraform planned or applied: **No**

## Evidence identity

```text
upstream pull request: #98
upstream branch: codex/production-connectors-secret-broker-v1
upstream head: f5ffdb4aaf60b09f40b1a8840ef5e5b62b49a141

deployment pull request: #99
deployment branch: codex/production-deployment-baseline-v1
pre-synchronization head: 70185cb0c9959dcf0f0e3b4123915c94c2c2bf79
synchronized evidence head: 1e2c859aa5edb6e9b5126df79996c86fb64d2003
dependency merge commit: 7ed7af471099c8343a355e966b8ab09790624ee0
rollback branch: codex/production-deployment-baseline-v1-pre-upstream-sync
```

## Change boundary

The dependency merge imports only the exact three-file connector-broker correction already present on PR #98:

- `src/application/governed_production_connectors.py`;
- `src/application/production_connectors.py`;
- `tests/application/test_connector_broker_execution_unification.py`.

The merge records PR #98 as a second parent so PR #99 is no longer behind its declared upstream branch. No deployment-specific implementation was rewritten, no production connector was enabled, and no provider or cloud action was performed.

`docs/PRODUCTION_DEPLOYMENT_BASELINE_V1.md` carries the same exact upstream head, dependency-merge identity, rollback branch, and canonical-broker regression requirement; the deployment runbook and this receipt identify the same dependency subject.

## Machine-readable receipt contract

The dependency evidence is now governed by:

- `schemas/stacked_dependency_sync_receipt.schema.json`;
- `governance/evolution/production_deployment_dependency_sync_receipt_v1.json`;
- `src/core/stacked_dependency_sync.py`;
- `tests/test_stacked_dependency_sync.py`.

The validator enforces:

- a strict Draft 2020-12 contract with no unknown properties;
- exact upstream PR, branch, and 40-character head identity;
- equality between the dependency merge parent and recorded upstream head;
- a distinct pre-synchronization and synchronized head;
- zero commits behind the declared upstream dependency;
- deterministic, sorted imported-path evidence;
- deterministic SHA-256 receipt identity and tamper detection;
- combined-main CI, stacked-base restoration, and operator-review requirements;
- explicit false values for cloud mutation, Terraform execution, connector activation, credential or secret access, external action, and readiness promotion.

The machine-readable record describes the completed PR #98 → PR #99 synchronization event at synchronized head `1e2c859a...`. Later commits may add governance around that evidence without rewriting the historical event subject.

## Verification requirement

PR #99 must be evaluated as a combined candidate against current `main` after dependency or evidence changes. The PR must then remain or be restored to its stacked base on PR #98. Exact-head CI, artifacts, readiness truth, and the resulting stacked merge candidate must be recorded before operator review.

CI run #1406 predates the dependency-receipt contract and cannot be reused as current evidence for the contract-cycle head. A fresh combined-main run is mandatory.

Any change to the upstream head, dependency parent, imported paths, synchronized event head, or evidence candidates invalidates the committed receipt digest and requires a new versioned receipt rather than silent mutation.

## Pull-request currentness gate

The historical receipt is immutable evidence of a completed synchronization event. Current review eligibility is evaluated separately against the GitHub pull-request event available to CI.

`src/core/stacked_dependency_sync.py` now compares the live pull-request identity with the receipt and classifies the event as:

- `CURRENT_STACK` when PR #99 still targets the exact recorded PR #98 branch and head;
- `COMBINED_MAIN_EVALUATION` when the branch is temporarily targeted at `main` for the required integration run;
- `STALE_STACK` when the pull-request number, downstream branch, upstream branch, or upstream head no longer matches.

The GitHub Actions regression test reads `GITHUB_EVENT_PATH` without making a provider API call. If PR #98 moves while the receipt still names the old upstream head, the exact-current stacked CI fails with `UPSTREAM_HEAD_DRIFT`. Combined-main evaluation remains distinguishable and is never reported as a current stack.

Every currentness-code change requires a fresh pull-request CI run at the exact implementation head; a prior dependency-receipt run cannot be reused.

This gate verifies pull-request currentness from the event snapshot supplied by GitHub Actions. It does not independently authenticate the event, query GitHub, inspect full commit history, or replace exact-head operator review.

The currentness cycle is independently reversible through:

```text
codex/production-deployment-baseline-v1-pre-dependency-currentness
```

## Rollback

The dependency-receipt contract cycle is independently reversible through:

```text
codex/production-deployment-baseline-v1-pre-dependency-receipt-contract
```

Abandoning or reverting the bounded contract, validator, receipt, test, and documentation commits requires no cloud, credential, database, connector, or deployment rollback.

## Truth boundary

Dependency synchronization and its receipt prove source-history, content alignment, receipt integrity, and current pull-request base identity only. They do not prove staging operation, production deployment, connector authorization, Secret Manager access, infrastructure readiness, or readiness-ledger promotion.
