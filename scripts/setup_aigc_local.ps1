param(
    [switch]$SkipVenv,
    [switch]$SkipTests,
    [switch]$ForceRecreateVenv
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Invoke-AigcStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host ""
    Write-Host "=== $Name ==="
    try {
        & $Action
        if ($LASTEXITCODE -ne 0) {
            throw "$Name exited with code $LASTEXITCODE"
        }
        Write-Host "PASS: $Name"
    }
    catch {
        Write-Error "FAIL: $Name`n$($_.Exception.Message)"
        Write-Host "Recovery: review the first failing step above; later steps were not trusted or executed."
        exit 1
    }
}

Write-Host "AIGC MVP+++ local setup and verification"
Write-Host "Repository: $RepoRoot"

$SystemPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $SystemPython) {
    throw "Python was not found. Install Python 3.10 or newer, reopen PowerShell, and rerun this script."
}

& $SystemPython.Source --version
if ($LASTEXITCODE -ne 0) {
    throw "Python exists but could not execute."
}

$PythonExe = $SystemPython.Source
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not $SkipVenv) {
    if ($ForceRecreateVenv -and (Test-Path ".venv")) {
        Write-Host "Removing existing .venv..."
        Remove-Item -Recurse -Force ".venv"
    }

    if (-not (Test-Path $VenvPython)) {
        Invoke-AigcStep -Name "Create virtual environment" -Action {
            & $SystemPython.Source -m venv .venv
        }
    }

    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment creation completed without producing $VenvPython"
    }

    $PythonExe = $VenvPython
    Write-Host "Using isolated interpreter: $PythonExe"
}
else {
    Write-Host "Using system interpreter because -SkipVenv was supplied: $PythonExe"
}

Invoke-AigcStep -Name "Show selected Python" -Action {
    & $PythonExe --version
}

Invoke-AigcStep -Name "Upgrade pip" -Action {
    & $PythonExe -m pip install --upgrade pip
}

Invoke-AigcStep -Name "Install reviewed dependencies" -Action {
    & $PythonExe -m pip install -r requirements.txt
}

Invoke-AigcStep -Name "Program health check" -Action {
    & $PythonExe .\src\aigc.py health --write
}

Invoke-AigcStep -Name "Contract validation" -Action {
    & $PythonExe .\src\aigc.py validate
}

Invoke-AigcStep -Name "Governance smoke" -Action {
    & $PythonExe .\src\aigc.py run governance-smoke
}

Invoke-AigcStep -Name "Cockpit smoke" -Action {
    & $PythonExe .\src\aigc.py run cockpit-smoke
}

Invoke-AigcStep -Name "Security and Privacy Wiring Gate" -Action {
    & $PythonExe .\src\security_privacy_wiring_cli.py --request .\config\counterparty_request_example.json
}

Invoke-AigcStep -Name "Agent Operating Doctrine" -Action {
    & $PythonExe .\src\agent_operating_doctrine_cli.py
}

if (-not $SkipTests) {
    Invoke-AigcStep -Name "Full test suite" -Action {
        & $PythonExe -m pytest -q
    }
}

Write-Host ""
Write-Host "AIGC MVP+++ setup and verification completed successfully."
Write-Host "Launch: .\RUN_AIGC_PROGRAM.bat"
Write-Host "Direct PowerShell launch: .\scripts\run_aigc_program.ps1"
Write-Host "Selected Python: $PythonExe"
Write-Host "Security gate: & '$PythonExe' .\src\security_privacy_wiring_cli.py --request .\config\counterparty_request_example.json"
Write-Host "Agent doctrine: & '$PythonExe' .\src\agent_operating_doctrine_cli.py"
