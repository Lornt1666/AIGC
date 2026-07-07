# AIGC Workbench Isolation

## Purpose

Workbench isolation lets AIGC plan ten or more simultaneous jobs without cross-contaminating state, evidence, artifacts, budgets, or approval status.

## Workspace Contract

Each work order workspace has:

- `workspace_id`
- `tenant_id`
- `work_order_id`
- `correlation_id`
- `data_classification`
- `budget_limits`
- `approval_state`
- `artifact_roots`
- `allowed_reference_ids`
- `external_action_performed`

## Isolation Rules

- workspace IDs must be unique;
- correlation IDs must be unique;
- artifact roots must not be reused;
- artifact roots must not traverse directories;
- external action remains false;
- a workspace cannot approve external action;
- budgets must include positive ceilings.

## Smoke Command

```powershell
python .\scripts\aigc_orchestration_cli.py workbench-smoke --count 10
```
