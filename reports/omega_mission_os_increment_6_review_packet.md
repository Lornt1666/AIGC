# Ω Mission OS Increment 6 Review Packet

## Exact branch

`feat/omega-mission-os-increment-6`

## Scope

Human-only local proposal decisions. No external action execution.

## Added

- Append-only local decision ledger.
- Operator-token authentication.
- Exact proposal revision binding.
- Reject, revision-request, and exact-authorization decisions.
- Fail-closed stale revision and incomplete binding checks.
- GET/POST local decision API.
- Contract, tests, and documentation.

## Authority statement

An `AUTHORIZED_NOT_EXECUTED` receipt confirms only that the accountable operator authorized the exact proposal revision. It does not prove or perform submission, communication, contract acceptance, invoicing, payment, connector execution, Quest transition, or canonical-state mutation.

## Review gates

- [ ] Hosted CI passes on exact head.
- [ ] Secret scan passes.
- [ ] Operator token is never persisted.
- [ ] Non-loopback clients remain rejected.
- [ ] Stale revisions fail closed.
- [ ] Missing counterparty/channel bindings cannot be authorized.
- [ ] Revision requests require explicit changes.
- [ ] Decision ledger remains outside canonical state roots.
- [ ] No external execution route exists.
- [ ] All receipts state `external_action_performed: false`.

## Merge condition

Keep the PR draft until every gate passes and the full diff receives governed review.
