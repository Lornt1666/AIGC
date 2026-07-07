# AIGC Orchestration Security Boundary

## Security Rule

The orchestration fabric is a local control plane, not a live connector layer.

## Required Blocks

- no live webhooks;
- no credential values;
- no external sends;
- no deployment;
- no publishing;
- no procurement;
- no account modification;
- no client delivery.

## Template Scanning

The validator checks n8n templates for:

- literal URLs;
- local machine paths;
- credential blocks;
- secret-like values;
- enabled external action nodes;
- missing dry-run mode;
- missing correlation fields.

## Kill Switch Position

The current fabric does not execute live actions. A future Live Action Gateway must check the runtime emergency stop before any connector attempt.
