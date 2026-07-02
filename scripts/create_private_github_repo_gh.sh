#!/usr/bin/env sh
set -eu

REPO_NAME="${1:-AIGC}"
gh auth status
gh repo create "$REPO_NAME" --private --source=. --remote=origin --push
