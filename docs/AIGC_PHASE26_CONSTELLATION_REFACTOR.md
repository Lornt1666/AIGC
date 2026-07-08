# AIGC Phase 26 Constellation Refactor Planner

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

Phase 26 instantiates the responsible next step after Phase 25.

Phase 25 maps the repository into the AIGC constellation. Phase 26 takes that map and produces a refactor plan that explains where files could live in a future constellation structure, what should remain in place, and what requires dependency review before any physical movement.

```text
Phase 25: classify the repo
Phase 26: propose the refactor
Future PR: perform reviewed physical moves
```

Phase 26 is deliberately not a mover. It is a planner, judge, and risk sentinel.

## Operating Sequence

```text
python .\src\aigc.py run phase25
python .\src\aigc.py run phase26
```

Or directly:

```powershell
python .\src\phase25_constellation_fabric.py --project-root . --config config\phase25_constellation_fabric.json --force-local
python .\src\phase26_constellation_refactor.py --project-root . --config config\phase26_constellation_refactor.json
```

Phase 26 reads:

- `data/phase25_constellation/aigc_phase25_constellation_manifest.json`

Phase 26 writes:

- `data/phase26_constellation_refactor/aigc_phase26_refactor_plan.json`
- `reports/phase26_constellation_refactor_report.md`
- `data/audit/aigc_phase26_audit.jsonl`

## What Phase 26 Decides

For each file in the Phase 25 manifest, Phase 26 creates a proposal containing:

| Field | Meaning |
|---|---|
| `source_path` | Current repository path. |
| `proposed_target_path` | Conceptual constellation target path. |
| `constellation_zone` | Operational zone assigned by Phase 25. |
| `ontology` | What kind of artifact the file is. |
| `taxonomy` | Artifact family or class. |
| `methodology` | Process lane supported by the file. |
| `agent_lane` | Agent that should own or inspect the file. |
| `risk_level` | Low, medium, high, or critical. |
| `proposed_action` | Move candidate, retained in place, or blocked until review. |
| `blockers` | Dependency, workflow, documentation, generated-artifact, or security blockers. |

## Responsible Physical Refactor Doctrine

The doctrine is:

```text
classification before relocation
proposal before mutation
review before movement
imports before commit
workflow safety before merge
```

A file should not be physically moved until the future refactor PR proves:

1. Python imports still work.
2. GitHub workflows still point to valid paths.
3. README and docs links still resolve.
4. Schema references still match artifact names.
5. Generated data lineage is preserved.
6. Secret-adjacent files are not exposed or renamed into unsafe locations.
7. Tests, validation, and reports are updated.

## Safety Boundary

Phase 26 obeys:

```text
external_action_allowed = false
physical_file_moves_allowed = false
source_rewrite_allowed = false
workflow_rewrite_allowed = false
credential_use_allowed = false
secret_value_logging_allowed = false
approval_required_for_future_write_back = true
```

So the agent constellation can now articulate the proper structure without silently altering the body of the repo.

## Agent Responsibilities

| Agent | Responsibility |
|---|---|
| Constellation Cartographer | Converts zones into target paths. |
| Dependency Sentinel | Flags imports, workflows, docs, and generated lineage risk. |
| Security Governor | Blocks secret-adjacent movement until manual review. |
| Audit Archivist | Writes the plan, report, and audit ledger. |

## Promotion Rule

Phase 26 output may become physical movement only through a separate reviewed PR.

That future PR should use the Phase 26 plan as a ledger, not as a command to blindly execute.

## Short Form

```text
Phase 25 names the stars.
Phase 26 draws the migration chart.
A future approved PR moves the ships.
```
