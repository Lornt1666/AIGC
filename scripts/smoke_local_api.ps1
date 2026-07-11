param(
    [string]$BaseUrl = "http://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "healthy" -or $health.external_action_performed -ne $false) {
    throw "Health check failed."
}
$status = Invoke-RestMethod -Uri "$BaseUrl/api/v1/system/status" -Method Get
if ($status.production_identity_access -ne "blocking") {
    throw "Production identity blocker was not preserved."
}
Write-Host "AIGC local API smoke test passed."
