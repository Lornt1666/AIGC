param(
    [switch]$SkipVenv,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "AIGC local setup"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python was not found. Install Python 3.10 or newer and rerun this setup script."
}

python --version

if (-not $SkipVenv) {
    if (-not (Test-Path ".venv")) {
        Write-Host "Creating .venv..."
        python -m venv .venv
    }
    Write-Host "Virtual environment exists at .venv. Activate it manually if desired: .\.venv\Scripts\Activate.ps1"
}

Write-Host "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "Running health check..."
python .\src\aigc.py health --write

Write-Host "Running contract validation..."
python .\src\aigc.py validate

Write-Host "Running smoke checks..."
python .\src\aigc.py run governance-smoke
python .\src\aigc.py run cockpit-smoke

if (-not $SkipTests) {
    Write-Host "Running tests..."
    python -m pytest
}

Write-Host "AIGC local setup complete."
Write-Host "Launch with: .\RUN_AIGC_PROGRAM.bat"
Write-Host "Or launch with: .\scripts\run_aigc_program.ps1"
