# AIGC External Action Processes and Procedures

## Purpose

This SOP defines the professional process for approval-gated external actions.

It exists because some external actions can be automated only after operator review and explicit approval, while other actions must remain permanently blocked.

## Scope

This SOP applies to approval-gated actions such as:

- apply;
- submit;
- accept;
- pay;
- purchase;
- deploy;
- bid;
- message;
- deliver work after operator review.

It does not authorize hard-blocked actions.

## Permanent Hard Blocks

AIGC must not:

- use credentials without a reviewed integration;
- bypass platform rules;
- fabricate credentials;
- self-approve;
- externally deliver work without operator review.

These are not approval-gated. They are blocked.

## Procedure Stages

Every external-action procedure packet follows these stages:

1. Action intake.
2. Eligibility review.
3. Platform terms review.
4. Truthfulness review.
5. Credential and secret review.
6. Operator popup review.
7. Operator Proceed decision.
8. Execution handoff.
9. Audit receipt.
10. Post-action review.

High-risk actions add specialized stages for money, contracts, deployment, or delivery quality.

## Popup Requirements

The local popup must display:

- exact action;
- exact destination;
- exact payload or payload hash;
- cost, price, bid, contract, or deployment obligations where relevant;
- platform terms status;
- risk class;
- rollback or correction plan;
- Cancel button;
- Proceed button.

For hard-blocked actions, Proceed is disabled.

## Separation of Duties

AIGC may:

- prepare;
- draft;
- recommend;
- build the popup;
- build the procedure packet;
- write the audit receipt.

AIGC may not:

- approve itself;
- hide payloads;
- hide destination;
- bypass terms;
- use unreviewed credentials;
- fabricate facts;
- execute without operator approval.

The operator must review and approve the exact action.

## Command

Build a professional procedure packet:

```powershell
python .\src\external_action_procedures_cli.py --action message --destination "manual-review" --payload-json "{\"message\":\"Draft only\"}"
```

Output path:

```text
reports/artifacts/external_action_procedures/<procedure_packet_id>/
```

Generated files:

- `external_action_procedure_packet.json`
- `external_action_procedure_report.md`

## Professional Standard

No external action should proceed until all of these are true:

- action is allowed by policy;
- platform terms or authorization are reviewed;
- payload is truthful;
- destination is exact;
- cost or obligations are visible;
- rollback/correction plan exists where relevant;
- operator popup is shown;
- operator clicks Proceed;
- audit receipt is prepared.

## Current Boundary

This PR procures the procedure layer and popup packets. It still does not execute external actions.

Actual live execution requires a future reviewed connector PR with official integrations, scoped permissions, secret-broker controls, tests, and audit receipts.
