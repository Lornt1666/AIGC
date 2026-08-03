# Ω Mission OS Increment 11 — Connector Kernel

## Purpose

Increment 11 introduces one canonical fail-closed governance layer for external connectors. It centralizes immutable execution packets, exact capability policy, authenticated approval verification, atomic approval/idempotency/rate reservation, packet-bound emergency-stop unlocks, recursive privacy redaction, append-only evidence, and audit-chain verification.

## Authority boundary

This increment does not activate production or add an external capability. Gmail remains limited to verified unsent draft creation. GitHub is migrated only as a read-only state adapter. Sending email and mutating GitHub are prohibited.

## Kernel contracts

- `ExecutionPacket`: canonical SHA-256-bound exact action packet with hard-coded false production/send authority.
- `ApprovalRecord`: exact packet/action/expiry/authority binding with an authenticated authority signature.
- `HMACApprovalVerifier`: trusted-authority allowlist plus protected runtime secret; initialization fails closed when configuration is missing.
- `KernelPolicy`: connector capability allowlist and bounded hourly rate limit.
- `ConnectorAdapter`: minimal provider health and execution interface.
- `AppendOnlyEvidenceLedger`: JSONL SHA-256 hash chain with a portable filesystem transaction lock.
- `ConnectorKernel`: registration, policy, approval verification, unlock validation and consumption, atomic reservation, execution, redaction, evidence, and guaranteed terminal relock.

## Emergency-stop lifecycle

`enabled=true` means locked. A temporary unlock must use `enabled=false` and bind the exact packet digest, approval ID, connector, capability, revision, expiry, no-send state, and production-disabled state.

After a valid unlock is observed, every terminal path—including success, provider failure, replay rejection, idempotency rejection, rate-limit rejection, and policy rejection—rewrites the stop atomically to `enabled=true`. The ledger records `CONNECTOR_UNLOCK_CONSUMED` and `CONNECTOR_EMERGENCY_STOP_RELOCKED` evidence.

## Atomic durable governance

The ledger transaction lock serializes verify/check/reserve across concurrent processes. Approval IDs, idempotency keys, uncertain outcomes, and hourly usage are reconstructed from durable reservation records after restart. A competing process cannot pass the same reservation gate before the first reservation is persisted and fsynced.

## Privacy

Redaction is recursive. Credentials, tokens, signatures, passwords, and email fields are removed from health and result surfaces. Raw provider object identifiers are replaced by SHA-256 hashes.

## Gmail migration

`GovernedGmailKernelAdapter` wraps the existing draft-only provider and exposes only `CREATE_DRAFT_VERIFIED`. It performs provider read-back and requires exact recipient, subject, body, and `sent=false`. The compatibility suite proves the governed Increment 11 path invokes the legacy provider only behind this adapter and kernel.

## GitHub migration

`GovernedGitHubKernelAdapter` exposes only `READ_REPOSITORY_STATE`. Any mutation marker fails closed. No PR, issue, branch, commit, or repository write capability is introduced.

## Deferred work

Production activation, Gmail sending, GitHub writes, Drive, Calendar, Slack, distributed database-backed locking, and deployment credential stores remain separate governed increments.
