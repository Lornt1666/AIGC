# Ω Mission OS Increment 11 — Connector Kernel

## Purpose

Increment 11 introduces one canonical fail-closed governance layer for external connectors. It centralizes immutable execution packets, exact capability policy, authenticated approval verification, atomic approval/idempotency/rate reservation, packet-bound emergency-stop control, recursive privacy redaction, append-only evidence, and audit-chain verification.

## Authority boundary

This increment does not activate production or add an external capability. Gmail remains limited to verified unsent draft creation. GitHub remains limited to read-only repository state. Sending email and mutating GitHub are prohibited.

## Kernel contracts

- `ExecutionPacket`: canonical SHA-256-bound exact-action packet with hard-coded false production/send authority.
- `ApprovalRecord`: exact packet/action/expiry/authority binding with an authenticated authority signature.
- `HMACApprovalVerifier`: trusted-authority allowlist plus protected runtime secret; initialization fails closed when configuration is missing.
- `KernelPolicy`: connector capability allowlist and bounded hourly rate limit.
- `AppendOnlyEvidenceLedger`: JSONL SHA-256 hash chain with crash-recoverable transaction ownership metadata.
- `ConnectorKernel`: approval validation, atomic unlock consumption, execution leasing, durable reservation, pre-effect revalidation, evidence, and fail-safe relocking.

## Emergency-stop and execution-lease lifecycle

`enabled=true` always means externally locked. A temporary operator unlock uses `enabled=false` and binds the exact packet digest, approval ID, connector, capability, revision, expiry, no-send state, and production-disabled state.

Inside the same transaction used for durable gating, the kernel atomically replaces that open unlock with `enabled=true` plus a single non-reusable execution lease. The lease binds the exact packet and approval and expires within a bounded interval. Before any provider effect, the kernel immediately rereads and verifies the lease.

Success, provider failure, replay rejection, idempotency rejection, rate-limit rejection, and policy rejection all terminate in a bounded relock procedure. Confirmed relock removes the active lease. The ledger records `CONNECTOR_UNLOCK_CONSUMED_TO_LEASE` and `CONNECTOR_EMERGENCY_STOP_RELOCKED`.

If relock cannot be confirmed after bounded retries, the kernel writes an fsynced redacted `CONNECTOR_RELOCK_CRITICAL_FAILURE` record to the dedicated critical evidence channel and raises `CriticalRelockError`.

## Atomic durable governance

The ledger transaction lock serializes unlock consumption, replay/idempotency/rate checks, and reservation. Lock ownership records include a random token, PID, hostname, and creation time. A lock can be recovered only after its stale threshold and only when its recorded local process is no longer alive. Live locks are never stolen.

Approval IDs, idempotency keys, uncertain outcomes, and hourly usage are reconstructed from durable reservation records after restart. Reservations are fsynced before provider execution.

## Privacy

Redaction is recursive. Credentials, tokens, signatures, passwords, and email fields are removed from health and result surfaces. Raw provider object identifiers are replaced by SHA-256 hashes. Critical failure evidence contains hashes rather than raw exception text.

## Gmail migration

`GovernedGmailKernelAdapter` wraps the existing draft-only provider and exposes only `CREATE_DRAFT_VERIFIED`. It performs provider read-back and requires exact recipient, subject, body, and `sent=false`.

## GitHub migration

`GovernedGitHubKernelAdapter` exposes only `READ_REPOSITORY_STATE`. Any mutation marker fails closed. No PR, issue, branch, commit, or repository write capability is introduced.

## Deferred work

Production activation, Gmail sending, GitHub writes, Drive, Calendar, Slack, database-backed distributed locking, and deployment credential stores remain separate governed increments.
