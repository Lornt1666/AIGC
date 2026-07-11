# AIGC Identity, Scope and Authorization Decision Kernel v1 Standard

## Purpose

Provide one deterministic, deny-by-default authorization boundary for actor identity references, tenant and project scope, session state, expiry, revocation, assurance level, resource sensitivity, action scope, and consequential human approval requirements.

## Canonical shared contracts

- `ActorReference` identifies the declared actor and authority source.
- `ApprovalReference` records attributable approval without treating possession of a link or token as authority.
- `GateReceipt` records the authorization result and reason codes against an exact revision.

## Decision order

1. Validate actor reference.
2. Enforce tenant isolation.
3. Enforce project isolation.
4. Validate session presence, expiry, and revocation.
5. Check explicit revocation registry.
6. Check requested action.
7. Check requested scopes against granted scopes.
8. Check assurance level.
9. Check resource sensitivity.
10. Check required human approval and independence.
11. Deny on any unresolved reason code; otherwise permit.
12. Emit a revision-bound gate receipt.

## Safety rules

- default result is deny;
- unknown or missing authority never becomes permit;
- cross-tenant and cross-project requests deny;
- expired or revoked sessions deny;
- revocation takes effect before permit;
- self-approval cannot satisfy an independence requirement;
- possession of a URL, identifier, session ID, or approval ID does not establish authority;
- no credentials or live identities are stored in repository artifacts.

## v1 boundary

This increment is a deterministic local simulator and contract implementation. It does not authenticate real users, integrate an identity provider, issue tokens, manage secrets, persist sessions, migrate databases, grant repository access, or perform external actions.

## Acceptance criteria

Positive permit test plus negative tests for tenant isolation, expiry, revocation, missing approval, and self-approval. CI must pass on the exact PR head. Rollback is a revert of the bounded PR.
