# Increment 3 — Canonical Read-Only Projection

Status: **Implemented on PR #153; operational validation pending CI**

## Scope

Increment 3 connects Ω Mission OS to:

- the canonical phase registry;
- canonical Quest persistence through SQLite immutable read-only mode;
- the existing AIGC contract validator;
- a bounded command-line projection;
- a separate GET-only FastAPI projection surface.

## Authority boundary

The projection layer does not initialize or migrate the Quest database. SQLite is opened with `mode=ro&immutable=1`. A missing database is not created. No route or command can create, qualify, approve, transition, execute, deliver, spend, message, deploy, or mutate canonical state.

## Validation sequence

1. Load the mission artifact from a repository-confined path.
2. Validate it against `schemas/mission.schema.json` through `src/core/contract_validator.py`.
3. Read allowlisted phase artifacts.
4. Project the canonical phase registry without executing any registered command.
5. Read Quest records from the canonical `records` table in immutable read-only mode.
6. Compose the mission snapshot.
7. Validate the snapshot against `schemas/mission_snapshot.schema.json`.
8. Return or print the projection without writing canonical state.

## CLI

```bash
python -m src.mission_os.cli \
  --root . \
  --mission config/mission.example.json \
  --database .aigc/local_operator.sqlite3
```

The CLI prints JSON to standard output only.

## API

```bash
uvicorn src.mission_os.api:app --host 127.0.0.1 --port 8010
```

Registered projection routes:

- `GET /health`
- `GET /api/v1/mission/snapshot`

No POST, PUT, PATCH, or DELETE mission routes are registered.

## Projection content

The snapshot includes:

- validated mission state;
- allowlisted source status and digests;
- registered phases and artifact availability;
- canonical Quest lifecycle projections;
- task progress;
- blockers and pending approvals;
- verified versus estimated revenue;
- provenance and warnings;
- explicit `external_action_performed: false`;
- explicit `canonical_state_mutated: false`.

## Tests

```bash
python -m unittest tests.test_mission_director tests.test_mission_projection
```

Tests verify database-byte immutability, missing-database non-creation, Quest projection, phase projection, contract validation markers, and GET-only API routing.

## Deferred

Increment 3 does not add dashboard mutation, scheduled execution, connector writes, mission-state persistence, approval consumption, or external action. Those capabilities require separate contracts, threat review, accountable authorization, and execution evidence.
