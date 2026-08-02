# Volume II — Runtime, Phase Orchestration, and Quest Integration

## Scope

Define how Mission OS coordinates AIGC's numbered phases and the transactional Quest lifecycle without merging or confusing them.

## Runtime cycle

`OBSERVE -> NORMALIZE -> ASSESS -> PRIORITIZE -> PLAN -> ROUTE -> PREPARE -> VALIDATE -> APPROVAL_REQUIRED -> EXECUTE -> VERIFY -> LEARN`

Each cycle produces a revision-bound runtime record. A cycle may stop at any gate without being treated as a failure.

## Plane integration

- Phase/Batch Plane performs discovery, assessment, drafting, compliance, quality, finance, and evolution work.
- Quest/Product Plane owns transactional candidate and work lifecycle state.
- Governance Plane grants bounded authority.
- Infrastructure Plane performs separately authorized platform mutations.
- Evidence Plane records what actually happened.

Mission OS composes these planes; it does not absorb their authority.

## Routing rules

- Opportunity discovery routes to existing radar and assessment phases.
- Proposal preparation routes to proposal, compliance, fidelity, quality, and customer-satisfaction phases.
- Approval preparation routes to Phase 5-compatible authorization packets.
- Controlled execution routes only to Phase 6-compatible execution modes.
- Business lifecycle changes route through canonical Quest transitions.
- Infrastructure changes require exact-revision infrastructure authorization.

## Idempotency and replay

Every runtime command must carry a unique operation ID, input digest, expected prior state, and replay policy. Duplicate operations must return the existing receipt or fail closed.

## Failure handling

Failures are classified as transient, validation, authorization, policy, dependency, security, evidence, or terminal. Recovery may retry only transient failures within a bounded budget. All others require revision or accountable approval.

## Acceptance criteria

Implementation requires a runtime state machine, routing registry, phase/Quest adapters, idempotency store, bounded retry policy, and synthetic end-to-end tests proving that no route bypasses existing approval and evidence controls.