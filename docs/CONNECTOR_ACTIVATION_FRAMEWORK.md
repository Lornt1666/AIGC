# Ω Mission OS Increment 12 — Connector Activation Framework

## Status

CONCEPTUAL GOVERNANCE IMPLEMENTATION — PRODUCTION ACTIVATION DISABLED

This increment adds connector registration and activation governance. It does not add provider operations, credentials, deployments, Gmail sending, GitHub mutation, or production authority.

## Architecture

`Mission Director → Connector Kernel → Connector Registry → Activation Framework → Append-Only Evidence → Human Authority`

The framework inherits the Connector Kernel's append-only evidence implementation and preserves its approval, replay, emergency-stop, privacy, and audit guarantees. Activation metadata never invokes a connector adapter.

## Registry

Each connector is registered by an integrity-bound `CapabilityManifest`. A connector identifier may not be rebound to a different manifest digest. Manifests are read-only in Increment 12 and support only `TEST` and `STAGING`.

## Environments

- `TEST`: isolated validation with no external effect.
- `STAGING`: controlled non-production validation with no newly authorized provider effect.
- `PRODUCTION`: structurally rejected in Increment 12.

Activation records are bound to exactly one environment and cannot be reused across environments.

## Lifecycle

`REGISTERED → CONFIGURED → DEPENDENCIES_VERIFIED → READY_FOR_ACTIVATION → ACTIVATED_TEST | ACTIVATED_STAGING`

Suspension and retirement are explicit. Invalid or skipped transitions fail closed.

## Dependency verification

Every required dependency has an identifier, satisfaction result, and evidence digest. Missing, malformed, or unsatisfied required dependencies reject record compilation before any activation evidence is emitted.

## Activation record

An activation record binds the connector/version, environment, requested read-only capabilities, manifest digest, approval digest, policy digest, dependency digest, actor, lifecycle state, timestamp, and authority flags. Its SHA-256 digest is recomputed before activation.

## Evidence

Lifecycle transitions and successful activations are appended to the existing crash-safe, append-only Connector Kernel evidence ledger. Evidence records explicitly preserve:

- `production_activation_authorized=false`
- `external_send_authorized=false`
- `github_mutation_authorized=false`

## Invariants

1. No production activation.
2. No Gmail sending.
3. No GitHub mutation capability.
4. No new external connector operation.
5. No activation before registration, configuration, dependency verification, and readiness.
6. No mutable registry rebinding.
7. No missing or unsatisfied required dependency.
8. No evidence emission for rejected activation.
9. Existing approval, replay, emergency-stop, privacy-redaction, and evidence-chain controls remain unchanged.

## Completion gate

The PR remains draft until exact-head hosted CI passes and governed review confirms every invariant above.
