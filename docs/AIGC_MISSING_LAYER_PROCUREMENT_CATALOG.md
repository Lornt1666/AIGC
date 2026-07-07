# AIGC Missing Layer Procurement Catalog

## Executive Decision

AIGC has a strong governed command-center foundation, but it is not complete for MVP+++ without additional governance, orchestration, privacy, supply-chain, and runtime-control layers.

The safe procurement decision is:

1. Procure missing layers as contracts and tests first.
2. Implement only local, non-live scaffolds until review passes.
3. Keep external systems disabled until a separate permit approves them.
4. Treat every outward action as a separate risk event.

## Procured Now

The latest procurement pass procures:

- public research provenance matrix
- missing-layer procurement catalog
- schema for the catalog
- tests that enforce source provenance, human review, and no external action
- AI RMF control-plane contract
- tool guardrail mesh contract
- interrupt/resume contract
- durable workflow readiness contract
- evidence workflow observability contract
- supply-chain provenance contract
- prompt-injection red-team contract
- privacy and retention contract
- cost and rate-limit contract
- post-quantum provider-selection contract
- buyer tenant-isolation contract
- safe push-command procurement record

## Procured Control Layers

These layers are now procured as local contracts, schemas, modules, tests, and documentation. They do not install or activate external systems.

- AI RMF control plane
- tool guardrail mesh
- human interrupt/resume records
- durable workflow execution readiness
- data workflow observability
- supply-chain provenance and release attestation
- prompt-injection red-team harness
- privacy/retention/data-classification layer
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
