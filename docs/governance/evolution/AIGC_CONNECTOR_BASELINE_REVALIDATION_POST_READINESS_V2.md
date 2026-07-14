# AIGC Connector Baseline Revalidation — Post-Readiness Main v2

Status: `REVALIDATION_PENDING_CI_AND_OPERATOR_REVIEW`  
Pull request: `#98`  
Previous verified head: `f5ffdb4aaf60b09f40b1a8840ef5e5b62b49a141`  
Current canonical main: `d8cd4f5f17a727e16fc7f2ed966f3458cac0808f`  
Rollback branch: `codex/production-connectors-secret-broker-v1-pre-post-readiness-revalidation`  
External action performed: **No**

## Objective

Revalidate the existing disabled production connector and Google Secret Manager broker baseline against the post-identity, post-readiness canonical mainline, correct bounded security findings from exact-head review, and preserve the internal/default-deny truth boundary.

## Repository relationship

The connector train contains connector-specific additions and no file-level overlap with the identity baseline merged through PR #95 or the readiness ledger merged through PR #100. GitHub reports PR #98 as mergeable against current `main`.

A fresh exact-head commit and synthetic merge candidate are required because earlier CI evidence predates the current mainline.

## Exact-head security corrections

Operator review identified two pre-merge truth defects:

1. authorized Secret Manager access accepted symbolic versions such as `latest`, which is not an immutable rollback-safe version binding;
2. adapter-facing secret material was copied into immutable `bytes`, so that copy was outside explicit zeroization.

The corrected boundary now:

- permits broad version syntax only while parsing disabled/unresolved configuration;
- requires a positive numeric secret version before any authorized client call;
- lends adapters a read-only `memoryview` backed by the resolver's mutable buffer;
- zeroizes that same underlying buffer after adapter execution, including failure paths;
- tests that a borrowed view observes zeroed bytes after close;
- performs no Secret Manager request in the production configuration.

## Truth boundary

The baseline remains internal and default-deny:

- every connector remains disabled;
- every destination allowlist remains empty;
- terms review remains required;
- staging evidence remains not started;
- the Secret Manager project ID remains unresolved;
- secret access remains unauthorized;
- OAuth and GitHub App authorization remain unauthorized;
- staging reads and writes remain unauthorized;
- production connector activation remains unauthorized;
- production external action remains unauthorized.

No Secret Manager request, credential use, OAuth grant, GitHub App installation, mailbox access, Drive access, repository operation, external message, deployment, or readiness promotion is performed by this revalidation.

## Expected readiness result

The canonical readiness score is expected to remain `66.80 / 100` with production readiness false and all five blocking gaps preserved:

```text
security_privacy_wiring
transactional_persistence
production_identity_access
approved_external_connectors
production_deployment
```

PR #98 does not update the production-readiness ledger. `approved_external_connectors` remains `planned` until exact-revision operational staging evidence, durable idempotency, provider-effect reconciliation, and a separate activation decision exist.

## Required gates

1. contract validation;
2. AEC-001 constitutional validation;
3. committed-content secret/redaction scan;
4. procurement smoke stages;
5. complete repository test suite;
6. readiness evaluation reproducing `66.80`;
7. test evidence artifact upload;
8. readiness evidence artifact upload;
9. exact-head operator review;
10. separate merge decision.

## Rollback

Before merge, close the PR or restore the connector branch to the preserved previous head. After merge, revert the connector baseline as one reviewed unit. No cloud, secret, provider, data, or external-system rollback is required because no live authority is activated.
