# AIGC Orchestration Fabric

## Purpose

The AIGC orchestration fabric is a local dry-run coordination layer. It creates workflow definitions, orchestration events, workflow execution records, and local reports without executing external actions.

## Boundary

The fabric may:

- list approved local workflow candidates;
- emit fixture events;
- run dry-run workflow simulations;
- validate n8n placeholder templates;
- create local reports under `reports/orchestration/`;
- prove workbench isolation for ten or more jobs.

The fabric may not:

- call live webhooks;
- send email or messages;
- submit work;
- deploy services;
- publish releases;
- procure or purchase;
- perform client delivery;
- read secret values;
- self-approve external actions.

## First Six Workflows

1. `intake_to_work_order`
2. `action_permit_approval_queue`
3. `regression_guard_check`
4. `evidence_pack_refresh`
5. `actor_execution_dry_run`
6. `delivery_draft`

Each workflow defaults `external_action_allowed` to false.

## Runtime Commands

```powershell
python .\scripts\aigc_orchestration_cli.py list-workflows
python .\scripts\aigc_orchestration_cli.py validate-n8n-templates
python .\scripts\aigc_orchestration_cli.py dry-run --workflow intake_to_work_order
python .\scripts\aigc_orchestration_cli.py workbench-smoke --count 10
python .\scripts\aigc_orchestration_cli.py orchestration-smoke
```

## Next Safe Evolution

The next implementation layer is the Live Action Gateway. It must remain separate from this fabric and require live action request, permit, allowlist, idempotency, kill-switch, and result audit records.
