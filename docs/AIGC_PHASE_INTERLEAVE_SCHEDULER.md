# AIGC Phase Interleave Scheduler

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

The AIGC phase system is not a single-pass ladder.

It is an interleaved pipeline where phases 1 through 26 exist as canonical procedure slots, but selected phases can recur between other phases as guards, audits, approvals, verifications, security checks, quality checks, observability loops, and evolution loops.

```text
phase number = canonical capability
phase occurrence = a specific pass through that capability
```

So the pipeline can contain events like:

```text
phase14@before:phase6
phase5@before:phase6
phase9@after:phase25
phase20@after:phase26
phase8@after:phase6
```

This lets AIGC reason like an operating system, not like a checklist.

## Why This Exists

Some phases are naturally repeatable:

| Phase | Repeat Function |
|---|---|
| Phase 5 | Approval gate before authority changes. |
| Phase 7 | Audit packet after execution or artifact generation. |
| Phase 8 | Evolution loop after outcomes, failures, or review. |
| Phase 9 | Verification tribunal before gates and after sensitive stages. |
| Phase 10 | Connector governance before connector use. |
| Phase 11 | Security vault before secret-reference access. |
| Phase 12 | Observability after runs, failures, and artifacts. |
| Phase 14 | Runtime preflight before sensitive work. |
| Phase 16 | Compliance/legal review before external-facing work. |
| Phase 17 | Incident response after safety signals. |
| Phase 20 | Fidelity forge after drafts, plans, and work-order governance. |
| Phase 21 | Customer satisfaction scoring after proposal or fidelity review. |
| Phase 22 | Quality kernel after fidelity and work-order stages. |

## Pipeline Position

The intended order is now:

```text
AIGC trigger
  -> Phase 1 cognitive phase router
  -> Phase 2-24 continuity bridge
  -> Phase Interleave Scheduler
  -> Auto-Approval Gate Procurement
  -> MVP+++ procurement packet
  -> Phase 25 constellation classification
  -> Phase 26 refactor planning
  -> artifact upload
```

## What the Scheduler Emits

The scheduler writes:

- `data/phase_interleaves/aigc_phase_interleave_schedule.json`
- `reports/phase_interleave_scheduler_report.md`
- `data/audit/aigc_phase_interleave_scheduler_audit.jsonl`

Each schedule item contains:

| Field | Meaning |
|---|---|
| `occurrence_id` | Specific repeated phase occurrence, such as `phase14@before:phase6:7`. |
| `phase_id` | Canonical phase, such as `phase14`. |
| `phase_slot` | Numeric slot from 1 through 26. |
| `role` | Primary, before, after, intent-before, or intent-after. |
| `anchor_phase` | Phase this occurrence protects, checks, or follows. |
| `reason` | Why the occurrence exists. |
| `auto_executable_in_workflow` | Whether the workflow may run the stage directly. |

## Safety Boundary

The scheduler is a planner only.

It performs no:

- external action;
- physical file movement;
- source rewrite;
- workflow rewrite;
- credential use;
- secret-value logging.

It can only produce a schedule artifact and audit record.

## Local Run

```powershell
python .\src\phase_interleave_scheduler.py --project-root . --config config\aigc_phase_interleave_scheduler.json
```

## Short Form

```text
Phases are numbered.
Occurrences are alive.
The scheduler decides where the guardians recur.
```
