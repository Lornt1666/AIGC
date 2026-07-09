# AIGC Operator Acceptance Protocol

## Purpose

This protocol defines how the operator reviews a governed work-order packet.

The work-order slice creates approval packets for internal preparation only. It does not approve external execution.

## Decision Options

After reviewing the generated packet, the operator may choose:

1. **Accept**
   - acknowledges the visible packet;
   - authorizes internal governed preparation only;
   - does not perform external action.

2. **Revise**
   - records required changes;
   - keeps the work order blocked from downstream acceptance.

3. **Deny**
   - rejects the packet;
   - keeps the work order from proceeding.

4. **Emergency Stop**
   - blocks runtime phase execution until cleared.

## Exact Phrase Rule

Each approval packet contains a required phrase.

The operator must type the exact phrase to accept.

The system must not auto-fill or self-submit the phrase.

## Self-Approval Rule

AIGC may generate an approval packet.

AIGC may not approve it.

Every generated approval packet records:

```json
{
  "approved": false,
  "self_approval_allowed": false,
  "external_action_performed": false
}
```

## What Acceptance Does Not Do

Acceptance does not:

- send a message;
- submit an application;
- post content;
- bid;
- invoice;
- accept a contract;
- use credentials;
- call a live external API;
- deploy infrastructure;
- log a secret;
- bypass platform rules.

## Review Checklist

Before accepting, verify:

- title and objective match operator intent;
- classification is reasonable;
- risk findings are visible;
- blocked operations remain blocked;
- external action permit is disabled;
- artifact manifest has hashes;
- validation receipt is clean;
- no raw secrets appear;
- desired output matches the work order;
- acceptance criteria are represented.

## Commands

Run a governed work order:

```powershell
python .\src\aigc.py run work-order --input .\config\example_work_order.json
```

Enable emergency stop:

```powershell
python .\src\aigc.py emergency-stop
```

Clear emergency stop:

```powershell
python .\src\aigc.py clear-emergency-stop
```

## Evidence

Regression tests cover:

- exact phrase visibility;
- no self-approval;
- no external action;
- symbolic layers granting no authority;
- blocked gateway state.
