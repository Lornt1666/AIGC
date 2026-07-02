#!/usr/bin/env bash
set -euo pipefail

OWNER="${1:-Lornt1666}"
REPO_NAME="${2:-AIGC}"
BRANCH="${3:-main}"

gh auth status

if ! cat <<JSON | gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "/repos/${OWNER}/${REPO_NAME}/branches/${BRANCH}/protection" \
  --input -
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["validate"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
then
  echo "GitHub branch protection was not applied." >&2
  echo "For private repositories, GitHub may require GitHub Pro or a public repository." >&2
  echo "Use scripts/install_local_git_guards.sh and PR-based CI until branch protection is available." >&2
  exit 1
fi

echo "Applied branch protection to ${OWNER}/${REPO_NAME}:${BRANCH}"
