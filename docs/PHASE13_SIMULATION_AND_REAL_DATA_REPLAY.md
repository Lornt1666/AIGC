# Phase 13 - Simulation and Real Data Replay

Phase 13 is the AIGC safety arena.

It has two modes:

- Phase 13A: synthetic non-production sandbox
- Phase 13B: real public read-only data replay

Phase 13B bridges the gap between synthetic simulation and the operational Phase 2 radar. It can retrieve real information from approved public/API/RSS sources, normalize/classify/score records, and export a replay file for Phase 3-style inspection.

It never applies, messages employers, bids, submits proposals, submits deliverables, uses credentials, or performs external execution.

Run synthetic sandbox:

```powershell
python .\src\phase13_simulation_arena.py
```

Run real read-only replay:

```powershell
python .\src\phase13_real_data_replay.py --source remoteok --limit 10
```

Allowed sources:

- `remoteok`
- `remotive`
- `weworkremotely`
- `github_issues`
