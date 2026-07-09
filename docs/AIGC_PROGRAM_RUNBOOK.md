# AIGC Local Program Runbook

## Purpose

This runbook describes the local runnable AIGC operator program layer.

The local program gives the operator a practical path to run AIGC from a Windows computer while preserving governance controls.

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

## Merge Readiness

This local program layer is ready only when:

- health check works;
- launchers exist;
- setup script is documented;
- tests pass;
- redaction scan is clean;
- CI passes;
- operator can run the program without guessing.
