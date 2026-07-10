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

Write-Host "Installing reviewed dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "Running health check..."
python .\src\aigc.py health --write

Write-Host "Running contract validation..."
python .\src\aigc.py validate

Write-Host "Running governance and cockpit smoke checks..."
python .\src\aigc.py run governance-smoke
python .\src\aigc.py run cockpit-smoke

Write-Host "Running Security & Privacy Wiring Gate smoke check..."
python .\src\security_privacy_wiring_cli.py --request .\config\counterparty_request_example.json

Write-Host "Running Agent Operating Doctrine smoke check..."
python .\src\agent_operating_doctrine_cli.py

if (-not $SkipTests) {
    Write-Host "Running tests..."
    python -m pytest
}

Write-Host "AIGC local setup complete."
Write-Host "Launch with: .\RUN_AIGC_PROGRAM.bat"
Write-Host "Or launch with: .\scripts\run_aigc_program.ps1"
Write-Host "Security gate: python .\src\security_privacy_wiring_cli.py --request .\config\counterparty_request_example.json"
Write-Host "Agent doctrine: python .\src\agent_operating_doctrine_cli.py"