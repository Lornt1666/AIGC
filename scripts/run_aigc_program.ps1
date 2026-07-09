param(
    [int]$Port = 8501,
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not $env:AIGC_SAFE_MODE) {
    $env:AIGC_SAFE_MODE = "1"
}
$env:AIGC_PROGRAM_PORT = "$Port"

Write-Host "AIGC local program launcher"
Write-Host "Safe mode: $env:AIGC_SAFE_MODE"
Write-Host "Port: $env:AIGC_PROGRAM_PORT"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python was not found. Install Python 3.10 or newer, then run scripts\setup_aigc_local.ps1."
}

if ($InstallDependencies -or $env:AIGC_INSTALL_DEPENDENCIES -eq "1") {
    Write-Host "Installing dependencies..."
    python -m pip install -r requirements.txt
}

Write-Host "Running local health check..."
python .\src\aigc.py health --write
if ($LASTEXITCODE -ne 0) {
    throw "Health check failed. Review the output before launching."
}

Write-Host "Launching AIGC Operator Cockpit..."
python -m streamlit run .\src\dashboard\operator_cockpit_app.py --server.port $Port
