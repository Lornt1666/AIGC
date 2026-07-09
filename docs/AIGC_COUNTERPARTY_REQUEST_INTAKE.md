# AIGC Counterparty Request Intake

## Purpose

AIGC must not accept, bid, submit, pay, purchase, deploy, message, or deliver against vague work.

Before any approval-gated external action can proceed, AIGC must show the operator what the other party is asking for.

This document defines the counterparty request intake gate.

## Core Rule

No external commitment may become proceed-capable unless the operator can see:

- who the counterparty is;
- where the request came from;
- what action is requested;
- what work is needed;
- what the expected outcome is;
- what deliverables are required;
- what acceptance criteria define success;
- what terms, pay, contract obligations, or costs apply;
- what deadline or timeline applies;
- what constraints, attachments, and prior communications exist;
- what information is still missing.

## Files

```text
config/counterparty_request_example.json
schemas/counterparty_request_packet.schema.json
schemas/counterparty_acceptance_review.schema.json
src/core/counterparty_request_intake.py
src/counterparty_request_intake_cli.py
```

## Command

```powershell
python .\src\counterparty_request_intake_cli.py --request .\config\counterparty_request_example.json
```

Output:

```text
reports/artifacts/counterparty_request_intake/<review_id>/counterparty_request_packet.json
reports/artifacts/counterparty_request_intake/<review_id>/counterparty_acceptance_review.json
reports/artifacts/counterparty_request_intake/<review_id>/counterparty_acceptance_review.md
```

## Decision States

### `insufficient_information`

The counterparty request is missing required fields.

Proceed is disabled.

### `blocked_pending_risk_review`

The request contains a hard-block risk or unsafe condition.

Proceed is disabled.

### `ready_for_operator_popup`

The request has enough information for the operator to review.

Proceed may be enabled in the popup layer.

### `ready_for_operator_popup_high_risk`

The request has enough information but involves acceptance, bid, payment, purchase, deploy, delivery, or another higher-risk action.

Proceed may be enabled only after enhanced review.

## Required Intake Fields

The acceptance gate checks for:

- `counterparty.name`
- `requested_action`
- `work_description.summary`
- `work_description.success_outcome`
- `deliverables`
- `acceptance_criteria`
- `terms.compensation`
- `terms.contract_obligations`
- `timeline.requested_deadline`

Placeholder values like `unknown`, `tbd`, or `not agreed yet` are treated as missing.

## Hard-Block Risk Examples

The intake gate flags language involving:

- bypassing platform rules;
- fabricated credentials;
- misrepresentation;
- unapproved credential use;
- self-approval.

## Professional Procedure

1. Capture the counterparty request.
2. Validate the request schema.
3. Build a visible acceptance summary.
4. Identify missing information.
5. Identify risk flags.
6. Decide whether Proceed can be enabled.
7. Write review artifacts.
8. Show the operator the exact work and terms before any external action.

## Operator Rule

If the request is vague, incomplete, risky, or unsupported by counterparty description, do not accept it.

Ask for clarification first.

AIGC must help the operator understand what is being accepted before any commitment is made.
