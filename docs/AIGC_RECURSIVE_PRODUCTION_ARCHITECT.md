# AIGC Recursive Production Architect

## Purpose

This subsystem converts the Omni-Meta-Trans-Neo-Para Auto-DevOps prompt into a bounded, contract-first AIGC planning engine.

It inventories and classifies the repository, builds ontology/taxonomy/methodology baselines, scores production readiness, and produces a reviewable transformation backlog.

It does not self-modify, self-approve, deploy, use credentials, delete files, or merge its own work.

## Run

```powershell
python .\src\recursive_production_architect_cli.py
```

Outputs:

```text
reports/artifacts/recursive_production_architect/<run_id>/recursive_production_cycle.json
reports/artifacts/recursive_production_architect/<run_id>/recursive_production_cycle.md
```

## Cycle Order

```text
repository inventory
→ ontology baseline
→ taxonomy baseline
→ methodology baseline
→ architecture assessment
→ production-readiness score
→ transformation backlog
→ operator review
→ separate reviewed implementation PRs
```

## Self-Recursion Boundary

The engine is recursive in planning discipline, not uncontrolled self-modification. Each run produces one evidence-backed cycle and stops for human review. Future cycles may evaluate the repository after approved PRs are merged.

Hard stops include:

- maximum cycle count;
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
