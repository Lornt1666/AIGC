param(
    [switch]$ContinueOnFailure
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Resolve-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    throw "Python 3 was not found. Install Python 3 and the repository requirements before initializing AIGC."
}

function Invoke-Python {
    param([string[]]$Arguments)
    if ($script:Python.Count -eq 2) {
        & $script:Python[0] $script:Python[1] @Arguments
    }
    else {
        & $script:Python[0] @Arguments
    }
}

$Python = Resolve-PythonCommand
$InitializeArgs = @("scripts/initialize_aigc.py")
if ($ContinueOnFailure) {
    $InitializeArgs += "--continue-on-failure"
}

Write-Host "=== AIGC Safe Initialization ===" -ForegroundColor Cyan
Write-Host "No login, provider mutation, Terraform apply, job submission, message, contract, or interview scheduling will occur."

Invoke-Python -Arguments $InitializeArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Initialization is blocked. Review the receipt output before continuing." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Initialization completed. Launching the local Operator Cockpit." -ForegroundColor Green
Invoke-Python -Arguments @("-m", "streamlit", "run", "src/dashboard/operator_cockpit_v2_app.py")
exit $LASTEXITCODE
