# Ω Mission OS Increment 11 — Connector Kernel

## Purpose

Increment 11 introduces one canonical, fail-closed governance layer for external connectors. It centralizes immutable execution packets, independently verified exact-action approvals, bounded packet-specific unlocks, durable replay/rate state, recursive privacy redaction, append-only evidence, and audit-chain verification.

## Authority boundary

This increment does not activate production or add an external capability. Gmail remains limited to verified unsent draft creation. GitHub is migrated only as a read-only state adapter. Sending email and mutating GitHub are prohibited.

## Architecture

```text
Mission Director
      |
Independent Approval Authority
      |
Connector Kernel
      |
+-----+-------------------+
|                         |
Gmail thin adapter   GitHub thin adapter
|                         |
+--- Exact packet unlock -+
      Evidence ledger
      Emergency stop
      Human authority
```

## Kernel contracts

- `ExecutionPacket`: canonical SHA-256-bound packet with exact connector, capability, payload, idempotency key, approval identifier, expiry, policy revision, and hard-coded false production/send authority.
- `ApprovalRecord`: independently verified record bound to the packet digest, connector, capability, authority, and expiry.
- `ApprovalVerifier`: separate authority interface; the kernel cannot mint or accept its own approval.
- `KernelPolicy`: connector capability allowlist and bounded hourly rate limit.
- `ConnectorAdapter`: minimal provider health and execution interface.
- `AppendOnlyEvidenceLedger`: JSONL SHA-256 hash chain with tamper detection and durable reservation state.
- `ConnectorKernel`: registration, health, packet/approval verification, exact unlock validation, durable replay/rate reconstruction, execution, recursive redaction, and terminal evidence.

## Emergency-stop semantics

`enabled=true` means locked and blocks every external action. Execution requires a short-lived `enabled=false` unlock record bound to the exact packet digest, approval ID, connector, capability, revision, and expiry. A generic or stale unlock fails closed.

## Durable governance

Approval consumption, idempotency reservations, uncertain outcomes, and hourly rate usage are reconstructed from `CONNECTOR_EXECUTION_RESERVED` records on every execution. Restarting the process does not restore authority or permit replay.

## Privacy boundary

Redaction is recursive across mappings and sequences. Credentials, email values, tokens, and secrets are removed from health and result surfaces. Provider object identifiers are replaced by SHA-256 hashes before they are returned or evidence-bound.

## Gmail compatibility and migration

`GovernedGmailKernelAdapter` wraps the existing draft-only provider and exposes only `CREATE_DRAFT_VERIFIED`. Existing provider methods remain implementation details behind the adapter. The kernel performs approval, unlock, reservation, replay, rate, evidence, and privacy enforcement; the adapter performs draft creation and exact provider read-back. Tests prove no raw provider identifier leaves the kernel and no send authority exists.

## GitHub migration

`GovernedGitHubKernelAdapter` exposes only `READ_REPOSITORY_STATE`. Any mutation marker fails closed. No PR, issue, branch, commit, or repository write capability is introduced.

## Deferred work

Production activation, Gmail sending, GitHub writes, Drive, Calendar, Slack, deployment credential stores, and multi-writer ledger locking remain separate governed increments.
