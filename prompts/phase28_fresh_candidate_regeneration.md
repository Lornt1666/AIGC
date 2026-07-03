# Phase 28 - Fresh Candidate Regeneration Controller

Phase 28 converts Phase 27 renewal records into fresh internal Phase 4 and Phase 5 candidate payloads only after an explicit operator-approved freshness review.

It is not a live execution layer. It does not browse, fetch data, overwrite canonical Phase 4 or Phase 5 files, approve actions, authorize Phase 6, contact employers, submit proposals, submit applications, submit deliverables, accept contracts, request payment, or use credentials.

## Regeneration Gate

Phase 28 may create regenerated candidates only when all configured freshness-review controls are satisfied:

- `approved` is true.
- `freshness_review_status` is `approved_for_internal_regeneration`.
- `review_id` and `reviewed_at` are present.
- source currentness, scope, compliance, quality plan, and payment/contract review flags are true.
- `allowed_output_mode` is `internal_candidate_only`.
- the received phrase exactly matches the required operator phrase.

If any control fails, Phase 28 creates blocked regeneration records with no embedded Phase 4 or Phase 5 candidate.

## Candidate Boundary

When the gate passes, Phase 28 creates only internal candidate payloads inside its own ledger:

- `fresh_phase4_candidate`
- `fresh_phase5_candidate`

These payloads remain pending candidates. The Phase 5 candidate is not approved, its Phase 6 status is false, and all external action remains blocked.

## Truth Principle

Phase 27 is the only input source for regeneration. Old Phase 4 and Phase 5 artifacts remain historical derivatives. Old action IDs are retained only for audit lineage and cannot be approved.
