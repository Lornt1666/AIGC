$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ($env:AIGC_INSTALL_DEPENDENCIES -eq "1") {
    python -m pip install -r requirements.txt
}

$HostAddress = if ($env:AIGC_WEBAPP_HOST) { $env:AIGC_WEBAPP_HOST } else { "127.0.0.1" }
$PortNumber = if ($env:PORT) { $env:PORT } else { "8000" }

uvicorn src.webapp.app:app --host $HostAddress --port $PortNumber
