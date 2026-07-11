# AIGC Assurance Sensorium and Nano-Control Mesh

**Document ID:** SENSORIUM-001  
**Status:** Proposed standard  
**Scope:** Repository, policy, evidence, review, runtime, and operational sensing

## Purpose

The Sensorium is a bounded, deterministic observation layer for AIGC. It detects drift, stale evidence, unsupported claims, governance violations, security/privacy risks, accessibility gaps, and operational weaknesses at the smallest practical unit of change.

Sensors observe and report. They never grant authority.

```text
signal source
→ sensor adapter
→ normalized observation
→ policy/context binding
→ invariant evaluation
→ finding
→ correlation and deduplication
→ review packet / gate receipt / readiness update
→ human decision where required
```

## Sensor families

1. Repository structure and dependency integrity
2. Contracts, schemas, compatibility, and migrations
3. Constitutional and governance compliance
4. Review state and exact-head freshness
5. Security and privacy boundaries
6. Identity, session, tenant, project, and authorization rules
7. Testing, evidence maturity, and receipt integrity
8. Accessibility and public trust
9. Operations, resilience, recovery, and monitoring
10. Documentation provenance, consistency, and staleness

## Nano-observation contract

Every observation records:

- stable observation and sensor identifiers;
- sensor version;
- repository and exact revision;
- artifact path and optional symbol/property/line locator;
- assurance domain and signal;
- severity and confidence;
- evidence and policy references;
- observation time and optional staleness boundary;
- confirmation that no sensitive payload is embedded.

Observations must never include raw credentials, secrets, or unnecessary personal data.

## Finding synthesis

Multiple observations may form one finding only through an explicit, reproducible correlation rule. Deduplication must retain all evidence references. A blocking invariant cannot be suppressed by an aggregate score.

## Sensor health

Each sensor reports one state:

- `HEALTHY`
- `DEGRADED`
- `STALE`
- `MISCONFIGURED`
- `UNAVAILABLE`
- `UNTRUSTED_INPUT`

A mandatory sensor that is unavailable produces `INSUFFICIENT_EVIDENCE`, never `PASS`.

## False-positive governance

Every sensor must define its rule, expected evidence, confidence basis, blind spots, false-positive treatment, steward, fixtures, and suppression process. Suppressions are explicit, scoped, owned, time-limited, revocable, and auditable. Silent ignore lists are prohibited.

## Execution modes

- `PR_DIFF`
- `REPOSITORY_BASELINE`
- `RELEASE`
- `POST_MERGE`
- `SCHEDULED_DRIFT`
- `INCIDENT`

No mode authorizes external action.

## Initial bounded implementation

Sensorium v1 shall implement only:

1. exact-revision binding;
2. missing constitutional traceability;
3. unsupported maturity claim detection;
4. secret-like payload protection;
5. stale evidence/reference detection;
6. registry, observation, health, and finding schemas;
7. deterministic runner interfaces;
8. Markdown and JSON reports;
9. CLI simulation;
10. positive and negative tests.

## Required negative tests

- unavailable mandatory sensor reports pass;
- head changes during execution;
- stale evidence treated as current;
- secret enters an observation or report;
- waiver lacks owner or expiry;
- duplicate observations create contradictory findings;
- blocking finding is averaged away;
- confidence has no basis;
- operator approval is labelled independent;
- policy or constitutional version is absent;
- observation references a missing artifact;
- structural evidence is promoted to production proof.

## Integration

The Sensorium feeds EIAP, the Review Packet Generator, Constitution Gate, Readiness Ledger, Documentation Agent, Review Evidence Agent, and future Identity Kernel sensors.

## Definition of done

Sensorium v1 is complete when one reviewed PR can inspect one AIGC revision, emit healthy/stale observations and synthesized findings, fail closed on missing mandatory evidence, feed review/readiness paths, and remain strictly advisory and operator-controlled.
