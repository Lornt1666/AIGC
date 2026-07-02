param(
  [string]$RepoName = "AIGC"
)

gh auth status
gh repo create $RepoName --private --source=. --remote=origin --push
