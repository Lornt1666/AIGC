# Ω Mission OS Increment 11 Review Packet

Status: DRAFT — REPAIRED EXACT-HEAD HOSTED CI AND GOVERNED REVIEW REQUIRED

## Scope

- Canonical connector registration and capability policy.
- Immutable execution packets and SHA-256 integrity.
- Independently verified exact-action approval records.
- Packet-bound, expiring emergency-stop unlocks with locked-by-default polarity.
- Durable approval/idempotency/rate reservations reconstructed from append-only evidence.
- Recursive privacy redaction and hashed provider identifiers.
- Structured uncertain-outcome evidence with durable non-retryability.
- Thin Gmail verified-draft adapter behind one kernel authority path.
- Thin GitHub read-only adapter.

## Mandatory invariants

- `enabled=true` means emergency-stop locked.
- Unlocks bind the exact packet digest, approval, connector, capability, revision, and expiry.
- The kernel cannot mint or self-verify approvals.
- Production activation remains false.
- Email send authority remains false.
- Gmail exposes only verified unsent draft creation.
- GitHub exposes only read-only repository state.
- Unknown or undeclared capabilities fail closed.
- Packets and approvals are exact-digest and expiry bound.
- Approval and idempotency reservations survive process restart.
- Hourly rate usage survives process restart.
- Reservations occur before any adapter effect.
- Uncertain outcomes remain non-retryable after restart.
- Evidence is append-only and hash chained.
- Redaction is recursive.
- Raw provider identifiers never leave the kernel result boundary.

## Required review

Inspect the complete repaired diff, run hosted CI on the exact head, verify schemas and regression tests, search for send and mutation authority, confirm the old Gmail provider is used only behind the kernel adapter for this path, and do not mark ready if any duplicated authority, credential exposure, replay weakness, evidence defect, unlock weakness, or backward-compatibility concern remains.
