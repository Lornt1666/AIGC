$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ($env:AIGC_INSTALL_DEPENDENCIES -eq "1") {
    python -m pip install -r requirements.txt
}

uvicorn src.webapp.app:app --host 0.0.0.0 --port 8000
