#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ ! -d ".githooks" ]]; then
  echo "Missing .githooks directory." >&2
  exit 1
fi

git config core.hooksPath .githooks

echo "AIGC local git guards installed."
echo "Direct commits and pushes to main are blocked locally."
echo "Use feature branches and draft pull requests while GitHub branch protection is unavailable."

