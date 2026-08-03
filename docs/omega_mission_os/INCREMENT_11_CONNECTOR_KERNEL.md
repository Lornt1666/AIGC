# Ω Mission OS Increment 11 — Connector Kernel

## Purpose

Increment 11 introduces one canonical, fail-closed governance layer for external connectors. It centralizes immutable execution packets, exact capability policy, approval consumption, idempotency reservation, replay prevention, hourly rate limits, emergency-stop enforcement, privacy redaction, append-only evidence, and audit-chain verification.

## Authority boundary

This increment does not activate production or add an external capability. Gmail remains limited to verified unsent draft creation. GitHub is migrated only as a read-only state adapter. Sending email and mutating GitHub are prohibited.

## Architecture

```text
Mission Director
      |
Connector Kernel
      |
+-----+-------------------+
|                         |
Gmail thin adapter   GitHub thin adapter
|                         |
+----- Approval / policy -+
      Evidence ledger
      Emergency stop
      Human authority
```

## Kernel contracts

- `ExecutionPacket`: canonical SHA-256-bound packet with exact connector, capability, payload, idempotency key, approval, expiry, policy revision, and hard-coded false production/send authority.
- `KernelPolicy`: connector capability allowlist and bounded hourly rate limit.
- `ConnectorAdapter`: minimal provider health and execution interface.
- `AppendOnlyEvidenceLedger`: JSONL SHA-256 hash chain with tamper detection.
- `ConnectorKernel`: registration, health, packet verification, emergency-stop checking, approval/idempotency reservation, execution, redaction, and terminal evidence.

## Fail-closed behavior

The kernel rejects unknown connectors, undeclared capabilities, expired or modified packets, approval replay, idempotency replay, exceeded rate limits, disabled or malformed emergency stops, production authority, send authority, GitHub mutation, Gmail send requests, and evidence tampering.

Adapter exceptions are classified as uncertain, recorded with a hashed error, and made non-retryable under the same approval and idempotency key.

## Gmail migration

`GovernedGmailKernelAdapter` wraps the existing draft-only provider and exposes only `CREATE_DRAFT_VERIFIED`. It performs provider read-back and requires exact recipient, subject, body, and `sent=false`.

## GitHub migration

`GovernedGitHubKernelAdapter` exposes only `READ_REPOSITORY_STATE`. Any mutation marker fails closed. No PR, issue, branch, commit, or repository write capability is introduced.

## Deferred work

Production activation, Gmail sending, GitHub writes, Drive, Calendar, Slack, persistent distributed rate limiting, and deployment credential stores remain separate governed increments.
