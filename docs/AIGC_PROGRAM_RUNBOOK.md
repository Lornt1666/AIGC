# AIGC Local Program Runbook

## Purpose

This runbook describes the local runnable AIGC operator program layer.

The local program gives the operator a practical path to run AIGC from a Windows computer while preserving governance controls.

## Active Phase 4/5 Hold

`config/phase2_to5_cycle_policy.json` is authoritative for the current cycle.
It permits only read-only review of existing Phase 4 inputs and archived,
expired Phase 5 packets plus one scoped internal improvement proposal. It
blocks local Phase 2–5 regeneration, packet acceptance, new workflow dispatch,
external contact, connector activation, and production activity.

Use the following read-only status commands:

```powershell
python .\src\aigc.py cycle-policy
python .\src\aigc.py curriculum
```

The Operator Cockpit reflects this hold by disabling its generation and packet
decision controls. Do not use another local surface to bypass it.

## Primary Launch Commands

```powershell
.\scripts\setup_aigc_local.ps1
.\RUN_AIGC_PROGRAM.bat
```

Alternative:

```powershell
.\scripts\run_aigc_program.ps1
```

## Core CLI Commands

```powershell
python .\src\aigc.py health --write
python .\src\aigc.py status
python .\src\aigc.py validate
python .\src\aigc.py run work-order --input .\config\example_work_order.json
python .\src\aigc.py run paycheque --input .\config\paycheque_workflow.json
python .\src\aigc.py run governance-smoke
python .\src\aigc.py run cockpit-smoke
```

## Program Surfaces

### Beginner Surface

- Double-click `RUN_AIGC_PROGRAM.bat`.

### Operator Surface

- Use `src/aigc.py` commands.

### Developer Surface

```powershell
python -m pytest
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md AIGC_MASTER_PROMPT.md OMEGA_X_CONSTITUTION.md schemas tests scripts .github
git diff --check
```

## Health Check

The health check verifies:

- Python version;
- standard imports;
- optional Streamlit availability;
- required files and folders;
- writable report path;
- emergency stop readability;
- external actions disabled by default.

Output path when `--write` is used:

```text
reports/artifacts/program_health/latest_program_health.json
```

## Local UI

The local UI is the Streamlit Operator Cockpit:

```powershell
python -m streamlit run .\src\dashboard\operator_cockpit_app.py
```

It includes governed work-order and paycheque pipeline surfaces inherited from the current main branch.

## Emergency Stop

Enable:

```powershell
python .\src\aigc.py emergency-stop
```

Clear:

```powershell
python .\src\aigc.py clear-emergency-stop
```

Runtime work is blocked while emergency stop is active.

## External Action Boundary

The local program does not:

- apply;
- submit;
- accept;
- pay;
- purchase;
- deploy;
- use credentials;
- retrieve secrets;
- bypass platform rules;
- approve itself.

## Manual Phase 6 / Phase 7 lifecycle

After a separately authorized native Phase 2–5 review workflow creates a fresh
packet, the operator may record its exact Phase 5 acceptance. Phase 6 then
creates a manual handoff only; the operator remains the external actor.

After the operator completes that handoff, record one exact confirmation with a
sanitized reference:

```powershell
python .\src\aigc.py confirm-manual-handoff `
  --execution-id AIGC-EXEC-... `
  --phrase "I, Justice Gray Maciocha, confirm manual handoff AIGC-EXEC-...." `
  --completion-reference "platform receipt reference"
```

This creates a Phase 6 confirmation record without storing secrets, marks the
authorization consumed for future handoff attempts, and unlocks only the
internal Phase 7 audit draft. It does not cause AIGC to contact or submit to
anyone.

## Production and connector boundary

Production remains locked. Do not activate a connector or deployment path until
the separate staging evidence, exact-revision release gate, required receipts,
and fresh candidate-bound operator approval are complete.

## Merge Readiness

This local program layer is ready only when:

- health check works;
- launchers exist;
- setup script is documented;
- tests pass;
- redaction scan is clean;
- CI passes;
- operator can run the program without guessing.
