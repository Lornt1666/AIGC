# AIGC Approval-Gated External Actions

## Purpose

This specification converts the operator request into a safe implementation model:

> AIGC may prepare external actions and show a local popup with exact action details and a `Proceed` button, but only lawful, platform-compliant, reviewed actions may ever proceed.

Some requested actions can be approval-gated.

Some requested actions must remain hard-blocked.

## Approval-Gated Possible Actions

These actions can be designed as operator-approved automations only after controls exist:

- apply
- submit
- accept
- pay
- purchase
- deploy
- bid
- message
- deliver work after operator review

Required common controls:

- exact action preview;
- exact destination preview;
- risk classification;
- platform terms status;
- cost/contract terms when relevant;
- rollback or correction plan when relevant;
- audit receipt;
- local popup;
- operator clicks `Proceed`;
- emergency stop remains available;
- no self-approval.

## Hard-Blocked Actions

These remain blocked even if a prompt requests them:

- use credentials without reviewed integration;
- bypass platform rules;
- fabricate credentials;
- self-approve;
- externally deliver work without operator review.

## Why They Are Blocked

### Unreviewed credential use

Credentials require official integration design, least privilege, secret broker, audit logging, revocation, and explicit operator approval.

### Platform-rule bypass

AIGC must not bypass platform terms, access controls, anti-abuse systems, or workflow restrictions.

### Fabricated credentials

AIGC must not invent education, certifications, licenses, work history, identity facts, portfolio claims, or completion state.

### Self-approval

AIGC cannot approve its own external actions.

### Delivery without operator review

External delivery requires operator review of the deliverable, destination, quality evidence, and risk state.

## Current Implementation

Files:

```text
config/approval_gated_external_actions.json
schemas/approval_gated_external_action_policy.schema.json
src/core/approval_gated_external_actions.py
src/approval_gated_external_actions_cli.py
```

Smoke command:

```powershell
python .\src\approval_gated_external_actions_cli.py smoke
```

Popup packet example:

```powershell
python .\src\approval_gated_external_actions_cli.py build-popup --action message --destination "manual-review" --payload-json "{\"message\":\"Draft only\"}"
```

## Product Direction

The future cockpit UI should display:

- title: `AIGC External Action Review`;
- exact action;
- exact recipient/destination;
- exact payload;
- cost or contract obligations;
- platform terms status;
- risk class;
- rollback/correction plan;
- `Cancel` button;
- `Proceed` button.

For hard-blocked actions, the `Proceed` button must be disabled.

## Core Rule

AIGC may automate execution only after explicit operator approval and only when the action is lawful, truthful, authorized, and platform-compliant.

AIGC must never automate deception, rule-bypass, credential misuse, or self-approval.
