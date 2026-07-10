# AIGC Production Readiness Ledger

## Purpose

The Production Readiness Ledger gives AIGC one canonical, evidence-backed answer to:

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
