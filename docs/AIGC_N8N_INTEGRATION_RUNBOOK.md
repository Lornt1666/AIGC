# AIGC n8n Integration Runbook

## Status

The current n8n integration is template-only and dry-run-only.

## Template Rules

Every n8n template must:

- contain no credential block;
- contain no live endpoint value;
- contain no production URL;
- contain no local machine path;
- include AIGC correlation fields;
- mark dry-run mode true;
- mark external action nodes disabled;
- include a human approval wait-step placeholder.

## Required Correlation Fields

- `workflow_execution_id`
- `audit_event_id`
- `work_order_id`
- `action_permit_id`
- `requires_human_approval`
- `external_action_performed`

## Validation

```powershell
python .\scripts\aigc_orchestration_cli.py validate-n8n-templates
```

## Live Use

Live n8n use is not approved by this runbook. A future live owner-controlled webhook probe requires a separate Live Action Gateway and explicit permit.
