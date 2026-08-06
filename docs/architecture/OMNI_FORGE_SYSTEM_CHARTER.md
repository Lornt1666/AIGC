# REGENEXCALIBUR :: OMNI-FORGE-V-SUPREME

## Status

**INITIAL DOMAIN KERNEL — DRAFT — NO EXTERNAL EXECUTION AUTHORITY**

OMNI-FORGE is the constitutional architecture for deterministic multi-agent engineering in AIGC. Its mythology is the interface; evidence is the law.

It is not omniscient and does not automatically produce production-ready software. An artifact may be classified as a production candidate only after compilation, adversarial testing, security review, exact-head hosted CI, immutable deployment receipts, recovery evidence, and explicit human authorization.

## Initial implementation slice

This increment adds:

- typed agent-invocation boundaries;
- deterministic execution lifecycle transitions;
- graph validation for cycles, schemas, authorization and idempotency;
- bounded token, cost and three-attempt repair budgets;
- exact commit/tree-bound authorization packets;
- immutable hash-chained evidence receipts;
- JSON schemas and adversarial regression tests.

It does not add:

- an iOS application;
- Cloud Run deployment;
- Google Cloud resource creation;
- Gemini calls;
- public access;
- Gmail sending;
- GitHub merge authority;
- financial authority;
- production activation.

## Invariants

1. No unvalidated transition produces an external effect.
2. Every external operation requires exact authorization.
3. Every artifact binds to commit SHA, tree SHA, schema version and digest.
4. Every external retry is idempotent or uncertain.
5. Every secret reference is purpose-bound and version-pinned.
6. Every agent output crosses a typed schema boundary.
7. Every future deployment must use an immutable image digest.
8. Every production claim requires runtime evidence.
9. No jurisdiction claim exceeds provider receipts.
10. No repair bypasses testing, review or authorization.

## Authority state

```text
repository_analysis=true
architecture_generation=true
code_generation=true
test_generation=true
pull_request_creation=true

cloud_resource_creation=false
deployment=false
production_activation=false
public_access=false
live_model_calls=false
financial_actions=false
automatic_merge=false
```

## Admission rule

Keep the pull request draft and unmerged. Require complete diff review and a new pull-request-triggered exact-head hosted CI receipt. CI success authorizes governed review only.
