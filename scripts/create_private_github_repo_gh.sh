#!/usr/bin/env sh
set -eu

OWNER="${1:-Lornt1666}"
REPO_NAME="${2:-AIGC}"
REPO_FULL_NAME="$OWNER/$REPO_NAME"
REMOTE_URL="https://github.com/$REPO_FULL_NAME.git"

gh auth status

if ! gh repo view "$REPO_FULL_NAME" >/dev/null 2>&1; then
  gh repo create "$REPO_FULL_NAME" --private --source=. --remote=origin
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

git push -u origin main
