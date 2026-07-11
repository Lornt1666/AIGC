# AIGC Assurance Sensorium v1 Standard

## Purpose

The Assurance Sensorium is the EIAP observation layer. It converts bounded, local, revision-bound signals into shared `Observation` and `Finding` contracts.

## Authority boundary

The Sensorium may observe, classify, correlate, and report. It may not approve, merge, deploy, grant access, infer human authority, use credentials, or perform external actions.

## Required behavior

1. Every observation binds to an exact revision.
2. Every sensor exposes a declared health state.
3. Invalid or untrusted inputs fail closed.
4. Mandatory unavailable sensors produce blocking findings.
5. Findings use EIAP shared contracts rather than private domain models.
6. Blocking findings cannot be averaged into a passing aggregate.
7. Sensitive payloads are excluded; only references and reason codes are retained.
8. Any head or policy change invalidates stale observations.

## v1 health taxonomy

- `healthy`
- `degraded`
- `stale`
- `misconfigured`
- `unavailable`
- `untrusted_input`

## v1 scope

This increment provides deterministic local observation and finding synthesis plus fail-closed aggregation. Repository adapters, policy drift sensors, runtime telemetry, persistence, scheduling, and network collection remain deferred.

## Acceptance criteria

- positive healthy observation test;
- unavailable sensor produces a blocking finding;
- invalid confidence and health states fail;
- exact-revision binding is required;
- CI passes on the exact PR head;
- rollback is a revert of the bounded PR.
