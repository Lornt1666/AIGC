# AIGC Truth → Method → WorkAttempt → Evidence Invariant v1

## Constitutional law

> **Occupational Control issues immutable truth. Method proposes how. WorkAttempt executes. Evidence proves what happened. Execution can never rewrite the contract that authorized it.**

This invariant is normative for AIGC occupational autonomy. Any runtime implementation, compatibility layer, agent, model, tool, MethodGenome, TaskGraph, Quest alias, retry controller, evaluator, delivery path, or learning loop that violates it is non-compliant.

## Four authoritative roles

### 1. Occupational Control — truth

Occupational Control owns the accepted and versioned professional truth that authorizes work:

- `CareerConstitution`;
- `CareerMandate@version`;
- sealed `WorkCommission@revision` + SHA-256;
- sealed `OutcomeContract@revision` + SHA-256;
- `AuthorityEnvelope`;
- admitted discipline and competency requirements;
- applicable policy version.

After acceptance, a WorkCommission or OutcomeContract revision is immutable. Material change creates a new revision with explicit lineage; it does not alter the prior authorization basis.

### 2. Method Plane — proposal

The Method Plane may propose and compare `MethodGenome` and `TaskGraph` candidates. It may optimize the means of satisfying the sealed occupational truth, but it may not broaden scope, grant authority, weaken completion gates, change risk classification, invent credentials, or redefine the requested outcome.

If a method requires a material change to governing truth, it emits an amendment request and stops that path until a new occupational revision is admitted.

### 3. Work Execution Plane — attempt

`WorkAttempt` is the sole mutable execution aggregate. It may change execution state, checkpoints, tool calls, retries, staged artifacts, worktree state, and method-selection state only.

Every attempt is pinned to:

```text
commission_id
commission_revision
commission_sha256
outcome_contract_id
outcome_contract_revision
outcome_contract_sha256
career_mandate_id
career_mandate_version
policy_version
method_genome_id / task_graph_version
```

Before every consequential transition the controller must revalidate these bindings. If any governing record is changed, superseded, revoked, expired, or no longer current, consequential execution fails closed and the WorkAttempt enters `STALE_AUTHORIZATION` or `SUPERSEDED`.

A new admitted occupational revision requires a new WorkAttempt. Authority and approval are never silently inherited across material revisions.

### 4. Evidence Plane — proof

Evidence records observed facts about a specific WorkAttempt; it does not grant authority or mutate occupational truth.

Every evidence receipt must bind to:

- the exact WorkAttempt identity and mutable execution revision;
- the same exact occupational binding used by that attempt;
- relevant artifact digests;
- verifier identity/type;
- observation time;
- independent-verification status where required;
- external-state freshness where external truth is claimed.

Canonical machine-readable receipt contract:

- `schemas/aigc_work_evidence_receipt.schema.json`

## Formal model

```text
OccupationalTruth :=
    CareerMandate@version
    + WorkCommission@revision+digest
    + OutcomeContract@revision+digest
    + AuthorityEnvelope
    + Policy@version

MethodProposal :=
    propose(OccupationalTruth, admitted_capabilities, constraints, evaluators)

WorkAttempt :=
    execute(MethodProposal)
    while exact_binding(OccupationalTruth)

Evidence :=
    record_and_verify(WorkAttempt, observed_effects, results, provenance)
```

## Drift law

```text
IF
    commission_revision_or_digest_changed
    OR outcome_contract_revision_or_digest_changed
    OR career_mandate_version_changed
    OR policy_version_changed
    OR authority_revoked_or_expired
THEN
    WorkAttempt.status = STALE_AUTHORIZATION | SUPERSEDED
    consequential_execution = DENY
    stale_approval_reuse = DENY
    new_WorkAttempt_required = true
```

## Non-interference laws

1. Method may read occupational truth but may not write it.
2. WorkAttempt may read occupational truth but may not write it.
3. Evidence may describe WorkAttempt and occupational bindings but may not grant authority or alter either.
4. A WorkAttempt cannot declare its own evidence sufficient when independent verification is required.
5. A generated narrative cannot create portfolio experience without attempt-bound delivery evidence.
6. Quest compatibility state cannot mutate or outrank WorkCommission or WorkAttempt state.
7. Learning proposals may improve methods but may not retroactively alter the truth or evidence of completed attempts.
8. Completion is evaluated against the sealed OutcomeContract, never against an execution-time reinterpretation.

## Required runtime acceptance properties

Before AIGC claims this invariant is runtime-enforced, tests must prove:

1. Mutation of a sealed WorkCommission is rejected.
2. Mutation of a sealed OutcomeContract is rejected.
3. Method code cannot write occupational authority fields.
4. WorkAttempt creation requires exact revision/digest bindings.
5. A changed commission digest causes `STALE_AUTHORIZATION` before consequential execution.
6. A superseded commission causes the old attempt to stop.
7. A new revision cannot reuse an approval bound to an old attempt/action digest.
8. Evidence receipts reject mismatched WorkAttempt/occupational bindings.
9. Evidence cannot transition authority state.
10. Quest compatibility code cannot become canonical authority.
11. Completion fails when required evidence is absent or bound to another attempt.
12. Independent-verification requirements fail closed when the verifier is not independent of the authoring lineage.

## Architectural shorthand

```text
TRUTH  → METHOD → ATTEMPT → PROOF
  |         |        |         |
immutable proposal  mutable   append-only / observed
  |         |        |         |
  +---------+--------+---------+
            exact binding
```

The boundary is intentional: **execution is powerful enough to perform the work, but structurally incapable of rewriting why it was permitted to perform that work.**
