# AIGC — Artificial Intelligence Gladiator Coliseum

AIGC is a governed, provider-neutral AI work operating system. It coordinates
specialized agents, evidence, memory, tools, employment workflows, software
delivery, and commercial preparation while keeping authority separate from
capability.

The shortest accurate description is:

> AIGC turns a human objective into a typed work order, produces and verifies a
> candidate result, and stops at the exact boundary where identity, permission,
> cost, communication, deployment, or another material consequence requires
> explicit authority.

This repository is not a claim of universal production availability. The current
release train is a locally verified reconstruction with several implemented
surfaces and explicit external blockers.

## Start here

- [AIGC System Atlas](docs/architecture/AIGC_SYSTEM_ATLAS_V1.md) — narrative,
  diagrams, system dimensions, parametrics, delivery surfaces, and readiness.
- [AIGC System Atlas presentation](docs/presentations/AIGC_SYSTEM_ATLAS_V1.pptx)
  — presentation-ready visual explanation.
- [Frozen Nexus integration contract](docs/architecture/AIGC_INTEGRATION_CONTRACT_V1.md)
  — canonical state, verification, authority, execution, and evidence semantics.
- [Autonomy amendment](docs/architecture/AIGC_INTEGRATION_CONTRACT_V1_AUTONOMY_AMENDMENT_001.md)
  — maximum safe autonomy with explicit authority at consequence boundaries.
- [Five subsystem contracts](docs/architecture/AIGC_CORE_SUBSYSTEM_CONTRACTS_V1.md)
  — SILVA, HexGate, VANIS, Correlation Station, and CHORUS.
- [RegenExcalibur Genesis](RegenExcalibur/universe-spec.md) — mythic-technical
  product language mapped to bounded engineering behavior.
- [LLM lifecycle](docs/architecture/AIGC_LLM_LIFECYCLE.md) — reference
  data-to-serving stack; training and production serving remain inactive.
- [Governed Wealth Operator](docs/architecture/AIGC_GOVERNED_WEALTH_OPERATOR_V1.md)
  — lawful opportunity, deliverable, application, revenue, invoice, and
  transaction preparation with consequential actions gated.
- [RegenExcalibur AIGC Coordinator architecture](pre_arch/architecture.md) —
  affix-tagged job, practice, work-submission, invoice, diagnostics, consent,
  and audit flows with deterministic local planning.
- [RegenExcalibur operator checklist](doc_runbook_post/operator_checklist.md) —
  consent, credential-reference, backup, deployment, verification, and rollback
  gates for an operator-controlled run.

## Five integrated systems

| System | Plain-language responsibility |
|---|---|
| SILVA | Proves where the software works: device, OS, browser, accessibility, performance, migration, and recovery. |
| HexGate | Evaluates identity, authority, privacy, safety, cost, and evidence before consequential execution. |
| VANIS | Coordinates versioned agents, models, and tools through bounded provider-neutral contracts. |
| Correlation Station | Preserves hashes, lineage, evidence, memory, telemetry, and reconciliation without converting them into authority. |
| CHORUS | Presents understandable plans, blockers, approvals, progress, and human takeover through user-facing surfaces. |

## Canonical law

```text
Reasoning != Verification != Authority != Execution != Evidence
Capability may grow autonomously; authority may not.
Indeterminate external effect -> read-only reconciliation -> no blind retry.
```

## Current evidence snapshot

The committed local readiness receipt reports:

| Measure | Current value |
|---|---:|
| Applicable required checks | 34 |
| Verified required checks | 12 |
| Verified ratio | 35.2941% |
| Minimum release ratio | 95% |
| Production ready | No |
| Authority granted | No |
| External production action performed | No |

These numbers describe the current registry and evidence set; they are not a
product-quality score and must not be increased without new exact-artifact proof.

## Local verification

```bash
.venv/bin/python scripts/build_aigc_system_atlas_data.py \
  --output reports/artifacts/aigc_system_atlas_local_snapshot.json
.venv/bin/python -m pytest -q
```

For the RegenExcalibur Coordinator specifically:

```bash
make diag-run PYTHON=.venv/bin/python
.venv/bin/python -m uvicorn src.webapp.regenexcalibur_api:app \
  --host 127.0.0.1 --port 8000
```

The coordinator plans `apply:jobs`, `articulate:practices`, `submit:work`, and
`invoice:hours`. It does not submit, send, sign, charge, deploy, or access a
third-party account without the exact operator-controlled consent, credential
reference, certified connector, and one-use execution permit required for that
consequence.

The local candidate and hosted exact-head CI are separate evidence boundaries.
Cloud deployment, public traffic, provider execution, mobile-store publication,
financial transactions, and blockchain mainnet activity require their own current
identities, terms, budgets, permits, receipts, and reconciliation evidence.
