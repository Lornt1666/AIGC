# AIGC Production Readiness Ledger

## Purpose

The Production Readiness Ledger gives AIGC one canonical, structurally evidenced answer to:

> What is complete, what is internal-only, what is partial, what is planned, and what still blocks production?

The ledger prevents recursive evolution from confusing activity with progress. A capability cannot remain `complete` or `implemented_internal` when its required repository evidence is absent.

## Run

```powershell
python .\src\production_readiness_ledger_cli.py
```

Outputs:

```text
reports/artifacts/production_readiness/<report_id>/production_readiness_report.json
reports/artifacts/production_readiness/<report_id>/production_readiness_report.md
```

## Status Model

- `complete` — implemented, evidenced, and suitable for its stated production scope.
- `implemented_internal` — operational inside AIGC but not a finished external production capability.
- `partial` — meaningful implementation exists, but one or more required layers are missing.
- `planned` — contract or design exists without sufficient implementation.
- `stale` — evidence exists but is no longer current or authoritative.
- `unimplemented` — no implementation evidence exists.
- `superseded` — replaced by a canonical newer capability.

## Truth Controls

The evaluator enforces:

1. Missing evidence downgrades completion claims.
2. A production-ready claim requires the weighted threshold.
3. A production-ready claim also requires zero blocking gaps.
4. Every report remains operator-reviewable.
5. No external action is performed.

## Current Highest-Impact Gap

The initial registry identifies production identity and access management as the highest-impact missing blocker:

- authenticated users;
- authorization and least privilege;
- secure sessions;
- tenant/project isolation;
- revocation and expiry;
- audit linkage;
- integration with observer authority and the Security & Privacy Wiring Gate.

This ledger does not implement identity infrastructure. It proves that identity is the proper next contract-first implementation PR.

## Evolution Cycle

```text
repository evidence
→ capability status validation
→ unsupported-claim downgrade
→ weighted readiness score
→ blocking-gap detection
→ one highest-impact next step
→ operator review
→ separate implementation PR
```

The ledger is the measurable metabolism of AIGC evolution: each future cycle must change evidence, status, readiness score, or blocker state rather than merely generate new language.

## Evidence Boundary

The ledger's current evidence model is `structural_repository_evidence_v2`.

It verifies non-empty repository paths and binds each report to the evaluated Git revision. This is stronger than filename existence alone, but it is intentionally labelled `structural_not_operational_proof`.

A source file, schema, or test file can prove that an implementation artifact exists. It cannot by itself prove runtime reliability, production security, recovery, performance, or user outcomes. Those maturity claims require later test, runtime, staging, monitoring, and recovery receipts.

Empty files and empty placeholder directories never count as evidence. Unknown Git revisions are recorded explicitly as `unbound`; they are not silently treated as verified.

## Unified CLI and CI

Run the non-blocking assessment:

```powershell
python .\src\aigc.py readiness
```

Require a production-ready result for a future release gate:

```powershell
python .\src\aigc.py readiness --require-production-ready
```

The CI workflow runs the assessment and uploads the revision-bound readiness receipt. It does not claim production readiness while blocking gaps remain.
