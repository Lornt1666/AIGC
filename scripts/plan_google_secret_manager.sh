#!/usr/bin/env sh
set -eu

PROJECT_ID="${1:-YOUR_PROJECT_ID}"
MEMBER="${2:-user:YOUR_EMAIL@example.com}"
python ./src/security/google_secret_manager_provisioning.py --project-id "$PROJECT_ID" --member "$MEMBER"
