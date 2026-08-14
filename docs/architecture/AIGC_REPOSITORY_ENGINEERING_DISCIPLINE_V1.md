# AIGC Repository Engineering Discipline v1

## Purpose

`REPOSITORY_ENGINEERING` is a bounded occupational discipline within AIGC. It is not AIGC itself and it is not an authority source. Its purpose is to map, repair, reorganize, modernize, test, document, and operationalize software repositories under an immutable `WorkCommission` and `OutcomeContract`.

This discipline implements the constitutional law:

> Occupational Control issues immutable truth. Method proposes how. WorkAttempt executes. Evidence proves what happened. Execution can never rewrite the contract that authorized it.

## Write eligibility

Repository mutation is forbidden until all five conditions pass:

```text
WRITE_ELIGIBLE :=
    RepositoryMapped
    AND RequirementsBound
    AND ImpactAnalyzed
    AND WorkAttemptValid
    AND AuthorityValid
```

A repository may be messy without being wrong. Organization, refactoring, cleanup, deletion, relocation, dependency replacement, or framework migration must therefore be justified by the active OutcomeContract or by an admitted dependency of that contract.

## RepositoryAtlas

Before mutation, the discipline constructs a versioned `RepositoryAtlas` containing at least:

- `FileGraph`
- `SymbolGraph`
- `ImportGraph`
- `CallGraph`
- `TestCoverageGraph`
- `ConfigurationGraph`
- `BuildGraph`
- `DeploymentGraph`
- `DataFlowGraph`
- `AuthorityBoundaryGraph`
- `EvidenceGraph`
- `RequirementTraceabilityGraph`

The atlas must bind to an exact repository revision and record coverage/unknowns. Unknown regions reduce confidence; they do not become assumed facts.

## Core capabilities

The discipline capability catalog is:

1. `repo.discover`
2. `repo.atlas.build`
3. `repo.requirements.trace`
4. `repo.architecture.analyze`
5. `repo.dependency.analyze`
6. `repo.dead_code.detect`
7. `repo.change.plan`
8. `repo.impact.predict`
9. `repo.worktree.create`
10. `repo.patch.execute`
11. `repo.build.verify`
12. `repo.tests.verify`
13. `repo.architecture.verify`
14. `repo.security.verify`
15. `repo.diff.review`
16. `repo.evidence.emit`
17. `repo.pr.prepare`

Capabilities 1–8 and 11–17 are read-only or verification-oriented unless their implementation explicitly requires an admitted local artifact write. Capabilities 9–10 are mutation capabilities and require `WRITE_ELIGIBLE`.

## MethodGenome catalog

Each commission selects one bounded method class. Different classes have different gates.

- `BUG_REPAIR`
- `FEATURE_IMPLEMENTATION`
- `REPOSITORY_REFORMATION`
- `ARCHITECTURE_MIGRATION`
- `DEPENDENCY_MODERNIZATION`
- `TEST_HARDENING`
- `CI_REPAIR`
- `SECURITY_HARDENING`
- `DOCUMENTATION_RECONSTRUCTION`
- `OPERATIONALIZATION`
- `DEAD_CODE_ELIMINATION`
- `RELEASE_PREPARATION`

A method may propose a different strategy but may not silently change the commission's requested outcome, authority, risk tier, target repository, or completion gates.

## Scope-expansion classification

New discoveries are classified before work continues:

```text
required for current OutcomeContract -> ADMITTED_DEPENDENCY
unrelated defect                         -> FINDING
architectural improvement                -> IMPROVEMENT_PROPOSAL
security issue that blocks current work  -> BLOCKING_FINDING
material scope expansion                 -> COMMISSION_AMENDMENT_PROPOSAL
```

Only `ADMITTED_DEPENDENCY` may enter the active TaskGraph without a new occupational decision. A `COMMISSION_AMENDMENT_PROPOSAL` never mutates the active WorkCommission.

## Multi-agent topology

Parallelize discovery and independent verification. Serialize authoritative mutation.

```text
                 ORCHESTRATOR
                      |
        +-------------+-------------+
        v             v             v
 Architecture      Security      Test Scout
    Scout            Scout
        \             |             /
         +------------+------------+
                      v
                 CHANGE PLAN
                      |
                      v
          AUTHORITATIVE WRITER
                      |
                      v
                candidate diff
                      |
        +-------------+-------------+
        v             v             v
      Tests        Security     Architecture
                                Verification
        \             |             /
         +------------+------------+
                      v
                   EVIDENCE
```

One authoritative writer owns the mutable worktree for a WorkAttempt. Scouts and evaluators are read-only with respect to that worktree unless a separate sub-artifact contract explicitly permits otherwise.

## Evaluation mesh

Minimum verification depends on method class and repository language, but the discipline must support:

- existing unit/integration/end-to-end tests;
- requirements-derived tests;
- static/type/compiler checks;
- architecture fitness checks;
- property-based tests where meaningful;
- mutation testing where meaningful;
- secret and security scanning;
- dependency/license analysis;
- exact-diff review;
- reproducible evidence receipts.

High-risk changes cannot be accepted solely from tests authored by the same execution lineage that produced the implementation.

## Evidence

A repository-engineering WorkAttempt must be able to emit:

- exact repository/base/head/tree identities;
- WorkCommission and OutcomeContract revisions/digests;
- RepositoryAtlas revision/digest;
- commands/tool actions executed;
- changed-file manifest;
- test and evaluator results;
- artifact digests;
- unresolved findings and their dispositions;
- completion assessment;
- rollback/recovery information when applicable.

Evidence may establish what happened. It cannot grant authority or expand scope.

## Self-hosting rule

AIGC may use its own repository as a Repository Engineering commission, but the agent executing that commission remains bound to the same contracts as it would for an external repository. Self-hosting never permits self-authorization.

The first self-hosting target is the runtime implementation of:

```text
WorkCommission -> MethodGenome -> WorkAttempt -> Evidence
```

inside AIGC itself.

The implementation must preserve the existing bounded-autodesign, authority, evidence, no-progress, one-writer, and independent-verification invariants.
