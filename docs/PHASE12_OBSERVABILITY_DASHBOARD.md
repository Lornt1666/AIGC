# Phase 12 - Observability Dashboard

Phase 12 is the AIGC command tower. It watches local AIGC health without performing external actions.

It monitors:

- audit logs
- Omega-X memory events
- phase artifacts
- approval packets
- execution receipts
- employer audit packet drafts
- evolution patch logs
- secret manifest policy
- secret-like patterns in unsafe files

Health states:

- `green`: healthy
- `yellow`: caution, incomplete telemetry, pending approval, or pending work
- `red`: critical issue such as secret-like findings or missing required security manifests

Run:

```powershell
python .\src\phase12_observability_dashboard.py --export
```

Outputs:

- `data/phase12_observability/system_snapshot.json`
- `reports/phase12_system_health.md`

Phase 12 never sends proposals, applies to jobs, accesses raw secrets, approves actions, changes audit history, or applies evolution patches.
