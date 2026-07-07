# AIGC Missing Layer Procurement Catalog

## Executive Decision

AIGC has a strong governed command-center foundation, but it is not complete for MVP+++ without additional governance, orchestration, privacy, supply-chain, and runtime-control layers.

The safe procurement decision is:

1. Procure missing layers as contracts and tests first.
2. Implement only local, non-live scaffolds until review passes.
3. Keep external systems disabled until a separate permit approves them.
4. Treat every outward action as a separate risk event.

## Procured Now

This commit procures:

- public research provenance matrix
- missing-layer procurement catalog
- schema for the catalog
- tests that enforce source provenance, human review, and no external action

## Planned Next Layers

### P0

- AI RMF control plane
- tool guardrail mesh
- human interrupt/resume records
- supply-chain provenance and release attestation
- prompt-injection red-team harness
- privacy/retention/data-classification layer

### P1

- durable workflow execution readiness
- data workflow observability
- cost/rate-limit/unbounded-consumption guard
- post-quantum provider integration plan
- buyer tenant isolation

## Acceptance Rule

No missing layer may enter implementation unless it has:

- at least one public research source
- an explicit missing reason
- procurement action
- acceptance tests
- risk controls
- forbidden-target block list
- human-review requirement
- `external_action_performed: false`

## Procurement Boundary

The procurement catalog does not:

- install services
- configure cloud accounts
- purchase subscriptions
- read secrets
- call webhooks
- perform live actions
- push deployment changes by itself

It only defines the controlled path from public research to safe implementation.
