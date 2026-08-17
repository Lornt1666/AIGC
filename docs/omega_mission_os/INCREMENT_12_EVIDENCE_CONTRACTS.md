# Ω Mission OS Increment 12 — Evidence Analytics Contracts

## Status

`SLICE A — CONTRACTS AND METRIC CATALOG ONLY`

This increment defines deterministic, machine-verifiable evidence contracts. It does not read canonical databases, materialize an analytics store, expose an API or dashboard, invoke a provider, authorize an action, or mutate canonical state.

## Architectural placement

Increment 12 Slice A is a subsystem of the existing **Evidence Plane**. It is not a sixth architecture plane and does not replace Phase, Quest/Product, Governance/Readiness, Infrastructure/CI, finance, authorization, or evidence authorities.

```text
canonical source systems
        │
        ▼
revision-bound lineage and metric contracts
        │
        ▼
future read-only analytics materialization (deferred)
        │
        ▼
operator/governance interpretation
```

Source systems remain authoritative. Analytics outputs are derived evidence and cannot silently amend their sources.

## Exact Slice A scope

Added:

1. Analytics run-envelope schema.
2. Evidence-lineage schema.
3. Entity-transition schema.
4. Metric-definition schema.
5. Metric-observation schema.
6. Data-quality-finding schema.
7. Versioned metric catalog containing:
   - Governed Progression Rate;
   - Evidence Completeness and Freshness;
   - Decision-Quality Calibration as an inactive definition.
8. Deterministic canonical JSON and SHA-256 validation.
9. Positive and adversarial fixtures.
10. Focused contract tests.

Not added:

- source adapters;
- SQLite/PostgreSQL analytics materialization;
- Phase 12 compatibility changes;
- API or dashboard routes;
- outcome-calibration execution;
- provider access;
- external connectors;
- production activation;
- autonomous threshold changes.

## Contract semantics

### Analytics run envelope

Binds one future analytics run to an exact repository revision, metric-catalog version, bounded timestamps, monotonic duration, source inventory, record counts, deterministic output digest, freshness, and evidence state. The authority flags are hard-false.

### Lineage reference

Binds a source system and identifier to an exact source revision or generation, SHA-256 digest, evidence reference, observation timestamp, freshness expectation, source state, and privacy classification. Sensitive payload inclusion is hard-false.

### Entity transition

Separates prior/new state, transition time, authoritative source digest, eligibility, expiry, contradiction, validity, and evidence state. An expired authorization cannot be represented as active pending.

### Metric definition

Requires explicit grain, reporting window, numerator, denominator, eligibility semantics, formula, source precedence, freshness policy, insufficiency states, guardrails, dimensions, deterministic computation, evidence requirements, and exact-revision/source-digest bindings.

### Metric observation

Binds a computed observation to the exact metric version, catalog version, repository revision, reporting window, decimal-string operands, dimensions, source lineage, source-digest set, freshness, evidence sufficiency, and deterministic digest.

### Data-quality finding

Requires severity, confidence, lifecycle status, affected entity, evidence references, exact revision, source digest, accountable role, remediation and verification conditions, blocking state, and evidence state.

## Evidence-state rules

The controlled evidence states are:

- `PASS`
- `FAIL`
- `INSUFFICIENT_EVIDENCE`
- `STALE`
- `UNAVAILABLE`
- `NOT_APPLICABLE`

Missing evidence never defaults to `PASS`. Unavailable mandatory sources produce `INSUFFICIENT_EVIDENCE`; stale sources cannot report green/pass; open blocking findings dominate aggregates.

## Deterministic digest rules

The implementation uses a bounded canonical JSON subset:

- UTF-8;
- object keys sorted lexicographically;
- no insignificant whitespace;
- Unicode preserved;
- NaN and infinities rejected;
- numeric metric values encoded as decimal strings;
- SHA-256 over canonical bytes.

The catalog carries a digest computed over the catalog object excluding the digest field itself. The validator recomputes and compares it.

## Privacy and data minimization

Contracts permit stable IDs, hashes, enums, timestamps, numeric measures, classified dimensions, and evidence references. Validation rejects secret-like keys, private-key material, email-like values, raw provider payloads, full proposal bodies, employer messages, and unnecessary personal fields.

## Metric catalog

### Governed Progression Rate

Counts progression only against a declared eligible denominator and fixed cohort/window. Raw stage counts are not described as conversion. Expired authorizations are excluded from active pending cohorts.

### Evidence Completeness and Freshness

Measures valid, lineage-bound, fresh required evidence against all applicable required evidence. A blocking integrity/privacy finding or unavailable mandatory source prevents a pass.

### Decision-Quality Calibration

Definition only. It remains `INACTIVE_SAMPLE_INSUFFICIENT`, requires at least 100 governed outcome-linked samples, and cannot change thresholds or behavior autonomously.

## Authority boundary

```text
production_activation_authorized=false
external_provider_action_authorized=false
external_action_performed=false
canonical_state_mutated=false
gmail_send_authority_present=false
github_runtime_mutation_authority_present=false
autonomous_behavior_change_allowed=false
emergency_stop_default=LOCKED
```

These contracts summarize evidence; they create no authority.

## Validation

```bash
python -m src.mission_os.evidence_analytics_contracts --repo-root .
python -m pytest -q tests/test_analytics_contracts.py
```

Repository-wide canonical CI remains required after integration on an exact topic-branch head.

## Deferred slices

- **Slice B:** read-only source adapters and deterministic materialization.
- **Slice C:** Phase 12 compatibility migration and coverage reconciliation.
- **Slice D:** read-only API and operator dashboard.
- **Slice E:** governed outcome calibration after real sample sufficiency.

No deferred slice is authorized by this document.

## Known limitations

- No source database is opened or verified in Slice A.
- No runtime performance, production, outcome, or business claim is established.
- JSON canonicalization is a documented deterministic subset, not a claim of full RFC 8785 conformance for arbitrary JSON numbers.
- Hosted CI, independent review, merge, post-merge verification, and runtime evidence remain separate gates.
