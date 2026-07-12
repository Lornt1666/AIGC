# AIGC Evolution Snapshot Architect

## Purpose

This subsystem converts the Omni-Meta-Trans-Neo-Para Auto-DevOps prompt into a bounded, contract-first AIGC planning engine.

It inventories and classifies the repository, builds ontology, taxonomy, and methodology baselines, scores structural production readiness, and produces a reviewable transformation backlog.

The historical module and CLI names retain `recursive_production_architect` for compatibility. The current execution contract is deliberately non-recursive: each invocation produces exactly one evidence-backed snapshot and stops for operator review.

It does not self-modify, self-approve, deploy, use credentials, delete files, or merge its own work.

## Run

```powershell
python .\src\recursive_production_architect_cli.py
```

Outputs retain their existing names for compatibility:

```text
reports/artifacts/recursive_production_architect/<run_id>/recursive_production_cycle.json
reports/artifacts/recursive_production_architect/<run_id>/recursive_production_cycle.md
```

Every receipt declares:

```text
execution_mode = single_snapshot_review_only
cycle_number = 1
cycles_executed = 1
```

## Snapshot Order

```text
repository inventory
→ ontology baseline
→ taxonomy baseline
→ methodology baseline
→ architecture assessment
→ structural production-readiness score
→ transformation backlog
→ operator review
→ separate reviewed implementation PRs
```

## Recursion Boundary

The engine applies recursive planning discipline across separate reviewed repository states. It does not execute multiple internal cycles in one run.

A future recursive mode requires a separate contract-first implementation defining:

- prior-cycle input and provenance;
- measurable state delta;
- convergence criteria;
- duplicate-work suppression;
- bounded mutation authority;
- stop conditions;
- rollback;
- operator review between material changes.

Until that contract exists, policies declaring more than one cycle or another execution mode fail closed.

Current hard stops include:

- single snapshot complete;
- operator review requirement;
- hard-block detection;
- proposed critical-file change;
- readiness target reached;
- no material improvement available.

## Paradigm Mapping

- **Omni:** whole-repository coherence.
- **Meta:** audit of architecture, methodology, and quality controls.
- **Trans:** controlled transition from current to target state.
- **Neo:** introduction of justified new patterns.
- **Para:** parallel classification of code, infrastructure, DevOps, data, and risk.

These terms organize analysis. They do not grant runtime authority.

## Production Standard

Every proposed implementation must use a separate branch and reviewed PR, preserve rollback, pass CI, preserve the Security & Privacy Wiring Gate, and remain operator-controlled.
