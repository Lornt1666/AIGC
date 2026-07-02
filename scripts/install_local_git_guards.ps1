param()

$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) {
  throw "This script must be run inside a git repository."
}

Set-Location $repoRoot

if (-not (Test-Path ".githooks")) {
  throw "Missing .githooks directory."
}

git config core.hooksPath .githooks

Write-Host "AIGC local git guards installed."
Write-Host "Direct commits and pushes to main are blocked locally."
Write-Host "Use feature branches and draft pull requests while GitHub branch protection is unavailable."

