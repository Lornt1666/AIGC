# AIGC Windows Desktop Setup

## Purpose

This guide explains how to run AIGC as a local Windows operator program.

The supported default mode is:

```text
BAT/PowerShell launcher + Python virtual environment + local Streamlit cockpit
```

No cloud deployment, credentials, production secret access, or external platform automation is required.

## Requirements

- Windows 10 or newer
- Python 3.10 or newer
- PowerShell
- Local copy of the `Lornt1666/AIGC` repository

Optional:

- Git
- GitHub Desktop
- VS Code

## First-Time Setup

From the repository root, run:

```powershell
.\scripts\setup_aigc_local.ps1
```

This will:

- verify Python;
- create `.venv` if missing;
- install requirements;
- run the local health check;
- run contract validation;
- run governance and cockpit smoke checks;
- run tests unless `-SkipTests` is supplied.

## Launch AIGC

Double-click:

```text
RUN_AIGC_PROGRAM.bat
```

Or run:

```powershell
.\scripts\run_aigc_program.ps1
```

The launcher runs:

```powershell
python .\src\aigc.py health --write
python -m streamlit run .\src\dashboard\operator_cockpit_app.py
```

## Safe Mode

Safe mode is enabled by default:

```text
AIGC_SAFE_MODE=1
```

Safe mode means:

- no live external action;
- no credential use;
- no secret retrieval;
- no platform submit/apply/accept/pay/purchase/deploy automation;
- no self-approval.

## Install Dependencies On Launch

If dependencies are missing, run:

```powershell
$env:AIGC_INSTALL_DEPENDENCIES="1"
.\scripts\run_aigc_program.ps1
```

Or in Command Prompt:

```cmd
set AIGC_INSTALL_DEPENDENCIES=1
RUN_AIGC_PROGRAM.bat
```

## Change Port

PowerShell:

```powershell
.\scripts\run_aigc_program.ps1 -Port 8502
```

Command Prompt:

```cmd
set AIGC_PROGRAM_PORT=8502
RUN_AIGC_PROGRAM.bat
```

## Desktop Shortcut

1. Right-click `RUN_AIGC_PROGRAM.bat`.
2. Choose **Create shortcut**.
3. Move the shortcut to Desktop.
4. Rename it to `AIGC Operator Program`.
5. Double-click it to launch.

## Troubleshooting

Run:

```powershell
python .\src\aigc.py health --write
```

Then review:

```text
reports/artifacts/program_health/latest_program_health.json
```

Common fixes:

- Python missing: install Python 3.10+.
- Streamlit missing: run `python -m pip install -r requirements.txt`.
- Validation failure: run `python .\src\aigc.py validate` and inspect the failing schema path.
- Emergency stop active: run `python .\src\aigc.py clear-emergency-stop` only if you understand why it was enabled.

## Boundary

AIGC prepares work. The operator commits externally.

AIGC must not click external Submit, Apply, Accept, Pay, Purchase, or Deploy buttons.
