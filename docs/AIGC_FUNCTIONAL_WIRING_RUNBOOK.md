# AIGC Functional Wiring Runbook

## Purpose

This runbook describes the governed work-order execution slice added to AIGC.

The slice turns operator intent into a dry-run artifact packet with:

- a work-order packet;
- a governance decision;
- a blocked external-action permit scaffold;
- a human-visible approval packet;
- an artifact manifest;
- a validation receipt;
- an AIGC run receipt;
- an operator review report.

No live external action is performed.

## Primary Commands

```powershell
python .\src\aigc.py validate
python .\src\aigc.py run work-order --input .\config\example_work_order.json
python .\src\aigc.py run governance-smoke
python .\src\aigc.py run cockpit-smoke
```

Standalone dry-run surface:

```powershell
python .\src\work_order_cli.py work-order --input .\config\example_work_order.json
python .\src\work_order_cli.py governance-smoke
python .\src\work_order_cli.py cockpit-smoke
```

## Output Location

Default work-order artifacts are written under:

```text
reports/artifacts/work_orders/<work_order_id>/<correlation_id>/
```

Governance smoke artifacts are written under:

```text
reports/artifacts/governance_smoke/<work_order_id>/<correlation_id>/
```

Each run produces:

- `work_order_packet.json`
- `governance_decision.json`
- `external_action_permit.json`
- `approval_packet.json`
- `artifact_manifest.json`
- `validation_receipt.json`
- `aigc_run_receipt.json`
- `operator_review_report.md`

## Operating Flow

```text
Operator Intent
  -> Work Order Intake
  -> Schema Validation
  -> Risk + Domain Classification
  -> Governance Router
  -> Allowed Internal Execution
  -> Artifact Generation
  -> Contract Validation
  -> Run Receipt
  -> Operator Review
  -> Accept / Revise / Deny / Emergency Stop
```

## Safety Boundary

The work-order slice may prepare, classify, generate, validate, and summarize.

It may not:

- submit applications;
- send outreach;
- bid;
- invoice;
- accept contracts;
- purchase anything;
- use credentials;
- call live external APIs;
- move files outside the workspace;
- deploy production systems;
- log secrets;
- approve its own output.

## Operator Actions

After a run, open the generated approval packet or operator report.

Choose one:

- **Accept** only after reading the visible review packet.
- **Revise** if the artifact needs correction.
- **Deny** if the work should not proceed.
- **Emergency Stop** if the runtime should block downstream execution.

Acceptance only covers internal governed preparation unless a later reviewed PR implements a scoped external-action gateway.

## Validation

Recommended validation sequence:

```powershell
python .\src\aigc.py validate
python -m pytest tests\test_work_order_packet.py tests\test_governance_router.py tests\test_external_action_gateway.py tests\test_secret_references.py tests\test_approval_gate.py tests\test_aigc_functional_wiring.py
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md AIGC_MASTER_PROMPT.md OMEGA_X_CONSTITUTION.md schemas tests scripts .github
```

## Result

AIGC now has a real governed functional pathway:

**intent in, governed work out, evidence attached, human authority preserved.**
