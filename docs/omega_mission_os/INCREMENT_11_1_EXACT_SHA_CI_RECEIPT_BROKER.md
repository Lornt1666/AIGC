# Ω Mission OS Increment 11.1 — Exact-SHA CI Receipt Broker

## Purpose

Provide a permanent, repository-native way to request hosted validation of an exact commit without changing `main`, manufacturing an empty commit, or accepting arbitrary workflow inputs.

## Trust boundary

A request branch contributes only one non-secret JSON document. The workflow checks out trusted broker code from `main`, validates a closed request contract, verifies that the full target SHA exists and is reachable from `main`, then checks out and executes the canonical validation suite from that exact target. Request-branch code is never executed.

## Authority boundary

- `contents: read` only.
- Checkout credentials are not persisted.
- All third-party actions are pinned to immutable commit SHAs.
- No secrets, OIDC, provider mutation, Terraform apply, deployment, production activation, Gmail send, or GitHub runtime mutation.
- Request fields cannot specify commands, paths, workflow names, environment variables, credentials, or provider actions.

## Receipt

A successful receipt binds the canonical request digest, requested and observed commit SHAs, tested Git tree SHA, workflow revision, run number and ID, canonical step conclusions, test result, artifact-manifest digest, and explicit false external-action and production-activation states. The receipt is canonically SHA-256 covered.

## Request lifecycle

`REQUESTED → CONTRACT_VALID → TARGET_REACHABLE_FROM_MAIN → EXACT_TARGET_CHECKED_OUT → CANONICAL_VALIDATION_PASSED → RECEIPT_PUBLISHED`

Any missing, malformed, mismatched, unauthorized, unreachable, failed, or partial state fails closed and produces no success receipt.

## Initial post-merge use

After this increment is separately reviewed, merged, and post-merge verified, create one request under `ci/exact_sha_requests/` targeting `ba6110a04ed11c942c6ec55deb4e84b29dee4a15`. The broker then validates the exact Increment 11 merge commit and publishes its hosted evidence artifact.
