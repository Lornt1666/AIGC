param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
    Write-Host "No AIGC local API process is listening on port $Port."
    exit 0
}

$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $processIds) {
    $process = Get-Process -Id $processId -ErrorAction Stop
    if ($process.ProcessName -notmatch "python|uvicorn") {
        throw "Refusing to stop non-Python process $($process.ProcessName) on port $Port."
    }
    Stop-Process -Id $processId -Force
}
Write-Host "AIGC local API stopped."
