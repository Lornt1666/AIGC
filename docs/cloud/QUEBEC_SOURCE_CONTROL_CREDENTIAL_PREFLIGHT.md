# AIGC Québec Cloud — Source-Control Credential Preflight

## Status

**BLOCKING SECURITY REVIEW — NO CLOUD AUTHORITY GRANTED**

Before AIGC creates or deploys any Google Cloud resource, the repository owner must review every legacy GitHub personal access token capable of repository, organization, enterprise, hook, key, workflow, package, or administrative access.

This document records a procedure. It contains no credential value, token fingerprint, authorization header, cookie, recovery code, or secret-bearing URL.

## Required outcome

Every legacy classic personal access token must be classified as exactly one of:

- `REVOKED_OR_DELETED`;
- `EXPIRED_OR_AUTOMATICALLY_REVOKED_WITH_EVIDENCE`;
- `STILL_REQUIRED_PENDING_CONTROLLED_ROTATION`;
- `INDETERMINATE_BLOCKS_CLOUD_AUTHORITY`.

A token remains blocking until GitHub settings, an applicable audit record, or an accountable rotation receipt proves that it is no longer usable or that its continued use is intentionally governed.

## Review procedure

1. Open GitHub **Settings → Developer settings → Personal access tokens → Tokens (classic)** through an authenticated owner session.
2. Review each listed token's name, scopes, last-used date, expiration, and current state without copying the token value.
3. Delete tokens that are no longer required.
4. For a token that still supports a legitimate automation:
   - identify the exact automation and repository;
   - suspend the automation if safe;
   - replace the classic token with `GITHUB_TOKEN`, a GitHub App installation token, OpenID Connect, or a fine-grained expiring token with the smallest required permissions;
   - verify the replacement;
   - revoke the classic token;
   - retain only a metadata receipt.
5. Review repository deploy keys, GitHub Apps, Actions secrets, environment secrets, webhooks, OAuth apps, SSH keys, active sessions, and authorized devices for unexplained access.
6. Rotate any downstream credential that could have been exposed through the old automation.
7. Record the completion evidence without storing a secret.

## Minimum evidence record

```json
{
  "schema_version": "aigc.github-credential-preflight.v1",
  "reviewed_account": "Lornt1666",
  "reviewed_at": "<ISO-8601 UTC>",
  "reviewed_by": "<accountable reviewer>",
  "classic_tokens_reviewed": true,
  "unresolved_classic_tokens": 0,
  "repository_deploy_keys_reviewed": true,
  "github_apps_reviewed": true,
  "actions_secrets_reviewed": true,
  "webhooks_reviewed": true,
  "active_sessions_reviewed": true,
  "raw_secret_values_recorded": false,
  "cloud_authority_unblocked": true,
  "evidence_sha256": "<SHA-256 of canonical metadata record>"
}
```

Do not put token names in public judge material when they reveal internal system purpose. Do not put raw values anywhere in the repository, prompts, screenshots, logs, receipts, Terraform inputs, or deployment packets.

## Preferred future identity model

Use, in order of preference:

1. GitHub Actions `GITHUB_TOKEN` with job-level least privilege;
2. GitHub App installation tokens with bounded repository permissions and short lifetime;
3. Workload Identity Federation / OpenID Connect for Google Cloud deployment;
4. fine-grained personal access tokens only when no workload identity is available, with explicit repositories, minimum permissions, and expiration.

Do not use a classic personal access token to provide Google Cloud runtime identity.

## Authorization binding

The Québec staging authorization must retain:

```text
legacy_github_credentials_reviewed_and_revoked_or_proven_inactive=true
```

until the review is repeated or a material source-control credential change occurs. Any unresolved token restores the value to `false` and blocks resource creation, deployment, public traffic, live model calls, publication, merge, and financial authority.
