param(
  [string]$Owner = "Lornt1666",
  [string]$RepoName = "AIGC",
  [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

gh auth status | Out-Host

$body = @{
  required_status_checks = @{
    strict = $true
    contexts = @("validate")
  }
  enforce_admins = $true
  required_pull_request_reviews = @{
    required_approving_review_count = 1
    dismiss_stale_reviews = $true
    require_code_owner_reviews = $false
  }
  restrictions = $null
  allow_force_pushes = $false
  allow_deletions = $false
  required_conversation_resolution = $true
} | ConvertTo-Json -Depth 8

$body | gh api `
  --method PUT `
  -H "Accept: application/vnd.github+json" `
  -H "X-GitHub-Api-Version: 2022-11-28" `
  "/repos/$Owner/$RepoName/branches/$Branch/protection" `
  --input -

Write-Host "Applied branch protection to ${Owner}/${RepoName}:${Branch}"
