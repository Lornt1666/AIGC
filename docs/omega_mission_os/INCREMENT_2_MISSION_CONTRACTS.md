# Increment 2 — Mission Contracts and Read-Only Mission Director

Status: **Implemented for review; no external-action authority**

## Added contracts

- `schemas/mission.schema.json` defines missions, objectives, tasks, dependencies, approvals, KPI records, evidence references, resource ceilings, stop conditions, and the explicit `external_action_authorized: false` invariant.
- `schemas/mission_snapshot.schema.json` defines the Director's read-only composition output, source health, separated verified and estimated revenue, blockers, approvals waiting, provenance, and mutation-denial flags.
- `config/mission.example.json` provides an inert CAD 2,000 revenue mission example.

## Mission Director

`src/mission_os/mission_director.py` reads a fixed allowlist of existing AIGC artifacts and emits a composed snapshot. It does not invoke phases, connectors, credentials, infrastructure, payment systems, or external communications.

Safety properties:

1. Source paths are constrained to the repository root.
2. Missing, malformed, and unsupported sources remain visible.
3. Source files are read but never rewritten.
4. Verified collected revenue remains separate from estimated or pipeline revenue.
5. Pending approvals are surfaced but never granted or consumed.
6. The Director requires `external_action_authorized` to be explicitly false.
7. Output declares `external_action_performed: false` and `canonical_state_mutated: false`.
8. The CLI refuses to write output into `data/`, `memory/`, `governance/`, or `config/` canonical-state directories.

## Local usage

Print a snapshot without writing a file:

```bash
python -m src.mission_os.mission_director config/mission.example.json --repo-root .
```

Write a disposable projection outside canonical state:

```bash
python -m src.mission_os.mission_director config/mission.example.json --repo-root . --output reports/mission_snapshot.preview.json
```

The preview is not execution evidence, authorization, financial proof, or a canonical state transition.

## Tests

```bash
python -m unittest tests.test_mission_director
```

The tests prove source immutability, visible missing and invalid inputs, repository-root path confinement, explicit denial of external authority, revenue classification, task progress calculation, and approval surfacing.

## Next increment

Increment 3 should add adapters for canonical Quest persistence and phase registries, schema validation through the existing contract validator, deterministic snapshot persistence in a dedicated non-authoritative projection store, and CLI/API exposure. Those adapters must remain read-only until separate mutation contracts and approvals are admitted.
