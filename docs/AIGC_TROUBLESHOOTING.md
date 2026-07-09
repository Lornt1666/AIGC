# AIGC Troubleshooting

## Start Here

Run:

```powershell
python .\src\aigc.py health --write
```

Review:

```text
reports/artifacts/program_health/latest_program_health.json
```

## Python Not Found

Install Python 3.10 or newer.

Then run:

```powershell
python --version
```

## Dependencies Missing

Run:

```powershell
python -m pip install -r requirements.txt
```

Or launch with dependency installation enabled:

```powershell
$env:AIGC_INSTALL_DEPENDENCIES="1"
.\scripts\run_aigc_program.ps1
```

## Streamlit Does Not Launch

Check whether Streamlit is installed:

```powershell
python -c "import streamlit; print('streamlit ok')"
```

Then run:

```powershell
python -m streamlit run .\src\dashboard\operator_cockpit_app.py
```

## Port Already In Use

Run on another port:

```powershell
.\scripts\run_aigc_program.ps1 -Port 8502
```

## Validation Fails

Run:

```powershell
python .\src\aigc.py validate
```

Read the failing artifact path and schema name. Fix the artifact or rerun the phase that generates it.

## Emergency Stop Is Active

Check status:

```powershell
python .\src\aigc.py status
```

Clear only after review:

```powershell
python .\src\aigc.py clear-emergency-stop
```

## Paycheque Pipeline Does Not Generate

Run:

```powershell
python .\src\aigc.py run paycheque --input .\config\paycheque_workflow.json
```

Confirm the config keeps all commit actions false:

```text
auto_apply=false
auto_submit=false
auto_accept=false
auto_pay=false
auto_purchase=false
auto_deploy=false
```

## Work Order Does Not Generate

Run:

```powershell
python .\src\aigc.py run work-order --input .\config\example_work_order.json
```

Artifacts should appear under:

```text
reports/artifacts/work_orders/
```

## Security Scan

Run:

```powershell
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md AIGC_MASTER_PROMPT.md OMEGA_X_CONSTITUTION.md schemas tests scripts .github
```

If findings appear, remove the unsafe value and rerun.

## Boundary Reminder

AIGC prepares. The operator commits externally.

AIGC must not submit, apply, accept, pay, purchase, deploy, use credentials, or self-approve.
