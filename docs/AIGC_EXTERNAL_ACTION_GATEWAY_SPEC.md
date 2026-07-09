# AIGC External Action Gateway Specification

## Purpose

The external-action gateway is a blocked-by-default scaffold.

It records whether a work order requests outward movement, but it does not execute anything externally.

Implemented in:

- `src/core/work_order.py`
- `schemas/external_action_permit.schema.json`
- `tests/test_external_action_gateway.py`

## Current State

For this sprint:

```json
{
  "live_execution_allowed": false,
  "external_action_performed": false
}
```

This is true even when `external_action_intent` is `proposed` or `required`.

## Permit States

If no external action is requested:

```text
not_requested_blocked_by_default
```

If external action is requested:

```text
blocked_pending_future_review
```

## Future Controls Required Before Live Execution

A future PR must implement and test all of the following before any external action can be considered:

- external action schema
- permit schema
- authority scope
- revocation path
- dry-run mode
- audit logging
- operator confirmation
- platform terms review
- rate limits
- rollback or stop control
- blocked-by-default tests

## What The Gateway Blocks

- sending messages
- submitting applications
- placing bids
- accepting contracts
- dispatching invoices
- using credentials
- changing accounts
- posting content
- calling live write APIs
- deploying production infrastructure
- moving files outside the workspace

## Review Law

AIGC may prepare a proposed action packet.

AIGC may not execute the proposed action.

Human approval is necessary but not sufficient until a live gateway exists with scoped authority and tests.

## Regression Evidence

`tests/test_external_action_gateway.py` proves:

- requested external actions remain blocked;
- non-requested actions still keep the gateway disabled;
- no live execution flag is enabled;
- no external action is reported as performed.
