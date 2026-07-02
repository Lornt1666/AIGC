param(
  [string]$Owner = "Lornt1666",
  [string]$RepoName = "AIGC"
)

gh auth status

$RepoFullName = "$Owner/$RepoName"
$RemoteUrl = "https://github.com/$RepoFullName.git"

gh repo view $RepoFullName *> $null
if ($LASTEXITCODE -ne 0) {
  gh repo create $RepoFullName --private --source=. --remote=origin
}

git remote get-url origin *> $null
if ($LASTEXITCODE -eq 0) {
  git remote set-url origin $RemoteUrl
} else {
  git remote add origin $RemoteUrl
}

git push -u origin main
