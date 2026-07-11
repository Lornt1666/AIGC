param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
if ($HostAddress -ne "127.0.0.1") {
    throw "AIGC local API must bind to 127.0.0.1 in bootstrap mode."
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
python -m uvicorn src.api.app:app --host $HostAddress --port $Port
