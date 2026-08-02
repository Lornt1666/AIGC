# Ω Mission OS Increment 9 Review Packet

Status: DRAFT — HOSTED CI AND FULL GOVERNED REVIEW REQUIRED

## Exact scope

- Real Gmail REST draft provider adapter.
- Connector disabled by default.
- Test account required for initial canary.
- Exact account fingerprint enforcement.
- Draft creation and read-back only.
- No send method or send route.

## Mandatory review gates

- Runtime requests exactly `gmail.compose`; broader and explicit send scopes are rejected.
- Review acknowledges that Google does not offer a general draft-create-only OAuth scope, so the no-send guarantee is application-enforced.
- Credentials are resolved outside repository and API payloads.
- Authenticated Gmail profile must match the governed account fingerprint.
- Non-test activation is blocked without a verified test-account canary receipt.
- Connector health, revocation, and runtime status routes require the local operator credential.
- Fixed endpoint allowlist contains profile, drafts.create, and drafts.get only.
- No `/send`, reply, forward, delete, update, label, or generic connector method exists.
- Increment 8 emergency stop and third-stage approval remain mandatory for actual draft creation.
- No credential, live Gmail content, activation receipt, or canary receipt is committed.

## Evidence required before readiness

- Passing hosted CI on exact head.
- Full diff and route review.
- Secret scan passes.
- Tests prove scope rejection, account mismatch fail-closed, test-canary gating, no send method, credential revocation, and draft read-back.
- Connector remains disabled in checked-in configuration.
