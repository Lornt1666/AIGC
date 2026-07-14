# AIGC Readiness Advancement — Post-Identity Main v2

Status: `IMPLEMENTED_ON_REVIEW_BRANCH_PENDING_CI_AND_OPERATOR_REVIEW`  
Base revision: `6f7f2d74b4cf95ba69d2f915ffa583085a71e30d`  
Branch: `codex/readiness-advancement-post-identity-v2`  
Supersedes: PR `#97` after reconstruction from current main  
Production deployment authorized: **No**  
Credentials or secrets used: **No**  
External action performed by AIGC runtime: **No**

## Objective

Reconcile the canonical production-readiness ledger with capabilities already merged and structurally evidenced on exact current `main`, while preserving the distinction between:

- repository structural evidence;
- internal implementation maturity;
- staging-observed operational evidence;
- production completion.

This change advances the structural meter only where merged repository evidence supports the movement. It does not mark a production blocker complete and does not authorize a live provider, connector, database, or deployment action.

## Current-main evidence basis

The following foundations are merged on `main`:

- governed Scout, Candidate, Quest, work-acceptance, and Quest Board flow;
- SQLite transactional authority, idempotency, migration, audit, and restart persistence;
- accepted Canadian Google Cloud environment decision;
- production security/privacy internal baseline;
- PostgreSQL connection, transaction, migration, and recovery-contract baseline;
- fail-closed production release gate;
- Google Identity Platform assertion-verification and durable server-session baseline from merged PR #95.

The identity baseline remains internal and offline-verifiable only. Its provider project ID is unresolved, its session-pepper Secret Manager reference is unresolved, and its provider configuration, onboarding, activation, deployment, and external-action authorities remain false. Therefore `production_identity_access` receives only `partial` structural credit and remains a production blocker.

## Evidence-backed status reconciliation

| Capability | Prior effective status | Reconciled effective status | Structural score delta | Production blocker retained |
|---|---:|---:|---:|---:|
| Work acquisition | `partial` | `implemented_internal` | +2.25 | No |
| Security/privacy wiring | `implemented_internal` | `implemented_internal` with current evidence | +0.00 | Yes |
| Transactional persistence | `planned` after evidence downgrade | `implemented_internal` | +4.95 | Yes |
| Production identity/access | `unimplemented` | `partial` | +4.50 | Yes |
| Production deployment | `unimplemented` | `planned` | +1.20 | Yes |
| **Total** |  |  | **+12.90** |  |

## Expected evaluator result

```text
prior structural readiness: 53.90 / 100
reconciled structural readiness: 66.80 / 100
net advancement: +12.90
threshold: 90.00
production_ready: false
```

Required blocking gaps remain:

```text
security_privacy_wiring
transactional_persistence
production_identity_access
approved_external_connectors
production_deployment
```

## Identity truth boundary

The identity capability is bound to these merged structural artifacts:

```text
config/production_identity_platform_baseline.json
src/infrastructure/identity/google_identity_platform_adapter.py
src/application/production_sessions.py
migrations/sqlite/0004_production_identity_sessions.sql
migrations/postgresql/0004_production_identity_sessions.sql
tests/integration/test_identity_platform_session_pipeline.py
```

The capability remains `partial` because no exact-revision staging evidence exists for:

- configured Identity Platform project;
- approved Secret Manager pepper reference and workload identity;
- real operator-controlled Google sign-in;
- managed subject mapping and session repositories;
- key rotation, revocation, outage, restart, rotation, and logout observations;
- cross-tenant and cross-project negative evidence;
- redaction review;
- a passing staging receipt.

Session rotation is treated as reauthenticated session replacement: fresh verified provider evidence is required, the old session is atomically invalidated, and the replacement begins a new absolute lifetime. Ordinary idle renewal remains capped by the active session's existing absolute expiry.

## Why the advancement is legitimate

The ledger measures bounded repository evidence. Missing evidence downgrades capability status. This branch registers only paths present on current `main` and uses maturity levels consistent with their documented boundaries:

- internal implementation is not operational completion;
- offline provider verification is not live production identity;
- a selected deployment architecture is not a deployed service;
- a PostgreSQL substrate is not a staging-observed managed database;
- a security baseline is not an independently reviewed operational security program.

## Threshold closure equation

Completing only the five current production blockers would move the score from `66.80` to `88.25`:

| Blocker completion | Additional points |
|---|---:|
| Security/privacy: `implemented_internal → complete` | +3.50 |
| Persistence: `implemented_internal → complete` | +2.25 |
| Identity/access: `partial → complete` | +4.50 |
| Connectors: `planned → complete` | +6.40 |
| Deployment: `planned → complete` | +4.80 |
| **Subtotal** | **+21.45** |

```text
66.80 + 21.45 = 88.25
```

The preferred final threshold bridge remains operational completion of `work_acquisition`:

```text
work_acquisition: implemented_internal → complete
score delta: +2.25
projected final score: 90.50
```

The score may change only through the canonical evaluator and verified evidence. Weights, multipliers, blocker semantics, and the threshold must not be manipulated to manufacture readiness.

## Required CI gates

The branch must pass:

1. contract validation;
2. AEC-001 validation;
3. committed-content secret/redaction scan;
4. procurement smoke stages;
5. focused readiness-ledger tests;
6. complete repository test suite;
7. readiness evaluation reproducing `66.80`;
8. test evidence upload;
9. readiness evidence upload;
10. operator review of the exact immutable head.

## Rollback

Before merge, close or abandon the branch.

After merge, revert this bounded ledger, test, and documentation change. No database rollback, cloud change, secret rotation, connector change, identity-provider change, or external recovery action is required.

## Definition of done

- exact current-main evidence paths are registered;
- identity partial credit is bound to the merged PR #95 baseline;
- the evaluator reports `66.80 / 100`;
- all five production blockers remain;
- `production_ready=false`;
- tests fail if score, maturity, evidence completeness, identity evidence, or blocker state drifts;
- CI passes on the reviewed branch head;
- the accountable operator makes a separate merge decision;
- exact-main readiness is verified after any authorized merge.
