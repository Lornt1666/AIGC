# AIGC Next Steps Coordination

## Purpose

This document coordinates the next responsible steps for PR #22 and the AIGC local-operator program path.

The goal is to move from a draft implementation packet into a runnable, reviewable, merge-ready, local program workflow without weakening the safety boundary.

## Current Packet

Active pull request:

```text
PR #22: feat(aigc): wire governed work-order and paycheque pipeline
Branch: codex/governed-work-order-execution-slice
Base: main
Status: draft
```

Implemented capabilities:

- governed work-order execution slice;
- paycheque pipeline preparation;
- blocked external-action permit scaffold;
- secret-reference-only handling;
- exact human-review approval packet path;
- cockpit tabs for New Work Order and Paycheque Pipeline;
- schema contracts;
- regression tests;
- implementation runbooks.

## Operating Law

AIGC prepares the path. The operator crosses the threshold.

AIGC may:

- find or ingest approved/read-only/exported opportunity data;
- rank opportunities, contracts, and payment actions;
- draft proposals, milestone notes, and invoice notes;
- produce artifact packets and audit receipts;
- show review/copy/open/mark-done controls;
- validate schemas;
- run smoke checks.

AIGC may not:

- auto-apply;
- auto-submit;
- auto-accept;
- auto-pay;
- auto-purchase;
- auto-deploy;
- auto-use credentials;
- log secrets;
- bypass platform rules;
- approve itself;
- treat symbolic language as authority.

## Ordered Next Steps

### Step 1 - Review PR #22

Operator/developer review:

```powershell
python .\src\aigc.py validate
python .\src\aigc.py run work-order --input .\config\example_work_order.json
python .\src\aigc.py run paycheque --input .\config\paycheque_workflow.json
python .\src\aigc.py run governance-smoke
python .\src\aigc.py run cockpit-smoke
python -m pytest
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md AIGC_MASTER_PROMPT.md OMEGA_X_CONSTITUTION.md schemas tests scripts .github
git diff --check
```

Exit criteria:

- CI passes;
- local validation passes or failures are documented;
- no secrets are detected;
- no external action is enabled;
- operator understands the cockpit path.

### Step 2 - Mark PR #22 Ready Only After Review

Do not merge while still uncertain.

Ready criteria:

- PR body accurately describes behavior;
- generated files are explainable;
- tests pass;
- work-order and paycheque pipeline commands run;
- cockpit opens;
- safety boundary remains intact.

### Step 3 - Merge PR #22 After Operator Approval

Merge only after explicit operator approval.

Recommended merge style:

```text
squash or merge commit according to repo preference
```

Do not auto-merge without operator instruction.

### Step 4 - Begin Local Runnable Program Finishing PR

Create a new branch after PR #22 is merged:

```powershell
git switch main
git pull --ff-only
git switch -c codex/finish-local-aigc-program
```

Target PR title:

```text
feat(aigc): finish local runnable operator program
```

Required scope:

- `RUN_AIGC_PROGRAM.bat`;
- `scripts/run_aigc_program.ps1`;
- `scripts/setup_aigc_local.ps1`;
- `src/core/program_health.py`;
- `src/program_health_cli.py`;
- `python .\src\aigc.py health`;
- artifact browser tab;
- validation tab;
- settings tab;
- emergency-stop status panel;
- Windows desktop setup documentation;
- launcher tests;
- program health tests.

### Step 5 - Keep Live External Action Blocked

Any live gateway must be a separate future PR.

Required before live gateway:

- external action schema;
- authority scope;
- platform terms review;
- rate limits;
- revocation path;
- audit logging;
- emergency stop;
- dry-run proof;
- no-secret logging;
- explicit human approval;
- tests proving blocked-by-default behavior.

## Button-Level Product Path

The target user loop is:

1. Open AIGC locally.
2. Click `GenerateDailyPipeline`.
3. Review opportunities, contracts, and invoice/payment drafts.
4. Click `ReviewDraft`.
5. Click `CopyText`.
6. Click `OpenPlatformLink`.
7. Manually paste and manually submit/apply/accept/pay only if appropriate.
8. Click `MarkCompletedInternalOnly` inside AIGC.
9. Review audit receipt.

## Coordination Summary

The proper sequence is:

```text
PR #22 review -> mark ready -> operator-approved merge -> local runnable program PR -> health/setup/launcher/cockpit polish -> future live gateway only if explicitly approved
```

AIGC must remain powerful in preparation and humble in authority.
