# AIGC Auto-Approval Gate Procurement

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

Auto-approval gates are not blind permission.

They are automatic policy classifiers inside the AIGC pipeline:

```text
stage request
  -> classify risk
  -> compare against gate policy
  -> auto-pass safe internal artifact stages
  -> require human review for elevated authority
  -> auto-deny forbidden actions
  -> write packet, report, and audit ledger
```

## What Can Auto-Pass

Auto-pass is limited to internal, non-destructive, non-external artifact work:

- internal metadata classification;
- internal artifact generation;
- internal report generation;
- schema validation;
- read-only repository cartography;
- proposal-only refactor planning;
- continuity ledger generation;
- procurement intent recording.

## What Requires Human Review

Human review is required for anything that changes authority or touches sensitive boundaries:

- external action request;
- physical file move request;
- source rewrite request;
- workflow rewrite request;
- credential access request;
- secret reference use request;
- approval gate state change;
- behavior change patch;
- connector write enablement.

## What Is Auto-Denied

The gate auto-denies:

- raw secret value logging;
- credential exfiltration;
- unscoped external action;
- unapproved identity use;
- bypassing human approval;
- delete without review;
- payment or spend without approval;
- live message send without approval.

## Pipeline Position

The intended order is:

```text
AIGC trigger
  -> Phase 1 cognitive phase router
  -> Phase 2-24 continuity bridge
  -> Auto-Approval Gate Procurement
  -> MVP+++ procurement packet
  -> Phase 25 constellation classification
  -> Phase 26 refactor planning
  -> artifact upload
```

## Outputs

The auto-approval gate stage writes:

- `data/auto_approval_gates/aigc_auto_approval_gate_packet.json`
- `reports/auto_approval_gate_procurement_report.md`
- `data/audit/aigc_auto_approval_gate_audit.jsonl`

## Local Run

```powershell
python .\src\auto_approval_gate_procurement.py --project-root . --config config\aigc_auto_approval_gates.json
```

## Safety Boundary

The gate itself performs no external action, file movement, source rewrite, workflow rewrite, credential use, or secret logging.

It can only produce decisions:

```text
auto_pass_internal_only
human_review_required
auto_deny
```

## Short Form

```text
Auto-approval gates approve paperwork, not power.
They pass the harmless.
They escalate the risky.
They deny the forbidden.
```
