# PIBC-v1 Rollback Runbook

## Trigger conditions

Rollback the runtime wiring when PIBC-v1 causes import failures, migration failures, regression-test failures, incorrect permit behavior, receipt-integrity failures, or unexpected disclosure of identity material.

## Procedure

1. Keep the pull request unmerged while CI or review findings remain unresolved.
2. If merged later under separate authority, revert the PIBC-v1 implementation commits or disable the identity-boundary composition path through a separately reviewed change.
3. Do not delete `identity_evidence_receipts` or rewrite prior receipts.
4. Retain migration `0002_identity_boundary_v1.sql`; an additive unused table is safer than destructive rollback.
5. Verify the existing authorization and Quest tests against the restored composition path.
6. Run database integrity checks and confirm append-only receipt triggers remain intact.
7. Record the reverted exact revision, reason, CI evidence, and operator decision.

## Recovery criterion

Recovery is complete only when the prior local operator API and Quest lifecycle are green under CI, no receipt evidence was deleted, and production readiness remains false unless independently proven.

Rollback does not authorize deployment or external action.
