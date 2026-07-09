# AIGC Paycheque Workflow Procurement

## Purpose

The Paycheque Workflow is the governed **Get Me Closer to a Paycheque** capability.

It maximizes automation of thinking, ranking, drafting, and organizing while preserving the operator as the only party who can commit externally.

## Architecture Overview

| Layer | Role |
| --- | --- |
| UI buttons | Operator triggers and approves actions. |
| Workflow engine | Orchestrates steps and enforces no-auto-commit rules. |
| AI assistant layer | Drafts content, ranks work, and structures the pipeline. |
| Integration layer | Opens links and prepares copyable text, never submits. |
| Audit and policy | Logs intent and enforces constraints. |

## Core Guardrails

The system must not:

- auto-apply;
- auto-submit;
- auto-accept;
- auto-pay;
- auto-purchase;
- auto-deploy;
- auto-use credentials;
- log secrets;
- impersonate anyone;
- bypass platform rules;
- bypass human approval;
- approve itself;
- treat symbolic language as authority.

The system may:

- read approved API/export/manual data;
- rank opportunities;
- draft proposals;
- draft milestone notes;
- draft invoice/payment notes;
- produce a dashboard payload;
- expose review/copy/open/mark-done controls;
- generate audit receipts.

## Main Function

```python
def prepare_paycheque_workflow(user_profile, platforms):
    ...
```

Implemented in:

```text
src/core/paycheque_workflow.py
```

CLI:

```powershell
python .\src\paycheque_workflow_cli.py --input .\config\paycheque_workflow.json
python .\src\aigc.py run paycheque --input .\config\paycheque_workflow.json
```

## Daily Loop

1. Operator clicks or runs `GenerateDailyPipeline`.
2. AIGC prepares opportunities, contract tasks, and payment actions.
3. AIGC ranks by expected payoff score.
4. AIGC drafts copyable text.
5. Operator reviews each item.
6. Operator opens the platform manually.
7. Operator pastes text manually.
8. Operator clicks platform Submit, Apply, Accept, Pay, or Deploy manually if appropriate.
9. Operator marks the item complete internally.

## Dashboard Buttons

The safe buttons are:

- `ReviewDraft`
- `CopyText`
- `OpenPlatformLink`
- `MarkCompletedInternalOnly`

The unsafe buttons remain unavailable:

- `Submit`
- `Apply`
- `Accept`
- `Pay`
- `Purchase`
- `Deploy`

## Output Artifacts

The workflow writes under:

```text
reports/artifacts/paycheque_pipeline/<pipeline_id>/
```

Generated files:

- `paycheque_pipeline.json`
- `paycheque_pipeline.md`
- `paycheque_audit_receipt.json`

## Human-in-the-Loop Law

AIGC can bring the operator closer to a paycheque by doing the thinking and drafting.

AIGC cannot cross the money/action boundary.

The operator always performs external commitment manually.

## Safety Boundary

The Paycheque Workflow is internal preparation only. It performs no live external action, no credential use, no payment action, no purchase, no contract acceptance, and no deployment.
